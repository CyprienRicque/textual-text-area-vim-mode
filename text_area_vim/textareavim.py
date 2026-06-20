import logging
from typing import Literal, override, Callable
from collections.abc import Awaitable
from enum import StrEnum

from pydantic import BaseModel
from textual import events
from textual.widgets import TextArea
from textual.document._document import Selection

from text_area_vim.find_motions import find_backward, find_forward, to_backward, to_forward
from text_area_vim.matching_pairs import find_around, find_inner, find_matching_pair
from text_area_vim.types import Location, RangeLocation


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
]

_MODE_CLASSES = {
  "normal": "normal-mode",
  "insert": "insert-mode",
  "visual": "visual-mode",
  "replace": "replace-mode",
  "operator_pending": "operator-pending",
}

class RangeMotionChar(StrEnum):
    t = 't'
    f = 'f'
    T = 'T'
    F = 'F'
    inner = 'i'
    around = 'a'


class SimpleMotionChar(StrEnum):
    dollar_sign = "dollar_sign"
    zero = "0"
    underscore = "underscore"
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

    VimTextArea.operator-pending .text-area--cursor {
        background: pink !important;
        color: $background;
        text-style: bold;
    }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cursor_blink = False
        self._vi_mode: VimMode = "normal"
        self._pending_action: RangeActionChar | None = None
        self._pending_motion: RangeMotion | None = None
        self._next_key_callback: Callable[..., Awaitable[bool]] | None = None
        self._first_vertical_move_on_visual_mode: Literal["up", "down"] | None = None

    @property
    def vi_mode(self) -> VimMode:
        return self._vi_mode

    @vi_mode.setter
    def vi_mode(self, value: VimMode) -> None:
        if self._vi_mode != value:
            self._vi_mode = value
            self._update_mode_styles()

    @property
    def pending_action(self) -> RangeActionChar | None:
        return self._pending_action

    @pending_action.setter
    def pending_action(self, value: RangeActionChar | None) -> None:
        if self._pending_action != value:
            self._pending_action = value
            self._update_mode_styles()

    @property
    def pending_motion(self) -> RangeMotion | None:
        return self._pending_motion

    @pending_motion.setter
    def pending_motion(self, value: RangeMotion | None) -> None:
        if self._pending_motion != value:
            self._pending_motion = value
            self._update_mode_styles()

    @property
    def next_key_callback(self) -> Callable[..., Awaitable[bool]] | None:
        return self._next_key_callback

    @next_key_callback.setter
    def next_key_callback(self, value: Callable[..., Awaitable[bool]] | None) -> None:
        if self._next_key_callback != value:
            self._next_key_callback = value
            self._update_mode_styles()

    @property
    def operator_pending(self) -> bool:
        return self.pending_action is not None or self.pending_motion is not None

    @override
    def on_mount(self) -> None:
        self._update_mode_styles()

    def _update_mode_styles(self) -> None:
        for cls in _MODE_CLASSES.values():
            self.remove_class(cls)
        if mode_class := _MODE_CLASSES.get(self.vi_mode):
            self.add_class(mode_class)
        if self.operator_pending:
            self.add_class(_MODE_CLASSES["operator_pending"])

    def action_cursor_absolute_line_start(self) -> None:
        row, _ = self.cursor_location
        self.context_aware_move_cursor((row, 0))

    @override
    async def _on_key(self, event: events.Key) -> None:
        if self.next_key_callback:
            range_action_finished = await self.next_key_callback(event)
            event.prevent_default()
            if range_action_finished:
                self.next_key_callback = None
            return

        if self.vi_mode == "normal":
            return await self._handle_normal_mode(event)
        elif self.vi_mode == "replace":
            return await self._handle_replace_mode(event)
        elif self.vi_mode == "insert":
            return await self._handle_insert_mode(event)
        elif self.vi_mode == "visual":
            return await self._handle_visual_mode(event)
        elif self.vi_mode == "visual_line":
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
        end = (self.cursor_location[0], self.cursor_location[1] + 1) 
        self.selection = Selection(self.cursor_location, end)
        self._update_mode("visual")

    def enter_line_visual_mode(self) -> None:
        current_row, _ = self.cursor_location
        line = self.get_line(current_row)
        self.selection = Selection((current_row, 0), (current_row, len(line)))
        self._update_mode("visual_line")

    def enter_replace_mode(self) -> None:
        self._update_mode("replace")

    async def replace_char_with_key(self, event: events.Key):
        self.action_delete_right()
        await super()._on_key(event)
        self.action_cursor_left()

    def enter_insert_mode(self) -> None:
        self.vi_mode = "insert"

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
        select: bool = self.vi_mode == "visual"
        super().action_cursor_left(select=select)

    def action_cursor_down(self) -> None:
        select = self.vi_mode == "visual"
        super().action_cursor_down(select=select)

    def action_cursor_up(self) -> None:
        select = self.vi_mode == "visual"
        super().action_cursor_up(select=select)

    def action_cursor_right(self) -> None:
        select = self.vi_mode == "visual"
        super().action_cursor_right(select=select)

    def action_delete_right(self) -> None:
        super().action_delete_right()

    def action_cursor_line_end(self) -> None:
        select = self.vi_mode == "visual"
        super().action_cursor_line_end(select=select)

    def action_cursor_line_start(self) -> None:
        select = self.vi_mode == "visual"
        super().action_cursor_line_start(select=select)

    def jump_to_match(self) -> None:
        select = self.vi_mode == "visual"

    def action_cursor_word_right(self) -> None:
        select = self.vi_mode == "visual"
        super().action_cursor_word_right(select=select)

    def action_cursor_word_left(self) -> None:
        select = self.vi_mode == "visual"
        super().action_cursor_word_left(select=select)

    async def key_after_range_action_pressed(self, event: events.Key) -> bool:
        if event.key in RangeMotionChar:
            logger.info(f"Setting current_motion to {event.key} and within_range_motion_key_pressed")
            self.pending_motion = RangeMotion(type_=RangeMotionChar(event.key))
            self.next_key_callback = self.within_range_motion_key_pressed
            return False
        
        if event.key not in SimpleMotionChar or not event.character:
            await self.replace_char_with_key(event)
            self._update_mode("normal")
            self.pending_action = None
            return True

        try:
            range_dest = self.get_single_motion_destination(
                motion_type=SimpleMotionChar(event.key),
                current_row=self.cursor_location[0],
                current_col=self.cursor_location[1],
                lines=self.document.lines
            )
            logger.info(f"{range_dest=}")
            if not range_dest:
                logger.info("no matching destination")
                return True

            self.execute_pending_action_motion(range_dest)
        finally:
            self.pending_action = None
            self.pending_motion = None
        return True

    async def within_range_motion_key_pressed(self, event: events.Key) -> bool:
        logger.info(f"within_range_motion_key_pressed {event.key}")
        if not self.pending_motion:
            raise ValueError("within_range_motion_key_pressed has no self.current_motion")

        if event.key in {"1", "2", "3", "4", "5", "6", "7", "8", "9"}:
            if not self.pending_motion.repeat:
                self.pending_motion.repeat = int(event.key)
            else:
                self.pending_motion.repeat = self.pending_motion.repeat * 10 + int(event.key)
            return False

        if not event.character:
            logger.warning(f"{event.key} has not char")
            return True

        self.pending_motion.char = event.character

        try:
            destination = self.resolve_destination()
            if not destination:
                logger.info(f"no matching destination for {self.pending_motion}")
                return True
            self.execute_pending_action_motion(destination)
        finally:
            self.pending_action = None
            self.pending_motion = None
        return True

    def execute_pending_action_motion(self, destination: RangeLocation):
        if not self.pending_action:
            self.context_aware_move_cursor(destination.end)
            return

        self.selection = Selection(destination.start, (destination.end[0], destination.end[1] + 1))

        if self.pending_action == RangeActionChar.delete:
            self.action_delete_left()
            self._update_mode("normal")
        if self.pending_action == RangeActionChar.change:
            self.action_delete_left()
            self._update_mode("insert")

    def delete_to(self, to: Location):
        self._delete_via_keyboard(self.cursor_location, to)

    def resolve_destination(self) -> RangeLocation | None:
        assert self.pending_motion is not None
        assert self.pending_motion.char is not None

        current_row, current_col = self.cursor_location
        char: str = self.pending_motion.char
        lines: list[str] = self.document.lines

        mapping: dict[RangeMotionChar, Callable[[int, int, str, list[str]], RangeLocation | None]] = {
            RangeMotionChar.f: find_forward,
            RangeMotionChar.t: to_forward,
            RangeMotionChar.F: find_backward,
            RangeMotionChar.T: to_backward,
            RangeMotionChar.inner: find_inner,
            RangeMotionChar.around: find_around,
        }
        fn = mapping[self.pending_motion.type_]
        return fn(
            current_row, current_col, char, lines
        )

    def range_action_c_key_pressed(self) -> None:
        logger.info(f"{self.selection}")
        self.next_key_callback = self.key_after_range_action_pressed
        self.pending_action = RangeActionChar.change

    def range_action_r_key_pressed(self) -> None:
        self.next_key_callback = self.key_after_range_action_pressed
        self.pending_action = RangeActionChar.replace_

    def range_action_d_key_pressed(self) -> None:
        logger.info("registering delete callback")
        self.next_key_callback = self.key_after_range_action_pressed
        self.pending_action = RangeActionChar.delete

    def f_key_pressed_as_first_key(self) -> None:
        self.pending_motion = RangeMotion(type_=RangeMotionChar.f)
        self.next_key_callback = self.within_range_motion_key_pressed

    def t_key_pressed_as_first_key(self) -> None:
        self.pending_motion = RangeMotion(type_=RangeMotionChar.t)
        self.next_key_callback = self.within_range_motion_key_pressed

    def F_key_pressed_as_first_key(self) -> None:
        self.pending_motion = RangeMotion(type_=RangeMotionChar.F)
        self.next_key_callback = self.within_range_motion_key_pressed

    def T_key_pressed_as_first_key(self) -> None:
        self.pending_motion = RangeMotion(type_=RangeMotionChar.T)
        self.next_key_callback = self.within_range_motion_key_pressed

    def s_key_pressed(self) -> None:
        super().action_delete_right()
        self._update_mode("insert")

    def u_key_pressed(self):
        self.undo()

    def ctrl_r_key_pressed(self):
        self.redo()

    def action_visual_line_cursor_down(self) -> None:
        if self.selection.start[0] == self.selection.end[0]:
            self._first_vertical_move_on_visual_mode = "down"
            if self.selection.start[1] > self.selection.end[1]:
                self.selection = Selection(self.selection.end, self.selection.start)

        if self._first_vertical_move_on_visual_mode == "down":
            if self.selection.end[0] == self.document.line_count:
                return
            line = self.get_line(self.selection.end[0] + 1)
            self.selection = Selection(self.selection.start, (self.selection.end[0] + 1, len(line)))
        else:
            if self.selection.start[0] == self.document.line_count:
                return
            self.selection = Selection(self.selection.start, (self.selection.end[0] + 1, 0))

    def action_visual_line_cursor_up(self) -> None:
        if self.selection.start[0] == self.selection.end[0]:
            self._first_vertical_move_on_visual_mode = "up"
            if self.selection.start[1] < self.selection.end[1]:
                self.selection = Selection(self.selection.end, self.selection.start)

        if self._first_vertical_move_on_visual_mode == "up":
            if self.selection.end[0] == 0:
                return
            start_line = self.get_line(self.selection.start[0])
            self.selection = Selection(
                (self.selection.start[0], len(start_line)),
                (self.selection.end[0] - 1, 0) 
            )
        else:
            if self.selection.end[0] == 0:
                return
            line = self.get_line(self.selection.end[0] - 1)
            self.selection = Selection(self.selection.start, (self.selection.end[0] - 1, len(line)))

    def context_aware_move_cursor(self, location: Location) -> None:  # FIXME: visual line mode
        select = self.vi_mode in {"visual", "visual_line"}
        logger.info(f"moving to {location=} with {select=}")
        super().move_cursor(location, select=select)

    def o_key_pressed(self) -> None:
        if self._first_vertical_move_on_visual_mode == "up":
            self._first_vertical_move_on_visual_mode = "down"
        else:
            self._first_vertical_move_on_visual_mode = "up"
        self.selection = Selection(self.selection.end, self.selection.start)

    @override
    def _on_blur(self, event: events.Blur) -> None:
        if self.vi_mode != "normal":
            self._update_mode("normal")

    def _update_mode(self, mode: VimMode) -> None:
        self.vi_mode = mode
        if self._vi_mode not in {"visual", "visual_line", "visual_block"}:
            self._first_vertical_move_on_visual_mode = None
        logger.info(f"{mode=}")

    @override
    def _on_focus(self, event: events.Focus) -> None:
        self._update_mode_styles()

    def get_single_motion_destination(
        self,
        motion_type: SimpleMotionChar,
        current_row: int,
        current_col: int,
        lines: list[str],
    ) -> RangeLocation | None:
        start: Location = (current_row, current_col)
        
        if motion_type == SimpleMotionChar.underscore:
            dest = self.get_cursor_line_start_location(smart_home=True)
            if dest:
                return RangeLocation(start=start, end=dest)

        elif motion_type == SimpleMotionChar.dollar_sign:
            end: Location = (current_row, len(self.document.lines[current_row]))
            return RangeLocation(start=start, end=end)

        elif motion_type == SimpleMotionChar.zero:
            end = (current_row, 0)
            return RangeLocation(start=start, end=end)

        elif motion_type == SimpleMotionChar.percent_sign:
            dest = find_matching_pair(current_row, current_col, lines)
            if dest:
                return RangeLocation(start=start, end=dest)

        return None



