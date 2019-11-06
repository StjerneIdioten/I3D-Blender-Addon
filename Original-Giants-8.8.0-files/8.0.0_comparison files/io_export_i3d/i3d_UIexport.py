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
#
# Copyright 2004 (C) GIANTS Software GmbH, Confidential, All Rights Reserved.

import bpy, bpy_extras
import io_export_i3d.i3d_IOexport as i3d_IOexport

global i3d_node
#-------------------------------------------------------------------------------
#   "I3D Exporter" I3D Menu Item
#-------------------------------------------------------------------------------
class I3D_MenuExport( bpy.types.Operator ):
    bl_label = "I3D Exporter"
    bl_idname = "i3d.menu_export"

    def execute( self, context ):
        try:
            bpy.utils.register_class( I3D_PanelExport )
            bpy.utils.register_class( I3D_PanelExport_ButtonClose )
            bpy.utils.register_class( I3D_PanelExport_ButtonExport )
            bpy.utils.register_class( I3D_PanelExport_ButtonAttr )
        except:
            pass
        return {'FINISHED'}
#-------------------------------------------------------------------------------
#   File -> Export
#-------------------------------------------------------------------------------
class I3D_FileExport( bpy.types.Operator, bpy_extras.io_utils.ExportHelper ):
    bl_idname           = "i3d.file_export"
    bl_label            = "Export I3D"
    bl_options          = {'PRESET'}
    filename_ext        = ".i3d"
    I3D_exportSelected  = bpy.props.BoolProperty   ( name = "Export Selected",  default = False )

    def __init__(self):
        self.filepath      = bpy.context.scene.I3D_export.I3D_exportFileLocation
        
    def draw( self, context ):
        layout = self.layout
        #-----------------------------------------
        # "Export Selected" box
        box = layout.box()
        row = box.row()
        row.prop( self,  "I3D_exportSelected" )
        #-----------------------------------------
        # "Export Options" box
        box = layout.box()
        row = box.row()
        # expand button for "Export Options"
        row.prop(   context.scene.I3D_UIexportSettings, 
                    "UI_exportOptions", 
                    icon='TRIA_DOWN' if context.scene.I3D_UIexportSettings.UI_exportOptions else 'TRIA_RIGHT', 
                    icon_only = True, 
                    emboss = False )
        # expanded view
        if context.scene.I3D_UIexportSettings.UI_exportOptions:
            row = box.row()
            row.prop( context.scene.I3D_export,  "I3D_exportIK"        )
            row.prop( context.scene.I3D_export,  "I3D_exportAnimation" )                
            row = box.row()
            row.prop( context.scene.I3D_export,  "I3D_exportShapes"    )
            row.prop( context.scene.I3D_export,  "I3D_exportNurbsCurves" )
            row = box.row()
            row.prop( context.scene.I3D_export,  "I3D_exportLights"      )
            row.prop( context.scene.I3D_export,  "I3D_exportCameras"     )
            row = box.row()
            row.prop( context.scene.I3D_export,  "I3D_exportParticleSystems" )
            row.prop( context.scene.I3D_export,  "I3D_exportUserAttributes"  )
        #-----------------------------------------
        # "Shape Export Subparts" box
        box = layout.box()
        row = box.row()
        # expand button for "Shape Export Subparts"
        row.prop(   context.scene.I3D_UIexportSettings, 
                    "UI_shapeExportSubparts", 
                    icon='TRIA_DOWN' if context.scene.I3D_UIexportSettings.UI_shapeExportSubparts else 'TRIA_RIGHT', 
                    icon_only = True, 
                    emboss = False )
        if context.scene.I3D_UIexportSettings.UI_shapeExportSubparts:
            row = box.row()
            row.prop( context.scene.I3D_export, "I3D_exportNormals"     )
            row.prop( context.scene.I3D_export, "I3D_exportTexCoords"   )
            row = box.row()
            row.prop( context.scene.I3D_export, "I3D_exportColors"      )
            row.prop( context.scene.I3D_export, "I3D_exportSkinWeigths" )
        #-----------------------------------------
        # "Miscellaneous" box
        box = layout.box()
        row = box.row()
        # expand button for "Miscellaneous"
        row.prop(   context.scene.I3D_UIexportSettings, 
                    "UI_miscellaneous", 
                    icon='TRIA_DOWN' if context.scene.I3D_UIexportSettings.UI_miscellaneous else 'TRIA_RIGHT', 
                    icon_only = True, 
                    emboss = False )
        if context.scene.I3D_UIexportSettings.UI_miscellaneous:
            row = box.row()
            row.prop( context.scene.I3D_export, "I3D_exportVerbose"       )
            row.prop( context.scene.I3D_export, "I3D_exportRelativePaths" )
            row = box.row()
            row.prop( context.scene.I3D_export, "I3D_exportApplyModifiers"  )
            row = box.row()
            row.prop( context.scene.I3D_export, "I3D_exportAxisOrientations"  )
        #-----------------------------------------
        
    def execute(self, context):
        bpy.context.scene.I3D_export.I3D_exportUseBlenderFileName   = False
        bpy.context.scene.I3D_export.I3D_exportFileLocation         = self.filepath
        if ( self.I3D_exportSelected ):
            i3d_IOexport.doExportSelecred()
        else:
            i3d_IOexport.doExportAll()
        return {'FINISHED'};
        
