from pathlib import Path

import numpy as np
import pytest
import trimesh
from OCP.BRep import BRep_Builder
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.IFSelect import IFSelect_RetDone
from OCP.Interface import Interface_Static
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer
from OCP.TopoDS import TopoDS_Compound
from OCP.gp import gp_Pln, gp_Pnt, gp_Dir

from app.geometry import GeometryError, analyze_step, analyze_stl


def write_step(path: Path, shape, unit="MM"):
    # This writer fixture preserves numeric coordinates and declares the chosen
    # unit (verified in CARTESIAN_POINT / CONVERSION_BASED_UNIT records).
    writer = STEPControl_Writer()
    Interface_Static.SetCVal_s("write.step.unit", unit)
    assert writer.Transfer(shape, STEPControl_AsIs) == IFSelect_RetDone
    assert writer.Write(str(path)) == IFSelect_RetDone
    Interface_Static.SetCVal_s("write.step.unit", "MM")
    return path


@pytest.mark.parametrize("encoding", ["stl", "stl_ascii"])
def test_stl_box_measurements_and_translation(tmp_path, encoding):
    mesh = trimesh.creation.box([10, 20, 30])
    mesh.apply_translation([101, -42, 19])
    path = tmp_path / "box.stl"
    mesh.export(path, file_type=encoding)
    result = analyze_stl(path, "mm")
    assert result.dimensions_mm == pytest.approx([10, 20, 30])
    assert result.surface_area_mm2 == pytest.approx(2200)
    assert result.volume_mm3 == pytest.approx(6000)
    assert result.center_of_mass_mm == pytest.approx([101, -42, 19])
    assert result.topology["triangles"] == 12
    assert result.preview.triangle_count == 12


@pytest.mark.parametrize("unit,scale", [("cm", 10), ("m", 1000), ("inch", 25.4)])
def test_stl_units_scale_length_area_and_volume(tmp_path, unit, scale):
    path = tmp_path / "cube.stl"
    trimesh.creation.box([1, 1, 1]).export(path)
    result = analyze_stl(path, unit)
    assert result.dimensions_mm == pytest.approx([scale] * 3)
    assert result.surface_area_mm2 == pytest.approx(6 * scale**2)
    assert result.volume_mm3 == pytest.approx(scale**3)


@pytest.mark.parametrize("defect", ["open", "inverted", "multiple"])
def test_stl_unsafe_volume_is_unavailable(tmp_path, defect):
    mesh = trimesh.creation.box([10, 20, 30])
    if defect == "open":
        mesh.update_faces(np.arange(len(mesh.faces) - 1))
    elif defect == "inverted":
        mesh.invert()
    else:
        other = mesh.copy()
        other.apply_translation([40, 0, 0])
        mesh = trimesh.util.concatenate([mesh, other])
    path = tmp_path / "invalid-volume.stl"
    mesh.export(path)
    result = analyze_stl(path, "mm")
    assert result.volume_mm3 is None
    assert result.center_of_mass_mm is None
    assert result.surface_area_mm2 > 0


def test_duplicate_triangles_rejected(tmp_path):
    mesh = trimesh.creation.box()
    mesh = trimesh.Trimesh(mesh.vertices, np.vstack([mesh.faces, mesh.faces[0]]), process=False)
    path = tmp_path / "duplicate.stl"
    mesh.export(path)
    with pytest.raises(GeometryError, match="重复"):
        analyze_stl(path, "mm")


@pytest.mark.parametrize("unit, scale", [("MM", 1), ("INCH", 25.4)])
def test_step_units_topology_and_exact_measurement(tmp_path, unit, scale):
    path = write_step(tmp_path / "box.step", BRepPrimAPI_MakeBox(gp_Pnt(100, -40, 10), 10, 20, 30).Shape(), unit)
    result = analyze_step(path)
    assert result.dimensions_mm == pytest.approx(np.array([10, 20, 30]) * scale)
    assert result.volume_mm3 == pytest.approx(6000 * scale**3)
    assert result.surface_area_mm2 == pytest.approx(2200 * scale**2)
    assert result.center_of_mass_mm == pytest.approx(np.array([105, -30, 25]) * scale)
    assert result.topology == {"faces": 6, "edges": 12, "vertices": 8, "solids": 1}
    assert result.surface_types == {"Plane": 6}
    assert result.preview is not None


def test_step_cylinder_analytic_properties(tmp_path):
    path = write_step(tmp_path / "cylinder.step", BRepPrimAPI_MakeCylinder(5, 20).Shape())
    result = analyze_step(path)
    assert result.volume_mm3 == pytest.approx(np.pi * 25 * 20)
    assert result.surface_area_mm2 == pytest.approx(2 * np.pi * 5 * 20 + 2 * np.pi * 25)
    assert result.surface_types == {"Plane": 2, "Cylinder": 1}
    assert result.preview is not None


def test_step_surface_has_no_solid_volume(tmp_path):
    plane = gp_Pln(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1))
    path = write_step(tmp_path / "surface.step", BRepBuilderAPI_MakeFace(plane, 0, 10, 0, 20).Shape())
    result = analyze_step(path)
    assert result.surface_area_mm2 == pytest.approx(200)
    assert result.volume_mm3 is None
    assert result.center_of_mass_mm is None


def test_step_assembly_does_not_sum_overlapping_solids(tmp_path):
    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    for x in (0, 5):
        builder.Add(compound, BRepPrimAPI_MakeBox(gp_Pnt(x, 0, 0), 10, 20, 30).Shape())
    path = write_step(tmp_path / "assembly.step", compound)
    result = analyze_step(path)
    assert result.topology["solids"] == 2
    assert result.volume_mm3 is None
    assert result.center_of_mass_mm is None
