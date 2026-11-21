# Business Card Editable PPT Project Flow

## Main Flow

```text
User natural language request
-> prompts/glm5_business_card_builder_params_from_nl_prompt.md
-> OpenCode/GLM5 one-shot JSON
-> business_card_builder_params.json
-> build_business_card_schema()
-> business_card.schema.json
-> compute_business_card_layout()
-> render_business_card_html() / render_business_card_svg()
-> export_business_card_outputs()
-> business_card.html / business_card.svg / business_card.png / business_card.pptx
-> verify_business_card_outputs()
-> summary.json / verification_report.json
```

## Layer Ownership

Prompt and GLM5:

```text
Extract only explicitly supplied business card facts.
Extract style/theme/layout/media/icon_policy intent.
Do not output resume sections.
Do not invent media paths or missing contact facts.
Do not output coordinates.
```

Builder:

```text
Normalize card_size, orientation, safe_margin, bleed, content_area.
Normalize fields: name, title, company, department, contacts, slogan, brand.
Preserve extra_fields.
Normalize logo/avatar/qr as intentional_media or placeholders.
Resolve contact icon policy.
Record warnings and uncertainties.
```

Layout:

```text
Compute all local bboxes from schema.
Adapt to media presence and field density.
Use one layout plan across SVG, HTML, PNG, PPTX, and verifier.
Mark overflow when content cannot fit safely.
```

Export:

```text
Write schema, HTML, SVG, PNG preview, PPTX, and summary.
Keep PPTX editable with text boxes, shapes, and local intentional media.
Do not insert a full-page screenshot.
```

Verifier:

```text
Check files, editable PPTX text, media accounting, full-page screenshot
avoidance, safe margins, overlap, overflow, style token usage, business-card
canvas size, and shared layout plan hash.
```

## Current Supported Scope

- Single-side card by default.
- `horizontal_card` and `vertical_card` canvas orientation.
- Layout styles: `left_logo_right_info`, `top_logo_bottom_info`, `centered`,
  `split_panel`, `minimal_corner`.
- Local logo/avatar/QR image paths or placeholders.
- Contact icons for phone/email/website/address/wechat/qq/social.

Back-side generation is intentionally not automatic. It should only be added
when the user explicitly asks for a double-sided card.

