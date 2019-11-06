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
print(__file__)

import bpy, bmesh
import os
import math, mathutils

def getFilePath():
    return bpy.path.ensure_ext( bpy.data.filepath, ".i3d" )

def getFileBasename():
    return bpy.path.basename( bpy.data.filepath )

def isFileSaved():
    if ( bpy.data.filepath ): return True
    else: return False

def appVersion():
    return bpy.app.version

def UISetLoadedNode(m_nodeStr):
    m_node = bpy.data.objects[m_nodeStr]
    UISetAttrString("I3D_nodeName",m_node.name)
    UISetAttrString("I3D_nodeIndex",getNodeIndex(m_node.name))

def UIGetLoadedNode():
    m_objPath = UIGetAttrString("I3D_nodeName")
    if (m_objPath in bpy.data.objects):
        return m_objPath
    else:
        return None

def I3DAddAttrBool(m_nodeStr,m_attr):
    I3DSetAttrBool(m_nodeStr,m_attr,bool(False))

def I3DSetAttrBool(m_nodeStr,m_attr,m_val):
    m_node = bpy.data.objects[m_nodeStr]
    m_node[m_attr] = m_val

def I3DAddAttrInt(m_nodeStr,m_attr):
    I3DSetAttrInt(m_nodeStr,m_attr,int(0))

def I3DSetAttrInt(m_nodeStr,m_attr,m_val):
    m_node = bpy.data.objects[m_nodeStr]
    m_node[m_attr] = m_val

def I3DAddAttrFloat(m_nodeStr,m_attr):
    I3DSetAttrFloat(m_nodeStr,m_attr,float(0.0))

def I3DSetAttrFloat(m_nodeStr,m_attr,m_val):
    m_node = bpy.data.objects[m_nodeStr]
    m_node[m_attr] = m_val

def I3DAddAttrString(m_nodeStr,m_attr):
    I3DSetAttrString(m_nodeStr,m_attr,str(""))

def I3DSetAttrString(m_nodeStr,m_attr,m_val):
    m_node = bpy.data.objects[m_nodeStr]
    m_node[m_attr] = m_val

def I3DGetAttr(m_nodeStr, m_attr):
    m_node = bpy.data.objects[m_nodeStr]
    return m_node[m_attr]

def I3DAttributeExists(m_nodeStr, m_attr):
    if m_nodeStr in bpy.data.objects:
        m_node = bpy.data.objects[m_nodeStr]
        if (m_attr in m_node):
            return True
    return False

def I3DRemoveAttribute(m_nodeStr, m_attr):
    m_node = bpy.data.objects[m_nodeStr]
    if(I3DAttributeExists(m_nodeStr, m_attr)):
        del m_node[m_attr]

def UIAttrExists(m_attr):
    try:
        m_str = "bpy.context.scene.I3D_UIexportSettings.{0}".format(m_attr)
        eval(m_str)
        return True
    except:
        return False

def UIGetAttrBool(key):
    m_str = "bpy.context.scene.I3D_UIexportSettings.{0}".format(key)
    return eval(m_str)

def UISetAttrBool(key,val):
    m_str = "bpy.context.scene.I3D_UIexportSettings.{0}=bool({1})".format(key,val)
    exec(m_str)

def UIGetAttrInt(key):
    m_str = "bpy.context.scene.I3D_UIexportSettings.{0}".format(key)
    return eval(m_str)

def UISetAttrInt(key, val):
    m_str = "bpy.context.scene.I3D_UIexportSettings.{0}=int({1})".format(key,val)
    exec(m_str)

def UIGetAttrFloat(key):
    m_str = "bpy.context.scene.I3D_UIexportSettings.{0}".format(key)
    return eval(m_str)

def UISetAttrFloat(key, val):
    m_str = "bpy.context.scene.I3D_UIexportSettings.{0}=float({1})".format(key,val)
    exec(m_str)

def UIGetAttrString(key):
    m_str = "bpy.context.scene.I3D_UIexportSettings.{0}".format(key)
    return eval(m_str)

def UISetAttrString(key, val):
    m_str = "bpy.context.scene.I3D_UIexportSettings.{0}=str('{1}')".format(key,val)
    exec(m_str)

