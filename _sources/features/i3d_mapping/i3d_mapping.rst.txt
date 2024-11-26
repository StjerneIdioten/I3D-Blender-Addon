.. _i3d_mapping:

I3D Mapping
===========

The exporter has the possibility of automatically exporting node indexes into the i3d-mapping of the xml file for your
mod. It gives you the option of individually enabling/disabling the mapping per object in blender and even renaming them
if you want a different name in the mapping vs. what you have in blender.


Setup
--------
To enable i3d-mapping for your project, you need to inform the exporter of the path to your xml-file.

* :menuselection:`Properties --> Scene Properties --> I3D Mapping Options --> XML File`

.. figure:: location_of_xml_picker.png

    Use the file picker to pick the xml-file in which you wish the i3d-mapping to appear

The file you pick needs to be a valid xml file or else you will get an error.

.. Note:: Currently the <i3dMappings> element needs to be present in the xml-file for the exporter to be able to do
    the mapping

Usage
-----
To get your nodes mapped to the correct indexes in the i3d-file you need to enable i3d-mapping for the object in blender
and optionally give it a name, if you don't want to use the name from blender. The option can be found at
:menuselection:`Properties -> Object Properties -> I3D Object Attributes -> I3D Mapping`

.. figure:: blender_example.png

    In this example the node index would be mapped to the name **Some Optional Name** and if the field was kept clear,
    then name would have been **Cube**

Gotchas
-------
If you have not installed :ref:`lxml<installation_setup_xml_library>` and is using the default xml-library,
then you will notice something most unfortunate with your xml-file.

All of the attributes you have setup for different things is now listed in alphabetical order instead of whatever order
you placed them in. This is because xml technically don't care about the order of attributes and since the exporter is
reading in the whole file to eventually export it out again, it does the attributes in alphabetical order. The attribute
order can be maintained when using `lxml`, but not with the builtin library.


Examples
--------

If you have something likes this

.. figure:: blender_structure_example.png

where all of the objects have i3d-mapping turned on and **Cube.001** has the
alternative name of **Awesome Cube**

Then you would get this

.. figure:: blender_structure_example_mapping.png

in the xml-file you have selected.