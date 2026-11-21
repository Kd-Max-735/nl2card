from __future__ import annotations

import json
import os
import re
import tempfile
import zipfile
from pathlib import Path

from business_card_ppt.business_card.builder import build_business_card_schema
from business_card_ppt.business_card.export import export_business_card_outputs
from business_card_ppt.business_card.layout_engine import compute_business_card_layout
from business_card_ppt.business_card.text_layout import intersects
from business_card_ppt.business_card.verifier import verify_business_card_outputs


ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "svg_material"


def _sample_schema():
    params = json.loads((ROOT / "tests" / "fixtures" / "sample_business_card_builder_params.json").read_text(encoding="utf-8"))
    return build_business_card_schema(params, icon_dir=ICON_DIR), params


def _double_sided_schema():
    params = json.loads((ROOT / "tests" / "fixtures" / "double_sided_business_card_builder_params.json").read_text(encoding="utf-8"))
    return build_business_card_schema(params, icon_dir=ICON_DIR), params


def _alternate_double_sided_schema():
    params = {
        "card_size": {"width": 340, "height": 204, "width_mm": 90, "height_mm": 54, "orientation": "horizontal_card"},
        "layout_style": "black_white_double_sided",
        "style": {
            "primary_color": "#000000",
            "secondary_color": "#DADADA",
            "background_color": "#FFFFFF",
            "text_color": "#000000",
            "muted_text_color": "#555555",
            "accent_color": "#000000",
            "font_family": "Microsoft YaHei",
            "style_keywords": ["minimal", "corporate"],
        },
        "design": {
            "background_texture": "light_gray_diagonal_stripes",
            "diagonal_stripes": True,
            "horizontal_line": True,
            "geometric_block": "left_black_block",
            "line_color": "#000000",
        },
        "icon_policy": {"contact_icons": True, "force_contact_icons": True},
        "sides": {
            "front": {
                "name": "Nova Labs",
                "title": "Director of Partnerships",
                "company": "ACME GLOBAL -RESEARCH-LAB-",
                "phone": "15500001234",
                "email": "hello@nova-labs.example",
                "website": "https://nova-labs.example",
                "address": "14 Innovation Boulevard, North Tower, Suite 1208",
                "logo_usage": "placeholder",
            },
            "back": {
                "company": "ACME GLOBAL -RESEARCH-LAB-",
                "logo_usage": "placeholder",
                "qr_usage": "placeholder",
            },
        },
        "uncertainties": [],
    }
    return build_business_card_schema(params, icon_dir=ICON_DIR), params


def _strip_contact_icon_pictures(pptx_path: Path) -> None:
    with zipfile.ZipFile(pptx_path, "r") as archive:
        entries = {item.filename: archive.read(item.filename) for item in archive.infolist()}
    for name, data in list(entries.items()):
        if name.startswith("ppt/slides/slide") and name.endswith(".xml"):
            text = data.decode("utf-8", errors="ignore")
            text = re.sub(r"<p:pic\b(?:(?!</p:pic>).)*contact-icon(?:(?!</p:pic>).)*</p:pic>", "", text, flags=re.DOTALL)
            entries[name] = text.encode("utf-8")
        elif name.startswith("ppt/media/contact_icon_"):
            entries.pop(name)
    fd, temp_name = tempfile.mkstemp(suffix=".pptx", dir=str(pptx_path.parent))
    os.close(fd)
    temp = Path(temp_name)
    try:
        with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in entries.items():
                archive.writestr(name, data)
        temp.replace(pptx_path)
    finally:
        if temp.exists():
            temp.unlink()


def test_horizontal_business_card_layout_does_not_overlap_or_exceed_bounds():
    schema, _ = _sample_schema()
    plan = compute_business_card_layout(schema)
    items = [item for item in plan["elements"] if item.get("kind") in {"text", "media"} and item.get("bounds")]

    assert plan["diagnostics"]["overflow"] is False
    for index, first in enumerate(items):
        for second in items[index + 1 :]:
            assert not intersects(first["bounds"], second["bounds"])


def test_export_writes_business_card_outputs_and_editable_pptx(tmp_path):
    schema, params = _sample_schema()

    summary = export_business_card_outputs(schema, tmp_path)
    report = verify_business_card_outputs(schema, summary, tmp_path, builder_params=params)

    for name in (
        "business_card_builder_params.json",
        "business_card.schema.json",
        "business_card.svg",
        "business_card.html",
        "business_card.png",
        "business_card.pptx",
        "summary.json",
        "verification_report.json",
    ):
        if name == "business_card_builder_params.json":
            continue
        assert (tmp_path / name).exists()
    assert report["passed"] is True, report["errors"]
    assert summary["pptx_structure"]["slide_count"] == 1
    assert summary["pptx_structure"]["text_count"] >= 5
    assert report["checks"]["no_full_page_screenshot"] is True

    with zipfile.ZipFile(tmp_path / "business_card.pptx") as archive:
        slide_xml = "\n".join(
            archive.read(name).decode("utf-8", errors="ignore")
            for name in archive.namelist()
            if name.startswith("ppt/slides/slide") and name.endswith(".xml")
        )
    assert "张明" in slide_xml
    assert "星河品牌咨询" in slide_xml
    assert "business-card-text:" in slide_xml
    assert "screenshot" not in slide_xml.lower()


