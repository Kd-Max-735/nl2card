from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from business_card_ppt.business_card.icon_resolver import resolve_icon
from business_card_ppt.core.schema import (
    DEFAULT_ICON_POLICY,
    DEFAULT_LAYOUT,
    DEFAULT_STYLE,
    PLACEHOLDER_TEXT,
    card_size_from_params,
    merge_defaults,
    normalize_layout_style,
    validate_schema_contract,
)


STANDARD_FIELDS = (
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
)

FIELD_ALIASES = {
    "role": "title",
    "tagline": "slogan",
    "tel": "phone",
    "mobile": "phone",
    "mail": "email",
    "url": "website",
    "location": "address",
    "weixin": "wechat",
}

CONTACT_FIELD_ORDER = ("phone", "email", "website", "address", "wechat", "qq", "social")
MEDIA_TYPES = ("logo", "avatar", "qr_code")
STYLE_KEYS = (
    "primary_color",
    "secondary_color",
    "background_color",
    "text_color",
    "muted_text_color",
    "accent_color",
    "font_family",
    "style_keywords",
)


def _is_declared_empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def _is_placeholder_value(value: Any) -> bool:
    return isinstance(value, str) and value.strip() == PLACEHOLDER_TEXT


def _placeholder(path: str, placeholders: list[dict[str, str]]) -> str:
    placeholders.append({"path": path, "text": PLACEHOLDER_TEXT})
    return PLACEHOLDER_TEXT


def _source_dict(params: dict[str, Any]) -> dict[str, Any]:
    card = params.get("business_card") if isinstance(params.get("business_card"), dict) else {}
    profile = params.get("profile") if isinstance(params.get("profile"), dict) else {}
    person = params.get("person") if isinstance(params.get("person"), dict) else {}
    merged: dict[str, Any] = {}
    for source in (card, profile, person, params):
        for key, value in source.items():
            if key not in merged:
                merged[key] = value
    return merged


def _normalize_field_value(key: str, value: Any, placeholders: list[dict[str, str]]) -> tuple[str, Any, bool]:
    canonical = FIELD_ALIASES.get(key, key)
    path = f"fields.{canonical}"
    if _is_declared_empty(value):
        return canonical, _placeholder(path, placeholders), True
    if _is_placeholder_value(value):
        placeholders.append({"path": path, "text": PLACEHOLDER_TEXT})
        return canonical, PLACEHOLDER_TEXT, True
    return canonical, value, False


