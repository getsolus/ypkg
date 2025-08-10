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


class Action:
    description: str = None
    command: str = None

    def __init__(self, description: str, command: str):
        self.description = description
        self.command = command


class Macros:
    actions: dict[str, Action] = None
    definitions: dict[str, str] = None

    def __init__(self, yml: dict = None):
        self.actions = {}
        self.definitions = {}

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
                description = action["description"]
                command = action["command"]

                self.actions[action] = Action(description, command)

        # Load definitions
        if "defines" in data:
            defines = data["defines"]

            if not isinstance(defines, list):
                raise ValueError("Expected list of definitions in macro config")

            for key, value in defines:
                if not isinstance(value, str):
                    raise ValueError("Expected a string value for definition")

                self.definitions[key] = value

    def add_definition(self, key: str, value: str) -> None:
        self.definitions[key] = value

    def match_action(self, pattern: str) -> Action | None:
        return self.actions[pattern]

    def match_definition(self, pattern: str) -> str | None:
        return self.definitions[pattern]