def UIShowError(m_str):
    if (UIGetAttrBool('I3D_exportVerbose')):
        print("Error: {0}".format(m_str))

def UIShowWarning(m_str):
    if (UIGetAttrBool('I3D_exportVerbose')):
        print("Warning: {0}".format(m_str))

def UIAddMessage(m_str):
    if (UIGetAttrBool('I3D_exportVerbose')):
        print(m_str)

def getSelectedNodes():
    m_iterItems = []
    for m_node in bpy.context.selected_objects:
        m_iterItems.append(m_node.name)
    m_iterItems.sort()
    return m_iterItems

def getSelectedNodesToExport():
    m_iterItems = []
    m_nodes = getSelectedNodes()
    for m_nodeStr in m_nodes:
        m_iterItems.append(m_nodeStr)
        addParentNodeToList(m_nodeStr,m_iterItems)
    m_iterItems.sort()
    return m_iterItems

def addParentNodeToList(m_nodeStr,m_iterItems):
    m_parentStr = getParentObjectWithoutWorld(m_nodeStr)
    if (m_parentStr):
        if (m_parentStr not in m_iterItems):
            m_iterItems.append(m_parentStr)
        addParentNodeToList(m_parentStr, m_iterItems)
    else:
        return m_iterItems

def isParentedToWorld(m_nodeStr):
    m_node = bpy.data.objects[m_nodeStr]
    m_parent = m_node.parent
    if (None==m_parent):
        return True
    else:
        return False

def getAllNodesToExport():
    m_result = []
    m_nodes = getWorldObjects()
    addChildObjects(m_nodes,m_result)
    return m_result

def getParentObjectWithoutWorld(m_nodeStr):
    m_node = bpy.data.objects[m_nodeStr]
    # if parented to the world return None
    if m_node.parent:
        return m_node.parent.name
    else:
        return None

def getChildObjects(m_parentStr):
    m_parent = bpy.data.objects[m_parentStr]
    m_iterItems = []
    for m_node in m_parent.children:
        m_iterItems.append(m_node.name)
    m_iterItems.sort()
    return m_iterItems

def getNodeInstances(m_nodeStr):
    m_nodes = []
    return m_nodes

def getNodeName(m_nodeStr):
    m_node = bpy.data.objects[m_nodeStr]
    return m_node.name

def getNodeData(m_nodeStr, m_nodeData):
    m_node = bpy.data.objects[m_nodeStr]
    m_nodeData["fullPathName"] = m_node.name
    m_nodeData["name"] = m_node.name
    m_nodeData["type"] = getNodeType(m_nodeStr)
    return m_nodeData

