import bpy
import importlib

from ...utils import copy_bone
from ...utils import make_deformer_name, strip_org
from ...utils import create_bone_widget, create_widget, create_cube_widget
from ...utils import connected_children_names, has_connected_children

from . import pantin_utils
from . import limb_common

importlib.reload(pantin_utils)
importlib.reload(limb_common)

script = """
ik_arm = ["%s", "%s", "%s"]
if is_selected(ik_arm):
    layout.prop(pose_bones[ik_arm[2]], '["pelvis_follow"]', text="Follow pelvis (" + ik_arm[2] + ")", slider=True)
"""

class Rig:
    def __init__(self, obj, bone_name, params):
        self.obj = obj
        self.org_bones = [bone_name] + connected_children_names(obj, bone_name)[:2]
        self.params = params
        if "right_layers" in params:
            self.right_layers = [bool(l) for l in params["right_layers"]]
        else:
            self.right_layers = None
        joint_name = self.params.joint_name

        if params.duplicate_lr:
            sides = ['.L', '.R']
        else:
            sides = ['']
        
        self.ik_limbs = {}
        for s in sides:
            self.ik_limbs[s] = limb_common.IKLimb(obj, self.org_bones, joint_name, params.do_flip, True, params.pelvis_name, s, ik_limits=[-150.0, 150.0, -160.0, 0.0])

    def generate(self):
        ui_script = ""
        for s, ik_limb in self.ik_limbs.items():
            ulimb_ik, ulimb_str, flimb_str, joint_str, elimb_ik, elimb_str = ik_limb.generate()

            bpy.ops.object.mode_set(mode='EDIT')

            # Def bones
            eb = self.obj.data.edit_bones
            if s == '.L':
                Z_index = self.params.Z_index
            else:
                Z_index = 5-self.params.Z_index
                
            for i, b in enumerate([elimb_str, flimb_str, ulimb_str]):
                def_bone = pantin_utils.create_deformation(self.obj, b, self.params.mutable_order, Z_index, i, b[4:-13]+s)

            # Set layers if specified
            if s == '.R' and self.right_layers:
                eb[ulimb_ik].layers = self.right_layers
                eb[joint_str].layers = self.right_layers
                eb[elimb_ik].layers = self.right_layers

            bpy.ops.object.mode_set(mode='OBJECT')
            pb = self.obj.pose.bones

            # Widgets
            if s == '.R':
                side_factor = 1.2
            else:
                side_factor = 1.0
            widget_size = pb[elimb_ik].length * side_factor
            pantin_utils.create_aligned_circle_widget(self.obj, ulimb_ik, number_verts=3, radius=widget_size)
            #pantin_utils.create_aligned_polygon_widget(self.obj, ulimb_ik, [[-1,-1], [-1,1], [1,1], [1,-1]])
            pantin_utils.create_aligned_circle_widget(self.obj, joint_str, radius=widget_size * 0.7)
            pantin_utils.create_aligned_circle_widget(self.obj, elimb_ik, radius=widget_size)

            # Bone groups
            if s == '.R':
                pantin_utils.assign_bone_group(self.obj, ulimb_ik, 'R')
                pantin_utils.assign_bone_group(self.obj, joint_str, 'R')
                pantin_utils.assign_bone_group(self.obj, elimb_ik, 'R')
            if s == '.L':
                pantin_utils.assign_bone_group(self.obj, ulimb_ik, 'L')
                pantin_utils.assign_bone_group(self.obj, joint_str, 'L')
                pantin_utils.assign_bone_group(self.obj, elimb_ik, 'L')


            # Constraints
            if s == '.R':
                for org, ctrl in zip(self.org_bones, [ulimb_str, flimb_str, elimb_str]):
                    con = pb[org].constraints.new('COPY_TRANSFORMS')
                    con.name = "copy_transforms"
                    con.target = self.obj
                    con.subtarget = ctrl

            ui_script += script % (ulimb_ik, joint_str, elimb_ik)

        return [ui_script]
                    
def add_parameters(params):
    params.Z_index = bpy.props.IntProperty(name="Z index", default=0, description="Defines member's Z order")
    params.mutable_order = bpy.props.BoolProperty(name="Mutable order", default=True, description="This member may change depth when flipped")
    params.duplicate_lr = bpy.props.BoolProperty(name="Duplicate LR", default=True, description="Create two limbs for left and right")
    params.do_flip = bpy.props.BoolProperty(name="Do Flip", default=True, description="True if the rig has a torso with flip system")
    params.pelvis_name = bpy.props.StringProperty(name="Pelvis Name", default="Pelvis", description="Name of the pelvis bone in whole rig")
    params.joint_name = bpy.props.StringProperty(name="Joint Name", default="Joint", description="Name of the middle joint")
    params.right_layers = bpy.props.BoolVectorProperty(size=32, description="Layers for the duplicated limb to be on")

