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

from io_export_i3d import DCC_PLATFORM as DCC_PLATFORM

if   "houdini" == DCC_PLATFORM:
    from . import dccHoudini as dcc
elif "blender" == DCC_PLATFORM:
    from . import dccBlender as dcc
    
#-------------------------------------------------------------------------------
#   Globals
#-------------------------------------------------------------------------------
TYPE_BOOL   = 1
TYPE_INT    = 2
TYPE_FLOAT  = 3
TYPE_STRING = 4
    
SETTINGS_ATTRIBUTES = {}
SETTINGS_ATTRIBUTES['I3D_static']               = {'type':TYPE_BOOL,  'defaultValue':True   }
SETTINGS_ATTRIBUTES['I3D_dynamic']              = {'type':TYPE_BOOL,  'defaultValue':False  }
SETTINGS_ATTRIBUTES['I3D_kinematic']            = {'type':TYPE_BOOL,  'defaultValue':False  }
SETTINGS_ATTRIBUTES['I3D_compound']             = {'type':TYPE_BOOL,  'defaultValue':False  }
SETTINGS_ATTRIBUTES['I3D_compoundChild']        = {'type':TYPE_BOOL,  'defaultValue':False  }
SETTINGS_ATTRIBUTES['I3D_collision']            = {'type':TYPE_BOOL,  'defaultValue':True   }
SETTINGS_ATTRIBUTES['I3D_collisionMask']        = {'type':TYPE_INT,   'defaultValue':255    }
SETTINGS_ATTRIBUTES['I3D_solverIterationCount'] = {'type':TYPE_INT,   'defaultValue':4      }
SETTINGS_ATTRIBUTES['I3D_restitution']          = {'type':TYPE_FLOAT, 'defaultValue':0      }
SETTINGS_ATTRIBUTES['I3D_staticFriction']       = {'type':TYPE_FLOAT, 'defaultValue':0.5    }
SETTINGS_ATTRIBUTES['I3D_dynamicFriction']      = {'type':TYPE_FLOAT, 'defaultValue':0.5    }
SETTINGS_ATTRIBUTES['I3D_linearDamping']        = {'type':TYPE_FLOAT, 'defaultValue':0.0    }
SETTINGS_ATTRIBUTES['I3D_angularDamping']       = {'type':TYPE_FLOAT, 'defaultValue':0.01   }
SETTINGS_ATTRIBUTES['I3D_density']              = {'type':TYPE_FLOAT, 'defaultValue':1.0    }
SETTINGS_ATTRIBUTES['I3D_ccd']                  = {'type':TYPE_BOOL,  'defaultValue':False  }
SETTINGS_ATTRIBUTES['I3D_trigger']              = {'type':TYPE_BOOL,  'defaultValue':False  }
SETTINGS_ATTRIBUTES['I3D_splitType']            = {'type':TYPE_INT,   'defaultValue':0      }
SETTINGS_ATTRIBUTES['I3D_splitMinU']            = {'type':TYPE_FLOAT, 'defaultValue':0.0    }
SETTINGS_ATTRIBUTES['I3D_splitMinV']            = {'type':TYPE_FLOAT, 'defaultValue':0.0    }
SETTINGS_ATTRIBUTES['I3D_splitMaxU']            = {'type':TYPE_FLOAT, 'defaultValue':1.0    }
SETTINGS_ATTRIBUTES['I3D_splitMaxV']            = {'type':TYPE_FLOAT, 'defaultValue':1.0    }
SETTINGS_ATTRIBUTES['I3D_splitUvWorldScale']    = {'type':TYPE_FLOAT, 'defaultValue':1.0    }
SETTINGS_ATTRIBUTES['I3D_joint']                = {'type':TYPE_BOOL,  'defaultValue':False  }
SETTINGS_ATTRIBUTES['I3D_projection']           = {'type':TYPE_BOOL,  'defaultValue':False  }
SETTINGS_ATTRIBUTES['I3D_projDistance']         = {'type':TYPE_FLOAT, 'defaultValue':0.01   }
SETTINGS_ATTRIBUTES['I3D_projAngle']            = {'type':TYPE_FLOAT, 'defaultValue':0.01   }
SETTINGS_ATTRIBUTES['I3D_xAxisDrive']           = {'type':TYPE_BOOL,  'defaultValue':False  }
SETTINGS_ATTRIBUTES['I3D_yAxisDrive']           = {'type':TYPE_BOOL,  'defaultValue':False  }
SETTINGS_ATTRIBUTES['I3D_zAxisDrive']           = {'type':TYPE_BOOL,  'defaultValue':False  }
SETTINGS_ATTRIBUTES['I3D_drivePos']             = {'type':TYPE_BOOL,  'defaultValue':False  }
SETTINGS_ATTRIBUTES['I3D_driveForceLimit']      = {'type':TYPE_FLOAT, 'defaultValue':100000 }
SETTINGS_ATTRIBUTES['I3D_driveSpring']          = {'type':TYPE_FLOAT, 'defaultValue':1.0    }
SETTINGS_ATTRIBUTES['I3D_driveDamping']         = {'type':TYPE_FLOAT, 'defaultValue':0.01   }
SETTINGS_ATTRIBUTES['I3D_breakableJoint']       = {'type':TYPE_BOOL,  'defaultValue':False  }
SETTINGS_ATTRIBUTES['I3D_jointBreakForce']      = {'type':TYPE_FLOAT, 'defaultValue':0.0    }
SETTINGS_ATTRIBUTES['I3D_jointBreakTorque']     = {'type':TYPE_FLOAT, 'defaultValue':0.0    }
SETTINGS_ATTRIBUTES['I3D_oc']                   = {'type':TYPE_BOOL,  'defaultValue':False  }
SETTINGS_ATTRIBUTES['I3D_castsShadows']         = {'type':TYPE_BOOL,  'defaultValue':False  }
SETTINGS_ATTRIBUTES['I3D_receiveShadows']       = {'type':TYPE_BOOL,  'defaultValue':False  }
SETTINGS_ATTRIBUTES['I3D_nonRenderable']        = {'type':TYPE_BOOL,  'defaultValue':False  }
SETTINGS_ATTRIBUTES['I3D_clipDistance']         = {'type':TYPE_FLOAT, 'defaultValue':0      }
SETTINGS_ATTRIBUTES['I3D_objectMask']           = {'type':TYPE_INT,   'defaultValue':255    }
SETTINGS_ATTRIBUTES['I3D_lightMask']            = {'type':TYPE_STRING,'defaultValue':'FFFF' }
SETTINGS_ATTRIBUTES['I3D_decalLayer']           = {'type':TYPE_INT,   'defaultValue':0      }
SETTINGS_ATTRIBUTES['I3D_mergeGroup']           = {'type':TYPE_INT,   'defaultValue':0      }
SETTINGS_ATTRIBUTES['I3D_mergeGroupRoot']       = {'type':TYPE_BOOL,  'defaultValue':False  }
SETTINGS_ATTRIBUTES['I3D_boundingVolume']       = {'type':TYPE_STRING,'defaultValue':''     }
SETTINGS_ATTRIBUTES['I3D_cpuMesh']              = {'type':TYPE_BOOL,  'defaultValue':False  }
SETTINGS_ATTRIBUTES['I3D_lod']                  = {'type':TYPE_BOOL,  'defaultValue':False  }
SETTINGS_ATTRIBUTES['I3D_lod1']                 = {'type':TYPE_FLOAT, 'defaultValue':0      }
SETTINGS_ATTRIBUTES['I3D_lod2']                 = {'type':TYPE_FLOAT, 'defaultValue':0      }
SETTINGS_ATTRIBUTES['I3D_lod3']                 = {'type':TYPE_FLOAT, 'defaultValue':0      }

