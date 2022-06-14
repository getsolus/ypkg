#!/bin/true
# -*- coding: utf-8 -*-
#
#  This file is part of ypkg2
#
#  Copyright 2022 Solus Project
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#

import gzip
import os
import shutil

compressed_exts = [
    ".gz",
    ".bz2",
    ".lz",
    ".zst",
    ".xz"
]


def is_compressed(path):
    """Check if a file is compressed."""

    parts = os.path.splitext(path)
    file_ext = parts[1]

    if file_ext in compressed_exts:
        return True

    return False


def compress_gzip(path):
    """Compresses a single file with `gzip`.

    The original file will be deleted after compression.
    """

    starting_size = os.path.getsize(path)

    # Open the file
    in_file = open(path)

    # Create the file to write to
    out_path = "{}.gz".format(path)
    # Open the file
    with open(path) as in_file, gzip.GzipFile(filename=out_path, mode="wb", compresslevel=9, mtime=0) as out_file:
        shutil.copyfileobj(in_file, out_file)

    # Remove the original file
    os.unlink(path)

    # Calculate and return the bytes saved by compression
    ending_size = os.path.getsize(out_path)
    return starting_size - ending_size


def update_link(path):
    """Update a symlink to point to the compressed target.

    This reads the target path of a symlink, unlinks it, and creates
    a new link pointing to the target path with `.gz` appended to the end.
    """

    if not os.path.islink(path):
        return

    # Get the link target
    link_target = os.readlink(path)
    if os.path.islink(link_target):
        # Skip if this is pointing to another link
        return

    # Figure out what the compressed target path is
    new_link = "{}.gz".format(link_target)

    # Re-link to the new target
    os.unlink(path)
    os.symlink(new_link, path)


def compress_dir(path):
    """Compress all files in a directory.

    This function iterates over all children in the
    given directory. If the file is a regular uncompressed
    file, it will be compressed with `gzip`.

    Files that are already compressed will be ignored.

    Symlinked files will have their links updated to point
    to the new (compressed) target path.
    """

    num_compressed = 0
    bytes_saved = 0

    # Iterate over each file in the directory
    for file in os.listdir(path):
        file_path = os.path.join(path, file)

        if is_compressed(file_path):
            continue

        # Check if the file is a symlink
        if os.path.islink(file_path):
            update_link(file_path)
        elif os.path.isfile(file_path):
            # We have a file, compress it
            bytes_saved += compress_gzip(file_path)
            num_compressed += 1

    return (num_compressed, bytes_saved)


def compress_man_pages(root):
    """Compresses manpage files recursively from the given root.

    This function iterates over all of the directories in the root,
    and compressing the contents of directories if they look like
    manpage directories (the directory name starts with `man`).

    If a directory is not a manpage directory, call this function
    again with the child directory as the new root.
    """

    num_compressed = 0
    bytes_saved = 0

    for dir in os.listdir(root):
        child_path = os.path.join(root, dir)

        # Ignore non-directories
        if not os.path.isdir(child_path):
            continue

        # Recurse into localized manpage dirs
        if not dir.startswith("man"):
            (c, s) = compress_man_pages(child_path)
            num_compressed += c
            bytes_saved += s
            continue

        # This appears to be a manpage dir,
        # so compress everything in it
        (c, s) = compress_dir(child_path)
        num_compressed += c
        bytes_saved += s

    return (num_compressed, bytes_saved)


def compress_info_pages(root):
    """Compress info page files in a directory.

    This is essentially a modified version of `compress_manpages`
    that is specifically tailored to the structure of the system
    info page directory.
    """

    bytes_saved = 0
    num_compressed = 0

    for child in os.listdir(root):
        path = os.path.join(root, child)

        if os.path.isfile(path):
            # Compress if the path is an uncompressed file
            # First, check if it actually looks like an info file
            if ".info" not in os.path.basename(path):
                continue

            # Only try to compress the file if it isn't already compressed
            if is_compressed(path):
                continue

            bytes_saved += compress_gzip(path)
            num_compressed += 1
        elif os.path.islink(path):
            # If it's a symlink, update it
            update_link(path)
        elif os.path.isdir(path):
            # Recurse into nested directories looking for info pages
            (c, s) = compress_info_pages(path)
            num_compressed += c
            bytes_saved += s

    return (num_compressed, bytes_saved)
