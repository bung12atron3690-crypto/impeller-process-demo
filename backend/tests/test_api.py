import subprocess

import pytest
import trimesh
from fastapi.testclient import TestClient
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

from app import main
from test_geometry import write_step

client = TestClient(main.app)


def test_health():
    assert client.get("/api/health").json()["status"] == "ok"


@pytest.mark.parametrize("filename", ["box.stl", "BOX.STL"])
def test_stl_upload_roundtrip(filename):
    response = client.post("/api/analyze", params={"filename": filename, "unit": "mm"}, content=trimesh.creation.box([10, 20, 30]).export(file_type="stl"))
    assert response.status_code == 200, response.text
    assert response.json()["volume_mm3"] == pytest.approx(6000)
    assert response.json()["filename"] == filename


def test_step_upload_roundtrip(tmp_path):
    path = write_step(tmp_path / "sample.stp", BRepPrimAPI_MakeBox(10, 20, 30).Shape())
    response = client.post("/api/analyze", params={"filename": path.name}, content=path.read_bytes())
    assert response.status_code == 200, response.text
    assert response.json()["topology"]["faces"] == 6


@pytest.mark.parametrize("filename,data,status", [("x.obj", b"text", 415), ("x.stl", b"", 422), ("x.stl", b"not a model", 422), ("x.step", b"not a model", 422)])
def test_bad_uploads(filename, data, status):
    response = client.post("/api/analyze", params={"filename": filename}, content=data)
    assert response.status_code == status
    assert isinstance(response.json()["detail"], str)


def test_upload_limit_applies_to_stream_without_content_length(monkeypatch):
    monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 4)
    response = client.post("/api/analyze?filename=x.stl", content=iter([b"123", b"456"]))
    assert response.status_code == 413


def test_invalid_unit():
    assert client.post("/api/analyze?filename=x.stl&unit=feet", content=b"123").status_code == 422


def test_timeout_is_handled_and_slot_is_released(monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("worker", 45)
    monkeypatch.setattr(main.subprocess, "run", timeout)
    response = client.post("/api/analyze?filename=x.step", content=b"data")
    assert response.status_code == 422
    assert "45" in response.json()["detail"]
    assert main.WORKER_SLOTS.acquire(blocking=False)
    assert main.WORKER_SLOTS.acquire(blocking=False)
    main.WORKER_SLOTS.release()
    main.WORKER_SLOTS.release()


def test_capacity_rejects_extra_work():
    main.WORKER_SLOTS.acquire()
    main.WORKER_SLOTS.acquire()
    try:
        assert client.post("/api/analyze?filename=x.stl", content=b"123").status_code == 503
    finally:
        main.WORKER_SLOTS.release()
        main.WORKER_SLOTS.release()
