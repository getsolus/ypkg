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


import magic
import re
import os
import subprocess
import sys
import shutil
import multiprocessing
import xattr
import base64

from .util import console_ui, readlink, remove_prefix, EMUL32PC

global share_ctx


v_dyn = re.compile(r".*ELF (64|32)\-bit LSB shared object,")
v_bin = re.compile(r".*ELF (64|32)\-bit LSB executable,")
v_pie = re.compile(r".*ELF (64|32)\-bit LSB pie executable,")
v_rel = re.compile(r".*ELF (64|32)\-bit LSB relocatable,")
shared_lib = re.compile(r".*Shared library: \[(.*)\].*")
r_path = re.compile(r".*Library rpath: \[(.*)\].*")
run_path = re.compile(r".*Library runpath: \[(.*)\].*")
r_soname = re.compile(r".*Library soname: \[(.*)\].*")

# Section names carrying GCC LTO bytecode
lto_section_name = re.compile(r"^\.(?:gnu\.lto|gnu\.debuglto|llvm\.lto)")

# Raw LLVM bitcode objects
llvm_bitcode_magic = re.compile(r"^LLVM IR bitcode")

# Parse output of `readelf -S`
readelf_section = re.compile(
    r"^\s*\[\s*\d+\]\s+(\S+)\s+(\S+)\s+\S+\s+\S+\s+(\S+)\s+\S+(.*)$"
)

# When run on an archive, readelf prefixes each member with a 'File:' line.
readelf_member = re.compile(r"^File:\s+(.+)$")

# readelf refuses to dump sections of raw LLVM bitcode members.
readelf_bitcode = re.compile(r"^readelf: Error: This is a LLVM bitcode file")

global_xattrs = dict()


def is_pkgconfig_file(pretty, mgs):
    """Simple as it sounds, work out if this is a pkgconfig file"""
    if pretty.endswith(".pc"):
        pname = os.path.basename(os.path.dirname(pretty))
        if pname == "pkgconfig":
            return True
    return False


def is_soname_link(file, mgs):
    """Used to detect soname links"""
    if not file.endswith(".so"):
        return False

    if os.path.islink(file) and not os.path.isdir(file):
        return True
    return False


def is_static_archive(file, mgs):
    """Very trivially determine .a files"""
    if not file.endswith(".a"):
        return False

    if mgs != "current ar archive":
        return False

    if os.path.islink(file) or os.path.isdir(file):
        return False

    return True


def is_system_map(file, mgs):
    """Ensure we have a system map file"""
    if "kernel/System.map-" not in file:
        return False

    if mgs != "ASCII text":
        return False

    if os.path.islink(file) or os.path.isdir(file):
        return False

    return True


class LtoBytecodeError(Exception):
    """Raised by examine workers when an installed .a/.o file only contains
    LTO bytecode without real object code. Such objects were built with
    LTO but without -ffat-lto-objects and are unusable."""

    def __init__(self, pretty):
        Exception.__init__(self, pretty)
        self.pretty = pretty


def may_carry_lto_bytecode(file, mgs):
    """Filter for installed objects that may carry unusable LTO bytecode"""
    if file.endswith(".ko"):
        return False
    if is_static_archive(file, mgs):
        return True
    return bool(file.endswith(".o") and v_rel.match(mgs))


def parse_readelf_section(line):
    """Parse a readelf section header line into a (name, type, size, flags)
    tuple, or None if the line isn't one"""
    m = readelf_section.match(line)
    if m is None:
        return None

    name = m.group(1)
    sec_type = m.group(2)
    size = int(m.group(3), 16)

    rest = m.group(4).strip().split()
    flags = rest[0] if rest and rest[0].isalpha() else ""

    return (name, sec_type, size, flags)