def getShapeData(m_shapeStr,m_nodeData):
    m_mesh = bpy.data.meshes[m_shapeStr]
    m_nodeData["name"] = m_mesh.name
    # --- generate exporting mesh
    m_meshOwners = getMeshOwners(m_shapeStr)
    m_obj = bpy.data.objects[m_meshOwners[0]]
    m_meshGen = m_obj.to_mesh( bpy.context.scene, UIGetAttrString('I3D_exportApplyModifiers') , "PREVIEW", calc_tessface = False )
    # -------------------------------------------------------------
    m_bvCenter, m_bvRadius = getBvCenterRadius(m_meshGen.name)
    if ( "BAKE_TRANSFORMS" == UIGetAttrString('I3D_exportAxisOrientations') ): # x z -y
        m_bvOrig      = m_bvCenter.xyz
        m_bvCenter.x  = m_bvOrig.x
        m_bvCenter.y  = m_bvOrig.z
        m_bvCenter.z  = - m_bvOrig.y
    m_nodeData["bvCenter"] = "{:.6f} {:.6f} {:.6f}".format(m_bvCenter.x,m_bvCenter.y,m_bvCenter.z)
    m_nodeData["bvRadius"] = "{:.6f}".format(m_bvRadius)
    # -------------------------------------------------------------
    m_materialsList = getShapeMaterials(m_meshGen.name)
    m_materials = {}
    for m_mat in m_materialsList:
        m_materials[m_mat] = []
    # --- triangulate mesh before processing
    m_bm = bmesh.new()
    m_bm.from_mesh( m_meshGen )
    bmesh.ops.triangulate( m_bm, faces = m_bm.faces )
    m_bm.to_mesh( m_meshGen )
    m_bm.free()
    # -------------------------------------------------------------
    if (len(m_materialsList) > 1):
        for m_polygon in m_meshGen.polygons:
            m_mat = m_meshGen.materials[m_polygon.material_index]
            if None == m_mat:
                m_mat = "default"
            else:
                m_mat = m_mat.name
            m_matItem = m_materials[m_mat]
            m_matItem.append(m_polygon.index)
    else:
        m_matItem = m_materials[m_materialsList[0]]
        for m_polygon in m_meshGen.polygons:
            m_matItem.append(m_polygon.index)
    # -------------------------------------------------------------
    m_vertices  = {}
    m_triangles = {}
    m_subsets   = {}
    m_vertices["data"]  = []
    m_triangles["data"] = []
    m_subsets["data"]   = []
    # -------------------------------------------------------------
    m_vertices["normal"] = "true"
    if len(m_meshGen.vertex_colors):
        m_vertices["color"] = "true"
    for m_i in range( len(m_meshGen.uv_layers) ):
        if m_i == 4: break
        m_str = "uv{:d}".format(m_i)
        m_vertices[m_str] = "true"
    # -------------------------------------------------------------
    m_indexBuffer    = {}
    m_currentIndex   = 0
    m_firstIndex     = 0
    m_numVerticesSet = set()
    m_trainglesCount = 0
    m_subsetsCount   = 0
    m_counter        = 0
    for m_mat in m_materialsList:
        m_matItem = m_materials[m_mat]
        m_trainglesCount += len( m_matItem )
        m_subsetsCount  += 1
        m_numIndices    = 0
        m_numVerticesSet.clear()
        for m_primIndex in m_matItem:
            m_polygon = m_meshGen.polygons[ m_primIndex ]
            m_strVI = ''
            for m_loopIndex in m_polygon.loop_indices:
                m_loop        = m_meshGen.loops[m_loopIndex]
                m_vertexIndex = m_loop.vertex_index
                m_vertItem = {}
                m_pos      = m_meshGen.vertices[ m_vertexIndex ].co.xyz[:]
                if ( "BAKE_TRANSFORMS" == UIGetAttrString('I3D_exportAxisOrientations')): # x z -y
                    m_pos = ( m_pos[0], m_pos[2], -m_pos[1] )
                m_vertItem["p"] = "{:.6f} {:.6f} {:.6f}".format(m_pos[0],m_pos[1],m_pos[2])
                if ("normal" in m_vertices):
                    m_value = m_meshGen.vertices[ m_vertexIndex ].normal.xyz[:]
                    if ( "BAKE_TRANSFORMS" == UIGetAttrString('I3D_exportAxisOrientations')): # x z -y
                        m_value = ( m_value[0], m_value[2], -m_value[1] )
                    m_vertItem["n"] = "{:.6f} {:.6f} {:.6f}".format(m_value[0],m_value[1],m_value[2])
                if ("color" in m_vertices):
                    m_value = m_meshGen.vertex_colors[0].data[m_vertexIndex].color[:]
                    m_Alpha = 1.0
                    m_vertItem["c"] = "{:.6f} {:.6f} {:.6f} {:.6f}".format(m_value[0],m_value[1],m_value[2],m_Alpha)
                if ("uv0" in m_vertices):
                    m_value = m_meshGen.uv_layers[0].data[m_loopIndex].uv[:]
                    m_vertItem["t0"] = "{:.6f} {:.6f}".format(m_value[0],m_value[1])
                if ("uv1" in m_vertices):
                    m_value = m_meshGen.uv_layers[1].data[m_loopIndex].uv[:]
                    m_vertItem["t1"] = "{:.6f} {:.6f}".format(m_value[0],m_value[1])
                if ("uv2" in m_vertices):
                    m_value = m_meshGen.uv_layers[2].data[m_loopIndex].uv[:]
                    m_vertItem["t2"] = "{:.6f} {:.6f}".format(m_value[0],m_value[1])
                if ("uv3" in m_vertices):
                    m_value = m_meshGen.uv_layers[3].data[m_loopIndex].uv[:]
                    m_vertItem["t3"] = "{:.6f} {:.6f}".format(m_value[0],m_value[1])
                m_indexData = IndexBufferItem(m_vertItem,m_mat)
                if ( m_indexData not in m_indexBuffer ):
                    m_indexBuffer[ m_indexData ] = m_counter
                    m_counter += 1
                    m_vertices["data"].append(m_vertItem)
                m_currentIndexVertex = m_indexBuffer[ m_indexData ]
                m_strVI  += " {:d}".format(m_currentIndexVertex)
                if ( 0 == m_numIndices ):
                    m_firstIndex  = m_currentIndex
                m_numVerticesSet.add( m_currentIndexVertex )
                m_currentIndex += 1
                m_numIndices   += 1
            m_triItem = {}
            m_triItem["vi"] = m_strVI.strip()
            m_triangles["data"].append(m_triItem)
        m_subsetItem = {}
        m_subsetItem["firstVertex"] = "{}".format(min(m_numVerticesSet))
        m_subsetItem["numVertices"] = "{}".format(len(m_numVerticesSet))
        m_subsetItem["firstIndex"]  = "{}".format(m_firstIndex)
        m_subsetItem["numIndices"]  = "{}".format(m_numIndices)
        m_subsets["data"].append(m_subsetItem)
    m_vertices["count"]  = "{}".format(len(m_indexBuffer))
    m_triangles["count"] = "{}".format(m_trainglesCount)
    m_subsets["count"]   = "{}".format(m_subsetsCount)
    m_nodeData["Materials"] = m_materialsList
    m_nodeData["Vertices"]  = m_vertices
    m_nodeData["Triangles"] = m_triangles
    m_nodeData["Subsets"]   = m_subsets
    # --- Remove generated mesh
    bpy.data.meshes.remove( m_meshGen )
    return m_nodeData

