import json

from rich.syntax import Syntax
from rich.traceback import Traceback

from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll
from textual.reactive import var
from textual.widgets import Tree, Markdown, Footer, Header, Static

import boto3


EXAMPLE_MARKDOWN1 = """
# Markdown Document

This is an example of Textual's `Markdown` widget.

## Features

Markdown syntax and extensions are supported.

- Typography *emphasis*, **strong**, `inline code` etc.
- Headers
- Lists (bullet and ordered)
- Syntax highlighted code blocks
- Tables!
"""

EXAMPLE_MARKDOWN2 = """
| Month    | Savings |
| -------- | ------- |
| January  | $250    |
| February | $80     |
| March    | $420    |
| January  | $250    |
| February | $80     |
| March    | $420    |
| January  | $250    |
| February | $80     |
| March    | $420    |
| January  | $250    |
| February | $80     |
| March    | $420    |
| January  | $250    |
| February | $80     |
| March    | $420    |
| January  | $250    |
| February | $80     |
| March    | $420    |
| January  | $250    |
| February | $80     |
| March    | $420    |
"""

EXAMPLE_MARKDOWN3 = """
Hyperlink test [link](https://www.google.com/)
"""


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
            tree: Tree[dict] = Tree("My clusters", id="tree-view")
            
            tree.root.boto3_data = {}
            tree.root.expand()

            clusters = self.hyperpod_client.list_clusters()
            for cluster in clusters:
                
                nodes = self.hyperpod_client.list_cluster_nodes(cluster["ClusterName"])

                tree_item_cluster = tree.root.add(cluster["ClusterName"], expand=False)
                tree_item_cluster.boto3_data = {"Cluster":cluster}

                for instance_group in cluster["InstanceGroups"]:
                    instance_group_name = instance_group["InstanceGroupName"]
                    tree_item_instance_group = tree_item_cluster.add(instance_group_name, expand=False)
                    tree_item_instance_group.boto3_data = {"InstanceGroup":instance_group}

                    for node in nodes[instance_group_name]:
                        node_id = node["InstanceId"]
                        tree_item_node = tree_item_instance_group.add_leaf(node_id)
                        tree_item_node.boto3_data = {"ClusterNode":node}

            yield tree

            with VerticalScroll(id="right-pane"):
                yield Markdown(markdown=EXAMPLE_MARKDOWN1, id="details")

        yield Footer()

    def on_mount(self) -> None:
        self.query_one(Tree).focus()

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:

        event.stop()

        details_view = self.query_one("#details", Markdown)

        boto3_data = event.node.boto3_data

        if "Cluster" in boto3_data:
            markdown = self.format_cluster_markdown( boto3_data["Cluster"] )
            details_view.update(markdown=markdown)

        elif "InstanceGroup" in boto3_data:
            markdown = self.format_instance_group_markdown( boto3_data["InstanceGroup"] )
            details_view.update(markdown=markdown)

        elif "ClusterNode" in boto3_data:
            details_view.update(markdown=EXAMPLE_MARKDOWN3)
        
        else:
            return

        self.query_one("#right-pane").scroll_home(animate=False)

    def on_markdown_link_clicked(self, event: Markdown.LinkClicked) -> None:

        event.stop()

        self.log("on_markdown_link_clicked",event.href)

    def action_toggle_tree_pane(self) -> None:
        self.show_tree = not self.show_tree

    def format_cluster_markdown(self, cluster):

        cluster_name = cluster["ClusterName"]
        cluster_status = cluster['ClusterStatus']
        creation_time = cluster["CreationTime"].strftime("%Y/%m/%d %H:%M:%S")
        arn = cluster["ClusterArn"]

        lines = []
        
        lines.append( f"## Cluster - [{cluster_name}]" )

        lines.append( f"#### Status" )

        lines.append( f"| Name | Value |" )
        lines.append( f"| ---- | ----- |" )
        lines.append( f"| Name | {cluster_name} |" )
        lines.append( f"| Status | {cluster_status} |" )
        lines.append( f"| Creation time | {creation_time} |" )
        lines.append( f"| Arn | {arn} |" )

        if cluster_status=="Failed":

            message = json.loads(cluster["FailureMessage"])

            lines.append( f"#### Failure message" )
            lines.append( f"```" )
            for line in message["errorMessage"].splitlines():
                print(f"{line}")
            lines.append( f"```" )

        return "\n".join(lines)


    def format_instance_group_markdown(self, instance_group):

        instance_group_name = instance_group["InstanceGroupName"]
        current_count = instance_group["CurrentCount"]
        target_count = instance_group["CurrentCount"]
        instance_type = instance_group["InstanceType"]
        threads_per_core = instance_group["ThreadsPerCore"]
        role_arn = instance_group["ExecutionRole"]
        lcc_s3_uri = instance_group["LifeCycleConfig"]["SourceS3Uri"]
        creatation_script = instance_group["LifeCycleConfig"]["OnCreate"]

        lines = []
        
        lines.append( f"## Instance group - [{instance_group_name}]" )

        lines.append( f"#### Status" )

        lines.append( f"| Name | Value |" )
        lines.append( f"| ---- | ----- |" )
        lines.append( f"| Name | {instance_group_name} |" )
        lines.append( f"| Count | {current_count} / {target_count} |" )
        lines.append( f"| Type | {instance_type} |" )
        lines.append( f"| Threads per core | {threads_per_core} |" )
        lines.append( f"| IAM Role | {role_arn} |" )

        lines.append( f"" )

        lines.append( f"#### Creation configuration" )

        lines.append( f"| Name | Value |" )
        lines.append( f"| ---- | ----- |" )
        lines.append( f"| S3 Uri | {lcc_s3_uri} |" )
        lines.append( f"| Creation script | {creatation_script} |" )

        return "\n".join(lines)


if __name__ == "__main__":
    HyperPodExplorer().run()
