#!/usr/bin/env bash

_manpages=(
    "data/man/man1/ypkg.1"
    "data/man/man5/package.yml.5"
)

pandoc="/usr/bin/pandoc"

if ! command -v "${pandoc}" > /dev/null 2>&1; then
    echo "Pandoc is not installed!"
    echo "Install it on Solus with 'eopkg install pandoc'"
    exit 1
fi

for manpage in "${_manpages[@]}"; do
    "${pandoc}" "${manpage}.md" -s -t html -o "${manpage}.html"
    "${pandoc}" "${manpage}.md" -s -t man -o "${manpage}"
done