def getMeshOwners(m_shapeStr):
    m_meshOwners = []
    for m_obj in bpy.data.objects:
        if 'MESH' == m_obj.type:
            m_mesh = m_obj.data
            if m_mesh.name == m_shapeStr:
                m_meshOwners.append(m_obj.name)
    return m_meshOwners

def getBvCenterRadius(m_shapeStr):
    m_mesh      = bpy.data.meshes[m_shapeStr]
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
    return m_bvCenter, m_bvRadius

def getNurbsCurveData(m_shapeStr,m_nodeData):
    m_curve = bpy.data.curves[m_shapeStr]
    m_nodeData["name"] = m_curve.name
    m_nodeData["form"] = "open"
    if ( len( m_curve.splines ) ):
        m_spline = m_curve.splines[0]
        if m_spline.use_cyclic_u: m_nodeData["form"] = "closed"
        m_splinePoints = None
        if ( "NURBS"  == m_spline.type ):   m_splinePoints = m_spline.points
        if ( "BEZIER" == m_spline.type ):   m_splinePoints = m_spline.bezier_points
        if ( m_splinePoints ):
            m_points = []
            for m_p in m_splinePoints:
                m_pointCoords  = m_p.co.xyz[:]
                m_orient = UIGetAttrString('I3D_exportAxisOrientations')
                if ( "BAKE_TRANSFORMS"  == m_orient ): # x z -y
                    m_pointCoords = ( m_pointCoords[0], m_pointCoords[2], - m_pointCoords[1] )
                m_points.append( "{:.6f} {:.6f} {:.6f}".format(m_pointCoords[0],m_pointCoords[1],m_pointCoords[2]) )
            m_nodeData['points'] = m_points
    return m_nodeData

def getShapeMaterials(m_shapeStr):
    m_materialIndexes = []
    m_materials = []
    m_mesh      = bpy.data.meshes[m_shapeStr]
    for m_polygon in m_mesh.polygons:
        if ( m_polygon.material_index  not in m_materialIndexes ):
            m_materialIndexes.append( m_polygon.material_index )
    for m_matIndex in  m_materialIndexes:
        if m_mesh.materials:
            m_mat = m_mesh.materials[m_matIndex]
            if m_mat:
                m_materials.append(m_mat.name)
            else:
                m_materials.append("default")
        else:
            m_materials.append("default")
    return m_materials

