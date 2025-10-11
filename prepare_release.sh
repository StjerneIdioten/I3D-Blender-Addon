#!/bin/bash
# Replace version number with new version number. Can contain dev version.
sed -i "s/^version = \".*\"/version = \"$1\"/" $GITHUB_WORKSPACE/addon/i3dio/blender_manifest.toml
cd $GITHUB_WORKSPACE/addon/i3dio
zip -r "../i3d_exporter-$1.zip" .
