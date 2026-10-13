"""Real geometry measurements, normalized to millimeters; no manufacturing inference."""
from pathlib import Path

import numpy as np
import trimesh

from .schemas import Analysis, Preview

MAX_TRIANGLES = 200_000
MAX_PREVIEW_TRIANGLES = 100_000


class GeometryError(ValueError):
    pass


def mesh_preview(mesh: trimesh.Trimesh, note: str) -> Preview | None:
    if len(mesh.faces) > MAX_PREVIEW_TRIANGLES:
        return None
    # Float64 coordinates are preserved until the client recenters the model.
    return Preview(
        positions=mesh.vertices.reshape(-1).tolist(),
        indices=mesh.faces.reshape(-1).tolist(),
        triangle_count=len(mesh.faces),
        note=note,
    )


def analyze_stl(path: Path, unit: str) -> Analysis:
    mesh = trimesh.load_mesh(path, file_type="stl", process=False)
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
        raise GeometryError("STL 中未找到三角网格。")
    if len(mesh.faces) > MAX_TRIANGLES:
        raise GeometryError("网格超过 200,000 个三角面，请降低精度后重试。")
    if not np.isfinite(mesh.vertices).all():
        raise GeometryError("模型包含无效坐标。")
    mesh.apply_scale({"mm": 1.0, "cm": 10.0, "m": 1000.0, "inch": 25.4}[unit])
    mesh.merge_vertices()
    if not mesh.nondegenerate_faces().all():
        raise GeometryError("网格包含退化三角面，请修复模型后重试。")
    if not mesh.unique_faces().all():
        raise GeometryError("网格包含重复三角面，请修复模型后重试。")
    # is_volume also checks orientation: never silently abs() negative volume.
    components = trimesh.graph.connected_components(mesh.face_adjacency, nodes=np.arange(len(mesh.faces)), min_len=1)
    usable_volume = len(components) == 1 and bool(mesh.is_volume)
    warnings = ["STL 不携带可靠单位；尺寸由所选单位换算。曲面面积与体积为三角网格近似值。",
                "尚未检查自交；封闭与法向检查通过不代表已完成制造级几何验证。"]
    if not usable_volume:
        warnings.append("网格未满足单一封闭、法向一致且正向的体积条件，体积与实体重心不可用。")
    preview = mesh_preview(mesh, "原始 STL 三角网格，显示坐标已居中；测量保留原始坐标系。")
    if preview is None:
        warnings.append("三角面超过 100,000，已跳过交互预览；几何统计仍使用完整网格。")
    return Analysis(
        format="STL", method="trimesh · 三角网格测量",
        unit_source=f"用户指定 {unit} → mm",
        dimensions_mm=mesh.extents.tolist(), bounds_mm=mesh.bounds.tolist(),
        surface_area_mm2=float(mesh.area),
        volume_mm3=float(mesh.volume) if usable_volume else None,
        center_of_mass_mm=mesh.center_mass.tolist() if usable_volume else None,
        topology={"triangles": len(mesh.faces), "mesh_vertices": len(mesh.vertices)},
        surface_types={},
        checks={"watertight": bool(mesh.is_watertight), "winding_consistent": bool(mesh.is_winding_consistent),
                "components": len(components), "volume_available": usable_volume},
        warnings=warnings, preview=preview,
    )


