import io
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from app.config import safe_join
from app.db import init_db
from app.services.images import ImageValidationError, decode_image
from app.services.projectio import import_project_zip


def test_safe_join_rejects_traversal(tmp_path):
    with pytest.raises(ValueError):
        safe_join(tmp_path, "..", "secret.txt")
    with pytest.raises(ValueError):
        safe_join(tmp_path, "a/b")
    assert safe_join(tmp_path, "ok.png").parent == tmp_path.resolve()


def test_decode_rejects_non_image():
    with pytest.raises(ImageValidationError):
        decode_image(b"this is not an image")


def test_decode_rejects_unsupported_format():
    buf = io.BytesIO()
    Image.new("RGB", (8, 8)).save(buf, format="TIFF")
    with pytest.raises(ImageValidationError):
        decode_image(buf.getvalue())


def test_zip_slip_rejected(tmp_path):
    init_db()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../evil.txt", "bad")
        zf.writestr("project.json", "{}")
    with pytest.raises(ValueError):
        import_project_zip(buf.getvalue())


def test_zip_requires_manifest():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("assets/a.png", b"data")
    with pytest.raises(ValueError):
        import_project_zip(buf.getvalue())
