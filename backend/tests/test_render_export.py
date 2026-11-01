import numpy as np
from PIL import Image, ImageDraw

from app.services.animation import (
    TEMPLATES,
    export_gif,
    export_webp,
    frame_metadata,
    pack_frames,
    template_frames,
)
from app.services.exporter import build_zip
from app.services.pseudo3d import TEMPLATES as P3D_TEMPLATES
from app.services.pseudo3d import heightmap, studio


def sprite_fixture():
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([20, 10, 44, 30], fill=(220, 80, 80, 255))
    d.rectangle([22, 30, 42, 58], fill=(80, 120, 220, 255))
    d.rectangle([24, 12, 30, 18], fill=(250, 240, 200, 255))
    return img


def test_templates_all_render_frames():
    src = sprite_fixture()
    for name, cfg in TEMPLATES.items():
        frames = template_frames(src, name, 4)
        assert len(frames) == 4
        assert all(f.mode == "RGBA" and f.size == frames[0].size for f in frames)
        assert any(np.asarray(f.getchannel("A")).max() > 0 for f in frames)


def test_gif_and_webp_exports():
    frames = template_frames(sprite_fixture(), "walk", 4)
    gif = export_gif(frames, 8)
    assert gif[:6] in {b"GIF87a", b"GIF89a"}
    webp = export_webp(frames, 8)
    assert webp[:4] == b"RIFF" and webp[8:12] == b"WEBP"
    with Image.open(__import__("io").BytesIO(gif)) as im:
        assert im.n_frames == 4
    with Image.open(__import__("io").BytesIO(webp)) as im:
        assert im.n_frames == 4


def test_pack_frames_and_metadata():
    frames = template_frames(sprite_fixture(), "idle", 6)
    sheet, meta = pack_frames(frames, columns=3, spacing=2)
    assert sheet.size[0] > 0
    assert len(meta["frames"]) == 6
    assert meta["columns"] == 3
    md = frame_metadata(frames, [f"f{i}" for i in range(6)], 8, True)
    assert md["frame_count"] == 6 and md["fps"] == 8


def test_pseudo3d_templates_and_heightmap():
    src = sprite_fixture().resize((128, 128))
    for name in P3D_TEMPLATES:
        out, info = studio(src, {"template": name})
        assert out.mode == "RGBA"
        assert out.width >= 128
        assert info["projection"] in {"isometric", "orthographic", "topdown", "side"}
        assert "disclaimer" in info
    hm = heightmap(src, 1.5)
    assert hm.mode == "RGBA" and hm.size == src.size


def test_false3d_deterministic():
    src = sprite_fixture()
    a, _ = studio(src, {"template": "iso_object", "angle": 45, "extrude": 0.3})
    b, _ = studio(src, {"template": "iso_object", "angle": 45, "extrude": 0.3})
    assert a.tobytes() == b.tobytes()


def test_zip_export_presets(tmp_path):
    img = sprite_fixture()
    assets = [{
        "id": "abc", "name": "hero walk", "kind": "spritesheet", "tags": ["hero"],
        "meta": {"fps": 8, "sheet": {"frames": {"hero_0": {"frame": {"x": 0, "y": 0, "w": 64, "h": 64}}}, "size": {"w": 64, "h": 64}}},
        "created_at": "2026-01-01",
    }]
    for preset in ("generic", "godot", "unity", "rpgmaker"):
        data, info = build_zip("Demo Project", assets, {"abc": img}, preset, "png")
        assert data[:2] == b"PK"
        assert info["count"] == 1
        import io, zipfile
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
            assert any(n.endswith(".png") for n in names)
            assert any(n.endswith("manifest.json") for n in names)
    data, _ = build_zip("Demo", assets, {"abc": img}, "generic", "jpeg")
    import io, zipfile
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        pngs = [n for n in zf.namelist() if n.endswith(".jpg")]
        assert pngs
