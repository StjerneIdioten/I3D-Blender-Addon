# Blender 2.8. Addon for i3D-Giants Game Engine
[![Open Source Love](https://badges.frapsoft.com/os/v1/open-source.png?v=103)](https://github.com/ellerbrock/open-source-badges/)
[![GPL Licence](https://badges.frapsoft.com/os/gpl/gpl.png?v=103)](https://opensource.org/licenses/GPL-3.0/)
[![semantic-release](https://img.shields.io/badge/%20%20%F0%9F%93%A6%F0%9F%9A%80-semantic--release-e10079.svg)](https://github.com/semantic-release/semantic-release)
![Workflow status](https://github.com/StjerneIdioten/I3D-Blender-Addon/workflows/Release/badge.svg)

As I am currently an university student, any amount will be greatly appreciated *(and will most likely be used for beer fueled coding binges, which translates into more features for the exporter)*

[![](https://www.paypalobjects.com/en_US/DK/i/btn/btn_donateCC_LG.gif)](https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=3BLFKTJDUC4Y6&currency_code=EUR&source=url)


## Table of Contents

* [Description](#description)
* [Introduction](#introduction)
* [Objectives](#objectives)
* [Technologies](#technologies)
* [Status](#status)
* [For Developers](#for-developers)
* [Help](#help)
* [Sources](#sources)
* [License](#license)

## Description

A project for updating the Giants Engine I3D exporter addon for blender 2.8

## Introduction

There is an existing exporter for blender supplied by Giants, but this isn't officially supported for newer blender versions and the code is outdated. The support from Giants themselves has also been lackluster and this project aims to supply a new addon with support and features driven by community feedback.


## Objectives

Current Priorities listed in order

1. Create a new addon, upholding standards put forth by both blender and python pep-8, that has a minimum of the same features as the currently available addon
2. Keep addon up to date with new version of Farming Simulator and Blender.
3. Add community requested features.


## Technologies
* Python 3.7
* PEP8-80 compliant (to the extent that it is possible)
* Blender 2.83

## Status

* Almost ready for the first release. Ironing out stability issues.

## Installation
The [Releases](https://github.com/StjerneIdioten/I3D-Blender-Addon/releases) page contains all releases starting from v0.10.0, which is the first properly tagged release. If a release starts targetting a higher blender version, then the prior version will be 'frozen' as the version for the previous version of blender. Features will not be backported, upgrade your blender instead.
All of these releases are packaged as blender expects them and should be installed just like any other [addon for blender](https://docs.blender.org/manual/en/latest/editors/preferences/addons.html#rd-party-add-ons). 

If you wish to fork the repository and play around with the code, then you need to put the git repository somewhere and symlink the "addon/i3dio" folder into your version of blenders addon folder.

It is probably also worth mentioning that this addon is NOT linux/mac compatible. It could become it, but I have not given that any thought since the Giants Engine is not running on anything but windows anyway.

## Documentation
As the exporter addon is currently in a pre-release stage, many of the features aren't really that well-documented apart from some internal documentation shared between testers. The [wiki](https://github.com/StjerneIdioten/I3D-Blender-Addon/wiki) is currently the best 'public' place to get information. It doesn't have everything yet, but the plan is that in time it is gonna be the only place you need to visit to get started with using this addon to create your fs-mods in blender.

## For Developers

This has mostly been a solo project so far, but any help is appreciated.
In case of wanting to join, the following knowledge is required:
* Git version control
* Knowledge of Python 3
* Knowledge of Blender 2.8
* [Angular Commit Guidelines](https://github.com/angular/angular.js/blob/master/DEVELOPERS.md#-git-commit-guidelines)

The repository is running CI using Github Actions. The current release process is that anything pushed into the master will generate a new release using semantic-release, which determines the next build version from the commit history (presuming that people follow angular style of commits) It will then change the build version in the `__init__.py` and upload a tagged release of this build.

Commit format:
> type(scope): Briefly describe change
>
> Further elaborate the motivation behind the change
>
> Close issues here

The following is which commit types the build system reacts to:

|Type|Scope|Version|Usage|
|:---|:---:|:---:|:---:|
|feat| * |minor|New feature|
|perf| * |patch|Performance Enhancement|
|fix| * |patch|Bug fix in existing code|
|refactor| * |patch|Rewrites existing code|
|style| * |false|A fix of comments, indentation, whitespaces etc.|
|docs| * |patch|Updates to the documentation that is bundled with the code (so not the README.md)|
|featsmall| * |patch|Smaller features that doesn't warrant a minor version update|
| * |no-release|false|Anything else where it shouldn't update the version|
|ci| * |false|Changes relating to the Continous Integration|

For triggering a major version upgrade, the footer of the commit should contain `BREAKING CHANGE:` followed by a description of what breaks.
The build system also automatically generates changelogs from the commit messages and bundles them together by first `Type` and then `scope`. The changelog will be in the description of the release on the release page.

Examples:
* Refactoring a piece of code in the main exporter module and close the related issue: 
> refactor(core-exporter): Refactor blender object type check
>
> Change the order of checks performed for object type to increase speed of execution
>
> Close #51

* Add a smaller feature such as an extra export attribute:
> feat-small(shader-picker): Add option for something
>
> Add option 'something' to material ui to enable automatic setting of 'something' in GE

* The major vesion is upgraded for non backwards compatible features such as a change of blender version used for development
> feat(blender): Upgrade blender version to 2.9
> 
> Update to further support new features
>
> BREAKING CHANGE: This breaks backwards compatability with older blender version. Use older builds if you have to stay at 2.83

## Help

If you need help with the addon in any way, the following channels are available:
* [Issue Tracker](https://github.com/StjerneIdioten/I3D-Blender-Addon/issues): If you come across any bugs or have a suggestion for a new feature, please post them here.
* [Wiki](https://github.com/StjerneIdioten/I3D-Blender-Addon/wiki): The wiki will eventually contain information on all the features of the exporter
* [VertexDezign Discord](https://discord.gg/GVfNFpM): There is an official support channel available for the exporter. For general questions etc. 
* [Redphoenix Youtube Showcase](https://www.youtube.com/watch?v=lRDPuKh9gow): Redphoenix has been to kind to create a youtube video showing all of the most important features
* [Redphoenix Youtube Full Tutorial](https://www.youtube.com/watch?v=O1jBP9EVauU&t=4s): Redphoenix has also created a complete walkthrough of exporting a model through the addon

I can also be reached in several other places, I am not hard to find through my nickname. But please keep exporter related support to the official channels listed here. So it might come in handy for anyone else with the same problem.

## Sources

 Required reading for contributors.

[Blender's API reference](https://docs.blender.org/api/current/info_api_reference.html)

[Blender's Best Practices](https://docs.blender.org/api/current/info_best_practice.html)

[Tips and trick from Blender.org](https://docs.blender.org/api/current/info_tips_and_tricks.html)

[Problems to be aware of](https://docs.blender.org/api/current/info_gotcha.html)

[Blender.org Changes from 2.79 to 2.8](https://docs.blender.org/api/current/change_log.html)

More Source information available at [Blender.org](https://docs.blender.org/api/current/index.html)

## License

This program is free software; you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; either version 2 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with this program; if not, write to the Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.

Copyright 2004 (C) GIANTS Software GmbH, Confidential, All Rights Reserved.
