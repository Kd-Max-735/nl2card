from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image

from business_card_ppt.business_card.text_layout import bottom, inside, intersects, measure_text_width, rect, right, wrap_text


DISPLAY_LABELS = {
    "phone": "TEL",
    "email": "EMAIL",
    "website": "WEB",
    "address": "ADD",
    "wechat": "微信",
    "qq": "QQ",
    "social": "社交",
}


def _content_area(schema: dict[str, Any]) -> dict[str, int]:
    area = schema.get("card_size", {}).get("content_area") or {}
    return rect(area.get("x", 18), area.get("y", 18), area.get("width", 304), area.get("height", 168))


def _media_exists(media: dict[str, Any]) -> bool:
    return bool(media.get("loaded") and media.get("path"))


def _media_requested(media: dict[str, Any]) -> bool:
    return bool(media.get("requested") or media.get("placeholder") or media.get("path"))


def _image_aspect(path_text: str | None) -> float | None:
    if not path_text:
        return None
    try:
        with Image.open(Path(path_text)) as image:
            width, height = image.size
            if width > 0 and height > 0:
                return width / height
    except Exception:
        return None
    return None


def _text_element(
    key: str,
    text: object,
    x: int,
    y: int,
    width: int,
    font_size: int,
    color: str,
    weight: str = "400",
    max_lines: int = 1,
    min_font_size: int = 7,
) -> dict[str, Any]:
    size = int(font_size)
    lines = wrap_text(text, width, size, max_lines=max_lines)
    while size > min_font_size and any(measure_text_width(line, size) > width for line in lines):
        size -= 1
        lines = wrap_text(text, width, size, max_lines=max_lines)
    line_height = max(size + 3, int(size * 1.25))
    height = max(line_height, line_height * max(1, len(lines)))
    return {
        "kind": "text",
        "key": key,
        "text": str(text or ""),
        "lines": lines,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "font_size": size,
        "line_height": line_height,
        "max_lines": max_lines,
        "overflow_lines": len(lines) > max_lines,
        "color": color,
        "weight": weight,
        "bounds": rect(x, y, width, height),
    }


def _media_element(kind: str, media: dict[str, Any], bounds: dict[str, int]) -> dict[str, Any]:
    aspect = _image_aspect(media.get("path")) if _media_exists(media) else None
    return {
        "kind": "media",
        "media_type": kind,
        "path": media.get("path"),
        "source": media.get("source"),
        "loaded": _media_exists(media),
        "placeholder": bool(media.get("placeholder") or not _media_exists(media)),
        "missing": bool(media.get("missing")),
        "aspect_ratio": aspect,
        "bounds": bounds,
    }


def _background_elements(schema: dict[str, Any]) -> list[dict[str, Any]]:
    card = schema["card_size"]
    style = schema["style"]
    design = schema.get("design", {})
    elements = [
        {
            "kind": "shape",
            "shape": "rect",
            "key": "background",
            "bounds": rect(0, 0, card["width"], card["height"]),
            "fill": style.get("background_color", "#FFFFFF"),
            "line": None,
        }
    ]
    if design.get("diagonal_stripes") or design.get("background_texture") == "light_gray_diagonal_stripes":
        stripe_color = str(design.get("stripe_color") or style.get("secondary_color", "#E6E6E6"))
        for offset in range(-int(card["height"]), int(card["width"]) + int(card["height"]), 14):
            elements.append(
                {
                    "kind": "line",
                    "key": f"stripe.{offset}",
                    "x1": offset,
                    "y1": int(card["height"]),
                    "x2": offset + int(card["height"]),
                    "y2": 0,
                    "width": 0.6,
                    "line": stripe_color,
                }
            )
    if schema.get("layout", {}).get("layout_style") == "split_panel":
        panel_width = max(92, int(card["width"] * 0.32))
        elements.append(
            {
                "kind": "shape",
                "shape": "rect",
                "key": "split_panel",
                "bounds": rect(0, 0, panel_width, card["height"]),
                "fill": style.get("primary_color", "#1F2937"),
                "line": None,
            }
        )
    return elements


