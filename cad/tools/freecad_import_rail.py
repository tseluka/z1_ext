# FreeCAD macro: build the Z1 7th-axis rail from cad/whole12 as separate, placed parts.
#
# GUI : Macro > Macros... > "User macros location" -> pick this folder, select
#       freecad_import_rail.py, Execute.  (Or: Macro > Macros... > Execute after browsing here.)
# CLI : freecadcmd cad/tools/freecad_import_rail.py      -> writes cad/whole12_rail.FCStd
#
# Result (units: mm, same frame as 00_full_assembly.stl, z = 0 = top of the base board):
#   RailBase (App::Part)  fixed parts
#   Carriage (App::Part)  moving parts -- change Carriage > Placement > Position > x
#                         (-520 .. 520 mm) to slide it along the rail.
# Parts are meshes.  Set MAKE_SOLIDS = True to also get Part solids (slower; needed for
# STEP export, booleans, or picking faces/edges).
import json, os
import FreeCAD as App
import Mesh

MAKE_SOLIDS = False
CARRIAGE_X_MM = 0.0          # initial carriage position along the rail
TRAVEL_MM = 520.0            # runners reach the hard stops at +-520 mm

def _repo_cad_dir():
    try:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../cad
    except NameError:
        pass
    if App.GuiUp:
        from PySide import QtGui
        d = QtGui.QFileDialog.getExistingDirectory(None, "Select the z1_ext/cad folder")
        if d:
            return d
    raise RuntimeError("Can't find the cad/ folder; run this file from z1_ext/cad/tools")

CAD = _repo_cad_dir()
PARTS = os.path.join(CAD, "whole12")
PLACEMENTS = json.load(open(os.path.join(CAD, "whole12_placements.json")))

# Same split as cad/tools/gen_rail_xacro.py
MOVING = {"04_runner", "05_carriage_plate", "06_steel_plate", "09_pinion_disc", "10_pinion_pin"}
def is_moving(name, t):
    return name in MOVING or (name == "13_chain_block" and t[2] == 24.0)

COLOR = {"01_base_board": (0.55, 0.42, 0.28), "06_steel_plate": (0.45, 0.47, 0.50),
         "07_rack": (0.35, 0.36, 0.38), "09_pinion_disc": (0.35, 0.36, 0.38),
         "10_pinion_pin": (0.35, 0.36, 0.38), "13_chain_block": (0.10, 0.10, 0.10),
         "14_hard_stop": (0.80, 0.15, 0.10)}
DEFAULT_COLOR = (0.75, 0.76, 0.78)

def _set_color(obj, rgb):
    if not App.GuiUp:
        return
    vo = obj.ViewObject
    for prop in ("ShapeColor",):           # Mesh and Part view providers both have it
        if hasattr(vo, prop):
            setattr(vo, prop, rgb)

doc = App.newDocument("Z1_7th_axis")
base = doc.addObject("App::Part", "RailBase")
carriage = doc.addObject("App::Part", "Carriage")
carriage.Placement.Base = App.Vector(CARRIAGE_X_MM, 0, 0)

meshes = {}
count = 0
for fname, insts in sorted(PLACEMENTS.items()):
    name = fname[:-4]
    if name not in meshes:
        meshes[name] = Mesh.Mesh(os.path.join(PARTS, fname))
    for k, inst in enumerate(insts):
        t = inst["t_mm"]
        R = inst["R"]
        assert R == [[1, 0, 0], [0, 1, 0], [0, 0, 1]], f"{fname}: unexpected rotation"
        label = f"{name}_{k}"
        obj = doc.addObject("Mesh::Feature", label)
        obj.Mesh = meshes[name]
        obj.Placement = App.Placement(App.Vector(*t), App.Rotation())
        _set_color(obj, COLOR.get(name, DEFAULT_COLOR))
        (carriage if is_moving(name, t) else base).addObject(obj)
        if MAKE_SOLIDS:
            import Part
            shape = Part.Shape()
            shape.makeShapeFromMesh(meshes[name].Topology, 0.01)
            solid = Part.makeSolid(Part.Shell(shape.Faces)).removeSplitter()
            sobj = doc.addObject("Part::Feature", label + "_solid")
            sobj.Shape = solid
            sobj.Placement = obj.Placement
            _set_color(sobj, COLOR.get(name, DEFAULT_COLOR))
            (carriage if is_moving(name, t) else base).addObject(sobj)
            if App.GuiUp:
                obj.ViewObject.Visibility = False
        count += 1

doc.recompute()
App.Console.PrintMessage(f"Z1 7th axis: {count} parts placed "
                         f"(carriage travel: -{TRAVEL_MM:g} .. {TRAVEL_MM:g} mm along x)\n")

if App.GuiUp:
    import FreeCADGui as Gui
    Gui.activeDocument().activeView().viewIsometric()
    Gui.SendMsgToActiveView("ViewFit")
else:
    out = os.path.join(CAD, "whole12_rail.FCStd")
    doc.saveAs(out)
    App.Console.PrintMessage(f"saved {out}\n")
