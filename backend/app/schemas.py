from typing import Literal

from pydantic import BaseModel


class Preview(BaseModel):
    positions: list[float]
    indices: list[int]
    triangle_count: int
    note: str


class Analysis(BaseModel):
    filename: str = ""
    format: Literal["STL", "STEP"]
    method: str
    unit: Literal["mm"] = "mm"
    unit_source: str
    dimensions_mm: list[float]
    bounds_mm: list[list[float]]
    surface_area_mm2: float
    volume_mm3: float | None
    center_of_mass_mm: list[float] | None
    topology: dict[str, int]
    surface_types: dict[str, int]
    checks: dict[str, bool | int | str]
    warnings: list[str]
    preview: Preview | None
    analysis_id: str | None = None
    source_sha256: str | None = None
    impeller: dict | None = None
    classification: str = "通用几何分析"
