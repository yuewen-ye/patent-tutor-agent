"""Text fitting helpers for slide layout overflow prevention."""

from __future__ import annotations

import pytest

from backend.app.presentation.renderer.text_fit import (
    estimate_text_height,
    scaled_font_size_to_fit,
)

pytestmark = pytest.mark.unit


def test_estimate_height_increases_with_longer_text() -> None:
    short = estimate_text_height("短", width_inches=4.0, font_size_pt=18)
    long = estimate_text_height("这是一段很长的中文文本，用来测试换行后的高度。", width_inches=4.0, font_size_pt=18)
    assert long > short


def test_estimate_height_increases_with_narrower_box() -> None:
    text = "这是一段用来测试换行的中文文本。"
    wide = estimate_text_height(text, width_inches=6.0, font_size_pt=18)
    narrow = estimate_text_height(text, width_inches=2.0, font_size_pt=18)
    assert narrow > wide


def test_scaled_font_size_reduces_when_text_overflows() -> None:
    text = "这是一段非常非常长的中文文本，肯定会超出固定高度的小文本框。"
    fitted = scaled_font_size_to_fit(
        text, width_inches=2.0, height_inches=0.5, requested_size_pt=24
    )
    assert fitted < 24


def test_scaled_font_size_keeps_requested_size_when_it_fits() -> None:
    text = "短文本"
    fitted = scaled_font_size_to_fit(
        text, width_inches=4.0, height_inches=1.0, requested_size_pt=18
    )
    assert fitted == 18


def test_scaled_font_size_respects_minimum() -> None:
    text = "这是一段极其长的中文文本" * 50
    fitted = scaled_font_size_to_fit(
        text, width_inches=1.0, height_inches=0.2, requested_size_pt=24, min_size_pt=8
    )
    assert fitted >= 8
