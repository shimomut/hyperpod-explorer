import time

from rich.syntax import Syntax
from rich.traceback import Traceback

from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll
from textual.reactive import var
from textual.widgets import Tree, Markdown, Footer, Header, Static

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

    print("re-enter test")
    time.sleep(10)

    HyperPodExplorer().run()
