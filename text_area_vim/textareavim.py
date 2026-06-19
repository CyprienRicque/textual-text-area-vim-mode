import logging
from textual import events
from textual.widgets import TextArea
from typing import Literal, override
from textual.document._document import Selection

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.FileHandler("debug.log"))

VimMode = Literal[
    "normal",
    "insert",
    "visual",
    "visual_line",
    "visual_block",
    "replace",
    "command",
    "terminal",
    "operator_pending",
]


class VimTextArea(TextArea):
    DEFAULT_CSS = """
    VimTextArea.normal-mode .text-area--cursor {
        background: $primary;
        color: $background;
        text-style: bold;
    }

    VimTextArea.insert-mode .text-area--cursor {
        background: black;
        color: lightblue;
        text-style: underline bold;
    }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cursor_blink = False
        self._vi_mode: VimMode = "normal"

    @override
    def on_mount(self) -> None:
        self._update_mode_styles()

    def _update_mode_styles(self) -> None:
        self.remove_class("normal-mode")
        self.remove_class("insert-mode")
        self.remove_class("visual-mode")
        if self._vi_mode == "normal":
            self.add_class("normal-mode")
        elif self._vi_mode == "insert":
            self.add_class("insert-mode")
        elif self._vi_mode == "visual":
            self.add_class("visual-mode")

    def action_cursor_absolute_line_start(self) -> None:
        """Move cursor to column 0 of the current line."""
        row, _ = self.cursor_location
        self.move_cursor((row, 0))

    @override
    async def _on_key(self, event: events.Key) -> None:
        if self._vi_mode == "normal":
            return await self._handle_normal_mode(event)
        elif self._vi_mode == "insert":
            return await self._handle_insert_mode(event)
        elif self._vi_mode == "visual":
            return await self._handle_visual_mode(event)
        elif self._vi_mode == "visual_line":
            return await self._handle_visual_line_mode(event)

    async def _handle_normal_mode(self, event: events.Key) -> None:
        logger.info(f"Key pressed {event.key}")
        event.prevent_default()
        if (handler := MODE_MAPPING.get(event.key)):
            handler(self)

    async def _handle_insert_mode(self, event: events.Key) -> None:
        if event.key == "escape":
            self._update_mode("normal")
            event.prevent_default()
            return

    async def _handle_visual_line_mode(self, event: events.Key) -> None:
        return await self._handle_visual_mode(event)  # TODO

    async def _handle_visual_mode(self, event: events.Key) -> None:
        event.prevent_default()
        if event.key == "escape":
            self._update_mode("normal")
            return
        if (handler := MODE_MAPPING.get(event.key)):
            handler(self)

    def enter_visual_mode(self) -> None:
        self.selection = Selection.cursor(self.cursor_location)
        self._update_mode("visual")

    def enter_line_visual_mode(self) -> None:
        current_row, current_col = self.cursor_location
        line = self.get_line(current_row)
        self.selection = Selection((current_row, 0), (current_row, len(line)))
        self.move_cursor((current_row, current_col))
        self._update_mode("visual_line")

    def enter_replace_mode(self) -> None:
        pass  # TODO

    def enter_insert_mode(self) -> None:
        self._vi_mode = "insert"
        self._update_mode_styles()

    def action_enter_insert_mode_after(self) -> None:
        self.action_cursor_right()
        self.enter_insert_mode()

    def action_enter_insert_mode_line_end(self) -> None:
        self.action_cursor_line_end()
        self.enter_insert_mode()

    def action_enter_insert_mode_line_start(self) -> None:
        self.action_cursor_line_start()
        self.enter_insert_mode()

    def action_cursor_left(self) -> None:
        select: bool = self._vi_mode == "visual"
        super().action_cursor_left(select=select)

    def action_cursor_down(self) -> None:
        select = self._vi_mode == "visual"
        super().action_cursor_down(select=select)

    def action_cursor_up(self) -> None:
        select = self._vi_mode == "visual"
        super().action_cursor_up(select=select)

    def action_cursor_right(self) -> None:
        select = self._vi_mode == "visual"
        super().action_cursor_right(select=select)

    def action_delete_right(self) -> None:
        super().action_delete_right()

    def action_cursor_line_end(self) -> None:
        select = self._vi_mode == "visual"
        super().action_cursor_line_end(select=select)

    def action_cursor_line_start(self) -> None:
        select = self._vi_mode == "visual"
        super().action_cursor_line_start(select=select)

    def action_cursor_word_right(self) -> None:
        select = self._vi_mode == "visual"
        super().action_cursor_word_right(select=select)

    def action_cursor_word_left(self) -> None:
        select = self._vi_mode == "visual"
        super().action_cursor_word_left(select=select)

    @override
    def _on_blur(self, event: events.Blur) -> None:
        if self._vi_mode != "normal":
            self._update_mode("normal")

    def _update_mode(self, mode: VimMode) -> None:
        self._vi_mode = mode
        self._update_mode_styles()

    @override
    def _on_focus(self, event: events.Focus) -> None:
        self._update_mode_styles()


MODE_MAPPING = {
    "h": VimTextArea.action_cursor_left,
    "j": VimTextArea.action_cursor_down,
    "k": VimTextArea.action_cursor_up,
    "l": VimTextArea.action_cursor_right,
    "x": VimTextArea.action_delete_right,
    "dollar_sign": VimTextArea.action_cursor_line_end,
    "0": VimTextArea.action_cursor_absolute_line_start,
    "underscore": VimTextArea.action_cursor_line_start,
    "w": VimTextArea.action_cursor_word_right,
    "b": VimTextArea.action_cursor_word_left,
    "I": VimTextArea.action_enter_insert_mode_line_start,
    "A": VimTextArea.action_enter_insert_mode_line_end,
    "a": VimTextArea.action_enter_insert_mode_after,
    "i": VimTextArea.enter_insert_mode,
    "v": VimTextArea.enter_visual_mode,
    "V": VimTextArea.enter_line_visual_mode,
    "r": VimTextArea.enter_replace_mode,
}
