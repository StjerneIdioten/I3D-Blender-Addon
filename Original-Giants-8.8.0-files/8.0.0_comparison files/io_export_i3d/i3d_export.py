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
#TODO: Dynamics, mergeGroups, skinning, animations

import time
import os.path
import xml.etree.cElementTree as xml_ET
from io_export_i3d.dcc import *


def I3DExportAll():
    I3DExport(False)

def I3DExportSelected():
    I3DExport(True)

def I3DExport(m_exportSelection):
    dcc.UIAddMessage('Start export...')
    m_start_time = time.time()
    m_expObj = I3DIOexport()
    m_expObj.export(m_exportSelection)
    m_end_time = time.time()
    dcc.UIAddMessage('Export time is {0} seconds'.format(m_end_time - m_start_time))
#------------------------------------------------------------------------
#------------------------------------------------------------------------
#------------------------------------------------------------------------
class I3DSceneNode(object):
    def __init__(self, m_node,m_parent="ROOT",m_nodeID=0):
        self._children = []
        m_nodeData     = getNodeData(m_node)
        self._treeID   = m_nodeData["fullPathName"]
        self._data     = m_nodeData
        self._nodeID   = m_nodeID
        self._parent   = getNodeData(m_parent)["fullPathName"]

    def addChild(self, m_cTreeID):
        self._children.append(m_cTreeID)

    def removeChild(self, m_cTreeID):
        self._children.remove(m_cTreeID)
#------------------------------------------------------------------------
#------------------------------------------------------------------------
#------------------------------------------------------------------------
class I3DShapeNode(object):
    def __init__(self, m_shapeID, m_sceneNodeData):
        self._shapeID   = m_shapeID
        self._shapeType = m_sceneNodeData["type"]
        self._treeID    = dcc.getShapeNode(m_sceneNodeData)
        self._data      = {}

    def _generateData(self):
        self._data      = getShapeData(self._treeID,self._shapeType)
#------------------------------------------------------------------------
#------------------------------------------------------------------------
#------------------------------------------------------------------------
class I3DMaterialNode(object):
    def __init__(self, m_materialID, m_treeID):
        self._materialID = m_materialID
        self._treeID     = m_treeID
        self._data       = getMaterialData(m_treeID)
#------------------------------------------------------------------------
#------------------------------------------------------------------------
#------------------------------------------------------------------------
class I3DFileNode(object):
    def __init__(self, m_fileID, m_treeID, m_type = "Texture"):
        self._fileID = m_fileID
        self._treeID = m_treeID
        self._data   = getFileData(m_treeID,m_type)
