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
from mathutils import Vector

from ...utils import MetarigError
from ...utils import new_bone, copy_bone
from ...utils import make_deformer_name, make_mechanism_name, strip_org
from ...utils import create_bone_widget, create_widget, create_cube_widget
from ...utils import connected_children_names, has_connected_children
from ...utils import align_bone_z_axis

from . import pantin_utils


class Rig:
    def __init__(self, obj, bone_name, params):
        self.obj = obj
        self.params = params

        eb = self.obj.data.edit_bones

        self.org_bone = bone_name
        if eb[bone_name].parent is not None:
            self.org_parent = eb[bone_name].parent.name
        else:
            self.org_parent = None
        if eb[bone_name].use_connect:
            raise MetarigError(
                "RIGIFY ERROR: Bone %s should not be connected. "
                "Check bone chain for multiple pantin.simple rigs" % (
                    strip_org(self.org_parent)))

    def generate(self):
        if self.params.use_parent_Z_index and self.org_parent is not None:
            # Get parent's Z indices
            bpy.ops.object.mode_set(mode='OBJECT')
            pb = self.obj.pose.bones
            def_parent_name = make_deformer_name(strip_org(self.org_parent))
            if (self.params.object_side != ".C" and
                    def_parent_name[-2:] not in ['.L', '.R']):
                def_parent_name += self.params.object_side
            # print("DEF PARENT", def_parent_name)
            if not def_parent_name in pb:
                raise MetarigError(
                    "RIGIFY ERROR: Bone %s does not have a %s side" % (
                        strip_org(self.org_parent), self.params.object_side))
            parent_p = pb[def_parent_name]
            member_Z_index = parent_p['member_index']
            bone_Z_index = 0
            for b in pb:
                if b.bone.use_deform and b.name.startswith('DEF-'):
                    if (b['member_index'] == member_Z_index
                            and b['bone_index'] > bone_Z_index):
                        bone_Z_index = b['bone_index']
            bone_Z_index += 1

            bpy.ops.object.mode_set(mode='EDIT')
        else:
            member_Z_index = self.params.member_Z_index
            bone_Z_index = self.params.first_bone_Z_index

        eb = self.obj.data.edit_bones

        # Get parent's layers
        if self.params.use_parent_layers and self.org_parent is not None:
            layers = list(eb[self.org_parent].layers)
        else:
            layers = self.params.layers

        ctrl_chain = []
        # mch_chain = []

        # Control bones
        # Left
        left_ctrl = copy_bone(self.obj, self.org_bone, strip_org(self.params.eye_name) + '.L')
        left_ctrl_e = eb[left_ctrl]
        left_ctrl_e.use_connect = False
        left_ctrl_e.tail = (left_ctrl_e.tail
                             + Vector((0, 0, 1)) * left_ctrl_e.length)
        left_ctrl_e.head = eb[self.org_bone].tail
        align_bone_z_axis(self.obj, left_ctrl, Vector((0, 1, 0)))
        ctrl_chain.append(left_ctrl)

        # Right
        right_ctrl = copy_bone(self.obj, self.org_bone, strip_org(self.params.eye_name) + '.R')
        right_ctrl_e = eb[right_ctrl]
        right_ctrl_e.use_connect = False
        right_ctrl_e.tail = (right_ctrl_e.head
                            + Vector((0, 0, 1)) * right_ctrl_e.length)
        align_bone_z_axis(self.obj, right_ctrl, Vector((0, 1, 0)))
        ctrl_chain.append(right_ctrl)

        # Main
        main_ctrl = copy_bone(self.obj, self.org_bone, strip_org(self.org_bone))
        main_ctrl_e = eb[main_ctrl]
        main_ctrl_e.head = (main_ctrl_e.head + main_ctrl_e.tail) / 2
        if self.org_parent is not None:
            main_ctrl_e.parent = eb[self.org_parent]
        ctrl_chain.append(main_ctrl)


        for ctrl_bone in ctrl_chain:
            eb[ctrl_bone].layers = layers

        # Mechanism bones
        inter = copy_bone(
            self.obj, self.org_bone, make_mechanism_name(
                strip_org(self.org_bone)+'.intermediate'))
        eb[inter].parent = eb[main_ctrl]
        eb[left_ctrl].parent = eb[inter]
        eb[right_ctrl].parent = eb[inter]
        
        # # Def bones
        for i, b in enumerate([left_ctrl, right_ctrl]):
            def_bone = pantin_utils.create_deformation(
                self.obj, b,
                self.params.flip_switch,
                member_Z_index,
                bone_Z_index + i,
                0.0,
                b)

        bpy.ops.object.mode_set(mode='OBJECT')
        pb = self.obj.pose.bones

        # Widgets
        pantin_utils.create_capsule_widget(
            self.obj, main_ctrl, width=pb[self.org_bone].length, height=pb[self.org_bone].length*0.7, align=False)
        for b in [left_ctrl, right_ctrl]:
            pantin_utils.create_aligned_circle_widget(
                self.obj, b, radius=pb[b].length / 5)
        # for ctrl_bone in ctrl_chain:
        #     global_scale = pb[ctrl_bone].length  # self.obj.dimensions[2]
        #     # member_factor = 0.06
        #     widget_size = global_scale * 0.5  # * member_factor
        #     pantin_utils.create_aligned_circle_widget(
        #         self.obj, ctrl_bone, radius=widget_size)

        # Constraints
        # for org, ctrl in zip(self.org_bones, mch_chain):
        con = pb[self.org_bone].constraints.new('COPY_TRANSFORMS')
        con.name = "copy_transforms"
        con.target = self.obj
        con.subtarget = inter

        # # Pelvis follow
        # if self.params.do_flip:
        #     pantin_utils.create_ik_child_of(
        #         self.obj, ctrl_bone, self.params.pelvis_name)


