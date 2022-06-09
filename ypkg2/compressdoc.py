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

compressed_exts = [
    ".gz",
    ".bz2",
    ".zst"
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

    # Open the file
    in_file = open(path)

    # Create the file to write to
    out_path = "{}.gz".format(path)
    out_file = gzip.open(out_path, "wb", 9) # Maximum compression

    # Write the contents to the compressed file through gzip
    out_file.writelines(in_file)

    # Close the files
    out_file.close()
    in_file.close()

    # Remove the original file
    os.unlink(path)

def compress_all_in_dir(path):
    """Compress all files in a directory.
    
    This function iterates over all children in the
    given directory. If the file is a regular uncompressed
    file, it will be compressed with `gzip`.

    Files that are already compressed will be ignored.

    Symlinked files will have their links updated to point
    to the new (compressed) target path.
    """

    # Iterate over each file in the directory
    for file in os.listdir(path):
        file_path = os.path.join(path, file)

        if is_compressed(file_path):
            continue

        # Check if the file is a symlink
        if os.path.islink(file_path):
            # Get the link target
            link_target = os.readlink(file_path)
            if os.path.islink(link_target):
                # Skip if this is pointing to another link
                continue

            # Figure out what the compressed target path is
            new_link = "{}.gz".format(link_target)

            # Re-link to the new target
            os.unlink(file_path)
            os.symlink(new_link, file_path)
        elif os.path.isfile(file_path):
            # We have a file, compress it
            compress_gzip(file_path)

def compress_man_dirs(root):
    """Compresses manpage files recursively from the given root.
    
    This function iterates over all of the directories in the root,
    and compressing the contents of directories if they look like
    manpage directories (the directory name starts with `man`).

    If a directory is not a manpage directory, call this function
    again with the child directory as the new root.
    """

    for dir in os.listdir(root):
        child_path = os.path.join(root, dir)

        # Ignore non-directories
        if not os.path.isdir(child_path):
            continue

        # Recurse into localized manpage dirs
        if not dir.startswith("man"):
            compress_man_dirs(child_path)
            continue

        # This appears to be a manpage dir,
        # so compress everything in it
        compress_all_in_dir(child_path)