def getMaterialFiles(m_materialStr):
    m_files = {}
    if m_materialStr in bpy.data.materials:
        m_mat = bpy.data.materials[m_materialStr]
        for m_slot in m_mat.texture_slots:
            if m_slot:
                if m_slot.use:
                    m_texture = m_slot.texture
                    if "IMAGE" == m_texture.type:
                        m_image = m_texture.image
                        if (m_image):
                            m_files[bpy.path.abspath(m_image.filepath)] = getTextureTypeInSlot(m_mat, m_slot)
        for m_key in m_mat.keys():
            m_str = "{}".format(m_key)
            if ( "customShader" == m_str ):
                m_files[m_mat["customShader"]] = "customShader"
            if ( 0 == m_str.find("customTexture_") ):
                m_files[m_mat[m_str]] = m_str
    return m_files

def getTextureTypeInSlot( m_mat, m_slot ):
    if ( m_slot.use_map_color_diffuse ):    return "Texture"
    if ( m_slot.use_map_normal ):           return "Normalmap"
    if ( m_slot.use_map_color_reflection ): return "Glossmap"
    return "Texture"

def getShapeNode(m_nodeData):
    m_nodeStr = m_nodeData["fullPathName"]
    if m_nodeStr in bpy.data.objects:
        m_obj = bpy.data.objects[m_nodeStr]
        return m_obj.data.name
    else:
        if ("fullPathNameOrig" in m_nodeData):
            m_nodeStr = m_nodeData["fullPathNameOrig"]
            if m_nodeStr in bpy.data.objects:
                m_obj = bpy.data.objects[m_nodeStr]
                return m_obj.data.name
    return None

def getNodeType(m_nodeStr):
    m_node = bpy.data.objects[m_nodeStr]
    m_nodeTypeStr = m_node.type
    if ('EMPTY'  == m_nodeTypeStr):
        return 'TYPE_TRANSFORM_GROUP'
    if ('LAMP'   == m_nodeTypeStr):
        return 'TYPE_LIGHT'
    if ('CAMERA' == m_nodeTypeStr):
        return 'TYPE_CAMERA'
    if ('CURVE'  == m_nodeTypeStr):
        return 'TYPE_NURBS_CURVE'
    if ('MESH'   == m_nodeTypeStr):
        return 'TYPE_MESH'
    return 'TYPE_TRANSFORM_GROUP'

def getNodeTranslationRotationScale(m_nodeStr):
    m_node = bpy.data.objects[m_nodeStr]
    m_orient = UIGetAttrString('I3D_exportAxisOrientations')
    if ( "BAKE_TRANSFORMS"  == m_orient ):
        # transform matrix Blender -> OpenGL
        m_matrix = mathutils.Matrix.Rotation( math.radians( -90 ), 4, "X" ) * m_node.matrix_local * mathutils.Matrix.Rotation( math.radians( 90 ), 4, "X" )
        if ( "CAMERA"  ==  m_node.type or "LAMP"  ==  m_node.type ):
            m_matrix = m_matrix * mathutils.Matrix.Rotation( math.radians( -90 ), 4, "X" )
        if ( m_node.parent ):
            if ( "CAMERA"  ==  m_node.parent.type or "LAMP"  ==  m_node.parent.type ):
                m_matrix = mathutils.Matrix.Rotation( math.radians( 90 ), 4, "X" ) * m_matrix
    else:
        if ( "KEEP_AXIS"  == m_orient ):
            if ( m_node.parent ):
                m_matrix = m_node.matrix_local
            else:
                m_matrix =  mathutils.Matrix.Rotation( math.radians( -90 ), 4, "X" ) * m_node.matrix_local
        elif ( "KEEP_TRANSFORMS"  == m_orient ):
            m_matrix        = m_node.matrix_local
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

def isNodeVisible(m_nodeStr):
    m_node = bpy.data.objects[m_nodeStr]
    return (not m_node.hide)

def getFileData(m_nodeStr,m_data):
    m_blend = os.path.dirname(bpy.data.filepath)
    m_str = os.path.relpath(m_nodeStr,m_blend)
    m_str = m_str.replace( "\\","/")
    m_data["filename"]     = m_str
    m_data["relativePath"] = "true"
    return m_data

