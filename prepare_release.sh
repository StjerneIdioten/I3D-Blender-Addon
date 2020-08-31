#!/bin/bash
# Split the version tag into separate numbers
IFS='.' read -ra VERSION <<< "$1"
# Replace version number with new version number
sed -ri -E "/version/s/[0-9]+, [0-9]+, [0-9]+/${VERSION[0]}, ${VERSION[1]}, ${VERSION[2]}/" $GITHUB_WORKSPACE/addon/i3dio/__init__.py
# Zip it all into the new build
sudo apt-get install -y zip
cd $GITHUB_WORKSPACE/addon
zip -r i3d_exporter.zip i3dio

