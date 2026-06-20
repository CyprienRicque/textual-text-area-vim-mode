"""Type definitions for text_area_vim package."""

from dataclasses import dataclass

Location = tuple[int, int]


@dataclass(frozen=True)
class RangeLocation:
    start: Location
    end: Location