def _line_element(key: str, x1: int, y1: int, x2: int, y2: int, color: str, width: float = 1.5) -> dict[str, Any]:
    return {"kind": "line", "key": key, "x1": x1, "y1": y1, "x2": x2, "y2": y2, "line": color, "width": width}


def _horizontal_line_hits_bounds(y: int, x1: int, x2: int, bounds: dict[str, Any], margin: int = 3) -> bool:
    left, right_edge = sorted((int(x1), int(x2)))
    if y < int(bounds.get("y", 0)) - margin or y > bottom(bounds) + margin:
        return False
    return not (right_edge < int(bounds.get("x", 0)) - margin or left > right(bounds) + margin)


def _line_hits_bounds(line: dict[str, Any], bounds: dict[str, Any], margin: int = 3) -> bool:
    key = str(line.get("key", ""))
    if key.startswith("stripe."):
        return False
    x1, y1, x2, y2 = (int(line.get("x1", 0)), int(line.get("y1", 0)), int(line.get("x2", 0)), int(line.get("y2", 0)))
    if y1 == y2:
        return _horizontal_line_hits_bounds(y1, x1, x2, bounds, margin)
    line_box = rect(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))
    expanded = rect(
        int(bounds.get("x", 0)) - margin,
        int(bounds.get("y", 0)) - margin,
        int(bounds.get("width", 0)) + margin * 2,
        int(bounds.get("height", 0)) + margin * 2,
    )
    return intersects(line_box, expanded)


def _find_clear_horizontal_y(elements: list[dict[str, Any]], card: dict[str, Any], preferred_y: int) -> int:
    critical = [item["bounds"] for item in elements if item.get("kind") in {"text", "media", "icon"} and item.get("bounds")]
    candidates = [preferred_y, int(card["height"] * 0.68), int(card["height"] * 0.35), int(card["height"] * 0.78)]
    candidates.extend(range(26, int(card["height"]) - 24, 6))
    for y in candidates:
        if not any(_horizontal_line_hits_bounds(y, 0, int(card["width"]), bounds, margin=4) for bounds in critical):
            return y
    return preferred_y