SETTINGS_UI = {}
SETTINGS_UI['I3D_exportIK']                     = {'type':TYPE_BOOL,  'defaultValue':False  }
SETTINGS_UI['I3D_exportAnimation']              = {'type':TYPE_BOOL,  'defaultValue':True   }
SETTINGS_UI['I3D_exportShapes']                 = {'type':TYPE_BOOL,  'defaultValue':True   }
SETTINGS_UI['I3D_exportNurbsCurves']            = {'type':TYPE_BOOL,  'defaultValue':False  }
SETTINGS_UI['I3D_exportLights']                 = {'type':TYPE_BOOL,  'defaultValue':True   }
SETTINGS_UI['I3D_exportCameras']                = {'type':TYPE_BOOL,  'defaultValue':True   }
SETTINGS_UI['I3D_exportParticleSystems']        = {'type':TYPE_BOOL,  'defaultValue':False  }
SETTINGS_UI['I3D_exportUserAttributes']         = {'type':TYPE_BOOL,  'defaultValue':True   }
SETTINGS_UI['I3D_exportNormals']                = {'type':TYPE_BOOL,  'defaultValue':True   }
SETTINGS_UI['I3D_exportColors']                 = {'type':TYPE_BOOL,  'defaultValue':True   }
SETTINGS_UI['I3D_exportTexCoords']              = {'type':TYPE_BOOL,  'defaultValue':True   }
SETTINGS_UI['I3D_exportSkinWeigths']            = {'type':TYPE_BOOL,  'defaultValue':True   }
SETTINGS_UI['I3D_exportMergeGroups']            = {'type':TYPE_BOOL,  'defaultValue':True   }
SETTINGS_UI['I3D_exportVerbose']                = {'type':TYPE_BOOL,  'defaultValue':True   }
SETTINGS_UI['I3D_exportRelativePaths']          = {'type':TYPE_BOOL,  'defaultValue':True   }
SETTINGS_UI['I3D_exportUseSoftwareFileName']    = {'type':TYPE_BOOL,  'defaultValue':True   }
SETTINGS_UI['I3D_exportFileLocation']           = {'type':TYPE_STRING,'defaultValue':''     }
SETTINGS_UI['I3D_nodeName']                     = {'type':TYPE_STRING,'defaultValue':''     }
SETTINGS_UI['I3D_nodeIndex']                    = {'type':TYPE_STRING,'defaultValue':''     }
#-------------------------------------------------------------------------------
#   UI
#-------------------------------------------------------------------------------
def I3DAttributeValueIsDefault(m_node,m_attr):
    m_val = I3DGetAttributeValue(m_node,m_attr)
    m_default = ""
    if ( m_attr in SETTINGS_ATTRIBUTES):
        m_default = SETTINGS_ATTRIBUTES[m_attr]['defaultValue']
    if ( m_attr in SETTINGS_UI):
        m_default = SETTINGS_UI[m_attr]['defaultValue']
    if (m_default==m_val):
        return True
    else:
        return False

