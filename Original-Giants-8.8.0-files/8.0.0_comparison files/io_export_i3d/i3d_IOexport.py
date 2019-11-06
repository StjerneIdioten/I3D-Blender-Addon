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

# TODO: IK, Animations, Skin Weights

import bpy, bmesh
import time, inspect
import math, mathutils
import xml.etree.cElementTree as xml_ET

BLENDER_CHECK_VERSION01 = ( 2, 70, 0 )

class I3D_IOexport( object ):
    def __init__( self ):
        self._i3d_exportIK                  = bpy.context.scene.I3D_export.I3D_exportIK
        self._i3d_exportAnimation           = bpy.context.scene.I3D_export.I3D_exportAnimation
        self._i3d_exportShapes              = bpy.context.scene.I3D_export.I3D_exportShapes
        self._i3d_exportNurbsCurves         = bpy.context.scene.I3D_export.I3D_exportNurbsCurves
        self._i3d_exportLights              = bpy.context.scene.I3D_export.I3D_exportLights
        self._i3d_exportCameras             = bpy.context.scene.I3D_export.I3D_exportCameras
        self._i3d_exportParticleSystems     = bpy.context.scene.I3D_export.I3D_exportParticleSystems
        self._i3d_exportUserAttributes      = bpy.context.scene.I3D_export.I3D_exportUserAttributes
        self._i3d_exportNormals             = bpy.context.scene.I3D_export.I3D_exportNormals
        self._i3d_exportColors              = bpy.context.scene.I3D_export.I3D_exportColors
        self._i3d_exportTexCoords           = bpy.context.scene.I3D_export.I3D_exportTexCoords
        self._i3d_exportSkinWeigths         = bpy.context.scene.I3D_export.I3D_exportSkinWeigths
        self._i3d_exportVerbose             = bpy.context.scene.I3D_export.I3D_exportVerbose
        self._i3d_exportRelativePaths       = bpy.context.scene.I3D_export.I3D_exportRelativePaths
        self._i3d_exportApplyModifiers      = bpy.context.scene.I3D_export.I3D_exportApplyModifiers
        self._I3D_exportAxisOrientations    = bpy.context.scene.I3D_export.I3D_exportAxisOrientations
        self._i3d_exportUseBlenderFileName  = bpy.context.scene.I3D_export.I3D_exportUseBlenderFileName
        self._i3d_exportFileLocation        = bpy.context.scene.I3D_export.I3D_exportFileLocation

        self._fileID        = 0
        self._nodeID        = 0
        self._shapeID       = 0
        self._dynamicsID    = 0

        self._objectsExportSelected     = False
        self._objectsToExportDict       = {}    # KEY: reference to 'bpy.types.Object' VALUE: nodeID
        self._filesToExportDict         = {}    # KEY: reference to 'bpy.types.ImageTexture' VALUE: fileID
        self._filesToExportCustomDict   = {}    # KEY: ( m_custom_shader, m_mat[ m_custom_shader ] ) or ( m_texture, m_mat[ m_texture ] ) VALUE: ( fileID, colorProfile or None )
        self._materialsToExportDict     = {}    # KEY: reference to 'bpy.types.Material' VALUE: fileID
        self._materialNone              = None  # if ( not None ) VALUE: fileID
        self._shapesMeshToExportDict    = {}    # KEY: reference to 'bpy_types.Mesh' VALUE: ( shapeID, reference to 'bpy.types.Object', string MaterialIDs )
        self._shapesCurveToExportDict   = {}    # KEY: reference to 'bpy.types.Curve' VALUE: shapeID
        self._dynamicsToExportDict      = {}    # KEY: reference to 'bpy.types.Object' VALUE: ( nodeID, dynamicsID, reference to 'bpy.types.ParticleSystemModifier' )

    def exportAll( self ):
        self._objectsExportSelected     = False
        self.export()

    def exportSelected( self ):
        self._objectsExportSelected     = True
        self.export()

    def export( self ):
        m_start_time = time.time()
        self._makeObjectsToExportDict()
        self._makeFilesToExportDict()
        self._makeMaterialsToExportDict()
        self._makeShapesToExportDicts()
        self._makeDynamicsToExportDict()
        self._xmlBuild()
        m_end_time = time.time()
        print( "Export time is %g seconds" % ( m_end_time - m_start_time ) )

    def __str__( self ):
        m_return = '----------------------------------------------\n'
        for m_obj, m_id      in self._objectsToExportDict.items():
            m_return += '%s == %s\n' %( m_obj,     m_id )
        for m_texture, m_id  in self._filesToExportDict.items():
            m_return += '%s == %s\n' %( m_texture, m_id )
        for m_mat, m_id      in self._materialsToExportDict.items():
            m_return += '%s == %s\n' %( m_mat,     m_id )
        return m_return

    def _makeObjectsToExportDict( self ):
        if self._objectsExportSelected:
            for m_obj in bpy.context.selected_objects:
                # ignore unHandeled objects
                self._nodeID += 1
                self._objectsToExportDict[ m_obj ] = self._nodeID
                # add all parent objects to the export list
                self._addAllParentsToObjectsToExportDict( m_obj )
        else:
            for m_obj in bpy.context.scene.objects:
                self._nodeID += 1
                self._objectsToExportDict[ m_obj ] = self._nodeID

    def _makeFilesToExportDict( self ):
        for m_obj in self._objectsToExportDict.keys():
            self._checkObjectFiles( m_obj )

    def _makeMaterialsToExportDict( self ):
        for m_obj in self._objectsToExportDict.keys():
            self._checkObjectMaterials( m_obj )

    def _makeShapesToExportDicts( self ):
        for m_obj in self._objectsToExportDict.keys():
            if ( "MESH" == m_obj.type and ( m_obj.data not in self._shapesMeshToExportDict ) ):
                self._shapeID += 1
                self._shapesMeshToExportDict[ m_obj.data ] = ( self._shapeID, m_obj, '' )
            if ( "CURVE" == m_obj.type and ( m_obj.data not in self._shapesCurveToExportDict ) ):
                self._shapeID += 1
                self._shapesCurveToExportDict[ m_obj.data ] = self._shapeID

    def _makeDynamicsToExportDict( self ):
        for m_obj in self._objectsToExportDict.keys():
            if ( "MESH" == m_obj.type and ( m_obj not in self._dynamicsToExportDict ) ):
                m_modifier = self._isObjectHasParticleSystem( m_obj )
                if ( m_modifier ):
                    self._dynamicsID    += 1
                    self._nodeID        += 1
                    self._dynamicsToExportDict[ m_obj ] = ( self._nodeID, self._dynamicsID, m_modifier )
    #
    #  =====================================================================================
    #
    def _xmlWriteFiles( self ):
        # general section
        for m_file, m_id in self._filesToExportDict.items():
            self._xml_files_item = xml_ET.SubElement( self._xml_files, "File" )
            self._xml_files_item.set( "fileId", "%d" %m_id )
            if self._i3d_exportRelativePaths:
                self._xml_files_item.set( "filename", m_file.image.filepath )
                self._xml_files_item.set( "relativePath", "true" )
            else:
                self._xml_files_item.set( "filename", bpy.path.abspath( m_file.image.filepath ) )
                self._xml_files_item.set( "relativePath", "false" )
        # custom data section
        for m_key, m_id in self._filesToExportCustomDict.items():
            self._xml_files_item = xml_ET.SubElement( self._xml_files, "File" )
            self._xml_files_item.set( "fileId", "%d" %m_id[0] )
            self._xml_files_item.set( "filename", m_key[1] )
            self._xml_files_item.set( "relativePath", "true" )
            if ( m_id[1] ):
                self._xml_files_item.set( "colorProfile", "%s" %m_id[1] )
    #
    #  =====================================================================================
    #
    def _xmlWriteMaterials( self ):
        for m_mat in self._materialsToExportDict.keys():
            self._xmlWriteMaterial( m_mat )
        if ( self._materialNone ):
            self._xml_materials_item = xml_ET.SubElement( self._xml_materials, "Material" )
            self._xml_materials_item.set( "name"         , "default" )
            self._xml_materials_item.set( "materialId"   , "%d" %self._materialNone )
            self._xml_materials_item.set( "diffuseColor" , "0.3 0.3 0.3 1"  )
            self._xml_materials_item.set( "specularColor", "0 0 0"  )
            self._xml_materials_item.set( "ambientColor" , "1 1 1"  )

    def _xmlWriteMaterial( self, m_mat ):
        # --------------------------------
        # general
        # --------------------------------
        m_textures  = self._getTexturesFromMaterial( m_mat )
        m_name      = m_mat.name
        m_id        = self._materialsToExportDict[ m_mat ]
        # --------------------------------
        # emissive
        # --------------------------------
        m_emission_use = m_mat.use_shadeless
        m_map_emission = None
        m_emission_color = m_mat.diffuse_color
        if ( "map_emission" in m_textures ):
            m_map_emission = m_textures["map_emission"]
        # --------------------------------
        # diffuse
        # --------------------------------
        m_map_diffuse = None
        m_diffuse_color = m_mat.diffuse_color
        if ( "map_diffuse" in m_textures ):
            m_map_diffuse = m_textures["map_diffuse"]
        # --------------------------------
        # specular
        # --------------------------------
        m_cosPower = m_mat.specular_hardness
        m_map_specular = None
        m_specular_color = m_mat.specular_color
        if ( "map_specular" in  m_textures ):
            m_map_specular = m_textures["map_specular"]
        # --------------------------------
        # normal
        # --------------------------------
        m_map_normal = None
        if ( "map_normal" in m_textures ):
            m_map_normal = m_textures["map_normal"]
        # --------------------------------
        # reflection
        # --------------------------------
        m_reflection_use    = m_mat.raytrace_mirror.use
        m_map_reflection    = None
        m_refractive_index  = m_mat.raytrace_mirror.fresnel
        if ( "map_reflection" in m_textures ):
            m_map_reflection = m_textures["map_reflection"]
        # --------------------------------
        # refraction and alpha_blending
        # --------------------------------
        m_alpha_blending = m_mat.use_transparency
        m_refraction_use = False
        m_coeff = m_mat.raytrace_transparency.ior
        if ( m_mat.use_transparency and ( "RAYTRACE" == m_mat.transparency_method ) ):
            m_alpha_blending = False
            m_refraction_use = True
        # --------------------------------
        # custom data
        # --------------------------------
        m_custom_shader, m_custom_shader_variation, m_custom_texture, m_custom_texture_wrap, m_custom_texture_colorProfile, m_custom_parameter = self._checkMaterialCustomData ( m_mat )
        # --------------------------------
        # write to xml
        # --------------------------------
        self._xml_materials_item = xml_ET.SubElement( self._xml_materials, "Material" )
        self._xml_materials_item.set( "name", m_name )
        self._xml_materials_item.set( "materialId", "%d" %m_id )
        # --------------------------------
        self._xml_materials_item.set( "ambientColor", "1 1 1" )
        # --------------------------------
        if ( m_emission_use ):
            if ( m_map_emission ):
                self._xml_materials_item_texture = xml_ET.SubElement( self._xml_materials_item, "Emissivemap" )
                self._xml_materials_item_texture.set( "fileId", "%d" %self._filesToExportDict[ m_map_emission ] )
                if ( not self._isTextureWrapped( m_map_emission ) ): self._xml_materials_item_texture.set( "wrap", "false" )
            else:
                self._xml_materials_item.set( "emissiveColor", "%.6f %.6f %.6f 1" %( m_emission_color.r, m_emission_color.g, m_emission_color.b ) )
        else:
            if ( m_map_diffuse ):
                self._xml_materials_item_texture = xml_ET.SubElement( self._xml_materials_item, "Texture" )
                self._xml_materials_item_texture.set( "fileId", "%d" %self._filesToExportDict[ m_map_diffuse ] )
                if ( not self._isTextureWrapped( m_map_diffuse ) ): self._xml_materials_item_texture.set( "wrap", "false" )
            else:
                self._xml_materials_item.set( "diffuseColor", "%.6f %.6f %.6f 1" %( m_diffuse_color.r, m_diffuse_color.g, m_diffuse_color.b ) )
        # --------------------------------
        self._xml_materials_item.set( "cosPower", "%i" %m_cosPower )
        if ( m_map_specular ):
            self._xml_materials_item_texture = xml_ET.SubElement( self._xml_materials_item, "Glossmap" )
            self._xml_materials_item_texture.set( "fileId", "%d" %self._filesToExportDict[ m_map_specular ] )
            if ( not self._isTextureWrapped( m_map_specular ) ): self._xml_materials_item_texture.set( "wrap", "false" )
            self._xml_materials_item.set( "specularColor", "1 1 1" )
        else:
            self._xml_materials_item.set( "specularColor", "%.6f %.6f %.6f" %( m_specular_color.r, m_specular_color.g, m_specular_color.b ) )
        # --------------------------------
        if ( m_map_normal ):
            self._xml_materials_item_texture = xml_ET.SubElement( self._xml_materials_item, "Normalmap" )
            self._xml_materials_item_texture.set( "fileId", "%d" %self._filesToExportDict[ m_map_normal ] )
            if ( not self._isTextureWrapped( m_map_normal ) ): self._xml_materials_item_texture.set( "wrap", "false" )
        # --------------------------------
        if ( m_reflection_use ):
            self._xml_materials_item_texture = xml_ET.SubElement( self._xml_materials_item, "Reflectionmap" )
            if ( m_map_reflection ):
                self._xml_materials_item_texture.set( "fileId", "%d" %self._filesToExportDict[ m_map_reflection ] )
                self._xml_materials_item_texture.set( "type", "cube" )
                self._xml_materials_item_texture.set( "wrap", "false" )
            else:
                self._xml_materials_item_texture.set( "type", "planar" )
            self._xml_materials_item_texture.set( "refractiveIndex", "%s" %m_refractive_index )
            self._xml_materials_item_texture.set( "bumpScale", "0.1" )
        # --------------------------------
        if ( m_refraction_use ):
            self._xml_materials_item_texture = xml_ET.SubElement( self._xml_materials_item, "Refractionmap" )
            self._xml_materials_item_texture.set( "type", "planar" )
            self._xml_materials_item_texture.set( "coeff", "%s" %m_coeff )
            self._xml_materials_item_texture.set( "bumpScale", "0.1" )
        # --------------------------------
        if ( m_alpha_blending ):
            self._xml_materials_item.set( "alphaBlending", "true" )
        # --------------------------------
        if m_custom_shader:
            m_key = ( m_custom_shader, m_mat[ m_custom_shader ] )
            self._xml_materials_item.set( "customShaderId", "%s" %self._filesToExportCustomDict[ m_key ][0] )
        if m_custom_shader_variation:
            self._xml_materials_item.set( "customShaderVariation", "%s" %m_mat[ m_custom_shader_variation ] )
        
        if ( len( m_custom_texture ) ):
            for m_texture in m_custom_texture:
                m_key           = ( m_texture, m_mat[ m_texture ] )
                m_textureName   = m_texture.split("_")[1]
                self._xml_materials_item_texture = xml_ET.SubElement( self._xml_materials_item, "Custommap" )
                self._xml_materials_item_texture.set( "name",   "%s" %m_textureName )
                self._xml_materials_item_texture.set( "fileId", "%s" %self._filesToExportCustomDict[ m_key ][0] )
                
                if ( len( m_custom_texture_wrap ) ):
                    for m_textureWrap in m_custom_texture_wrap:
                        m_textureWrapName  = m_textureWrap.split("_")[1]
                        m_textureWrapValue = m_mat[ m_textureWrap ]
                        if (  ( m_textureName == m_textureWrapName ) and
                              ( ("false" == m_textureWrapValue ) or ("true" == m_textureWrapValue ) ) ):
                            self._xml_materials_item_texture.set( "wrap", m_textureWrapValue )
                
        if ( len( m_custom_parameter ) ):
            for m_parameter in m_custom_parameter:
                self._xml_materials_item_texture = xml_ET.SubElement( self._xml_materials_item, "CustomParameter" )
                self._xml_materials_item_texture.set( "name",   "%s" %m_parameter.split("_")[1] )
                self._xml_materials_item_texture.set( "value",  "%s" %m_mat[ m_parameter ] )
    #
    #  =====================================================================================
    #
    def _xmlWriteScene( self ):
        m_objectsSortedList = []

        for m_obj in self._objectsToExportDict.keys():
            if ( None ==  m_obj.parent ):
                m_objectsSortedList.append( m_obj.name )

        m_objectsSortedList.sort()
        # --------------------------------
        # sort before exporting
        for m_objName in m_objectsSortedList:
            m_obj = bpy.data.objects[ m_objName ]
            self._xmlWriteSceneObject( m_obj, self._xml_scene )

    def _xmlWriteSceneObject_Dynamic( self, m_obj, m_xmlCurrent ):
        m_mesh                    = m_obj.data
        m_emitterShapeNodeID      = self._objectsToExportDict[ m_obj ]
        m_nodeID                  = self._dynamicsToExportDict[ m_obj ][0]
        m_dynamicID               = self._dynamicsToExportDict[ m_obj ][1]
        m_particleSystemModifier  = self._dynamicsToExportDict[ m_obj ][2]
        m_dynamicName             = m_particleSystemModifier.name
        m_shapeName               = m_obj.name
        m_nonRenderable           = m_obj.I3D_attributes.I3D_nonRenderable
        m_castsShadows            = m_obj.I3D_attributes.I3D_castsShadows
        m_receiveShadows          = m_obj.I3D_attributes.I3D_receiveShadows
        m_shapeID                 = self._shapesMeshToExportDict[ m_mesh ][0]
        m_materialIDs             = self._shapesMeshToExportDict[ m_mesh ][2]

        m_translation, m_rotation, m_scale = self._getTranslationRotationScale( m_obj )

        m_xmlCurrent.set( "name"                , m_dynamicName  )
        m_xmlCurrent.set( "nodeId"              , "%d" %m_nodeID )
        m_xmlCurrent.set( "materialIds"         , m_materialIDs  )
        m_xmlCurrent.set( "dynamicId"           , "%d" %m_dynamicID  )
        m_xmlCurrent.set( "emitterShapeNodeId"  , "%d" %m_emitterShapeNodeID )
        if ( m_castsShadows ):   m_xmlCurrent.set( "castsShadows"    , "true" )
        else:                    m_xmlCurrent.set( "castsShadows"    , "false" )
        if ( m_receiveShadows ): m_xmlCurrent.set( "receiveShadows"  , "true" )
        else:                    m_xmlCurrent.set( "receiveShadows"  , "false" )
        if ( m_nonRenderable ):  m_xmlCurrent.set( "nonRenderable" , "true" )
        m_xmlCurrent_child        = xml_ET.SubElement( m_xmlCurrent, "Shape" )
        m_xmlCurrent_child.set( "name"           , m_shapeName )
        m_xmlCurrent_child.set( "nodeId"         , "%d" %m_emitterShapeNodeID )
        m_xmlCurrent_child.set( "shapeId"        , "%d" %m_shapeID )
        m_xmlCurrent_child.set( "materialIds"    , m_materialIDs  )
        m_xmlCurrent_child.set( "nonRenderable"  , "true" )
        m_xmlCurrent_child.set( "castsShadows"   , "false" )
        m_xmlCurrent_child.set( "receiveShadows" , "false" )

        self._xmlWriteVisClipObjmaskLightmask( m_obj, m_xmlCurrent )
        m_xmlCurrent.set( "translation",  m_translation )
        m_xmlCurrent_child.set( "rotation",     m_rotation )
        m_xmlCurrent_child.set( "scale",        m_scale )

    def _xmlWriteSceneObject_ShapeCurve( self, m_obj, m_xmlCurrent ):
        m_curve         = m_obj.data
        m_curveID       = self._shapesCurveToExportDict[ m_curve ]
        m_xmlCurrent.set( "shapeId" , "%d" %m_curveID )

    def _xmlWriteSceneObject_ShapeMesh( self, m_obj, m_xmlCurrent ):
        # TODO skinBindNodes, skinBindNodeIds
        m_mesh                  = m_obj.data
        m_shapeID               = self._shapesMeshToExportDict[ m_mesh ][0]
        m_materialIDs           = self._shapesMeshToExportDict[ m_mesh ][2]
        m_nonRenderable         = m_obj.I3D_attributes.I3D_nonRenderable
        m_castsShadows          = m_obj.I3D_attributes.I3D_castsShadows
        m_receiveShadows        = m_obj.I3D_attributes.I3D_receiveShadows
        m_rigidBody             = False
        m_static                = m_obj.I3D_attributes.I3D_static
        m_kinematic             = m_obj.I3D_attributes.I3D_kinematic
        m_dynamic               = m_obj.I3D_attributes.I3D_dynamic
        m_compound              = m_obj.I3D_attributes.I3D_compound
        m_compoundChild         = m_obj.I3D_attributes.I3D_compoundChild
        m_collision             = m_obj.I3D_attributes.I3D_collision
        m_collisionMask         = None
        m_trigger               = m_obj.I3D_attributes.I3D_trigger
        m_restitution           = None
        m_staticFriction        = None
        m_dynamicFriction       = None
        m_linearDamping         = None
        m_angularDamping        = None
        m_skinWidth             = None
        m_density               = None
        m_solverIterationCount  = None
        # Continues Collision Detection
        m_ccd                   = m_obj.I3D_attributes.I3D_ccd

        if   ( m_static ):
            m_rigidBody = True
            m_kinematic = False
            m_dynamic   = False
        elif ( m_dynamic ):
            m_rigidBody = True
            m_kinematic = False
        elif ( m_kinematic ):
            m_rigidBody = True
        if ( not m_rigidBody ):
            m_compound  = False
        if ( m_compound )       : m_compoundChild = False
        if ( m_compoundChild )  : m_rigidBody = True
        if ( 255 != m_obj.I3D_attributes.I3D_collisionMask ): m_collisionMask  = m_obj.I3D_attributes.I3D_collisionMask
        if ( m_rigidBody ):
            if ( 0.0  != m_obj.I3D_attributes.I3D_restitution  )        : m_restitution           = m_obj.I3D_attributes.I3D_restitution
            if ( 0.5  != m_obj.I3D_attributes.I3D_staticFriction  )     : m_staticFriction        = m_obj.I3D_attributes.I3D_staticFriction
            if ( 0.5  != m_obj.I3D_attributes.I3D_dynamicFriction )     : m_dynamicFriction       = m_obj.I3D_attributes.I3D_dynamicFriction
            if ( 0.5  != m_obj.I3D_attributes.I3D_linearDamping   )     : m_linearDamping         = m_obj.I3D_attributes.I3D_linearDamping
            if ( 0.5  != m_obj.I3D_attributes.I3D_angularDamping  )     : m_angularDamping        = m_obj.I3D_attributes.I3D_angularDamping
            if ( 0.05 != m_obj.I3D_attributes.I3D_skinWidth )           : m_skinWidth             = m_obj.I3D_attributes.I3D_skinWidth
            if ( 1    != m_obj.I3D_attributes.I3D_density )             : m_density               = m_obj.I3D_attributes.I3D_density
            if ( 4    != m_obj.I3D_attributes.I3D_solverIterationCount ): m_solverIterationCount  = m_obj.I3D_attributes.I3D_solverIterationCount
        m_xmlCurrent.set( "shapeId"        , "%d" %m_shapeID )
        m_xmlCurrent.set( "materialIds"    , m_materialIDs )
        if ( m_static )        : m_xmlCurrent.set( "static"         , "true" )
        if ( m_dynamic )       : m_xmlCurrent.set( "dynamic"        , "true" )
        if ( m_kinematic )     : m_xmlCurrent.set( "kinematic"      , "true" )
        if ( m_compound )      : m_xmlCurrent.set( "compound"       , "true" )
        if ( m_compoundChild ) : m_xmlCurrent.set( "compoundChild"  , "true" )
        if ( not m_collision ) : m_xmlCurrent.set( "collision"      , "false" )
        if ( m_trigger )       : m_xmlCurrent.set( "trigger"        , "true" )
        if ( m_collisionMask ) : m_xmlCurrent.set( "collisionMask"  , "%s" %m_collisionMask )
        if ( m_restitution )            : m_xmlCurrent.set( "restitution"           , "%s" %m_restitution )
        if ( m_staticFriction )         : m_xmlCurrent.set( "staticFriction"        , "%s" %m_staticFriction )
        if ( m_dynamicFriction )        : m_xmlCurrent.set( "dynamicFriction"       , "%s" %m_dynamicFriction )
        if ( m_linearDamping )          : m_xmlCurrent.set( "linearDamping"         , "%s" %m_linearDamping )
        if ( m_angularDamping )         : m_xmlCurrent.set( "angularDamping"        , "%s" %m_angularDamping )
        if ( m_skinWidth )              : m_xmlCurrent.set( "skinWidth"             , "%s" %m_skinWidth )
        if ( m_density )                : m_xmlCurrent.set( "density"               , "%s" %m_density )
        if ( m_solverIterationCount )   : m_xmlCurrent.set( "solverIterationCount"  , "%s" %m_solverIterationCount )
        if ( m_rigidBody and m_ccd )    : m_xmlCurrent.set( "ccd"                   , "true" )
        self._xmlWriteBool( m_xmlCurrent, "castsShadows"   , m_castsShadows )
        self._xmlWriteBool( m_xmlCurrent, "receiveShadows" , m_receiveShadows )
        if ( m_nonRenderable ) : m_xmlCurrent.set( "nonRenderable"  , "true" )

    def _xmlWriteSceneObject_Light( self, m_obj, m_xmlCurrent ):
        m_type          = None
        m_diffuseColor  = None
        m_specularColor = None
        m_emitDiffuse   = None
        m_emitSpecular  = None
        m_range         = None
        m_decayRate     = None
        m_coneAngle     = None
        m_dropOff       = None
        m_castShadowMap = None
        if ( "POINT" == m_obj.data.type ): m_type = "point"
        if ( "SUN"   == m_obj.data.type ):
            m_type      = "directional"
            m_decayRate = "0"
        if ( "SPOT"  == m_obj.data.type ):
            m_type      = "spot"
            m_coneAngle = "%.3f" %math.degrees( m_obj.data.spot_size )
            m_dropOff   = "%.3f" %( 5*m_obj.data.spot_blend )
        if ( ( "POINT" == m_obj.data.type ) or ( "SPOT"   == m_obj.data.type ) ):
            if   ( "INVERSE_LINEAR" == m_obj.data.falloff_type ): m_decayRate = "1"
            elif ( "INVERSE_SQUARE" == m_obj.data.falloff_type ): m_decayRate = "2"
            m_decayRate = "0"
        m_diffuseColor  = "%.3f %.3f %.3f" %m_obj.data.color[:]
        m_specularColor = "%.3f %.3f %.3f" %m_obj.data.color[:]
        if ( m_obj.data.use_diffuse )  :    m_emitDiffuse  = "true"
        else:                               m_emitDiffuse  = "false"
        if ( m_obj.data.use_specular ) :    m_emitSpecular = "true"
        else:                               m_emitSpecular = "false"
        if ( "NOSHADOW" != m_obj.data.shadow_method ):
            m_castShadowMap = "true"
        m_range = "%.3f" %m_obj.data.distance
        m_xmlCurrent.set( "type" , m_type )
        m_xmlCurrent.set( "diffuseColor"  , m_diffuseColor )
        m_xmlCurrent.set( "specularColor" , m_specularColor )
        m_xmlCurrent.set( "emitDiffuse"   , m_emitDiffuse )
        m_xmlCurrent.set( "emitSpecular"  , m_emitSpecular )
        m_xmlCurrent.set( "decayRate"     , m_decayRate )
        m_xmlCurrent.set( "range"         , m_range )
        if ( m_castShadowMap ):
            m_xmlCurrent.set( "castShadowMap" , m_castShadowMap )
            if ( "directional" == m_type ):
                m_xmlCurrent.set( "depthMapBias"                        , "0.0012"  )
                m_xmlCurrent.set( "depthMapSlopeScaleBias"              , "2"       )
                m_xmlCurrent.set( "depthMapSlopeClamp"                  , "0.0005"  )
                m_xmlCurrent.set( "depthMapResolution"                  , "2048"    )
                m_xmlCurrent.set( "shadowFarDistance"                   , "80"      )
                m_xmlCurrent.set( "shadowExtrusionDistance"             , "200"     )
                m_xmlCurrent.set( "shadowPerspective"                   , "false"   )
                m_xmlCurrent.set( "numShadowMapSplits"                  , "3"       )
                m_xmlCurrent.set( "shadowMapSplitDistancesParameter"    , "0.4"     )
        if ( "spot" == m_type ):
            m_xmlCurrent.set( "coneAngle"     , m_coneAngle )
            m_xmlCurrent.set( "dropOff"       , m_dropOff )

    def _xmlWriteSceneObject_Camera( self, m_obj, m_xmlCurrent ):
        m_fov      = None
        m_nearClip = None
        m_farClip  = None
        m_fov      = "%.2f" %m_obj.data.lens
        m_nearClip = "%.2f" %m_obj.data.clip_start
        m_farClip  = "%.2f" %m_obj.data.clip_end
        m_xmlCurrent.set( "fov"     , m_fov )
        m_xmlCurrent.set( "nearClip", m_nearClip )
        m_xmlCurrent.set( "farClip" , m_farClip )

    def _xmlWriteSceneObject_TransformGroup( self, m_obj, m_xmlCurrent ):
        m_lodDistance       = None

        m_joint             = m_obj.I3D_attributes.I3D_joint
        m_projection        = m_obj.I3D_attributes.I3D_projection
        m_projDistance      = None
        m_projAngle         = None
        m_xAxisDrive        = m_obj.I3D_attributes.I3D_xAxisDrive
        m_yAxisDrive        = m_obj.I3D_attributes.I3D_yAxisDrive
        m_zAxisDrive        = m_obj.I3D_attributes.I3D_zAxisDrive
        m_drivePos          = m_obj.I3D_attributes.I3D_drivePos
        m_driveForceLimit   = None
        m_driveSpring       = None
        m_driveDamping      = None
        m_breakableJoint    = m_obj.I3D_attributes.I3D_breakableJoint
        m_jointBreakForce   = None
        m_jointBreakTorque  = None

        if ( m_obj.I3D_attributes.I3D_lod ):
            if ( m_obj.I3D_attributes.I3D_lod1 ):
                m_lodDistance = "0 %s" %m_obj.I3D_attributes.I3D_lod1
                if ( m_obj.I3D_attributes.I3D_lod2 > m_obj.I3D_attributes.I3D_lod1 ):
                    m_lodDistance += " %s" %m_obj.I3D_attributes.I3D_lod2
                    if( m_obj.I3D_attributes.I3D_lod3 > m_obj.I3D_attributes.I3D_lod2 ):
                        m_lodDistance += " %s" %m_obj.I3D_attributes.I3D_lod3
        if ( m_lodDistance ): m_xmlCurrent.set( "lodDistance", m_lodDistance )

        if ( m_lodDistance ): m_joint = None
        if ( 0.010    != m_obj.I3D_attributes.I3D_projDistance  )      : m_projDistance      = m_obj.I3D_attributes.I3D_projDistance
        if ( 0.010    != m_obj.I3D_attributes.I3D_projAngle  )         : m_projAngle         = m_obj.I3D_attributes.I3D_projAngle
        if ( 100000.0 != m_obj.I3D_attributes.I3D_driveForceLimit  )   : m_driveForceLimit   = m_obj.I3D_attributes.I3D_driveForceLimit
        if ( 1.000    != m_obj.I3D_attributes.I3D_driveSpring  )       : m_driveSpring       = m_obj.I3D_attributes.I3D_driveSpring
        if ( 0.010    != m_obj.I3D_attributes.I3D_driveDamping  )      : m_driveDamping      = m_obj.I3D_attributes.I3D_driveDamping
        if ( 0.000    != m_obj.I3D_attributes.I3D_jointBreakForce  )   : m_jointBreakForce   = m_obj.I3D_attributes.I3D_jointBreakForce
        if ( 0.000    != m_obj.I3D_attributes.I3D_jointBreakTorque  )  : m_jointBreakTorque  = m_obj.I3D_attributes.I3D_jointBreakTorque
        if ( m_joint ):
            m_xmlCurrent.set( "joint", "true" )
            if ( m_projection )         :  m_xmlCurrent.set( "projection", "true" )
            if ( m_xAxisDrive )         :  m_xmlCurrent.set( "xAxisDrive", "true" )
            if ( m_yAxisDrive )         :  m_xmlCurrent.set( "yAxisDrive", "true" )
            if ( m_zAxisDrive )         :  m_xmlCurrent.set( "zAxisDrive", "true" )
            if ( m_drivePos   )         :  m_xmlCurrent.set( "drivePos"  , "true" )
            if ( m_breakableJoint )     :  m_xmlCurrent.set( "breakableJoint"   , "true" )
            if ( m_projDistance )       :  m_xmlCurrent.set( "projDistance"     , "%s" %m_projDistance )
            if ( m_projAngle )          :  m_xmlCurrent.set( "projAngle"        , "%s" %m_projAngle )
            if ( m_driveForceLimit )    :  m_xmlCurrent.set( "driveForceLimit"  , "%s" %m_driveForceLimit )
            if ( m_driveSpring )        :  m_xmlCurrent.set( "driveSpring"      , "%s" %m_driveSpring )
            if ( m_driveDamping )       :  m_xmlCurrent.set( "driveDamping"     , "%s" %m_driveDamping )
            if ( m_jointBreakForce )    :  m_xmlCurrent.set( "jointBreakForce"  , "%s" %m_jointBreakForce )
            if ( m_jointBreakTorque )   :  m_xmlCurrent.set( "jointBreakTorque" , "%s" %m_jointBreakTorque )

    def _xmlWriteSceneObject_General( self, m_obj, m_xmlCurrent ):
        m_name        = m_obj.name
        m_nodeID      = self._objectsToExportDict[ m_obj ]
        m_translation, m_rotation, m_scale = self._getTranslationRotationScale( m_obj )

        self._xmlWriteVisClipObjmaskLightmask( m_obj, m_xmlCurrent )
        m_xmlCurrent.set( "name", m_name )
        m_xmlCurrent.set( "nodeId", "%d"  %m_nodeID )
        m_xmlCurrent.set( "translation",  m_translation )
        m_xmlCurrent.set( "rotation",     m_rotation )
        m_xmlCurrent.set( "scale",        m_scale )

    @staticmethod
    def _xmlWriteVisClipObjmaskLightmask( m_obj, m_xmlCurrent ):
        m_visibility   = m_obj.hide
        m_clipDistance = m_obj.I3D_attributes.I3D_clipDistance
        m_objectMask   = None
        m_lightMask    = None
        m_decalLayer   = m_obj.I3D_attributes.I3D_decalLayer
        if ( 255    != m_obj.I3D_attributes.I3D_objectMask ): m_objectMask = m_obj.I3D_attributes.I3D_objectMask
        if ( "FFFF" != m_obj.I3D_attributes.I3D_lightMask  ): m_lightMask  = int( m_obj.I3D_attributes.I3D_lightMask, 16 )
        if ( m_visibility )   : m_xmlCurrent.set( "visibility", "false" )
        if ( m_clipDistance ) : m_xmlCurrent.set( "clipDistance", "%s" %m_clipDistance )
        if ( m_objectMask )   : m_xmlCurrent.set( "objectMask"  , "%s" %m_objectMask )
        if ( m_lightMask )    : m_xmlCurrent.set( "lightMask"   , "%s" %m_lightMask )
        if ( m_decalLayer )   : m_xmlCurrent.set( "decalLayer"  , "%s" %m_decalLayer )

    def _getTranslationRotationScale( self, m_obj ):
        m_orient = self._I3D_exportAxisOrientations

        if ( "BAKE_TRANSFORMS"  == m_orient ):
            # transform matrix Blender -> OpenGL
            m_matrix = mathutils.Matrix.Rotation( math.radians( -90 ), 4, "X" ) * m_obj.matrix_local * mathutils.Matrix.Rotation( math.radians( 90 ), 4, "X" )

            if ( "CAMERA"  ==  m_obj.type or "LAMP"  ==  m_obj.type ):
                m_matrix = m_matrix * mathutils.Matrix.Rotation( math.radians( -90 ), 4, "X" )
            if ( m_obj.parent ):
                if ( "CAMERA"  ==  m_obj.parent.type or "LAMP"  ==  m_obj.parent.type ):
                    m_matrix = mathutils.Matrix.Rotation( math.radians( 90 ), 4, "X" ) * m_matrix
        else:
            if ( "KEEP_AXIS"  == m_orient ):
                if ( m_obj.parent ):
                    m_matrix = m_obj.matrix_local
                else:
                    m_matrix =  mathutils.Matrix.Rotation( math.radians( -90 ), 4, "X" ) * m_obj.matrix_local
            elif ( "KEEP_TRANSFORMS"  == m_orient ):
                m_matrix        = m_obj.matrix_local

        m_translation   = m_matrix.to_translation()[:]
        m_rotation      = m_matrix.to_euler( "XYZ" )
        m_rotation      = ( math.degrees( m_rotation.x ),
                            math.degrees( m_rotation.y ),
                            math.degrees( m_rotation.z ) )
        m_scale         = m_matrix.to_scale()[:]

        m_translation  = "%.6f %.6f %.6f" %( m_translation )
        m_rotation     = "%.3f %.3f %.3f" %( m_rotation  )
        m_scale        = "%.6f %.6f %.6f" %( m_scale )
        return ( m_translation, m_rotation, m_scale )

    def _xmlWriteSceneObject( self, m_obj, m_xmlParent ):
        # CURVES ALSO BAKED
        # CAMERAS, LIGHTS, TRANSFORMS (only if they are replacement for light or cameras) - Keep Axis mode

        if ( "MESH"    ==  m_obj.type and
               ( m_obj not in self._dynamicsToExportDict ) ): m_objType = "Shape"
        if ( "MESH"    ==  m_obj.type and
               ( m_obj in self._dynamicsToExportDict ) )    : m_objType = "Dynamic"
        if ( "CURVE"   ==  m_obj.type   )       : m_objType = "Shape"
        if ( "EMPTY"   ==  m_obj.type   )       : m_objType = "TransformGroup"
        if ( "CAMERA"  ==  m_obj.type   )       : m_objType = "Camera"
        if ( "LAMP"    ==  m_obj.type   )       : m_objType = "Light"
        if ( not self._checkObject( m_obj ) )   : m_objType = "TransformGroup"
        if ( not self._i3d_exportParticleSystems and "Dynamic" ==  m_objType  ) : m_objType = "Shape"
        if ( not self._i3d_exportShapes          and "MESH"    ==  m_obj.type ) : m_objType = "TransformGroup"
        if ( not self._i3d_exportNurbsCurves     and "CURVE"   ==  m_obj.type ) : m_objType = "TransformGroup"
        if ( not self._i3d_exportCameras         and "CAMERA"  ==  m_obj.type ) : m_objType = "TransformGroup"
        if ( not self._i3d_exportLights          and "LAMP"    ==  m_obj.type ) : m_objType = "TransformGroup"

        # General
        m_xmlCurrent  = xml_ET.SubElement( m_xmlParent, m_objType )
        if ( not "Dynamic" == m_objType ):
            self._xmlWriteSceneObject_General( m_obj, m_xmlCurrent )

        # TransformGroup
        if ( "TransformGroup" == m_objType ):
            self._xmlWriteSceneObject_TransformGroup( m_obj, m_xmlCurrent )

        # Camera
        if ( "Camera" == m_objType ):
            self._xmlWriteSceneObject_Camera( m_obj, m_xmlCurrent )

        # Light
        if ( "Light" == m_objType ):
            self._xmlWriteSceneObject_Light( m_obj, m_xmlCurrent )

        #Shape Mesh
        if ( "Shape" == m_objType and "MESH" ==  m_obj.type ):
            self._xmlWriteSceneObject_ShapeMesh( m_obj, m_xmlCurrent )

        #Shape Curve
        if ( "Shape" == m_objType and "CURVE" ==  m_obj.type ):
            self._xmlWriteSceneObject_ShapeCurve( m_obj, m_xmlCurrent )

        # Dynamic
        if ( "Dynamic" == m_objType and "MESH" ==  m_obj.type ):
            self._xmlWriteSceneObject_Dynamic( m_obj, m_xmlCurrent )

        # sort before exporting
        m_objectsSortedList = []
        for m_child in m_obj.children:
            if ( m_child in self._objectsToExportDict ):
                m_objectsSortedList.append( m_child.name )
        m_objectsSortedList.sort()
        # write children
        for m_childName in m_objectsSortedList:
            m_child = bpy.data.objects[ m_childName ]
            self._xmlWriteSceneObject( m_child, m_xmlCurrent )
    #
    #  =====================================================================================
    #
    def _xmlWriteShapes( self ):
        if ( self._i3d_exportShapes ):
            for m_mesh, m_meshData in self._shapesMeshToExportDict.items():
                m_meshID     = m_meshData[0]
                m_meshOwner  = m_meshData[1]
                self._xmlWriteShape_Mesh( m_meshOwner, m_mesh, m_meshID )
        if ( self._i3d_exportNurbsCurves ):
            for m_curve in self._shapesCurveToExportDict.keys():
                self._xmlWriteShape_Curve( m_curve )

    def _xmlWriteShape_Curve( self, m_curve ):
        m_name                          = m_curve.name
        m_id                            = self._shapesCurveToExportDict[ m_curve ]
        xml_shapes_nurbsCurve           = xml_ET.SubElement( self._xml_shapes, "NurbsCurve" )
        xml_shapes_nurbsCurve.set( "name", m_name )
        xml_shapes_nurbsCurve.set( "degree", "3" )
        xml_shapes_nurbsCurve.set( "shapeId", "%d" %m_id )
        m_form   = "open"
        if ( len( m_curve.splines ) ):
            m_spline = m_curve.splines[0]
            m_points = None
            if m_spline.use_cyclic_u: m_form   = "closed"
            if ( "NURBS"  == m_spline.type ):   m_points = m_spline.points
            if ( "BEZIER" == m_spline.type ):   m_points = m_spline.bezier_points
            if ( m_points ):
                for m_point in m_points:
                    xml_shapes_nurbsCurve_item  = xml_ET.SubElement( xml_shapes_nurbsCurve,  "cv" )
                    
                    m_pointCoords  = m_point.co.xyz[:]
                    if ( "BAKE_TRANSFORMS" == self._I3D_exportAxisOrientations ): # x z -y
                        m_pointCoords = ( m_pointCoords[0], m_pointCoords[2], - m_pointCoords[1] )
                    
                    xml_shapes_nurbsCurve_item.set( "c",  "%.6f %.6f %.6f" %(m_pointCoords) )
        xml_shapes_nurbsCurve.set( "form", m_form )

    def _xmlWriteShape_Mesh( self, m_obj, m_meshSource, m_meshID ):
        m_meshGen = m_obj.to_mesh( bpy.context.scene, self._i3d_exportApplyModifiers , "PREVIEW", calc_tessface = False )
        # triangulate mesh before exporting
        self._shapeMeshTriangulate( m_meshGen, self._i3d_exportVerbose )
        if ( self._i3d_exportVerbose ):     print( "GENERATED MESH IS: %s" %m_meshGen.name )

        m_materialIDs = self._xmlWriteShape_MeshData( m_obj, m_meshGen, m_meshID )

        if ( self._i3d_exportVerbose ):     print( "GENERATED MESH %s WAS REMOVED" %m_meshGen.name )
        bpy.data.meshes.remove( m_meshGen )
        # Update self._shapesMeshToExportDict, add proper m_materialIDs
        m_meshData = self._shapesMeshToExportDict[ m_meshSource ]
        self._shapesMeshToExportDict[ m_meshSource ] = ( m_meshData[0], m_meshData[1], m_materialIDs )

    def _xmlWriteShape_MeshData( self, m_obj, m_mesh, m_meshID ):
        if ( self._i3d_exportVerbose ):
            m_start_time = time.time()
        
        m_indexBuffer = {}
        m_format = None
        if ( "BAKE_TRANSFORMS"  == self._I3D_exportAxisOrientations ):
            m_format = "baked"
        xml_shapes_indTriangleSet               = xml_ET.SubElement( self._xml_shapes, "IndexedTriangleSet" )
        m_name  = m_obj.data.name
        m_id    = m_meshID
        m_bvCenter, m_bvRadius = self._getBvCenterRadius( m_obj.data )
        
        if ( "baked" == m_format ): # x z -y
            m_bvOrig      = m_bvCenter.xyz
            m_bvCenter.x  = m_bvOrig.x
            m_bvCenter.y  = m_bvOrig.z
            m_bvCenter.z  = - m_bvOrig.y

        xml_shapes_indTriangleSet.set( "name", m_name )
        xml_shapes_indTriangleSet.set( "shapeId"      , "%d" %m_id )
        xml_shapes_indTriangleSet.set( "bvCenter"     , "%.6f %.6f %.6f" %( m_bvCenter.xyz[:] ) )
        xml_shapes_indTriangleSet.set( "bvRadius"     , "%.6f" %m_bvRadius )
        xml_shapes_indTriangleSet.set( "isOptimized"  , "false" )

        m_needTangent   = self._needCalculateTangents( m_obj )
        m_needNormal    = self._i3d_exportNormals
        m_needTexCoords = self._i3d_exportTexCoords
        m_needColors    = self._i3d_exportColors

        if ( m_needTexCoords ):
            m_uvLayersIndexes   = len( m_mesh.uv_layers )
            if ( m_uvLayersIndexes > 4 ): m_uvLayersIndexes = 4
        else:
            m_uvLayersIndexes   = 0
        
        # -------------------------------------------------------------
        # computing tangents and normals for using with loop indices
        # -------------------------------------------------------------
        if ( BLENDER_CHECK_VERSION01 <= bpy.app.version ):
            if ( m_uvLayersIndexes ):
                m_mesh.calc_tangents()
        # -------------------------------------------------------------
        
        if ( m_needColors ):
            m_vertColorsIndexes = len( m_mesh.vertex_colors )
            if ( m_vertColorsIndexes > 1 ): m_vertColorsIndexes = 1
        else:
            m_vertColorsIndexes = 0

        m_polygonsByMaterialIndex = [ [] for m_i in range( len( m_mesh.materials ) ) ]
        if ( 0 == len( m_polygonsByMaterialIndex ) ): m_polygonsByMaterialIndex.append( [] ) #object do not have materials assigned
        for m_polygon in m_mesh.polygons:
            m_polygonsByMaterialIndex[ m_polygon.material_index ].append( m_polygon.index )

        xml_shapes_indTriangleSetVertices       = xml_ET.SubElement( xml_shapes_indTriangleSet, "Vertices" )
        xml_shapes_indTriangleSetTriangles      = xml_ET.SubElement( xml_shapes_indTriangleSet, "Triangles" )
        xml_shapes_indTriangleSetSubsets        = xml_ET.SubElement( xml_shapes_indTriangleSet, "Subsets" )
        if ( m_needNormal ):
            xml_shapes_indTriangleSetVertices.set( "normal", "true" )
        if ( m_needTangent ):
            xml_shapes_indTriangleSetVertices.set( "tangent", "true" )
        if ( m_needTexCoords ):
            for m_uvlayerIndex in range( m_uvLayersIndexes ):
                xml_shapes_indTriangleSetVertices.set( "uv%d" %m_uvlayerIndex, "true" )
        if ( m_needColors and m_vertColorsIndexes ):
            xml_shapes_indTriangleSetVertices.set( "color", "true" )

        m_currentIndex          = 0
        m_currentIndexVertex    = 0
        m_firstIndex            = 0
        m_firstVertex           = 0
        m_numVerticesSet        = set()
        m_trainglesCount        = 0
        m_subsetsCount          = 0
        m_materialIDs           = ''

        m_counter = 0
        for m_matIndex, m_polygonIndices in enumerate( m_polygonsByMaterialIndex ):
            # EXPORT SECTION BY MATERIALS
            m_trainglesCount += len( m_polygonIndices )
            if ( len( m_polygonIndices ) ):

                m_subsetsCount  += 1
                m_numIndices    = 0
                m_numVerticesSet.clear()

                if ( 0 == len( m_mesh.materials ) ):
                    m_materialID = self._materialNone
                else:
                    m_materialID    = self._getIDbyMaterial( m_mesh.materials[ m_matIndex ] )
                m_materialIDs   += " %d," %m_materialID

                for m_polygonIndex in m_polygonIndices:
                    # EXPORT SECTION BY TRIANGLES
                    m_polygon            = m_mesh.polygons[ m_polygonIndex ]
                    m_polygonLoopIndices = m_polygon.loop_indices
                    m_strVI              = ''
                    for m_loopIndex in m_polygonLoopIndices:
                        #
                        # get relevant data for vertex
                        #
                        m_indexData   = IndexBufferItem( m_mesh, m_loopIndex, m_needNormal, m_uvLayersIndexes, m_vertColorsIndexes, m_format )
                        if ( m_indexData not in m_indexBuffer ):
                            m_indexBuffer[ m_indexData ] = m_counter
                            m_counter += 1
                            # save data to xml
                            xml_shapes_indTriangleSetVertices_item  = xml_ET.SubElement( xml_shapes_indTriangleSetVertices,  "v" )
                            xml_shapes_indTriangleSetVertices_item.set( "p",  "%.6f %.6f %.6f" %m_indexData.m_vertexCoords )
                            if ( m_needNormal ):
                                xml_shapes_indTriangleSetVertices_item.set( "n", "%.6f %.6f %.6f" %m_indexData.m_vertexNormals  )
                            if ( m_needTexCoords ):
                                for m_uvlayerIndex in range( len( m_indexData.m_vertexUVs )):
                                    xml_shapes_indTriangleSetVertices_item.set( "t%d" %m_uvlayerIndex, "%.6f %.6f" %m_indexData.m_vertexUVs[ m_uvlayerIndex ] )
                            if ( m_needColors ):
                                for m_vertColorIndex in range( len( m_indexData.m_vertexColors )):
                                    xml_shapes_indTriangleSetVertices_item.set( "c", "%.6f %.6f %.6f" %m_indexData.m_vertexColors[ m_vertColorIndex ] )

                        m_currentIndexVertex = m_indexBuffer[ m_indexData ]
                        m_strVI             += " %d" %m_currentIndexVertex
                        #
                        # ----------------------------
                        #
                        if ( 0 == m_numIndices ):
                            m_firstVertex = m_currentIndexVertex
                            m_firstIndex  = m_currentIndex

                        m_numVerticesSet.add( m_currentIndexVertex )
                        m_currentIndex += 1
                        m_numIndices   += 1

                    xml_shapes_indTriangleSetTriangles_item = xml_ET.SubElement( xml_shapes_indTriangleSetTriangles, "t" )
                    xml_shapes_indTriangleSetTriangles_item.set( "vi", m_strVI.strip() )

                xml_shapes_indTriangleSetSubsets_item   = xml_ET.SubElement( xml_shapes_indTriangleSetSubsets,   "Subset" )
                xml_shapes_indTriangleSetSubsets_item.set( "firstVertex", "%s" %min( m_numVerticesSet ) )
                xml_shapes_indTriangleSetSubsets_item.set( "numVertices", "%s" %( max( m_numVerticesSet ) + 1 ) )
                xml_shapes_indTriangleSetSubsets_item.set( "firstIndex" , "%s" %m_firstIndex )
                xml_shapes_indTriangleSetSubsets_item.set( "numIndices" , "%s" %m_numIndices )
        xml_shapes_indTriangleSetVertices.set ( "count", "%s" %len( m_indexBuffer ) )
        xml_shapes_indTriangleSetTriangles.set( "count", "%s" %m_trainglesCount )
        xml_shapes_indTriangleSetSubsets.set(   "count", "%s" %m_subsetsCount )

        if ( self._i3d_exportVerbose ):
            m_end_time = time.time()
            print( "    %s time is %g seconds" % ( inspect.stack()[0][3], m_end_time - m_start_time ) )

        m_materialIDs = m_materialIDs.strip()
        m_materialIDs = m_materialIDs.strip(",")
        return m_materialIDs
    #
    #  =====================================================================================
    #
    def _xmlWriteDynamics( self ):
        for m_obj in self._dynamicsToExportDict.keys():
            self._xmlWriteDynamics_ParticleSystem( m_obj )

    def _xmlWriteDynamics_ParticleSystem( self, m_obj ):
        m_nodeID                     = self._dynamicsToExportDict[ m_obj ][0]
        m_dynamicID                  = self._dynamicsToExportDict[ m_obj ][1]
        m_particleSystemModifier     = self._dynamicsToExportDict[ m_obj ][2]
        m_name                       = m_particleSystemModifier.particle_system.name
        xml_dynamics_particleSystem  = xml_ET.SubElement( self._xml_dynamics, "ParticleSystem" )
        xml_dynamics_particleSystem.set( "name", m_name )
        xml_dynamics_particleSystem.set( "dynamicId"            , "%d" %m_dynamicID )
        xml_dynamics_particleSystem.set( "type"                 , "sprite" )
        xml_dynamics_particleSystem.set( "rate"                 , "0.018" )
        xml_dynamics_particleSystem.set( "lifespan"             , "1500" )
        xml_dynamics_particleSystem.set( "maxCount"             , "50" )
        xml_dynamics_particleSystem.set( "speed"                , "0.005" )
        xml_dynamics_particleSystem.set( "speedRandom"          , "0" )
        xml_dynamics_particleSystem.set( "tangentSpeed"         , "0.1" )
        xml_dynamics_particleSystem.set( "normalSpeed"          , "1" )
        xml_dynamics_particleSystem.set( "spriteScaleX"         , "0.3" )
        xml_dynamics_particleSystem.set( "spriteScaleY"         , "0.3" )
        xml_dynamics_particleSystem.set( "blendFactor"          , "1" )
        xml_dynamics_particleSystem.set( "blendInFactor"        , "0" )
        xml_dynamics_particleSystem.set( "blendOutFactor"       , "1" )
        xml_dynamics_particleSystem.set( "randomInitRotation"   , "true" )
        xml_dynamics_particleSystem.set( "deltaRotateMin"       , "-0.006" )
        xml_dynamics_particleSystem.set( "deltaRotateMax"       , "0.006" )
        xml_dynamics_particleSystem_gravity = xml_ET.SubElement( xml_dynamics_particleSystem, "Gravity" )
        xml_dynamics_particleSystem_gravity.set( "force", "0 -0.5 0" )
    #
    #  =====================================================================================
    #
    def _xmlWriteUserAttributes( self ):
        for m_obj in self._objectsToExportDict.keys():
            if ( self._isObjectHasUserAttributes( m_obj ) ):
                self._xmlWriteUserAttributes_item( m_obj )

    def _xmlWriteUserAttributes_item( self, m_obj ):
        m_nodeID                = self._objectsToExportDict[ m_obj ]
        xml_userAttributes_item = xml_ET.SubElement( self._xml_userAttributes, "UserAttribute" )
        xml_userAttributes_item.set( "nodeId", "%d"  %m_nodeID )
        for m_key in m_obj.keys():
            if ( 0 == ( "%s" %m_key ).find( "userAttribute_" ) ):
                m_attributeName   = m_key.split("_")[1]
                m_attributeType   = self._getUserAttributeType( m_obj, m_key )
                m_attributeValue  = m_obj[ m_key ]
                xml_userAttributes_item_attr = xml_ET.SubElement( xml_userAttributes_item, "Attribute" )
                xml_userAttributes_item_attr.set( "name" ,  m_attributeName )
                xml_userAttributes_item_attr.set( "type" ,  m_attributeType )
                xml_userAttributes_item_attr.set( "value",  "%s" %m_attributeValue )
    #
    #  =====================================================================================
    #
    def _xmlBuild( self ):

        # i3D
        self._xml_i3d = xml_ET.Element( "i3D" )
        if ( self._isSaved() ):
            m_name = bpy.path.basename( bpy.data.filepath )
        else:
            m_name = "untitled"

        self._xml_i3d.set( "name", m_name )
        self._xml_i3d.set( "version", "1.6" )
        self._xml_i3d.set( "xsi:noNamespaceSchemaLocation", "http://i3d.giants.ch/schema/i3d-1.6.xsd" )
        self._xml_i3d.set( "xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance" )

        # Asset
        self._xml_asset    = xml_ET.SubElement( self._xml_i3d,   "Asset" )
        self._xml_software = xml_ET.SubElement( self._xml_asset, "Export" )
        self._xml_software.set( "program", "Blender" )
        self._xml_software.set( "version", "%s.%s.%s" %bpy.app.version )

        # Files
        self._xml_files          = xml_ET.SubElement( self._xml_i3d, "Files" )
        self._xmlWriteFiles()

        # Materials
        self._xml_materials      = xml_ET.SubElement( self._xml_i3d, "Materials" )
        self._xmlWriteMaterials()

        # Shapes
        self._xml_shapes         = xml_ET.SubElement( self._xml_i3d, "Shapes" )
        self._xmlWriteShapes()

        # Dynamics
        if ( self._i3d_exportParticleSystems ):
            self._xml_dynamics   = xml_ET.SubElement( self._xml_i3d, "Dynamics" )
            self._xmlWriteDynamics()

        # Scene
        self._xml_scene          = xml_ET.SubElement( self._xml_i3d, "Scene" )
        self._xmlWriteScene()

        # Animation
        if ( self._i3d_exportAnimation ):
            self._xml_animation  = xml_ET.SubElement( self._xml_i3d, "Animation" )

        # UserAttributes
        if ( self._i3d_exportUserAttributes ):
            self._xml_userAttributes = xml_ET.SubElement( self._xml_i3d, "UserAttributes" )
            self._xmlWriteUserAttributes()

        self._indent( self._xml_i3d ) #prettyprint
        self._xml_tree = xml_ET.ElementTree( self._xml_i3d )
        if ( self._i3d_exportUseBlenderFileName ):
            if ( self._isSaved() ):
                m_filepath = bpy.path.ensure_ext( bpy.data.filepath, ".i3d" )
            else:
                m_filepath = "c:/tmp/untitled.i3d"
        else:
            m_filepath = bpy.path.abspath( self._i3d_exportFileLocation )
            m_filepath = bpy.path.ensure_ext( m_filepath, ".i3d" )
        print( "-----------------------------------------------" )
        try:
            self._xml_tree.write( m_filepath, xml_declaration = True, encoding = "iso-8859-1", method = "xml" )
            print( "Exported Successfully!    %s" %m_filepath )
        except Exception as m_exception:
            print( "ERROR: %s " %( m_exception ) )
    #
    #  =====================================================================================
    #
    def _getIDbyMaterial( self, m_mat ):
        if ( m_mat ):
            m_materialID = self._materialsToExportDict[ m_mat ]
        else:
            m_materialID = self._materialNone
        return m_materialID

    def _getTexturesFromMaterial( self, m_mat ):
        m_textures = {}
        for m_slot in m_mat.texture_slots:
            if ( ( m_slot )  and
                 ( m_slot.use ) and
                 ( m_slot.texture in self._filesToExportDict ) and
                 ( self._checkTextureInSlot( m_mat, m_slot ) ) ):
                m_textures[ self._checkTextureInSlot( m_mat, m_slot ) ] = m_slot.texture
        return m_textures

    def _addAllParentsToObjectsToExportDict( self, m_obj ):
        if ( m_obj.parent ):
            if ( m_obj.parent not in self._objectsToExportDict ):
                self._nodeID += 1
                self._objectsToExportDict[ m_obj.parent ] = self._nodeID
            self._addAllParentsToObjectsToExportDict( m_obj.parent  )

    @staticmethod
    def _isObjectHasParticleSystem( m_obj ):
        if ( len( m_obj.modifiers ) ):
            for m_modifier in m_obj.modifiers:
                if ( "PARTICLE_SYSTEM" == m_modifier.type ):
                    return m_modifier
        return None

    @staticmethod
    def _isTextureWrapped( m_texture ):
        if ( "REPEAT" == m_texture.extension ):
            return True
        else:
            return False

    @staticmethod
    def _checkObject( m_obj ):
        m_return = False
        if (  "MESH"   ==  m_obj.type or
              "CURVE"  ==  m_obj.type or
              "EMPTY"  ==  m_obj.type or
              "CAMERA" ==  m_obj.type or
            ( "LAMP"   ==  m_obj.type and ( "POINT" == m_obj.data.type or "SUN" == m_obj.data.type or "SPOT" == m_obj.data.type ) ) ):
            m_return = True
        return m_return

    def _checkObjectFiles ( self, m_obj ):
        m_materials = self._getObjectMaterials( m_obj )
        for m_mat in m_materials:
            if ( "materialNone" != m_mat ):
                # general section
                for m_slot in m_mat.texture_slots:
                    if ( ( m_slot ) and
                         ( m_slot.use ) and
                         ( self._checkTextureInSlot( m_mat, m_slot ) ) and
                         ( m_slot.texture not in self._filesToExportDict ) and
                         ( "IMAGE" ==  m_slot.texture.type ) and
                         ( hasattr( m_slot.texture, "image" ) ) and
                         ( "FILE" == m_slot.texture.image.source ) and
                         ( not m_slot.texture.image.packed_file ) ):
                        self._fileID += 1
                        self._filesToExportDict[ m_slot.texture ] = self._fileID
                # custom data section
                m_custom_shader, m_custom_shader_variation, m_custom_texture, m_custom_texture_wrap, m_custom_texture_colorProfile, m_custom_parameter = self._checkMaterialCustomData ( m_mat )
                if ( m_custom_shader ):
                    # ----------------------------------
                    m_key = ( m_custom_shader, m_mat[ m_custom_shader ] )
                    # ----------------------------------
                    if ( m_key not in self._filesToExportCustomDict ):
                        self._fileID += 1
                        self._filesToExportCustomDict[ m_key ] = ( self._fileID, None )
                if ( len( m_custom_texture ) ):
                    for m_texture in m_custom_texture:
                        m_textureName   = m_texture.split("_")[1]
                        m_colorProfile = None
                        if ( len( m_custom_texture_colorProfile ) ):
                            for m_textureCP in m_custom_texture_colorProfile:
                                m_textureCPName  = m_textureCP.split("_")[1]
                                m_textureCPValue = m_mat[ m_textureCP ]
                                if (  ( m_textureName == m_textureCPName ) and
                                      ( ("sRGB" == m_textureCPValue ) or ("linearRGB" == m_textureCPValue ) ) ):
                                    m_colorProfile = m_textureCPValue
                        # -----------------------------------------
                        m_key = ( m_texture, m_mat[ m_texture ] )
                        # -----------------------------------------
                        if ( m_key not in  self._filesToExportCustomDict ):
                            self._fileID += 1
                            self._filesToExportCustomDict[ m_key ] = ( self._fileID, m_colorProfile )
                        else:
                            if ( m_colorProfile and not self._filesToExportCustomDict[ m_key ][1] ):
                                self._filesToExportCustomDict[ m_key ] = ( self._filesToExportCustomDict[ m_key ][0], m_colorProfile )

    def _checkObjectMaterials( self, m_obj ):
        m_materials = self._getObjectMaterials( m_obj )
        if ( 0 == len( m_materials ) and ( not self._materialNone ) ):
            self._fileID += 1
            self._materialNone = self._fileID
        for m_mat in m_materials:
            if ( ( m_mat not in self._materialsToExportDict )  and
                 ( "materialNone" != m_mat ) ):
                self._fileID += 1
                self._materialsToExportDict[ m_mat ] = self._fileID
            if ( "materialNone" == m_mat and ( not self._materialNone ) ):
                self._fileID += 1
                self._materialNone = self._fileID

    def _needCalculateTangents( self, m_obj ):
        m_materials = self._getObjectMaterials( m_obj )
        for m_mat in m_materials:
            if ( "materialNone" != m_mat ):
                m_textures = self._getTexturesFromMaterial( m_mat )
                if ( "map_normal" in m_textures ):
                    return True
        return False

    @staticmethod
    def _getObjectMaterials( m_obj ):
        m_materialIndexes = []
        m_materials = {}
        if ( "MESH"   !=  m_obj.type ):
            return m_materials
        for m_polygon in m_obj.data.polygons:
            if ( m_polygon.material_index  not in m_materialIndexes ):
                m_materialIndexes.append( m_polygon.material_index )
        for m_matIndex in  m_materialIndexes:
            if ( m_obj.material_slots ):
                m_mat =  m_obj.material_slots[ m_matIndex ].material
                if ( m_mat ):
                    m_materials[ m_mat ] = m_matIndex
                else:
                    m_materials[ "materialNone" ] = m_matIndex
        return m_materials

    @staticmethod
    def _checkMaterialCustomData( m_mat ):
        m_custom_shader                 = None
        m_custom_shader_variation       = None
        m_custom_texture                = []
        m_custom_texture_wrap           = []
        m_custom_texture_colorProfile   = []
        m_custom_parameter              = []
        for m_key in m_mat.keys():
            if ( "customShader" ==  "%s" %m_key ):
                m_custom_shader = "%s" %m_key
            if ( "customShaderVariation" ==  "%s" %m_key ):
                m_custom_shader_variation = "%s" %m_key
            if ( 0 == ( "%s" %m_key ).find( "customTexture_" )  ):
                m_custom_texture.append( "%s" %m_key )
            if ( 0 == ( "%s" %m_key ).find( "customTextureWrap_" )  ):
                m_custom_texture_wrap.append( "%s" %m_key )
            if ( 0 == ( "%s" %m_key ).find( "customTextureColorProfile_" )  ):
                m_custom_texture_colorProfile.append( "%s" %m_key )
            if ( 0 == ( "%s" %m_key ).find( "customParameter_" )  ):
                m_custom_parameter.append( "%s" %m_key )
        return ( m_custom_shader, m_custom_shader_variation, m_custom_texture, m_custom_texture_wrap, m_custom_texture_colorProfile, m_custom_parameter )

    @staticmethod
    def _isObjectHasUserAttributes( m_obj ):
        for m_key in m_obj.keys():
            if ( 0 == ( "%s" %m_key ).find( "userAttribute_" ) ):
                return True
        return False

    @staticmethod
    def _getUserAttributeType( m_obj, m_key ):
        m_attributeType   = m_obj['_RNA_UI'][ m_key ]['description']
        if ( "scriptCallback" == m_attributeType ): return m_attributeType
        if ( "boolean"        == m_attributeType ): return m_attributeType
        if ( "float"          == m_attributeType ): return m_attributeType
        if ( "integer"        == m_attributeType ): return m_attributeType
        if ( "string"         == m_attributeType ): return m_attributeType
        return "string"

    @staticmethod
    def _checkTextureInSlot( m_mat, m_slot ):
        if ( m_slot.use_map_color_diffuse and m_mat.use_shadeless ): return "map_emission"
        if ( m_slot.use_map_color_diffuse ):                         return "map_diffuse"
        if ( m_slot.use_map_normal ):                                return "map_normal"
        if ( m_slot.use_map_color_reflection ):                      return "map_specular"
        if ( m_slot.use_map_mirror and m_mat.raytrace_mirror.use ):  return "map_reflection"
        return None

    @staticmethod
    def _isSaved( ):
        if ( bpy.data.filepath ): return True
        else: return False

    @staticmethod
    def _shapeMeshTriangulate( m_mesh, m_verbose = True ):
        if ( m_verbose ):
            m_start_time = time.time()

        m_bm = bmesh.new()
        m_bm.from_mesh( m_mesh )
        bmesh.ops.triangulate( m_bm, faces = m_bm.faces )
        m_bm.to_mesh( m_mesh )
        m_bm.free()

        if ( m_verbose ):
            m_end_time = time.time()
            print( "    %s time is %g seconds" % ( inspect.stack()[0][3], m_end_time - m_start_time ) )

    @staticmethod
    def _getBvCenterRadius( m_mesh ):
        '''
        bvCenter - average position of all vertices in local space.
        '''
        m_vSum      = mathutils.Vector( (0,0,0) )
        m_bvRadius  = mathutils.Vector( (0,0,0) )
        m_vCount    = 0
        for m_v in m_mesh.vertices:
            m_vSum      += m_v.co
            m_vCount    += 1
        m_bvCenter = m_vSum / m_vCount

        for m_v in m_mesh.vertices:
            m_vect      = m_bvCenter - m_v.co
            m_bvRadius  = max( m_vect.length, m_bvRadius )
            
        return ( m_bvCenter, m_bvRadius )

    @staticmethod
    def _xmlWriteBool( m_xmlCurrent, m_attr, m_val ):
        if ( m_val ):
            m_xmlCurrent.set( m_attr , "true" )
        else:
            m_xmlCurrent.set( m_attr , "false" )

    @staticmethod
    def _indent( elem, level = 0 ):
        """
        source http://effbot.org/zone/element-lib.htm#prettyprint
        """
        i = "\n" + level*"  "
        if len( elem ):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for elem in elem:
                I3D_IOexport._indent( elem, level + 1 )
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i