#------------------------------------------------------------------------
#------------------------------------------------------------------------
#------------------------------------------------------------------------
class I3DSceneGraph(object):
    def __init__(self):
        self._nodeID    = 0
        self._shapeID   = 0
        self._matID     = 0
        self._fileID    = 0
        self._nodes     = {}
        self._shapes    = {}
        self._materials = {}
        self._files     = {}
        self._nodes["ROOT"] = I3DSceneNode("ROOT")

    def addNode(self, m_node, m_parent="ROOT"):
        self._nodeID +=1
        m_treeItem   = I3DSceneNode(m_node,m_parent,self._nodeID)
        self._nodes[m_treeItem._treeID] = m_treeItem
        m_treeParent = self._nodes[m_treeItem._parent]
        m_treeParent.addChild(m_treeItem._treeID)
        # UI check
        self.checkUI(m_treeItem)

    def generateShapes(self):
        for m_treeID in self.traverse(m_node="DEPTH"):
            m_treeItem   = self._nodes[m_treeID]
            m_data       = m_treeItem._data
            if ("TYPE_MESH" == m_data["type"] or "TYPE_NURBS_CURVE" == m_data["type"]):
                self._shapeID += 1
                m_shapeItem = I3DShapeNode(self._shapeID,m_data)
                self._shapes[m_shapeItem._treeID] = m_shapeItem
        for m_key, m_shape in self._shapes.items():
            m_shape._generateData()

    def generateMaterials(self):
        for m_key, m_shape in self._shapes.items():
            if "TYPE_MESH" == m_shape._shapeType:
                m_materialsList = dcc.getShapeMaterials(m_shape._treeID)
                for m_mat in m_materialsList:
                    self._matID += 1
                    m_materialItem = I3DMaterialNode(self._matID,m_mat)
                    self._materials[m_materialItem._treeID] = m_materialItem

    def generateFiles(self):
        for m_key, m_material in self._materials.items():
            m_filesDict = dcc.getMaterialFiles(m_material._treeID)
            for m_file, m_type in m_filesDict.items():
                self._fileID += 1
                m_fileItem = I3DFileNode(self._fileID,m_file,m_type)
                self._files[m_fileItem._treeID] = m_fileItem

    def generateInstances(self):
        for m_treeID in self.traverse(m_node="DEPTH"):
            m_treeItem   = self._nodes[m_treeID]
            m_data       = m_treeItem._data
            if ("TYPE_INSTANCER" == m_data["type"]):
                m_nodes = getInstances(m_treeID)
                for m_i in range(len(m_nodes)):
                    self._nodeID +=1
                    m_node = m_nodes[m_i]
                    m_treeItemNew   = I3DSceneNode(m_node["fullPathNameOrig"],m_treeID,self._nodeID)
                    m_treeItemNew._treeID = "{}_{}".format(m_treeItemNew._treeID,m_i)
                    m_treeItemNew._data['fullPathNameOrig'] = m_node["fullPathNameOrig"]
                    m_treeItemNew._data['translation']      = m_node["translation"]
                    m_treeItemNew._data['rotation']         = m_node["rotation"]
                    m_treeItemNew._data['scale']            = m_node["scale"]
                    self._nodes[m_treeItemNew._treeID] = m_treeItemNew
                    m_treeParent = self._nodes[m_treeItemNew._parent]
                    m_treeParent.addChild(m_treeItemNew._treeID)

    def checkUI(self, m_treeItem ):
        m_data       = m_treeItem._data
        if ("TYPE_LIGHT" == m_data["type"] and
            (False==UIGetAttrBool('I3D_exportLights'))):
            m_data["type"] = "TYPE_TRANSFORM_GROUP"
        elif ("TYPE_CAMERA" == m_data["type"] and
            (False==UIGetAttrBool('I3D_exportCameras'))):
            m_data["type"] = "TYPE_TRANSFORM_GROUP"
        elif ("TYPE_NURBS_CURVE" == m_data["type"] and
            (False==UIGetAttrBool('I3D_exportNurbsCurves'))):
            m_data["type"] = "TYPE_TRANSFORM_GROUP"
        elif (("TYPE_MESH" == m_data["type"]
            or "TYPE_NURBS_CURVE" == m_data["type"]
            or "TYPE_MERGED_MESH" == m_data["type"]
            or "TYPE_SPLIT_SHAPE" == m_data["type"]
            or "TYPE_INSTANCER"   == m_data["type"])
            and (False==UIGetAttrBool('I3D_exportShapes'))):
            m_data["type"] = "TYPE_TRANSFORM_GROUP"
        elif ("TYPE_EMITTER" == m_data["type"] and
            (False==UIGetAttrBool('I3D_exportParticleSystems'))):
            m_data["type"] = "TYPE_TRANSFORM_GROUP"
        elif ("TYPE_MERGED_MESH" == m_data["type"] and
            (False==UIGetAttrBool('I3D_exportMergeGroups'))):
            m_data["type"] = "TYPE_MESH"

    def removeNode(self,m_treeID):
        m_treeItem   = self._nodes[m_treeID]
        m_treeParent = self._nodes[m_treeItem._parent]
        m_treeChildren = m_treeItem._children
        for m_treeChild in m_treeChildren:
            self.removeNode(m_treeChild)
        m_treeParent.removeChild(m_treeItem._treeID)
        del self._nodes[m_treeItem._treeID]

    def traverse(self, m_treeID = "ROOT", m_node = "DEPTH"):
        yield m_treeID
        m_queue = self._nodes[m_treeID]._children
        while m_queue:
            yield m_queue[0]
            m_expansion = self._nodes[m_queue[0]]._children
            if  "DEPTH" == m_node:
                m_queue = m_expansion + m_queue[1:]  # depth-first
            elif "BREADTH" == m_node:
                m_queue = m_queue[1:] + m_expansion  # width-first

    def display(self, m_treeID = "ROOT", m_depth =0):
        m_treeItem      = self._nodes[m_treeID]
        m_data          = m_treeItem._data
        m_treeChildren  = m_treeItem._children
        dcc.UIAddMessage("    "*m_depth + "{0} {1} {2}".format(m_treeItem._nodeID,m_treeID,m_data["type"]) )
        m_depth += 1
        for m_treeChild in m_treeChildren:
            self.display(m_treeChild,m_depth)

    def xmlWriteScene(self,m_xmlParent,m_treeID="ROOT"):
        m_treeItem      = self._nodes[m_treeID]
        m_treeChildren  = m_treeItem._children
        for m_treeChildID in m_treeChildren:
            m_treeChildItem = self._nodes[m_treeChildID]
            m_data          = m_treeChildItem._data
            if ("TYPE_LIGHT" == m_data["type"]):
                m_xmlCurrent  = xml_ET.SubElement( m_xmlParent, "Light" )
                self._xmlWriteSceneObject_Light( m_treeChildItem, m_xmlCurrent )
            elif ("TYPE_CAMERA" == m_data["type"]):
                m_xmlCurrent  = xml_ET.SubElement( m_xmlParent, "Camera" )
                self._xmlWriteSceneObject_Camera( m_treeChildItem, m_xmlCurrent )
            elif ("TYPE_MESH" == m_data["type"]):
                m_xmlCurrent  = xml_ET.SubElement( m_xmlParent, "Shape" )
                self._xmlWriteSceneObject_ShapeMesh( m_treeChildItem, m_xmlCurrent )
            elif ("TYPE_NURBS_CURVE" == m_data["type"]):
                m_xmlCurrent  = xml_ET.SubElement( m_xmlParent, "Shape" )
                self._xmlWriteSceneObject_ShapeCurve( m_treeChildItem, m_xmlCurrent )
            else:
                m_xmlCurrent  = xml_ET.SubElement( m_xmlParent, "TransformGroup" )
                self._xmlWriteSceneObject_TransformGroup( m_treeChildItem, m_xmlCurrent )
            self.xmlWriteScene(m_xmlCurrent,m_treeChildID)

    def _xmlWriteSceneObject_General(self, m_treeItem, m_xmlCurrent ):
        m_data = m_treeItem._data
        self._xmlWriteString( m_xmlCurrent, "name",        m_data["name"] )
        self._xmlWriteInt(    m_xmlCurrent ,"nodeId",      m_treeItem._nodeID )
        self._xmlWriteString( m_xmlCurrent, "translation", m_data["translation"] )
        self._xmlWriteString( m_xmlCurrent, "rotation",    m_data["rotation"] )
        self._xmlWriteString( m_xmlCurrent, "scale",       m_data["scale"] )
        if ( "visibility" in m_data):
            if (False == m_data["visibility"]):
                m_xmlCurrent.set( "visibility", "false" )
        if ( "I3D_clipDistance" in m_data): self._xmlWriteAttr( m_xmlCurrent, "clipDistance", m_data, "I3D_clipDistance")
        if ( "I3D_objectMask"   in m_data): self._xmlWriteAttr( m_xmlCurrent, "objectMask",   m_data, "I3D_objectMask")
        if ( "I3D_lightMask" in m_data):
            m_lightMask = int(m_data["I3D_lightMask"],16)
            self._xmlWriteInt( m_xmlCurrent ,"lightMask", m_lightMask )

    def _xmlWriteSceneObject_TransformGroup(self, m_treeItem, m_xmlCurrent):
        self._xmlWriteSceneObject_General(m_treeItem,m_xmlCurrent)
        m_data  = m_treeItem._data
        m_joint = None
        if ( "I3D_joint" in m_data):
            m_joint = m_data["I3D_joint"]
        if ( "I3D_lod" in m_data):
            m_lodDistance = ""
            m_lod1 = 0
            m_lod2 = 0
            m_lod3 = 0
            if ("I3D_lod1" in m_data): m_lod1 = m_data["I3D_lod1"]
            if ("I3D_lod2" in m_data): m_lod2 = m_data["I3D_lod2"]
            if ("I3D_lod3" in m_data): m_lod3 = m_data["I3D_lod3"]
            if ("I3D_lod1" in m_data):
                m_lodDistance = "0 {}".format(m_lod1)
            if (m_lod2 > m_lod1):
                m_lodDistance += " {}".format(m_lod2)
            if (m_lod3 > m_lod2):
                m_lodDistance += " {}".format(m_lod3)
            if (m_lodDistance):
                self._xmlWriteString( m_xmlCurrent, "lodDistance", m_lodDistance )
                m_joint = None
        if (m_joint):
            if ( "I3D_projection"       in m_data): self._xmlWriteAttr( m_xmlCurrent, "projection",       m_data, "I3D_projection" )
            if ( "I3D_xAxisDrive"       in m_data): self._xmlWriteAttr( m_xmlCurrent, "xAxisDrive",       m_data, "I3D_xAxisDrive" )
            if ( "I3D_yAxisDrive"       in m_data): self._xmlWriteAttr( m_xmlCurrent, "yAxisDrive",       m_data, "I3D_yAxisDrive" )
            if ( "I3D_zAxisDrive"       in m_data): self._xmlWriteAttr( m_xmlCurrent, "zAxisDrive",       m_data, "I3D_zAxisDrive" )
            if ( "I3D_drivePos"         in m_data): self._xmlWriteAttr( m_xmlCurrent, "drivePos",         m_data, "I3D_drivePos" )
            if ( "I3D_breakableJoint"   in m_data): self._xmlWriteAttr( m_xmlCurrent, "breakableJoint",   m_data, "I3D_breakableJoint" )
            if ( "I3D_projDistance"     in m_data): self._xmlWriteAttr( m_xmlCurrent, "projDistance",     m_data, "I3D_projDistance" )
            if ( "I3D_projAngle"        in m_data): self._xmlWriteAttr( m_xmlCurrent, "projAngle",        m_data, "I3D_projAngle" )
            if ( "I3D_driveForceLimit"  in m_data): self._xmlWriteAttr( m_xmlCurrent, "driveForceLimit",  m_data, "I3D_driveForceLimit" )
            if ( "I3D_driveSpring"      in m_data): self._xmlWriteAttr( m_xmlCurrent, "driveSpring",      m_data, "I3D_driveSpring" )
            if ( "I3D_driveDamping"     in m_data): self._xmlWriteAttr( m_xmlCurrent, "driveDamping",     m_data, "I3D_driveDamping" )
            if ( "I3D_jointBreakForce"  in m_data): self._xmlWriteAttr( m_xmlCurrent, "jointBreakForce",  m_data, "I3D_jointBreakForce" )
            if ( "I3D_jointBreakTorque" in m_data): self._xmlWriteAttr( m_xmlCurrent, "jointBreakTorque", m_data, "I3D_jointBreakTorque" )

    def _xmlWriteSceneObject_Light(self, m_treeItem, m_xmlCurrent):
        self._xmlWriteSceneObject_General(m_treeItem,m_xmlCurrent)
        m_data  = m_treeItem._data
        if ( "lightData" in m_data):
            m_light = m_data["lightData"]
            for key,value in m_light.items():
                self._xmlWriteString( m_xmlCurrent, key, value )

    def _xmlWriteSceneObject_Camera( self, m_treeItem, m_xmlCurrent ):
        self._xmlWriteSceneObject_General(m_treeItem,m_xmlCurrent)
        m_data  = m_treeItem._data
        if ( "cameraData" in m_data):
            m_camera = m_data["cameraData"]
            for key,value in m_camera.items():
                self._xmlWriteString( m_xmlCurrent, key, value )

    def _xmlWriteSceneObject_ShapeMesh(self, m_treeItem, m_xmlCurrent):
        self._xmlWriteSceneObject_General(m_treeItem,m_xmlCurrent)
        m_data  = m_treeItem._data
        m_shapeStr      = dcc.getShapeNode(m_data)
        m_shapeID       = self._shapes[m_shapeStr]._shapeID
        m_materialsList = self._shapes[m_shapeStr]._data["Materials"]
        # -------------------------------------------------------------
        m_list = []
        for m_mat in m_materialsList:
            m_matID = self._materials[m_mat]._materialID
            m_list.append(m_matID)
        m_materialIDs = ','.join(map(str, m_list))
        # -------------------------------------------------------------
        m_rigidBody = False
        m_static    = False
        m_kinematic = False
        m_dynamic   = False
        m_compound  = False
        m_compoundChild = False
        if ( "I3D_static" in m_data):
            m_static    = m_data["I3D_static"]
        if ( "I3D_kinematic" in m_data):
            m_kinematic = m_data["I3D_kinematic"]
        if ( "I3D_dynamic" in m_data):
            m_dynamic   = m_data["I3D_dynamic"]
        if ( "I3D_compound" in m_data):
            m_compound  = m_data["I3D_compound"]
        if ( "I3D_compoundChild" in m_data):
            m_compoundChild = m_data["I3D_compoundChild"]
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
        self._xmlWriteInt( m_xmlCurrent ,"shapeId", m_shapeID )
        if ( m_static )        : self._xmlWriteString( m_xmlCurrent, "static",        "true" )
        if ( m_dynamic )       : self._xmlWriteString( m_xmlCurrent, "dynamic",       "true" )
        if ( m_kinematic )     : self._xmlWriteString( m_xmlCurrent, "kinematic",     "true" )
        if ( m_compound )      : self._xmlWriteString( m_xmlCurrent, "compound",      "true" )
        if ( m_compoundChild ) : self._xmlWriteString( m_xmlCurrent, "compoundChild", "true" )
        if ( m_rigidBody ):
            if ( "I3D_restitution" in m_data):          self._xmlWriteAttr( m_xmlCurrent, "restitution",          m_data, "I3D_restitution" )
            if ( "I3D_staticFriction" in m_data):       self._xmlWriteAttr( m_xmlCurrent, "staticFriction",       m_data, "I3D_staticFriction" )
            if ( "I3D_dynamicFriction" in m_data):      self._xmlWriteAttr( m_xmlCurrent, "dynamicFriction",      m_data, "I3D_dynamicFriction" )
            if ( "I3D_linearDamping" in m_data):        self._xmlWriteAttr( m_xmlCurrent, "linearDamping",        m_data, "I3D_linearDamping" )
            if ( "I3D_angularDamping" in m_data):       self._xmlWriteAttr( m_xmlCurrent, "angularDamping",       m_data, "I3D_angularDamping" )
            if ( "I3D_density" in m_data):              self._xmlWriteAttr( m_xmlCurrent, "density",              m_data, "I3D_density" )
            if ( "I3D_ccd" in m_data):                  self._xmlWriteAttr( m_xmlCurrent, "ccd",                  m_data, "I3D_ccd" )
            if ( "I3D_solverIterationCount" in m_data): self._xmlWriteAttr( m_xmlCurrent, "solverIterationCount", m_data, "I3D_solverIterationCount" )
        if ( "I3D_collision" in m_data):      self._xmlWriteAttr( m_xmlCurrent, "collision",      m_data, "I3D_collision" )
        if ( "I3D_trigger" in m_data):        self._xmlWriteAttr( m_xmlCurrent, "trigger",        m_data, "I3D_trigger" )
        if ( "I3D_nonRenderable" in m_data):  self._xmlWriteAttr( m_xmlCurrent, "nonRenderable",  m_data, "I3D_nonRenderable" )
        if ( "I3D_castsShadows" in m_data):   self._xmlWriteAttr( m_xmlCurrent, "castsShadows",   m_data, "I3D_castsShadows" )
        if ( "I3D_receiveShadows" in m_data): self._xmlWriteAttr( m_xmlCurrent, "receiveShadows", m_data, "I3D_receiveShadows" )
        if ( "I3D_cpuMesh" in m_data):        self._xmlWriteAttr( m_xmlCurrent, "cpuMesh",        m_data, "I3D_cpuMesh" )
        if ( "I3D_decalLayer" in m_data):     self._xmlWriteAttr( m_xmlCurrent, "decalLayer",     m_data, "I3D_decalLayer" )
        if ( "I3D_collisionMask" in m_data):  self._xmlWriteAttr( m_xmlCurrent, "collisionMask",  m_data, "I3D_collisionMask" )
        m_splitMinU = 0
        m_splitMinV = 0
        m_splitMaxU = 1
        m_splitMaxV = 1
        m_splitUvWorldScale = 1
        if ( "I3D_splitMinU" in m_data): m_splitMinU = m_data["I3D_splitMinU"]
        if ( "I3D_splitMinV" in m_data): m_splitMinV = m_data["I3D_splitMinV"]
        if ( "I3D_splitMaxU" in m_data): m_splitMaxU = m_data["I3D_splitMaxU"]
        if ( "I3D_splitMaxV" in m_data): m_splitMaxV = m_data["I3D_splitMaxV"]
        if ( "I3D_splitUvWorldScale" in m_data): m_splitUvWorldScale = m_data["I3D_splitUvWorldScale"]
        if ( "I3D_splitType" in m_data):
            self._xmlWriteAttr( m_xmlCurrent, "splitType", m_data, "I3D_splitType" )
            m_str = "{} {} {} {} {}".format(m_splitMinU,m_splitMinV,m_splitMaxU,m_splitMaxV,m_splitUvWorldScale)
            self._xmlWriteString( m_xmlCurrent, "splitUvs", m_str )
        self._xmlWriteString( m_xmlCurrent, "materialIds", m_materialIDs )

    def _xmlWriteSceneObject_ShapeCurve(self, m_treeItem, m_xmlCurrent):
        self._xmlWriteSceneObject_General(m_treeItem,m_xmlCurrent)
        m_data     = m_treeItem._data
        m_shapeStr = dcc.getShapeNode(m_data)
        m_shapeID  = self._shapes[m_shapeStr]._shapeID
        self._xmlWriteInt( m_xmlCurrent,"shapeId", m_shapeID )

    def xmlWriteFiles(self,m_xmlParent):
        for m_key, m_file in self._files.items():
            m_xmlCurrent = xml_ET.SubElement( m_xmlParent, "File" )
            m_data       = m_file._data
            self._xmlWriteInt(    m_xmlCurrent, "fileId",       m_file._fileID )
            self._xmlWriteString( m_xmlCurrent, "relativePath", m_data["relativePath"]  )
            self._xmlWriteString( m_xmlCurrent, "filename",     m_data["filename"]  )

    def xmlWriteMaterials(self,m_xmlParent):
        for m_key, m_material in self._materials.items():
            m_xmlCurrent = xml_ET.SubElement( m_xmlParent, "Material" )
            m_data       = m_material._data
            self._xmlWriteInt(    m_xmlCurrent, "materialId",    m_material._materialID )
            self._xmlWriteString( m_xmlCurrent, "name",          m_data["name"]  )
            self._xmlWriteString( m_xmlCurrent, "diffuseColor",  m_data["diffuseColor"]  )
            self._xmlWriteString( m_xmlCurrent, "specularColor", m_data["specularColor"]  )
            if ( "emissiveColor" in m_data): self._xmlWriteString( m_xmlCurrent, "emissiveColor", m_data["emissiveColor"] )
            if ( "alphaBlending" in m_data): self._xmlWriteString( m_xmlCurrent, "alphaBlending", m_data["alphaBlending"] )
            for m_item in ["Texture","Glossmap","Normalmap"]:
                if ( m_item in m_data):
                    m_xmlChild = xml_ET.SubElement( m_xmlCurrent, m_item )
                    m_fileID = self._files[m_data[m_item]]._fileID
                    self._xmlWriteInt( m_xmlChild, "fileId", m_fileID )
            if ( "customShaderVariation" in m_data): self._xmlWriteString( m_xmlCurrent, "customShaderVariation", m_data["customShaderVariation"] )
            if ( "CustomParameter" in m_data):
                for m_key, m_value in m_data["CustomParameter"].items():
                    m_xmlChild = xml_ET.SubElement( m_xmlCurrent, "CustomParameter" )
                    self._xmlWriteString( m_xmlChild, "name",  m_key )
                    self._xmlWriteString( m_xmlChild, "value", m_value )
            if ( "customShader" in m_data):
                m_fileID = self._files[m_data["customShader"]]._fileID
                self._xmlWriteInt( m_xmlCurrent, "customShaderId", m_fileID )
            if ("Custommap" in m_data):
                for m_key, m_value in m_data["Custommap"].items():
                    m_xmlChild = xml_ET.SubElement( m_xmlCurrent, "Custommap" )
                    m_fileID = self._files[m_value]._fileID
                    self._xmlWriteString( m_xmlChild, "name",   m_key )
                    self._xmlWriteInt(    m_xmlChild, "fileId", m_fileID )

    def xmlWriteShapes(self,m_xmlParent):
        for m_key, m_shape in self._shapes.items():
            #dcc.UIAddMessage("{1} {0} {2}".format( m_key, m_shape._shapeID, m_shape._treeID ))
            if "TYPE_MESH" == m_shape._shapeType:
                self._xmlWriteShape_Mesh( m_xmlParent, m_shape )
            if "TYPE_NURBS_CURVE" == m_shape._shapeType:
                self._xmlWriteShape_Curve( m_xmlParent, m_shape )

    def xmlWriteUserAttributes(self,m_xmlParent):
        for m_treeID in self.traverse(m_node="DEPTH"):
            m_treeItem   = self._nodes[m_treeID]
            m_attributes = dcc.getNodeUserAttributes(m_treeID)
            if len(m_attributes):
                m_xmlCurrent  = xml_ET.SubElement( m_xmlParent, "UserAttribute" )
                self._xmlWriteInt( m_xmlCurrent, "nodeId", m_treeItem._nodeID )
                for m_attr in m_attributes:
                    m_xmlAttr  = xml_ET.SubElement( m_xmlCurrent, "Attribute" )
                    self._xmlWriteString( m_xmlAttr, "name",  m_attr["name"] )
                    self._xmlWriteString( m_xmlAttr, "type",  m_attr["type"] )
                    self._xmlWriteString( m_xmlAttr, "value", m_attr["value"] )

    def  _xmlWriteShape_Curve(self, m_xmlParent, m_shape):
        m_xmlCurrent  = xml_ET.SubElement( m_xmlParent, "NurbsCurve" )
        m_data = m_shape._data
        #m_data = getShapeData(m_shape._treeID,m_shape._shapeType)
        self._xmlWriteInt(    m_xmlCurrent, "shapeId", m_shape._shapeID )
        self._xmlWriteString( m_xmlCurrent, "name",    m_data["name"]  )
        self._xmlWriteString( m_xmlCurrent, "degree",  m_data["degree"]  )
        self._xmlWriteString( m_xmlCurrent, "form",    m_data["form"]  )
        for m_point in m_data["points"]:
            m_xmlItem = xml_ET.SubElement( m_xmlCurrent,  "cv" )
            self._xmlWriteString( m_xmlItem, "c", m_point )

    def _xmlWriteShape_Mesh(self, m_xmlParent, m_shape):
        m_xmlCurrent  = xml_ET.SubElement( m_xmlParent, "IndexedTriangleSet" )
        m_data = m_shape._data
        #m_data = getShapeData(m_shape._treeID,m_shape._shapeType)
        self._xmlWriteInt(    m_xmlCurrent, "shapeId",     m_shape._shapeID )
        self._xmlWriteString( m_xmlCurrent, "name",        m_data["name"]  )
        self._xmlWriteString( m_xmlCurrent, "isOptimized", m_data["isOptimized"]  )
        self._xmlWriteString( m_xmlCurrent, "bvCenter",    m_data["bvCenter"]  )
        self._xmlWriteString( m_xmlCurrent, "bvRadius",    m_data["bvRadius"]  )
        m_vertices  = m_data["Vertices"]
        m_triangles = m_data["Triangles"]
        m_subsets   = m_data["Subsets"]
        # -------------------------------------------------------------
        m_xmlVertices  = xml_ET.SubElement( m_xmlCurrent, "Vertices" )
        self._xmlWriteString( m_xmlVertices, "count", m_vertices["count"]  )
        if ( "normal" in m_vertices ):
            self._xmlWriteString( m_xmlVertices, "normal",  "true" )
            self._xmlWriteString( m_xmlVertices, "tangent", "true" )
        if ( "uv0" in m_vertices ):   self._xmlWriteString( m_xmlVertices, "uv0",   "true" )
        if ( "uv1" in m_vertices ):   self._xmlWriteString( m_xmlVertices, "uv1",   "true" )
        if ( "uv2" in m_vertices ):   self._xmlWriteString( m_xmlVertices, "uv2",   "true" )
        if ( "uv3" in m_vertices ):   self._xmlWriteString( m_xmlVertices, "uv3",   "true" )
        if ( "color" in m_vertices ): self._xmlWriteString( m_xmlVertices, "color", "true" )
        for m_vert in m_vertices["data"]:
            m_xmlV  = xml_ET.SubElement( m_xmlVertices, "v" )
            self._xmlWriteString( m_xmlV, "p", m_vert["p"]  )
            if ( "normal" in m_vertices ): self._xmlWriteString( m_xmlV, "n",  m_vert["n"] )
            if ( "color"  in m_vertices ): self._xmlWriteString( m_xmlV, "c",  m_vert["c"] )
            if ( "uv0"    in m_vertices ): self._xmlWriteString( m_xmlV, "t0", m_vert["t0"] )
            if ( "uv1"    in m_vertices ): self._xmlWriteString( m_xmlV, "t1", m_vert["t1"] )
            if ( "uv2"    in m_vertices ): self._xmlWriteString( m_xmlV, "t2", m_vert["t2"] )
            if ( "uv3"    in m_vertices ): self._xmlWriteString( m_xmlV, "t3", m_vert["t3"] )
        # -------------------------------------------------------------
        m_xmlTriangles = xml_ET.SubElement( m_xmlCurrent, "Triangles" )
        self._xmlWriteString( m_xmlTriangles, "count", m_triangles["count"]  )
        for m_tri in m_triangles["data"]:
            m_xmlT  = xml_ET.SubElement( m_xmlTriangles, "t" )
            self._xmlWriteString( m_xmlT, "vi", m_tri["vi"]  )
        # -------------------------------------------------------------
        m_xmlSubsets   = xml_ET.SubElement( m_xmlCurrent, "Subsets" )
        self._xmlWriteString( m_xmlSubsets, "count", m_subsets["count"]  )
        for m_subs in m_subsets["data"]:
            m_xmlS = xml_ET.SubElement( m_xmlSubsets, "Subset" )
            self._xmlWriteString( m_xmlS, "firstVertex", m_subs["firstVertex"]  )
            self._xmlWriteString( m_xmlS, "numVertices", m_subs["numVertices"]  )
            self._xmlWriteString( m_xmlS, "firstIndex",  m_subs["firstIndex"]  )
            self._xmlWriteString( m_xmlS, "numIndices",  m_subs["numIndices"]  )

    def _xmlWriteAttr(self, m_xmlCurrent, m_attrStr, m_data, m_valStr ):
        m_type = SETTINGS_ATTRIBUTES[m_valStr]['type']
        if (TYPE_BOOL == m_type):
            self._xmlWriteBool(m_xmlCurrent,m_attrStr,m_data[m_valStr])
        elif(TYPE_INT == m_type):
            self._xmlWriteInt(m_xmlCurrent,m_attrStr,m_data[m_valStr])
        elif(TYPE_FLOAT == m_type):
            self._xmlWriteFloat(m_xmlCurrent,m_attrStr,m_data[m_valStr])
        elif(TYPE_STRING == m_type):
            self._xmlWriteString(m_xmlCurrent,m_attrStr,m_data[m_valStr])

    @staticmethod
    def _xmlWriteBool( m_xmlCurrent, m_attrStr, m_val ):
        if ( m_val ):
            m_xmlCurrent.set( m_attrStr , "true" )
        else:
            m_xmlCurrent.set( m_attrStr , "false" )

    @staticmethod
    def _xmlWriteInt( m_xmlCurrent, m_attrStr, m_val ):
        m_xmlCurrent.set( m_attrStr, "{:d}".format(m_val) )

    @staticmethod
    def _xmlWriteFloat( m_xmlCurrent, m_attrStr, m_val ):
        m_xmlCurrent.set( m_attrStr, "{}".format(m_val) )

    @staticmethod
    def _xmlWriteString( m_xmlCurrent, m_attrStr, m_val ):
        m_xmlCurrent.set( m_attrStr, m_val )