def getMaterialData(m_nodeStr, m_data):
    if m_nodeStr in bpy.data.materials:
        m_mat = bpy.data.materials[m_nodeStr]
        m_data["name"] = m_mat.name
        m_r = m_mat.diffuse_color.r
        m_g = m_mat.diffuse_color.g
        m_b = m_mat.diffuse_color.b
        m_data["diffuseColor"]  = "{} {} {} 1".format(m_r,m_g,m_b)
        if (m_mat.use_shadeless):
            m_data["emissiveColor"]  = "{} {} {} 1".format(m_r,m_g,m_b)
        m_smoothness = m_mat.specular_color.r
        m_metalic    = m_mat.specular_color.b
        m_data["specularColor"]  = "{} 1 {}".format(m_smoothness,m_metalic)
        if (m_mat.use_transparency):
            m_data["alphaBlending"] = "true"
        if ("customShaderVariation") in m_mat.keys():
            m_data["customShaderVariation"] = m_mat["customShaderVariation"]
        m_files = getMaterialFiles(m_nodeStr)
        m_customParameters = {}
        m_customTextures = {}
        for m_file, m_type in m_files.items():
            if ("Texture"      == m_type): m_data["Texture"]      = m_file
            if ("Glossmap"     == m_type): m_data["Glossmap"]     = m_file
            if ("Normalmap"    == m_type): m_data["Normalmap"]    = m_file
            if ("customShader" == m_type): m_data["customShader"] = m_file
            if (0 == m_type.find("customTexture_")):
                m_key = m_type.split("customTexture_")[1]
                m_customTextures[m_key] = m_file
        for m_item in m_mat.keys():
            if (0 == m_item.find("customParameter_")):
                m_key = m_item.split("customParameter_")[1]
                m_customParameters[m_key] = m_mat[m_item]
        if len(m_customParameters):
            m_data["CustomParameter"] = m_customParameters
        if len(m_customTextures):
            m_data["Custommap"] = m_customTextures
    return m_data

def getLightData(m_nodeStr, m_light):
    if (isObjDataExists(m_nodeStr,"type")):
        m_type = getObjData(m_nodeStr,"type")
        if ("SUN"   == m_type): m_light["type"] = "directional"
        if ("POINT" == m_type): m_light["type"] = "point"
        if ("SPOT"  == m_type):
            m_light["type"] = "spot"
            if (isObjDataExists(m_nodeStr,"spot_size")):
                m_light["coneAngle"] = "{:.3f}".format(math.degrees(getObjData(m_nodeStr,"spot_size")))
            if (isObjDataExists(m_nodeStr,"spot_blend")):
                m_light["dropOff"] = "{:.3f}".format(5.0*getObjData(m_nodeStr,"spot_blend"))
    if (isObjDataExists(m_nodeStr,"color")):
        m_color = getObjData(m_nodeStr,"color")
        m_light["color"] = "{} {} {}".format(m_color.r,m_color.g,m_color.b)
    if (isObjDataExists(m_nodeStr,"use_diffuse")):
        m_emitDiffuse = getObjData(m_nodeStr,"use_diffuse")
        if (not m_emitDiffuse): m_light["emitDiffuse"] = "false"
    if (isObjDataExists(m_nodeStr,"use_specular")):
        m_emitSpecular = getObjData(m_nodeStr,"use_specular")
        if (not m_emitSpecular): m_light["emitSpecular"] = "false"
    if (isObjDataExists(m_nodeStr,"falloff_type")):
        m_decayRate = getObjData(m_nodeStr,"falloff_type")
        if ("CONSTANT" == m_decayRate): m_light["decayRate"] = "0"
        if ("INVERSE_LINEAR" == m_decayRate): m_light["decayRate"] = "1"
        if ("INVERSE_SQUARE" == m_decayRate): m_light["decayRate"] = "2"
    if (isObjDataExists(m_nodeStr,"distance")):
        m_light["range"] = "{}".format(getObjData(m_nodeStr,"distance"))
    if (isObjDataExists(m_nodeStr,"shadow_method")):
        m_castShadowMap = getObjData(m_nodeStr,"shadow_method")
        if ( "NOSHADOW" == m_castShadowMap):  m_light["castShadowMap"] = "false"
    return m_light

