# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2019 - Johannes Hartung <j.hartung@gmx.net>             *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU Lesser General Public License (LGPL)    *
# *   as published by the Free Software Foundation; either version 2 of     *
# *   the License, or (at your option) any later version.                   *
# *   for detail see the LICENCE text file.                                 *
# *                                                                         *
# *   This program is distributed in the hope that it will be useful,       *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU Library General Public License for more details.                  *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with this program; if not, write to the Free Software   *
# *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
# *   USA                                                                   *
# *                                                                         *
# ***************************************************************************

__title__ = "FreeCAD YAML and JSON mesh reader and writer"
__author__ = "Johannes Hartung"
__url__ = "http://www.freecadweb.org"

## @package importYAMLJSONMesh
#  \ingroup FEM
#  \brief FreeCAD YAML and JSON Mesh reader and writer for FEM workbench

import json
import os

import FreeCAD

has_yaml = True
try:
    import yaml
except ImportError:
    FreeCAD.Console.PrintMessage("No YAML available (import yaml failure), " +
                                 "yaml import/export won't work\n")
    has_yaml = False


from . import importToolsFem


# ********* generic FreeCAD import and export methods *********
if open.__module__ == '__builtin__':
    # because we'll redefine open below (Python2)
    pyopen = open
elif open.__module__ == 'io':
    # because we'll redefine open below (Python3)
    pyopen = open


def open(filename):
    "called when freecad opens a file"
    docname = os.path.splitext(os.path.basename(filename))[0]
    insert(filename, docname)


def insert(filename, docname):
    "called when freecad wants to import a file"
    try:
        doc = FreeCAD.getDocument(docname)
    except NameError:
        doc = FreeCAD.newDocument(docname)
    FreeCAD.ActiveDocument = doc
    import_yaml_json_mesh(filename)


def convert_femmesh_to_dict(femmesh):
    """
    Converts FemMesh into dictionary structure which can immediately used
    from importToolsFem.make_femmesh(mesh_data) to create a valid FEM mesh.
    """
    mesh_data = {}

    seg2 = []
    seg3 = []

    tri3 = []
    tri6 = []
    quad4 = []
    quad8 = []

    tet4 = []
    tet10 = []
    hex8 = []
    hex20 = []
    pent6 = []
    pent15 = []

    # associations for lens of tuples to different
    # edge, face, and volume elements

    len_to_edge = {2: seg2, 3: seg3}
    len_to_face = {3: tri3, 6: tri6, 4: quad4, 8: quad8}
    len_to_volume = {4: tet4,
                     10: tet10,
                     8: hex8,
                     20: hex20,
                     6: pent6,
                     15: pent15}

    # analyze edges

    for e in femmesh.Edges:
        t = femmesh.getElementNodes(e)
        len_to_edge[len(t)].append((e, t))

    # analyze faces

    for f in femmesh.Faces:
        t = femmesh.getElementNodes(f)
        len_to_face[len(t)].append((f, t))

    # analyze volumes

    for v in femmesh.Volumes:
        t = femmesh.getElementNodes(v)
        len_to_volume[len(t)].append((v, t))

    mesh_data = {
        'Nodes': dict([(k, (v.x, v.y, v.z))
                       for (k, v) in femmesh.Nodes.items()]),
        'Seg2Elem': dict(seg2),
        'Seg3Elem': dict(seg3),

        'Tria3Elem': dict(tri3),
        'Tria6Elem': dict(tri6),
        'Quad4Elem': dict(quad4),
        'Quad8Elem': dict(quad8),

        'Tetra4Elem': dict(tet4),
        'Tetra10Elem': dict(tet10),
        'Hexa8Elem': dict(hex8),
        'Hexa20Elem': dict(hex20),
        'Penta6Elem': dict(pent6),
        'Penta15Elem': dict(pent15),

        'Groups': dict([(group_num,
                         (femmesh.getGroupName(group_num),
                          femmesh.getGroupElements(group_num))
                         ) for group_num in femmesh.Groups])
    }
    # no pyr5, pyr13?
    # no groups?
    return mesh_data


def convert_raw_data_to_mesh_data(raw_mesh_data):
    """
    Converts raw dictionary data from JSON or YAML file to proper dict
    for importToolsFem.make_femmesh(mesh_data). This is necessary since
    JSON and YAML save dict keys as strings while make_femmesh expects
    integers.
    """
    mesh_data = {}
    for (type_key, type_dict) in raw_mesh_data.items():
        if type_key.lower() != "groups":
            mesh_data[type_key] = dict([(int(k), v)
                                        for (k, v) in type_dict.items()])
    return mesh_data


def export(objectslist, fileString):
    "called when freecad exports a file"
    if len(objectslist) != 1:
        FreeCAD.Console.PrintError("This exporter can only export one object.\n")
        return
    obj = objectslist[0]
    if not obj.isDerivedFrom("Fem::FemMeshObject"):
        FreeCAD.Console.PrintError("No FEM mesh object selected.\n")
        return

    mesh_data = convert_femmesh_to_dict(obj.FemMesh)

    if fileString != "":
        fileName, fileExtension = os.path.splitext(fileString)
        if fileExtension.lower() == ".json":
            fp = pyopen(fileString, "wt")
            json.dump(mesh_data, fp, indent=4)
            fp.close()
        elif (fileExtension.lower() == ".yaml" or fileExtension.lower() == ".yml") and has_yaml:
            fp = pyopen(fileString, "wt")
            yaml.safe_dump(mesh_data, fp)
            fp.close()


# ********* module specific methods *********
def import_yaml_json_mesh(fileString, analysis=None):
    """
    insert a FreeCAD FEM Mesh object in the ActiveDocument
    """

    filePath, fileName = os.path.split(fileString)
    fileNameNoExt, fileExtension = os.path.splitext(fileName)

    raw_mesh_data = {}
    if fileExtension.lower() == ".json":
        fp = pyopen(fileString, "rt")
        raw_mesh_data = json.load(fp)
        fp.close()
    elif (fileExtension.lower() == ".yaml" or fileExtension.lower() == ".yml") and has_yaml:
        fp = pyopen(fileString, "rt")
        raw_mesh_data = yaml.load(fp)
        fp.close()
    else:
        FreeCAD.Console.PrintError("Unknown extension, please select other importer.\n")

    FreeCAD.Console.PrintMessage("Converting indices to integer numbers ...")
    mesh_data = convert_raw_data_to_mesh_data(raw_mesh_data)
    FreeCAD.Console.PrintMessage("OK\n")

    mesh_name = fileNameNoExt
    femmesh = importToolsFem.make_femmesh(mesh_data)
    if femmesh:
        mesh_object = FreeCAD.ActiveDocument.addObject('Fem::FemMeshObject',
                                                       mesh_name)
        mesh_object.FemMesh = femmesh
