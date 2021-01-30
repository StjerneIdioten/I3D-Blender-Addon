.. _toolchain:

Toolchain
=========

This page serves the purpose of detailing which tools have been used in developing the addon. Both as an inspiration
and a guide to setup your own environment if you want to help with development of the addon.
It will both contain description of server-side tools such as the continuous integration, which builds the project, as
well as local tools that makes life easier as a developer.

Commitizen
----------
This project utilizes `Commitizen <https://github.com/commitizen/cz-cli>`_ to make it easier to follow the commit
message convention that this project enforces.

It gives you a clear overview of the possible message formats, without you having to look up the conventions everytime.

To install follow `this <https://github.com/commitizen/cz-cli#conventional-commit-messages-as-a-global-utility>`_ which
outlines how to install commitizen outside of the project (globally). You can skip the step about making the .czrc file
in the home folder as this file is provided by the project (Just in case that you already use commitizen)

To use commitizen just write ``git cz`` instead of ``git commit`` and you will be guided through actually making a
proper commit that adheres to the standards that the build system follows.



