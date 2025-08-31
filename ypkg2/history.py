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
import subprocess

from yaml import load as yaml_load

try:
    from yaml import CLoader as Loader
except Exception:
    from yaml import Loader

from .ypkgspec import YpkgSpec

MAX_HISTORY_LEN = 10

cve_hit = re.compile(r".*(CVE\-[0-9]+\-[0-9]+).*")


class CommiterInfo:
    name = None
    email = None
    date = None
    subject = None
    body = None


def get_git_tags(wdir: str):
    cmd = 'git -C "{}" tag --sort=-refname'.format(wdir)

    ret = set()

    try:
        out = subprocess.check_output(cmd, shell=True)
    except Exception:
        return None

    for i in out.split("\n"):
        i = i.strip()
        ret.add(i)
    return sorted(list(ret))


def get_yml_at_tag(wdir: str, tag: str):
    cmd = 'git -C "{}" show {}:package.yml'.format(wdir, tag)

    try:
        out = subprocess.check_output(cmd, shell=True)
    except Exception:
        return None
    yml = YpkgSpec()

    try:
        yaml_data = yaml_load(out, Loader=Loader)
    except Exception:
        return False

    if not yml.load_from_data(yaml_data):
        return None
    return yml


def get_commiter_infos(wdir: str, tag: str):
    fmt = "%an\n%ae\n%ad\n%s\n%b"
    cmd = 'git -C "{}" log --pretty=format:"{}" {} -1 --date=iso'.format(wdir, fmt, tag)

    out = None
    try:
        out = subprocess.check_output(cmd, shell=True)
    except Exception:
        return None

    splits = out.split("\n")
    if len(splits) < 4:
        return None
    com = CommiterInfo()
    com.name = splits[0].strip()
    com.email = splits[1].strip()
    com.date = splits[2].split(" ")[0].strip()
    com.subject = splits[3].strip()
    if len(splits) > 4:
        com.body = "\n".join(splits[4:])

    return com
