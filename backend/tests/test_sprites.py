from PIL import Image, ImageDraw

from app.services.sprites import extract_sprites, pack_spritesheet


def transparent_fixture():
    img = Image.new("RGBA", (300, 160), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    colors = [(200, 50, 50, 255), (50, 200, 90, 255), (60, 80, 220, 255)]
    for i in range(3):
        x = 20 + i * 90
        d.ellipse([x, 30, x + 50, 90], fill=colors[i])
        d.rectangle([x + 18, 70, x + 32, 120], fill=colors[i])
    return img


def test_alpha_extraction_count_and_crop():
    img = transparent_fixture()
    result = extract_sprites(img, {"method": "auto_alpha", "min_area": 50})
    assert len(result.sprites) == 3
    for s in result.sprites:
        assert s.image.mode == "RGBA"
        assert s.image.width > 10 and s.image.height > 10
        assert s.image.getchannel("A").getbbox() is not None
        assert s.area > 50


def test_background_color_extraction():
    img = Image.new("RGB", (200, 100), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.rectangle([20, 20, 60, 70], fill=(10, 10, 10))
    d.rectangle([120, 25, 160, 75], fill=(20, 80, 200))
    result = extract_sprites(img, {"method": "bg_color", "tolerance": 20, "min_area": 20})
    assert len(result.sprites) == 2
    assert result.background == (255, 255, 255)


def test_manual_rectangles_and_polygon():
    img = transparent_fixture()
    result = extract_sprites(img, {"method": "manual_rect", "rects": [[20, 30, 50, 90], [110, 30, 50, 90]]})
    assert len(result.sprites) == 2
    poly = extract_sprites(img, {"method": "manual_polygon", "polygons": [[[20, 20], [70, 20], [70, 100], [20, 100]]]})
    assert len(poly.sprites) == 1


def test_merge_gap_and_min_area_filters():
    img = transparent_fixture()
    one = extract_sprites(img, {"method": "auto_alpha", "merge_gap": 60, "min_area": 50})
    assert len(one.sprites) == 1
    none = extract_sprites(img, {"method": "auto_alpha", "min_area": 100000})
    assert len(none.sprites) == 0


def test_normalize_and_pack():
    img = transparent_fixture()
    result = extract_sprites(img, {"method": "auto_alpha", "normalize": True, "normalize_size": 64, "min_area": 50})
    assert all(s.image.size == (64, 64) for s in result.sprites)
    sheet, meta = pack_spritesheet([s.image for s in result.sprites], [s.name for s in result.sprites], {
        "columns": 2, "padding": 2, "spacing": 3,
    })
    assert sheet.mode == "RGBA"
    assert len(meta["frames"]) == 3
    assert meta["columns"] == 2
    assert meta["size"]["w"] == 2 * 2 + 2 * 64 + 3
    for frame in meta["frames"].values():
        x, y, w, h = frame["frame"]["x"], frame["frame"]["y"], frame["frame"]["w"], frame["frame"]["h"]
        assert x >= 0 and y >= 0 and x + w <= sheet.width and y + h <= sheet.height
