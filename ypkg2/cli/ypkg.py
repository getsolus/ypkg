#!/usr/bin/env python3
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

from ypkg2 import console_ui
from ypkg2.main import show_version
import subprocess
import sys
import os
import argparse


def main():
    parser = argparse.ArgumentParser(description="Ypkg")
    parser.add_argument(
        "-n", "--no-colors", help="Disable color output", action="store_true"
    )
    parser.add_argument(
        "-v", "--version", action="store_true", help="Show version information and exit"
    )
    parser.add_argument(
        "-f",
        "--force",
        help="Force install dependencies, i.e. no prompt",
        action="store_true",
    )
    parser.add_argument(
        "-D",
        "--output-dir",
        type=str,
        help="Set the output directory for resulting files",
    )
    parser.add_argument(
        "-B",
        "--build-dir",
        type=str,
        help="Set the base directory for performing the build",
    )
    # Main file
    parser.add_argument("filename", help="Path to the ypkg YAML file", nargs="?")

    args = parser.parse_args()
    # Kill colors
    if args.no_colors:
        console_ui.allow_colors = False
    # Show version
    if args.version:
        show_version()

    # Grab filename
    if not args.filename:
        console_ui.emit_error("Error", "Please provide a filename")
        print("")
        parser.print_help()
        sys.exit(1)

    needFakeroot = True
    if os.geteuid() == 0:
        if "FAKED_MODE" not in os.environ:
            needFakeroot = False

    vargs = sys.argv[1:]
    cargs = " ".join([x for x in vargs if x != "-f" and x != "--force"])

    try:
        output_flag = f"-D {args.output_dir}" if args.output_dir else ""
        force_flag = "--force" if args.force else ""
        subprocess.check_call(
            f"ypkg-install-deps {output_flag} {force_flag} {args.filename}", shell=True
        )

        if needFakeroot:
            sub = "fakeroot "
        else:
            sub = ""

        subprocess.check_call(f"{sub}ypkg-build {cargs}", shell=True)
    except Exception as e:
        print(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
