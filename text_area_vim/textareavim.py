import logging
from textual import events
from textual.widgets import TextArea
from typing import Literal, override, Callable, Annotated
from collections.abc import Awaitable
from textual.document._document import Selection
from pydantic import BaseModel, Field
from enum import StrEnum

from text_area_vim.find_motions import find_backward, find_forward

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.FileHandler("debug.log"))

Location = tuple[int, int]

VimMode = Literal[
    "normal",
    "insert",
    "visual",
    "visual_line",
    "visual_block",
    "replace",
    "command",
    "terminal",
]

_MODE_CLASSES = {
  "normal": "normal-mode",
  "insert": "insert-mode",
  "visual": "visual-mode",
  "replace": "replace-mode",
}

class RangeMotionChar(StrEnum):
    t = 't'
    f = 'f'
    T = 'T'
    F = 'F'


class SimpleMotionChar(StrEnum):
    end_of_line = "dollar_sign"
    start_of_line = "0"
    first_non_blank = "underscore"
    percent_sign = "percent_sign"


class RangeActionChar(StrEnum):
    delete = "d"
    change = "c"
    replace_ = "r"


class RangeMotion(BaseModel):
    type_: RangeMotionChar
    repeat: int | None = None
    char: str | None = None


class VimTextArea(TextArea):
    DEFAULT_CSS = """
    VimTextArea.normal-mode .text-area--cursor {
        background: $primary;
        color: $background;
        text-style: bold;
    }

    VimTextArea.replace-mode .text-area--cursor {
        background: black;
        color: lightblue;
        text-style: underline bold;
    }

    VimTextArea.insert-mode .text-area--cursor {
        background: yellow;
        color: $background;
        text-style: bold;
    }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cursor_blink = False
        self._vi_mode: VimMode = "normal"
        self._next_key_callback: Callable[..., Awaitable[bool]] | None = None
        self.current_action: RangeActionChar | None = None
        self.current_motion: RangeMotion | None = None

    @override
    def on_mount(self) -> None:
        self._update_mode_styles()

    def _update_mode_styles(self) -> None:
        for cls in _MODE_CLASSES.values():
            self.remove_class(cls)
        if mode_class := _MODE_CLASSES.get(self._vi_mode):
            self.add_class(mode_class)

    def action_cursor_absolute_line_start(self) -> None:
        row, _ = self.cursor_location
        self.move_cursor((row, 0))

    @override
    async def _on_key(self, event: events.Key) -> None:
        if self._next_key_callback:
            range_action_finished = await self._next_key_callback(event)
            event.prevent_default()
            if range_action_finished:
                self._next_key_callback = None
                self._update_mode("normal")
            return

        if self._vi_mode == "normal":
            return await self._handle_normal_mode(event)
        elif self._vi_mode == "replace":
            return await self._handle_replace_mode(event)
        elif self._vi_mode == "insert":
            return await self._handle_insert_mode(event)
        elif self._vi_mode == "visual":
            return await self._handle_visual_mode(event)
        elif self._vi_mode == "visual_line":
            return await self._handle_visual_line_mode(event)

    async def _handle_replace_mode(self, event: events.Key) -> None:
        if event.key == "escape":
            self._update_mode("normal")
            event.prevent_default()
            return

        self.action_delete_right()
        await super()._on_key(event)

    async def _handle_normal_mode(self, event: events.Key) -> None:
        logger.info(f"Key pressed {event.key} {event.character}")
        event.prevent_default()
        if (handler := MODE_MAPPING.get(event.key)):
            handler(self)

    async def _handle_insert_mode(self, event: events.Key) -> None:
        if event.key == "escape":
            self._update_mode("normal")
            event.prevent_default()
            return

    async def _handle_visual_line_mode(self, event: events.Key) -> None:
        event.prevent_default()
        if event.key == "escape":
            self._update_mode("normal")
            self.selection = Selection.cursor(self.cursor_location)
            return

        if (handler := VISUAL_LINE_MODE_MAPPING.get(event.key)):
            return handler(self)
        if (handler := MODE_MAPPING.get(event.key)):
            return handler(self)


    async def _handle_visual_mode(self, event: events.Key) -> None:
        event.prevent_default()
        if event.key == "escape":
            self.selection = Selection.cursor(self.cursor_location)
            self._update_mode("normal")
            return

        if (handler := MODE_MAPPING.get(event.key)):
            handler(self)

    def enter_visual_mode(self) -> None:
        self.selection = Selection.cursor(self.cursor_location)
        self._update_mode("visual")

    def enter_line_visual_mode(self) -> None:
        current_row, _ = self.cursor_location
        line = self.get_line(current_row)
        self.selection = Selection((current_row, 0), (current_row, len(line)))
        self._update_mode("visual_line")

    def enter_replace_mode(self) -> None:
        self._update_mode("replace")

    async def replace_char_with_key(self, event: events.Key) -> bool:
        self.action_delete_right()
        await super()._on_key(event)
        self.action_cursor_left()
        return True

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

    def jump_to_match(self) -> None:
        select = self._vi_mode == "visual"

    def action_cursor_word_right(self) -> None:
        select = self._vi_mode == "visual"
        super().action_cursor_word_right(select=select)

    def action_cursor_word_left(self) -> None:
        select = self._vi_mode == "visual"
        super().action_cursor_word_left(select=select)

    async def key_after_range_action_pressed(self, event: events.Key) -> bool:
        if event.key in RangeMotionChar:
            logger.info(f"Setting current_motion to {event.key} and within_range_motion_key_pressed")
            self.current_motion = RangeMotion(type_=RangeMotionChar(event.key))
            self._next_key_callback = self.within_range_motion_key_pressed
            return False
        
        if event.key not in SimpleMotionChar or not event.character:
            return True

        try:
            destination = get_single_motion_destination(
                motion_type=event.character,
                current_row=self.cursor_location[0],
                current_col=self.cursor_location[1],
                lines=self.document.lines
            )
            logger.info(f"{destination=}")
            if not destination:
                logger.info("no matching destination")
                return True
            self.execute_pending_action(destination)
        finally:
            self.current_action = None
            self.current_motion = None
        return True

    async def within_range_motion_key_pressed(self, event: events.Key) -> bool:
        logger.info(f"within_range_motion_key_pressed {event.key}")
        if not self.current_motion:
            raise ValueError("within_range_motion_key_pressed has no self.current_motion")

        if event.key in {"1", "2", "3", "4", "5", "6", "7", "8", "9"}:
            if not self.current_motion.repeat:
                self.current_motion.repeat = int(event.key)
            else:
                self.current_motion.repeat = self.current_motion.repeat * 10 + int(event.key)
            return False

        if not event.character:
            return True

        self.current_motion.char = event.character

        try:
            destination = self.resolve_destination()
            if not destination:
                logger.info("no matching destination")
                return True
            self.execute_pending_action(destination)
        finally:
            self.current_action = None
            self.current_motion = None
        return True

    def execute_pending_action(self, destination: Location):
        if not self.current_action:
            self.move_cursor(destination)
            return
        if self.current_action == RangeActionChar.delete:
            self.delete_to(destination)

    def delete_to(self, to: Location):
        self._delete_via_keyboard(self.cursor_location, to)

    def resolve_destination(self) -> tuple[int, int] | None:
        assert self.current_motion is not None
        assert self.current_motion.char is not None

        current_row, current_col = self.cursor_location
        char: str = self.current_motion.char
        lines: list[str] = self.document.lines

        mapping: dict[RangeMotionChar, Callable[[int, int, str, list[str]], tuple[int, int] | None]] = {
            RangeMotionChar.f: find_forward,
            RangeMotionChar.t: find_forward,
            RangeMotionChar.F: find_backward,
            RangeMotionChar.T: find_backward,
        }
        return mapping[self.current_motion.type_](
            current_row, current_col, char, lines
        )

    def range_action_c_key_pressed(self) -> None:
        self._next_key_callback = self.key_after_range_action_pressed
        self.current_action = RangeActionChar.change

    def range_action_r_key_pressed(self) -> None:
        self._next_key_callback = self.key_after_range_action_pressed
        self.current_action = RangeActionChar.replace_

    def range_action_d_key_pressed(self) -> None:
        logger.info("registering delete callback")
        self._next_key_callback = self.key_after_range_action_pressed
        self.current_action = RangeActionChar.delete

    def f_key_pressed_as_first_key(self) -> None:
        self.current_motion = RangeMotion(type_=RangeMotionChar.F)
        self._next_key_callback = self.within_range_motion_key_pressed

    def t_key_pressed_as_first_key(self) -> None:
        self.current_motion = RangeMotion(type_=RangeMotionChar.T)
        self._next_key_callback = self.within_range_motion_key_pressed

    def s_key_pressed(self) -> None:
        super().action_delete_right()
        self._update_mode("insert")

    def u_key_pressed(self):
        self.undo()

    def action_visual_line_cursor_down(self) -> None:
        current_row, _ = self.cursor_location
        if current_row + 1 >= self.document.line_count:
            return
        line = self.get_line(current_row + 1)
        self.selection = Selection(self.selection.start, (current_row + 1, len(line)))

    def action_visual_line_cursor_up(self) -> None:
        current_row, _ = self.cursor_location
        if current_row == 0:
            return
        self.selection = Selection((current_row - 1, 0), self.selection.end)

    @override
    def _on_blur(self, event: events.Blur) -> None:
        if self._vi_mode != "normal":
            self._update_mode("normal")

    def _update_mode(self, mode: VimMode) -> None:
        self._vi_mode = mode
        logger.info(f"{mode=}")
        self._update_mode_styles()

    @override
    def _on_focus(self, event: events.Focus) -> None:
        self._update_mode_styles()


MODE_MAPPING = {
    # Simple Motions
    "h": VimTextArea.action_cursor_left,
    "j": VimTextArea.action_cursor_down,
    "k": VimTextArea.action_cursor_up,
    "l": VimTextArea.action_cursor_right,
    "w": VimTextArea.action_cursor_word_right,
    "b": VimTextArea.action_cursor_word_left,
    SimpleMotionChar.end_of_line: VimTextArea.action_cursor_line_end,
    SimpleMotionChar.start_of_line: VimTextArea.action_cursor_absolute_line_start,
    SimpleMotionChar.first_non_blank: VimTextArea.action_cursor_line_start,
    SimpleMotionChar.percent_sign: VimTextArea.jump_to_match,

    # Complex motion 
    "f": VimTextArea.f_key_pressed_as_first_key,
    "t": VimTextArea.t_key_pressed_as_first_key,

    # Simple actions
    "x": VimTextArea.action_delete_right,
    "s": VimTextArea.s_key_pressed,
    "u": VimTextArea.u_key_pressed,

    # Mode change + motion
    "I": VimTextArea.action_enter_insert_mode_line_start,
    "A": VimTextArea.action_enter_insert_mode_line_end,
    "a": VimTextArea.action_enter_insert_mode_after,

    # Mode change
    "i": VimTextArea.enter_insert_mode,
    "v": VimTextArea.enter_visual_mode,
    "V": VimTextArea.enter_line_visual_mode,
    "R": VimTextArea.enter_replace_mode,

    # Range action
    RangeActionChar.change: VimTextArea.range_action_c_key_pressed,
    RangeActionChar.delete: VimTextArea.range_action_d_key_pressed,
    RangeActionChar.replace_: VimTextArea.range_action_r_key_pressed,
}

VISUAL_LINE_MODE_MAPPING = {
    "j": VimTextArea.action_visual_line_cursor_down,
    "k": VimTextArea.action_visual_line_cursor_up,
}


def get_single_motion_destination(
    motion_type: str,
    current_row: int,
    current_col: int,
    lines: list[str],
) -> tuple[int, int] | None:
    if motion_type == "underscore":
        # First non-blank character on current line
        line = lines[current_row] if current_row < len(lines) else ""
        for idx, char in enumerate(line):
            if char != " ":
                return (current_row, idx)
        return (current_row, 0)

    elif motion_type == "dollar_sign":
        line = lines[current_row] if current_row < len(lines) else ""
        return (current_row, len(line) - 1) if line else (current_row, 0)

    elif motion_type == "0":
        return (current_row, 0)

    return None

