from __future__ import annotations

import html
import os
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_AUTO_SIZE, MSO_VERTICAL_ANCHOR
from pptx.util import Inches, Pt

from business_card_ppt.business_card.layout_engine import compute_business_card_layout
from business_card_ppt.business_card.renderer import render_business_card_html, render_business_card_svg
from business_card_ppt.io.writer import ensure_dir, write_json, write_text


PX_PER_INCH = 96


def _emu(px: int | float):
    return Inches(float(px) / PX_PER_INCH)


def _rgb(hex_color: str) -> RGBColor:
    value = str(hex_color or "#000000").lstrip("#")
    if len(value) != 6:
        value = "000000"
    return RGBColor(int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def _add_rect(slide, bounds: dict[str, int], fill: str, line: str | None = None, name: str | None = None) -> int:
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, _emu(bounds["x"]), _emu(bounds["y"]), _emu(bounds["width"]), _emu(bounds["height"]))
    if name:
        shape.name = name
    shape.fill.solid()
    shape.fill.fore_color.rgb = _rgb(fill)
    if line:
        shape.line.color.rgb = _rgb(line)
    else:
        shape.line.fill.background()
    return 1


def _add_shape(slide, element: dict[str, Any]) -> int:
    bounds = element["bounds"]
    shape_name = str(element.get("shape") or "rect")
    shape_type = MSO_SHAPE.PARALLELOGRAM if shape_name == "parallelogram" else MSO_SHAPE.RECTANGLE
    shape = slide.shapes.add_shape(shape_type, _emu(bounds["x"]), _emu(bounds["y"]), _emu(bounds["width"]), _emu(bounds["height"]))
    shape.name = f"business-card-shape:{element.get('key')}"
    shape.fill.solid()
    shape.fill.fore_color.rgb = _rgb(str(element.get("fill", "#FFFFFF")))
    line = element.get("line")
    if line:
        shape.line.color.rgb = _rgb(str(line))
    else:
        shape.line.fill.background()
    return 1


def _add_line(slide, element: dict[str, Any]) -> int:
    line = slide.shapes.add_connector(
        MSO_CONNECTOR.STRAIGHT,
        _emu(element.get("x1", 0)),
        _emu(element.get("y1", 0)),
        _emu(element.get("x2", 0)),
        _emu(element.get("y2", 0)),
    )
    line.name = f"business-card-line:{element.get('key')}"
    line.line.color.rgb = _rgb(str(element.get("line", "#000000")))
    line.line.width = Pt(float(element.get("width", 1)))
    return 1


def _add_circle(slide, bounds: dict[str, int], fill: str, name: str | None = None) -> int:
    shape = slide.shapes.add_shape(MSO_SHAPE.OVAL, _emu(bounds["x"]), _emu(bounds["y"]), _emu(bounds["width"]), _emu(bounds["height"]))
    if name:
        shape.name = name
    shape.fill.solid()
    shape.fill.fore_color.rgb = _rgb(fill)
    shape.line.fill.background()
    return 1


def _add_contact_icon(slide, element: dict[str, Any], style: dict[str, Any]) -> int:
    bounds = element["bounds"]
    icon = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, _emu(bounds["x"]), _emu(bounds["y"]), _emu(bounds["width"]), _emu(bounds["height"]))
    source = element.get("source_icon") or {}
    source_name = Path(str(source.get("path", ""))).name if source.get("path") else ""
    icon.name = f"contact-icon:{element.get('key')}:{source_name}"
    icon.fill.background()
    icon.line.color.rgb = _rgb(str(element.get("fill", style.get("accent_color", "#000000"))))
    icon.line.width = Pt(0.8)
    return 1


def _contact_icon_record(element: dict[str, Any], slide_index: int) -> dict[str, Any]:
    bounds = element["bounds"]
    source = element.get("source_icon") or {}
    path = source.get("path")
    return {
        "kind": element.get("key"),
        "slide_index": slide_index,
        "source_path": str(path or ""),
        "filename": Path(str(path or "")).name,
        "bounds": bounds,
        "rendered_in_pptx": False,
        "render_mode": "pending" if path else "fallback",
    }


def _add_text(slide, element: dict[str, Any], font_family: str) -> int:
    bounds = element["bounds"]
    box = slide.shapes.add_textbox(_emu(bounds["x"]), _emu(bounds["y"]), _emu(bounds["width"]), _emu(bounds["height"] + 2))
    box.name = f"business-card-text:{element.get('key', 'text')}"
    frame = box.text_frame
    frame.clear()
    frame.word_wrap = False
    frame.auto_size = MSO_AUTO_SIZE.NONE
    frame.vertical_anchor = MSO_VERTICAL_ANCHOR.TOP
    frame.margin_left = 0
    frame.margin_right = 0
    frame.margin_top = 0
    frame.margin_bottom = 0
    lines = element.get("lines") or [str(element.get("text") or "")]
    for index, line_text in enumerate(lines):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.space_after = Pt(0)
        paragraph.space_before = Pt(0)
        run = paragraph.add_run()
        run.text = str(line_text)
        run.font.size = Pt(int(element.get("font_size", 10)))
        run.font.bold = str(element.get("weight")) in {"600", "700", "bold", "true"}
        run.font.name = font_family
        run.font.color.rgb = _rgb(str(element.get("color") or "#111827"))
    return 1


