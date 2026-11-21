from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from business_card_ppt.business_card.layout_engine import compute_business_card_layout


def _svg_text(element: dict[str, Any], font_family: str) -> str:
    attrs = (
        f'data-layout-key="{escape(str(element.get("key", "")))}" '
        f'data-full-text="{escape(str(element.get("text", "")))}" '
        f'x="{element["x"]}" y="{element["y"] + element["font_size"]}" '
        f'font-family="{escape(font_family)}" font-size="{element["font_size"]}" '
        f'font-weight="{escape(str(element.get("weight", "400")))}" '
        f'fill="{escape(str(element.get("color", "#111827")))}"'
    )
    parts = [f"<text {attrs}>"]
    for index, line in enumerate(element.get("lines") or [element.get("text", "")]):
        dy = 0 if index == 0 else element.get("line_height", element.get("font_size", 10) + 3)
        parts.append(f'<tspan x="{element["x"]}" dy="{dy}">{escape(str(line))}</tspan>')
    parts.append("</text>")
    return "".join(parts)


def _svg_media(element: dict[str, Any], style: dict[str, Any]) -> str:
    bounds = element["bounds"]
    media_type = element.get("media_type", "media")
    if element.get("loaded") and element.get("path"):
        href = Path(str(element["path"])).resolve().as_uri()
        return (
            f'<image data-intentional-media="{escape(media_type)}" x="{bounds["x"]}" y="{bounds["y"]}" '
            f'width="{bounds["width"]}" height="{bounds["height"]}" href="{escape(href)}" '
            'preserveAspectRatio="xMidYMid meet" />'
        )
    label = {"logo": "LOGO", "avatar": "头像", "qr_code": "QR"}.get(media_type, media_type)
    return (
        f'<rect data-media-placeholder="{escape(media_type)}" x="{bounds["x"]}" y="{bounds["y"]}" '
        f'width="{bounds["width"]}" height="{bounds["height"]}" rx="4" fill="none" '
        f'stroke="{escape(str(style.get("accent_color", "#0F766E")))}" stroke-dasharray="4 3" />'
        f'<text x="{bounds["x"] + bounds["width"] / 2:g}" y="{bounds["y"] + bounds["height"] / 2 + 4:g}" '
        f'font-size="9" text-anchor="middle" fill="{escape(str(style.get("muted_text_color", "#4B5563")))}">{escape(label)}</text>'
    )


def _svg_element(element: dict[str, Any], style: dict[str, Any]) -> str:
    kind = element.get("kind")
    bounds = element.get("bounds") or {}
    if kind == "shape":
        line = element.get("line")
        line_attrs = f' stroke="{escape(str(line))}"' if line else ' stroke="none"'
        return (
            f'<rect data-shape-key="{escape(str(element.get("key", "")))}" x="{bounds["x"]}" y="{bounds["y"]}" '
            f'width="{bounds["width"]}" height="{bounds["height"]}" fill="{escape(str(element.get("fill", "#FFFFFF")))}"{line_attrs} />'
        )
    if kind == "line":
        return (
            f'<line data-line-key="{escape(str(element.get("key", "")))}" x1="{element.get("x1", 0)}" y1="{element.get("y1", 0)}" '
            f'x2="{element.get("x2", 0)}" y2="{element.get("y2", 0)}" stroke="{escape(str(element.get("line", "#000000")))}" '
            f'stroke-width="{element.get("width", 1)}" />'
        )
    if kind == "media":
        return _svg_media(element, style)
    if kind == "icon":
        source = element.get("source_icon") or {}
        if source.get("path"):
            href = Path(str(source["path"])).resolve().as_uri()
            return (
                f'<rect data-contact-icon-frame="{escape(str(element.get("key", "")))}" x="{bounds["x"]}" y="{bounds["y"]}" '
                f'width="{bounds["width"]}" height="{bounds["height"]}" fill="none" '
                f'stroke="{escape(str(element.get("fill", style.get("accent_color", "#0F766E"))))}" stroke-width="0.5" />'
                f'<image data-contact-icon="{escape(str(element.get("key", "")))}" x="{bounds["x"]}" y="{bounds["y"]}" '
                f'width="{bounds["width"]}" height="{bounds["height"]}" href="{escape(href)}" />'
            )
        return (
            f'<rect data-contact-icon="{escape(str(element.get("key", "")))}" '
            f'x="{bounds["x"]}" y="{bounds["y"]}" width="{bounds["width"]}" height="{bounds["height"]}" '
            f'fill="{escape(str(element.get("fill", style.get("accent_color", "#0F766E"))))}" />'
        )
    if kind == "text":
        return _svg_text(element, str(style.get("font_family", "Microsoft YaHei")))
    return ""


def _svg_elements(elements: list[dict[str, Any]], style: dict[str, Any]) -> list[str]:
    return [markup for element in elements if (markup := _svg_element(element, style))]


def render_business_card_svg(schema: dict[str, Any]) -> str:
    card = schema["card_size"]
    style = schema["style"]
    layout_plan = compute_business_card_layout(schema)
    side_keys = schema.get("side_order") or ["front", "back"]
    side_gap = 18
    if schema.get("sides"):
        width = int(card["width"])
        height = int(card["height"]) * len(side_keys) + side_gap * (len(side_keys) - 1)
        parts: list[str] = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" data-component="EditableBusinessCard" data-preview-side-count="{len(side_keys)}" '
            f'data-layout-plan-hash="{layout_plan["layout_plan_hash"]}" data-background="{escape(str(style.get("background_color")))}">'
        ]
        for index, side_key in enumerate(side_keys):
            side_schema = schema["sides"][side_key]
            offset_y = index * (int(card["height"]) + side_gap)
            parts.append(f'<g data-card-side="{escape(side_key)}" transform="translate(0 {offset_y})">')
            parts.extend(_svg_elements(layout_plan["sides"][side_key]["elements"], side_schema["style"]))
            parts.append("</g>")
        parts.append("</svg>\n")
        return "\n".join(parts)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{card["width"]}" height="{card["height"]}" '
        f'viewBox="0 0 {card["width"]} {card["height"]}" data-component="EditableBusinessCard" data-preview-side-count="1" '
        f'data-layout-plan-hash="{layout_plan["layout_plan_hash"]}" data-background="{escape(str(style.get("background_color")))}">'
    ]
    parts.extend(_svg_elements(layout_plan["elements"], style))
    parts.append("</svg>\n")
    return "\n".join(parts)


def render_business_card_html(schema: dict[str, Any]) -> str:
    svg = render_business_card_svg(schema)
    card = schema["card_size"]
    layout_hash = compute_business_card_layout(schema)["layout_plan_hash"]
    side_count = len(schema.get("side_order") or ["front", "back"]) if schema.get("sides") else 1
    return (
        "<!doctype html>\n"
        '<html lang="zh-CN">\n'
        "<head>\n"
        '<meta charset="utf-8" />\n'
        "<title>Editable Business Card Preview</title>\n"
        "<style>"
        "html,body{margin:0;background:transparent;}"
        ".preview-root{min-height:100vh;display:flex;justify-content:center;align-items:flex-start;padding:24px;box-sizing:border-box;}"
        f".business-card{{width:{int(card['width'])}px;max-width:100%;}}"
        ".business-card svg{display:block;width:100%;height:auto;}"
        "</style>\n"
        "</head>\n"
        f'<body><main class="preview-root" data-preview-side-count="{side_count}"><div class="business-card" '
        f'data-layout-plan-hash="{layout_hash}" data-preview-side-count="{side_count}">{svg}</div></main></body>\n'
        "</html>\n"
    )