def I3DGetAttributeValue(m_node, m_attr):
    if(dcc.I3DAttributeExists(m_node, m_attr)):
        return dcc.I3DGetAttr(m_node, m_attr)
    else:
        if ( m_attr in SETTINGS_ATTRIBUTES):
            return SETTINGS_ATTRIBUTES[m_attr]['defaultValue']
        if ( m_attr in SETTINGS_UI):
            return SETTINGS_UI[m_attr]['defaultValue']
    return ""

def I3DSaveAttributeBool(m_node, m_attr, m_val):
    if(not dcc.I3DAttributeExists(m_node, m_attr)):
        dcc.I3DAddAttrBool(m_node,m_attr)
    dcc.I3DSetAttrBool(m_node,m_attr,m_val)
    
def I3DSaveAttributeInt(m_node, m_attr, m_val):
    if(not dcc.I3DAttributeExists(m_node, m_attr)):
        dcc.I3DAddAttrInt(m_node,m_attr)
    dcc.I3DSetAttrInt(m_node,m_attr,m_val)
    
def I3DSaveAttributeFloat(m_node, m_attr, m_val):
    if(not dcc.I3DAttributeExists(m_node, m_attr)):
        dcc.I3DAddAttrFloat(m_node,m_attr)
    dcc.I3DSetAttrFloat(m_node,m_attr,m_val)
    