#------------------------------------------------------------------------
#------------------------------------------------------------------------
#------------------------------------------------------------------------
class I3DIOexport( object ):
    __instance = None
    def __new__(cls):
        if cls.__instance == None:
            cls.__instance = object.__new__(cls)
        return cls.__instance

    def __init__( self ):
        self._fileID          = 0
        self._nodeID          = 0
        self._shapeID         = 0
        self._dynamicsID      = 0
        self._sceneGraph      = I3DSceneGraph()
        self._exportSelection = False

    def export( self, m_exportSelection = False ):
        self._exportSelection = m_exportSelection
        self._generateSceneGraph()
        self._xmlBuild()

    def _generateSceneGraph(self):
        self._objectsToExportList = dcc.getAllNodesToExport()
        if (self._exportSelection):
            self._objectsToExportList = dcc.getSelectedNodesToExport()
        # add nodes to the sceneGraph
        for m_node in self._objectsToExportList:
            if (dcc.isParentedToWorld(m_node)):
                self._generateSceneGraphItem(m_node,"ROOT")
        # ------
        self._sceneGraph.generateInstances()
        #self._sceneGraph.display()
        self._sceneGraph.generateShapes()
        self._sceneGraph.generateMaterials()
        self._sceneGraph.generateFiles()

    def _generateSceneGraphItem(self,m_node,m_parent):
        self._sceneGraph.addNode(m_node,m_parent)
        for m_child in dcc.getChildObjects(m_node):
            if (m_child in self._objectsToExportList):
                self._generateSceneGraphItem(m_child,m_node)

    def _xmlWriteFiles(self):
        self._sceneGraph.xmlWriteFiles(self._xml_files)

    def _xmlWriteMaterials(self):
        self._sceneGraph.xmlWriteMaterials(self._xml_materials)

    def _xmlWriteShapes(self):
        self._sceneGraph.xmlWriteShapes(self._xml_shapes)

    def _xmlWriteDynamics(self):
        pass

    def _xmlWriteAnimation(self):
        pass

    def _xmlWriteUserAttributes(self):
        self._sceneGraph.xmlWriteUserAttributes(self._xml_userAttributes)

    def _xmlWriteScene(self):
        self._sceneGraph.xmlWriteScene(self._xml_scene)
        '''
        for m_node in self._sceneGraph.traverse(m_node="DEPTH"):
            print(m_node)
        for m_node in self._sceneGraph.traverse(m_node="BREADTH"):
            print(m_node)
        '''

    def _xmlBuild( self ):
        # i3D
        self._xml_i3d = xml_ET.Element( "i3D" )
        if (dcc.isFileSaved()):
            m_name = dcc.getFileBasename()
        else:
            m_name = "untitled"
        self._xml_i3d.set( "name", m_name )
        self._xml_i3d.set( "version", "1.6" )
        self._xml_i3d.set( "xsi:noNamespaceSchemaLocation", "http://i3d.giants.ch/schema/i3d-1.6.xsd" )
        self._xml_i3d.set( "xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance" )
        # Asset
        self._xml_asset    = xml_ET.SubElement( self._xml_i3d,   "Asset" )
        self._xml_software = xml_ET.SubElement( self._xml_asset, "Export" )
        self._xml_software.set( "program", DCC_PLATFORM )
        self._xml_software.set( "version", "{0}".format( dcc.appVersion() ) )
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
        if ( UIGetAttrBool("I3D_exportParticleSystems") ):
            self._xml_dynamics   = xml_ET.SubElement( self._xml_i3d, "Dynamics" )
            self._xmlWriteDynamics()
        # Scene
        self._xml_scene          = xml_ET.SubElement( self._xml_i3d, "Scene" )
        self._xmlWriteScene()
        # Animation
        if ( UIGetAttrBool("I3D_exportAnimation") ):
            self._xml_animation  = xml_ET.SubElement( self._xml_i3d, "Animation" )
            self._xmlWriteAnimation()
        # UserAttributes
        if ( UIGetAttrBool("I3D_exportUserAttributes") ):
            self._xml_userAttributes = xml_ET.SubElement( self._xml_i3d, "UserAttributes" )
            self._xmlWriteUserAttributes()
        self._indent( self._xml_i3d ) #prettyprint
        self._xml_tree = xml_ET.ElementTree( self._xml_i3d )
        if ( UIGetAttrBool('I3D_exportUseSoftwareFileName') ):
            if ( dcc.isFileSaved() ):
                m_filepath = dcc.getFilePath()
            else:
                m_filepath = "c:/tmp/untitled.i3d"
        else:
            m_filepath = os.path.abspath( UIGetAttrString("I3D_exportFileLocation") )
            m_filepath = "{0}.i3d".format(os.path.splitext(m_filepath)[0])
        try:
            m_fwrite = open(m_filepath,'w')
            m_fwrite.close()
        except IOError:
            dcc.UIShowError('Could not open file: {0}'.format(m_filepath))
            return 1
        try:
            self._xml_tree.write( m_filepath, xml_declaration = True, encoding = "iso-8859-1", method = "xml" )
            dcc.UIAddMessage('Exported to {0}'.format(m_filepath))
        except Exception as m_exception:
            dcc.UIShowError(m_exception)
            return 1
        return 0

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
                I3DIOexport._indent( elem, level + 1 )
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i