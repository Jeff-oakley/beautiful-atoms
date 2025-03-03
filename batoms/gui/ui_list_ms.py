"""
"""

import bpy
from bpy.types import Menu, Panel, UIList


class BATOMS_MT_ms_context_menu(Menu):
    bl_label = "Molecular Surface Specials"
    bl_idname = "BATOMS_MT_ms_context_menu"

    def draw(self, _context):
        layout = self.layout
        op = layout.operator("surface.ms_add", icon='ADD',
                             text="Add Molecular Surface")
        layout.separator()
        op = layout.operator("surface.ms_remove", icon='X',
                             text="Delete All Molecular Surface")
        op.all = True


class BATOMS_UL_ms(UIList):
    def draw_item(self, _context, layout, _data, item, icon, active_data, _active_propname, index):
        ms = item
        custom_icon = 'OBJECT_DATAMODE'
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            split = layout.split(factor=0.5, align=False)
            split.prop(ms, "name", text="", emboss=False, icon=custom_icon)
            row = split.row(align=True)
            row.emboss = 'NONE_OR_STATUS'
            row.prop(ms, "type", text="")
            row.prop(ms, "select", text="")
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon=custom_icon)


class BATOMS_PT_ms(Panel):
    bl_label = "Molecular Surface"
    bl_category = "Surface"
    bl_idname = "BATOMS_PT_ms"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    # bl_options = {'DEFAULT_CLOSED'}

    COMPAT_ENGINES = {'BLENDER_RENDER', 'BLENDER_EEVEE', 'BLENDER_WORKBENCH'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        if obj:
            return obj.batoms.type != 'OTHER'
        else:
            return False

    def draw(self, context):
        layout = self.layout

        ob = context.object
        ba = bpy.data.collections[ob.batoms.label].batoms
        if len(ba.bms) > 0:
            kb = ba.bms[ba.ms_index]
        else:
            kb = None

        row = layout.row()

        rows = 3
        if kb:
            rows = 5

        row.template_list("BATOMS_UL_ms", "", ba, "bms",
                          ba, "ms_index", rows=rows)

        col = row.column(align=True)
        op = col.operator("surface.ms_add", icon='ADD', text="")
        op = col.operator("surface.ms_remove", icon='REMOVE', text="")
        if kb is not None:
            op.name = kb.name
        col.separator()

        col.menu("BATOMS_MT_ms_context_menu", icon='DOWNARROW_HLT', text="")

        if kb:
            col.separator()

            sub = col.column(align=True)

            split = layout.split(factor=0.4)
            row = split.row()

            row = split.row()
            row.alignment = 'RIGHT'

            sub = row.row(align=True)
            sub.label()  # XXX, for alignment only

            sub = row.row()
            layout.use_property_split = True
            row = layout.row()
            col = layout.column()
            sub = col.column(align=True)
            sub.prop(kb, "type", text="Type")
            sub.prop(kb, "probe", text="Probe")
            sub.prop(kb, "resolution", text="Resolution")
            sub.prop(kb, "select", text="Select")
            col.prop(kb, "color",  text="color")
            col.separator()
            op = layout.operator(
                "surface.ms_draw", icon='GREASEPENCIL', text="Draw")