def _plan_media(schema: dict[str, Any], area: dict[str, int]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    assets = schema.get("assets", {})
    style = schema["layout"].get("layout_style", "left_logo_right_info")
    media_elements: list[dict[str, Any]] = []
    reserved = {"left": area["x"], "top": area["y"], "right": right(area), "bottom": bottom(area)}

    logo = assets.get("logo") or {}
    avatar = assets.get("avatar") or {}
    qr = assets.get("qr_code") or {}

    if _media_requested(logo):
        size = 44 if schema["card_size"]["orientation"] == "horizontal_card" else 38
        logo_bounds = rect(area["x"], area["y"], size, size)
        if style == "centered":
            logo_bounds = rect(area["x"] + (area["width"] - size) / 2, area["y"], size, size)
        elif style == "split_panel":
            logo_bounds = rect(20, area["y"], size, size)
        media_elements.append(_media_element("logo", logo, logo_bounds))
        if style in {"left_logo_right_info", "minimal_corner"}:
            reserved["left"] = max(reserved["left"], right(logo_bounds) + 10)
        elif style in {"centered", "top_logo_bottom_info"}:
            reserved["top"] = max(reserved["top"], bottom(logo_bounds) + 8)

    if _media_requested(avatar):
        size = 42
        avatar_bounds = rect(right(area) - size, area["y"], size, size)
        media_elements.append(_media_element("avatar", avatar, avatar_bounds))
        reserved["right"] = min(reserved["right"], avatar_bounds["x"] - 8)

    if _media_requested(qr):
        size = 54 if schema["card_size"]["orientation"] == "horizontal_card" else 48
        qr_bounds = rect(right(area) - size, bottom(area) - size, size, size)
        media_elements.append(_media_element("qr_code", qr, qr_bounds))
        reserved["right"] = min(reserved["right"], qr_bounds["x"] - 8)

    if style == "split_panel":
        reserved["left"] = max(reserved["left"], 112)
    return media_elements, reserved


def _field_value(fields: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if fields.get(key):
            return fields[key]
    return None


def _add_text(elements: list[dict[str, Any]], element: dict[str, Any], cursor_y: int, gap: int) -> int:
    elements.append(element)
    return bottom(element["bounds"]) + gap


def _text_plan(schema: dict[str, Any], area: dict[str, int], reserved: dict[str, int]) -> list[dict[str, Any]]:
    style = schema["style"]
    layout = schema["layout"]
    fields = schema.get("fields", {})
    extras = schema.get("extra_fields") or []
    min_size = int(layout.get("min_font_size", 7))
    line_gap = int(layout.get("line_gap", 4))
    x = reserved["left"]
    y = reserved["top"]
    width = max(60, reserved["right"] - x)
    elements: list[dict[str, Any]] = []

    if layout.get("layout_style") == "centered":
        x = area["x"]
        width = area["width"]

    name = _field_value(fields, "name", "brand_name")
    if name:
        y = _add_text(
            elements,
            _text_element("name", name, x, y, width, int(layout.get("name_font_size", 18)), style["text_color"], "700", 1, min_size),
            y,
            2,
        )
    title_company = " / ".join(str(value) for value in (_field_value(fields, "title"), _field_value(fields, "department")) if value)
    if title_company:
        y = _add_text(elements, _text_element("title", title_company, x, y, width, 9, style["muted_text_color"], "400", 1, min_size), y, line_gap)
    company = _field_value(fields, "company")
    if company and company != name:
        y = _add_text(elements, _text_element("company", company, x, y, width, 11, style["text_color"], "600", 1, min_size), y, line_gap)
    slogan = _field_value(fields, "slogan")
    if slogan:
        y = _add_text(elements, _text_element("slogan", slogan, x, y, width, 9, style["accent_color"], "400", 2, min_size), y, line_gap)

    contact_y = max(y + 2, area["y"] + 88 if schema["card_size"]["orientation"] == "horizontal_card" else y)
    contact_width = width
    for key in ("phone", "email", "website", "address", "wechat", "qq", "social"):
        value = fields.get(key)
        if not value:
            continue
        label = DISPLAY_LABELS.get(key, key)
        text = f"{label}: {value}"
        icon_space = 14 if schema.get("icon_policy", {}).get("contact_icons", True) else 0
        if icon_space:
            elements.append(
                {
                    "kind": "icon",
                    "key": key,
                    "bounds": rect(x, contact_y + 1, 9, 9),
                    "fill": style.get("accent_color", "#0F766E"),
                    "source_icon": next((item.get("icon") for item in schema.get("contacts", []) if item.get("kind") == key), None),
                }
            )
        element = _text_element(
            f"contact.{key}",
            text,
            x + icon_space,
            contact_y,
            max(40, contact_width - icon_space),
            int(layout.get("base_font_size", 10)),
            style["text_color"],
            "400",
            2 if key == "address" else 1,
            min_size,
        )
        elements.append(element)
        contact_y = bottom(element["bounds"]) + int(layout.get("contact_row_gap", 3))

    for index, extra in enumerate(extras):
        text = f"{extra.get('label')}: {extra.get('value')}"
        element = _text_element(f"extra.{index}", text, x, contact_y, contact_width, 8, style["muted_text_color"], "400", 1, min_size)
        elements.append(element)
        contact_y = bottom(element["bounds"]) + int(layout.get("contact_row_gap", 3))
    return elements


def _contact_icon_source(schema: dict[str, Any], key: str) -> dict[str, Any] | None:
    return next((item.get("icon") for item in schema.get("contacts", []) if item.get("kind") == key), None)


def _black_white_side_plan(schema: dict[str, Any], area: dict[str, int]) -> list[dict[str, Any]]:
    card = schema["card_size"]
    style = schema["style"]
    design = schema.get("design", {})
    fields = schema.get("fields", {})
    assets = schema.get("assets", {})
    side = schema.get("side", "front")
    line_color = str(design.get("line_color") or style.get("accent_color") or "#000000")
    elements = _background_elements(schema)
    content_elements: list[dict[str, Any]] = []

    if side == "back":
        qr = assets.get("qr_code") or {}
        logo = assets.get("logo") or {}
        content_elements.append(_media_element("qr_code", qr, rect(48, 64, 58, 58)))
        content_elements.append(_media_element("logo", logo, rect(164, 70, 38, 38)))
        company = _field_value(fields, "company", "brand_name")
        if company:
            content_elements.append(_text_element("company", company, 212, 78, 104, 9, style["text_color"], "700", 3, 7))
        line_y = _find_clear_horizontal_y(content_elements, card, int(card["height"] * 0.53))
        block_bounds = rect(0, line_y - 12, 64, 24)
        elements.append(
            {
                "kind": "shape",
                "shape": "parallelogram",
                "key": f"{side}.geometric_block",
                "bounds": block_bounds,
                "fill": line_color,
                "line": None,
            }
        )
        elements.append(_line_element(f"{side}.horizontal_line", right(block_bounds) - 2, line_y, int(card["width"]), line_y, line_color, 2.0))
        elements.extend(content_elements)
        return elements

    logo = assets.get("logo") or {}
    content_elements.append(_media_element("logo", logo, rect(204, 30, 38, 38)))
    company = _field_value(fields, "company", "brand_name")
    if company:
        content_elements.append(_text_element("company", company, 244, 36, 78, 8, style["text_color"], "700", 3, 6))
    name = _field_value(fields, "name", "brand_name")
    if name:
        content_elements.append(_text_element("name", name, area["x"], 30, 170, 20, style["text_color"], "700", 1, 12))
    title = _field_value(fields, "title")
    if title:
        content_elements.append(_text_element("title", title, area["x"], 56, 176, 9, style.get("muted_text_color", "#4B5563"), "400", 2, 7))

    contact_y = 122
    for key in ("phone", "email", "address", "website", "wechat", "qq", "social"):
        value = fields.get(key)
        if not value:
            continue
        content_elements.append(
            {
                "kind": "icon",
                "key": key,
                "bounds": rect(area["x"], contact_y + 1, 9, 9),
                "fill": line_color,
                "source_icon": _contact_icon_source(schema, key),
            }
        )
        label = DISPLAY_LABELS.get(key, key)
        text = f"{label}: {value}"
        max_lines = 3 if key in {"address", "website", "email", "social"} else 2
        element = _text_element(f"contact.{key}", text, area["x"] + 14, contact_y, 230, 8, style["text_color"], "400", max_lines, 6)
        content_elements.append(element)
        contact_y = bottom(element["bounds"]) + 3
    line_y = _find_clear_horizontal_y(content_elements, card, int(card["height"] * 0.53))
    block_bounds = rect(0, line_y - 12, 64, 24)
    elements.append(
        {
            "kind": "shape",
            "shape": "parallelogram",
            "key": f"{side}.geometric_block",
            "bounds": block_bounds,
            "fill": line_color,
            "line": None,
        }
    )
    elements.append(_line_element(f"{side}.horizontal_line", right(block_bounds) - 2, line_y, int(card["width"]), line_y, line_color, 2.0))
    elements.extend(content_elements)
    return elements


def _diagnostics(elements: list[dict[str, Any]], area: dict[str, int], card: dict[str, Any]) -> dict[str, Any]:
    page = rect(0, 0, card["width"], card["height"])
    text_and_media = [item for item in elements if item.get("kind") in {"text", "media", "icon"} and item.get("bounds")]
    overlaps: list[str] = []
    out_of_bounds: list[str] = []
    safe_margin_errors: list[str] = []
    line_conflicts: list[str] = []
    text_errors: list[str] = []
    for index, first in enumerate(text_and_media):
        bounds = first["bounds"]
        if not inside(bounds, page, tolerance=1):
            out_of_bounds.append(f"{first.get('key') or first.get('media_type')} exceeds card bounds")
        if first.get("kind") in {"text", "media"} and not inside(bounds, area, tolerance=1):
            safe_margin_errors.append(f"{first.get('key') or first.get('media_type')} exceeds safe content area")
        for second in text_and_media[index + 1 :]:
            if first.get("kind") == "icon" and str(second.get("key", "")).endswith(str(first.get("key"))):
                continue
            if second.get("kind") == "icon" and str(first.get("key", "")).endswith(str(second.get("key"))):
                continue
            if intersects(bounds, second["bounds"]):
                overlaps.append(f"{first.get('key') or first.get('media_type')} overlaps {second.get('key') or second.get('media_type')}")
        if first.get("kind") == "text":
            if any("…" in str(line) for line in first.get("lines") or []):
                text_errors.append(f"{first.get('key')} contains ellipsis")
            expected_height = int(first.get("line_height", 0)) * max(1, len(first.get("lines") or []))
            if int(first.get("height", 0)) < expected_height:
                text_errors.append(f"{first.get('key')} text box is too short for computed lines")
            if first.get("overflow_lines"):
                text_errors.append(f"{first.get('key')} uses more lines than preferred")
    lines = [item for item in elements if item.get("kind") == "line" and not str(item.get("key", "")).startswith("stripe.")]
    for line in lines:
        for item in text_and_media:
            if _line_hits_bounds(line, item["bounds"], margin=2):
                line_conflicts.append(f"{line.get('key')} crosses {item.get('key') or item.get('media_type')}")
    overflow = bool(out_of_bounds or safe_margin_errors or overlaps or line_conflicts or text_errors)
    return {
        "overflow": overflow,
        "overflow_reasons": out_of_bounds + safe_margin_errors + overlaps + line_conflicts + text_errors,
        "overlaps": overlaps,
        "out_of_bounds": out_of_bounds,
        "safe_margin_errors": safe_margin_errors,
        "line_conflicts": line_conflicts,
        "text_errors": text_errors,
    }


def compute_business_card_layout(schema: dict[str, Any]) -> dict[str, Any]:
    if schema.get("sides"):
        side_plans: dict[str, Any] = {}
        overflow_reasons: list[str] = []
        overlaps: list[str] = []
        out_of_bounds: list[str] = []
        safe_margin_errors: list[str] = []
        line_conflicts: list[str] = []
        text_errors: list[str] = []
        for side_key in schema.get("side_order") or ["front", "back"]:
            side_schema = schema["sides"][side_key]
            side_plan = compute_business_card_layout(side_schema)
            side_plans[side_key] = side_plan
            diagnostics = side_plan.get("diagnostics", {})
            overflow_reasons.extend(f"{side_key}: {item}" for item in diagnostics.get("overflow_reasons") or [])
            overlaps.extend(f"{side_key}: {item}" for item in diagnostics.get("overlaps") or [])
            out_of_bounds.extend(f"{side_key}: {item}" for item in diagnostics.get("out_of_bounds") or [])
            safe_margin_errors.extend(f"{side_key}: {item}" for item in diagnostics.get("safe_margin_errors") or [])
            line_conflicts.extend(f"{side_key}: {item}" for item in diagnostics.get("line_conflicts") or [])
            text_errors.extend(f"{side_key}: {item}" for item in diagnostics.get("text_errors") or [])
        card = schema["card_size"]
        area = _content_area(schema)
        plan = {
            "card_bounds": rect(0, 0, card["width"], card["height"]),
            "content_area": area,
            "elements": side_plans.get("front", {}).get("elements", []),
            "sides": side_plans,
            "diagnostics": {
                "overflow": bool(overflow_reasons),
                "overflow_reasons": overflow_reasons,
                "overlaps": overlaps,
                "out_of_bounds": out_of_bounds,
                "safe_margin_errors": safe_margin_errors,
                "line_conflicts": line_conflicts,
                "text_errors": text_errors,
            },
        }
        encoded = json.dumps(plan, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        plan["layout_plan_hash"] = hashlib.sha256(encoded).hexdigest()[:16]
        return plan

    card = schema["card_size"]
    area = _content_area(schema)
    if schema.get("layout", {}).get("layout_style") == "black_white_double_sided" or schema.get("design", {}).get("horizontal_line"):
        elements = _black_white_side_plan(schema, area)
    else:
        elements = _background_elements(schema)
        media_elements, reserved = _plan_media(schema, area)
        text_elements = _text_plan(schema, area, reserved)
        elements.extend(media_elements)
        elements.extend(text_elements)
    diagnostics = _diagnostics(elements, area, card)
    plan = {
        "card_bounds": rect(0, 0, card["width"], card["height"]),
        "content_area": area,
        "elements": elements,
        "diagnostics": diagnostics,
    }
    encoded = json.dumps(plan, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    plan["layout_plan_hash"] = hashlib.sha256(encoded).hexdigest()[:16]
    return plan
