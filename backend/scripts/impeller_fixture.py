"""Synthetic, straight radial-blade fixtures. Not production impeller CAD."""
import math
from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf


def make_impeller(blades=6, cap=False, omit_last=False):
    shape = BRepPrimAPI_MakeCylinder(60, 6).Shape()
    shape = BRepAlgoAPI_Fuse(shape, BRepPrimAPI_MakeCylinder(15, 30).Shape()).Shape()
    for i in range(blades - int(omit_last)):
        blade = BRepPrimAPI_MakeBox(gp_Pnt(12, -1.5, 5), 45, 3, 25).Shape()
        transform = gp_Trsf()
        transform.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), i * 2 * math.pi / blades)
        shape = BRepAlgoAPI_Fuse(shape, BRepBuilderAPI_Transform(blade, transform, True).Shape()).Shape()
    if cap:
        top = BRepPrimAPI_MakeCylinder(60, 2).Shape()
        transform = gp_Trsf()
        from OCP.gp import gp_Vec
        transform.SetTranslation(gp_Vec(0, 0, 28))
        shape = BRepAlgoAPI_Fuse(shape, BRepBuilderAPI_Transform(top, transform, True).Shape()).Shape()
    return shape
