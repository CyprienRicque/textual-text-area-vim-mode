"""Find matching bracket/parenthesis/brace positions for Vim % command."""

from text_area_vim.types import Location, RangeLocation

# Map opening to closing
PAIRS = {
    "(": ")",
    "[": "]",
    "{": "}",
    "<": ">",
}
# Map closing to opening
REVERSE_PAIRS = {v: k for k, v in PAIRS.items()}
ALL_PAIRS = set(PAIRS.keys()) | set(REVERSE_PAIRS.keys())


def find_matching_pair(
    current_row: int,
    current_col: int,
    lines: list[str],
) -> Location | None:
    """
    Find the position of the matching bracket/parenthesis/brace.
    
    Args:
        current_row: Current cursor row
        current_col: Current cursor column
        lines: All lines of text
        
    Returns:
        Tuple of (row, col) of matching pair, or None if no match found
    """
    if current_row >= len(lines):
        return None
    
    line = lines[current_row]
    if current_col >= len(line):
        return None
    
    char = line[current_col]
    
    if char not in ALL_PAIRS:
        return None
    
    if char in PAIRS:
        # Opening bracket: find matching closing
        return _find_closing(current_row, current_col, char, PAIRS[char], lines)
    else:
        # Closing bracket: find matching opening
        return _find_opening(current_row, current_col, char, REVERSE_PAIRS[char], lines)


def _find_closing(
    start_row: int,
    start_col: int,
    open_char: str,
    close_char: str,
    lines: list[str],
) -> Location | None:
    """Find matching closing bracket from an opening bracket."""
    depth = 1
    row, col = start_row, start_col + 1
    
    while row < len(lines):
        line = lines[row]
        while col < len(line):
            c = line[col]
            if c == open_char:
                depth += 1
            elif c == close_char:
                depth -= 1
                if depth == 0:
                    return (row, col)
            col += 1
        row += 1
        col = 0
    
    return None


def _find_opening(
    start_row: int,
    start_col: int,
    close_char: str,
    open_char: str,
    lines: list[str],
) -> Location | None:
    """Find matching opening bracket from a closing bracket."""
    depth = 1
    row, col = start_row, start_col - 1
    
    while row >= 0:
        line = lines[row]
        while col >= 0:
            c = line[col]
            if c == close_char:
                depth += 1
            elif c == open_char:
                depth -= 1
                if depth == 0:
                    return (row, col)
            col -= 1
        row -= 1
        col = len(lines[row]) - 1 if row >= 0 else -1
    
    return None


def find_inner(
    current_row: int,
    current_col: int,
    char: str,
    lines: list[str],
) -> RangeLocation | None:
    """
    Find the inner range of a matching pair (excluding delimiters).
    For Vim 'i' text object.
    
    Args:
        current_row: Current cursor row
        current_col: Current cursor column
        char: The character at cursor position (should be a pair character)
        lines: All lines of text
        
    Returns:
        RangeLocation with start and end positions (excluding delimiters), or None
    """
    match_pos = find_matching_pair(current_row, current_col, lines)
    if match_pos is None:
        return None
    
    match_row, match_col = match_pos
    
    # Determine which is opening and which is closing
    line = lines[current_row]
    if current_col >= len(line):
        return None
    
    cursor_char = line[current_col]
    
    if cursor_char in PAIRS:
        # Current position is opening, match_pos is closing
        start_row, start_col = current_row, current_col
        end_row, end_col = match_row, match_col
    else:
        # Current position is closing, match_pos is opening
        start_row, start_col = match_row, match_col
        end_row, end_col = current_row, current_col
    
    # For inner: move start forward, end backward (exclude delimiters)
    # Move start forward
    if start_col + 1 < len(lines[start_row]):
        start_col += 1
    elif start_row + 1 < len(lines):
        start_row += 1
        start_col = 0
    else:
        return None
    
    # Move end backward
    if end_col > 0:
        end_col -= 1
    elif end_row > 0:
        end_row -= 1
        end_col = len(lines[end_row]) - 1
    else:
        return None
    
    return RangeLocation(start=(start_row, start_col), end=(end_row, end_col))


def find_around(
    current_row: int,
    current_col: int,
    char: str,
    lines: list[str],
) -> RangeLocation | None:
    """
    Find the around range of a matching pair (including delimiters).
    For Vim 'a' text object.
    
    Args:
        current_row: Current cursor row
        current_col: Current cursor column
        char: The character at cursor position (should be a pair character)
        lines: All lines of text
        
    Returns:
        RangeLocation with start and end positions (including delimiters), or None
    """
    match_pos = find_matching_pair(current_row, current_col, lines)
    if match_pos is None:
        return None
    
    match_row, match_col = match_pos
    
    # Determine which is opening and which is closing
    line = lines[current_row]
    if current_col >= len(line):
        return None
    
    cursor_char = line[current_col]
    
    if cursor_char in PAIRS:
        # Current position is opening, match_pos is closing
        start_row, start_col = current_row, current_col
        end_row, end_col = match_row, match_col
    else:
        # Current position is closing, match_pos is opening
        start_row, start_col = match_row, match_col
        end_row, end_col = current_row, current_col
    
    # For around: include the delimiters
    return RangeLocation(start=(start_row, start_col), end=(end_row, end_col))