def I3DSaveAttributeString(m_node, m_attr, m_val):
    if(not dcc.I3DAttributeExists(m_node, m_attr)):
        dcc.I3DAddAttrString(m_node,m_attr)
    dcc.I3DSetAttrString(m_node,m_attr,m_val)
    
def I3DLoadObjectAttributes():
    m_nodes = dcc.getSelectedNodes()
    if(0 is not len(m_nodes)):
        m_node = m_nodes[0]
        for k,v in SETTINGS_ATTRIBUTES.items():
            if   v['type'] == TYPE_BOOL:
                dcc.UISetAttrBool(k,I3DGetAttributeValue(m_node, k))
            elif v['type'] == TYPE_INT:
                dcc.UISetAttrInt(k,I3DGetAttributeValue(m_node, k))
            elif v['type'] == TYPE_FLOAT:
                dcc.UISetAttrFloat(k,I3DGetAttributeValue(m_node, k))
            elif v['type'] == TYPE_STRING:
                dcc.UISetAttrString(k,I3DGetAttributeValue(m_node, k))
        dcc.UISetLoadedNode(m_node)
    else:
        dcc.UIShowWarning('Nothing selected')

def I3DSaveObjectAttributes():
    m_node = dcc.UIGetLoadedNode()
    if(None is not m_node):
        I3DSaveAttributes(m_node)
    else:
        dcc.UIShowWarning('Nothing loaded')
        
def I3DRemoveObjectAttributes():
    m_node = dcc.UIGetLoadedNode()
    if(None is not m_node):
        I3DRemoveAttributes(m_node)
        I3DLoadObjectAttributes()
    else:
        dcc.UIShowWarning('Nothing loaded')
        
def I3DApplySelectedAttributes():
    m_nodes = dcc.getSelectedNodes()
    if(0 is not len(m_nodes)):
        for m_node in m_nodes:
            I3DSaveAttributes(m_node)
    else:
        dcc.UIShowWarning('Nothing selected')

def I3DRemoveSelectedAttributes():
    m_nodes = dcc.getSelectedNodes()
    if(0 is not len(m_nodes)):
        for m_node in m_nodes:
            I3DRemoveAttributes(m_node)
        I3DLoadObjectAttributes()
    else:
        dcc.UIShowWarning('Nothing selected')

def I3DRemoveAttributes(m_node):
    for k, v in SETTINGS_ATTRIBUTES.items():
        dcc.I3DRemoveAttribute(m_node, k)
        
def I3DSaveAttributes(m_node):
    for k, v in SETTINGS_ATTRIBUTES.items():
        if   v['type'] == TYPE_BOOL:
            I3DSaveAttributeBool(m_node,   k, UIGetAttrBool(k) )
        elif v['type'] == TYPE_INT:
            I3DSaveAttributeInt(m_node,    k, UIGetAttrInt(k) )
        elif v['type'] == TYPE_FLOAT:
            I3DSaveAttributeFloat(m_node,  k, UIGetAttrFloat(k) )
        elif v['type'] == TYPE_STRING:
            I3DSaveAttributeString(m_node, k, UIGetAttrString(k) )

def UIGetAttrBool(m_attr):
    if dcc.UIAttrExists(m_attr):
        return dcc.UIGetAttrBool(m_attr)
    else:
        if ( m_attr in SETTINGS_ATTRIBUTES):
            return SETTINGS_ATTRIBUTES[m_attr]['defaultValue']
        if ( m_attr in SETTINGS_UI):
            return SETTINGS_UI[m_attr]['defaultValue']
    return False

def UIGetAttrInt(m_attr):
    if dcc.UIAttrExists(m_attr):
        return dcc.UIGetAttrInt(m_attr)
    else:
        if ( m_attr in SETTINGS_ATTRIBUTES):
            return SETTINGS_ATTRIBUTES[m_attr]['defaultValue']
        if ( m_attr in SETTINGS_UI):
            return SETTINGS_UI[m_attr]['defaultValue']
    return int(0)