def fileExportMenuItem(self, context):
    self.layout.operator( I3D_FileExport.bl_idname, text ="GIANTS I3D (.i3d)" );
#-------------------------------------------------------------------------------
#   Properties Pannel
#-------------------------------------------------------------------------------
class I3D_PanelExport( bpy.types.Panel ):
    bl_label        = "GIANTS I3D Exporter"
    bl_space_type   = "VIEW_3D"
    bl_region_type  = "UI"
    bl_idname       = "i3d_panel_export"
    bl_context      = "scene"

    def draw( self, context ):
        layout = self.layout
        layout.prop( context.scene.I3D_UIexportSettings,  "UI_settingsMode", expand = True )
        #-----------------------------------------
        # "Export" tab
        if   'exp'  == context.scene.I3D_UIexportSettings.UI_settingsMode:
            #-----------------------------------------
            # "Export Options" box
            box = layout.box()
            row = box.row()
            # expand button for "Export Options"
            row.prop(   context.scene.I3D_UIexportSettings, 
                        "UI_exportOptions", 
                        icon='TRIA_DOWN' if context.scene.I3D_UIexportSettings.UI_exportOptions else 'TRIA_RIGHT', 
                        icon_only = True, 
                        emboss = False )
            # expanded view
            if context.scene.I3D_UIexportSettings.UI_exportOptions:
                row = box.row()
                row.prop( context.scene.I3D_export,  "I3D_exportIK"        )
                row.prop( context.scene.I3D_export,  "I3D_exportAnimation" )                
                row = box.row()
                row.prop( context.scene.I3D_export,  "I3D_exportShapes"    )
                row.prop( context.scene.I3D_export,  "I3D_exportNurbsCurves" )
                row = box.row()
                row.prop( context.scene.I3D_export,  "I3D_exportLights"      )
                row.prop( context.scene.I3D_export,  "I3D_exportCameras"     )
                row = box.row()
                row.prop( context.scene.I3D_export,  "I3D_exportParticleSystems" )
                row.prop( context.scene.I3D_export,  "I3D_exportUserAttributes"  )
            #-----------------------------------------
            # "Shape Export Subparts" box
            box = layout.box()
            row = box.row()
            # expand button for "Shape Export Subparts"
            row.prop(   context.scene.I3D_UIexportSettings, 
                        "UI_shapeExportSubparts", 
                        icon='TRIA_DOWN' if context.scene.I3D_UIexportSettings.UI_shapeExportSubparts else 'TRIA_RIGHT', 
                        icon_only = True, 
                        emboss = False )
            if context.scene.I3D_UIexportSettings.UI_shapeExportSubparts:
                row = box.row()
                row.prop( context.scene.I3D_export, "I3D_exportNormals"     )
                row.prop( context.scene.I3D_export, "I3D_exportTexCoords"   )
                row = box.row()
                row.prop( context.scene.I3D_export, "I3D_exportColors"      )
                row.prop( context.scene.I3D_export, "I3D_exportSkinWeigths" )
            #-----------------------------------------
            # "Miscellaneous" box
            box = layout.box()
            row = box.row()
            # expand button for "Miscellaneous"
            row.prop(   context.scene.I3D_UIexportSettings, 
                        "UI_miscellaneous", 
                        icon='TRIA_DOWN' if context.scene.I3D_UIexportSettings.UI_miscellaneous else 'TRIA_RIGHT', 
                        icon_only = True, 
                        emboss = False )
            if context.scene.I3D_UIexportSettings.UI_miscellaneous:
                row = box.row()
                row.prop( context.scene.I3D_export, "I3D_exportVerbose"       )
                row.prop( context.scene.I3D_export, "I3D_exportRelativePaths" )
                row = box.row()
                row.prop( context.scene.I3D_export, "I3D_exportApplyModifiers"  )
                row = box.row()
                row.prop( context.scene.I3D_export, "I3D_exportAxisOrientations"  )
            #-----------------------------------------
            # "Output File" box
            box = layout.box()
            row = box.row()
            # expand button for "Output File"
            row.prop(   context.scene.I3D_UIexportSettings, 
                        "UI_outputFile", 
                        icon='TRIA_DOWN' if context.scene.I3D_UIexportSettings.UI_outputFile else 'TRIA_RIGHT', 
                        icon_only = True, 
                        emboss = False )
            if context.scene.I3D_UIexportSettings.UI_outputFile:
                row = box.row()
                row.prop( context.scene.I3D_export, "I3D_exportUseBlenderFileName" )
                row = box.row()
                row.enabled = not context.scene.I3D_export.I3D_exportUseBlenderFileName
                row.prop( context.scene.I3D_export, "I3D_exportFileLocation"       )
            #-----------------------------------------
            row = layout.row( align = True )
            row.operator( "i3d.panel_export_do", text = "Export All"      ).state = 1
            row.operator( "i3d.panel_export_do", text = "Export Selected" ).state = 2
        #-----------------------------------------
        # "Attributes" tab
        elif 'attr' == context.scene.I3D_UIexportSettings.UI_settingsMode:
            #-----------------------------------------
            # "Current Node" box
            box = layout.box()
            row = box.row()
            # expand button for "Current Node"
            row.prop(   context.scene.I3D_UIexportSettings, 
                        "UI_currentNode", 
                        icon='TRIA_DOWN' if context.scene.I3D_UIexportSettings.UI_currentNode else 'TRIA_RIGHT', 
                        icon_only = True, 
                        emboss = False )
            # expanded view
            if context.scene.I3D_UIexportSettings.UI_currentNode:
                row = box.row()                
                row = row.box().row()
                # GET NAME FROM PROPERTY
                global i3d_node
                row.label( text = "Current")
                row.label( text = i3d_node.getName() )
            #-----------------------------------------
            # "Rigid Body" box
            box = layout.box()
            row = box.row()
            # expand button for "Rigid Body"
            row.prop(   context.scene.I3D_UIexportSettings, 
                        "UI_rigidBody", 
                        icon='TRIA_DOWN' if context.scene.I3D_UIexportSettings.UI_rigidBody else 'TRIA_RIGHT', 
                        icon_only = True, 
                        emboss = False )
            # expanded view
            if context.scene.I3D_UIexportSettings.UI_rigidBody:
                split = box.split()
                col = split.column()
                col.label( "Static" )
                col.label( "Kinematic" )
                col.label( "Dynamic" )
                col.label( "Compound" )
                col.label( "Compound Child" )
                col.label( "Collision" )
                col.label( "Collision Mask" )
                col.label( "Restitution" )
                col.label( "Static Friction" )
                col.label( "Dynamic Friction" )
                col.label( "Linear Damping" )
                col.label( "Angular Damping" )
                col.label( "Density" )
                col.label( "Skin Width" )
                col.label( "Solve Iterations" )
                col.label( "Continues Collision Detection" )
                col.label( "Trigger" )
                col = split.column()
                col.prop( context.scene.I3D_attributes,  "I3D_static",                text = "" )
                col.prop( context.scene.I3D_attributes,  "I3D_kinematic",             text = "" )  
                col.prop( context.scene.I3D_attributes,  "I3D_dynamic",               text = "" )  
                col.prop( context.scene.I3D_attributes,  "I3D_compound",              text = "" )  
                col.prop( context.scene.I3D_attributes,  "I3D_compoundChild",         text = "" )  
                col.prop( context.scene.I3D_attributes,  "I3D_collision",             text = "" )  
                col.prop( context.scene.I3D_attributes,  "I3D_collisionMask",         text = "" )  
                col.prop( context.scene.I3D_attributes,  "I3D_restitution",           text = "" )  
                col.prop( context.scene.I3D_attributes,  "I3D_staticFriction",        text = "" )  
                col.prop( context.scene.I3D_attributes,  "I3D_dynamicFriction",       text = "" )  
                col.prop( context.scene.I3D_attributes,  "I3D_linearDamping",         text = "" )  
                col.prop( context.scene.I3D_attributes,  "I3D_angularDamping",        text = "" )  
                col.prop( context.scene.I3D_attributes,  "I3D_density",               text = "" )  
                col.prop( context.scene.I3D_attributes,  "I3D_skinWidth",             text = "" )  
                col.prop( context.scene.I3D_attributes,  "I3D_solverIterationCount",  text = "" )
                col.prop( context.scene.I3D_attributes,  "I3D_ccd",                   text = "" )  
                col.prop( context.scene.I3D_attributes,  "I3D_trigger",               text = "" )
            #-----------------------------------------
            # "Joint" box
            box = layout.box()
            row = box.row()
            # expand button for "Joint"
            row.prop(   context.scene.I3D_UIexportSettings, 
                        "UI_joint", 
                        icon='TRIA_DOWN' if context.scene.I3D_UIexportSettings.UI_joint else 'TRIA_RIGHT', 
                        icon_only = True, 
                        emboss = False )
            # expanded view
            if context.scene.I3D_UIexportSettings.UI_joint:
                split = box.split()
                col = split.column()
                col.label( "Joint" )
                col.label( "Projection" )
                col.label( "Projection Distance" )
                col.label( "Projection Angle" )
                col.label( "X-Axis Drive" )
                col.label( "Y-Axis Drive" )
                col.label( "Z-Axis Drive" )
                col.label( "Drive Position" )
                col.label( "Drive Force Limit" )
                col.label( "Drive Spring" )
                col.label( "Drive Damping" )
                col.label( "Breakable" )
                col.label( "Break Force" )
                col.label( "Break Torque" )
                col = split.column()
                col.prop( context.scene.I3D_attributes,  "I3D_joint",            text = "" )
                col.prop( context.scene.I3D_attributes,  "I3D_projection",       text = "" )
                col.prop( context.scene.I3D_attributes,  "I3D_projDistance",     text = "" )
                col.prop( context.scene.I3D_attributes,  "I3D_projAngle",        text = "" )
                col.prop( context.scene.I3D_attributes,  "I3D_xAxisDrive",       text = "" )
                col.prop( context.scene.I3D_attributes,  "I3D_yAxisDrive",       text = "" )
                col.prop( context.scene.I3D_attributes,  "I3D_zAxisDrive",       text = "" )
                col.prop( context.scene.I3D_attributes,  "I3D_drivePos",         text = "" )
                col.prop( context.scene.I3D_attributes,  "I3D_driveForceLimit",  text = "" )
                col.prop( context.scene.I3D_attributes,  "I3D_driveSpring",      text = "" )
                col.prop( context.scene.I3D_attributes,  "I3D_driveDamping",     text = "" )
                col.prop( context.scene.I3D_attributes,  "I3D_breakableJoint",   text = "" )
                col.prop( context.scene.I3D_attributes,  "I3D_jointBreakForce",  text = "" )
                col.prop( context.scene.I3D_attributes,  "I3D_jointBreakTorque", text = "" )
            #-----------------------------------------
            # "Rendering" box
            box = layout.box()
            row = box.row()
            # expand button for "Rendering"
            row.prop(   context.scene.I3D_UIexportSettings, 
                        "UI_rendering", 
                        icon='TRIA_DOWN' if context.scene.I3D_UIexportSettings.UI_rendering else 'TRIA_RIGHT', 
                        icon_only = True, 
                        emboss = False )
            # expanded view
            if context.scene.I3D_UIexportSettings.UI_rendering:
                split = box.split()
                col = split.column()
                col.label( "Occlusion Culling" )
                col.label( "Casts Shadows" )
                col.label( "Receive Shadows" )
                col.label( "Non Renderable" )
                col.label( "Clip Distance" )
                col.label( "Object Mask" )
                col.label( "Light Mask (Hex)" )
                col.label( "Decal Layer" )
                col.label( "LOD" )
                col.label( "Child 0 Distance" )
                col.label( "Child 1 Distance" )
                col.label( "Child 2 Distance" )
                col.label( "Child 3 Distance" )
                col = split.column()
                col.prop( context.scene.I3D_attributes,  "I3D_oc",             text = "" )
                col.prop( context.scene.I3D_attributes,  "I3D_castsShadows",   text = "" )
                col.prop( context.scene.I3D_attributes,  "I3D_receiveShadows", text = "" )
                col.prop( context.scene.I3D_attributes,  "I3D_nonRenderable",  text = "" )
                col.prop( context.scene.I3D_attributes,  "I3D_clipDistance",   text = "" )
                col.prop( context.scene.I3D_attributes,  "I3D_objectMask",     text = "" )
                col.prop( context.scene.I3D_attributes,  "I3D_lightMask",      text = "" )
                col.prop( context.scene.I3D_attributes,  "I3D_decalLayer",     text = "" )
                col.prop( context.scene.I3D_attributes,  "I3D_lod",            text = "" )
                row = col.row()
                row.enabled = False
                row.prop( context.scene.I3D_UIexportSettings,  "I3D_lod0",     text = "" )
                col.prop( context.scene.I3D_attributes,        "I3D_lod1",     text = "" )
                col.prop( context.scene.I3D_attributes,        "I3D_lod2",     text = "" )
                col.prop( context.scene.I3D_attributes,        "I3D_lod3",     text = "" )
            #-----------------------------------------
            row = layout.row( align = True )
            row.operator( "i3d.panel_export_attr", text = "Load Current"    ).state = 1
            row.operator( "i3d.panel_export_attr", text = "Save Current"    ).state = 2
            row = layout.row( align = True )
            row.operator( "i3d.panel_export_attr", text = "Apply Selected"  ).state = 3
            #-----------------------------------------
        row = layout.row( )
        row.operator( "i3d.panel_export_close", icon = 'X' )
