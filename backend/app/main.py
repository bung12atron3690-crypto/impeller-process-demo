"""Geometry analysis API. Uploaded models exist only for the current request."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import BoundedSemaphore
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from .schemas import Analysis
from . import analysis_store
from .planning import PlanRequest, generate_plan

app = FastAPI(title="Impeller Process Demo API", version="0.3.0")
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
WORKER_TIMEOUT_SECONDS = 45
WORKER_SLOTS = BoundedSemaphore(2)
BACKEND_ROOT = Path(__file__).resolve().parent.parent


class HealthResponse(BaseModel):
    status: str
    service: str


@app.get("/api/health", response_model=HealthResponse, tags=["System"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="impeller-process-demo")


def run_analysis(path: Path, output: Path, unit: str, axis: str = "Z") -> Analysis:
    try:
        process = subprocess.run(
            [sys.executable, "-m", "app.worker", str(path), str(output), unit, axis],
            cwd=BACKEND_ROOT, timeout=WORKER_TIMEOUT_SECONDS,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(422, "模型解析超过 45 秒，请简化模型后重试。") from exc
    if process.returncode != 0 or not output.exists():
        raise HTTPException(422, "模型解析进程未完成，请检查文件或降低模型复杂度。")
    if output.stat().st_size > 32 * 1024 * 1024:
        raise HTTPException(422, "解析结果过大，请简化模型后重试。")
    payload = json.loads(output.read_text(encoding="utf-8"))
    if "error" in payload:
        raise HTTPException(422, payload["error"])
    return Analysis.model_validate(payload["result"])


@app.post("/api/analyze", response_model=Analysis, tags=["Geometry"],
          openapi_extra={"requestBody": {"required": True, "content": {
              "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
          }}})
async def analyze(
    request: Request,
    filename: str = Query(min_length=1, max_length=255),
    unit: Literal["mm", "cm", "m", "inch"] = "mm",
    axis: Literal["X", "Y", "Z"] = "Z",
) -> Analysis:
    """Send raw STL/STEP bytes. unit applies only to STL; STEP uses file units."""
    suffix = Path(filename).suffix.lower()
    if suffix not in {".stl", ".step", ".stp"}:
        raise HTTPException(415, "仅支持 STL、STEP、STP 文件。")
    if not WORKER_SLOTS.acquire(blocking=False):
        raise HTTPException(503, "分析任务已满，请稍后重试。")
    try:
        with TemporaryDirectory(prefix="impeller-") as directory:
            path = Path(directory) / f"model{suffix}"
            size = 0
            digest = hashlib.sha256()
            with path.open("wb") as target:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:
                        raise HTTPException(413, "文件不能超过 20 MiB。")
                    digest.update(chunk)
                    target.write(chunk)
            if size == 0:
                raise HTTPException(422, "文件为空，请选择有效模型。")
            result = await run_in_threadpool(run_analysis, path, Path(directory) / "result.json", unit, axis)
            result.filename = filename.replace("\\", "/").split("/")[-1]
            result.source_sha256 = digest.hexdigest()
            analysis_store.save(result)
            return result
    finally:
        WORKER_SLOTS.release()


@app.post("/api/process-plan", tags=["Planning"])
def process_plan(inputs: PlanRequest) -> dict:
    analysis = analysis_store.get(inputs.analysis_id)
    if analysis is None:
        raise HTTPException(404, "分析结果已过期或服务已重启，请重新上传模型。")
    try:
        return generate_plan(analysis, inputs)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
