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

from . import console_ui
from . import remove_prefix
from .compressdoc import compress_info_pages, compress_man_pages
from .ypkgspec import YpkgSpec
from .sources import SourceManager
from .ypkgcontext import YpkgContext
from .scripts import ScriptGenerator
from .packages import PackageGenerator, PRIORITY_USER
from .examine import PackageExaminer
from . import metadata
from .dependencies import DependencyResolver
from . import packager_name, packager_email
from . import EMUL32PC
from .ui import humanize

import ypkg2

import sys
import argparse
import os
import shutil
import tempfile
import subprocess
from configobj import ConfigObj


def show_version():
    print("Ypkg - Package Build Tool")
    print("\nCopyright (C) 2015-2018 Ikey Doherty\n")
    print("This program is free software; you are free to redistribute it\n"
          "and/or modify it under the terms of the GNU General Public License"
          "\nas published by the Free Software foundation; either version 3 of"
          "\nthe License, or (at your option) any later version.")
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Ypkg Package Build Tool")
    parser.add_argument("-n", "--no-colors", help="Disable color output",
                        action="store_true")
    parser.add_argument("-v", "--version", action="store_true",
                        help="Show version information and exit")
    parser.add_argument("-t", "--timestamp", help="Unix timestamp for build",
                        type=int, default=-1)
    parser.add_argument("-D", "--output-dir", type=str,
                        help="Set the output directory for resulting files")
    # Main file
    parser.add_argument("filename", help="Path to the ypkg YAML file to build",
                        nargs='?')

    outputDir = "."

    args = parser.parse_args()
    # Kill colors
    if args.no_colors:
        console_ui.allow_colors = False
    # Show version
    if args.version:
        show_version()
    if args.timestamp > 0:
        metadata.history_timestamp = args.timestamp

    if args.output_dir:
        od = args.output_dir
        if not os.path.exists(args.output_dir):
            console_ui.emit_error("Opt", "{} does not exist".format(od))
            sys.exit(1)
        outputDir = od
    outputDir = os.path.abspath(outputDir)

    # Grab filename
    if not args.filename:
        console_ui.emit_error("Error",
                              "Please provide a filename to ypkg-build")
        print("")
        parser.print_help()
        sys.exit(1)

    # Test who we are
    if os.geteuid() == 0:
        if "FAKED_MODE" not in os.environ:
            console_ui.emit_warning("Warning", "ypkg-build should be run via "
                                    "fakeroot, not as real root user")
    else:
        console_ui.emit_error("Fail", "ypkg-build must be run with fakeroot, "
                              "or as the root user (not recommended)")
        sys.exit(1)

    build_package(args.filename, outputDir)


def clean_build_dirs(context):
    if os.path.exists(context.get_build_dir()):
        try:
            shutil.rmtree(context.get_build_dir())
        except Exception as e:
            console_ui.emit_error("BUILD", "Could not clean build directory")
            print(e)
            return False
    return True


