"""Vim find motions: f, F, t, T."""

from typing import Tuple


def _search_char(
    current_row: int,
    current_col: int,
    char: str,
    lines: list[str],
    forward: bool,
    repeat: int = 1,
) -> Tuple[int, int] | None:
    if not char or repeat < 1:
        return None
    
    found = 0
    
    if forward:
        # Search forward from current position
        row, col = current_row, current_col + 1
        while row < len(lines):
            line = lines[row]
            # Start from current col in first line
            start_col = col if row == current_row else 0
            
            while True:
                idx = line.find(char, start_col)
                if idx == -1:
                    break
                found += 1
                if found == repeat:
                    return (row, idx)
                start_col = idx + 1
            
            row += 1
            col = 0
    else:
        # Search backward from current position
        row, col = current_row, current_col - 1
        while row >= 0:
            line = lines[row]
            # Search from col backwards
            if row == current_row:
                end_col = col + 1
            else:
                end_col = len(line)
            
            while True:
                idx = line.rfind(char, 0, end_col)
                if idx == -1:
                    break
                found += 1
                if found == repeat:
                    return (row, idx)
                end_col = idx
            
            row -= 1
            col = len(lines[row]) - 1 if row >= 0 else -1
    
    return None


def find_forward(
    current_row: int,
    current_col: int,
    char: str,
    lines: list[str],
    repeat: int = 1,
) -> Tuple[int, int] | None:
    """
    Find next occurrence of char moving forward (for 'f' motion).
    Stops ON the character.
    
    Args:
        current_row: Starting row position
        current_col: Starting column position
        char: Character to search for
        lines: All lines of text
        repeat: Which occurrence to find (1=first, 2=second, etc.)
    """
    return _search_char(current_row, current_col, char, lines, forward=True, repeat=repeat)


def find_backward(
    current_row: int,
    current_col: int,
    char: str,
    lines: list[str],
    repeat: int = 1,
) -> Tuple[int, int] | None:
    """
    Find previous occurrence of char moving backward (for 'F' motion).
    Stops ON the character.
    
    Args:
        current_row: Starting row position
        current_col: Starting column position
        char: Character to search for
        lines: All lines of text
        repeat: Which occurrence to find (1=first, 2=second, etc.)
    """
    return _search_char(current_row, current_col, char, lines, forward=False, repeat=repeat)


def to_forward(
    current_row: int,
    current_col: int,
    char: str,
    lines: list[str],
    repeat: int = 1,
) -> Tuple[int, int] | None:
    """
    Move to just before next occurrence of char (for 't' motion).
    Relies on find_forward implementation.
    
    Args:
        current_row: Starting row position
        current_col: Starting column position
        char: Character to search for
        lines: All lines of text
        repeat: Which occurrence to find (1=first, 2=second, etc.)
    """
    result = find_forward(current_row, current_col, char, lines, repeat=repeat)
    if result is None:
        return None
    row, col = result
    # Move to position before the found character
    if col > 0:
        return (row, col - 1)
    elif row > 0:
        return (row - 1, len(lines[row - 1]) - 1)
    return None


def to_backward(
    current_row: int,
    current_col: int,
    char: str,
    lines: list[str],
    repeat: int = 1,
) -> Tuple[int, int] | None:
    """
    Move to just before previous occurrence of char (for 'T' motion).
    Relies on find_backward implementation.
    """
    result = find_backward(current_row, current_col, char, lines, repeat=repeat)
    if result is None:
        return None
    row, col = result
    # Move to position before the found character
    if col > 0:
        return (row, col - 1)
    elif row > 0:
        return (row - 1, len(lines[row - 1]) - 1)
    return None
