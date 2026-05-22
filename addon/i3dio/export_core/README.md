# export_core Overview

This package implements the core of the I3D export pipeline for Blender. It is responsible for traversing the Blender scene, building an intermediate representation (IR), resolving all necessary data (geometry, materials, animations, etc.), and serializing the result to the I3D file format.

## Pipeline Stages

1. **Scene Traversal** (`traverse.py`)
   - Traverses the Blender scene graph and collects all relevant objects
   - Respects visibility, selection filters, and collection hierarchy

2. **IR Construction** (`ir/`)
   - Scene converted into an intermediate representation—a tree of `SceneNode` objects
   - `builder.py` provides methods for creating nodes and adding derived shapes
   - `model.py` defines the core data structures (`SceneNode`, `NodeKind`, extensions)

3. **Resolution Passes** (`resolve/`)
   - Multiple passes fill in details on the IR, organized into phases:
     - **basics**: Node kinds, names
     - **structure**: Armatures, merge groups, skinned meshes, curve shapes, shape links, bounding volumes
     - **properties**: Node-specific properties
     - **finalize**: Build shapes, resolve materials, compute vertex requirements
     - **final**: Matrices, animations, i3D mappings, user attributes, files
   - See `resolve/runner.py` for the full pass/phase ordering

4. **Resource Management** (`resources/`)
   - Deduplicated resources managed by tables: `MaterialTable`, `FileTable`, `ShapeTable`
   - Stable IDs assigned for export
   - `ShapeKey` provides keying strategies for different shape modes (normal, merge, skinned, curve)

5. **Geometry Building** (`geometry/`)
   - `mesh/` — Meshes converted to IndexedTriangleSet (`BuiltITS`)
   - `curve/` — NURBS curves built as `BuiltNurbsCurve`
   - `built.py` — Base `BuiltShape` class and `ShapeKind` discriminator

6. **Blender Data Extraction** (`blender/`)
   - `evaluated_mesh.py` — Extract mesh data with proper coordinate transformation
   - `evaluated_curve.py` — Extract curve control points with coordinate transformation
   - `bones.py` — Bone/armature utilities

7. **Serialization** (`serialize/`)
   - IR and resources serialized to I3D XML and binary streams
   - `write_i3d.py` — Main writer, dispatches to geometry-specific writers
   - `indexed_triangle_set_stream.py` — ITS binary format
   - `nurbs_curve_stream.py` — NurbsCurve XML format

---

## Key Concepts

### NodeKind
Every node in the IR has a kind (e.g., `SHAPE`, `GROUP`, `LIGHT`, `CAMERA`).

- After `resolve/kinds`: no `UNRESOLVED` nodes remain
- `set_kind()` is the only way kinds change
- Any `NodeKind.SHAPE` node must have a `_shape` extension (guaranteed by `set_kind()`)

### ShapeMode & ShapeKey
Shapes are deduplicated based on their mode:

| Mode | Description | Key Fields |
|------|-------------|------------|
| `NORMAL` | Single mesh, keyed by datablock | `data_ptr`, `apply_modifiers`, `slot_signature` |
| `MERGE_GROUP` | Multiple meshes merged | `object_ptr` (root) |
| `MERGE_CHILDREN` | Children merged with generic values | `object_ptr` |
| `SKINNED_MESH` | Armature-driven mesh | `object_ptr` (per instance) |
| `NURBS_CURVE` | NURBS curve spline | `object_ptr`, `spline_index` |

### ShapeKind (BuiltShape discriminator)
Built geometry types:

- `INDEXED_TRIANGLE_SET` — Triangulated mesh data
- `NURBS_CURVE` — NURBS curve control points

### One-to-Many Relationships
Some Blender objects produce multiple i3D nodes:

- **Curves with multiple splines**: Each spline becomes a separate `Shape` node via `add_derived_shape()`
- **Merge groups**: Multiple mesh objects merged into one `Shape`

### Coordinate Transformation
Blender uses different coordinate conventions than i3D:

- `blender/evaluated_mesh.py` and `blender/evaluated_curve.py` handle transformation
- Uses `conversion_matrix` (Y-up adjustment) and `unit_scale`
- Respects object hierarchy via `reference_frame`

---

## Resolve Pass Details

### Phase: basics
| Pass | Description |
|------|-------------|
| `kinds` | Determine `NodeKind` for each node based on object type |
| `names` | Finalize unique names for export |

### Phase: structure
| Pass | Description |
|------|-------------|
| `armatures` | Process armature relationships and bone hierarchies |
| `child_of_constraints` | Handle Child-Of constraints targeting bones |
| `merge_children` | Identify and mark merge-children relationships |
| `merge_groups` | Build merge group shapes from multiple objects |
| `skinned_meshes` | Set up skinned mesh bind indices and weights |
| `curve_shapes` | Create derived Shape nodes for each spline in curve objects |
| `shape_links` | Link nodes sharing the same shape data |
| `bounding_volumes` | Compute bounding volumes for mesh shapes |

