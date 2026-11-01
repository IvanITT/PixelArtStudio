from PIL import Image, ImageDraw

from app.services.tileset import (
    TERRAINS,
    extract_tiles,
    generate_terrain_tileset,
    make_seamless,
    recolor,
    tiles_to_sheet,
    variation,
)


def tile_fixture(size=16, cols=4, rows=3):
    img = Image.new("RGBA", (cols * size, rows * size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for r in range(rows):
        for c in range(cols):
            color = (60 + c * 40, 120 + r * 30, 90)
            d.rectangle([c * size, r * size, (c + 1) * size - 1, (r + 1) * size - 1], fill=color)
            d.rectangle([c * size + 2, r * size + 2, c * size + 8, r * size + 8], fill=(240, 240, 240))
    # duplicate of first tile
    img.paste(img.crop((0, 0, size, size)), (3 * size, 0))
    return img


def test_extract_tiles_and_duplicates():
    img = tile_fixture()
    tiles = extract_tiles(img, {"tile_size": 16})
    assert len(tiles) == 12
    assert sum(1 for t in tiles if t.duplicate_of is not None) == 1
    sheet, meta = tiles_to_sheet(tiles, columns=4, spacing=1, padding=1)
    assert meta["rows"] == 3
    assert meta["size"]["w"] == 2 + 4 * 16 + 3
    assert sheet.width == meta["size"]["w"]


def test_grid_offset_and_spacing():
    img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for y in range(0, 100, 20):
        for x in range(0, 100, 20):
            d.rectangle([x + 2, y + 2, x + 14, y + 14], fill=(100, 150, 200, 255))
    tiles = extract_tiles(img, {"tile_size": 16, "margin": 2, "spacing": 4, "detect_duplicates": False})
    # A 100px sheet with 2px margin, 16px tiles and 4px spacing fits exactly
    # 5x5 cells: 2 + 5*16 + 4*4 + 2 == 100.
    assert len(tiles) == 25
    assert tiles[0].source_x == 2 and tiles[0].source_y == 2
    assert tiles[1].source_x == 22
    assert tiles[5].source_y == 22


def test_terrain_autotile_metadata_and_preview():
    sheet, meta, preview = generate_terrain_tileset("grass", 16, seed=42, variations=2)
    assert sheet.size == (4 * 2 * 16, 4 * 16)
    assert len(meta["autotile"]["tiles"]) == 32
    assert meta["autotile"]["bits"] == {"north": 1, "east": 2, "south": 4, "west": 8}
    assert preview.width > 0 and preview.height > 0
    assert meta["seed"] == 42
    # Every terrain must render without errors.
    for terrain in TERRAINS:
        s, m, p = generate_terrain_tileset(terrain, 8, seed=3)
        assert s.width == 32 and s.height == 32


def test_terrain_deterministic():
    a, _, _ = generate_terrain_tileset("stone", 16, 99)
    b, _, _ = generate_terrain_tileset("stone", 16, 99)
    assert a.tobytes() == b.tobytes()


def test_recolor_and_variant():
    img = tile_fixture()
    tiles = extract_tiles(img, {"tile_size": 16})
    src = tiles[0].image
    out = recolor(src, 60, 1.2, 0.9)
    assert out.size == src.size
    flip = variation(src, "flip_h", 1)
    assert flip.size == src.size
    assert flip.tobytes() != src.tobytes()


def test_seamless_reduces_edge_error():
    img = Image.new("RGBA", (64, 64))
    d = ImageDraw.Draw(img)
    for y in range(64):
        for x in range(64):
            img.putpixel((x, y), ((x * 4) % 256, (y * 4) % 256, (x * y) % 256, 255))
    out, before, after = make_seamless(img, 0.2)
    assert out.size == img.size
    assert after <= before + 0.001
