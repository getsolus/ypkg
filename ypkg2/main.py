#!/usr/bin/env python3
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

import subprocess
import sys
import os

import pisi.specfile
from pisi.db.filesdb import FilesDB
from pisi.db.installdb import InstallDB
from pisi.db.packagedb import PackageDB
import typer
from typing_extensions import Annotated

from . import metadata
from .history import (
    cve_hit,
    get_git_tags,
    get_yml_at_tag,
    get_commiter_infos,
    MAX_HISTORY_LEN,
)
from .build import build_package
from .ypkgspec import YpkgSpec, PackageHistory
from .util import console_ui, pkgconfig_dep, pkgconfig32_dep


app = typer.Typer()


@app.command()
def build(
    filename: Annotated[str, typer.Argument(help="Path to the ypkg YAML file.")],
    output_dir: Annotated[
        str,
        typer.Option(
            "--output-dir",
            "-D",
            help="Set the output directory for resulting files.",
        ),
    ] = "",
    build_dir: Annotated[
        str,
        typer.Option(
            "--build-dir",
            "-B",
            help="Set the base directory for performing the build.",
        ),
    ] = "",
    timestamp: Annotated[
        int,
        typer.Option("--timestamp", "-t", help="Set the UNIX timestamp for the build."),
    ] = -1,
    no_color: Annotated[
        bool, typer.Option("--no-colors", "-n", help="Disable color output.")
    ] = False,
):
    """
    Build a package from a YPKG YAML file.
    """
    outputDir = "."

    # Kill colors
    if no_color:
        console_ui.allow_colors = False

    if timestamp > 0:
        metadata.history_timestamp = timestamp

    if output_dir:
        od = output_dir
        if not os.path.exists(output_dir):
            console_ui.emit_error("Opt", f"{od} does not exist")
            sys.exit(1)
        outputDir = od
    outputDir = os.path.abspath(outputDir)

    if build_dir:
        buildDir = os.path.abspath(build_dir)
    else:
        buildDir = None

    # Test who we are
    if os.geteuid() == 0:
        if "FAKED_MODE" not in os.environ:
            console_ui.emit_warning(
                "Warning",
                "ypkg-build should be run via fakeroot, not as real root user",
            )
    else:
        console_ui.emit_error(
            "Fail",
            "ypkg-build must be run with fakeroot, "
            "or as the root user (not recommended)",
        )
        sys.exit(1)

    build_package(filename, outputDir, buildDir)


@app.command()
def gen_history(
    filename: Annotated[str, typer.Argument(help="Path to the ypkg YAML file.")],
    output_dir: Annotated[
        str,
        typer.Option(
            "--output-dir",
            "-D",
            help="Set the output directory for resulting files.",
        ),
    ] = "",
):
    """
    Generates a history.xml file.
    """
    if not filename:
        print("Fatal: No filename provided")
        sys.exit(1)

    yml = os.path.abspath(filename)
    wdir = os.path.dirname(yml)

    # check git exists
    fp = os.path.join(wdir, ".git")
    if not os.path.exists(fp):
        print(f"Debug: Skipping non git tree: {wdir}")
        sys.exit(0)

    outputDir = wdir
    if output_dir:
        od = output_dir
        if not os.path.exists(output_dir):
            print(f"{od} does not exist")
            sys.exit(1)
        outputDir = od
    outputDir = os.path.abspath(outputDir)

    tags = get_git_tags(wdir)

    history = list()

    for tag in tags:
        tag = tag.strip()
        if tag == "":
            continue
        spec = get_yml_at_tag(wdir, tag)
        if not spec:
            continue
        info = get_commiter_infos(wdir, tag)
        if not info:
            continue
        history.append((spec, info))

    history = sorted(history, key=lambda x: x[0].pkg_release, reverse=True)

    if len(history) > MAX_HISTORY_LEN:
        history = history[0:MAX_HISTORY_LEN]

    hist = os.path.join(outputDir, "history.xml")

    hist_obj = PackageHistory()
    for i in history:
        com = i[1]
        spec = i[0]
        update = pisi.specfile.Update()
        update.name = str(com.name)
        update.email = com.email
        update.version = spec.pkg_version
        update.release = str(spec.pkg_release)
        update.date = com.date
        comment = com.subject
        if com.body:
            comment += "\n" + com.body
        update.comment = comment
        for word in comment.split():
            if cve_hit.match(word):
                update.type = "security"
                break
        hist_obj.history.append(update)

    hist_obj.write(hist)