#-------------------------------------------------------------------------------
#   Pannel Buttons
#-------------------------------------------------------------------------------
class I3D_PanelExport_ButtonAttr( bpy.types.Operator ):
    bl_idname  = "i3d.panel_export_attr"
    bl_label   = "Attributes"
    state      = bpy.props.IntProperty()
    
    def execute( self, context ):
        global i3d_node
        if   1 == self.state:            
            i3d_node.connect( bpy.context.active_object )
            i3d_node.loadCurrent()
        elif 2 == self.state:
            i3d_node.saveCurrent()
        elif 3 == self.state:
            i3d_node.applySelected( bpy.context.selected_objects )
        return {'FINISHED'}  

class I3D_PanelExport_ButtonExport( bpy.types.Operator ):
    bl_idname  = "i3d.panel_export_do"
    bl_label   = "Export"
    state      = bpy.props.IntProperty()
    
    def execute( self, context ):
        if   1 == self.state:
            i3d_IOexport.doExportAll()
        elif 2 == self.state:
            i3d_IOexport.doExportSelecred()
        return {'FINISHED'}  
        
class I3D_PanelExport_ButtonClose( bpy.types.Operator ):
    bl_idname  = "i3d.panel_export_close"
    bl_label   = "Close"

    def execute( self, context ):
        bpy.utils.unregister_class( I3D_PanelExport )
        bpy.utils.unregister_class( I3D_PanelExport_ButtonClose )
        bpy.utils.unregister_class( I3D_PanelExport_ButtonExport )
        bpy.utils.unregister_class( I3D_PanelExport_ButtonAttr )
        return {'FINISHED'}