def _add_media(slide, element: dict[str, Any], style: dict[str, Any]) -> tuple[int, int]:
    bounds = element["bounds"]
    media_type = element.get("media_type", "media")
    if element.get("loaded") and element.get("path"):
        picture = slide.shapes.add_picture(str(element["path"]), _emu(bounds["x"]), _emu(bounds["y"]), _emu(bounds["width"]), _emu(bounds["height"]))
        picture.name = f"intentional-media:{media_type}"
        return 1, 0
    _add_rect(slide, bounds, "#FFFFFF", str(style.get("accent_color", "#0F766E")), name=f"media-placeholder:{media_type}")
    label = {"logo": "LOGO", "avatar": "头像", "qr_code": "QR"}.get(media_type, media_type)
    text_element = {
        "key": f"placeholder.{media_type}",
        "text": label,
        "bounds": bounds,
        "font_size": 9,
        "color": style.get("muted_text_color", "#4B5563"),
        "weight": "400",
    }
    _add_text(slide, text_element, str(style.get("font_family", "Microsoft YaHei")))
    return 0, 2


def _pptx_picture_count(pptx_path: Path) -> int:
    with zipfile.ZipFile(pptx_path) as archive:
        return sum(
            archive.read(name).decode("utf-8", errors="ignore").count("<p:pic")
            for name in archive.namelist()
            if name.startswith("ppt/slides/slide") and name.endswith(".xml")
        )


def _pptx_media_count(pptx_path: Path) -> int:
    with zipfile.ZipFile(pptx_path) as archive:
        return len([name for name in archive.namelist() if name.startswith("ppt/media/")])


def _next_rid(rels_xml: str) -> str:
    ids = [int(value) for value in re.findall(r'Id="rId(\d+)"', rels_xml)]
    return f"rId{max(ids, default=0) + 1}"


def _next_cnvpr_id(slide_xml: str) -> int:
    ids = [int(value) for value in re.findall(r'<p:cNvPr[^>]*\bid="(\d+)"', slide_xml)]
    return max(ids, default=1) + 1


def _svg_picture_xml(record: dict[str, Any], rid: str, shape_id: int) -> str:
    bounds = record["bounds"]
    name = f"contact-icon:{record.get('kind')}:{record.get('filename')}"
    return (
        "<p:pic>"
        "<p:nvPicPr>"
        f'<p:cNvPr id="{shape_id}" name="{html.escape(name, quote=True)}"/>'
        '<p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr>'
        "<p:nvPr/>"
        "</p:nvPicPr>"
        "<p:blipFill>"
        f'<a:blip r:embed="{rid}"/>'
        "<a:stretch><a:fillRect/></a:stretch>"
        "</p:blipFill>"
        "<p:spPr>"
        f'<a:xfrm><a:off x="{int(_emu(bounds["x"]))}" y="{int(_emu(bounds["y"]))}"/>'
        f'<a:ext cx="{int(_emu(bounds["width"]))}" cy="{int(_emu(bounds["height"]))}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        "</p:spPr>"
        "</p:pic>"
    )