def analyze_step(path: Path) -> Analysis:
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepGProp import BRepGProp
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.Bnd import Bnd_Box
    from OCP.GProp import GProp_GProps
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_REVERSED, TopAbs_SOLID, TopAbs_VERTEX
    from OCP.TopExp import TopExp
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopTools import TopTools_IndexedMapOfShape
    from OCP.TopoDS import TopoDS

    reader = STEPControl_Reader()
    if reader.ReadFile(str(path)) != IFSelect_RetDone:
        raise GeometryError("STEP 文件无法读取，请检查文件内容是否完整。")
    # STEP reader converts declared file units to a millimeter target system.
    reader.SetSystemLengthUnit(1.0)
    if reader.TransferRoots() == 0:
        raise GeometryError("STEP 文件没有可转换的几何体。")
    shape = reader.OneShape()
    if shape.IsNull():
        raise GeometryError("STEP 文件不包含有效几何体。")

    def mapped(kind):
        mapping = TopTools_IndexedMapOfShape()
        TopExp.MapShapes_s(shape, kind, mapping)
        return [mapping.FindKey(i) for i in range(1, mapping.Extent() + 1)]

    faces, edges, vertices, solids = [mapped(kind) for kind in (TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX, TopAbs_SOLID)]
    if not faces:
        raise GeometryError("STEP 文件只有点或曲线，没有可分析的曲面。")
    if len(faces) > 10_000:
        raise GeometryError("STEP 超过 10,000 个曲面，请简化模型后重试。")
    valid = bool(BRepCheck_Analyzer(shape).IsValid())
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    bounds = np.array(box.Get()).reshape(2, 3)
    area = GProp_GProps()
    BRepGProp.SurfaceProperties_s(shape, area)
    mass = GProp_GProps()
    # Avoid summing overlapping assembly solids or mixing solids and loose faces.
    single_solid = False
    if len(solids) == 1:
        solid_faces = TopTools_IndexedMapOfShape()
        TopExp.MapShapes_s(solids[0], TopAbs_FACE, solid_faces)
        single_solid = solid_faces.Extent() == len(faces)
    if valid and single_solid:
        BRepGProp.VolumeProperties_s(solids[0], mass, True)
    volume_available = valid and single_solid and mass.Mass() > 0
    surface_types: dict[str, int] = {}
    for face in faces:
        kind = BRepAdaptor_Surface(TopoDS.Face_s(face)).GetType().name.replace("GeomAbs_", "")
        surface_types[kind] = surface_types.get(kind, 0) + 1
    warnings = ["STEP 面、边、顶点为 B-rep 拓扑计数；三维预览为曲面离散近似，不参与面积与体积计算。"]
    if not valid:
        warnings.append("B-rep 有效性检查未通过；面积和尺寸仅供诊断，体积与重心不可用。")
    if not volume_available:
        warnings.append("仅对单一有效实体提供体积与重心；曲面模型、混合模型或多实体装配暂不计算。")
    preview = None
    try:
        deflection = max(float(np.max(bounds[1] - bounds[0])) * 0.001, 0.01)
        mesher = BRepMesh_IncrementalMesh(shape, deflection, False, 0.35, False)
        if not mesher.IsDone():
            raise GeometryError("曲面离散失败")
        positions, triangles = [], []
        for original_face in faces:
            face = TopoDS.Face_s(original_face)
            location = TopLoc_Location()
            triangulation = BRep_Tool.Triangulation_s(face, location)
            if triangulation is None:
                raise GeometryError("曲面缺少三角网格")
            if len(triangles) + triangulation.NbTriangles() > MAX_PREVIEW_TRIANGLES:
                raise GeometryError("预览超过 100,000 个三角面")
            offset = len(positions)
            transform = location.Transformation()
            for i in range(1, triangulation.NbNodes() + 1):
                point = triangulation.Node(i).Transformed(transform)
                positions.append([point.X(), point.Y(), point.Z()])
            for i in range(1, triangulation.NbTriangles() + 1):
                indices = [n - 1 + offset for n in triangulation.Triangle(i).Get()]
                if face.Orientation() == TopAbs_REVERSED:
                    indices.reverse()
                triangles.append(indices)
        mesh = trimesh.Trimesh(vertices=positions, faces=triangles, process=False)
        preview = mesh_preview(mesh, f"STEP 曲面离散预览，弦高容差 {deflection:.4g} mm；测量来自 B-rep。")
    except Exception:
        warnings.append("当前模型无法生成限额内的预览，已保留几何统计。")
    center = mass.CentreOfMass()
    return Analysis(
        format="STEP", method="OpenCascade · B-rep 几何积分",
        unit_source="STEP 声明单位由 OpenCascade 转换为 mm",
        dimensions_mm=(bounds[1] - bounds[0]).tolist(), bounds_mm=bounds.tolist(),
        surface_area_mm2=area.Mass(), volume_mm3=mass.Mass() if volume_available else None,
        center_of_mass_mm=[center.X(), center.Y(), center.Z()] if volume_available else None,
        topology={"faces": len(faces), "edges": len(edges), "vertices": len(vertices), "solids": len(solids)},
        surface_types=surface_types,
        checks={"brep_valid": valid, "volume_available": volume_available},
        warnings=warnings, preview=preview,
    )