def UIGetAttrFloat(m_attr):
    if dcc.UIAttrExists(m_attr):
        return dcc.UIGetAttrFloat(m_attr)
    else:
        if ( m_attr in SETTINGS_ATTRIBUTES):
            return SETTINGS_ATTRIBUTES[m_attr]['defaultValue']
        if ( m_attr in SETTINGS_UI):
            return SETTINGS_UI[m_attr]['defaultValue']
    return float(0.0)

def UIGetAttrString(m_attr):
    if dcc.UIAttrExists(m_attr):
        return dcc.UIGetAttrString(m_attr)
    else:
        if ( m_attr in SETTINGS_ATTRIBUTES):
            return SETTINGS_ATTRIBUTES[m_attr]['defaultValue']
        if ( m_attr in SETTINGS_UI):
            return SETTINGS_UI[m_attr]['defaultValue']
    return str("")

def getNodeData(m_node):
    m_nodeData = {}
    m_nodeData["fullPathName"] = "ROOT"
    m_nodeData["name"] = "ROOT"
    m_nodeData["type"] = "TYPE_TRANSFORM_GROUP"
    for key in SETTINGS_ATTRIBUTES.keys():
        if (not I3DAttributeValueIsDefault(m_node,key)):
            m_nodeData[key] = I3DGetAttributeValue(m_node,key)
    if ("ROOT" == m_node):
        return m_nodeData
    m_nodeData = dcc.getNodeData(m_node,m_nodeData)
    m_translation, m_rotation, m_scale = dcc.getNodeTranslationRotationScale( m_node )
    m_nodeData["translation"]   = m_translation
    m_nodeData["rotation"]      = m_rotation
    m_nodeData["scale"]         = m_scale
    m_nodeData["visibility"]    = dcc.isNodeVisible(m_node)
    if ("TYPE_LIGHT"== m_nodeData["type"]):
        m_nodeData["lightData"]  = getLightData(m_node)
    if ("TYPE_CAMERA"== m_nodeData["type"]):
        m_nodeData["cameraData"] = getCameraData(m_node)
    return m_nodeData

def getMaterialData(m_node):
    m_nodeData = {}
    m_nodeData["fullPathName"] = m_node
    m_nodeData["name"] = "default"
    m_nodeData["diffuseColor"]  = "0.5 0.5 0.5 1"
    m_nodeData["specularColor"] = "0 1 0"
    return dcc.getMaterialData(m_node,m_nodeData)

def getFileData(m_node,m_type):
    m_nodeData = {}
    m_nodeData["fullPathName"] = m_node
    m_nodeData["relativePath"] = "false"
    if m_type in ["Texture","Glossmap","Normalmap"]:
        m_nodeData = dcc.getFileData(m_node,m_nodeData)
    else:
        m_nodeData["filename"] = m_node
        m_nodeData["relativePath"] = "true"
    return m_nodeData

def getInstances(m_node):
    m_nodes = dcc.getNodeInstances(m_node)
    return m_nodes

def getShapeData(m_shape,m_type):
    m_nodeData = {}
    m_nodeData["name"]        = "Undefined"
    if ( "TYPE_MESH" == m_type ):
        m_nodeData["isOptimized"] = "false"
        m_nodeData = dcc.getShapeData(m_shape,m_nodeData)
    elif("TYPE_NURBS_CURVE" == m_type):
        m_nodeData["name"]   = "Undefined"
        m_nodeData["degree"] = "3"
        m_nodeData["form"]   = "open"
        m_nodeData = dcc.getNurbsCurveData(m_shape,m_nodeData)
    return m_nodeData

def getLightData(m_node):
    m_light = {}
    m_light["type"]             = "directional"
    m_light["color"]            = "1 1 1"
    m_light["emitDiffuse"]      = "true"
    m_light["emitSpecular"]     = "true"
    m_light["decayRate"]        = "1"
    m_light["range"]            = "100"
    m_light["castShadowMap"]    = "true"
    return  dcc.getLightData(m_node, m_light)

def getCameraData(m_node):
    m_camera = {}
    m_camera["fov"]      = "60"
    m_camera["nearClip"] = "0.1"
    m_camera["farClip"]  = "10000"
    return dcc.getCameraData(m_node, m_camera)