def execute_step(context, step, step_n, work_dir):
    script = ScriptGenerator(context, context.spec, work_dir)
    if context.emul32:
        script.define_export("EMUL32BUILD", "1")
        script.define_export("PKG_CONFIG_PATH", EMUL32PC)
    if context.avx2:
        script.define_export("AVX2BUILD", "1")
    if context.gen_pgo:
        script.define_export("PGO_GEN_BUILD", "1")
    if context.use_pgo:
        script.define_export("PGO_USE_BUILD", "1")
    extraScript = None
    endScript = None

    # Allow GCC and such to pick up on our timestamp
    script.define_export("SOURCE_DATA_EPOCH",
                         "{}".format(metadata.history_timestamp))

    # Handle the anal nature of llvm profiling
    if context.gen_pgo and context.spec.pkg_clang:
        profileFile = os.path.join(context.get_pgo_dir(),
                                   "default-%m.profraw")
        script.define_export("LLVM_PROFILE_FILE", profileFile)
        script.define_export("YPKG_PGO_DIR", context.get_pgo_dir())
    elif context.use_pgo and context.spec.pkg_clang:
        profileFile = os.path.join(context.get_pgo_dir(),
                                   "default.profdata")
        extraScript = "%llvm_profile_merge"
        script.define_export("LLVM_PROFILE_FILE", profileFile)
        script.define_export("YPKG_PGO_DIR", context.get_pgo_dir())

    if context.avx2 and step_n == "install":
        endScript = "%avx2_lib_shift"

    exports = script.emit_exports()

    # Run via bash with enable and error
    full_text = "#!/usr/bin/env -i /bin/bash --norc --noprofile\n" \
                "set -e\nset -x\n"
    # cd to the given directory
    full_text += "\n\ncd \"%workdir%\"\n"

    # Add our exports
    full_text += "\n".join(exports)
    if context.spec.pkg_environment:
        full_text += "\n\n{}\n".format(context.spec.pkg_environment)
    if extraScript:
        full_text += "\n\n{}\n".format(extraScript)
    full_text += "\n\n{}\n".format(step)
    if endScript:
        full_text += "\n\n{}\n".format(endScript)
    output = script.escape_string(full_text)

    with tempfile.NamedTemporaryFile(prefix="ypkg-%s" % step_n) as script_ex:
        script_ex.write(output)
        script_ex.flush()

        cmd = ["/bin/bash", "--norc", "--noprofile", script_ex.name]
        try:
            subprocess.check_call(cmd, stdin=subprocess.PIPE)
        except KeyboardInterrupt:
            pass
        except Exception as e:
            print(e)
            return False
    return True


