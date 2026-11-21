from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree
from html import unescape

from business_card_ppt.business_card.layout_engine import compute_business_card_layout
from business_card_ppt.business_card.text_layout import inside, intersects
from business_card_ppt.io.writer import write_json


STANDARD_FACT_KEYS = {
    "name",
    "title",
    "role",
    "company",
    "department",
    "phone",
    "email",
    "website",
    "address",
    "wechat",
    "qq",
    "social",
    "slogan",
    "tagline",
    "brand_name",
}
NON_FACT_KEYS = {
    "style",
    "theme",
    "style_intent",
    "layout",
    "layout_style",
    "icon_policy",
    "card_size",
    "page",
    "canvas",
    "orientation",
    "uncertainties",
    "media_usage",
}


def _pptx_texts(pptx_path: Path) -> list[str]:
    texts: list[str] = []
    with zipfile.ZipFile(pptx_path) as archive:
        for name in archive.namelist():
            if not (name.startswith("ppt/slides/slide") and name.endswith(".xml")):
                continue
            root = ElementTree.fromstring(archive.read(name))
            for node in root.iter():
                if node.tag.endswith("}t") and node.text:
                    texts.append(node.text)
    return texts


def _pptx_slide_texts(pptx_path: Path) -> list[list[str]]:
    slide_texts: list[list[str]] = []
    with zipfile.ZipFile(pptx_path) as archive:
        slide_names = sorted(
            [name for name in archive.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", name)],
            key=lambda value: int(re.search(r"slide(\d+)\.xml$", value).group(1)),  # type: ignore[union-attr]
        )
        for name in slide_names:
            texts: list[str] = []
            root = ElementTree.fromstring(archive.read(name))
            for node in root.iter():
                if node.tag.endswith("}t") and node.text:
                    texts.append(node.text)
            slide_texts.append(texts)
    return slide_texts


def _pptx_slide_count(pptx_path: Path) -> int:
    with zipfile.ZipFile(pptx_path) as archive:
        return len([name for name in archive.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", name)])


def _pptx_shape_names(pptx_path: Path) -> list[str]:
    names: list[str] = []
    with zipfile.ZipFile(pptx_path) as archive:
        for name in archive.namelist():
            if not (name.startswith("ppt/slides/slide") and name.endswith(".xml")):
                continue
            root = ElementTree.fromstring(archive.read(name))
            for node in root.iter():
                if node.tag.endswith("}cNvPr") and node.attrib.get("name"):
                    names.append(node.attrib["name"])
    return names


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


def _pptx_contact_icon_picture_names(pptx_path: Path) -> list[str]:
    names: list[str] = []
    with zipfile.ZipFile(pptx_path) as archive:
        for name in archive.namelist():
            if not (name.startswith("ppt/slides/slide") and name.endswith(".xml")):
                continue
            xml = archive.read(name).decode("utf-8", errors="ignore")
            for match in re.finditer(r"<p:pic\b.*?</p:pic>", xml, flags=re.DOTALL):
                name_match = re.search(r'<p:cNvPr[^>]*name="([^"]*contact-icon[^"]*)"', match.group(0))
                if name_match:
                    names.append(name_match.group(1))
    return names


def _expected_texts(schema: dict[str, Any]) -> list[str]:
    if schema.get("sides"):
        values: list[str] = []
        for side_key in schema.get("side_order") or ["front", "back"]:
            values.extend(_expected_texts(schema["sides"][side_key]))
        return values
    values: list[str] = []
    fields = schema.get("fields", {})
    for key in ("name", "title", "company", "department", "slogan", "brand_name"):
        if fields.get(key):
            values.append(str(fields[key]))
    for key in ("phone", "email", "website", "address", "wechat", "qq", "social"):
        if fields.get(key):
            values.append(str(fields[key]))
    for extra in schema.get("extra_fields") or []:
        if extra.get("value"):
            values.append(str(extra["value"]))
    return values


def _side_expected_texts(schema: dict[str, Any], side_key: str) -> list[str]:
    if not schema.get("sides"):
        return _expected_texts(schema)
    return _expected_texts(schema["sides"][side_key])


def _schema_blob(schema: dict[str, Any]) -> str:
    return json.dumps(schema, ensure_ascii=False, sort_keys=True)


def _normalize_visible_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u3000", " ")).strip()


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", "", value)


def _visible_svg_text_errors(source_name: str, markup: str) -> list[str]:
    errors: list[str] = []
    for match in re.finditer(r"<text\b(?P<attrs>[^>]*)>(?P<body>.*?)</text>", markup, flags=re.DOTALL):
        attrs = match.group("attrs")
        body = match.group("body")
        full_match = re.search(r'data-full-text="([^"]*)"', attrs)
        visible_parts = [unescape(part) for part in re.findall(r"<tspan\b[^>]*>(.*?)</tspan>", body, flags=re.DOTALL)]
        visible = _normalize_visible_text(" ".join(re.sub(r"<[^>]+>", "", part) for part in visible_parts))
        if "…" in visible:
            errors.append(f"{source_name} visible text contains ellipsis: {visible}")
        if not full_match:
            continue
        full_text = _normalize_visible_text(unescape(full_match.group(1)))
        if full_text and visible and _compact_text(full_text) != _compact_text(visible):
            errors.append(f"{source_name} visible text differs from data-full-text: {full_text!r} vs {visible!r}")
    return errors


def _fact_values_from_builder_params(params: dict[str, Any] | None) -> list[str]:
    if not params:
        return []
    values: list[str] = []

    def collect(value: Any, key: str = "") -> None:
        if key in NON_FACT_KEYS:
            return
        if isinstance(value, dict):
            for child_key, child_value in value.items():
                collect(child_value, child_key)
        elif isinstance(value, list):
            if key == "style_keywords":
                return
            for item in value:
                collect(item, key)
        elif value is not None:
            text = str(value).strip()
            if len(text) >= 2 and not text.startswith("#") and key not in {"path_resolution"}:
                values.append(text)

    for key, value in params.items():
        if key in STANDARD_FACT_KEYS or key in {"extra_fields", "fields", "business_card", "profile", "person"}:
            collect(value, key)
    return values


def _rect_errors(schema: dict[str, Any], layout_plan: dict[str, Any]) -> list[str]:
    if schema.get("sides"):
        errors: list[str] = []
        for side_key in schema.get("side_order") or ["front", "back"]:
            errors.extend(
                f"{side_key}: {item}"
                for item in _rect_errors(schema["sides"][side_key], layout_plan["sides"][side_key])
            )
        return errors
    errors: list[str] = []
    content_area = layout_plan["content_area"]
    card_bounds = layout_plan["card_bounds"]
    items = [item for item in layout_plan["elements"] if item.get("kind") in {"text", "media"} and item.get("bounds")]
    for item in items:
        name = item.get("key") or item.get("media_type")
        bounds = item["bounds"]
        if not inside(bounds, card_bounds, tolerance=1):
            errors.append(f"{name} exceeds card bounds")
        if not inside(bounds, content_area, tolerance=1):
            errors.append(f"{name} exceeds safe_margin content area")
    for index, first in enumerate(items):
        for second in items[index + 1 :]:
            if intersects(first["bounds"], second["bounds"]):
                errors.append(f"{first.get('key') or first.get('media_type')} overlaps {second.get('key') or second.get('media_type')}")
    return errors


def _style_token_errors(schema: dict[str, Any], svg_text: str) -> list[str]:
    errors: list[str] = []
    style = schema.get("style", {})
    for key in ("primary_color", "background_color", "text_color", "accent_color", "font_family"):
        if not style.get(key):
            errors.append(f"schema.style is missing {key}")
    for key in ("background_color", "text_color", "accent_color"):
        value = str(style.get(key) or "")
        if value and value not in svg_text:
            errors.append(f"style token {key} is not used by renderer")
    return errors


def _media_errors(schema: dict[str, Any], summary: dict[str, Any]) -> tuple[list[str], list[str]]:
    if schema.get("sides"):
        errors: list[str] = []
        warnings: list[str] = []
        for side_key in schema.get("side_order") or ["front", "back"]:
            side_errors, side_warnings = _media_errors(schema["sides"][side_key], summary)
            errors.extend(f"{side_key}: {item}" for item in side_errors)
            warnings.extend(side_warnings)
        return errors, warnings
    errors: list[str] = []
    warnings: list[str] = []
    records = summary.get("intentional_media", [])
    for media_type in ("logo", "avatar", "qr_code"):
        media = schema.get("assets", {}).get(media_type) or {}
        requested = media.get("requested") or media.get("placeholder") or media.get("path")
        if requested and not any(item.get("type") == media_type for item in records):
            errors.append(f"{media_type} is requested but not recorded in intentional_media")
        if media.get("missing"):
            warnings.append(f"{media_type}_path is missing; placeholder rendered")
        if media.get("placeholder") and not media.get("loaded"):
            warnings.append(f"{media_type} placeholder rendered")
    return errors, warnings


def _expected_contact_icons(schema: dict[str, Any]) -> list[dict[str, str]]:
    if schema.get("sides"):
        icons: list[dict[str, str]] = []
        for side_key in schema.get("side_order") or ["front", "back"]:
            for item in _expected_contact_icons(schema["sides"][side_key]):
                icons.append({**item, "side": side_key})
        return icons
    if not schema.get("icon_policy", {}).get("contact_icons", True):
        return []
    icons = []
    for contact in schema.get("contacts") or []:
        icon = contact.get("icon") or {}
        if icon.get("path"):
            icons.append({"kind": str(contact.get("kind") or ""), "path": str(icon["path"])})
    return icons


def _contact_icon_errors(
    schema: dict[str, Any],
    summary: dict[str, Any],
    pptx_contact_icon_picture_names: list[str],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    expected = _expected_contact_icons(schema)
    records = summary.get("contact_icons") or []
    rendered = [item for item in records if item.get("rendered_in_pptx") and item.get("render_mode") in {"svg_picture", "pptx_vector_shape"}]
    if not expected:
        return errors, warnings
    if len(records) < len(expected):
        errors.append(f"pptx missing rendered contact icon records: expected {len(expected)}, got {len(records)}")
    if int(summary.get("pptx_contact_icon_count") or 0) != len(expected):
        errors.append(
            f"pptx_contact_icon_count must equal schema contact icon count {len(expected)}, got {summary.get('pptx_contact_icon_count')}"
        )
    if len(rendered) != len(expected):
        errors.append(f"pptx missing rendered contact icon: expected {len(expected)}, got {len(rendered)}")
    failed = [item for item in records if item.get("render_mode") in {"fallback", "failed"}]
    if failed:
        errors.append(f"contact icon rendered as empty placeholder or failed: {failed}")
    if len(pptx_contact_icon_picture_names) < len(expected):
        errors.append("schema icons are not visible in pptx")
    for icon in expected:
        if not Path(icon["path"]).exists():
            warnings.append(f"contact icon path is missing: {icon['path']}")
    return errors, warnings


def _classify_error(error: str) -> str:
    lower = error.lower()
    if "missing explicit builder fact" in lower or "schema.style" in lower:
        return "upstream_semantic_missing"
    if "pptx" in lower or "media_count" in lower or "picture" in lower or "editable text" in lower:
        return "export_adapter_issue"
    return "layout_repairable"


def classify_verification_issues(errors: list[str]) -> dict[str, list[dict[str, str]]]:
    categories = {"upstream_semantic_missing": [], "layout_repairable": [], "export_adapter_issue": []}
    for error in errors:
        kind = _classify_error(error)
        categories[kind].append({"issue_type": kind, "message": error})
    return categories


def verify_business_card_outputs(
    schema: dict[str, Any],
    summary: dict[str, Any],
    output_dir: str | Path,
    builder_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    target_dir = Path(output_dir)
    pptx_path = target_dir / "business_card.pptx"
    svg_path = target_dir / "business_card.svg"
    html_path = target_dir / "business_card.html"
    png_path = target_dir / "business_card.png"
    schema_path = target_dir / "business_card.schema.json"
    summary_path = target_dir / "summary.json"
    errors: list[str] = []
    warnings: list[str] = list(schema.get("warnings", []))

    for path in (pptx_path, svg_path, html_path, png_path, schema_path, summary_path):
        if not path.exists():
            errors.append(f"missing output file: {path.name}")

    pptx_text_blob = ""
    slide_texts: list[list[str]] = []
    actual_slide_count = 0
    pptx_shape_names: list[str] = []
    picture_count = 0
    media_count = 0
    pptx_contact_icon_picture_names: list[str] = []
    if pptx_path.exists():
        try:
            texts = _pptx_texts(pptx_path)
            slide_texts = _pptx_slide_texts(pptx_path)
            actual_slide_count = _pptx_slide_count(pptx_path)
            pptx_text_blob = "\n".join(texts)
            pptx_shape_names = _pptx_shape_names(pptx_path)
            picture_count = _pptx_picture_count(pptx_path)
            media_count = _pptx_media_count(pptx_path)
            pptx_contact_icon_picture_names = _pptx_contact_icon_picture_names(pptx_path)
        except Exception as exc:
            errors.append(f"pptx cannot be opened: {exc}")

    expected_texts = _expected_texts(schema)
    compact_pptx_text_blob = _compact_text(pptx_text_blob)
    missing_texts = [text for text in expected_texts if _compact_text(text) not in compact_pptx_text_blob]
    if missing_texts:
        errors.append(f"missing editable text in pptx: {missing_texts}")
    if len([text for text in pptx_text_blob.splitlines() if text.strip()]) < max(1, min(3, len(expected_texts))):
        errors.append("pptx editable text count is unexpectedly low")

    loaded_media = [item for item in summary.get("intentional_media", []) if item.get("loaded")]
    rendered_contact_icon_count = len([item for item in summary.get("contact_icons", []) if item.get("rendered_in_pptx")])
    allowed_picture_count = len(loaded_media) + rendered_contact_icon_count
    if picture_count > allowed_picture_count:
        errors.append("pptx picture_count exceeds loaded intentional_media count")
    if len(loaded_media) and picture_count < len(loaded_media):
        errors.append("pptx picture_count is lower than loaded intentional_media count")
    if media_count > allowed_picture_count:
        errors.append("pptx media_count exceeds loaded intentional_media count")
    if "full-page" in "\n".join(pptx_shape_names).lower() or "screenshot" in "\n".join(pptx_shape_names).lower():
        errors.append("pptx appears to contain a full-page screenshot shape")

    card = schema.get("card_size", {})
    if (int(card.get("width", 0)), int(card.get("height", 0))) == (794, 1123):
        errors.append("card canvas still uses A4 resume size")
    if card.get("orientation") not in {"horizontal_card", "vertical_card"}:
        errors.append("business card orientation is invalid")

    svg_text = svg_path.read_text(encoding="utf-8") if svg_path.exists() else ""
    html_text = html_path.read_text(encoding="utf-8") if html_path.exists() else ""
    layout_plan = compute_business_card_layout(schema)
    summary_hash = summary.get("layout_plan_hash")
    if summary_hash != layout_plan["layout_plan_hash"]:
        errors.append("summary layout_plan_hash does not match computed layout plan")
    if svg_text and f'data-layout-plan-hash="{layout_plan["layout_plan_hash"]}"' not in svg_text:
        errors.append("svg does not use the shared layout plan hash")
    if html_text and f'data-layout-plan-hash="{layout_plan["layout_plan_hash"]}"' not in html_text:
        errors.append("html does not use the shared layout plan hash")

    double_sided = bool(schema.get("double_sided") or schema.get("sides"))
    summary_slide_count = int((summary.get("pptx_structure") or {}).get("slide_count") or 0)
    if actual_slide_count and summary_slide_count and actual_slide_count != summary_slide_count:
        errors.append(f"summary slide_count {summary_slide_count} does not match pptx slide_count {actual_slide_count}")
    if double_sided:
        if summary_slide_count not in {1, 2}:
            errors.append(f"double-sided schema requires summary slide_count 1 or 2, got {summary_slide_count}")
        if actual_slide_count not in {1, 2}:
            errors.append(f"double-sided schema requires 1 or 2 pptx slides, got {actual_slide_count}")
        uncertainty_text = " ".join(str(item) for item in schema.get("uncertainties") or [])
        if "不支持双面" in uncertainty_text or "does not support" in uncertainty_text.lower():
            errors.append("schema says double-sided is unsupported")
        for marker in ('data-card-side="front"', 'data-card-side="back"'):
            if marker not in svg_text:
                errors.append(f"svg missing side marker: {marker}")
            if marker not in html_text:
                errors.append(f"html missing side marker: {marker}")
        for side_key in ("front", "back"):
            side_texts = _side_expected_texts(schema, side_key)
            missing_svg = [text for text in side_texts if text not in svg_text]
            missing_html = [text for text in side_texts if text not in html_text]
            if missing_svg:
                errors.append(f"svg missing {side_key} text: {missing_svg}")
            if missing_html:
                errors.append(f"html missing {side_key} text: {missing_html}")
        preview_structure = summary.get("preview_structure") or {}
        png_structure = summary.get("png_structure") or {}
        svg_structure = summary.get("svg_structure") or {}
        html_structure = summary.get("html_structure") or {}
        for label, structure in (
            ("preview_structure", preview_structure),
            ("png_structure", png_structure),
            ("svg_structure", svg_structure),
            ("html_structure", html_structure),
        ):
            if int(structure.get("side_count") or 0) != 2:
                errors.append(f"{label}.side_count must be 2 for double-sided schema")
        if actual_slide_count == 1:
            shape_blob = "\n".join(pptx_shape_names).lower()
            front_texts = _side_expected_texts(schema, "front")
            back_texts = _side_expected_texts(schema, "back")
            has_front_marker = "front." in shape_blob or "card-side:front" in shape_blob
            has_back_marker = "back." in shape_blob or "card-side:back" in shape_blob
            if not has_front_marker or not has_back_marker:
                errors.append("single-slide double-sided pptx must contain front/back object markers")
            if any(_compact_text(text) not in compact_pptx_text_blob for text in front_texts):
                errors.append("single-slide double-sided pptx is missing front content")
            if any(_compact_text(text) not in compact_pptx_text_blob for text in back_texts):
                errors.append("single-slide double-sided pptx is missing back content")
        if len(slide_texts) >= 2:
            back_blob = "\n".join(slide_texts[1])
            front_fields = (schema.get("sides", {}).get("front", {}) or {}).get("fields", {})
            forbidden_keys = ("name", "title", "phone", "email", "website", "address", "wechat", "qq", "social")
            forbidden = [str(front_fields[key]) for key in forbidden_keys if front_fields.get(key)]
            leaked = [text for text in forbidden if text and text in back_blob]
            if leaked:
                errors.append(f"back side contains front-only text: {leaked}")

    errors.extend(_style_token_errors(schema, svg_text))
    media_errors, media_warnings = _media_errors(schema, summary)
    errors.extend(media_errors)
    warnings.extend(media_warnings)
    contact_icon_errors, contact_icon_warnings = _contact_icon_errors(schema, summary, pptx_contact_icon_picture_names)
    errors.extend(contact_icon_errors)
    warnings.extend(contact_icon_warnings)
    layout_diagnostics = layout_plan.get("diagnostics", {})
    if layout_diagnostics.get("overflow"):
        errors.append("layout overflow: " + "; ".join(layout_diagnostics.get("overflow_reasons") or []))
    else:
        errors.extend(_rect_errors(schema, layout_plan))

    schema_blob = _schema_blob(schema)
    for fact in _fact_values_from_builder_params(builder_params):
        if fact and fact not in schema_blob:
            errors.append(f"missing explicit builder fact in schema: {fact}")

    if "<foreignObject" in svg_text:
        errors.append("svg contains foreignObject")
    errors.extend(_visible_svg_text_errors("svg", svg_text))
    errors.extend(_visible_svg_text_errors("html", html_text))

    report = {
        "passed": not errors,
        "errors": errors,
        "warnings": sorted(set(warnings)),
        "issue_categories": classify_verification_issues(errors),
        "checks": {
            "pptx_opened": pptx_path.exists() and not any(error.startswith("pptx cannot") for error in errors),
            "editable_text_count": len([text for text in pptx_text_blob.splitlines() if text.strip()]),
            "expected_text_count": len(expected_texts),
            "picture_count": picture_count,
            "media_count": media_count,
            "no_full_page_screenshot": picture_count <= allowed_picture_count,
            "pptx_contact_icon_count": summary.get("pptx_contact_icon_count", 0),
            "slide_count": actual_slide_count,
            "card_width": card.get("width"),
            "card_height": card.get("height"),
            "orientation": card.get("orientation"),
            "overflow": bool(layout_diagnostics.get("overflow")),
            "layout_plan_hash": layout_plan["layout_plan_hash"],
            "intentional_media_count": len(summary.get("intentional_media", [])),
        },
    }
    write_json(target_dir / "verification_report.json", report)
    return report