#-------------------------------------------------------------------------------
#   CurrentNode Class
#-------------------------------------------------------------------------------
class I3D_Node( object ):
    currentNode = None
    attributes  = [ 'I3D_static', 
                    'I3D_kinematic', 
                    'I3D_dynamic', 
                    'I3D_compound', 
                    'I3D_compoundChild', 
                    'I3D_collision', 
                    'I3D_collisionMask', 
                    'I3D_solverIterationCount',
                    'I3D_restitution', 
                    'I3D_staticFriction', 
                    'I3D_dynamicFriction', 
                    'I3D_linearDamping',        
                    'I3D_angularDamping', 
                    'I3D_density', 
                    'I3D_skinWidth', 
                    'I3D_ccd', 
                    'I3D_trigger',
                    'I3D_joint', 
                    'I3D_projection', 
                    'I3D_projDistance', 
                    'I3D_projAngle', 
                    'I3D_xAxisDrive',
                    'I3D_yAxisDrive', 
                    'I3D_zAxisDrive', 
                    'I3D_drivePos', 
                    'I3D_driveForceLimit',       
                    'I3D_driveSpring', 
                    'I3D_driveDamping', 
                    'I3D_breakableJoint', 
                    'I3D_jointBreakForce',
                    'I3D_jointBreakTorque', 
                    'I3D_oc',
                    'I3D_castsShadows',
                    'I3D_receiveShadows',
                    'I3D_nonRenderable', 
                    'I3D_clipDistance',          
                    'I3D_objectMask', 
                    'I3D_lightMask', 
                    'I3D_decalLayer', 
                    'I3D_lod', 
                    'I3D_lod1', 
                    'I3D_lod2', 
                    'I3D_lod3'  ]

    def __init__( self ):
        bpy.types.Scene.I3D_currentNode = self.currentNode

    def __del__( self ):
        del bpy.types.Scene.I3D_currentNode
    
    def exists( self ):
        ''' True if self.currentNode exists and is currentNode of bpy.types.Object class '''
        if not hasattr ( bpy.context.scene, 'I3D_currentNode' ): return False
        if not isinstance( self.currentNode, bpy.types.Object ): return False
        if self.currentNode in bpy.data.objects[:]:
            return True
        else:
            return False

    def _update( self, obj ):
        self.currentNode = obj
        bpy.types.Scene.I3D_currentNode = obj
                
    def connect( self, obj ):
        self._update( obj )
        
    def getName( self ):
        if self.exists(): return self.currentNode.name 
        else:
            self._update( None )
            return "None"  
    
    def _getObjectAttr( self, attr ):
        return getattr( self.currentNode.I3D_attributes, attr )

    def _getSceneAttr( self, attr ):
        return getattr( bpy.context.scene.I3D_attributes, attr ) 
        
    def _setObjectAtr( self, attr, value ):
        setattr(self.currentNode.I3D_attributes, attr, value )

    def _setSceneAttr( self, attr, value ):
        setattr( bpy.context.scene.I3D_attributes, attr, value )

    def _save( self, obj ):
        ''' take data from context.scene and save it to the object '''
        for attr in self.attributes:
            setattr( obj.I3D_attributes, attr, self._getSceneAttr( attr ) )
    
    def saveCurrent( self ):
        if self.exists():
            self._save( self.currentNode )
            return True
        else:
            return False
    
    def loadCurrent( self ):
        if self.exists():
            for attr in self.attributes:
                self._setSceneAttr( attr, self._getObjectAttr( attr ) )
            return True
        else:
            return False

    def applySelected( self, selected_objects ):
        for obj in selected_objects:
            self._save( obj )    
