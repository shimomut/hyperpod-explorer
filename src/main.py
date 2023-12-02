import time

from rich.syntax import Syntax
from rich.traceback import Traceback

from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll
from textual.reactive import var
from textual.widgets import Tree, Markdown, Footer, Header, Static

import boto3


EXAMPLE_MARKDOWN = """\
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

EXAMPLE_MARKDOWN2 = """\
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
            tree.root.expand()

            clusters = self.hyperpod_client.list_clusters()
            for cluster in clusters:
                
                nodes = self.hyperpod_client.list_cluster_nodes(cluster["ClusterName"])

                tree_item_cluster = tree.root.add(cluster["ClusterName"], expand=False)
                tree_item_cluster.data = cluster

                for instance_group in cluster["InstanceGroups"]:
                    instance_group_name = instance_group["InstanceGroupName"]
                    tree_item_instance_group = tree_item_cluster.add(instance_group_name, expand=False)
                    tree_item_instance_group.data = tree_item_instance_group

                    for node in nodes[instance_group_name]:
                        node_id = node["InstanceId"]
                        tree_item_node = tree_item_instance_group.add_leaf(node_id)
                        tree_item_node.data = node

            yield tree

            #with VerticalScroll(id="code-view"):
            #    yield Static(id="code", expand=True)

            with VerticalScroll(id="right-pane"):
                yield Markdown(markdown=EXAMPLE_MARKDOWN, id="details")

        yield Footer()

    def on_mount(self) -> None:
        self.query_one(Tree).focus()

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        event.stop()
        details_view = self.query_one("#details", Markdown)

        details_view.update(markdown=EXAMPLE_MARKDOWN2)

        self.query_one("#right-pane").scroll_home(animate=False)
        self.sub_title = str(id(event))

    def action_toggle_tree_pane(self) -> None:
        self.show_tree = not self.show_tree


if __name__ == "__main__":
    HyperPodExplorer().run()
