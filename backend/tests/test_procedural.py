import numpy as np

from app.services.procedural import GENERATORS, catalog, generate_asset, generate_variations


def test_catalog_complete():
    items = catalog()
    assert len(items) == len(GENERATORS) == 31
    groups = {i["group"] for i in items}
    assert groups == {"nature", "fantasy", "environment", "scifi"}
    for item in items:
        assert item["params"]
        names = [p["name"] for p in item["params"]]
        assert "size" in names and "seed" not in names


def test_every_generator_renders():
    for gid in GENERATORS:
        img, info = generate_asset(gid, {"size": 32}, seed=123)
        assert img.mode == "RGBA"
        assert img.size == (32, 32)
        alpha = np.asarray(img.getchannel("A"))
        assert alpha.max() > 0, f"{gid} rendered fully transparent"
        assert info["generator"] == gid
        # visible pixel ratio should be meaningful for an asset
        assert (alpha > 0).mean() > 0.015, f"{gid} is nearly empty"


def test_determinism_and_seed_variation():
    a, _ = generate_asset("tree", {"size": 48, "canopy": "round", "branches": 6}, 777)
    b, _ = generate_asset("tree", {"size": 48, "canopy": "round", "branches": 6}, 777)
    c, _ = generate_asset("tree", {"size": 48, "canopy": "round", "branches": 6}, 778)
    assert a.tobytes() == b.tobytes()
    assert a.tobytes() != c.tobytes()


def test_palette_restriction():
    palette = ["#000000", "#ffffff", "#ff0000", "#00ff00", "#0000ff"]
    img, info = generate_asset("robot", {"size": 48, "palette": "gameboy"}, 5)
    used = {f"#{r:02x}{g:02x}{b:02x}" for r, g, b, a in img.getdata() if a > 0}
    assert used <= {"#0f380f", "#306230", "#8bac0f", "#9bbc0f"}
    assert info["palette_id"] == "gameboy"


def test_params_are_clamped():
    img, info = generate_asset("flower", {"size": 9999, "petals": 999}, 1)
    assert img.size == (128, 128)
    assert info["params"]["petals"] <= 10


def test_variation_counts():
    items = generate_variations("rock", {"size": 24}, 10, 5)
    assert len(items) == 5
    assert len({i[1]["seed"] for i in items}) == 5


def test_groups_cover_all():
    counts = {}
    for gid, spec in GENERATORS.items():
        counts[spec["group"]] = counts.get(spec["group"], 0) + 1
    assert counts["nature"] >= 8
    assert counts["fantasy"] >= 7
    assert counts["environment"] >= 7
    assert counts["scifi"] >= 5
