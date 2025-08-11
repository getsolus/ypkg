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


from .util import console_ui
from .macros import Macros
from .ypkgcontext import YpkgContext
from .ypkgspec import YpkgSpec

from collections import OrderedDict
import glob
import os
from pathlib import Path

from yaml import load as yaml_load

try:
    from yaml import CLoader as Loader
except Exception:
    from yaml import Loader


class ScriptGenerator:
    """Generates build scripts on the fly by providing a default header
    tailored to the current build context and performing substitution
    on exported macros from this instance"""

    arches: dict[str, Macros] = None
    macros: list[Macros] = None
    context: YpkgContext = None
    spec: YpkgSpec = None
    exports: OrderedDict[str, str] = None
    unexports: list[str] = None
    work_dir: str = None

    def __init__(self, context: YpkgContext, spec: YpkgSpec, work_dir: str):
        self.work_dir = work_dir
        self.arches = {}
        self.macros = []
        self.context = context
        self.spec = spec

        self.init_default_macros()
        self.init_default_exports()

        macros_path = os.path.join("/usr", "share", "ypkg", "macros")
        actions_path = os.path.join(macros_path, "actions")
        arches_path = os.path.join(macros_path, "arches")

        # Load all of the arches from the globbed files
        for file in glob.glob(arches_path + "/*.yaml"):
            try:
                with open(file, "r") as f:
                    yamlData = yaml_load(f, Loader=Loader)

                identifier = Path(file).stem
                self.arches[identifier] = Macros(yamlData)
            except ValueError as e:
                console_ui.emit_warning(
                    os.path.basename(file), f"Invalid arch definition: {e}"
                )
                continue
            except Exception as e:
                console_ui.emit_warning(
                    "SCRIPTS", f"Cannot load arch file '{file}': {e}"
                )
                continue

        # Load all of the macros from the globbed files
        for file in glob.glob(actions_path + "/*.yaml"):
            try:
                with open(file, "r") as f:
                    yamlData = yaml_load(f, Loader=Loader)

                self.macros.append(Macros(yamlData))
            except ValueError as e:
                console_ui.emit_warning(
                    os.path.basename(file), f"Invalid macro definition: {e}"
                )
                continue
            except Exception as e:
                console_ui.emit_warning(
                    "SCRIPTS", f"Cannot load macro file '{file}': {e}"
                )
                continue

    def define_export(self, key: str, value: str) -> None:
        """Define a shell export for scripts"""
        self.exports[key] = value

    def define_unexport(self, key: str) -> None:
        """Ensure key is unexported from shell script"""
        self.unexports.append(key)

    def init_default_macros(self) -> None:
        default_macros = Macros()

        if self.context.emul32:
            default_macros.add_definition("libdir", "/usr/lib32")
            default_macros.add_definition("LIBSUFFIX", "32")
        else:
            default_macros.add_definition("libdir", "/usr/lib64")
            default_macros.add_definition("LIBSUFFIX", "64")

        default_macros.add_definition("PREFIX", "/usr")

        default_macros.add_definition("installroot", self.context.get_install_dir())
        default_macros.add_definition("workdir", self.work_dir)
        default_macros.add_definition(
            "JOBS", "-j{}".format(self.context.build.jobcount)
        )
        default_macros.add_definition("YJOBS", "{}".format(self.context.build.jobcount))

        # Consider moving this somewhere else
        default_macros.add_definition("CFLAGS", " ".join(self.context.build.cflags))
        default_macros.add_definition("CXXFLAGS", " ".join(self.context.build.cxxflags))
        default_macros.add_definition("LDFLAGS", " ".join(self.context.build.ldflags))
        default_macros.add_definition(
            "RUSTFLAGS", " ".join(self.context.build.rustflags)
        )

        default_macros.add_definition("HOST", self.context.build.host)
        default_macros.add_definition("ARCH", self.context.build.arch)
        # Based on the default target list defined in rocBLAS's CMakeLists.txt
        default_macros.add_definition(
            "AMDGPUTARGETS",
            "gfx803;gfx900;gfx906;gfx908;gfx90a;gfx1010;gfx1030;gfx1100;gfx1101;gfx1102",
        )
        default_macros.add_definition("PKGNAME", self.spec.pkg_name)
        default_macros.add_definition("PKGFILES", self.context.files_dir)

        default_macros.add_definition("package", self.context.spec.pkg_name)
        default_macros.add_definition("release", self.context.spec.pkg_release)
        default_macros.add_definition("version", self.context.spec.pkg_version)
        default_macros.add_definition("sources", self.context.get_sources_directory())

        default_macros.add_definition("rootdir", self.context.get_package_root_dir())
        default_macros.add_definition("builddir", self.context.get_build_dir())

        self.macros.append(default_macros)

    def init_default_exports(self) -> None:
        """Initialise our exports"""
        self.exports = OrderedDict()
        self.unexports = []

        self.define_export("CFLAGS", " ".join(self.context.build.cflags))
        self.define_export("CXXFLAGS", " ".join(self.context.build.cxxflags))
        self.define_export("LDFLAGS", " ".join(self.context.build.ldflags))
        self.define_export("RUSTFLAGS", " ".join(self.context.build.rustflags))
        self.define_export("FFLAGS", " ".join(self.context.build.cxxflags))
        self.define_export("FCFLAGS", " ".join(self.context.build.cxxflags))
        self.define_export("PATH", self.context.get_path())
        self.define_export("workdir", "%workdir%")
        self.define_export("package", "%package%")
        self.define_export("release", "%release%")
        self.define_export("version", "%version%")
        self.define_export("sources", "%sources%")
        self.define_export("pkgfiles", "%PKGFILES%")
        self.define_export("installdir", "%installroot%")
        self.define_export("PKG_ROOT_DIR", "%rootdir%")
        # Build dir, which is one level up from the source directory.
        self.define_export("PKG_BUILD_DIR", "%builddir%")
        self.define_export("LT_SYS_LIBRARY_PATH", "%libdir%")
        self.define_export("CC", self.context.build.cc)
        self.define_export("CXX", self.context.build.cxx)
        if self.context.build.ld_as_needed:
            self.define_export("LD_AS_NEEDED", "1")

        # Handle lto correctly
        if self.context.spec.pkg_optimize and not self.context.spec.pkg_clang:
            if (
                "thin-lto" in self.context.spec.pkg_optimize
                or "lto" in self.context.spec.pkg_optimize
            ):
                self.define_export("AR", "gcc-ar")
                self.define_export("RANLIB", "gcc-ranlib")
                self.define_export("NM", "gcc-nm")
        else:
            if self.context.spec.pkg_clang:
                self.define_export("AR", "llvm-ar")
                self.define_export("RANLIB", "llvm-ranlib")
                self.define_export("NM", "llvm-nm")

        # Handle sccache. It is enabled together with ccache
        if os.path.exists("/usr/bin/sccache"):
            if self.context.build.ccache and self.spec.pkg_ccache:
                self.define_export("RUSTC_WRAPPER", "/usr/bin/sccache")

        # Source archives often have the version string as part of the file name which results in the version string
        # being part of the workdir path. Since ccache uses the file path as part of the cache key this can result in
        # very low cache hit rates when upgrading versions if the build references files via absolute paths. Luckily
        # ccache allows us to set the base_dir to avoid this problem which we can set as an environmental variable.
        # Ref: https://ccache.dev/manual/4.10.html#_compiling_in_different_directories
        if self.context.build.ccache and self.spec.pkg_ccache:
            self.define_export("CCACHE_BASEDIR", "%workdir%")

        if not console_ui.allow_colors:
            self.define_export("TERM", "dumb")

        # Mask display
        self.define_unexport("DISPLAY")
        # Mask sudo from anyone
        self.define_unexport("SUDO_USER")
        self.define_unexport("SUDO_GID")
        self.define_unexport("SUDO_UID")
        self.define_unexport("SUDO_COMMAND")
        self.define_unexport("CDPATH")

    def emit_exports(self) -> list[str]:
        """TODO: Grab known exports into an OrderedDict populated by an rc
        YAML file to allow easier manipulation"""
        ret = []
        for key in self.exports:
            ret.append('export {}="{}"'.format(key, self.exports[key]))

        unset_line = "unset {} || :".format(" ".join(self.unexports))
        ret.append(unset_line)
        return ret

    def is_valid_macro_char(self, char: chr) -> bool:
        if char.isalpha() or char.isdigit():
            return True
        if char == "_":
            return True

        return False

    def escape_single(self, line: str) -> (str, bool):
        offset = line.find("%")

        if offset < 0:
            return (line, False)

        pattern = "%"

        # Create a matcher in the format of %foo% or %bar
        for i in range(offset + 1, len(line)):
            if line[i] == "%":
                pattern += "%"
                break

            if self.is_valid_macro_char(line[i]):
                pattern += line[i]
            else:
                break

        isDefinition = pattern[-1] == "%"
        name = pattern.removeprefix("%").removesuffix("%")

        for macro in self.macros:
            if isDefinition:
                definition = macro.match_definition(name)

                if definition is None:
                    continue

                return (line.replace(pattern, str(definition).removesuffix("\n")), True)
            else:
                action = macro.match_action(name)

                if action is None:
                    continue

                return (
                    line.replace(pattern, str(action.command).removesuffix("\n")),
                    True,
                )

        # No matches, return the line as-is
        return (line, False)

    def escape_string(self, input_string: str) -> str:
        """Recursively escape our macros out of a string until no more of our
        macros appear in it"""
        ret = []

        for line in input_string.split("\n"):
            while True:
                (line, cont) = self.escape_single(line)
                if not cont:
                    ret.append(line)
                    break

        return "\n".join(ret)
