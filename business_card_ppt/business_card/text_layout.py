from __future__ import annotations

import math
import re
from typing import Any


def measure_text_width(text: object, font_size: int = 10) -> int:
    width = 0.0
    for char in str(text or ""):
        if "\u4e00" <= char <= "\u9fff":
            width += font_size
        elif char.isspace():
            width += font_size * 0.35
        elif char in ".:/\\-+()[]@":
            width += font_size * 0.45
        else:
            width += font_size * 0.58
    return int(math.ceil(width))


def chars_for_width(width: int | float, font_size: int) -> int:
    return max(1, int(float(width) / max(1, font_size * 0.72)))


def _tokenize_text(value: str) -> list[str]:
    tokens: list[str] = []
    for chunk in re.findall(r"\s+|[^\s]+", value):
        if chunk.isspace():
            tokens.append(" ")
            continue
        tokens.append(chunk)
    return tokens


def _split_long_token(token: str, width: int, font_size: int) -> list[str]:
    if measure_text_width(token, font_size) <= width:
        return [token]
    raw_parts = [part for part in re.split(r"(?<=[/.:@?&=_])|(?=[/.:@?&=_])", token) if part]
    parts = raw_parts if len(raw_parts) > 1 else list(token)
    output: list[str] = []
    current = ""
    for part in parts:
        candidate = current + part
        if current and measure_text_width(candidate, font_size) > width:
            output.append(current)
            current = part
        else:
            current = candidate
    if current:
        output.append(current)
    final: list[str] = []
    for part in output:
        if measure_text_width(part, font_size) <= width:
            final.append(part)
            continue
        current = ""
        for char in part:
            candidate = current + char
            if current and measure_text_width(candidate, font_size) > width:
                final.append(current)
                current = char
            else:
                current = candidate
        if current:
            final.append(current)
    return final


def wrap_text(text: object, width: int, font_size: int, max_lines: int | None = None) -> list[str]:
    value = str(text or "").strip()
    if not value:
        return []
    lines: list[str] = []
    for source_line in value.splitlines() or [value]:
        source_line = source_line.strip()
        if not source_line:
            continue
        current = ""
        pending_space = ""
        for token in _tokenize_text(source_line):
            if token == " ":
                if current:
                    pending_space = " "
                continue
            pieces = _split_long_token(token, width, font_size)
            for piece in pieces:
                candidate = f"{current}{pending_space}{piece}" if current else piece
                if current and measure_text_width(candidate, font_size) > width:
                    lines.append(current.rstrip())
                    current = piece
                else:
                    current = candidate
                pending_space = ""
        if current:
            lines.append(current.rstrip())
    return lines or [value]


def fit_font_size(text: object, width: int, requested_size: int, min_size: int) -> int:
    size = int(requested_size)
    while size > min_size and measure_text_width(text, size) > width:
        size -= 1
    return max(min_size, size)


def rect(x: int | float, y: int | float, width: int | float, height: int | float) -> dict[str, int]:
    return {
        "x": int(round(x)),
        "y": int(round(y)),
        "width": int(round(width)),
        "height": int(round(height)),
    }


def right(bounds: dict[str, Any]) -> int:
    return int(bounds.get("x", 0)) + int(bounds.get("width", 0))


def bottom(bounds: dict[str, Any]) -> int:
    return int(bounds.get("y", 0)) + int(bounds.get("height", 0))


def intersects(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return not (
        right(a) <= int(b.get("x", 0))
        or right(b) <= int(a.get("x", 0))
        or bottom(a) <= int(b.get("y", 0))
        or bottom(b) <= int(a.get("y", 0))
    )


def inside(inner: dict[str, Any], outer: dict[str, Any], tolerance: int = 0) -> bool:
    return (
        int(inner.get("x", 0)) >= int(outer.get("x", 0)) - tolerance
        and int(inner.get("y", 0)) >= int(outer.get("y", 0)) - tolerance
        and right(inner) <= right(outer) + tolerance
        and bottom(inner) <= bottom(outer) + tolerance
    )
