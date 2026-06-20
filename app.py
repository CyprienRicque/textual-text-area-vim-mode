from typing import override, ClassVar
from textual.app import App, ComposeResult

from text_area_vim import VimTextArea


class ExampleVimApp(App[ComposeResult]):
    """Example application demonstrating VimTextArea."""

    CSS: ClassVar[str] = """
    Screen {
        align: center middle;
    }
    """

    @override
    def compose(self) -> ComposeResult:
        yield VimTextArea((
                "# Type here...\n"
                "# Press 'i' to enter insert mode.\n"
                "# Press \"Esc\" to return to normal mode.\n"
                "\n"
                "def main(oui: str):\n"
                "    pass\n"
                "\n"
                "{\n"
                "   \"oui\": \"non\"\n"
                "   1: 2\n"
                "}\n"

        ))

    def on_mount(self) -> None:
        self.title = "Example Application"
        self.sub_title = "a vim-based text area"


if __name__ == "__main__":
    app = ExampleVimApp()
    app.run()