def _normalize_fields(params: dict[str, Any], placeholders: list[dict[str, str]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source = _source_dict(params)
    fields: dict[str, Any] = {}
    field_meta: list[dict[str, Any]] = []
    for raw_key in STANDARD_FIELDS:
        if raw_key not in source:
            continue
        key, value, placeholder = _normalize_field_value(raw_key, source[raw_key], placeholders)
        if key in fields and fields[key] == value:
            continue
        fields[key] = value
        field_meta.append({"key": key, "source_key": raw_key, "placeholder": placeholder})

    for raw_field in params.get("fields") or []:
        if not isinstance(raw_field, dict):
            continue
        raw_key = str(raw_field.get("key") or raw_field.get("name") or raw_field.get("field") or "").strip()
        if not raw_key:
            continue
        key, value, placeholder = _normalize_field_value(raw_key, raw_field.get("value"), placeholders)
        fields[key] = value
        field_meta.append({"key": key, "source_key": raw_key, "placeholder": placeholder})
    return fields, field_meta


def _normalize_extra_fields(params: dict[str, Any], fields: dict[str, Any], placeholders: list[dict[str, str]]) -> list[dict[str, Any]]:
    extras: list[dict[str, Any]] = []
    raw_extra = params.get("extra_fields") or []
    if isinstance(raw_extra, dict):
        raw_extra = [{"label": key, "value": value} for key, value in raw_extra.items()]
    for index, item in enumerate(raw_extra):
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or item.get("key") or item.get("name") or "").strip()
        if not label:
            continue
        value = item.get("value")
        placeholder = False
        if _is_declared_empty(value):
            value = _placeholder(f"extra_fields[{index}].value", placeholders)
            placeholder = True
        elif _is_placeholder_value(value):
            placeholders.append({"path": f"extra_fields[{index}].value", "text": PLACEHOLDER_TEXT})
            placeholder = True
        if str(label).lower() not in fields:
            extras.append({"label": label, "value": value, "placeholder": placeholder})
    return extras


def _resolve_path(path_text: str | None) -> tuple[str | None, bool, str]:
    if not path_text:
        return None, False, ""
    raw = Path(path_text)
    resolved = raw if raw.is_absolute() else Path.cwd() / raw
    return str(resolved), resolved.exists(), "absolute" if raw.is_absolute() else "cwd_relative"


def _raw_media(params: dict[str, Any], media_type: str) -> Any:
    assets = params.get("assets") if isinstance(params.get("assets"), dict) else {}
    media = params.get("media") if isinstance(params.get("media"), dict) else {}
    return (
        params.get(f"{media_type}_path")
        or assets.get(media_type)
        or media.get(media_type)
        or params.get(media_type)
    )


def _normalize_media_item(params: dict[str, Any], media_type: str, warnings: list[str]) -> dict[str, Any]:
    raw = _raw_media(params, media_type)
    requested = raw is not None
    usage_key = "qr_usage" if media_type == "qr_code" else f"{media_type}_usage"
    media_usage = params.get("media_usage") if isinstance(params.get("media_usage"), dict) else {}
    usage = params.get(usage_key) or media_usage.get(media_type)
    if isinstance(raw, dict):
        path_text = raw.get("path") or raw.get("src")
        requested = True
    else:
        path_text = raw
    if isinstance(path_text, str) and path_text.strip().lower() in {"placeholder", "占位", "占位图"}:
        path_text = None
        requested = True
    if not path_text:
        placeholder = bool(
            requested
            or str(usage or "").lower()
            in {"placeholder", "required", "show", "visible", "front", "back", "front_and_back", "both"}
        )
        return {
            "type": media_type,
            "source": None,
            "path": None,
            "exists": False,
            "loaded": False,
            "placeholder": placeholder,
            "missing": False,
            "requested": requested or placeholder,
        }
    resolved, exists, resolution = _resolve_path(str(path_text))
    if not exists:
        warnings.append(f"{media_type}_path does not exist; placeholder will be rendered: {path_text}")
    return {
        "type": media_type,
        "source": str(path_text),
        "path": resolved,
        "path_resolution": resolution,
        "exists": exists,
        "loaded": exists,
        "placeholder": not exists,
        "missing": not exists,
        "requested": True,
    }


def _normalize_style(params: dict[str, Any]) -> dict[str, Any]:
    raw_style = params.get("style") if isinstance(params.get("style"), dict) else {}
    theme = params.get("theme") if isinstance(params.get("theme"), dict) else {}
    style = merge_defaults(DEFAULT_STYLE, theme)
    style = merge_defaults(style, raw_style)
    style_intent = params.get("style_intent") if isinstance(params.get("style_intent"), dict) else {}
    for key in STYLE_KEYS:
        if key in params and params[key]:
            style[key] = params[key]
        if key in style_intent and style_intent[key]:
            style.setdefault(key, style_intent[key])
    keywords = style.get("style_keywords") or style_intent.get("style_keywords") or []
    if isinstance(keywords, str):
        keywords = [keywords]
    style["style_keywords"] = keywords
    explicit_accent = bool(raw_style.get("accent_color") or theme.get("accent_color") or params.get("accent_color"))
    keyword_text = " ".join(str(item).lower() for item in keywords)
    design = params.get("design") if isinstance(params.get("design"), dict) else {}
    if not explicit_accent and ("黑白" in keyword_text or "black" in keyword_text or design.get("line_color") == "#000000"):
        style["accent_color"] = "#000000"
        style.setdefault("secondary_color", "#D9D9D9")
    if style_intent:
        style["source_intent"] = deepcopy(style_intent)
    return style


def _normalize_icon_policy(params: dict[str, Any], style: dict[str, Any]) -> dict[str, Any]:
    policy = merge_defaults(DEFAULT_ICON_POLICY, params.get("icon_policy") if isinstance(params.get("icon_policy"), dict) else {})
    keywords = " ".join(str(item).lower() for item in style.get("style_keywords") or [])
    if "极简" in keywords or "minimal" in keywords:
        policy["contact_icons"] = bool(policy.get("force_contact_icons", False))
    return policy


def _contact_records(fields: dict[str, Any], icon_policy: dict[str, Any], icon_dir: str | Path | None) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[dict[str, str]]]:
    contacts: list[dict[str, Any]] = []
    icons: list[dict[str, str]] = []
    fallbacks: list[dict[str, str]] = []
    for key in CONTACT_FIELD_ORDER:
        if key not in fields:
            continue
        contact: dict[str, Any] = {"kind": key, "value": fields[key]}
        if icon_policy.get("contact_icons", True):
            result = resolve_icon(key, icon_dir)
            if result.path:
                contact["icon"] = {"requested": result.requested, "used": result.used, "path": str(result.path)}
                icons.append(contact["icon"])
            if result.fallback:
                fallbacks.append(result.to_summary())
        contacts.append(contact)
    return contacts, icons, fallbacks


