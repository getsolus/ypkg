#!/bin/true
# -*- coding: utf-8 -*-
#
#  This file is part of ypkg2
#
#  Copyright 2015-2020 Solus Project
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#

from .ui import YpkgUI

import re
import os


global console_ui

console_ui = YpkgUI()


def remove_prefix(fpath, prefix):
    if fpath.startswith(prefix):
        fpath = fpath[len(prefix)+1:]
    if fpath[0] != '/':
        fpath = "/" + fpath
    return fpath


def readlink(path):
    return os.path.normpath(os.readlink(path))


def is_rootlessmode():
    if "FAKED_MODE" in os.environ:
        return True
    if "ROOTLESSKIT_PARENT_EUID" in os.environ:
        return True
    return False


pkgconfig32_dep = re.compile("^pkgconfig32\((.*)\)$")
pkgconfig_dep = re.compile("^pkgconfig\((.*)\)$")


global packager_name
global packager_email


packager_name = "Automated Package Build"
packager_email = "no.email.set.in.config"

EMUL32PC = "/usr/lib32/pkgconfig:/usr/share/pkgconfig:/usr/lib/pkgconfig"