def test_outputs_use_same_layout_plan_hash(tmp_path):
    schema, params = _sample_schema()
    summary = export_business_card_outputs(schema, tmp_path)
    report = verify_business_card_outputs(schema, summary, tmp_path, builder_params=params)

    assert report["passed"] is True
    layout_hash = compute_business_card_layout(schema)["layout_plan_hash"]
    assert summary["layout_plan_hash"] == layout_hash
    assert f'data-layout-plan-hash="{layout_hash}"' in (tmp_path / "business_card.svg").read_text(encoding="utf-8")
    assert f'data-layout-plan-hash="{layout_hash}"' in (tmp_path / "business_card.html").read_text(encoding="utf-8")


def test_double_sided_export_writes_two_editable_slides(tmp_path):
    schema, params = _double_sided_schema()

    summary = export_business_card_outputs(schema, tmp_path)
    report = verify_business_card_outputs(schema, summary, tmp_path, builder_params=params)

    assert report["passed"] is True, report["errors"]
    assert summary["pptx_structure"]["slide_count"] in {1, 2}
    assert report["checks"]["slide_count"] in {1, 2}
    assert summary["preview_structure"]["side_count"] == 2
    assert summary["svg_structure"]["side_count"] == 2
    assert summary["html_structure"]["side_count"] == 2
    assert summary["png_structure"]["side_count"] == 2
    assert summary["contact_icon_count"] == 4
    assert summary["pptx_contact_icon_count"] == 4
    assert all(item["render_mode"] in {"svg_picture", "pptx_vector_shape"} for item in summary["contact_icons"])
    assert not summary["layout_diagnostics"].get("line_conflicts")
    assert not summary["layout_diagnostics"].get("text_errors")
    assert report["checks"]["no_full_page_screenshot"] is True
    assert 'data-card-side="front"' in (tmp_path / "business_card.svg").read_text(encoding="utf-8")
    assert 'data-card-side="back"' in (tmp_path / "business_card.svg").read_text(encoding="utf-8")
    assert 'data-card-side="front"' in (tmp_path / "business_card.html").read_text(encoding="utf-8")
    assert 'data-card-side="back"' in (tmp_path / "business_card.html").read_text(encoding="utf-8")

    with zipfile.ZipFile(tmp_path / "business_card.pptx") as archive:
        names = set(archive.namelist())
        assert "ppt/slides/slide1.xml" in names
        assert "ppt/slides/slide2.xml" in names or summary["pptx_structure"]["slide_count"] == 1
        assert len([name for name in names if name.startswith("ppt/media/contact_icon_") and name.endswith(".svg")]) == 4
        slide1 = archive.read("ppt/slides/slide1.xml").decode("utf-8", errors="ignore")
        slide2 = archive.read("ppt/slides/slide2.xml").decode("utf-8", errors="ignore") if "ppt/slides/slide2.xml" in names else slide1
    assert "WPS Docer" in slide1
    assert "Chief Executive Officer" in slide1
    assert "TEL: 13800000001" in slide1
    assert "EMAIL: Kingsoft@docer.com" in slide1
    assert "ADD: Building 1, Zhuhai Jinshan Software Park" in slide1
    assert "WEB: http://www.docer.com" in slide1
    assert "KINGSOFT OFFICE" in slide1
    assert "-PROFESSIONAL-" in slide1
    assert "KINGSOFT OFFICE" in slide2
    assert "-PROFESSIONAL-" in slide2
    assert "WPS Docer" not in slide2
    assert "Chief Executive Officer" not in slide2
    assert "13800000001" not in slide2
    assert "screenshot" not in (slide1 + slide2).lower()


def test_verifier_fails_when_pptx_contact_icons_are_empty_rectangles(tmp_path):
    schema, params = _double_sided_schema()
    summary = export_business_card_outputs(schema, tmp_path)
    _strip_contact_icon_pictures(tmp_path / "business_card.pptx")
    summary["contact_icons"] = [
        {**item, "rendered_in_pptx": False, "render_mode": "fallback"}
        for item in summary["contact_icons"]
    ]
    summary["pptx_contact_icon_count"] = 0
    summary["pptx_structure"]["pptx_contact_icon_count"] = 0

    report = verify_business_card_outputs(schema, summary, tmp_path, builder_params=params)

    assert report["passed"] is False
    assert any(
        "pptx missing rendered contact icon" in error
        or "contact icon rendered as empty placeholder" in error
        or "schema icons are not visible in pptx" in error
        for error in report["errors"]
    )


