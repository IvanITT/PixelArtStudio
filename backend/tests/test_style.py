import numpy as np
from PIL import Image, ImageDraw

from app.services.style import aggregate_report, analyze_image, apply_style, normalize_profile


def sprite(w=48, h=48):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([8, 8, 40, 40], fill=(200, 70, 80, 255))
    d.rectangle([18, 18, 30, 30], fill=(30, 40, 90, 255))
    return img


def test_profile_defaults_and_palette_resolution():
    profile = normalize_profile({"palette_id": "gameboy", "pixel_scale": 99, "outline": "weird"})
    assert profile["colors"] == ["#0f380f", "#306230", "#8bac0f", "#9bbc0f"]
    assert profile["pixel_scale"] == 8
    assert profile["outline"] == "none"
    assert profile["max_colors"] == 0


def test_palette_application_is_exact_and_audited():
    styled, info = apply_style(sprite(), {"colors": ["#0f380f", "#306230", "#8bac0f", "#9bbc0f"]})
    palette = {
        (15, 56, 15),
        (48, 98, 48),
        (139, 172, 15),
        (155, 188, 15),
    }
    visible = {(r, g, b) for r, g, b, a in styled.getdata() if a > 12}
    assert visible <= palette
    assert info["colors_after"] <= 4
    assert "palette" in info["applied"]
    assert info["score_after"] >= info["score_before"]


def test_outline_only_inside_alpha():
    styled, info = apply_style(sprite(), {"outline": "dark", "outline_width": 1})
    arr = np.array(styled)
    assert info["outline_pixels"] > 0
    ring = (arr[..., 3] > 0) & (np.max(arr[..., :3], axis=2) < 40)
    assert ring.sum() >= info["outline_pixels"]
    assert styled.size == (48, 48)


def test_pixel_scale_detection():
    base = sprite(24, 24)
    up = base.resize((96, 96), Image.Resampling.NEAREST)
    assert analyze_image(up, {"pixel_scale": 4})["pixel_scale"] == 4
    assert analyze_image(sprite(48, 48), {"pixel_scale": 4})["pixel_scale"] == 1
    styled, info = apply_style(sprite(71, 71), {"pixel_scale": 2})
    assert styled.size == (71, 71)
    assert info["pixel_scale_after"] == 2


def test_aggregate_reports_consistency():
    profile = {"colors": ["#0f380f", "#306230", "#8bac0f", "#9bbc0f"], "max_colors": 4}
    rows = []
    for name in ("a", "b", "c"):
        styled, info = apply_style(sprite(), profile)
        metrics = analyze_image(styled, profile)
        rows.append({"name": name, **metrics})
    summary = aggregate_report(rows)
    assert summary["assets"] == 3
    assert summary["score"] >= 80
    assert summary["consistent"] is True
    assert summary["pairwise_palette_overlap"] == 100.0
