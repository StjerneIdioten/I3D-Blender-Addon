.. _installation_setup:

Setup the Exporter
==================

Once you have downloaded and verified the exporter according to the previous section found
:ref:`here<installation_exporter>`, then there are a few steps left to make the exporter give you the best results.

These options can be found in the :guilabel:`Addon Preferences` of the exporter addon and will be explained individually
below.

.. figure:: ../exporter/verify_install.png

    The addon preferences are found in the same place as where we verified that the addon had been installed properly

.. Caution:: Although these steps aren't strictly necessary to make the exporter do it's job, it is strongly advised
    to follow them to make sure you get the most possible value out of the exporter!

FS Data Folder
--------------

The exporter has the ability to automatically resolve paths to files you use from the Farming Simulator data directory.
So if you are eg. using some shared texture or maybe using one of the shaders, then the exporter will correctly replace
the absolute path to your specific directory, with the general format of :class:`$data\\some\\shared\\resource`

To do this the exporter needs to know where your FS Data directory is located and due to there being several different
folder names depending on where you got the game from, it is easiest if you select this yourself. You use the filepicker
to select the data folder from within your Farming Simulator folder.

What if I don't?
^^^^^^^^^^^^^^^^
The exporter will just export all files/references with absolute paths. Which means that the mod will only work on your
own pc, unless you manually edit all of the references to be relative to the data folder. You will also receive a
warning in the blender info console everytime you export.

.. _installation_setup_xml_library:

XML Library
-----------

The exporter does a lot of xml parsing and writing, since FS mods use a combination of *.i3d* and *.xml* files, where
the *.i3d* files are actually just *.xml* files with a specific format.

The version of python that blender addons are written in comes with a builtin library for handling xml-files, but it
has some quirks that has had to be worked around for certain features in the addon to function correctly
(eg. :ref:`i3d-mapping<i3d_mapping>`). This is actually mostly Giants fault, since they don't follow the xml-standards
exactly and use certain things that aren't allowed in normal xml.

Anyway, to work around this the addon will try to use another xml-library called `lxml`, which is way more powerful, but
it does not come with blender per default.

So to install this library two things need to be present:

- An active internet connection
- Blender needs to be run with administrator privileges

And to install you just run blender with these two things present and the addon does it automatically, it also selects
`lxml` as the preferred library once installed.

Internet Connection
^^^^^^^^^^^^^^^^^^^
The library/module needs to be fetched from **The Python Package Index**, which the addon can do automatically. This
is a one time thing so you don't need an active internet connection going forward after `lxml` has been installed.

Administrative Privileges
^^^^^^^^^^^^^^^^^^^^^^^^^
Blender does not allow the addon to modify it's python installation without having administrative privileges.

.. figure:: run_as_admin.png

    :kbd:`Right-click` on blender and select :guilabel:`Run as administrator` or whatever the equivalent is in your
    language

Again this only needs to be done once and afterwards you don't have to run blender with administrative privileges.

Verify
^^^^^^
To verify that `lxml` has actually been installed, you can go to the addon preferences and see that it is present in
the dropdown-menu. If not, then look in the `blender system console`_ for a reason why the installation of `lxml`
failed.

.. figure:: verify.png

    `LXML` should be in the dropdown list and automatically selected as the currently used library, if you only see
    `ElementTree` then something went wrong with the installation of `lxml`

What If this is not possible?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
If it is not possible for you, for one reason or the other, to have an internet connection or administrative rights.
Then the exporter will still work, but it will default to use the builtin library which has limited functionality.
Currently the only feature affected is :ref:`i3d-mapping<i3d_mapping>`, which you can read more about in the docs
for that specific feature. But there might be more features affected in the future.

.. _blender system console: https://docs.blender.org/manual/en/latest/advanced/command_line/launch/windows.html#details













