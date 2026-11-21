from __future__ import annotations

from business_card_ppt.business_card.text_layout import wrap_text


def test_latin_brand_phrase_wraps_on_word_boundary_without_ellipsis():
    lines = wrap_text("ACME GLOBAL -RESEARCH-LAB-", width=72, font_size=8, max_lines=2)

    assert lines == ["ACME GLOBAL", "-RESEARCH-LAB-"]
    assert all("…" not in line for line in lines)


def test_long_address_wraps_without_silent_truncation():
    text = "ADD: 14 Innovation Boulevard, North Tower, Suite 1208"
    lines = wrap_text(text, width=150, font_size=8, max_lines=2)

    assert "…" not in " ".join(lines)
    assert "".join(lines).replace(" ", "") == text.replace(" ", "")