#-------------------------------------------------------------------------------
#   Init Scene PropertyGroups
#-------------------------------------------------------------------------------
class I3D_UIexportSettings( bpy.types.PropertyGroup ):
    UI_settingsMode = bpy.props.EnumProperty(
                items = [ ('exp' ,  'Export'   ,  ''), 
                          ('attr',  'Attributes', '') ],
                name = "Settings Mode"
                )
    UI_exportOptions       = bpy.props.BoolProperty   ( name = "Export Options",        default = True  )
    UI_shapeExportSubparts = bpy.props.BoolProperty   ( name = "Shape Export Subparts", default = True  )
    UI_miscellaneous       = bpy.props.BoolProperty   ( name = "Miscellaneous",         default = True  )
    UI_outputFile          = bpy.props.BoolProperty   ( name = "Output File",           default = True  )
    UI_currentNode         = bpy.props.BoolProperty   ( name = "Current Node",          default = True  )
    UI_rigidBody           = bpy.props.BoolProperty   ( name = "Rigid Body",            default = True  )
    UI_joint               = bpy.props.BoolProperty   ( name = "Joint",                 default = False )
    UI_rendering           = bpy.props.BoolProperty   ( name = "Rendering",             default = True  )
    I3D_lod0               = bpy.props.FloatProperty  ( name = "Child 0 Distance",      default = 0.000 )
    
    @classmethod
    def register( cls ):
        bpy.types.Scene.I3D_UIexportSettings = bpy.props.PointerProperty(
            name = "I3D UI Export Settings",
            type =  cls,
            description = "I3D UI Export Settings"
        )
    @classmethod
    def unregister( cls ):
        if bpy.context.scene.get( 'I3D_UIexportSettings' ):  del bpy.context.scene[ 'I3D_UIexportSettings' ]
        try:    del bpy.types.Scene.I3D_UIexportSettings
        except: pass

