from rich.syntax import Syntax
from rich.traceback import Traceback

from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll
from textual.reactive import var
from textual.widgets import Tree, Footer, Header, Static


class HyperPodExplorer(App):

    CSS_PATH = "default.tcss"
    BINDINGS = [
        ("f", "toggle_tree_pane", "Toggle Tree Pane"),
        ("q", "quit", "Quit"),
    ]

    show_tree = var(True)

    def watch_show_tree(self, show_tree: bool) -> None:
        self.set_class(show_tree, "-show-tree")

    def compose(self) -> ComposeResult:
        yield Header()
        with Container():

            # Left tree pane            
            tree: Tree[dict] = Tree("Dune", id="tree-view")
            tree.root.expand()
            characters = tree.root.add("Characters", expand=True)
            characters.add_leaf("Paul")
            characters.add_leaf("Jessica")
            characters.add_leaf("Chani")
            yield tree

            with VerticalScroll(id="code-view"):
                yield Static(id="code", expand=True)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(Tree).focus()

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        event.stop()
        code_view = self.query_one("#code", Static)

        syntax = Syntax.from_path(
            "main.py",
            line_numbers=True,
            word_wrap=False,
            indent_guides=True,
            theme="github-dark",
        )

        code_view.update(syntax)
        self.query_one("#code-view").scroll_home(animate=False)
        self.sub_title = str(id(event))

    def action_toggle_tree_pane(self) -> None:
        self.show_tree = not self.show_tree


if __name__ == "__main__":
    HyperPodExplorer().run()
