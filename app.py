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
        yield VimTextArea("Type here...\nPress 'i' to enter insert mode.\nPress 'Esc' to return to normal mode.")

    def on_mount(self) -> None:
        self.title = "Example Application"
        self.sub_title = "a vim-based text area"


if __name__ == "__main__":
    app = ExampleVimApp()
    app.run()