class I3D_export( bpy.types.PropertyGroup ):
    ''' PropertyGroup for the  I3D_export Settings attached to the bpy.types.Scene '''
    I3D_exportIK                  = bpy.props.BoolProperty   ( name = "IK",                   default = False )
    I3D_exportAnimation           = bpy.props.BoolProperty   ( name = "Animation",            default = True  )
    I3D_exportShapes              = bpy.props.BoolProperty   ( name = "Shapes",               default = True  )
    I3D_exportNurbsCurves         = bpy.props.BoolProperty   ( name = "Nurbs Curves",         default = False )
    I3D_exportLights              = bpy.props.BoolProperty   ( name = "Lights",               default = True  )
    I3D_exportCameras             = bpy.props.BoolProperty   ( name = "Cameras",              default = True  )
    I3D_exportParticleSystems     = bpy.props.BoolProperty   ( name = "Particle Systems",     default = False )
    I3D_exportUserAttributes      = bpy.props.BoolProperty   ( name = "User Attributes",      default = True  )
    I3D_exportNormals             = bpy.props.BoolProperty   ( name = "Normals",              default = True  )
    I3D_exportColors              = bpy.props.BoolProperty   ( name = "Vertex Colors",        default = True  )
    I3D_exportTexCoords           = bpy.props.BoolProperty   ( name = "UVs",                  default = True  )
    I3D_exportSkinWeigths         = bpy.props.BoolProperty   ( name = "Skin Weigths",         default = True  )
    I3D_exportVerbose             = bpy.props.BoolProperty   ( name         = "Verbose",
                                                               description  = "Print more info",
                                                               default      = False ) 
    I3D_exportRelativePaths       = bpy.props.BoolProperty   ( name = "Relative Paths",       default = True  )
    I3D_exportApplyModifiers      = bpy.props.BoolProperty   ( name = "Apply Modifiers",      default = True  )
    I3D_exportAxisOrientations    = bpy.props.EnumProperty   ( 
                                    items = [   ( "BAKE_TRANSFORMS" , "Bake Transforms" , "Change axis Z = Y" ), 
                                                ( "KEEP_AXIS"       , "Keep Axis"       , "Rotate Root objects on 90 degrees by X" ),
                                                ( "KEEP_TRANSFORMS" , "Keep Transforms" , "Export without any changes" )   ],
                                    name    = "Axis Orientations",
                                    default = "BAKE_TRANSFORMS" )
    I3D_exportUseBlenderFileName  = bpy.props.BoolProperty   ( name = "Use Blender Filename", default = True  )
    I3D_exportFileLocation        = bpy.props.StringProperty ( name = "File Location",  subtype = "FILE_PATH" )
    
    @classmethod
    def register( cls ):
        bpy.types.Scene.I3D_export = bpy.props.PointerProperty(
            name = "I3D Export Settings",
            type =  cls,
            description = "I3D Export Settings"
        )

    @classmethod
    def unregister( cls ):
        if bpy.context.scene.get( 'I3D_export' ):  del bpy.context.scene[ 'I3D_export' ]
        try:    del bpy.types.Scene.I3D_export
        except: pass

