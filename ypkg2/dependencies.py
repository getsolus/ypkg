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
from pisi.db.installdb import InstallDB
from pisi.db.packagedb import PackageDB
from pisi.db.filesdb import FilesDB
import os

# Provided historically for our pre-glvnd architecture.
# Technically speaking this isn't required anymore, but lets just
# play it safe for those directly using ypkg on old NVIDIA drivers.
ExceptionRules = [
    "libEGL.so",
    "libEGL.so.1",
    "libEGL.so.1.0.0",
    "libGLESv1_CM.so",
    "libGLESv1_CM.so.1",
    "libGLESv1_CM.so.1.1.0",
    "libGLESv2.so",
    "libGLESv2.so.2",
    "libGLESv2.so.2.0.0",
    "libGL.so",
    "libGL.so.1",
    "libGL.so.1.0.0",
    "libGL.so.1.2.0",
    "libglx.so",
    "libglx.so.1",
]


class DependencyResolver:

    idb = None
    pdb = None
    fdb = None

    global_rpaths = set()
    global_rpaths32 = set()
    global_sonames = dict()
    global_sonames32 = dict()
    global_pkgconfigs = dict()
    global_pkgconfig32s = dict()
    global_kernels = dict()
    gene = None

    bindeps_cache = dict()
    bindeps_emul32 = dict()

    pkgconfig_cache = dict()
    pkgconfig32_cache = dict()

    files_cache = dict()

    kernel_cache = dict()

    deadends = dict()

    # Cached from packagedb
    pkgConfigs = None
    pkgConfigs32 = None

    def search_file(self, fname):
        if fname[0] == '/':
            fname = fname[1:]
        if fname in self.deadends:
            return None
        if self.fdb.has_file(fname):
            return self.fdb.get_file(fname)
        # Nasty file conflict crap happened on update and the filesdb
        # is now inconsistent ..
        ret = self.fdb.search_file(fname)
        if len(ret) == 1:
            return ret[0]
        # Just blacklist further lookups here
        self.deadends[fname] = 0
        return None

    def __init__(self):
        """ Allows us to do look ups on all packages """
        self.idb = InstallDB()
        self.pdb = PackageDB()
        self.fdb = FilesDB()

        # Cache the pkgconfigs known in the pdb
        self.pkgConfigs, self.pkgConfigs32 = self.pdb.get_pkgconfig_providers()

    def get_symbol_provider(self, info, symbol):
        """ Grab the symbol from the local packages """
        if info.emul32:
            tgtMap = self.global_sonames32
            rPaths = self.global_rpaths32
        else:
            tgtMap = self.global_sonames
            rPaths = self.global_rpaths

        if symbol in tgtMap:
            pkgname = tgtMap[symbol]
            return self.ctx.spec.get_package_name(pkgname)

        # Check if its in any rpath
        for rpath in rPaths:
            fpath = os.path.join(rpath, symbol)
            pkg = self.gene.get_file_owner(fpath)
            if pkg:
                return self.ctx.spec.get_package_name(pkg.name)
        return None

    def get_symbol_external(self, info, symbol, paths=None):
        """ Get the provider of the required symbol from the files database,
            i.e. installed binary dependencies
        """
        # Try a cached approach first.
        if info.emul32:
            if symbol in self.bindeps_emul32:
                return self.bindeps_emul32[symbol]
        else:
            if symbol in self.bindeps_cache:
                return self.bindeps_cache[symbol]

        if symbol in ExceptionRules:
            if info.emul32:
                return "libglvnd-32bit"
            else:
                return "libglvnd"

        if not paths:
            paths = ["/usr/lib64", "/usr/lib"]
            if info.emul32:
                paths = ["/usr/lib32", "/usr/lib", "/usr/lib64"]

            if info.rpaths:
                paths.extend(info.rpaths)

        pkg = None
        for path in paths:
            fpath = os.path.join(path, symbol)
            if not os.path.exists(fpath):
                continue
            lpkg = None
            if fpath in self.files_cache:
                lpkg = self.files_cache[fpath]
            else:
                pkg = self.search_file(fpath)
                if pkg:
                    lpkg = pkg[0]
            if lpkg:
                if info.emul32:
                    self.bindeps_emul32[symbol] = lpkg
                else:
                    self.bindeps_cache[symbol] = lpkg
                console_ui.emit_info("Dependency",
                                     "{} adds dependency on {} from {}".
                                     format(info.pretty, symbol, lpkg))

                # Populate a global files cache, basically there is a high
                # chance that each package depends on multiple things in a
                # single package.
                for file in self.idb.get_files(lpkg).list:
                    self.files_cache["/" + file.path] = lpkg
                return lpkg
        return None

    def get_pkgconfig_provider(self, info, name):
        """ Get the internal provider for a pkgconfig name """
        if info.emul32:
            if name in self.global_pkgconfig32s:
                pkg = self.global_pkgconfig32s[name]
                return self.ctx.spec.get_package_name(pkg)
        if name in self.global_pkgconfigs:
            pkg = self.global_pkgconfigs[name]
            return self.ctx.spec.get_package_name(pkg)
        return None

    def get_pkgconfig_external(self, info, name):
        """ Get the external provider of a pkgconfig name """
        pkg = None

        if info.emul32:
            if name in self.pkgconfig32_cache:
                return self.pkgconfig32_cache[name]
        else:
            if name in self.pkgconfig_cache:
                return self.pkgconfig_cache[name]

        if info.emul32:
            # InstallDB set
            nom = self.fdb.get_pkgconfig32_provider(name)
            if nom:
                pkg = self.idb.get_package(nom[0])
            if not pkg:
                nom = self.fdb.get_pkgconfig_provider(name)
                if nom:
                    pkg = self.idb.get_package(nom[0])

            # PackageDB set
            if not pkg:
                if name in self.pkgConfigs32:
                    pkg = self.pdb.get_package(self.pkgConfigs32[name])
            if not pkg:
                if name in self.pkgConfigs:
                    pkg = self.pdb.get_package(self.pkgConfigs[name])
        else:
            nom = self.fdb.get_pkgconfig_provider(name)
            if nom:
                pkg = self.idb.get_package(nom[0])
            if not pkg:
                if name in self.pkgConfigs:
                    pkg = self.pdb.get_package(self.pkgConfigs[name])

        if not pkg:
            return None
        if info.emul32:
            self.pkgconfig32_cache[name] = pkg.name
        else:
            self.pkgconfig_cache[name] = pkg.name
        return pkg.name

    def handle_binary_deps(self, packageName, info):
        """ Handle direct binary dependencies """
        pkgName = self.ctx.spec.get_package_name(packageName)

        for sym in info.symbol_deps:
            r = self.get_symbol_provider(info, sym)
            if not r:
                r = self.get_symbol_external(info, sym)
                if not r:
                    print("Fatal: Unknown symbol: {}".format(sym))
                    continue
            # Don't self depend
            if pkgName == r:
                continue
            self.gene.packages[packageName].depend_packages.add(r)

    def handle_pkgconfig_deps(self, packageName, info):
        """ Handle pkgconfig dependencies """
        pkgName = self.ctx.spec.get_package_name(packageName)

        for item in info.pkgconfig_deps:

            prov = self.get_pkgconfig_provider(info, item)
            if not prov:
                prov = self.get_pkgconfig_external(info, item)

            if not prov:
                console_ui.emit_warning("PKGCONFIG", "Not adding unknown"
                                        " dependency {} to {}".
                                        format(item, pkgName))
                continue
            tgtPkg = self.gene.packages[packageName]

            # Yes, it's a set, but i  dont want the ui emission spam
            if prov in tgtPkg.depend_packages:
                continue
            # Forbid circular dependencies
            if pkgName == prov:
                continue
            tgtPkg.depend_packages.add(prov)

            console_ui.emit_info("PKGCONFIG", "{} adds dependency on {}".
                                 format(pkgName, prov))

    def handle_pkgconfig_provides(self, packageName, info):
        adder = None
        if info.emul32:
            adder = "pkgconfig32({})".format(info.pkgconfig_name)
        else:
            adder = "pkgconfig({})".format(info.pkgconfig_name)
        # TODO: Add versioning in examine.py .. ?
        self.gene.packages[packageName].provided_symbols.add(adder)
        pass

    def handle_soname_links(self, packageName, info):
        """ Add dependencies between packages due to a .so splitting """
        ourName = self.ctx.spec.get_package_name(packageName)

        for link in info.soname_links:
            fi = self.gene.get_file_owner(link)
            if not fi:
                console_ui.emit_warning("SOLINK", "{} depends on non existing "
                                        "soname link: {}".
                                        format(packageName, link))
                continue
            pkgName = self.ctx.spec.get_package_name(fi.name)
            if pkgName == ourName:
                continue
            self.gene.packages[packageName].depend_packages.add(pkgName)
            console_ui.emit_info("SOLINK", "{} depends on {} through .so link".
                                 format(ourName, pkgName))

    def get_kernel_provider(self, info, version):
        """ i.e. self dependency situation """
        if version in self.global_kernels:
            pkg = self.global_kernels[version]
            return self.ctx.spec.get_package_name(pkg)
        return None

    def get_kernel_external(self, info, version):
        """ Try to find the owning kernel for a version """
        if version in self.kernel_cache:
            return self.kernel_cache[version]

        paths = [
            "/usr/lib/kernel",
            "/usr/lib64/kernel"
        ]

        pkg = None
        for path in paths:
            # Special file in the main kernel package
            fpath = "{}/System.map-{}".format(path, version)
            if not os.path.exists(fpath):
                continue
            lpkg = None
            if fpath in self.files_cache:
                lpkg = self.files_cache[fpath]
            else:
                pkg = self.search_file(fpath)
                if pkg:
                    lpkg = pkg[0]
            if lpkg:
                self.kernel_cache[version] = lpkg
                console_ui.emit_info("Kernel",
                                     "{} adds module dependency on {} from {}".
                                     format(info.pretty, version, lpkg))

                # Populate a global files cache, basically there is a high
                # chance that each package depends on multiple things in a
                # single package.
                for file in self.idb.get_files(lpkg).list:
                    self.files_cache["/" + file.path] = lpkg
                return lpkg
        return None

    def handle_kernel_deps(self, packageName, info):
        """ Add dependency between packages due to kernel version """
        pkgName = self.ctx.spec.get_package_name(packageName)

        r = self.get_kernel_provider(info, info.dep_kernel)
        if not r:
            r = self.get_kernel_external(info, info.dep_kernel)
            if not r:
                print("Fatal: Unknown kernel: {}".format(sym))
                return
        # Don't self depend
        if pkgName == r:
            return
        self.gene.packages[packageName].depend_packages.add(r)

    def compute_for_packages(self, context, gene, packageSet):
        """ packageSet is a dict mapping here. """
        self.gene = gene
        self.packageSet = packageSet
        self.ctx = context

        # First iteration, collect the globals
        for packageName in packageSet:
            for info in packageSet[packageName]:
                if info.rpaths:
                    if info.emul32:
                        self.global_rpaths32.update(info.rpaths)
                    else:
                        self.global_rpaths.update(info.rpaths)
                if info.soname:
                    if info.emul32:
                        self.global_sonames32[info.soname] = packageName
                    else:
                        self.global_sonames[info.soname] = packageName
                if info.pkgconfig_name:
                    pcName = info.pkgconfig_name
                    if info.emul32:
                        self.global_pkgconfig32s[pcName] = packageName
                    else:
                        self.global_pkgconfigs[pcName] = packageName
                if info.prov_kernel:
                    self.global_kernels[info.prov_kernel] = packageName

        # Ok now find the dependencies
        for packageName in packageSet:
            for info in packageSet[packageName]:
                if info.symbol_deps:
                    self.handle_binary_deps(packageName, info)

                if info.pkgconfig_deps:
                    self.handle_pkgconfig_deps(packageName, info)

                if info.pkgconfig_name:
                    self.handle_pkgconfig_provides(packageName, info)

                if info.soname_links:
                    self.handle_soname_links(packageName, info)

                if info.dep_kernel:
                    self.handle_kernel_deps(packageName, info)
        return True
