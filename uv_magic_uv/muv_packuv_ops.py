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

import bpy
import bmesh
import mathutils
from bpy.props import FloatProperty, BoolProperty
from mathutils import Vector
from math import fabs
from collections import defaultdict
from . import muv_common
import time

__author__ = "Nutti <nutti.metro@gmail.com>"
__status__ = "production"
__version__ = "4.0"
__date__ = "XX XXX 2015"


# pack UV
class MUV_PackUV(bpy.types.Operator):
    bl_idname = "uv.muv_packuv"
    bl_label = "Pack UV"
    bl_description = "Pack UV (Same UV Islands are integrated)"
    bl_options = {'REGISTER', 'UNDO'}

    __face_to_verts = defaultdict(set)
    __vert_to_faces = defaultdict(set)

    rotate = BoolProperty(
        name="Rotate",
        description="Rotate option used by default pack UV function",
        default=False)

    margin = FloatProperty(
        name="Margin",
        description="Margin used by default pack UV function",
        min=0,
        max=1,
        default=0.001)
    
    def __init__(self):
        self.__face_to_verts = defaultdict(set)
        self.__vert_to_faces = defaultdict(set)

    def execute(self, context):
        start = time.time()
        begin = start

        obj = bpy.context.active_object
        bm = bmesh.from_edit_mesh(obj.data)
        if muv_common.check_version(2, 73, 0) >= 0:
            bm.faces.ensure_lookup_table()
        if not bm.loops.layers.uv:
            self.report({'WARNING'}, "Object must have more than one UV map")
            return {'CANCELLED'}
        uv_layer = bm.loops.layers.uv.verify()

        selected_faces = [f for f in bm.faces if f.select]
                
        for f in selected_faces:
            for l in f.loops:
                id = l[uv_layer].uv.to_tuple(5), l.vert.index
                self.__face_to_verts[f.index].add(id)
                self.__vert_to_faces[id].add(f.index)

        end = time.time()
        elapsed_time = end - start
        print(("elapsed_time(make_db):{0}".format(elapsed_time)) + "[sec]")
        start = end

        uv_island_lists = self.__get_island(bm)

        end = time.time()
        elapsed_time = end - start
        print(("elapsed_time(__get_island):{0}".format(elapsed_time)) + "[sec]")
        start = end

        island_info = self.__get_island_info(uv_layer, uv_island_lists)

        end = time.time()
        elapsed_time = end - start
        print(("elapsed_time(__get_island_info):{0}".format(elapsed_time)) + "[sec]")
        start = end
        
        num_group = self.__group_island(island_info)
        
        end = time.time()
        elapsed_time = end - start
        print(("elapsed_time(__group_island):{0}".format(elapsed_time)) + "[sec]")
        start = end

        loop_lists = [l for f in bm.faces for l in f.loops]

        bpy.ops.mesh.select_all(action='DESELECT')

        # pack UV
        for gidx in range(num_group):
            group = list(filter(lambda i:i['group']==gidx, island_info))
            for f in group[0]['faces']:
                f['face'].select = True

        bmesh.update_edit_mesh(obj.data)

        bpy.ops.uv.select_all(action='SELECT')
        bpy.ops.uv.pack_islands(rotate=self.rotate, margin=self.margin)

        # copy/paste UV among same island
        for gidx in range(num_group):
            group = list(filter(lambda i:i['group']==gidx, island_info))
            if len(group) <= 1:
                continue
            for g in group[1:]:
                for (src_face, dest_face) in zip(group[0]['sorted'], g['sorted']):
                    for (src_loop, dest_loop) in zip(src_face['face'].loops, dest_face['face'].loops):
                        loop_lists[dest_loop.index][uv_layer].uv = loop_lists[src_loop.index][uv_layer].uv

        bpy.ops.uv.select_all(action='DESELECT')
        bpy.ops.mesh.select_all(action='DESELECT')

        for f in selected_faces:
            f.select = True

        bpy.ops.uv.select_all(action='SELECT')

        bmesh.update_edit_mesh(obj.data)

        end = time.time()
        elapsed_time = end - start
        print(("elapsed_time(copy):{0}".format(elapsed_time)) + "[sec]")

        elapsed_time = end - begin
        print(("elapsed_time(all):{0}".format(elapsed_time)) + "[sec]")

        return {'FINISHED'}

    def __sort_island_faces(self, kd, uvs, isl1, isl2):

        sorted_faces = []
        for f in isl1['sorted']:
            uv, idx, dist = kd.find(Vector((f['ave_uv'].x, f['ave_uv'].y, 0.0)))
            sorted_faces.append(isl2['faces'][uvs[idx]['face_idx']])
        return sorted_faces


    def __group_island(self, island_info):
        # check if there is same island
        num_group = 0
        while True:
            for isl in island_info:
                if isl['group'] == -1:
                    break
            else:
                break
            isl['group'] = num_group
            isl['sorted'] = isl['faces']
            
            for isl_2 in island_info:
                if isl_2['group'] == -1:
                    center_x_matched = (fabs(isl_2['center'].x - isl['center'].x) < 0.001)
                    center_y_matched = (fabs(isl_2['center'].y - isl['center'].y) < 0.001)
                    size_x_matched = (fabs(isl_2['size'].x - isl['size'].x) < 0.001)
                    size_y_matched = (fabs(isl_2['size'].y - isl['size'].y) < 0.001)
                    center_matched = center_x_matched and center_y_matched
                    size_matched = size_x_matched and size_y_matched
                    num_uv_matched = (isl_2['num_uv'] == isl['num_uv'])
                    if center_matched and size_matched and num_uv_matched:
                        isl_2['group'] = num_group
                        kd = mathutils.kdtree.KDTree(len(isl_2['faces']))
                        uvs = [{'uv': Vector((f['ave_uv'].x, f['ave_uv'].y, 0.0)), 'face_idx': fidx} for fidx, f in enumerate(isl_2['faces'])]
                        for i, uv in enumerate(uvs):
                            kd.insert(uv['uv'], i)
                        kd.balance()
                        # find two same UV pair for transfering UV
                        isl_2['sorted'] = self.__sort_island_faces(kd, uvs, isl, isl_2)
            num_group = num_group + 1
        return num_group


    def __get_island_info(self, uv_layer, islands):
        island_info = []

        # get information about each island
        for isl in islands:
            info = {}
            max = Vector((-10000000.0, -10000000.0))
            min = Vector((10000000.0, 10000000.0))
            ave = Vector((0.0, 0.0))
            num = 0
            for face in isl:
                n = 0
                a = Vector((0.0, 0.0))
                for l in face['face'].loops:
                    uv = l[uv_layer].uv
                    if uv.x > max.x:
                        max.x = uv.x
                    if uv.y > max.y:
                        max.y = uv.y
                    if uv.x < min.x:
                        min.x = uv.x
                    if uv.y < min.y:
                        min.y = uv.y
                    a = a + uv
                    n = n + 1
                ave = ave + a
                num = num + n
                a = a / n
                face['ave_uv'] = a
            ave = ave / num

            info['center'] = ave
            info['size'] = max - min
            info['num_uv'] = num
            info['group'] = -1
            info['faces'] = isl

            island_info.append(info)
        
        return island_info

    def __parse_island(self, bm, face_idx, faces_left, island):
        if face_idx in faces_left:
            faces_left.remove(face_idx)
            island.append({'face': bm.faces[face_idx]})
            for v in self.__face_to_verts[face_idx]:
                connected_faces = self.__vert_to_faces[v]
                if connected_faces:
                    for cf in connected_faces:
                        self.__parse_island(bm, cf, faces_left, island)

    def __get_island(self, bm):
        uv_island_lists = []
        faces_left = set(self.__face_to_verts.keys())
        while len(faces_left) > 0:
            current_island = []
            face_idx = list(faces_left)[0]
            self.__parse_island(bm, face_idx, faces_left, current_island)
            uv_island_lists.append(current_island)
        return uv_island_lists


