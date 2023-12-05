import os
import json
import time
import urllib
import subprocess
import tempfile

from rich.syntax import Syntax
from rich.traceback import Traceback

from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll
from textual.reactive import var
from textual.widgets import Tree, Markdown, Footer, Header, Static

import boto3

import cwlog


class SuspendTui:
    
    def __init__(self, app):
        self.app = app
    
    def __enter__(self):
        self.app._driver.stop_application_mode()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.app.refresh()
        self.app._driver.start_application_mode()


class HyperPodClient:

    def __init__(self):
        self.sagemaker_client = boto3.client("sagemaker")

    def list_clusters(self):

        clusters = []    
        next_token = None

        while True:
            
            params = {}
            if next_token:
                params["NextToken"] = next_token

            response = self.sagemaker_client.list_clusters(**params)

            for cluster in response["ClusterSummaries"]:
                cluster = self.sagemaker_client.describe_cluster(
                    ClusterName = cluster["ClusterName"]
                )
                clusters.append(cluster)

            if "NextToken" not in response or not response["NextToken"]:
                break

        return clusters


    def list_cluster_nodes(self, cluster_name):

        nodes = {}
        next_token = None

        while True:
            
            params = {
                "ClusterName" : cluster_name
            }
            if next_token:
                params["NextToken"] = next_token

            response = self.sagemaker_client.list_cluster_nodes(**params)

            for node in response["ClusterNodeSummaries"]:
                instance_group_name = node["InstanceGroupName"]
                if instance_group_name not in nodes:
                    nodes[instance_group_name] = []
                nodes[instance_group_name].append(node)

            if "NextToken" not in response or not response["NextToken"]:
                break

        return nodes        


class BaseTreeData:
    pass

class ClusterTreeData(BaseTreeData):
    pass

class InstanceGroupTreeData(BaseTreeData):
    pass

class InstanceTreeData(BaseTreeData):
    pass