def getCameraData(m_nodeStr, m_camera):
    if (isObjDataExists(m_nodeStr,"lens")):
        m_camera["fov"] = "{:.3f}".format(getObjData(m_nodeStr,"lens"))
    if (isObjDataExists(m_nodeStr,"clip_start")):
        m_camera["nearClip"] = "{:.3f}".format(getObjData(m_nodeStr,"clip_start"))
    if (isObjDataExists(m_nodeStr,"clip_end")):
        m_camera["farClip"] = "{:.3f}".format(getObjData(m_nodeStr,"clip_end"))
    if (isObjDataExists(m_nodeStr,"type")):
        m_type = getObjData(m_nodeStr,"type")
        if ('ORTHO'== m_type):
            m_camera["orthographic"] = "true"
            if (isObjDataExists(m_nodeStr,"ortho_scale")):
                m_camera["orthographicHeight"]  = "{}".format(getObjData(m_nodeStr,"ortho_scale"))
    return m_camera

def isObjDataExists(m_nodeStr,m_parm):
    m_str = 'bpy.data.objects["{}"].data.{}'.format(m_nodeStr,m_parm)
    try:
        eval(m_str)
        return True
    except:
        return False

def getObjData(m_nodeStr,m_parm):
    m_str = 'bpy.data.objects["{}"].data.{}'.format(m_nodeStr,m_parm)
    return eval(m_str)

def addChildObjects(m_nodes,m_result):
    for m_nodeStr in m_nodes:
        m_result.append(m_nodeStr)
        m_childs = getChildObjects(m_nodeStr)
        addChildObjects(m_childs,m_result)

def getNodeIndex( m_nodeStr ):
    return getDepth(m_nodeStr,"")

def getIndex( m_nodeStr ):
    m_node = bpy.data.objects[m_nodeStr]
    m_objParent = m_node.parent
    # if parented to the world
    if (None == m_objParent):
        m_iterItems = getWorldObjects()
    else:
        m_iterItems = getChildObjects(m_objParent.name)
    for i in range(len(m_iterItems)):
        m_child = m_iterItems[i]
        if (m_node.name == m_child):
            return i
    return None

def getDepth( m_nodeStr, m_ind ):
    m_node = bpy.data.objects[m_nodeStr]
    m_index = getIndex( m_node.name )
    m_objParent = m_node.parent
    # if parented to the world
    if (None == m_objParent):
        m_ind   = "{}>{}".format( m_index, m_ind ) # last run
        return m_ind
    else:
        if "" == m_ind:
            m_ind   = "{}{}".format( m_index, m_ind ) # first run
        else:
            m_ind   = "{}|{}".format( m_index, m_ind )
        m_ind = getDepth( m_objParent.name, m_ind )
    return m_ind

def getWorldObjects():
    m_iterItems = []
    for m_node in bpy.context.scene.objects:
        if (None is m_node.parent):
            m_iterItems.append(m_node.name)
    m_iterItems.sort()
    return m_iterItems

def getNodeUserAttributes(m_nodeStr):
    m_attributes = []
    m_types = ["boolean","string","scriptCallback","float"]
    if m_nodeStr in bpy.data.objects:
        m_node = bpy.data.objects[m_nodeStr]
        for m_key in m_node.keys():
            if (0==m_key.find("userAttribute_")):
                try:
                    m_list = m_key.split("_",2)
                    m_type = m_list[1]
                    m_name = m_list[2]
                    m_val  = m_node[ m_key ]
                    if m_type in m_types:
                        if ("boolean"==m_type):
                            if m_val: m_val = "true"
                            else:     m_val = "false"
                        m_val = "{}".format(m_val)
                        m_item = {}
                        m_item["name"]  = m_name
                        m_item["type"]  = m_type
                        m_item["value"] = m_val
                        m_attributes.append(m_item)
                except:
                    pass
    return m_attributes
#------------------------------------------------------------------------
#------------------------------------------------------------------------
#------------------------------------------------------------------------
class IndexBufferItem( object ):
    def __init__(self,m_vertItem,m_mat):
        self._str  = "{}".format(m_mat)
        for m_key,m_item in m_vertItem.items():
            self._str += " {}".format(m_item)

    def __hash__(self):
        return hash(self._str)

    def __eq__(self, other):
        return self._str == other._str