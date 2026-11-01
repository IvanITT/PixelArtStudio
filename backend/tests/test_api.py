import io
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def make_png(w=128, h=96, transparent=False):
    mode = "RGBA" if transparent else "RGB"
    bg = (0, 0, 0, 0) if transparent else (240, 240, 240)
    img = Image.new(mode, (w, h), bg)
    d = ImageDraw.Draw(img)
    d.ellipse([10, 10, 50, 50], fill=(200, 40, 60, 255) if transparent else (200, 40, 60))
    d.rectangle([60, 20, 110, 80], fill=(30, 120, 210, 255) if transparent else (30, 120, 210))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(scope="module")
def project(client):
    r = client.post("/api/projects", json={"name": "API Test", "description": "test", "category": "Testing"})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def source(client, project):
    r = client.post(
        f"/api/projects/{project['id']}/assets/upload",
        files={"file": ("sample.png", make_png(), "image/png")},
        data={"name": "Sample", "kind": "source"},
    )
    assert r.status_code == 200, r.text
    return r.json()


def wait_job(client, job_id, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/api/jobs/{job_id}")
        assert r.status_code == 200
        data = r.json()
        if data["status"] in {"done", "error", "cancelled"}:
            return data
        time.sleep(0.2)
    raise AssertionError("job timed out")


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["offline"] is True
    assert data["status"] == "ok"
    assert "OpenCV" in data["versions"]


def test_settings_roundtrip(client):
    r = client.patch("/api/settings", json={"worker_threads": 3})
    assert r.status_code == 200
    assert r.json()["worker_threads"] == 3
    client.patch("/api/settings", json={"worker_threads": 4})
    assert client.get("/api/settings").json()["worker_threads"] == 4


def test_project_crud(client):
    r = client.post("/api/projects", json={"name": "Temp"})
    pid = r.json()["id"]
    assert client.get(f"/api/projects/{pid}").status_code == 200
    r = client.patch(f"/api/projects/{pid}", json={"name": "Renamed", "favorite": True})
    assert r.json()["name"] == "Renamed"
    assert r.json()["favorite"] is True
    assert client.delete(f"/api/projects/{pid}").status_code == 400
    assert client.delete(f"/api/projects/{pid}?confirm=true").json()["deleted"] is True
    assert client.get(f"/api/projects/{pid}").status_code == 404


def test_upload_validation(client, project):
    r = client.post(
        f"/api/projects/{project['id']}/assets/upload",
        files={"file": ("bad.png", b"not an image", "image/png")},
    )
    assert r.status_code == 400


def test_pixelart_preview_and_export(client, project, source):
    payload = {
        "project_id": project["id"],
        "asset_id": source["id"],
        "options": {"width": 64, "height": 48, "colors": 8, "dither": "floyd", "quantizer": "median_cut"},
    }
    r = client.post("/api/pixelart/preview", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["url"].endswith(".png") or ".png?v=" in data["url"]
    assert data["info"]["colors_used"] <= 8
    r2 = client.post("/api/pixelart/preview", json=payload)
    assert r2.json()["cached"] is True
    r = client.post("/api/pixelart/export", json={**payload, "name": "Test pixel"})
    assert r.status_code == 200, r.text
    asset = r.json()["asset"]
    assert asset["width"] == 64
    assert asset["kind"] == "pixelart"
    # download formats
    r = client.get(f"/api/assets/{asset['id']}/download?format=bmp")
    assert r.status_code == 200
    assert r.content[:2] == b"BM"


def test_pixelart_background_job(client, project, source):
    payload = {
        "project_id": project["id"],
        "asset_id": source["id"],
        "options": {"width": 48, "height": 40, "colors": 6, "dither": "none", "quantizer": "median_cut"},
    }
    r = client.post("/api/pixelart/job", json=payload)
    assert r.status_code == 200, r.text
    job = wait_job(client, r.json()["job_id"])
    assert job["status"] == "done", job
    assert job["progress"] == 100
    assert job["result"]["url"]
    assert job["result"]["info"]["width"] == 48


def test_sprite_extraction_and_sheet(client, project):
    transparent = make_png(200, 80, transparent=True)
    r = client.post(
        f"/api/projects/{project['id']}/assets/upload",
        files={"file": ("sprites.png", transparent, "image/png")},
        data={"name": "Sprites"},
    )
    asset = r.json()
    r = client.post("/api/sprites/extract", json={
        "project_id": project["id"], "asset_id": asset["id"],
        "options": {"method": "bg_color", "tolerance": 30, "min_area": 10},
        "save": True,
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["count"] >= 1
    ids = [s["id"] for s in data["sprites"]]
    r = client.post("/api/sprites/pack", json={
        "project_id": project["id"], "sprite_ids": ids,
        "options": {"columns": min(2, len(ids)), "spacing": 2, "padding": 1},
        "name": "Test sheet",
    })
    assert r.status_code == 200, r.text
    sheet = r.json()
    assert sheet["asset"]["kind"] == "spritesheet"
    assert len(sheet["sheet"]["frames"]) == len(ids)


def test_tileset_terrain_and_export_package(client, project):
    r = client.post("/api/tileset/terrain", json={
        "project_id": project["id"], "terrain": "grass", "tile_size": 16, "seed": 7, "variations": 1,
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["asset"]["kind"] == "tileset"
    assert len(data["tiles"]) == 16
    r = client.post("/api/export/package", json={
        "project_id": project["id"], "asset_ids": [data["asset"]["id"]],
        "preset": "godot", "format": "png",
    })
    assert r.status_code == 200
    job = wait_job(client, r.json()["job_id"])
    assert job["status"] == "done", job
    assert job["result"]["download_url"].endswith(".zip")
    r = client.get(job["result"]["download_url"])
    assert r.status_code == 200
    assert r.content[:2] == b"PK"


def test_tileset_seamless(client, project, source):
    r = client.post("/api/tileset/seamless", json={
        "project_id": project["id"], "asset_id": source["id"], "save": True,
    })
    assert r.status_code == 200, r.text
    assert r.json()["asset"]["kind"] == "tile"


def test_procedural_generate(client, project):
    r = client.post("/api/procedural/generate", json={
        "project_id": project["id"], "generator": "tree",
        "params": {"size": 32, "canopy": "pine"}, "seed": 12, "count": 2, "save": True,
    })
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) == 2
    assert items[0]["asset"]["kind"] == "procedural"
    assert items[0]["asset"]["meta"]["seed"] == 12


def test_false3d(client, project, source):
    r = client.post("/api/false3d/preview", json={
        "project_id": project["id"], "asset_id": source["id"],
        "options": {"template": "iso_object", "extrude": 0.3}, "save": True,
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["asset"]["kind"] == "false3d"
    assert "disclaimer" in data["info"]


def test_animation_flow(client, project, source):
    r = client.post(f"/api/projects/{project['id']}/animations", json={
        "name": "Test walk", "fps": 10, "loop": True, "frames": [source["id"]],
    })
    assert r.status_code == 200, r.text
    anim = r.json()
    r = client.post(f"/api/animations/{anim['id']}/template", json={
        "asset_id": source["id"], "template": "walk", "frames": 4,
    })
    assert r.status_code == 200, r.text
    anim = r.json()
    assert anim["frame_count"] == 5
    r = client.post(f"/api/animations/{anim['id']}/export", json={"format": "sheet"})
    assert r.status_code == 200, r.text
    assert r.json()["asset"]["kind"] == "spritesheet"
    r = client.post(f"/api/animations/{anim['id']}/export", json={"format": "gif"})
    assert r.status_code == 200, r.text
    gif = r.json()["asset"]
    r = client.get(gif["url"])
    assert r.content[:3] == b"GIF"
    r = client.post(f"/api/animations/{anim['id']}/export", json={"format": "json"})
    assert r.status_code == 200
    # frame ops
    r = client.post(f"/api/animations/{anim['id']}/reorder", json={"from_index": 0, "to_index": 2})
    assert r.status_code == 200
    r = client.post(f"/api/animations/{anim['id']}/duplicate-frame", json={"from_index": 1, "to_index": 0})
    assert r.status_code == 200
    assert r.json()["frame_count"] == 6
    r = client.delete(f"/api/animations/{anim['id']}/frames/0")
    assert r.json()["frame_count"] == 5


def test_workspace_composite(client, project, source):
    r = client.post("/api/workspace/export", json={
        "project_id": project["id"], "width": 128, "height": 128,
        "layers": [{"asset_id": source["id"], "x": 10, "y": 12, "scale": 0.5, "rotation": 10, "opacity": 0.8}],
    })
    assert r.status_code == 200, r.text
    asset = r.json()["asset"]
    assert asset["kind"] == "workspace"
    assert asset["width"] == 128


def test_project_save_backup_export_import(client, project):
    r = client.post(f"/api/projects/{project['id']}/save", json={
        "note": "manual", "state": {"workspace": {"width": 256, "height": 256, "layers": []}},
    })
    assert r.status_code == 200, r.text
    assert r.json()["backup"] is not None
    backups = client.get(f"/api/projects/{project['id']}/backups").json()
    assert backups
    r = client.post(f"/api/projects/{project['id']}/backups/{backups[0]['id']}/restore")
    assert r.status_code == 200, r.text
    export = client.get(f"/api/projects/{project['id']}/export")
    assert export.status_code == 200
    data = export.content
    r = client.post("/api/projects/import", files={"file": ("project.zip", data, "application/zip")})
    assert r.status_code == 200, r.text
    imported = r.json()
    assert imported["id"] != project["id"]
    assert imported["asset_count"] > 0
    assert client.get(f"/api/projects/{imported['id']}/assets").status_code == 200
    # duplicate
    r = client.post(f"/api/projects/{project['id']}/duplicate")
    assert r.status_code == 200
    dup = r.json()
    assert dup["asset_count"] > 0
    assert dup["id"] != project["id"]


def test_library_filters(client, project):
    r = client.get(f"/api/projects/{project['id']}/assets?kind=procedural&favorite=false")
    assert r.status_code == 200
    assert all(a["kind"] == "procedural" for a in r.json())
    tags = client.get(f"/api/projects/{project['id']}/tags")
    assert tags.status_code == 200
    assert isinstance(tags.json(), list)
    r = client.get(f"/api/palettes?project_id={project['id']}")
    assert any(p["id"] == "gameboy" for p in r.json())
