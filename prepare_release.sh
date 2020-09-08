#!/bin/bash
# Replace version number with new version number. Can contain dev version.
sed -i "/^__version/c\__version__ = \"$1\"" $GITHUB_WORKSPACE/addon/i3dio/__init__.py
# Split the version tag into separate numbers
IFS='.-' read -ra VERSION <<< "$1"
# Replace bl_info version number with new version number (This one can't contain a development tag if present)
sed -ri -E "/version/s/[0-9]+, [0-9]+, [0-9]+/${VERSION[0]}, ${VERSION[1]}, ${VERSION[2]}/" $GITHUB_WORKSPACE/addon/i3dio/__init__.py
# Zip it all into the new build
sudo apt-get install -y zip
cd $GITHUB_WORKSPACE/addon
zip -r i3d_exporter.zip i3dio

