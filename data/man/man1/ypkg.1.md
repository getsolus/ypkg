---
title: YPKG
section: 1
header: User Manual
footer: ypkg 35.1.1
date: December 8, 2025
---

# NAME

ypkg(1) -- Build Solus ypkg files


# SYNOPSIS

`ypkg [OPTIONS] command [ARGS]...`


# DESCRIPTION

`ypkg` is a tool to generate an `eopkg` package file from a `package.yml(5)` file.

Note that you should not use `ypkg(1)` directly unless completely unavoidable.
Instead, you should be using `solbuild(1)` for isolated build environments.

# OPTIONS

The following options are applicable to `ypkg(1)`.

 * `-h`, `--help`

   Print the command line options for `ypkg(1)` and exit.


# SUBCOMMANDS

All available subcommands are listed below by their primary name.

`build <package.yml>`

    Given a `package.yml(5)` file, it will attempt to build the
    package according to the rules, patterns and steps set in the
    file.

    For details on the package format itself, please refer to the
    `package.yml(5)` manpage, or the Solus wiki.

    * `-D`, `--output-dir`:

        Set the output directory for resulting files.

    * `-B`, `--build-dir`:

        Set the base directory for performing the build.

    * `-t`, `--timestamp`:

        This argument should be a UNIX timestamp, and will be used to set the file
        timestamps inside the final `.eopkg` archive, as well as the container files
        within that archive.

        Using this option helps achieve reproducible builds, and this option is passed
        by `solbuild(1)` automatically for ypkg builds. It will examine the git history
        and use the UTC UNIX timestamp for the last tag, ensuring the package can be
        built by any machine using `solbuild(1)` and result in an identical package,
        byte for byte.

    * `-n`, `--no-colors`:

        Disable text colorization in the output from `ypkg(1)` and all child processes.

    * `--help`:

        Show help text about this command.

`gen-history <filename>`

    Generates a history.xml file.

    * `-D`, `--output-dir`:

        Set the output directory for resulting files.

    * `--help`:

        Show help text about this command.

`install-deps <package.yml>`

    This command will install all of the build dependencies listed in the
    given `package.yml(5)` file. Note that resolution of `pkgconfig` and `pkgconfig32`
    dependencies is handled automatically.

    * `-D`, `--output-dir`:

        Set the output directory for resulting files.

    * `-e`, `--eopkg-cmd`:

        Specify which `eopkg(1)` command to use.

    * `-f`, `--force`:

        Force the installation of package dependencies, which will bypass any
        prompting by `ypkg(1)`. The default behaviour is to prompt before installing
        packages.

    * `-n`, `--no-colors`:

        Disable text colorization in the output from `ypkg(1)` and all child processes.

    * `--help`:

        Show help text about this command.

# EXIT STATUS

On success, 0 is returned. A non-zero return code signals a failure.


# COPYRIGHT

 * Copyright © 2016-2025 Solus Project

Released under the terms of the CC-BY-SA-3.0 license


# SEE ALSO

`solbuild(1)`, `ypkg-install-deps(1)`, `ypkg-build(1)`, `package.yml(5)`

 * https://github.com/getsolus/ypkg
 * https://getsol.us/articles/packaging

# NOTES

Creative Commons Attribution-ShareAlike 3.0 Unported

 * http://creativecommons.org/licenses/by-sa/3.0/
