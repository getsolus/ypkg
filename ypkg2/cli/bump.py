#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  ybump.py
#
#  Copyright 2015-2020 Solus Project
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
import sys
from ruamel.yaml import YAML

## The YAML 1.2 spec technically does not allow key names to be greater than 128 characters. This is problematic for us
## as we use the source URI as the key in ypkg, causing the infamous splitting of long source names and causing lines
## to start with `- ?`. Override this limit in ruamel to allow us to continue to mangle the YAML spec in this way.
## 32x the limit oughta be enough for anyone, right?
from ruamel.yaml.emitter import Emitter

Emitter.MAX_SIMPLE_KEY_LENGTH = 4096


def usage(msg=None, ex=1):
    if msg:
        print(msg)
    else:
        print(("Usage: %s file.yml" % sys.argv[0]))
    sys.exit(ex)


def main():
    if len(sys.argv) != 2:
        usage()

    with open(sys.argv[1]) as fp:
        lines = fp.readlines()
        fp.seek(0)
        yaml = YAML()
        data = yaml.load(fp)
    data["release"] += 1
    maxwidth = len(max(lines, key=len))
    try:
        with open(sys.argv[1], "w") as fp:
            yaml.indent(mapping=4, sequence=6, offset=4)
            yaml.width = maxwidth
            yaml.dump(data, fp)
    except Exception as e:
        print("Error writing file, may need to reset it.")
        print(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