class IndexBufferItem( object ):
    def __init__( self, m_mesh, m_index, m_needNormals = True,  m_uvLayersIndexes = 0, m_vertColorsIndexes = 0, m_format = None ):
        
        self.m_format           = m_format
        
        m_indexData = self._getVertexDataByLoopIndex( m_mesh, m_index, m_needNormals, m_uvLayersIndexes, m_vertColorsIndexes )
        
        self.m_vertexIndex      = m_indexData[0]
        self.m_vertexCoords     = m_indexData[1]
        self.m_vertexNormals    = m_indexData[2]
        self.m_vertexUVs        = m_indexData[4]
        self.m_vertexColors     = m_indexData[5]
        
        self._m_hashLoopIndex   = m_index
        self._m_hashIndex       = self.m_vertexIndex
        self._m_hashCoords      = frozenset( self.m_vertexCoords )
        self._m_hashNormals     = frozenset( self.m_vertexNormals )
        self._m_hashTangents    = frozenset( m_indexData[3] )
        self._m_hashUV          = frozenset( self.m_vertexUVs )
        self._m_hashColor       = frozenset( self.m_vertexColors )
        

    def __hash__( self ):
        if ( BLENDER_CHECK_VERSION01 <= bpy.app.version ):
            return ( hash( ( self._m_hashTangents,  self._m_hashIndex , self._m_hashCoords, self._m_hashNormals, self._m_hashUV, self._m_hashColor ) ) )
        else:
            return ( hash( ( self._m_hashLoopIndex, self._m_hashIndex , self._m_hashCoords, self._m_hashNormals, self._m_hashUV, self._m_hashColor ) ) )

    def __eq__( self, other ):
        if ( BLENDER_CHECK_VERSION01 <= bpy.app.version ):
            return ( self._m_hashTangents,  self._m_hashIndex , self._m_hashCoords, self._m_hashNormals, self._m_hashUV, self._m_hashColor ) == ( other._m_hashTangents,  other._m_hashIndex , other._m_hashCoords, other._m_hashNormals, other._m_hashUV, other._m_hashColor )
        else:
            return ( self._m_hashLoopIndex, self._m_hashIndex , self._m_hashCoords, self._m_hashNormals, self._m_hashUV, self._m_hashColor ) == ( other._m_hashLoopIndex, other._m_hashIndex , other._m_hashCoords, other._m_hashNormals, other._m_hashUV, other._m_hashColor )

    def _getVertexDataByLoopIndex( self, m_mesh, m_index, m_needNormals, m_uvLayersIndexes, m_vertColorsIndexes ):
        m_loop          = m_mesh.loops[ m_index ]
        m_vertexIndex   = m_loop.vertex_index

        m_vertexCoords  = m_mesh.vertices[ m_vertexIndex ].co.xyz[:]
        if ( "baked" == self.m_format  ): # x z -y
            m_vertexCoords = ( m_vertexCoords[0], m_vertexCoords[2], - m_vertexCoords[1] )
        
        m_vertexNormals  = ( 0, 0, 0 )
        m_vertexTangents = ( 0, 0, 0 )
        if ( m_needNormals ):
            m_vertexNormals = m_mesh.vertices[ m_vertexIndex ].normal.xyz[:]
            if ( BLENDER_CHECK_VERSION01 <= bpy.app.version ):
                m_vertexTangents = m_loop.tangent.xyz[:]
            if ( "baked" == self.m_format  ): # x z -y
                m_vertexNormals = ( m_vertexNormals[0], m_vertexNormals[2], - m_vertexNormals[1] )
        
        m_vertexUVs     = [ ]
        m_vertexColors  = [ ]

        for m_uvlayerIndex in range( m_uvLayersIndexes ):
            m_vertexUVs.append( m_mesh.uv_layers[ m_uvlayerIndex ].data[ m_index ].uv[:]  )

        for m_vertColorIndex in range( m_vertColorsIndexes ):
            m_vertexColors.append( m_mesh.vertex_colors[ m_vertColorIndex ].data[ m_vertexIndex ].color[:] )

        return ( m_vertexIndex, m_vertexCoords, m_vertexNormals, m_vertexTangents, m_vertexUVs, m_vertexColors )

def doExportAll():
    m_exp = I3D_IOexport()
    m_exp.exportAll()

def doExportSelecred():
    m_exp = I3D_IOexport()
    m_exp.exportSelected()