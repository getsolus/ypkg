#!/bin/true
# -*- coding: utf-8 -*-
#
#  This file is part of ypkg2
#
#  Copyright 2025 Solus Project
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#

import re
import os

from .ui import YpkgUI


global console_ui

console_ui = YpkgUI()


def remove_prefix(fpath: str, prefix: str) -> str:
    """Removes a prefix from a path.

    If the resulting string does not start with a '/',
    one will be prepended.

    :param fpath str: The path to trim.
    :param prefix str: The prefix to trim from the path.
    :return: The trimmed path.
    """
    fpath = fpath.removeprefix(prefix)

    if not fpath.startswith("/"):
        return f"/{fpath}"

    return fpath


def readlink(path: str) -> str:
    """Read a file link, returning the path to the target file.

    The resulting path will be normalized.

    :param path str: The path of the file link.
    :return: The path to the file the link points to.
    """
    return os.path.normpath(os.readlink(path))


pkgconfig32_dep = re.compile(r"^pkgconfig32\((.*)\)$")
pkgconfig_dep = re.compile(r"^pkgconfig\((.*)\)$")


global packager_name
global packager_email


packager_name = "Automated Package Build"
packager_email = "no.email.set.in.config"

EMUL32PC = "/usr/lib32/pkgconfig:/usr/share/pkgconfig:/usr/lib/pkgconfig"