def parameters_ui(layout, params):
    """ Create the ui for the rig parameters.
    """
    r = layout.row()
    r.prop(params, "Z_index")
    r.prop(params, "mutable_order")
    c = layout.column()
    c.prop(params, "joint_name")
    c = layout.column()
    c.prop(params, "do_flip")
    c.prop(params, "pelvis_name")
    r = layout.row()
    r.prop(params, "duplicate_lr")

    r = layout.row()
    r.active = params.duplicate_lr
    
    # Layers for the right arm
    col = r.column(align=True)
    row = col.row(align=True)
    row.prop(params, "right_layers", index=0, toggle=True, text="")
    row.prop(params, "right_layers", index=1, toggle=True, text="")
    row.prop(params, "right_layers", index=2, toggle=True, text="")
    row.prop(params, "right_layers", index=3, toggle=True, text="")
    row.prop(params, "right_layers", index=4, toggle=True, text="")
    row.prop(params, "right_layers", index=5, toggle=True, text="")
    row.prop(params, "right_layers", index=6, toggle=True, text="")
    row.prop(params, "right_layers", index=7, toggle=True, text="")
    row = col.row(align=True)
    row.prop(params, "right_layers", index=16, toggle=True, text="")
    row.prop(params, "right_layers", index=17, toggle=True, text="")
    row.prop(params, "right_layers", index=18, toggle=True, text="")
    row.prop(params, "right_layers", index=19, toggle=True, text="")
    row.prop(params, "right_layers", index=20, toggle=True, text="")
    row.prop(params, "right_layers", index=21, toggle=True, text="")
    row.prop(params, "right_layers", index=22, toggle=True, text="")
    row.prop(params, "right_layers", index=23, toggle=True, text="")

    col = r.column(align=True)
    row = col.row(align=True)
    row.prop(params, "right_layers", index=8, toggle=True, text="")
    row.prop(params, "right_layers", index=9, toggle=True, text="")
    row.prop(params, "right_layers", index=10, toggle=True, text="")
    row.prop(params, "right_layers", index=11, toggle=True, text="")
    row.prop(params, "right_layers", index=12, toggle=True, text="")
    row.prop(params, "right_layers", index=13, toggle=True, text="")
    row.prop(params, "right_layers", index=14, toggle=True, text="")
    row.prop(params, "right_layers", index=15, toggle=True, text="")
    row = col.row(align=True)
    row.prop(params, "right_layers", index=24, toggle=True, text="")
    row.prop(params, "right_layers", index=25, toggle=True, text="")
    row.prop(params, "right_layers", index=26, toggle=True, text="")
    row.prop(params, "right_layers", index=27, toggle=True, text="")
    row.prop(params, "right_layers", index=28, toggle=True, text="")
    row.prop(params, "right_layers", index=29, toggle=True, text="")
    row.prop(params, "right_layers", index=30, toggle=True, text="")
    row.prop(params, "right_layers", index=31, toggle=True, text="")

def create_sample(obj):
    # generated by rigify.utils.write_metarig
    bpy.ops.object.mode_set(mode='EDIT')
    arm = obj.data

    bones = {}

    bone = arm.edit_bones.new('Bras haut')
    bone.head[:] = 0.0056, -0.0000, 1.3408
    bone.tail[:] = 0.0100, -0.0000, 1.1262
    bone.roll = -0.0201
    bone.use_connect = False
    bones['Bras haut'] = bone.name
    bone = arm.edit_bones.new('Bras bas')
    bone.head[:] = 0.0100, -0.0000, 1.1262
    bone.tail[:] = 0.0383, -0.0000, 0.8731
    bone.roll = -0.1117
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['Bras haut']]
    bones['Bras bas'] = bone.name
    bone = arm.edit_bones.new('Main')
    bone.head[:] = 0.0383, -0.0000, 0.8731
    bone.tail[:] = 0.0383, -0.0000, 0.7657
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['Bras bas']]
    bones['Main'] = bone.name

    bpy.ops.object.mode_set(mode='OBJECT')
    pbone = obj.pose.bones[bones['Bras haut']]
    pbone.rigify_type = 'pantin.arm'
    pbone.lock_location = (False, False, True)
    pbone.lock_rotation = (True, True, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'XZY'
    try:
        pbone.rigify_parameters.right_layers = [False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, False]
    except AttributeError:
        pass
    try:
        pbone.rigify_parameters.joint_name = "Coude"
    except AttributeError:
        pass
    pbone = obj.pose.bones[bones['Bras bas']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, True)
    pbone.lock_rotation = (True, True, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'XZY'
    pbone = obj.pose.bones[bones['Main']]
    pbone.rigify_type = ''
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