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

from .tuning import TuningFlag, TuningGroup


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
        """ Load a set of macros from a file """

        # Load actions
        if "actions" in data:
            actions = data["actions"]

            if not isinstance(actions, list):
                raise ValueError("Expected list of actions in macro config")

            for action in actions:
                for key, value in action.items():
                    description = value["description"]
                    command = value["command"]

                    self.actions[key] = Action(description, command)

        # Load definitions
        if "defines" in data:
            defines = data["defines"]

            if not isinstance(defines, list):
                raise ValueError("Expected list of definitions in macro config")

            for define in defines:
                for key, value in define.items():
                    self.definitions[key] = value

        # Load flags
        if "flags" in data:
            flags = data["flags"]

            if not isinstance(flags, list):
                raise ValueError("Expected list of flag groups in macro config")

            for group in flags:
                if not isinstance(group, dict):
                    raise ValueError("Expected dictionary of flags in macro config")

                for k, v in group.items():
                    compiler_flags = TuningFlag()
                    compiler_flags.parse(v)
                    self.flags[k] = compiler_flags

        # Load tunings
        if "tuning" in data:
            tuning = data["tuning"]

            if not isinstance(tuning, list):
                raise ValueError("Expected list of tuning groups in macro config")

            for group in tuning:
                if not isinstance(group, dict):
                        raise ValueError("Expected dictionary of tuning groups in macro config")

                for key, value in group.items():
                    tuning_group = TuningGroup()
                    tuning_group.parse(value)
                    self.tuning[key] = tuning_group

        # Load the default tuning groups
        if "defaultTuningGroups" in data:
            self.default_tuning_groups = data["defaultTuningGroups"]

    def add_definition(self, key: str, value: str) -> None:
        self.definitions[key] = value

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
