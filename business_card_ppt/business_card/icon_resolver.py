from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ICON_ALIASES = {
    "phone": ("phone", "tel", "mobile", "电话"),
    "email": ("email", "mail", "邮箱"),
    "website": ("website", "web", "url", "网站"),
    "address": ("address", "location", "map", "地址"),
    "wechat": ("wechat", "weixin", "微信"),
    "qq": ("qq", "QQ"),
    "social": ("social", "share", "社交"),
}


@dataclass(frozen=True)
class IconResult:
    requested: str
    used: str | None
    path: Path | None
    fallback: bool
    reason: str = ""

    def to_summary(self) -> dict[str, str]:
        return {
            "requested": self.requested,
            "used": self.used or "",
            "path": str(self.path or ""),
            "reason": self.reason,
        }


def scan_svg_icons(icon_dir: str | Path | None) -> dict[str, Path]:
    root = Path(icon_dir) if icon_dir else Path(__file__).resolve().parents[2] / "svg_material"
    if not root.exists():
        return {}
    icons: dict[str, Path] = {}
    for path in root.glob("*.svg"):
        icons[path.stem.lower()] = path
        icons[path.stem] = path
    return icons


def resolve_icon(kind: str | None, icon_dir: str | Path | None = None) -> IconResult:
    requested = str(kind or "").strip()
    if not requested:
        return IconResult("", None, None, False)
    icons = scan_svg_icons(icon_dir)
    candidates = [requested, requested.lower()]
    for canonical, aliases in ICON_ALIASES.items():
        if requested.lower() == canonical or requested in aliases or requested.lower() in [alias.lower() for alias in aliases]:
            candidates.extend([canonical, *aliases])
            break
    for candidate in candidates:
        if candidate in icons:
            return IconResult(requested, icons[candidate].stem, icons[candidate], False)
        if candidate.lower() in icons:
            path = icons[candidate.lower()]
            return IconResult(requested, path.stem, path, False)
    default_path = icons.get("default") or icons.get("默认")
    if default_path:
        return IconResult(requested, default_path.stem, default_path, True, "requested contact icon was not found; default icon used")
    return IconResult(requested, None, None, True, "requested contact icon was not found; icon omitted")

