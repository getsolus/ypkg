#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  yupdate.py
#
#  Copyright 2015-2020 Solus Project
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#

import argparse
import atexit
import sys
import os
import subprocess
import pisi.version
from ruamel.yaml import YAML

## The YAML 1.2 spec technically does not allow key names to be greater than 128 characters. This is problematic for us
## as we use the source URI as the key in ypkg, causing the infamous splitting of long source names and causing lines
## to start with `- ?`. Override this limit in ruamel to allow us to continue to mangle the YAML spec in this way.
## 32x the limit oughta be enough for anyone, right?
from ruamel.yaml.emitter import Emitter

Emitter.MAX_SIMPLE_KEY_LENGTH = 4096

parser = argparse.ArgumentParser()
parser.add_argument("version", type=str, help="new version of package")
parser.add_argument("url", type=str, help="url to new package version")
parser.add_argument(
    "--tag-prefix", type=str, help="git version tag prefix [default: v]", default="v"
)
parser.add_argument(
    "--yml",
    type=str,
    help="path to package yml config [default: ./package.yml]",
    default="package.yml",
)
parser.add_argument(
    "-nb", nargs="?", help="Don't bump the release number [default: True]", default=True
)
parser.add_argument(
    "--cache",
    nargs="?",
    help="Cache the tarball in the solbuild cache to avoid redownloading [default: False]",
    default=False,
)


def usage(msg=None, ex=1):
    if msg:
        print(msg)
    else:
        parser.print_help()
    sys.exit(ex)


def shasum(url):
    try:
        r = os.system('wget "%s"' % url)
    except:
        print("Failed to download file")
        sys.exit(1)
    if r != 0:
        print("Failed to download file")
        sys.exit(1)

    sha256 = subprocess.check_output(["sha256sum", filename]).split()[0].strip()
    return sha256.decode("utf-8")


def cache_tarball_to_solbuild(filename, sha256sum):
    solbuildcacheloc = "/var/lib/solbuild/sources/{}".format(sha256sum)
    finalloc = "{}/{}".format(solbuildcacheloc, filename)
    if not os.path.exists(finalloc):
        try:
            print("Caching tarball in the solbuild cache")
            # having to invoke sudo is annoying, could add a pkexec script to make it 'nicer'
            r = subprocess.check_output(
                "sudo mkdir -p {}".format(solbuildcacheloc), shell=True
            )
            r = subprocess.check_output(
                "sudo mv {} {}".format(filename, finalloc), shell=True
            )
        except Exception as e:
            print("Error moving tarball to solbuild cache")
            print(e)
            sys.exit(1)
        return True
    else:
        print("Tarball already exists in solbuild cache")
        return False


def main():
    global cleanup
    cleanup = True
    args = parser.parse_args()

    ymlfile = args.yml
    if not os.path.exists(ymlfile):
        usage("Specified file does not exist")
    if not ymlfile.endswith(".yml"):
        usage("%s does not look like a valid package.yml file" % ymlfile)

    newversion = args.version
    try:
        d = pisi.version.Version(newversion)
    except Exception as e:
        print(("Problematic version string: %s" % e))
        sys.exit(1)

    url = args.url
    global filename
    filename = os.path.basename(url)
    sha256sum = shasum(url)
    if not url.startswith("git|"):
        source = {url: sha256sum}
    else:
        source = {url: args.tag_prefix + newversion}

    with open(ymlfile, "r") as infile:
        lines = infile.readlines()
        infile.seek(0)
        yaml = YAML()
        data = yaml.load(infile)
    data["source"][0] = source
    if args.nb is not None:
        data["release"] += 1
    data["version"] = newversion
    maxwidth = len(max(lines, key=len))

    try:
        with open(ymlfile, "w") as fp:
            yaml.indent(mapping=4, sequence=4, offset=4)
            yaml.width = maxwidth
            yaml.dump(data, fp)
    except Exception as e:
        print("Error writing file, may need to reset it.")
        print(e)
        sys.exit(1)

    # Attempt to cache to solbuild if set
    if args.cache is not False and not url.startswith("git|"):
        if cache_tarball_to_solbuild(filename, sha256sum):
            cleanup = False


if __name__ == "__main__":
    main()


@atexit.register
def cleanuponexit():
    """Cleanup on exit."""
    if cleanup is not False and filename != "":
        os.unlink(filename)