def add_parameters(params):
    params.use_parent_Z_index = bpy.props.BoolProperty(
        name="Use parent's Z Index",
        default=True,
        description="The object will use its parent's Z index")
    params.member_Z_index = bpy.props.FloatProperty(
        name="Z index",
        default=0.0,
        description="Defines member's Z order")
    params.first_bone_Z_index = bpy.props.FloatProperty(
        name="First Bone Z index",
        default=0.0,
        description="Defines bone's Z order")
    params.flip_switch = bpy.props.BoolProperty(
        name="Flip Switch",
        default=False,
        description="This member may change depth when flipped")
    params.do_flip = bpy.props.BoolProperty(
        name="Do Flip",
        default=True,
        description="True if the rig has a torso with flip system")
    params.pelvis_name = bpy.props.StringProperty(
        name="Pelvis Name",
        default="Pelvis",
        description="Name of the pelvis bone in whole rig")
    params.eye_name = bpy.props.StringProperty(
        name="Eye Name",
        default="Eye",
        description="Name of the eye bone")
    params.use_parent_layers = bpy.props.BoolProperty(
        name="Use parent's layers",
        default=True,
        description="The object will use its parent's layers")
    params.layers = bpy.props.BoolVectorProperty(
        size=32,
        description="Layers for the object")


def parameters_ui(layout, params):
    """ Create the ui for the rig parameters.
    """
    r = layout.row()
    r.prop(params, "use_parent_Z_index")

    if not params.use_parent_Z_index:
        r = layout.row()
        r.prop(params, "member_Z_index")
        r.prop(params, "first_bone_Z_index")
    r = layout.row()
    r.prop(params, "flip_switch")
    r = layout.row()
    r.prop(params, "eye_name")
    col = layout.column(align=True)
    c = layout.column()
    c.prop(params, "do_flip")
    c.prop(params, "pelvis_name")

    # Layers
    col = layout.column(align=True)
    col.prop(params, "use_parent_layers")
    if not params.use_parent_layers:
        col = layout.column(align=True)
        col.label("Layers:")
        r = col.row()
        col = r.column(align=True)
        row = col.row(align=True)
        row.prop(params, "layers", index=0, toggle=True, text="")
        row.prop(params, "layers", index=1, toggle=True, text="")
        row.prop(params, "layers", index=2, toggle=True, text="")
        row.prop(params, "layers", index=3, toggle=True, text="")
        row.prop(params, "layers", index=4, toggle=True, text="")
        row.prop(params, "layers", index=5, toggle=True, text="")
        row.prop(params, "layers", index=6, toggle=True, text="")
        row.prop(params, "layers", index=7, toggle=True, text="")
        row = col.row(align=True)
        row.prop(params, "layers", index=16, toggle=True, text="")
        row.prop(params, "layers", index=17, toggle=True, text="")
        row.prop(params, "layers", index=18, toggle=True, text="")
        row.prop(params, "layers", index=19, toggle=True, text="")
        row.prop(params, "layers", index=20, toggle=True, text="")
        row.prop(params, "layers", index=21, toggle=True, text="")
        row.prop(params, "layers", index=22, toggle=True, text="")
        row.prop(params, "layers", index=23, toggle=True, text="")

        col = r.column(align=True)
        row = col.row(align=True)
        row.prop(params, "layers", index=8, toggle=True, text="")
        row.prop(params, "layers", index=9, toggle=True, text="")
        row.prop(params, "layers", index=10, toggle=True, text="")
        row.prop(params, "layers", index=11, toggle=True, text="")
        row.prop(params, "layers", index=12, toggle=True, text="")
        row.prop(params, "layers", index=13, toggle=True, text="")
        row.prop(params, "layers", index=14, toggle=True, text="")
        row.prop(params, "layers", index=15, toggle=True, text="")
        row = col.row(align=True)
        row.prop(params, "layers", index=24, toggle=True, text="")
        row.prop(params, "layers", index=25, toggle=True, text="")
        row.prop(params, "layers", index=26, toggle=True, text="")
        row.prop(params, "layers", index=27, toggle=True, text="")
        row.prop(params, "layers", index=28, toggle=True, text="")
        row.prop(params, "layers", index=29, toggle=True, text="")
        row.prop(params, "layers", index=30, toggle=True, text="")
        row.prop(params, "layers", index=31, toggle=True, text="")


def create_sample(obj):
    # generated by rigify.utils.write_metarig
    bpy.ops.object.mode_set(mode='EDIT')
    arm = obj.data

    bones = {}

    bone = arm.edit_bones.new('Eyes')
    bone.head[:] = -0.0045, -0.0000, 1.5476
    bone.tail[:] = 0.0964, -0.0000, 1.5476
    bone.roll = 1.5708
    bone.use_connect = False
    bones['Eyes'] = bone.name

    bpy.ops.object.mode_set(mode='OBJECT')
    pbone = obj.pose.bones[bones['Eyes']]
    pbone.rigify_type = 'pantin.eyes'
    pbone.lock_location = (False, False, True)
    pbone.lock_rotation = (True, True, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'XZY'
    try:
        pbone.rigify_parameters.eye_name = "Oeil"
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.pelvis_name = "Bassin"
    except AttributeError:
        pass

    bpy.ops.object.mode_set(mode='EDIT')
    for bone in arm.edit_bones:
        bone.select = False
        bone.select_head = False
        bone.select_tail = False
    for b in bones:
        bone = arm.edit_bones[bones[b]]
        bone.select = True
        bone.select_head = True
        bone.select_tail = True
        arm.edit_bones.active = bone