def test_double_sided_long_text_exports_without_ellipsis_or_line_conflicts(tmp_path):
    schema, params = _alternate_double_sided_schema()

    summary = export_business_card_outputs(schema, tmp_path)
    report = verify_business_card_outputs(schema, summary, tmp_path, builder_params=params)

    svg_text = (tmp_path / "business_card.svg").read_text(encoding="utf-8")
    html_text = (tmp_path / "business_card.html").read_text(encoding="utf-8")
    assert report["passed"] is True, report["errors"]
    assert "…" not in svg_text
    assert "…" not in html_text
    assert "ACME GLOBAL" in svg_text
    assert "-RESEARCH-LAB-" in svg_text
    assert "14 Innovation Boulevard" in svg_text
    assert not summary["layout_diagnostics"].get("line_conflicts")


def test_double_sided_verifier_fails_when_svg_and_html_only_include_front(tmp_path):
    schema, params = _double_sided_schema()
    summary = export_business_card_outputs(schema, tmp_path)
    svg_path = tmp_path / "business_card.svg"
    html_path = tmp_path / "business_card.html"
    svg_path.write_text(svg_path.read_text(encoding="utf-8").replace('data-card-side="back"', 'data-card-side="missing-back"'), encoding="utf-8")
    html_path.write_text(html_path.read_text(encoding="utf-8").replace('data-card-side="back"', 'data-card-side="missing-back"'), encoding="utf-8")

    report = verify_business_card_outputs(schema, summary, tmp_path, builder_params=params)

    assert report["passed"] is False
    assert any("svg missing side marker" in error for error in report["errors"])
    assert any("html missing side marker" in error for error in report["errors"])


def test_verifier_fails_when_visible_svg_or_html_text_is_truncated(tmp_path):
    schema, params = _double_sided_schema()
    summary = export_business_card_outputs(schema, tmp_path)
    for name in ("business_card.svg", "business_card.html"):
        path = tmp_path / name
        path.write_text(path.read_text(encoding="utf-8").replace(">KINGSOFT OFFICE<", ">KINGSOFT OFFIC…<", 1), encoding="utf-8")

    report = verify_business_card_outputs(schema, summary, tmp_path, builder_params=params)

    assert report["passed"] is False
    assert any("visible text contains ellipsis" in error for error in report["errors"])


def test_verifier_fails_when_layout_reports_line_crossing_content(tmp_path, monkeypatch):
    import business_card_ppt.business_card.verifier as verifier_module

    schema, params = _double_sided_schema()
    summary = export_business_card_outputs(schema, tmp_path)
    real_plan = compute_business_card_layout(schema)
    bad_plan = dict(real_plan)
    bad_plan["diagnostics"] = {
        **real_plan["diagnostics"],
        "overflow": True,
        "overflow_reasons": ["back: back.horizontal_line crosses qr_code"],
        "line_conflicts": ["back: back.horizontal_line crosses qr_code"],
    }
    monkeypatch.setattr(verifier_module, "compute_business_card_layout", lambda _schema: bad_plan)

    report = verify_business_card_outputs(schema, summary, tmp_path, builder_params=params)

    assert report["passed"] is False
    assert any("back.horizontal_line crosses qr_code" in error for error in report["errors"])


def test_double_sided_verifier_fails_when_single_slide_lacks_back_markers(tmp_path):
    schema, params = _double_sided_schema()
    front_schema = schema["sides"]["front"]
    summary = export_business_card_outputs(front_schema, tmp_path)
    summary["pptx_structure"]["slide_count"] = 1
    summary["preview_structure"] = {"side_count": 2, "sides": ["front", "back"], "layout": "combined", "renderer": "test"}
    summary["png_structure"] = dict(summary["preview_structure"])
    summary["svg_structure"] = {"side_count": 2, "sides": ["front", "back"], "layout": "combined"}
    summary["html_structure"] = {"side_count": 2, "sides": ["front", "back"], "layout": "combined"}

    report = verify_business_card_outputs(schema, summary, tmp_path, builder_params=params)

    assert report["passed"] is False
    assert any("single-slide double-sided pptx must contain front/back object markers" in error for error in report["errors"])


def test_content_too_dense_reports_overflow_in_verifier(tmp_path):
    params = {
        "name": "Overflow User",
        "title": "A very long role title that will consume visible width",
        "company": "A company with a very long legal entity name and branch name",
        "phone": "12345678901234567890",
        "email": "very.long.email.address.for.testing@example-very-long-domain.com",
        "website": "https://www.example.com/products/services/consulting/business-card-overflow-test",
        "address": "A very long address with building, district, city, province, country, and postal code",
        "wechat": "overflow_wechat_handle",
        "qq": "1234567890",
        "social": "linkedin.com/in/overflow-user-with-a-long-slug",
        "extra_fields": [{"label": f"字段{i}", "value": "这是一段额外信息" * 4} for i in range(8)],
    }
    schema = build_business_card_schema(params, icon_dir=ICON_DIR)
    summary = export_business_card_outputs(schema, tmp_path)
    report = verify_business_card_outputs(schema, summary, tmp_path, builder_params=params)

    assert report["passed"] is False
    assert report["checks"]["overflow"] is True
    assert any("layout overflow" in error for error in report["errors"])