def _inject_svg_contact_icons(pptx_path: Path, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pending = [record for record in records if record.get("render_mode") == "pending" and record.get("source_path")]
    if not pending:
        return records

    with zipfile.ZipFile(pptx_path, "r") as archive:
        entries = {item.filename: archive.read(item.filename) for item in archive.infolist()}

    content_types = entries.get("[Content_Types].xml", b"").decode("utf-8")
    if 'Extension="svg"' not in content_types:
        content_types = content_types.replace(
            "</Types>",
            '<Default Extension="svg" ContentType="image/svg+xml"/></Types>',
        )
        entries["[Content_Types].xml"] = content_types.encode("utf-8")

    media_index = len([name for name in entries if name.startswith("ppt/media/")]) + 1
    for record in pending:
        source = Path(str(record["source_path"]))
        if not source.exists() or source.suffix.lower() != ".svg":
            record["render_mode"] = "failed"
            record["error"] = "source SVG icon is missing"
            continue

        slide_name = f"ppt/slides/slide{record['slide_index']}.xml"
        rels_name = f"ppt/slides/_rels/slide{record['slide_index']}.xml.rels"
        if slide_name not in entries:
            record["render_mode"] = "failed"
            record["error"] = "target slide XML is missing"
            continue

        rels_xml = entries.get(
            rels_name,
            b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>',
        ).decode("utf-8")
        rid = _next_rid(rels_xml)
        media_name = f"ppt/media/contact_icon_{media_index}_{source.name}"
        media_index += 1
        entries[media_name] = source.read_bytes()
        rel = (
            f'<Relationship Id="{rid}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
            f'Target="../media/{Path(media_name).name}"/>'
        )
        rels_xml = rels_xml.replace("</Relationships>", f"{rel}</Relationships>")
        entries[rels_name] = rels_xml.encode("utf-8")

        slide_xml = entries[slide_name].decode("utf-8")
        picture_xml = _svg_picture_xml(record, rid, _next_cnvpr_id(slide_xml))
        slide_xml = slide_xml.replace("</p:spTree>", f"{picture_xml}</p:spTree>")
        entries[slide_name] = slide_xml.encode("utf-8")
        record["render_mode"] = "svg_picture"
        record["rendered_in_pptx"] = True

    fd, temp_name = tempfile.mkstemp(suffix=".pptx", dir=str(pptx_path.parent))
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in entries.items():
                archive.writestr(name, data)
        temp_path.replace(pptx_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()
    return records


def _render_pptx(schema: dict[str, Any], pptx_path: Path) -> dict[str, int]:
    presentation = Presentation()
    card = schema["card_size"]
    presentation.slide_width = _emu(card["width"])
    presentation.slide_height = _emu(card["height"])
    layout_plan = compute_business_card_layout(schema)
    shape_count = 0
    text_count = 0
    picture_instances = 0
    contact_icons: list[dict[str, Any]] = []
    if schema.get("sides"):
        slide_sources = [
            (schema["sides"][side_key], layout_plan["sides"][side_key])
            for side_key in schema.get("side_order") or ["front", "back"]
        ]
    else:
        slide_sources = [(schema, layout_plan)]
    for slide_index, (slide_schema, slide_plan) in enumerate(slide_sources, start=1):
        style = slide_schema["style"]
        slide = presentation.slides.add_slide(presentation.slide_layouts[6])
        for element in slide_plan["elements"]:
            kind = element.get("kind")
            if kind == "shape":
                shape_count += _add_shape(slide, element)
            elif kind == "line":
                shape_count += _add_line(slide, element)
            elif kind == "icon":
                record = _contact_icon_record(element, slide_index)
                if record.get("source_path"):
                    contact_icons.append(record)
                else:
                    shape_count += _add_contact_icon(slide, element, style)
                    contact_icons.append(record)
            elif kind == "media":
                pictures, shapes = _add_media(slide, element, style)
                picture_instances += pictures
                shape_count += shapes
            elif kind == "text":
                text_count += _add_text(slide, element, str(style.get("font_family", "Microsoft YaHei")))
    presentation.save(pptx_path)
    contact_icons = _inject_svg_contact_icons(pptx_path, contact_icons)
    rendered_contact_icons = [item for item in contact_icons if item.get("rendered_in_pptx")]
    return {
        "slide_count": len(slide_sources),
        "text_count": text_count,
        "shape_count": shape_count,
        "picture_count": _pptx_picture_count(pptx_path),
        "media_count": _pptx_media_count(pptx_path),
        "intentional_picture_instances": picture_instances,
        "contact_icon_count": len(contact_icons),
        "pptx_contact_icon_count": len(rendered_contact_icons),
        "contact_icons": contact_icons,
    }


def _draw_png_elements(draw: ImageDraw.ImageDraw, elements: list[dict[str, Any]], style: dict[str, Any], y_offset: int = 0) -> None:
    for element in elements:
        bounds = element.get("bounds") or {}
        y = int(bounds.get("y", 0)) + y_offset
        if element.get("kind") == "shape":
            draw.rectangle(
                [bounds["x"], y, bounds["x"] + bounds["width"], y + bounds["height"]],
                fill=element.get("fill", "#FFFFFF"),
                outline=element.get("line"),
            )
        elif element.get("kind") == "line":
            draw.line(
                [element.get("x1", 0), int(element.get("y1", 0)) + y_offset, element.get("x2", 0), int(element.get("y2", 0)) + y_offset],
                fill=element.get("line", "#000000"),
                width=max(1, int(float(element.get("width", 1)))),
            )
        elif element.get("kind") == "text":
            line_height = int(element.get("line_height", int(element.get("font_size", 10)) + 3))
            for index, line in enumerate(element.get("lines") or [str(element.get("text", ""))]):
                draw.text((bounds["x"], y + index * line_height), str(line), fill=element.get("color", "#111827"))
        elif element.get("kind") == "media":
            draw.rectangle(
                [bounds["x"], y, bounds["x"] + bounds["width"], y + bounds["height"]],
                outline=style.get("accent_color", "#0F766E"),
            )
        elif element.get("kind") == "icon":
            draw.rectangle(
                [bounds["x"], y, bounds["x"] + bounds["width"], y + bounds["height"]],
                outline=element.get("fill", style.get("accent_color", "#0F766E")),
            )


def _render_png_fallback(schema: dict[str, Any], png_path: Path) -> None:
    card = schema["card_size"]
    style = schema["style"]
    layout_plan = compute_business_card_layout(schema)
    side_gap = 18
    if schema.get("sides"):
        side_keys = schema.get("side_order") or ["front", "back"]
        width = int(card["width"])
        height = int(card["height"]) * len(side_keys) + side_gap * (len(side_keys) - 1)
        image = Image.new("RGB", (width, height), str(style.get("background_color", "#FFFFFF")))
        draw = ImageDraw.Draw(image)
        for index, side_key in enumerate(side_keys):
            offset_y = index * (int(card["height"]) + side_gap)
            _draw_png_elements(draw, layout_plan["sides"][side_key]["elements"], schema["sides"][side_key]["style"], offset_y)
        image.save(png_path)
        return
    image = Image.new("RGB", (int(card["width"]), int(card["height"])), str(style.get("background_color", "#FFFFFF")))
    draw = ImageDraw.Draw(image)
    _draw_png_elements(draw, layout_plan["elements"], style)
    image.save(png_path)


def _render_png_preview(schema: dict[str, Any], html_path: Path, png_path: Path) -> str:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            side_count = len(schema.get("side_order") or ["front", "back"]) if schema.get("sides") else 1
            side_gap = 18 if schema.get("sides") else 0
            page = browser.new_page(
                viewport={
                    "width": int(schema["card_size"]["width"]) + 96,
                    "height": int(schema["card_size"]["height"]) * side_count + side_gap * max(0, side_count - 1) + 96,
                },
                device_scale_factor=1,
            )
            page.goto(html_path.resolve().as_uri(), wait_until="load")
            page.locator("main.preview-root > div.business-card").screenshot(path=str(png_path), omit_background=True)
            browser.close()
        return "playwright"
    except Exception:
        _render_png_fallback(schema, png_path)
        return "pillow_fallback"


def _preview_structure(schema: dict[str, Any], renderer: str) -> dict[str, Any]:
    if schema.get("sides"):
        sides = list(schema.get("side_order") or ["front", "back"])
        return {"side_count": len(sides), "sides": sides, "layout": "combined", "renderer": renderer}
    return {"side_count": 1, "sides": [str(schema.get("side") or "front")], "layout": "single", "renderer": renderer}


def export_business_card_outputs(schema: dict[str, Any], output_dir: str | Path) -> dict[str, Any]:
    target_dir = ensure_dir(output_dir)
    layout_plan = compute_business_card_layout(schema)
    svg = render_business_card_svg(schema)
    html = render_business_card_html(schema)

    schema_path = write_json(target_dir / "business_card.schema.json", schema)
    svg_path = write_text(target_dir / "business_card.svg", svg)
    html_path = write_text(target_dir / "business_card.html", html)
    png_path = target_dir / "business_card.png"
    pptx_path = target_dir / "business_card.pptx"
    png_renderer = _render_png_preview(schema, html_path, png_path)
    pptx_structure = _render_pptx(schema, pptx_path)
    preview_structure = _preview_structure(schema, png_renderer)

    summary = {
        "files": {
            "schema": str(schema_path),
            "html": str(html_path),
            "svg": str(svg_path),
            "png": str(png_path),
            "pptx": str(pptx_path),
        },
        "layout_plan_hash": layout_plan["layout_plan_hash"],
        "layout_diagnostics": layout_plan["diagnostics"],
        "pptx_structure": pptx_structure,
        "preview_structure": preview_structure,
        "html_structure": {"side_count": preview_structure["side_count"], "sides": preview_structure["sides"], "layout": preview_structure["layout"]},
        "svg_structure": {"side_count": preview_structure["side_count"], "sides": preview_structure["sides"], "layout": preview_structure["layout"]},
        "png_structure": preview_structure,
        "contact_icon_count": pptx_structure.get("contact_icon_count", 0),
        "pptx_contact_icon_count": pptx_structure.get("pptx_contact_icon_count", 0),
        "contact_icons": pptx_structure.get("contact_icons", []),
        "intentional_media": schema.get("assets", {}).get("intentional_media", []),
        "fallback_icons": schema.get("assets", {}).get("fallback_icons", []),
        "warnings": schema.get("warnings", []),
    }
    write_json(target_dir / "summary.json", summary)
    return summary
