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

from enum import Enum


class CompilerFlag(Enum):
    C = 1
    CXX = 2
    F = 3
    D = 4
    RUST = 5
    LD = 6


class CompilerFlags:
    c: str | None = None
    cxx: str | None = None
    f: str | None = None
    d: str | None = None
    rust: str | None = None
    ld: str | None = None

    def get(self, flag: CompilerFlag) -> str | None:
        match flag:
            case CompilerFlag.C:
                return self.c
            case CompilerFlag.CXX:
                return self.cxx
            case CompilerFlag.F:
                return self.f
            case CompilerFlag.D:
                return self.d
            case CompilerFlag.RUST:
                return self.rust
            case CompilerFlag.LD:
                return self.ld

    def parse(self, obj: dict[str, str | dict[str, str]]) -> None:
        for k, v in obj.items():
            match k:
                case "c":
                    self.c = v
                case "cxx":
                    self.cxx = v
                case "f":
                    self.f = v
                case "d":
                    self.d = v
                case "rust":
                    self.rust = v
                case "ld":
                    self.ld = v
                case _:
                    continue


class Toolchain(Enum):
    LLVM = 1
    GNU = 2


class TuningFlag:
    root: CompilerFlags = None
    gnu: CompilerFlags = None
    llvm: CompilerFlags = None

    def get(self, flag: CompilerFlag, toolchain: Toolchain) -> str:
        ret: str = None

        match toolchain:
            case Toolchain.GNU:
                ret = self.gnu.get(flag)
            case Toolchain.LLVM:
                ret = self.llvm.get(flag)

        if ret is None:
            ret = self.root.get(flag)

        return ret

    def parse(self, group: dict[str, str | dict[str, str]]) -> None:
        for key, value in group.items():
            match key:
                case "gnu":
                    self.gnu = CompilerFlags()
                    self.gnu.parse(value)
                case "llvm":
                    self.llvm = CompilerFlags()
                    self.llvm.parse(value)
                case _:
                    continue

        self.root = CompilerFlags()
        self.root.parse(group)


class TuningOption:
    enabled: list[str] = None
    disabled: list[str] = None

    def parse(self, options: dict[str, list[str]]) -> None:
        if "enabled" in options:
            enabled = options["enabled"]

            if isinstance(enabled, list):
                self.enabled = enabled
            else:
                self.enabled = [enabled]

        if "disabled" in options:
            disabled = options["disabled"]

            if isinstance(disabled, list):
                self.disabled = disabled
            else:
                self.disabled = [disabled]


class TuningGroup:
    root: TuningOption = None
    default: str | None = None
    options: dict[str, TuningOption] = None

    def parse(self, group: dict) -> None:
        self.options = {}

        for key, value in group.items():
            match key:
                case "default":
                    self.default = value
                case "options":
                    for option in value:
                        for k, v in option.items():
                            o = TuningOption()
                            o.parse(v)
                            self.options[k] = o
                case _:
                    continue

        self.root = TuningOption()
        self.root.parse(group)
