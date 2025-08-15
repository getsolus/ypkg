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

from .macros import Action, Macros

from enum import Enum


class Script:
    commands: list[str] = None
    env: str | None = None
    resolved_actions: dict[str, str] = None
    resolved_definitions: dict[str, str] = None

    def __init__(self):
        self.commands = []
        self.resolved_actions = {}
        self.resolved_definitions = {}


class TokenType(Enum):
    ACTION = 1
    DEFINITION = 2
    PLAIN = 3
    NEWLINE = 4

    content: str = None

    def __init__(self, content: str):
        self.content = content


class Token:
    token_type: TokenType = None
    content: str | None = None

    def __init__(self, token_type: TokenType, content: str | None = None):
        self.token_type = token_type
        self.content = content


class Parsed:
    commands: list[str] = None
    env: str | None = None

    def __init__(self, commands: list[str], env: str | None):
        self.commands = commands
        self.env = env


def tokenize(content: str) -> list[Token]:
    """Turn script content into a bunch of tokens.

    Parameters:
        content -- The script content to tokenize.

    Returns:
        A list of Tokens.
    """
    tokens: list[Token] = []
    identifier_start = -1
    plain_start = -1

    # Iterate over each character, looking for our identifier
    # symbols ('%') and newlines.
    for i, char in enumerate(content):
        match char:
            case "%":
                if plain_start is not -1:
                    plain_text = content[plain_start:i]
                    plain_start = -1
                    token = Token(TokenType.PLAIN, plain_text)
                    tokens.append(token)

                if identifier_start is not -1:
                    # We already have a start, so this must be the end
                    identifier = content[identifier_start + 1 : i]
                    identifier_start = -1
                    token = Token(TokenType.DEFINITION, identifier)
                    tokens.append(token)
                else:
                    # Store the start of the identifier
                    identifier_start = i
            case "\n":
                # Check if we've encountered the start of an identifier
                # If yes, then extract it before appending a newline.
                # Same thing if a block of plain text has started.
                if identifier_start is not -1:
                    identifier = content[identifier_start + 1 : i]
                    identifier_start = -1
                    token = Token(TokenType.ACTION, identifier)
                    tokens.append(token)
                elif plain_start is not -1:
                    plain_text = content[plain_start:i]
                    plain_start = -1
                    token = Token(TokenType.PLAIN, plain_text)
                    tokens.append(token)

                tokens.append(Token(TokenType.NEWLINE))
            case " ":
                # Identifiers cannot have spaces in them
                if identifier_start is not -1:
                    identifier = content[identifier_start + 1 : i]
                    identifier_start = -1
                    token = Token(TokenType.ACTION, identifier)
                    tokens.append(token)
            case _:
                if identifier_start is -1:
                    if plain_start is -1:
                        plain_start = i

    # Check if we have an identifier or plain text started, but
    # not closed by the end of the content block. In this case,
    # we need to extract the remaining text as either an action
    # or plain text.
    if identifier_start is not -1:
        token = Token(TokenType.ACTION, content[identifier_start + 1 :])
        tokens.append(token)
    elif plain_start is not -1:
        token = Token(TokenType.PLAIN, content[plain_start:])
        tokens.append(token)

    return tokens


def parse(
    content: str,
    env: str | None,
    actions: dict[str, Action],
    definitions: dict[str, str],
) -> Parsed:
    """Parse script content, forming a fully escaped string to execute.

    This function calls itself recursively, since macros can contain nested
    macros.

    Parameters:
        content -- The content to parse.
        env -- Any environment variables that should be prepended to the script.
        actions -- A set of loaded macro actions.
        definitions -- A set of loaded macro definitions.

    Returns:
        A built string ready for execution.
    """

    def parse_content_only(
        content: str, actions: dict[str, Action], definitions: dict[str, str]
    ) -> str | None:
        ret: str = ""
        parsed = parse(content, None, actions, definitions)
        for command in parsed.commands:
            ret += command
        return ret

    commands: list[str] = []
    prepended = f"{env}\n{content}"
    tokens = tokenize(content)

    # Iterate over all of our tokens to build our final script string
    for token in tokens:
        c = ""

        match token.token_type:
            case TokenType.ACTION:
                action = actions[token.content]
                nested = parse_content_only(action.command, actions, definitions)

                if nested is not None:
                    c += nested
            case TokenType.DEFINITION:
                definition = definitions[token.content]
                nested = parse_content_only(definition, actions, definitions)

                if nested is not None:
                    c += nested
            case TokenType.PLAIN:
                c += token.content
            case TokenType.NEWLINE:
                c += "\n"

        commands.append(c)

    parsed = Parsed(commands, env)
    return parsed


class Parser:
    actions: dict[str, Action] = None
    definitions: dict[str, str] = None
    env: str | None = None

    def __init__(self, env: str | None):
        self.actions = {}
        self.definitions = {}
        self.env = env

    def add_action(self, identifier: str, action: Action) -> None:
        self.actions[identifier] = action

    def add_definition(self, identifier: str, definition: str) -> None:
        self.definitions[identifier] = definition

    def add_macros(self, macros: Macros) -> None:
        for key, value in macros.actions:
            self.add_action(key, value)

        for key, value in macros.definitions:
            self.add_definition(key, value)

    def parse(self, content: str) -> Script | None:
        parsed = parse(content, self.env, self.actions, self.definitions)