def _normalize_design(params: dict[str, Any]) -> dict[str, Any]:
    raw = params.get("design") if isinstance(params.get("design"), dict) else {}
    design = {
        "background_texture": raw.get("background_texture"),
        "diagonal_stripes": bool(raw.get("diagonal_stripes") or raw.get("background_texture") == "light_gray_diagonal_stripes"),
        "horizontal_line": bool(raw.get("horizontal_line")),
        "geometric_block": raw.get("geometric_block"),
        "line_color": raw.get("line_color") or raw.get("block_color") or "#000000",
        "stripe_color": raw.get("stripe_color") or "#E6E6E6",
    }
    if raw:
        for key, value in raw.items():
            design.setdefault(key, value)
    return design


def _side_dicts(params: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_sides = params.get("sides")
    if isinstance(raw_sides, dict):
        result = {
            key: value
            for key, value in raw_sides.items()
            if key in {"front", "back"} and isinstance(value, dict)
        }
        if result:
            return result
    if isinstance(raw_sides, list):
        result: dict[str, dict[str, Any]] = {}
        for item in raw_sides:
            if not isinstance(item, dict):
                continue
            side_key = str(item.get("side") or item.get("name") or "").strip().lower()
            if side_key in {"front", "back"}:
                result[side_key] = item
        if result:
            return result
    result = {}
    for side_key in ("front", "back"):
        value = params.get(side_key)
        if isinstance(value, dict):
            result[side_key] = value
    return result


def _shared_side_params(params: dict[str, Any]) -> dict[str, Any]:
    skip = set(STANDARD_FIELDS) | {"fields", "extra_fields", "sides", "front", "back", "uncertainties"}
    return {key: deepcopy(value) for key, value in params.items() if key not in skip}


def _merge_side_params(shared: dict[str, Any], side: dict[str, Any], side_key: str, root: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(shared)
    if side_key == "front":
        for key in STANDARD_FIELDS:
            if key in root and key not in side:
                merged[key] = deepcopy(root[key])
        if "fields" in root and "fields" not in side:
            merged["fields"] = deepcopy(root["fields"])
        if "extra_fields" in root and "extra_fields" not in side:
            merged["extra_fields"] = deepcopy(root["extra_fields"])
    merged.update(deepcopy(side))
    merged["side"] = side_key
    if side_key == "back":
        for key in CONTACT_FIELD_ORDER + ("name", "title", "role", "department", "slogan", "tagline", "brand_name"):
            if key not in side:
                merged.pop(key, None)
        if "fields" not in side:
            merged.pop("fields", None)
        if "extra_fields" not in side:
            merged["extra_fields"] = []
    return merged


def _combine_intentional_media(sides: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for side_key, side_schema in sides.items():
        for item in side_schema.get("assets", {}).get("intentional_media", []):
            record = deepcopy(item)
            record["side"] = side_key
            marker = (str(record.get("type")), str(record.get("path")), side_key)
            if marker not in seen:
                records.append(record)
                seen.add(marker)
    return records


def _build_single_business_card_schema(
    builder_params: dict[str, Any] | None,
    icon_dir: str | Path | None = None,
    side: str | None = None,
) -> dict[str, Any]:
    params = deepcopy(builder_params or {})
    warnings: list[str] = []
    placeholders: list[dict[str, str]] = []
    card_size = card_size_from_params(params)
    raw_layout = params.get("layout") if isinstance(params.get("layout"), dict) else {}
    layout_style, layout_warning = normalize_layout_style(params.get("layout_style") or raw_layout.get("layout_style"))
    layout = merge_defaults(DEFAULT_LAYOUT, params.get("layout") if isinstance(params.get("layout"), dict) else {})
    layout["layout_style"] = layout_style
    layout["safe_margin"] = int(card_size["safe_margin"])
    layout["bleed"] = int(card_size["bleed"])
    if layout_warning:
        warnings.append(layout_warning)

    fields, field_meta = _normalize_fields(params, placeholders)
    extra_fields = _normalize_extra_fields(params, fields, placeholders)
    style = _normalize_style(params)
    icon_policy = _normalize_icon_policy(params, style)
    contacts, icons, fallback_icons = _contact_records(fields, icon_policy, icon_dir)
    media = {media_type: _normalize_media_item(params, media_type, warnings) for media_type in MEDIA_TYPES}
    intentional_media = [
        {
            "type": item["type"],
            "source": item.get("source"),
            "path": item.get("path"),
            "loaded": bool(item.get("loaded")),
            "placeholder": bool(item.get("placeholder")),
            "missing": bool(item.get("missing")),
            "reason": "local business card media; never used as a full-slide screenshot",
        }
        for item in media.values()
        if item.get("requested") or item.get("placeholder") or item.get("path")
    ]

    schema: dict[str, Any] = {
        "type": "business_card",
        "component": "EditableBusinessCard",
        "version": "1.0",
        "side": side or params.get("side") or "front",
        "card_size": card_size,
        "canvas": {"width": card_size["width"], "height": card_size["height"]},
        "style": style,
        "layout": layout,
        "design": _normalize_design(params),
        "icon_policy": icon_policy,
        "fields": fields,
        "field_meta": field_meta,
        "contacts": contacts,
        "extra_fields": extra_fields,
        "assets": {
            **media,
            "icons": icons,
            "fallback_icons": fallback_icons,
            "intentional_media": intentional_media,
        },
        "placeholders": {"text": PLACEHOLDER_TEXT, "items": placeholders},
        "uncertainties": deepcopy(params.get("uncertainties") or []),
        "warnings": warnings,
    }
    errors = validate_schema_contract(schema)
    if errors:
        raise ValueError("; ".join(errors))
    return schema


def build_business_card_schema(builder_params: dict[str, Any] | None, icon_dir: str | Path | None = None) -> dict[str, Any]:
    params = deepcopy(builder_params or {})
    side_params = _side_dicts(params)
    if not side_params:
        return _build_single_business_card_schema(params, icon_dir=icon_dir)

    shared = _shared_side_params(params)
    if "front" not in side_params:
        side_params["front"] = {}
    if "back" not in side_params:
        side_params["back"] = {}

    side_schemas: dict[str, dict[str, Any]] = {}
    for side_key in ("front", "back"):
        merged = _merge_side_params(shared, side_params[side_key], side_key, params)
        side_schemas[side_key] = _build_single_business_card_schema(merged, icon_dir=icon_dir, side=side_key)

    schema = deepcopy(side_schemas["front"])
    schema["side"] = "front"
    schema["double_sided"] = True
    schema["side_order"] = ["front", "back"]
    schema["sides"] = side_schemas
    schema["assets"]["intentional_media"] = _combine_intentional_media(side_schemas)
    schema["warnings"] = sorted(
        set(schema.get("warnings", []) + side_schemas["back"].get("warnings", []))
    )
    schema["uncertainties"] = deepcopy(params.get("uncertainties") or [])
    return schema