class I3D_attributes( bpy.types.PropertyGroup ):
    ''' PropertyGroup for the  I3D_attributes Settings attached to the bpy.types.Scene '''
    I3D_static                = bpy.props.BoolProperty   ( name = "Static",              default = True,  description = "passive Rigid Body non movable"  )
    I3D_kinematic             = bpy.props.BoolProperty   ( name = "Kinematic",           default = False, description = "passive Rigid Body movable"      )
    I3D_dynamic               = bpy.props.BoolProperty   ( name = "Dynamic",             default = False, description = "active Rigid Body simulated"     )
    I3D_compound              = bpy.props.BoolProperty   ( name = "Compound",            default = False, description = "group of Rigid Bodies"           )
    I3D_compoundChild         = bpy.props.BoolProperty   ( name = "Compound Child",      default = False, description = "part of a group of Rigid Bodies" )
    I3D_collision             = bpy.props.BoolProperty   ( name = "Collision",           default = True   )
    I3D_collisionMask         = bpy.props.IntProperty    ( name = "Collision Mask",      default = 255    )
    I3D_solverIterationCount  = bpy.props.IntProperty    ( name = "Solver Iterations",   default = 4      )
    I3D_restitution           = bpy.props.FloatProperty  ( name = "Restitution",         default = 0.000  )
    I3D_staticFriction        = bpy.props.FloatProperty  ( name = "Static Friction",     default = 0.500  )
    I3D_dynamicFriction       = bpy.props.FloatProperty  ( name = "Dynamic Friction",    default = 0.500  )
    I3D_linearDamping         = bpy.props.FloatProperty  ( name = "Linear Damping",      default = 0.500  )
    I3D_angularDamping        = bpy.props.FloatProperty  ( name = "Angular Damping",     default = 0.500  )
    I3D_density               = bpy.props.FloatProperty  ( name = "Density",             default = 1.000  )
    I3D_skinWidth             = bpy.props.FloatProperty  ( name = "Skin Width",          default = 0.050  )
    I3D_ccd                   = bpy.props.BoolProperty   ( name = "Continues Collision Detection" , default = False  )
    I3D_trigger               = bpy.props.BoolProperty   ( name = "Trigger",             default = False  )
    I3D_joint                 = bpy.props.BoolProperty   ( name = "Joint",               default = False  )
    I3D_projection            = bpy.props.BoolProperty   ( name = "Projection",          default = False  )
    I3D_projDistance          = bpy.props.FloatProperty  ( name = "Projection Distance", default = 0.010  )
    I3D_projAngle             = bpy.props.FloatProperty  ( name = "Projection Angle",    default = 0.010  )
    I3D_xAxisDrive            = bpy.props.BoolProperty   ( name = "X-Axis Drive",        default = False  )
    I3D_yAxisDrive            = bpy.props.BoolProperty   ( name = "Y-Axis Drive",        default = False  )
    I3D_zAxisDrive            = bpy.props.BoolProperty   ( name = "Z-Axis Drive",        default = False  )
    I3D_drivePos              = bpy.props.BoolProperty   ( name = "Drive Position",      default = False  )
    I3D_driveForceLimit       = bpy.props.FloatProperty  ( name = "Drive Force Limit",   default = 100000.0 )
    I3D_driveSpring           = bpy.props.FloatProperty  ( name = "Drive Spring",        default = 1.000  )
    I3D_driveDamping          = bpy.props.FloatProperty  ( name = "Drive Damping",       default = 0.010  )
    I3D_breakableJoint        = bpy.props.BoolProperty   ( name = "Breakable",           default = False  )
    I3D_jointBreakForce       = bpy.props.FloatProperty  ( name = "Break Force",         default = 0.000  )
    I3D_jointBreakTorque      = bpy.props.FloatProperty  ( name = "Break Torque",        default = 0.000  )
    I3D_oc                    = bpy.props.BoolProperty   ( name = "Occlusion Culling",   default = False  )
    I3D_castsShadows          = bpy.props.BoolProperty   ( name = "Casts Shadows",       default = True  )
    I3D_receiveShadows        = bpy.props.BoolProperty   ( name = "Receive Shadows",     default = True  )
    I3D_nonRenderable         = bpy.props.BoolProperty   ( name = "Non Renderable",      default = False  )
    I3D_clipDistance          = bpy.props.FloatProperty  ( name = "Clip Distance",       default = 0.000  )
    I3D_objectMask            = bpy.props.IntProperty    ( name = "Object Mask",         default = 255    )
    I3D_lightMask             = bpy.props.StringProperty ( name = "Light Mask (Hex)",    default = "FFFF" )
    I3D_decalLayer            = bpy.props.IntProperty    ( name = "Decal Layer",         default = 0 )
    I3D_lod                   = bpy.props.BoolProperty   ( name = "LOD",                 default = False  )
    I3D_lod1                  = bpy.props.FloatProperty  ( name = "Child 1 Distance",    default = 0.000  )
    I3D_lod2                  = bpy.props.FloatProperty  ( name = "Child 2 Distance",    default = 0.000  )
    I3D_lod3                  = bpy.props.FloatProperty  ( name = "Child 3 Distance",    default = 0.000  )
    
    @classmethod
    def register( cls ):
        ''' Attach  PropertyGroup to All Scenes '''
        bpy.types.Scene.I3D_attributes = bpy.props.PointerProperty(
            name = "I3D Attributes Settings",
            type =  cls,
            description = "I3D Attributes Settings"
        )
        ''' Attach  PropertyGroup to All Objects '''
        bpy.types.Object.I3D_attributes = bpy.props.PointerProperty(
            name = "I3D Attributes Settings",
            type =  cls,
            description = "I3D Attributes Settings"
        )

    @classmethod
    def unregister( cls ):
        if bpy.context.scene.get( 'I3D_attributes' ):  del bpy.context.scene[ 'I3D_attributes' ]
        try:    
            del bpy.types.Scene.I3D_attributes
            del bpy.types.Object.I3D_attributes
        except: pass