@app.command()
def install_deps(
    filename: Annotated[str, typer.Argument(help="Path to the ypkg YAML file.")],
    output_dir: Annotated[
        str,
        typer.Option(
            "--output-dir",
            "-D",
            help="Set the output directory for resulting files.",
        ),
    ] = "",
    eopkg_cmd: Annotated[
        str,
        typer.Option(
            "--eopkg-cmd",
            "-e",
            help="Specify which eopkg command to use.",
        ),
    ] = "eopkg.py3",
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force install dependencies."),
    ] = False,
    no_color: Annotated[
        bool, typer.Option("--no-colors", "-n", help="Disable color output.")
    ] = False,
):
    """
    Installs the dependencies required to build a package.
    """
    spec = YpkgSpec()

    # Kill colors
    if no_color:
        console_ui.allow_colors = False

    # Grab filename
    if not filename:
        console_ui.emit_error("Error", "Please provide a filename")
        sys.exit(1)

    if not spec.load_from_path(filename):
        sys.exit(1)

    pc32deps = set()
    pcdeps = set()
    ndeps = set()

    idb = InstallDB()
    pdb = PackageDB()
    fdb = FilesDB()

    console_ui.emit_info(
        "BuildDep",
        f"Checking build-deps for {spec.pkg_name}-{spec.pkg_version}-{spec.pkg_release}",
    )

    if spec.pkg_builddeps:
        for dep in spec.pkg_builddeps:
            em32 = pkgconfig32_dep.match(dep)
            if em32:
                pc32deps.add(em32.group(1))
                continue
            em = pkgconfig_dep.match(dep)
            if em:
                pcdeps.add(em.group(1))
                continue
            if not idb.has_package(dep):
                ndeps.add(dep)

    if spec.pkg_checkdeps:
        for dep in spec.pkg_checkdeps:
            em32 = pkgconfig32_dep.match(dep)
            if em32:
                pc32deps.add(em32.group(1))
                continue
            em = pkgconfig_dep.match(dep)
            if em:
                pcdeps.add(em.group(1))
                continue
            if not idb.has_package(dep):
                ndeps.add(dep)

    # Get the global known pkgconfig providers
    pkgConfigs, pkgConfigs32 = pdb.get_pkgconfig_providers()

    for i in pc32deps:
        local = False
        pkg = None

        # Try global pkgconfig names first.
        if i in pkgConfigs32:
            pkg = pdb.get_package(pkgConfigs32[i])
        elif i in pkgConfigs:
            pkg = pdb.get_package(pkgConfigs[i])

        # Try the filesdb
        if not pkg:
            local = True
            nom = fdb.get_pkgconfig32_provider(i)
            if nom:
                pkg = idb.get_package_by_pkgconfig32(nom[0])
        if not pkg:
            nom = fdb.get_pkgconfig_provider(i)
            if nom:
                pkg = idb.get_package_by_pkgconfig(nom[0])

        if local:
            console_ui.emit_warning(
                f"pkgconfig32:{i}", "This dependency is not in any repo"
            )
        if not pkg:
            console_ui.emit_error(
                "BuildDep",
                f"pkgconfig32({i}) build dep doesn't exist in the repository.",
            )
            sys.exit(1)
        if not idb.has_package(pkg.name):
            ndeps.add(pkg.name)

    for i in pcdeps:
        local = False
        pkg = None
        if i in pkgConfigs:
            pkg = pdb.get_package(pkgConfigs[i])
        if not pkg:
            nom = fdb.get_pkgconfig_provider(i)
            if nom:
                pkg = idb.get_package_by_pkgconfig(nom[0])
            local = True
        if local:
            console_ui.emit_warning(
                f"pkgconfig:{i}", "This dependency is not in any repo"
            )
        if not pkg:
            console_ui.emit_error(
                "BuildDep",
                f"pkgconfig({i}) build dep does not exist in the repository.",
            )
            sys.exit(1)
        if not idb.has_package(pkg.name):
            ndeps.add(pkg.name)

    if len(ndeps) < 1:
        console_ui.emit_success("BuildDep", "All build deps satisfied")
        sys.exit(0)

    if os.geteuid() != 0:
        cmd = f"sudo {eopkg_cmd} install {' '.join(ndeps)}"
    else:
        cmd = f"{eopkg_cmd} install {' '.join(ndeps)}"

    if force:
        cmd += " --yes-all"

    if no_color:
        cmd += " -N"

    invalid = [x for x in ndeps if not pdb.has_package(x)]
    if len(invalid) > 0:
        console_ui.emit_error("BuildDep", f"Unknown build deps: {' '.join(invalid)}")
        sys.exit(1)

    console_ui.emit_info("BuildDep", f"Requesting installation of: {' '.join(ndeps)}")
    try:
        subprocess.check_call(cmd, shell=True)
    except Exception:
        console_ui.emit_error("BuildDep", "Failed to install build deps")
        sys.exit(1)


if __name__ == "__main__":
    app()
