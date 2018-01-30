# <pep8-80 compliant>

# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

__author__ = "Nutti <nutti.metro@gmail.com>"
__status__ = "production"
__version__ = "4.5"
__date__ = "19 Nov 2017"


from collections import defaultdict
from pprint import pprint
from math import fabs, sqrt

import bpy
from mathutils import Vector
import bmesh


DEBUG = False


def debug_print(*s):
    """
    Print message to console in debugging mode
    """

    if DEBUG:
        pprint(s)


def check_version(major, minor, _):
    """
    Check blender version
    """

    if bpy.app.version[0] == major and bpy.app.version[1] == minor:
        return 0
    if bpy.app.version[0] > major:
        return 1
    if bpy.app.version[1] > minor:
        return 1
    return -1


def redraw_all_areas():
    """
    Redraw all areas
    """

    for area in bpy.context.screen.areas:
        area.tag_redraw()


def get_space(area_type, region_type, space_type):
    """
    Get current area/region/space
    """

    area = None
    region = None
    space = None

    for area in bpy.context.screen.areas:
        if area.type == area_type:
            break
    else:
        return (None, None, None)
    for region in area.regions:
        if region.type == region_type:
            break
    for space in area.spaces:
        if space.type == space_type:
            break

    return (area, region, space)


def __get_island_info(uv_layer, islands):
    """
    get information about each island
    """

    island_info = []
    for isl in islands:
        info = {}
        max_uv = Vector((-10000000.0, -10000000.0))
        min_uv = Vector((10000000.0, 10000000.0))
        ave_uv = Vector((0.0, 0.0))
        num_uv = 0
        for face in isl:
            n = 0
            a = Vector((0.0, 0.0))
            for l in face['face'].loops:
                uv = l[uv_layer].uv
                if uv.x > max_uv.x:
                    max_uv.x = uv.x
                if uv.y > max_uv.y:
                    max_uv.y = uv.y
                if uv.x < min_uv.x:
                    min_uv.x = uv.x
                if uv.y < min_uv.y:
                    min_uv.y = uv.y
                a = a + uv
                n = n + 1
            ave_uv = ave_uv + a
            num_uv = num_uv + n
            a = a / n
            face['ave_uv'] = a
        ave_uv = ave_uv / num_uv

        info['center'] = ave_uv
        info['size'] = max_uv - min_uv
        info['num_uv'] = num_uv
        info['group'] = -1
        info['faces'] = isl
        info['max'] = max_uv
        info['min'] = min_uv

        island_info.append(info)

    return island_info


def __parse_island(bm, face_idx, faces_left, island,
                   face_to_verts, vert_to_faces):
    """
    Parse island
    """

    if face_idx in faces_left:
        faces_left.remove(face_idx)
        island.append({'face': bm.faces[face_idx]})
        for v in face_to_verts[face_idx]:
            connected_faces = vert_to_faces[v]
            if connected_faces:
                for cf in connected_faces:
                    __parse_island(bm, cf, faces_left, island, face_to_verts,
                                   vert_to_faces)


def __get_island(bm, face_to_verts, vert_to_faces):
    """
    Get island list
    """

    uv_island_lists = []
    faces_left = set(face_to_verts.keys())
    while faces_left:
        current_island = []
        face_idx = list(faces_left)[0]
        __parse_island(bm, face_idx, faces_left, current_island,
                       face_to_verts, vert_to_faces)
        uv_island_lists.append(current_island)

    return uv_island_lists


def __create_vert_face_db(faces, uv_layer):
    # create mesh database for all faces
    face_to_verts = defaultdict(set)
    vert_to_faces = defaultdict(set)
    for f in faces:
        for l in f.loops:
            id_ = l[uv_layer].uv.to_tuple(5), l.vert.index
            face_to_verts[f.index].add(id_)
            vert_to_faces[id_].add(f.index)

    return (face_to_verts, vert_to_faces)


def get_island_info(obj, only_selected=True):
    bm = bmesh.from_edit_mesh(obj.data)
    if check_version(2, 73, 0) >= 0:
        bm.faces.ensure_lookup_table()

    return get_island_info_from_bmesh(bm, only_selected)


def get_island_info_from_bmesh(bm, only_selected=True):
    if not bm.loops.layers.uv:
        return None
    uv_layer = bm.loops.layers.uv.verify()

    # create database
    if only_selected:
        selected_faces = [f for f in bm.faces if f.select]
    else:
        selected_faces = [f for f in bm.faces]
    ftv, vtf = __create_vert_face_db(selected_faces, uv_layer)

    # Get island information
    uv_island_lists = __get_island(bm, ftv, vtf)
    island_info = __get_island_info(uv_layer, uv_island_lists)

    return island_info


def get_uvimg_editor_board_size(area):
    if area.spaces.active.image:
        return area.spaces.active.image.size

    return (255.0, 255.0)


def calc_polygon_2d_area(points):
    area = 0.0
    for i, p1 in enumerate(points):
        p2 = points[(i + 1) % len(points)]
        v1 = p1 - points[0]
        v2 = p2 - points[0]
        a = v1.x * v2.y - v1.y * v2.x
        area = area + a

    return fabs(0.5 * area)


def calc_polygon_3d_area(points):
    area = 0.0
    for i, p1 in enumerate(points):
        p2 = points[(i + 1) % len(points)]
        v1 = p1 - points[0]
        v2 = p2 - points[0]
        cx = v1.y * v2.z - v1.z * v2.y
        cy = v1.z * v2.x - v1.x * v2.z
        cz = v1.x * v2.y - v1.y * v2.x
        a = sqrt(cx * cx + cy * cy + cz * cz)
        area = area + a

    return 0.5 * area


def measure_mesh_area(obj):
    bm = bmesh.from_edit_mesh(obj.data)
    if check_version(2, 73, 0) >= 0:
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

    sel_faces = [f for f in bm.faces if f.select]

    # measure
    mesh_area = 0.0
    for f in sel_faces:
        verts = [l.vert.co for l in f.loops]
        f_mesh_area = calc_polygon_3d_area(verts)
        mesh_area = mesh_area + f_mesh_area

    return mesh_area


def measure_uv_area(obj):
    bm = bmesh.from_edit_mesh(obj.data)
    if check_version(2, 73, 0) >= 0:
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

    if not bm.loops.layers.uv:
        return None
    uv_layer = bm.loops.layers.uv.verify()

    if not bm.faces.layers.tex:
        return None
    tex_layer = bm.faces.layers.tex.verify()

    sel_faces = [f for f in bm.faces if f.select]

    # measure
    uv_area = 0.0
    for f in sel_faces:
        uvs = [l[uv_layer].uv for l in f.loops]
        f_uv_area = calc_polygon_2d_area(uvs)
        if tex_layer:
            img = f[tex_layer].image
            if not img:
                return None
            uv_area = uv_area + f_uv_area * img.size[0] * img.size[1]

    return uv_area


def diff_point_to_segment(a, b, p):
    ab = b - a
    normal_ab = ab.normalized()

    ap = p - a
    dist_ax = normal_ab.dot(ap)

    # cross point
    x = a + normal_ab * dist_ax

    # difference between cross point and point
    xp = p - x

    return xp, x
