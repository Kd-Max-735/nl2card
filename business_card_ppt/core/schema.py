from __future__ import annotations

from copy import deepcopy
from typing import Any


PLACEHOLDER_TEXT = "等待用户填入"

SUPPORTED_ORIENTATIONS = {"horizontal_card", "vertical_card"}
SUPPORTED_LAYOUT_STYLES = {
    "left_logo_right_info",
    "top_logo_bottom_info",
    "centered",
    "split_panel",
    "minimal_corner",
    "black_white_double_sided",
}

DEFAULT_CARD_SIZE: dict[str, Any] = {
    "unit": "px",
    "width": 340,
    "height": 204,
    "width_mm": 90,
    "height_mm": 54,
    "orientation": "horizontal_card",
    "page_format": "business_card_90x54mm",
    "safe_margin": 18,
    "bleed": 11,
    "content_area": {"x": 18, "y": 18, "width": 304, "height": 168},
}

DEFAULT_STYLE: dict[str, Any] = {
    "theme": "clean_business",
    "primary_color": "#1F2937",
    "secondary_color": "#E5E7EB",
    "background_color": "#FFFFFF",
    "text_color": "#111827",
    "muted_text_color": "#4B5563",
    "accent_color": "#0F766E",
    "font_family": "Microsoft YaHei",
    "style_keywords": [],
}

DEFAULT_LAYOUT: dict[str, Any] = {
    "layout_style": "left_logo_right_info",
    "safe_margin": 18,
    "bleed": 11,
    "min_font_size": 7,
    "base_font_size": 10,
    "name_font_size": 18,
    "line_gap": 4,
    "contact_row_gap": 3,
}

DEFAULT_ICON_POLICY: dict[str, Any] = {
    "contact_icons": True,
    "icon_style": "line",
    "fallback": "omit",
}


def merge_defaults(defaults: dict[str, Any], overrides: dict[str, Any] | None) -> dict[str, Any]:
    merged = deepcopy(defaults)
    if overrides:
        for key, value in overrides.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                child = deepcopy(merged[key])
                child.update(value)
                merged[key] = child
            else:
                merged[key] = value
    return merged


def normalize_orientation(value: object) -> str:
    text = str(value or "").strip()
    if text in SUPPORTED_ORIENTATIONS:
        return text
    if text.lower() in {"vertical", "portrait", "vertical_card"}:
        return "vertical_card"
    return "horizontal_card"


def normalize_layout_style(value: object) -> tuple[str, str | None]:
    text = str(value or "").strip()
    if text in SUPPORTED_LAYOUT_STYLES:
        return text, None
    if text:
        return "left_logo_right_info", f"Unsupported layout_style {text!r}; downgraded to left_logo_right_info."
    return "left_logo_right_info", None


def card_size_from_params(params: dict[str, Any]) -> dict[str, Any]:
    raw = params.get("card_size") or params.get("page") or params.get("canvas") or {}
    orientation = normalize_orientation(params.get("orientation") or raw.get("orientation"))
    card_size = merge_defaults(DEFAULT_CARD_SIZE, raw if isinstance(raw, dict) else {})
    if orientation == "vertical_card":
        width = int(card_size.get("width") or DEFAULT_CARD_SIZE["height"])
        height = int(card_size.get("height") or DEFAULT_CARD_SIZE["width"])
        if width > height:
            width, height = height, width
        card_size.update(
            {
                "width": width,
                "height": height,
                "width_mm": min(card_size.get("width_mm", 54), card_size.get("height_mm", 90)),
                "height_mm": max(card_size.get("width_mm", 54), card_size.get("height_mm", 90)),
                "orientation": "vertical_card",
            }
        )
    else:
        width = int(card_size.get("width") or DEFAULT_CARD_SIZE["width"])
        height = int(card_size.get("height") or DEFAULT_CARD_SIZE["height"])
        if width < height:
            width, height = height, width
        card_size.update(
            {
                "width": width,
                "height": height,
                "width_mm": max(card_size.get("width_mm", 90), card_size.get("height_mm", 54)),
                "height_mm": min(card_size.get("width_mm", 90), card_size.get("height_mm", 54)),
                "orientation": "horizontal_card",
            }
        )
    safe_margin = int(card_size.get("safe_margin") or DEFAULT_CARD_SIZE["safe_margin"])
    card_size["safe_margin"] = safe_margin
    card_size["bleed"] = int(card_size.get("bleed") or DEFAULT_CARD_SIZE["bleed"])
    card_size["content_area"] = {
        "x": safe_margin,
        "y": safe_margin,
        "width": max(1, int(card_size["width"]) - safe_margin * 2),
        "height": max(1, int(card_size["height"]) - safe_margin * 2),
    }
    if "page_format" not in card_size:
        card_size["page_format"] = "business_card_90x54mm"
    return card_size


def validate_schema_contract(schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("type", "component", "version", "card_size", "style", "layout", "fields", "assets"):
        if key not in schema:
            errors.append(f"missing schema key: {key}")
    if schema.get("type") != "business_card":
        errors.append("schema.type must be business_card")
    if schema.get("component") != "EditableBusinessCard":
        errors.append("schema.component must be EditableBusinessCard")
    if schema.get("card_size", {}).get("orientation") not in SUPPORTED_ORIENTATIONS:
        errors.append("card_size.orientation is not supported")
    if schema.get("layout", {}).get("layout_style") not in SUPPORTED_LAYOUT_STYLES:
        errors.append("layout.layout_style is not supported")
    if not isinstance(schema.get("fields"), dict):
        errors.append("fields must be a dict")
    return errors