MODE_MAPPING = {
    # Simple Motions
    "h": VimTextArea.action_cursor_left,
    "j": VimTextArea.action_cursor_down,
    "k": VimTextArea.action_cursor_up,
    "l": VimTextArea.action_cursor_right,
    "w": VimTextArea.action_cursor_word_right,
    "b": VimTextArea.action_cursor_word_left,
    SimpleMotionChar.dollar_sign: VimTextArea.action_cursor_line_end,
    SimpleMotionChar.zero: VimTextArea.action_cursor_absolute_line_start,
    SimpleMotionChar.underscore: VimTextArea.action_cursor_line_start,
    SimpleMotionChar.percent_sign: VimTextArea.jump_to_match,

    # Complex motion 
    "f": VimTextArea.f_key_pressed_as_first_key,
    "t": VimTextArea.t_key_pressed_as_first_key,
    "F": VimTextArea.F_key_pressed_as_first_key,
    "T": VimTextArea.T_key_pressed_as_first_key,

    # Simple actions
    "x": VimTextArea.action_delete_right,
    "s": VimTextArea.s_key_pressed,
    "u": VimTextArea.u_key_pressed,
    "ctrl+r": VimTextArea.ctrl_r_key_pressed,

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

    # other
    "o": VimTextArea.o_key_pressed
}

VISUAL_LINE_MODE_MAPPING = {
    "j": VimTextArea.action_visual_line_cursor_down,
    "k": VimTextArea.action_visual_line_cursor_up,
}
