from __future__ import annotations

import json
import sys


def main() -> int:
    prompt = sys.stdin.read()
    if "business_card_builder_params.json" not in prompt:
        raise SystemExit("prompt is not the business card builder params prompt")
    payload = {
        "name": "Fake Sample",
        "company": "Demo Studio",
        "phone": "10086",
        "layout_style": "minimal_corner",
        "style": {
            "accent_color": "#008577",
            "background_color": "#FFFFFF",
            "text_color": "#111111",
        },
        "uncertainties": [],
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