def scan_object_lto_bytecode(file):
    """Scan a standalone ELF relocatable for LTO bytecode without any real
    code, i.e. an object compiled with LTO but without -ffat-lto-objects.

    Such objects only contain LTO sections alongside empty placeholder
    sections, and are unusable when linked without the LTO plugin. Returns
    True when the object is affected, False otherwise.
    """
    try:
        proc = subprocess.Popen(
            ["readelf", "-S", "-W", file],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
    except OSError as e:
        console_ui.emit_warning(
            "LTO", f"Failed to scan object file for LTO bytecode: {file}"
        )
        print(e)
        return False

    has_lto = False
    has_code = False

    out = proc.stdout
    if out is None:
        proc.wait()
        return False

    try:
        for line in out:
            sec = parse_readelf_section(line)
            if sec is None:
                continue
            name, sec_type, size, flags = sec
            if lto_section_name.match(name):
                has_lto = True
            elif sec_type in ("PROGBITS", "NOBITS") and "A" in flags and size > 0:
                has_code = True
    except (OSError, ValueError, UnicodeDecodeError) as e:
        console_ui.emit_warning(
            "LTO", f"Failed to scan object file for LTO bytecode: {file}"
        )
        print(e)
        return False
    finally:
        try:
            proc.kill()
        except OSError:
            pass
        try:
            proc.wait()
        except OSError:
            pass

    return has_lto and not has_code


def scan_archive_lto_bytecode(file):
    """Scan a static archive for members that only contain LTO bytecode
    without any real code, i.e. objects compiled with LTO but without
    -ffat-lto-objects.

    Returns the name of the first offending member, or None when the archive
    only contains usable objects. Members that are raw LLVM bitcode (Clang
    LTO objects) are reported as well.
    """
    try:
        proc = subprocess.Popen(
            ["readelf", "-S", "-W", file],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
    except OSError as e:
        console_ui.emit_warning(
            "LTO", f"Failed to scan archive for LTO bytecode: {file}"
        )
        print(e)
        return None

    offending = None
    member = None
    has_lto = False
    has_code = False

    def bad_member():
        return member if has_lto and not has_code else None

    out = proc.stdout
    if out is None:
        proc.wait()
        return None

    try:
        for line in out:
            m = readelf_member.match(line)
            if m:
                # New member starts, check the previous one
                offending = bad_member()
                if offending:
                    break
                member = m.group(1).strip()
                has_lto = False
                has_code = False
                continue
            if readelf_bitcode.match(line):
                # Raw LLVM bitcode member is LTO bytecode without any code
                offending = member
                break
            sec = parse_readelf_section(line)
            if sec is None:
                continue
            name, sec_type, size, flags = sec
            if lto_section_name.match(name):
                has_lto = True
            elif sec_type in ("PROGBITS", "NOBITS") and "A" in flags and size > 0:
                has_code = True
    except (OSError, ValueError, UnicodeDecodeError) as e:
        console_ui.emit_warning(
            "LTO", f"Failed to scan archive for LTO bytecode: {file}"
        )
        print(e)
        return None
    finally:
        try:
            proc.kill()
        except OSError:
            pass
        try:
            proc.wait()
        except OSError:
            pass

    if offending is None:
        offending = bad_member()
    return offending


class FileReport:
    pkgconfig_deps = None
    pkgconfig_name = None

    emul32 = False

    soname = None
    symbol_deps = None

    rpaths = None

    soname_links = None

    xattrs = None

    # Dependent kernel versions
    dep_kernel = None
    prov_kernel = None

    def scan_kernel(self, file):
        """Scan a .ko file to figure out which kernel this depends on"""
        cmd = 'LC_ALL=C /sbin/modinfo --field=vermagic "{}"'.format(file)
        try:
            output = subprocess.check_output(cmd, shell=True)
        except Exception as e:
            console_ui.emit_warning(
                "File", "Failed to scan kernel modules for path: {}".format(file)
            )
            return
        line = output.split("\n")[0]
        splits = line.strip().split(" ")
        if "modversions" not in splits:
            return
        if "mod_unload" not in splits:
            return
        self.dep_kernel = splits[0].strip()

    def scan_binary(self, file, check_soname=False):
        cmd = 'LC_ALL=C /usr/bin/readelf -d "{}"'.format(file)
        try:
            output = subprocess.check_output(cmd, shell=True).decode()
        except Exception as e:
            console_ui.emit_warning(
                "File", "Failed to scan binary deps for path: {}".format(file)
            )
            return

        for line in output.split("\n"):
            line = line.strip()

            # Match rpath
            r = r_path.match(line)
            if r:
                if self.rpaths is None:
                    self.rpaths = set()
                self.rpaths.update(r.group(1).split(":"))
                continue

            # Also check runpath
            r2 = run_path.match(line)
            if r2:
                if self.rpaths is None:
                    self.rpaths = set()
                self.rpaths.update(r2.group(1).split(":"))
                continue

            # Match direct needed dependency
            m = shared_lib.match(line)
            if m:
                if self.symbol_deps is None:
                    self.symbol_deps = set()
                self.symbol_deps.add(m.group(1))
                continue

            # Check the soname for this binary file
            if check_soname:
                so = r_soname.match(line)
                if so:
                    self.soname = so.group(1)

    def scan_pkgconfig(self, file):
        sub = ""
        pcDir = os.path.dirname(file)
        pcPaths = []
        # Ensure we account for private pkgconfig deps too
        if self.emul32:
            pcPaths.append(os.path.join(pcDir, "../../lib32/pkgconfig"))
            pcPaths.append(EMUL32PC)
        else:
            pcPaths.append(os.path.join(pcDir, "../../lib64/pkgconfig"))
            pcPaths.append(os.path.join(pcDir, "../../lib/pkgconfig"))
        pcPaths.append(os.path.join(pcDir, "../../share/pkgconfig"))
        pkgConfigPaths = []
        for path in pcPaths:
            p = os.path.abspath(path)
            if p and os.path.exists(p) and p not in pkgConfigPaths:
                pkgConfigPaths.append(p)

        if len(pkgConfigPaths) > 0:
            sub = 'PKG_CONFIG_PATH="{}" '.format(":".join(pkgConfigPaths))

        cmds = [
            'LC_ALL=C {}pkg-config --print-requires "{}"',
            'LC_ALL=C {}pkg-config --print-requires-private "{}"',
        ]

        pcname = os.path.basename(file).split(".pc")[0]
        self.pkgconfig_name = pcname

        if not share_ctx.spec.pkg_autodep:
            return
        for cmd in cmds:
            try:
                out = subprocess.check_output(
                    cmd.format(sub, file), shell=True
                ).decode()
            except Exception as e:
                print(e)
                continue
            for line in out.split("\n"):
                line = line.strip()

                if line == "":
                    continue
                name = None
                # In future we'll do something useful with versions
                if ">=" in line:
                    name = line.split(">=")[0]
                elif "=" in line:
                    # This is an internal dependency
                    name = line.split("=")[0]
                else:
                    name = line
                name = name.strip()

                if not self.pkgconfig_deps:
                    self.pkgconfig_deps = set()
                self.pkgconfig_deps.add(name)

    def add_solink(self, file, pretty):
        """.so links are almost always split into -devel subpackages in ypkg,
        unless explicitly overriden. However, they are useless without the
        actual versioned so they link to. Therefore, we add an automatic
        dependency to the hosting package when we find one of these, i.e:

        zlib:
            /usr/lib64/libz.so.1.2.8
        zlib-devel:
            /usr/lib64/libz.so -> libz.so.1.2.8

        zlib-devel -> zlib
        """
        fpath = readlink(file)

        dirn = os.path.dirname(file)
        fobj = os.path.join(dirn, fpath)

        try:
            mg = magic.from_file(fobj)
        except Exception as e:
            return

        if not v_dyn.match(mg):
            return
        fpath = remove_prefix(fobj, share_ctx.get_install_dir())
        if not self.soname_links:
            self.soname_links = set()
        self.soname_links.add(fpath)

    def add_kernel_prov(self, file):
        self.prov_kernel = str(file.split("System.map-")[1])

    def __init__(self, pretty, file, mgs):
        global share_ctx
        self.pretty = pretty
        self.file = file

        if pretty.startswith("/usr/lib32/") or pretty.startswith("/lib32"):
            self.emul32 = True
        if is_pkgconfig_file(pretty, mgs):
            self.scan_pkgconfig(file)
        if is_system_map(pretty, mgs):
            self.add_kernel_prov(file)

        # Some things omit automatic dependencies
        if share_ctx.spec.pkg_autodep:
            if is_soname_link(file, mgs):
                self.add_solink(file, pretty)
            elif v_dyn.match(mgs):
                self.scan_binary(file, True)
            elif v_bin.match(mgs):
                self.scan_binary(file, False)
            elif v_pie.match(mgs):
                self.scan_binary(file, False)
            elif v_rel.match(mgs) and file.endswith(".ko"):
                self.scan_kernel(file)


def strip_file(context, pretty, file, magic_string, mode=None):
    """Schedule a strip, basically."""
    if not context.spec.pkg_strip:
        return
    exports = ["LC_ALL=C"]
    if context.spec.pkg_optimize and not context.spec.pkg_clang:
        if (
            "thin-lto" in context.spec.pkg_optimize
            or "lto" in context.spec.pkg_optimize
        ):
            exports.extend(['AR="gcc-ar"', 'RANLIB="gcc-ranlib"', 'NM="gcc-nm"'])
    else:
        if context.spec.pkg_clang:
            exports.extend(['AR="llvm-ar"', 'RANLIB="llvm-ranlib"', 'NM="llvm-nm"'])

    cmd = '{} strip {} "{}"'
    flags = ""
    if mode == "shared":
        flags = "--strip-unneeded"
    elif mode == "ko":
        flags = "-g --strip-unneeded"
    elif mode == "ar" or mode == "object":
        flags = "--strip-debug -p -R .gnu.lto_* -R .gnu.debuglto_* -R .llvm.lto -N __gnu_lto_v1"
        if context.spec.pkg_clang:
            cmd = '{} llvm-objcopy {} "{}"'
    try:
        s = " ".join(exports)
        subprocess.check_call(cmd.format(s, flags, file), shell=True)
        console_ui.emit_info("Stripped", pretty)
    except Exception as e:
        console_ui.emit_warning("Strip", "Failed to strip '{}'".format(pretty))
        print(e)


def get_debug_path(context, file, magic_string):
    """Grab the NT_GNU_BUILD_ID"""
    cmd = 'LC_ALL=C readelf -n "{}"'.format(file)
    try:
        lines = subprocess.check_output(cmd, shell=True).decode()
    except Exception as e:
        return None

    for line in lines.split("\n"):
        if "Build ID:" not in line:
            continue
        v = line.split(":")[1].strip()

        libdir = "/usr/lib"
        if "ELF 32" in magic_string:
            libdir = "/usr/lib32"

        path = os.path.join(libdir, "debug", ".build-id", v[0:2], v[2:])
        return path + ".debug"
    return None


def get_xattrs(context, pretty, file):
    attributes = {}

    try:
        xt = xattr.xattr(file)
        if xt:
            for key in xt:
                attributes[str(key)] = base64.b64encode(xt[key]).decode("utf-8")
    except Exception as ex:
        console_ui.emit_warning("XAttr", "Failed to determine xattr")
        print(ex)
    return attributes


def examine_file(*args):
    global share_ctx
    package = args[0]
    pretty = args[1]
    file = args[2]
    mgs = args[3]

    context = share_ctx

    # Static archives/object files may carry only LTO bytecode which are unusable without
    # real code. This must run before the strip below, which discards the LTO sections
    # from .a/.o files.
    if may_carry_lto_bytecode(file, mgs):
        if mgs == "current ar archive":
            offender = scan_archive_lto_bytecode(file)
        else:
            offender = scan_object_lto_bytecode(file)
        if offender:
            raise LtoBytecodeError(pretty)

    xattrs = None
    if v_dyn.match(mgs):
        # Get soname, direct deps and strip
        store_debug(context, pretty, file, mgs)
        strip_file(context, pretty, file, mgs, mode="shared")
    elif v_bin.match(mgs) or v_pie.match(mgs):
        # Preserve xattr *before* stripping the file.
        xattrs = get_xattrs(context, pretty, file)
        # Get direct deps, and strip
        store_debug(context, pretty, file, mgs)
        strip_file(context, pretty, file, mgs, mode="executable")
    elif v_rel.match(mgs):
        # Kernel object in all probability
        if file.endswith(".ko"):
            store_debug(context, pretty, file, mgs)
            strip_file(context, pretty, file, mgs, mode="ko")
        elif file.endswith(".o"):
            strip_file(context, pretty, file, mgs, mode="object")
    elif mgs == "current ar archive":
        # Strip only.
        strip_file(context, pretty, file, mgs, mode="ar")

    freport = FileReport(pretty, file, mgs)
    if xattrs and len(xattrs) > 0:
        freport.xattrs = xattrs
    return freport


def store_debug(context, pretty, file, magic_string):
    if not context.can_dbginfo:
        return
    if not context.spec.pkg_debug:
        return

    did = get_debug_path(context, file, magic_string)

    if did is None:
        if "ELF 32" in magic_string:
            did = "/usr/lib32/debug/{}.debug".format(pretty)
        else:
            did = "/usr/lib/debug/{}.debug".format(pretty)

    did_full = os.path.join(context.get_install_dir(), did[1:])

    # Account for race condition in directory creation
    dirs = os.path.dirname(did_full)
    try:
        os.makedirs(dirs, mode=0o0755)
    except Exception as e:
        pass
    if not os.path.exists(dirs):
        console_ui.emit_error("Debug", "Failed to make directory")
        return

    cmd = 'objcopy --only-keep-debug "{}" "{}"'.format(file, did_full)
    try:
        subprocess.check_call(cmd, shell=True)
    except Exception as e:
        console_ui.emit_warning("objcopy", "Failed --only-keep-debug")
        return
    cmd = 'objcopy --add-gnu-debuglink="{}" "{}"'.format(did_full, file)
    try:
        subprocess.check_call(cmd, shell=True)
    except Exception as e:
        console_ui.emit_warning("objcopy", "Failed --add-gnu-debuglink")
        return


class PackageExaminer:
    """Responsible for identifying files suitable for further examination,
    such as those that should be removed, checked for dependencies,
    providers, and even those that should be stripped
    """

    def __init__(self):
        self.libtool_file = re.compile("libtool library file, ASCII text.*")
        self.can_kernel = True

    def should_nuke_file(self, context, pretty, file, mgs):
        # it's not that we hate.. Actually, no, we do. We hate you libtool.
        if context.spec.pkg_lastrip and self.libtool_file.match(mgs):
            return True
        if pretty == "/usr/share/info/dir":
            return True
        if pretty.startswith("/emul32"):
            return True
        # Nuke AVX2 dir .a files with no remorse
        if pretty.startswith("/usr/lib64/glibc-hwcaps/x86-64-v3/"):
            if ".so" not in pretty:
                return True
            # Don't want .so links, they're useless.
            if pretty.endswith(".so") and os.path.islink(file):
                return True
        return False

    def file_is_of_interest(self, pretty, file, mgs):
        """So we can keep our list of things to check low"""
        if v_dyn.match(mgs) or v_bin.match(mgs) or v_pie.match(mgs) or v_rel.match(mgs):
            if not self.can_kernel and file.endswith(".ko"):
                return False
            return True
        if is_pkgconfig_file(pretty, mgs):
            return True
        if is_soname_link(file, mgs):
            return True
        if is_static_archive(file, mgs):
            return True
        if self.can_kernel and is_system_map(file, mgs):
            return True
        return False

    def examine_package(self, context, package):
        """Examine the given package and update symbols, etc."""
        install_dir = context.get_install_dir()

        global share_ctx
        global global_xattrs

        share_ctx = context

        # Right now we actually only care about magic matching
        removed = set()

        pool = multiprocessing.Pool()
        results = list()
        lto_offenders = list()

        for file in package.emit_files():
            if file[0] == "/":
                file = file[1:]
            fpath = os.path.join(install_dir, file)
            try:
                mgs = magic.from_file(fpath)
            except Exception as e:
                print(e)
                continue
            if self.should_nuke_file(context, "/" + file, fpath, mgs):
                try:
                    if os.path.isfile(fpath):
                        os.unlink(fpath)
                    else:
                        shutil.rmtree(fpath)
                except Exception as e:
                    console_ui.emit_error(
                        "Clean", "Failed to remove unwantedfile: {}".format(e)
                    )
                    return False
                console_ui.emit_info(
                    "Clean", "Removed unwanted file: {}".format("/" + file)
                )
                removed.add("/" + file)
                continue

            # Raw LLVM bitcode objects are not ELF relocatables, so they never get
            # dispatched for examination. Catch them here with a magic check.
            # The entire file is unsuitable for distribution regardless.
            if llvm_bitcode_magic.match(mgs) and file.endswith(".o"):
                lto_offenders.append("/" + file)

            if not self.file_is_of_interest("/" + file, fpath, mgs):
                continue
            # Handle this asynchronously
            results.append(
                pool.apply_async(
                    examine_file, [package, "/" + file, fpath, mgs], callback=None
                )
            )

        pool.close()
        pool.join()

        infos = list()
        for x in results:
            try:
                infos.append(x.get())
            except LtoBytecodeError as e:
                lto_offenders.append(e.pretty)

        for info in infos:
            if not info.xattrs:
                continue
            global_xattrs[info.pretty] = info.xattrs

        for r in removed:
            package.remove_file(r)

        if len(lto_offenders) > 0:
            for pretty in lto_offenders:
                console_ui.emit_error(
                    "LTO",
                    "{} contains LTO bytecode without real object code".format(
                        pretty
                    ),
                )
            console_ui.emit_error(
                "LTO",
                "Installed .a/.o files must contain real compiled code. "
                "Preferably remove the offending file or rebuild with "
                "'fat-lto-objects' as part of the 'optimize' key."
            )

        return infos

    def examine_packages(self, context, packages):
        """Examine all packages, in order to update dependencies, etc"""
        console_ui.emit_info("Examine", "Examining packages")

        examinations = dict()
        for package in packages:
            ir = self.examine_package(context, package)
            if not ir:
                continue
            examinations[package.name] = ir
        return examinations
