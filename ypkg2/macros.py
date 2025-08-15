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

from .util import console_ui
from .tuning import TuningFlag, TuningGroup

import glob
import os
from pathlib import Path

from yaml import load as yaml_load

try:
    from yaml import CLoader as Loader
except Exception as e:
    from yaml import Loader


class MacroError(Exception):
    """Exception raised for invalid macro definitions.

    Attributes:
        reason -- How the macro is invalid.
        message -- Explanation of the error.
    """

    def __init__(self, reason: str):
        self.reason = reason
        self.message = "Invalid macro definition"

        super.__init__(self.message)


class Action:
    description: str = None
    command: str = None

    def __init__(self, description: str, command: str):
        self.description = description
        self.command = command


class Macros:
    actions: dict[str, Action] = None
    definitions: dict[str, str] = None
    flags: dict[str, TuningFlag] = None
    tuning: dict[str, TuningGroup] = None
    default_tuning_groups: list[str] = None

    def __init__(self, yml: dict = None):
        self.actions = {}
        self.definitions = {}
        self.flags = {}
        self.tuning = {}
        self.default_tuning_groups = []

        if yml is not None:
            self._load(yml)

    def _load(self, data: dict) -> None:
        """Load a set of macros from a file"""

        # Load actions
        if "actions" in data:
            actions = data["actions"]

            if not isinstance(actions, list):
                raise MacroError("Expected list of actions in macro config")

            for action in actions:
                for key, value in action.items():
                    description = value["description"]
                    command = value["command"]

                    self.actions[key] = Action(description, command)

        # Load definitions
        if "defines" in data:
            defines = data["defines"]

            if not isinstance(defines, list):
                raise MacroError("Expected list of definitions in macro config")

            for define in defines:
                for key, value in define.items():
                    self.definitions[key] = value

        # Load flags
        if "flags" in data:
            flags = data["flags"]

            if not isinstance(flags, list):
                raise MacroError("Expected list of flag groups in macro config")

            for group in flags:
                if not isinstance(group, dict):
                    raise MacroError("Expected dictionary of flags in macro config")

                for k, v in group.items():
                    compiler_flags = TuningFlag()
                    compiler_flags.parse(v)
                    self.flags[k] = compiler_flags

        # Load tunings
        if "tuning" in data:
            tuning = data["tuning"]

            if not isinstance(tuning, list):
                raise MacroError("Expected list of tuning groups in macro config")

            for group in tuning:
                if not isinstance(group, dict):
                    raise MacroError(
                        "Expected dictionary of tuning groups in macro config"
                    )

                for key, value in group.items():
                    tuning_group = TuningGroup()
                    tuning_group.parse(value)
                    self.tuning[key] = tuning_group

        # Load the default tuning groups
        if "defaultTuningGroups" in data:
            self.default_tuning_groups = data["defaultTuningGroups"]

    def add_action(self, key: str, action: Action) -> None:
        """Add an action to the macro set.

        Parameters:
            key (str): The key to use for this action.
            action (Action): The action to add.
        """
        self.actions[key] = action

    def add_definition(self, key: str, value: str) -> None:
        """Add a definition to the macro set.

        Parameters:
            key (str): The key to use for this definition.
            value (str): The value of this definition.
        """
        self.definitions[key] = value

    def add_macros(self, other: "Macros") -> None:
        """Add actions and definitions from another Macros object.

        Parameters:
            other (Macros): The macros object to copy from.
        """
        for key, action in other.actions:
            self.add_action(key, action)

        for key, definition in other.definitions:
            self.add_definition(key, definition)

    def match_action(self, pattern: str) -> Action | None:
        if pattern in self.actions:
            return self.actions[pattern]
        else:
            return None

    def match_definition(self, pattern: str) -> str | None:
        if pattern in self.definitions:
            return self.definitions[pattern]
        else:
            return None


class MacroSet:
    macros: list[Macros] = None
    arches: dict[str, Macros] = None

    def __init__(self):
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
            except MacroError as e:
                console_ui.emit_warning(
                    os.path.basename(file), f"{e.message}: {e.reason}"
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
            except MacroError as e:
                console_ui.emit_warning(
                    os.path.basename(file), f"{e.message}: {e.reason}"
                )
                continue
            except Exception as e:
                console_ui.emit_warning(
                    "SCRIPTS", f"Cannot load macro file '{file}': {e}"
                )
                continue
