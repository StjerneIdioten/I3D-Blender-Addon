.. _installation_exporter:

Getting the Exporter
====================

The exporter is to be installed in the same way as any `blender addon`_, but here is a follow along guide to double
check that everything has been done correctly.

.. _blender addon: https://docs.blender.org/manual/en/latest/editors/preferences/addons.html#rd-party-add-ons

Download
--------

The current place to get the exporter is from the `github repository`_. Here you can also find the sourcecode if that
interests you. In the right side of the github page you will find a link to the `releases`_, which will get you to a
page that looks similar to this:

.. figure:: releases.png

    This is currently the ONLY place from where you should download the exporter!

Each release has notes attached, which explains what is new/changed in this release.
As blender gets new versions the exporter will move along with it and versions for older versions of blender will be
kept here for compatibility reasons, but they will not be updated with new features!

.. Caution:: If a release has the label **Pre-release** or a hypen in the version name with some text after, then this
    is an experimental build! This is where new features are pushed for testing, so make sure to keep a backup of your
    blend file if using these versions. If any bugs are encountered please report them on the `issue tracker`_.

To actually get the .zip file needed one should expand the :guilabel:`Assets` and click :guilabel:`I3D Exporter`,
which should net you a file called :guilabel:`i3d_exporter.zip`

.. figure:: releases_pick.png

    This is the file you should download to get the exporter (This is just a random release and might not be the newest
    one available, when you read this)

.. _github repository: https://github.com/StjerneIdioten/I3D-Blender-Addon
.. _releases: https://github.com/StjerneIdioten/I3D-Blender-Addon/releases
.. _issue tracker: https://github.com/StjerneIdioten/I3D-Blender-Addon/issues


Installation in Blender
-----------------------

To install the addon go into blender and goto :menuselection:`Edit --> Preferences --> Add-ons` here you should find a
button named :guilabel:`Install`, which will give you a filebrowser to select the zip file you downloaded in the previous
section.

.. figure:: install_browser.png

    Click install to get a filebrowser to select the zip

.. Note:: While it is possible to extract the zip manually into the blender addon folder, it is recommended to use the
    install button within blender itself to do it. This is due to the addon needing a specific naming of the folder in
    which it resides to work!

Verify Installation
-------------------

You should now be able to find :guilabel:`Unofficial GIANTS I3D Exporter Tools` in your list of addons. Make sure that
you have toggled on the *Community* category!

.. figure:: verify_install.png

    Here I have searched specifically for *i3d* to only show the exporter addon

If for some reason you choose to unpack the addon into the folder yourself, then make sure you have this exact
structure:

.. figure:: correct_folder_structure.png

    Of course with your own username and whatever blender version you are installing the addon to. The important part
    is that the code files resides in a folder called *i3dio* within *addons*

What's Next?
------------

Now that you have the addon install you should proceed to next next section which describes how to setup a few things
required for the addon to work in an optimal way.




