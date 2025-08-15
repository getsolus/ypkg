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

import pytest

from ypkg2.macros import Action
from ypkg2.parser import Parser, Script, Token, TokenType, tokenize


def test_tokenize():
    # Given
    content = "\n\n%patch %pkgfiles%/0001-deps-analysis-elves-In-absence-of-soname.-make-one-u.patch%foo%"

    # When
    tokens = tokenize(content)

    # Then
    expected_tokens = [
        Token(TokenType.NEWLINE),
        Token(TokenType.NEWLINE),
        Token(TokenType.ACTION, "patch"),
        Token(TokenType.DEFINITION, "pkgfiles"),
        Token(
            TokenType.PLAIN,
            "/0001-deps-analysis-elves-In-absence-of-soname.-make-one-u.patch",
        ),
        Token(TokenType.DEFINITION, "foo"),
    ]

    assert len(tokens) == len(expected_tokens)

    for i, token in enumerate(tokens):
        expected = expected_tokens[i]

        assert token.token_type == expected.token_type
        assert token.content == expected.content


# def test_parse():
#     # Given
#     content = "\n\n%patch %pkgfiles%/0001-deps-analysis-elves-In-absence-of-soname.-make-one-u.patch"
#     parser = Parser(env=None)
#
#     parser.add_action("patch", Action("test", "patch -v %nested_flag%"))
#     for ident, definition in [
#         ("nested_flag", "--args=%nested_arg%,b,c"),
#         ("nested_arg", "a"),
#         ("pkgfiles", "%root%/pkg"),
#         ("root", "/mason"),
#     ]:
#         parser.add_definition(ident, definition)
#
#     # When
#     parsed = parser.parse(content)
#
#     # Then
#     # expected = Script(
#     #     [
#     #         "patch -v --args=a,b,c /mason/pkg/0001-deps-analysis-elves-In-absence-of-soname.-make-one-u.patch"
#     #     ],
#     #     None,
#     # )
#     expected = Script()
#     expected.commands = [
#         "patch -v --args=a,b,c /mason/pkg/0001-deps-analysis-elves-In-absence-of-soname.-make-one-u.patch"
#     ]
#
#     assert len(parsed.commands) == len(expected.commands)