class HyperPodExplorer(App):

    CSS_PATH = "default.tcss"
    BINDINGS = [
        ("f", "toggle_tree_pane", "Toggle Tree Pane"),
        ("q", "quit", "Quit"),
    ]

    show_tree = var(True)

    def __init__(self,**args):
        super().__init__(**args)
        self.hyperpod_client = HyperPodClient()

    def watch_show_tree(self, show_tree: bool) -> None:
        self.set_class(show_tree, "-show-tree")

    def compose(self) -> ComposeResult:
        yield Header()
        with Container():

            # Left tree pane            
            tree: Tree[BaseTreeData] = Tree("My clusters", id="tree-view", data=None)
            
            tree.root.expand()

            clusters = self.hyperpod_client.list_clusters()
            for cluster in clusters:
                
                nodes = self.hyperpod_client.list_cluster_nodes(cluster["ClusterName"])

                cluster_tree_data = ClusterTreeData()
                cluster_tree_data.cluster_name = cluster["ClusterName"]
                cluster_tree_data.cluster_status = cluster["ClusterStatus"]
                cluster_tree_data.arn = cluster["ClusterArn"]
                cluster_tree_data.cluster_id = cluster["ClusterArn"].split("/")[-1]
                cluster_tree_data.creation_time = cluster["CreationTime"]
                if "FailureMessage" in cluster:
                    cluster_tree_data.message = cluster["FailureMessage"]
                else:
                    cluster_tree_data.message = None

                tree_item_cluster = tree.root.add(cluster["ClusterName"], data=cluster_tree_data, expand=False)

                for instance_group in cluster["InstanceGroups"]:

                    instance_group_name = instance_group["InstanceGroupName"]

                    instance_group_tree_data = InstanceGroupTreeData()
                    instance_group_tree_data.instance_group_name = instance_group_name

                    instance_group_tree_data.instance_group_name = instance_group["InstanceGroupName"]
                    instance_group_tree_data.current_count = instance_group["CurrentCount"]
                    instance_group_tree_data.target_count = instance_group["CurrentCount"]
                    instance_group_tree_data.instance_type = instance_group["InstanceType"]
                    instance_group_tree_data.threads_per_core = instance_group["ThreadsPerCore"]
                    instance_group_tree_data.role_arn = instance_group["ExecutionRole"]
                    instance_group_tree_data.lcc_s3_uri = instance_group["LifeCycleConfig"]["SourceS3Uri"]
                    instance_group_tree_data.creatation_script = instance_group["LifeCycleConfig"]["OnCreate"]

                    tree_item_instance_group = tree_item_cluster.add(instance_group_name, data=instance_group_tree_data, expand=False)

                    if instance_group_name in nodes:
                        for node in nodes[instance_group_name]:
                            
                            node_id = node["InstanceId"]

                            instance_tree_data = InstanceTreeData()
                            instance_tree_data.instance_id = node["InstanceId"]
                            instance_tree_data.instance_type = node["InstanceType"]
                            instance_tree_data.instance_group_name = node["InstanceGroupName"]
                            instance_tree_data.instance_status = node["InstanceStatus"]["Status"]
                            instance_tree_data.message = node["InstanceStatus"]["Message"]
                            instance_tree_data.ssm_target = f"sagemaker-cluster:{cluster_tree_data.cluster_id}_{instance_group_name}-{instance_tree_data.instance_id}"
                            instance_tree_data.log_group = f"/aws/sagemaker/Clusters/{cluster_tree_data.cluster_name}/{cluster_tree_data.cluster_id}"
                            instance_tree_data.log_stream = f"LifecycleConfig/{instance_group_name}/{instance_tree_data.instance_id}"
                            instance_tree_data.cluster_creation_time = cluster_tree_data.creation_time

                            tree_item_node = tree_item_instance_group.add_leaf(node_id, data=instance_tree_data)

            yield tree

            with VerticalScroll(id="right-pane"):
                yield Markdown(markdown=self.format_welcome_markdown(), id="details")

        yield Footer()

    def on_mount(self) -> None:
        self.query_one(Tree).focus()

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:

        event.stop()

        details_view = self.query_one("#details", Markdown)
        details_view.update(markdown=self.format_markdown(event.node.data))
        self.query_one("#right-pane").scroll_home(animate=False)

    def on_markdown_link_clicked(self, event: Markdown.LinkClicked) -> None:

        event.stop()

        self.log("on_markdown_link_clicked",event.href)

        parsed_href = urllib.parse.urlparse(event.href)
        parsed_query = urllib.parse.parse_qs(parsed_href.query)
        if parsed_href.scheme == "ssm":
            if parsed_href.path == "/start-session":
                self.run_ssm_session(parsed_query["target"][0])
        elif parsed_href.scheme == "logs":
            if parsed_href.path == "/view-log-stream":
                self.run_logs_viewer(parsed_query["group"][0], parsed_query["stream"][0], int(parsed_query["start-time"][0]))

    def run_ssm_session( self, ssm_target ):

        self.log("run_ssm_session")

        with SuspendTui(self):
            subprocess.run( ["aws", "ssm", "start-session", "--target", ssm_target] )

    def run_logs_viewer( self, log_group, stream, start_time ):

        self.log("run_logs_viewer")

        with tempfile.TemporaryDirectory() as log_output_dir:

            output_filename = os.path.join(log_output_dir,"log.txt")
            with open(output_filename, "w") as fd:

                with SuspendTui(self):

                    th = cwlog.CloudWatchLogsStreamDumpThread(log_group=log_group, stream=stream, start_time=start_time, fd=fd)
                    th.start()
            
                    try:
                        subprocess.run( ["tail", "-f", output_filename] )
                    except KeyboardInterrupt:
                        pass

                    th.cancel()
                    th.join()

    def action_toggle_tree_pane(self) -> None:
        self.show_tree = not self.show_tree

    def format_markdown(self, tree_data):

        if tree_data is None:
            return self.format_welcome_markdown()

        elif isinstance(tree_data,ClusterTreeData):
            return self.format_cluster_markdown(tree_data)

        elif isinstance(tree_data,InstanceGroupTreeData):
            return self.format_instance_group_markdown(tree_data)

        elif isinstance(tree_data,InstanceTreeData):
            return self.format_node_markdown(tree_data)
        
        else:
            assert False, f"Unknown tree data type - type(tree_data)"

    def format_welcome_markdown(self):

        lines = []
        
        lines.append( f"# Welcome to HyperPod Explorer" )
        lines.append( f"Xyz" )
        lines.append( f"## Features" )
        lines.append( f"- 111" )
        lines.append( f"- 222" )
        lines.append( f"- 333" )
        lines.append( f"## How to use" )
        lines.append( f"Sample usage here." )

        return "\n".join(lines)

    def format_cluster_markdown(self, data):

        lines = []
        
        lines.append( f"## Cluster - [{data.cluster_name}]" )

        lines.append( f"#### Status" )

        lines.append( f"| Name | Value |" )
        lines.append( f"| ---- | ----- |" )
        lines.append( f"| Name | {data.cluster_name} |" )
        lines.append( f"| Status | {data.cluster_status} |" )
        creation_time_s = data.creation_time.strftime("%Y/%m/%d %H:%M:%S")
        lines.append( f"| Creation time | {creation_time_s} |" )
        lines.append( f"| Arn | {data.arn} |" )

        if data.message is not None:
            message = data.message
        else:
            message = "(empty)"

        lines.append( f"#### Message" )
        lines.append( f"```" )
        for line in message.splitlines():
            lines.append(f"{line}")
        lines.append( f"```" )

        return "\n".join(lines)

    def format_instance_group_markdown(self, data):

        lines = []
        
        lines.append( f"## Instance group - [{data.instance_group_name}]" )

        lines.append( f"#### Status" )

        lines.append( f"| Name | Value |" )
        lines.append( f"| ---- | ----- |" )
        lines.append( f"| Name | {data.instance_group_name} |" )
        lines.append( f"| Count | {data.current_count} / {data.target_count} |" )
        lines.append( f"| Type | {data.instance_type} |" )
        lines.append( f"| Threads per core | {data.threads_per_core} |" )
        lines.append( f"| IAM Role | {data.role_arn} |" )

        lines.append( f"" )

        lines.append( f"#### Creation configuration" )

        lines.append( f"| Name | Value |" )
        lines.append( f"| ---- | ----- |" )
        lines.append( f"| S3 Uri | {data.lcc_s3_uri} |" )
        lines.append( f"| Creation script | {data.creatation_script} |" )

        return "\n".join(lines)

    def format_node_markdown(self, data):

        lines = []
        
        lines.append( f"## Node - [{data.instance_id}]" )

        lines.append( f"#### Status" )

        lines.append( f"| Name | Value |" )
        lines.append( f"| ---- | ----- |" )
        lines.append( f"| Instance ID | {data.instance_id} |" )
        lines.append( f"| Type | {data.instance_type} |" )
        lines.append( f"| Status | {data.instance_status} |" )

        if data.message is not None:
            message = data.message
        else:
            message = "(empty)"

        lines.append( f"#### Message" )
        lines.append( f"```" )
        for line in message.splitlines():
            lines.append(f"{line}")
        lines.append( f"```" )

        lines.append( f"#### SSM session" )
        lines.append( f"  - Session target : {data.ssm_target}" )
        lines.append( f"  - [Connect](ssm://localhost/start-session?target={urllib.parse.quote(data.ssm_target)})" )

        lines.append( f"#### CloudWatch Log" )
        lines.append( f"  - Log group : {data.log_group}" )
        lines.append( f"  - Log stream : {data.log_stream}" )
        log_group_encoded = urllib.parse.quote(data.log_group)
        log_stream_encoded = urllib.parse.quote(data.log_stream)
        start_time = int(data.cluster_creation_time.timestamp() * 1000)
        lines.append( f"  - [View provisionin log](logs://localhost/view-log-stream?group={log_group_encoded}&stream={log_stream_encoded}&start-time={start_time})" )

        return "\n".join(lines)


if __name__ == "__main__":
    HyperPodExplorer().run()