### Phase: properties
| Pass | Description |
|------|-------------|
| `node_properties` | Resolve node-specific i3D properties |

### Phase: finalize
| Pass | Description |
|------|-------------|
| `build_shapes_then_materials_then_reqs` | Build geometry, finalize material IDs, compute vertex requirements |

### Phase: final
| Pass | Description |
|------|-------------|
| `matrices` | Compute final transformation matrices |
| `animations` | Sample and resolve animations |
| `mappings` | Collect i3D mapping entries |
| `user_attributes` | Resolve user attribute data |
| `files` | Resolve file paths and copy/convert files |

---

## Geometry Types

### IndexedTriangleSet (Meshes)
- Built from `MESH` objects
- Triangulated with proper UV, normal, and vertex color handling
- Supports skinning (bind poses, bone weights)
- See: `geometry/mesh/`

### NurbsCurve
- Built from `CURVE` objects with NURBS/BEZIER/POLY splines
- **Classification**: Curves with bevel/extrusion export as meshes (IndexedTriangleSet)
- **Spline handling**: Each spline in a curve object becomes a separate Shape node
- **Minimum points**: i3D requires ≥3 control points; 2-point curves get a midpoint inserted
- See: `geometry/curve/`, `resolve/shapes/curve_shapes.py`

---

## Extending the Pipeline

### Adding a new geometry type
1. Add a `ShapeMode` variant in `resources/shapes.py`
2. Add a `ShapeKind` variant in `geometry/built.py`
3. Create a `BuiltXxx` dataclass extending `BuiltShape`
4. Implement the build function in `geometry/<type>/`
5. Add coordinate transformation helpers in `blender/` if needed
6. Add a resolve pass in `resolve/shapes/` if the type needs special handling
7. Add serialization in `serialize/` (binary stream or XML writer)
8. Update `serialize/write_i3d.py` to dispatch to the new writer

### Adding a new resolve pass
1. Implement the pass function in the appropriate `resolve/` submodule
2. Register it in `resolve/runner.py` under the correct phase
3. Document dependencies on other passes

### Adding a new node property
1. Add the property to the IR model if needed
2. Create or update a resolve pass to populate it
3. Update serialization to emit the property

---

## File Structure

```
export_core/
├── ctx.py              # ExportContext: shared state for entire export
├── errors.py           # Custom exceptions
├── ids.py              # ID allocation utilities
├── messages.py         # Logging/message severity
├── pipeline.py         # Top-level export orchestration
├── post_export.py      # Post-export actions
├── reporting.py        # Reporter class for logging
├── traverse.py         # Scene traversal logic
│
├── ir/                 # Intermediate Representation
│   ├── model.py        # SceneNode, NodeKind, extensions
│   ├── builder.py      # SceneBuilder: node creation, derived shapes
│   ├── animation.py    # Animation data structures
│   └── helpers.py      # IR utilities
│
├── resolve/            # Resolution passes
│   ├── runner.py       # Pass/phase orchestration
│   ├── common/         # General passes (kinds, names, materials, etc.)
│   ├── shapes/         # Shape-specific passes
│   │   ├── assemble.py         # Build dispatch and material finalization
│   │   ├── bounding_volume.py  # Bounding box computation
│   │   ├── curve_shapes.py     # Curve → NurbsCurve/mesh classification
│   │   ├── link.py             # Shape linking/deduplication
│   │   ├── merge_children.py   # Merge-children resolution
│   │   ├── merge_group.py      # Merge-group resolution
│   │   ├── skinned_mesh.py     # Skinned mesh setup
│   │   └── vertex_requirements.py  # Vertex attribute requirements
│   └── animations/     # Animation sampling and reduction
│
├── resources/          # Resource tables
│   ├── base.py         # Base table class
│   ├── files.py        # FileTable
│   ├── materials.py    # MaterialTable
│   └── shapes.py       # ShapeTable, ShapeKey, ShapeMode
│
├── geometry/           # Geometry building
│   ├── built.py        # BuiltShape base, ShapeKind enum
│   ├── mesh/           # IndexedTriangleSet building
│   │   └── its.py      # BuiltITS, mesh triangulation
│   └── curve/          # NurbsCurve building
│       └── build_nurbs.py  # BuiltNurbsCurve, spline extraction
│
├── blender/            # Blender data extraction
│   ├── evaluated_mesh.py   # Mesh coordinate transformation
│   ├── evaluated_curve.py  # Curve coordinate transformation
│   └── bones.py            # Bone/armature utilities
│
└── serialize/          # I3D serialization
    ├── write_i3d.py                # Main writer
    ├── indexed_triangle_set_stream.py  # ITS binary format
    ├── nurbs_curve_stream.py       # NurbsCurve XML format
    ├── emit_scene.py               # Scene graph XML
    ├── emit_materials.py           # Materials XML
    ├── emit_files.py               # Files XML
    ├── emit_animation.py           # Animation XML
    ├── emit_i3d_mappings.py        # i3D mappings XML
    ├── emit_user_attributes.py     # User attributes XML
    └── xml_attrs.py                # XML attribute utilities
```

---