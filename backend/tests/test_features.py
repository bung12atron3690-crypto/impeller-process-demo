from pathlib import Path
import sys

import numpy as np
import pytest
import trimesh
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeBox
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.gp import gp_Ax2, gp_Pnt, gp_Dir, gp_Ax1, gp_Trsf

from app.geometry import analyze_step, analyze_stl
from app.features import recognize
from test_geometry import write_step

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from impeller_fixture import make_impeller


@pytest.fixture(scope="module")
def candidate(tmp_path_factory):
    path = write_step(tmp_path_factory.mktemp("impeller") / "six.step", make_impeller(6))
    result = analyze_step(path)
    result.impeller = recognize(result)
    return result


def test_six_blades_and_evidence(candidate):
    result = candidate.impeller
    assert result["status"] == "candidate"
    assert result["blade_count"] == 6
    assert result["evidence_ratio"] == 1
    assert len(result["rings"]) == 9
    assert result["outer_diameter_mm"] == pytest.approx(120)
    assert result["sampled_material_arc_min_mm"] == pytest.approx(3, abs=0.45)


@pytest.mark.parametrize("blades", [4, 7, 9, 12])
def test_other_blade_counts(tmp_path, blades):
    path = write_step(tmp_path / f"{blades}.step", make_impeller(blades))
    result = recognize(analyze_step(path))
    assert result["status"] == "candidate"
    assert result["blade_count"] == blades


def test_translation_and_axis_selection(candidate):
    result = candidate.model_copy(deep=True)
    points = np.array(result.preview.positions).reshape(-1, 3)
    rotation = np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]])
    points = points @ rotation.T + [123, 35, -80]
    result.preview.positions = points.reshape(-1).tolist()
    result.bounds_mm = [points.min(axis=0).tolist(), points.max(axis=0).tolist()]
    assert recognize(result, "X")["blade_count"] == 6
    assert recognize(result, "Z")["status"] == "unresolved"


def test_positive_stl(candidate, tmp_path):
    mesh = trimesh.Trimesh(np.array(candidate.preview.positions).reshape(-1, 3), np.array(candidate.preview.indices).reshape(-1, 3), process=True)
    path = tmp_path / "six.stl"
    mesh.export(path)
    result = recognize(analyze_stl(path, "mm"))
    assert result["blade_count"] == 6


@pytest.mark.parametrize("kind", ["box", "cylinder", "flange", "closed_impeller"])
def test_non_impellers_and_closed_shroud_not_candidates(tmp_path, kind):
    if kind == "box":
        shape = BRepPrimAPI_MakeBox(120, 120, 30).Shape()
    elif kind == "closed_impeller":
        shape = make_impeller(6, cap=True)
    else:
        shape = BRepPrimAPI_MakeCylinder(60, 20).Shape()
        if kind == "flange":
            for angle in np.arange(6) * np.pi / 3:
                tool = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(40*np.cos(angle),40*np.sin(angle),-1),gp_Dir(0,0,1)),5,22).Shape()
                shape = BRepAlgoAPI_Cut(shape,tool).Shape()
    result = recognize(analyze_step(write_step(tmp_path / f"{kind}.step", shape)))
    assert result["status"] == "unresolved"
    assert result["blade_count"] is None


def test_missing_mesh_or_volume_does_not_infer(candidate):
    for updates in [{"preview": None}, {"checks": {"volume_available": False}}]:
        assert recognize(candidate.model_copy(update=updates))["status"] == "unresolved"


def test_gear_is_not_open_impeller(tmp_path):
    shape = BRepPrimAPI_MakeCylinder(40, 20).Shape()
    for angle in np.arange(12)*np.pi/6:
        tooth = BRepPrimAPI_MakeBox(gp_Pnt(35,-3,0),20,6,20).Shape()
        transform = gp_Trsf()
        transform.SetRotation(gp_Ax1(gp_Pnt(0,0,0),gp_Dir(0,0,1)),angle)
        shape = BRepAlgoAPI_Fuse(shape,BRepBuilderAPI_Transform(tooth,transform,True).Shape()).Shape()
    result=recognize(analyze_step(write_step(tmp_path/'gear.step',shape)))
    assert result['status'] == 'unresolved'


def test_missing_blade_breaks_periodic_evidence(tmp_path):
    shape=make_impeller(6,omit_last=True)
    result=recognize(analyze_step(write_step(tmp_path/'missing.step',shape)))
    assert result['status'] == 'unresolved'