#-------------------------------------------------------------------------------
#   Register
#-------------------------------------------------------------------------------
def register():
    global i3d_node
    i3d_node = I3D_Node()
    # Register I3D_UIexportSettings I3D_export PropertyGroups
    bpy.utils.register_class( I3D_export )
    bpy.utils.register_class( I3D_attributes )
    bpy.utils.register_class( I3D_UIexportSettings )
    # --------------------------------------------------------------------------
    bpy.utils.register_class( I3D_MenuExport )
    # --------------------------------------------------------------------------
    bpy.utils.register_class( I3D_FileExport )
    bpy.types.INFO_MT_file_export.append( fileExportMenuItem )

def unregister():
    global i3d_node
    del i3d_node
    bpy.utils.unregister_class( I3D_MenuExport )
    # UNRegister I3D_UIexportSettings I3D_export PropertyGroups
    bpy.utils.unregister_class( I3D_UIexportSettings )
    bpy.utils.unregister_class( I3D_attributes )
    # --------------------------------------------------------------------------
    bpy.utils.unregister_class( I3D_export )
    # --------------------------------------------------------------------------
    try:
        bpy.utils.unregister_class( I3D_PanelExport )
        bpy.utils.unregister_class( I3D_PanelExport_ButtonClose )
        bpy.utils.unregister_class( I3D_PanelExport_ButtonExport )
        bpy.utils.unregister_class( I3D_PanelExport_ButtonAttr )
    except:
        pass
    # --------------------------------------------------------------------------
    bpy.utils.unregister_class( I3D_FileExport )
    bpy.types.INFO_MT_file_export.remove( fileExportMenuItem )

if __name__ == "__main__":
    register()
#-------------------------------------------------------------------------------