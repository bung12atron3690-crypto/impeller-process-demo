"""Generate small reference parts with known dimensions; run from backend/."""
from pathlib import Path

import numpy as np
import trimesh
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer

folder = Path(__file__).resolve().parents[2] / "models" / "samples"
folder.mkdir(parents=True, exist_ok=True)
box = trimesh.creation.box([10, 20, 30])
box.apply_translation([5, 10, 15])
box.export(folder / "box-10x20x30-mm.stl")
box.update_faces(np.arange(len(box.faces) - 1))
box.export(folder / "open-box-mm.stl")
for name, shape in [
    ("box-10x20x30-mm.step", BRepPrimAPI_MakeBox(10, 20, 30).Shape()),
    ("cylinder-r5-h20-mm.step", BRepPrimAPI_MakeCylinder(5, 20).Shape()),
]:
    writer = STEPControl_Writer()
    writer.Transfer(shape, STEPControl_AsIs)
    writer.Write(str(folder / name))
print(f"Samples created: {folder}")


# These synthetic radial-blade examples validate the heuristic, not manufacturing.
from impeller_fixture import make_impeller
for count in (6, 7):
    writer = STEPControl_Writer()
    writer.Transfer(make_impeller(count), STEPControl_AsIs)
    writer.Write(str(folder / f"synthetic-impeller-{count}-mm.step"))
