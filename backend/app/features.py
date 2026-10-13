"""Conservative radial-section heuristic, not a semantic CAD classifier."""
from collections import Counter

import numpy as np
import trimesh

from .schemas import Analysis

SAMPLES = 720
HEIGHTS = (0.35, 0.55, 0.75)
RADII = (0.50, 0.65, 0.80)


def inside_segments(points: np.ndarray, segments: np.ndarray) -> np.ndarray:
    """Even/odd crossings for closed planar section contours, including holes."""
    inside = np.zeros(len(points), dtype=bool)
    x, y = points.T
    for a, b in segments:
        if abs(b[1] - a[1]) < 1e-12:
            continue
        crossing = ((a[1] > y) != (b[1] > y)) & (x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0])
        inside ^= crossing
    return inside


def ring_measure(mask: np.ndarray, radius: float) -> dict:
    starts = np.flatnonzero(mask & ~np.roll(mask, 1))
    ends = np.flatnonzero(~mask & np.roll(mask, 1))
    count = len(starts)
    if count < 1:
        return {"count": 0, "pitch_cv": 1.0, "occupancy": float(mask.mean()), "material_arc_mm": None, "gap_arc_mm": None}
    lengths = [int(np.min((ends - start) % SAMPLES)) for start in starts]
    gaps = [int(np.min((starts - end) % SAMPLES)) for end in ends]
    pitches = np.diff(np.r_[starts, starts[0] + SAMPLES])
    return {"count": count, "pitch_cv": float(pitches.std() / pitches.mean()),
            "occupancy": float(mask.mean()), "material_arc_mm": float(min(lengths) * 2 * np.pi * radius / SAMPLES),
            "gap_arc_mm": float(min(gaps) * 2 * np.pi * radius / SAMPLES)}


def recognize(analysis: Analysis, axis: str = "Z") -> dict:
    result = {"status": "unresolved", "axis": axis, "method": "radial-section-v1",
              "blade_count": None, "outer_diameter_mm": None, "axial_height_mm": None,
              "sampled_material_arc_min_mm": None, "sampled_gap_arc_min_mm": None,
              "evidence_ratio": 0.0, "rings": [], "reasons": [],
              "limitations": ["仅适用于轴线平行所选坐标轴、轴心接近横向包围盒中心的开式周期叶片模型。",
                              "圆环材料弧长不是叶片法向厚度，空隙弧长不是全局最小流道宽度；不得直接用于刀具约束。",
                              "证据一致率是截面投票比例，不是分类正确概率；尚未用真实叶轮验证。",
                              "未识别入口/轮毂直径、叶片曲率、根部圆角、真实最小壁厚或刀具可达性。"]}
    if not analysis.checks.get("volume_available") or analysis.preview is None:
        result["reasons"] = ["需要单一有效体积模型及可用离散网格；保留通用几何结果。"]
        return result
    axial = "XYZ".index(axis)
    transverse = [i for i in range(3) if i != axial]
    mesh = trimesh.Trimesh(vertices=np.array(analysis.preview.positions).reshape(-1, 3),
                           faces=np.array(analysis.preview.indices).reshape(-1, 3), process=False)
    bounds = np.array(analysis.bounds_mm)
    center = bounds.mean(axis=0)
    extent = bounds[1] - bounds[0]
    if min(extent[transverse]) / max(extent[transverse]) < 0.9:
        result["reasons"] = ["横向尺寸不满足近圆形包络条件，请检查轴向或保持通用模式。"]
        return result
    radius = float(np.linalg.norm(mesh.vertices[:, transverse] - center[transverse], axis=1).max())
    height = float(extent[axial])
    if radius <= 0 or not 0.08 <= height / (2 * radius) <= 1.2:
        result["reasons"] = ["轴向高径比超出当前识别范围。"]
        return result
    normal = np.eye(3)[axial]
    angles = (np.arange(SAMPLES) + 0.37) * 2 * np.pi / SAMPLES
    circle = np.column_stack([np.cos(angles), np.sin(angles)])

    def section(fraction):
        origin = center.copy()
        origin[axial] = bounds[0, axial] + height * fraction
        lines = trimesh.intersections.mesh_plane(mesh, normal, origin)
        return lines[:, :, transverse] - center[transverse] if len(lines) else np.empty((0, 2, 2))

    # One end must behave like a backing disk; the opposite end must be open.
    ends = [section(f) for f in (0.05, 0.95)]
    end_fill = [float(np.mean([inside_segments(circle * radius * r, lines).mean() for r in RADII])) for lines in ends]
    result["end_occupancy"] = end_fill
    if not (max(end_fill) > 0.95 and min(end_fill) < 0.50):
        result["reasons"] = ["未同时发现单侧连续底盘和另一侧开放特征；不启用叶轮工艺。"]
        return result
    rings = []
    for h in HEIGHTS:
        lines = section(h)
        for r in RADII:
            ring = ring_measure(inside_segments(circle * radius * r, lines), radius * r)
            rings.append({**ring, "height_fraction": h, "radius_mm": radius * r})
    accepted = [r for r in rings if 4 <= r["count"] <= 24 and r["pitch_cv"] <= 0.12 and 0.02 <= r["occupancy"] <= 0.45]
    result["rings"] = rings
    if not accepted:
        result["reasons"] = ["采样圆环未检测到稳定的 4–24 个周期薄片。"]
        return result
    count, votes = Counter(r["count"] for r in accepted).most_common(1)[0]
    agreed = [r for r in accepted if r["count"] == count]
    result["evidence_ratio"] = votes / len(rings)
    if votes < 6 or len({r["height_fraction"] for r in agreed}) < 2 or len({r["radius_mm"] for r in agreed}) < 3:
        result["reasons"] = ["不同高度/半径的计数不一致，可能存在分流叶片、局部特征或轴心偏差。"]
        return result
    result.update(status="candidate", blade_count=int(count), outer_diameter_mm=2 * radius, axial_height_mm=height,
                  sampled_material_arc_min_mm=min(r["material_arc_mm"] for r in agreed),
                  sampled_gap_arc_min_mm=min(r["gap_arc_mm"] for r in agreed),
                  reasons=[f"{votes}/9 个采样圆环支持 {count} 个近等距材料区间，且具有单侧底盘与开放端。",
                           "该几何模式也可能出现在散热件等零件中，需要人工确认零件族。"])
    return result
