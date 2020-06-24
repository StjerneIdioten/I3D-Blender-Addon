# Blender 2.8. Addon for i3D-Giants Game Engine
[![Open Source Love](https://badges.frapsoft.com/os/v1/open-source.svg?v=103)](https://github.com/ellerbrock/open-source-badges/)
[![GPL Licence](https://badges.frapsoft.com/os/gpl/gpl.svg?v=103)](https://opensource.org/licenses/GPL-3.0/)

As I am currently an university student, any amount will be greatly appreciated *(and will most likely be used for beer fueled coding binges, which translates into more features for the exporter)*

[![](https://www.paypalobjects.com/en_US/DK/i/btn/btn_donateCC_LG.gif)](https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=3BLFKTJDUC4Y6&currency_code=EUR&source=url)


## Table of Contents

* [Description](#description)
* [Introduction](#introduction)
* [Objectives](#objectives)
* [Technologies](#technologies)
* [Status](#status)
* [Access](#access)
* [Sources](#sources)
* [Licence](#licence)

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
* PEP8-80 compliant (althought this may not always be possible
* Blender 2.82

## Status

* Working towards first feature-complete stable release

## Installation
The [Releases](https://github.com/StjerneIdioten/I3D-Blender-Addon/releases) page will always contain a release with the latest features tagged "latest". This might not be stable, so use with care. The page also holds other releases that I add once I deem them to have been tested properly, but keep in mind that at this point this is all pre-release stuff, so make sure to keep a backup of your blend files as I cannot guarantee that the exporter will keep them in a usable state.
All of these releases are packaged as blender expects them and should be installed just like any other addon for blender.

If you wish to fork the repository and play around with the code, then you need to put the git repository somewhere and symlink the "addon/i3dio" folder into your version of blenders addon folder.

It is probably also worth mentioning that this addon is NOT linux/mac compatible. It could become it, but I have not given that any thought since the Giants Engine is not running on anything but windows anyway.

## Access

This has mostly been a solo project so far, but any help is appreciated.
In case of wanting to join, the following knowledge is required:
* Git version control
* Knowledge of Python 3
* Knowledge of Blender 2.8

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
