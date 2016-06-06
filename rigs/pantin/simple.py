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

from ...utils import MetarigError
from ...utils import copy_bone
from ...utils import make_deformer_name, strip_org
from ...utils import create_bone_widget, create_widget, create_cube_widget
from ...utils import connected_children_names, has_connected_children

from . import pantin_utils

class Rig:
    def __init__(self, obj, bone_name, params):
        self.obj = obj
        self.params = params

        self.org_bones = [bone_name] + connected_children_names(self.obj, bone_name)
        self.org_parent = self.obj.data.edit_bones[bone_name].parent.name

    def generate(self):
        if self.params.use_parent_Z_index:
            # Get parent's Z indices
            bpy.ops.object.mode_set(mode='OBJECT')
            pb = self.obj.pose.bones
            def_parent_name = make_deformer_name(strip_org(self.org_parent))
            if self.params.object_side != ".C":
                def_parent_name += self.params.object_side
            if not def_parent_name in pb:
                raise MetarigError("RIGIFY ERROR: Bone %s does not have a %s side" % (strip_org(self.org_parent), self.params.object_side))
            parent_p = pb[def_parent_name]
            member_Z_index = parent_p['member_index']
            bone_Z_index = 0
            for b in pb:
                if b.bone.use_deform and b.name.startswith('DEF-'):  
                    if b['member_index'] == member_Z_index and b['bone_index'] > bone_Z_index:
                        bone_Z_index = b['bone_index']
            bone_Z_index += 1

            bpy.ops.object.mode_set(mode='EDIT')
        else:
            member_Z_index = self.params.member_Z_index
            bone_Z_index = self.params.first_bone_Z_index

        eb = self.obj.data.edit_bones
        
        # Get parent's layers
        if self.params.use_parent_layers:
            layers = eb[self.org_parent].layers
        else:
            layers = self.params.layers
            
        ctrl_chain = []
        # def_chain = []

        # if self.params.duplicate_lr:
        #     sides = ['.L', '.R']
        # else:
        sides = [self.params.object_side]
        if sides[0] == '.C':
            sides[0] = ''
        for s in sides:
            for i, b in enumerate(self.org_bones):
                # Control bones
                ctrl_bone = copy_bone(self.obj, b)
                ctrl_bone_e = eb[ctrl_bone]

                # Name
                ctrl_bone_e.name = strip_org(b) + s

                # Parenting
                if i == 0:
                    # First bone
                    # TODO Check if parent still exists, else check if .L / .R exists, else do nothing
                    if eb[b].parent is not None:
                        bone_parent_name = eb[b].parent.name 
                        if not bone_parent_name in eb:
                            raise MetarigError("RIGIFY ERROR: Bone %s does not have a %s side" % (strip_org(eb[b].parent.name), s))
                        ctrl_bone_e.parent = eb[bone_parent_name]
                    else:
                        ctrl_bone_e.parent = eb['MCH-Flip']
                else:
                    # The rest
                    ctrl_bone_e.parent = eb[ctrl_chain[-1]]

                ctrl_bone_e.layers = layers

                # Add to list
                ctrl_chain += [ctrl_bone_e.name]

                # Def bones
                def_bone = pantin_utils.create_deformation(self.obj, b, self.params.mutable_order, member_Z_index, bone_Z_index + i, b+s)
                # def_chain.append(def_bone)

            bpy.ops.object.mode_set(mode='OBJECT')
            pb = self.obj.pose.bones

            # Constraints
            for org, ctrl in zip(self.org_bones, ctrl_chain):
                con = pb[org].constraints.new('COPY_TRANSFORMS')
                con.name = "copy_transforms"
                con.target = self.obj
                con.subtarget = ctrl
        
def add_parameters(params):
    params.use_parent_Z_index = bpy.props.BoolProperty(name="Use parent's Z Index",
                                                  default=True,
                                                  description="The object will use its parent's Z index")
    params.member_Z_index = bpy.props.FloatProperty(name="Z index",
                                           default=0.0,
                                           description="Defines member's Z order")
    params.first_bone_Z_index = bpy.props.FloatProperty(name="First Bone Z index",
                                           default=0.0,
                                           description="Defines bone's Z order")
    params.mutable_order = bpy.props.BoolProperty(name="Mutable Order",
                                                  default=False,
                                                  description="This member may change depth when flipped")
    # params.member_Z_index = bpy.props.FloatProperty(name="Indice Z membre", default=0.0, description="Définit l'ordre des membres dans l'espace")
    # params.first_bone_Z_index = bpy.props.FloatProperty(name="Indice Z premier os", default=0.0, description="Définit l'ordre des os dans l'espace")
    # params.mutable_order = bpy.props.BoolProperty(name="Ordre change", default=True, description="Ce membre peut changer de profondeur")
    # params.duplicate_lr = bpy.props.BoolProperty(name="Duplicate LR",
    #                                              default=True,
    #                                              description="Create two limbs for left and right")
    params.object_side = bpy.props.EnumProperty(name="Side",
                                         default='.C',
                                         description="If the limb is not to be duplicated, choose its side",
                                         items=(('.L', 'Left', ""),
                                                ('.C', 'Center', ""),
                                                ('.R', 'Right', ""),
                                                ))
    params.use_parent_layers = bpy.props.BoolProperty(name="Use parent's layers",
                                                  default=True,
                                                  description="The object will use its parent's layers")
    params.layers = bpy.props.BoolVectorProperty(size=32,
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
    r.prop(params, "mutable_order")
    # r = layout.row()
    # r.prop(params, "duplicate_lr")
    # if not params.duplicate_lr:
    col = layout.column(align=True)
    r = col.row()
    r.label("Side:")
    r = col.row()
    r.prop(params, "object_side", expand=True)

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

    bone = arm.edit_bones.new('Chapeau')
    bone.head[:] = 0.0432, -0.0000, 1.6260
    bone.tail[:] = 0.0432, -0.0000, 1.7549
    bone.roll = 3.1416
    bone.use_connect = False
    bones['Chapeau'] = bone.name

    bpy.ops.object.mode_set(mode='OBJECT')
    pbone = obj.pose.bones[bones['Chapeau']]
    pbone.rigify_type = 'pantin.simple'
    pbone.lock_location = (False, False, True)
    pbone.lock_rotation = (True, True, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'XZY'

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