def build_package(filename, outputDir):
    """ Will in future be moved to a separate part of the module """
    spec = YpkgSpec()
    if not spec.load_from_path(filename):
        print("Unable to continue - aborting")
        sys.exit(1)

    possibles = ["{}/.config/solus/packager", "{}/.solus/packager", "{}/.evolveos/packager"]

    packager_name = ypkg2.packager_name
    packager_email = ypkg2.packager_email

    dflt = True
    for item in possibles:
        fpath = item.format(os.path.expanduser("~"))
        if not os.path.exists(fpath):
            continue
        try:
            c = ConfigObj(fpath)
            pname = c["Packager"]["Name"]
            pemail = c["Packager"]["Email"]

            packager_name = pname
            packager_email = pemail
            dflt = False
            break
        except Exception as e:
            console_ui.emit_error("Config", "Error in packager config:")
            print(e)
            dflt = True
            break
    if dflt:
        packager_name = ypkg2.packager_name
        packager_email = ypkg2.packager_email
        console_ui.emit_warning("Config", "Using default packager values")
        print("  Name: {}".format(packager_name))
        print("  Email: {}".format(packager_email))

    spec.packager_name = packager_name
    spec.packager_email = packager_email
    # Try to load history
    dirn = os.path.dirname(filename)
    hist = os.path.join(dirn, "history.xml")
    if os.path.exists(hist):
        if not spec.load_history(hist):
            sys.exit(1)

    metadata.initialize_timestamp(spec)

    manager = SourceManager()
    if not manager.identify_sources(spec):
        print("Unable to continue - aborting")
        sys.exit(1)

    # Dummy content
    console_ui.emit_info("Info", "Building {}-{}".
                         format(spec.pkg_name, spec.pkg_version))

    ctx = YpkgContext(spec)

    need_verify = []
    for src in manager.sources:
        if src.cached(ctx):
            need_verify.append(src)
            continue
        if not src.fetch(ctx):
            console_ui.emit_error("Source", "Cannot continue without sources")
            sys.exit(1)
        need_verify.append(src)

    for verify in need_verify:
        if not verify.verify(ctx):
            console_ui.emit_error("Source", "Cannot verify sources")
            sys.exit(1)

    steps = {
        'setup': spec.step_setup,
        'build': spec.step_build,
        'install': spec.step_install,
        'check': spec.step_check,
        'profile': spec.step_profile,
    }

    r_runs = list()

    # Before we get started, ensure PGOs are cleaned
    if not ctx.clean_pgo():
        console_ui.emit_error("Build", "Failed to clean PGO directories")
        sys.exit(1)

    if not ctx.clean_install():
        console_ui.emit_error("Build", "Failed to clean install directory")
        sys.exit(1)
    if not ctx.clean_pkg():
        console_ui.emit_error("Build", "Failed to clean pkg directory")

    possible_sets = []
    # Emul32 is *always* first
    # AVX2 emul32 comes first too so "normal" emul32 can override it
    if spec.pkg_emul32:
        if spec.pkg_avx2:
            # Emul32, avx2 build
            possible_sets.append((True, True))
        # Normal, no-avx2, emul32 build
        possible_sets.append((True, False))

    # Build AVX2 before native, but after emul32
    if spec.pkg_avx2:
        possible_sets.append((False, True))

    # Main step, always last
    possible_sets.append((False, False))

    for emul32, avx2 in possible_sets:
        r_steps = list()
        c = YpkgContext(spec, emul32=emul32, avx2=avx2)
        if spec.step_profile is not None:
            c = YpkgContext(spec, emul32=emul32, avx2=avx2)
            c.enable_pgo_generate()
            r_steps.append(['setup', c])
            r_steps.append(['build', c])
            r_steps.append(['profile', c])
            c = YpkgContext(spec, emul32=emul32, avx2=avx2)
            c.enable_pgo_use()
            r_steps.append(['setup', c])
            r_steps.append(['build', c])
            r_steps.append(['install', c])
            r_steps.append(['check', c])
        else:
            c = YpkgContext(spec, emul32=emul32, avx2=avx2)
            r_steps.append(['setup', c])
            r_steps.append(['build', c])
            r_steps.append(['install', c])
            r_steps.append(['check', c])
        r_runs.append((emul32, avx2, r_steps))

    for emul32, avx2, run in r_runs:
        if emul32:
            console_ui.emit_info("Build", "Building for emul32")
        else:
            console_ui.emit_info("Build", "Building native package")
        if avx2:
            console_ui.emit_info("Build", "Building for AVX2 optimisations")

        for step, context in run:
            # When doing setup, always do pre-work by blasting away any
            # existing build directories for the current context and then
            # re-extracting sources
            if step == "setup":
                if not clean_build_dirs(context):
                    sys.exit(1)

                # Only ever extract the primary source ourselves
                if spec.pkg_extract:
                    src = manager.sources[0]
                    console_ui.emit_info("Source",
                                         "Extracting source")
                    if not src.extract(context):
                        console_ui.emit_error("Source",
                                              "Cannot extract sources")
                        sys.exit(1)

                if spec.step_profile:
                    try:
                        if not os.path.exists(context.get_pgo_dir()):
                            os.makedirs(context.get_pgo_dir(), 00755)
                    except Exception as e:
                        console_ui.emit_error("Source", "Error creating dir")
                        print(e)
                        sys.exit(1)

            work_dir = manager.get_working_dir(context)
            if not os.path.exists(work_dir):
                try:
                    os.makedirs(work_dir, mode=00755)
                except Exception as e:
                    console_ui.emit_error("Source", "Error creating directory")
                    print(e)
                    sys.exit(1)

            r_step = steps[step]
            if not r_step:
                continue

            console_ui.emit_info("Build", "Running step: {}".format(step))

            if execute_step(context, r_step, step, work_dir):
                console_ui.emit_success("Build", "{} successful".
                                        format(step))
                continue
            console_ui.emit_error("Build", "{} failed for {}".format(step, spec.pkg_name))
            sys.exit(1)

    # Compress manpage files
    man_dirs = [
        "{}/usr/share/man".format(ctx.get_install_dir()),
        "{}/usr/man".format(ctx.get_install_dir()),
    ]
    for dir in man_dirs:
        if not os.path.exists(dir):
            continue

        console_ui.emit_info("Man", "Compressing manpages in '{}'...".format(dir))
        try:
            (compressed, saved) = compress_man_pages(dir)
            console_ui.emit_success("Man", "Compressed {} file(s), saving {}".format(compressed, humanize(saved)))
        except Exception as e:
            console_ui.emit_warning("Man", "Failed to compress man pages in '{}'".format(dir))
            print(e)
    
    # Now try to compress any info pages
    info_dir = "{}/usr/share/info".format(ctx.get_install_dir())
    if os.path.exists(info_dir):
        console_ui.emit_info("Man", "Compressing info pages...")
        try:
            (compressed, saved) = compress_info_pages(info_dir)
            console_ui.emit_success("Man", "Compressed {} file(s), saving {}".format(compressed, humanize(saved)))
        except Exception as e:
            console_ui.emit_warning("Man", "Failed to compress info pages")
            print(e)

    # Add user patterns - each consecutive package has higher priority than the
    # package before it, ensuring correct levels of control
    gene = PackageGenerator(spec)
    count = 0
    for pkg in spec.patterns:
        for pt in spec.patterns[pkg]:
            gene.add_pattern(pt, pkg, priority=PRIORITY_USER + count)
        count += 1

    idir = ctx.get_install_dir()
    bad_dir = os.path.join(idir, "emul32")
    if os.path.exists(bad_dir):
        shutil.rmtree(bad_dir)

    for root, dirs, files in os.walk(idir):
        for f in files:
            fpath = os.path.join(root, f)

            localpath = remove_prefix(fpath, idir)
            gene.add_file(localpath)
        if len(dirs) == 0 and len(files) == 0:
            console_ui.emit_warning("Package", "Including empty directory: {}".
                                    format(remove_prefix(root, idir)))
            gene.add_file(remove_prefix(root, idir))

        # Handle symlinks to directories.
        for d in dirs:
            fpath = os.path.join(root, d)
            if os.path.islink(fpath):
                gene.add_file(remove_prefix(fpath, idir))

    if not os.path.exists(ctx.get_packaging_dir()):
        try:
            os.makedirs(ctx.get_packaging_dir(), mode=00755)
        except Exception as e:
            console_ui.emit_error("Package", "Failed to create pkg dir")
            print(e)
            sys.exit(1)

    exa = PackageExaminer()
    # Avoid expensive self calculations for kernels
    exa.can_kernel = True
    if spec.get_component("main") == "kernel.image":
        exa.can_kernel = False

    exaResults = exa.examine_packages(ctx, gene.packages.values())
    if exaResults is None:
        console_ui.emit_error("Package", "Failed to correctly examine all "
                              "packages.")
        sys.exit(1)

    deps = DependencyResolver()
    if not deps.compute_for_packages(ctx, gene, exaResults):
        console_ui.emit_error("Dependencies", "Failed to compute all"
                              " dependencies")
        sys.exit(1)

    dbgs = ["/usr/lib64/debug", "/usr/lib/debug", "/usr/lib32/debug"]
    if ctx.can_dbginfo:
        for dbg in dbgs:
            fpath = os.path.join(ctx.get_install_dir(), dbg[1:])
            if not os.path.exists(fpath):
                continue
            for root, dirs, files in os.walk(fpath):
                # Empty directories in dbginfo we don't care about.
                for f in files:
                    fpath = os.path.join(root, f)

                    localpath = remove_prefix(fpath, idir)

                    gene.add_file(localpath)

    if len(gene.packages) == 0:
        console_ui.emit_error("Package", "No resulting packages found")
        w = "https://solus-project.com/articles/packaging/"
        print("Ensure your files end up in $installdir. Did you mean to "
              "use %make_install?\n\nPlease see the help center: {}".format(w))
        sys.exit(1)

    gene.emit_packages()
    # TODO: Ensure main is always first
    for package in sorted(gene.packages):
        pkg = gene.packages[package]
        files = sorted(pkg.emit_files())
        if len(files) == 0:
            console_ui.emit_info("Package", "Skipping empty package: {}".
                                 format(package))
            continue
        metadata.create_eopkg(ctx, gene, pkg, outputDir)

    # Write out the final pspec
    metadata.write_spec(ctx, gene, outputDir)

    for pkg in spec.patterns:
        if pkg in gene.packages:
            continue
        nm = spec.get_package_name(pkg)
        console_ui.emit_warning("Package:{}".format(pkg),
                                "Did not produce {} by any pattern".format(nm))

    # TODO: Consider warning about unused patterns
    ctx.clean_pkg()
    console_ui.emit_success("Package", "Building complete")
    sys.exit(0)
