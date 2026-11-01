import io

import numpy as np
from PIL import Image, ImageDraw

from app.services.pixelart import process_pixel_art


def sample_image(w=160, h=120):
    img = Image.new("RGB", (w, h), (245, 245, 245))
    d = ImageDraw.Draw(img)
    d.ellipse([20, 20, 80, 80], fill=(200, 40, 60))
    d.rectangle([90, 30, 140, 90], fill=(30, 120, 210))
    d.polygon([(20, 110), (80, 60), (140, 110)], fill=(60, 160, 80))
    return img


def test_resize_and_color_count():
    res = process_pixel_art(sample_image(), {"width": 64, "height": 48, "colors": 8, "dither": "none"})
    assert res.image.size == (64, 48)
    colors = {(r, g, b) for r, g, b, a in res.image.getdata() if a > 0}
    assert 1 <= len(colors) <= 8
    assert res.info["width"] == 64


def test_deterministic_output():
    a = process_pixel_art(sample_image(), {"width": 48, "height": 48, "colors": 8, "dither": "floyd"}).image
    b = process_pixel_art(sample_image(), {"width": 48, "height": 48, "colors": 8, "dither": "floyd"}).image
    assert a.tobytes() == b.tobytes()


def test_kmeans_seeded():
    a = process_pixel_art(sample_image(), {"width": 40, "height": 40, "colors": 6, "quantizer": "kmeans", "seed": 5}).image
    b = process_pixel_art(sample_image(), {"width": 40, "height": 40, "colors": 6, "quantizer": "kmeans", "seed": 5}).image
    assert a.tobytes() == b.tobytes()


def test_all_dithers_and_quantizers():
    for q in ("median_cut", "octree", "adaptive", "kmeans"):
        for d in ("floyd", "bayer", "atkinson", "jjn"):
            res = process_pixel_art(sample_image(80, 80), {
                "width": 32, "height": 32, "colors": 8, "quantizer": q, "dither": d,
            })
            assert res.image.size == (32, 32)
            assert res.info["colors_used"] <= 8


def test_custom_palette_restriction():
    palette = ["#000000", "#ff0000", "#00ff00", "#0000ff", "#ffffff"]
    res = process_pixel_art(sample_image(), {
        "width": 40, "height": 40, "palette_colors": palette, "dither": "floyd",
    })
    used = {f"#{r:02x}{g:02x}{b:02x}" for r, g, b, a in res.image.getdata() if a > 0}
    assert used <= set(palette)


def test_transparency_and_block_size():
    res = process_pixel_art(sample_image(), {
        "width": 64, "height": 64, "block_size": 4, "transparent": True,
        "bg_color": "#f5f5f5", "bg_tolerance": 20, "colors": 8, "dither": "none",
    })
    assert res.image.mode == "RGBA"
    assert res.image.size == (64, 64)
    alphas = list(res.image.getchannel("A").getdata())
    assert min(alphas) == 0 and max(alphas) == 255
    assert res.info["work_width"] == 16


def test_brightness_saturation_affect_result():
    normal = process_pixel_art(sample_image(), {"width": 40, "height": 40, "colors": 8, "dither": "none"}).image
    bright = process_pixel_art(sample_image(), {"width": 40, "height": 40, "colors": 8, "dither": "none", "brightness": 1.5}).image
    assert np.asarray(bright, dtype=float).mean() > np.asarray(normal, dtype=float).mean()


def test_png_bytes():
    res = process_pixel_art(sample_image(), {"width": 32, "height": 32})
    buf = io.BytesIO()
    res.image.save(buf, format="PNG")
    with Image.open(io.BytesIO(buf.getvalue())) as im:
        assert im.size == (32, 32)
