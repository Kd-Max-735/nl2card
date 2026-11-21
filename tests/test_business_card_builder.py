from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from business_card_ppt.business_card.builder import build_business_card_schema


ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "svg_material"


def test_direct_builder_params_create_business_card_schema():
    params = json.loads((ROOT / "tests" / "fixtures" / "sample_business_card_builder_params.json").read_text(encoding="utf-8"))

    schema = build_business_card_schema(params, icon_dir=ICON_DIR)

    assert schema["type"] == "business_card"
    assert schema["component"] == "EditableBusinessCard"
    assert schema["card_size"]["orientation"] == "horizontal_card"
    assert schema["card_size"]["width"] == 340
    assert schema["card_size"]["height"] == 204
    assert schema["fields"]["name"] == "张明"
    assert schema["fields"]["company"] == "星河品牌咨询"
    assert "education" not in schema
    assert "sections" not in schema


def test_user_explicit_fields_are_preserved_and_unmentioned_fields_are_not_generated():
    params = {
        "name": "Alex Chen",
        "company": "North Studio",
        "phone": "555-0100",
        "extra_fields": [{"label": "预约码", "value": "A-19"}],
    }

    schema = build_business_card_schema(params, icon_dir=ICON_DIR)

    assert schema["fields"] == {"name": "Alex Chen", "company": "North Studio", "phone": "555-0100"}
    assert schema["extra_fields"] == [{"label": "预约码", "value": "A-19", "placeholder": False}]
    assert "email" not in schema["fields"]
    assert "website" not in schema["fields"]


def test_empty_declared_field_becomes_placeholder():
    schema = build_business_card_schema({"name": "", "company": "Acme"}, icon_dir=ICON_DIR)

    assert schema["fields"]["name"] == "等待用户填入"
    assert schema["field_meta"][0]["placeholder"] is True
    assert schema["placeholders"]["items"] == [{"path": "fields.name", "text": "等待用户填入"}]


def test_media_paths_valid_missing_and_unprovided(tmp_path):
    logo = tmp_path / "logo.png"
    Image.new("RGB", (40, 20), "#123456").save(logo)

    schema = build_business_card_schema(
        {
            "name": "Media Test",
            "logo_path": str(logo),
            "avatar_path": str(tmp_path / "missing-avatar.png"),
            "qr_usage": "placeholder",
        },
        icon_dir=ICON_DIR,
    )

    assert schema["assets"]["logo"]["loaded"] is True
    assert schema["assets"]["avatar"]["missing"] is True
    assert schema["assets"]["avatar"]["placeholder"] is True
    assert schema["assets"]["qr_code"]["placeholder"] is True
    assert any(item["type"] == "logo" and item["loaded"] for item in schema["assets"]["intentional_media"])
    assert any("avatar_path does not exist" in warning for warning in schema["warnings"])


def test_style_color_font_keywords_enter_schema_style():
    schema = build_business_card_schema(
        {
            "name": "Style Test",
            "style": {
                "primary_color": "#001122",
                "background_color": "#FAFAFA",
                "text_color": "#111111",
                "accent_color": "#DD5500",
                "font_family": "SimHei",
                "style_keywords": ["科技感", "金融"],
            },
        },
        icon_dir=ICON_DIR,
    )

    assert schema["style"]["primary_color"] == "#001122"
    assert schema["style"]["background_color"] == "#FAFAFA"
    assert schema["style"]["accent_color"] == "#DD5500"
    assert schema["style"]["font_family"] == "SimHei"
    assert schema["style"]["style_keywords"] == ["科技感", "金融"]


def test_minimal_style_can_disable_contact_icons():
    schema = build_business_card_schema(
        {"name": "Icon Test", "phone": "555", "style": {"style_keywords": ["极简"]}},
        icon_dir=ICON_DIR,
    )

    assert schema["icon_policy"]["contact_icons"] is False
    assert schema["contacts"][0].get("icon") is None


def test_double_sided_builder_params_create_front_and_back_schemas():
    params = json.loads((ROOT / "tests" / "fixtures" / "double_sided_business_card_builder_params.json").read_text(encoding="utf-8"))

    schema = build_business_card_schema(params, icon_dir=ICON_DIR)

    assert schema["double_sided"] is True
    assert schema["side_order"] == ["front", "back"]
    assert schema["sides"]["front"]["fields"]["name"] == "WPS Docer"
    assert schema["sides"]["front"]["fields"]["phone"] == "13800000001"
    assert schema["sides"]["back"]["fields"] == {"company": "KINGSOFT OFFICE -PROFESSIONAL-"}
    assert schema["sides"]["front"]["assets"]["logo"]["placeholder"] is True
    assert schema["sides"]["back"]["assets"]["qr_code"]["placeholder"] is True
    assert schema["sides"]["front"]["design"]["diagonal_stripes"] is True
