#!/bin/bash
# VERSION: 20040320.0026
#
# Compress (with bzip2 or gzip) all man pages in a hierarchy and
# update symlinks - By Marc Heerdink <marc @ koelkast.net>
# Modified to be able to gzip or bzip2 files as an option and to deal
# with all symlinks properly by Mark Hymers <markh @ linuxfromscratch.org>
#
# Modified 20030930 by Yann E. Morin <yann.morin.1998 @ anciens.enib.fr>
# to accept compression/decompression, to correctly handle hard-links,
# to allow for changing hard-links into soft- ones, to specify the
# compression level, to parse the man.conf for all occurrences of MANPATH,
# to allow for a backup, to allow to keep the newest version of a page.
# Modified 20040330 by Tushar Teredesai to replace $0 by the name of the script.
#   (Note: It is assumed that the script is in the user's PATH)
#
# TODO:
#        - choose a default compress method to be based on the available
#          tool : gzip or bzip2;
#        - offer an option to automagically choose the best compression method
#          on a per page basis (eg. check which ofgzip/bzip2/whatever is the
#          most effective, page per page);
#        - when a MANPATH env var exists, use this instead of /etc/man.conf
#          (useful for users to (de)compress their man pages;
#        - offer an option to restore a previous backup;
#        - add other compression engines (compress, zip, etc?). Needed?

# Funny enough, this function prints some help.
function help ()
{
  if [ -n "$1" ]; then
    echo "Unknown option : $1"
  fi
  ( echo "Usage: $MY_NAME <comp_method> [options] [dirs]" && \
  cat << EOT
Where comp_method is one of :
  --gzip, --gz, -g
  --bzip2, --bz2, -b
                Compress using gzip or bzip2.

  --decompress, -d
                Decompress the man pages.

  --backup      Specify a .tar backup shall be done for every directories.
                In case a backup already exists, it is saved as .tar.old prior
                to making the new backup. If an .tar.old backup exist, it is
                removed prior to saving the backup.
                In backup mode, no other action is performed.

And where options are :
  -1 to -9, --fast, --best
                The compression level, as accepted by gzip and bzip2. When not
                specified, uses the default compression level for the given
                method (-6 for gzip, and -9 for bzip2). Not used when in backup
                or decompress modes.

  --force, -F   Force (re-)compression, even if the previous one was the same
                method. Useful when changing the compression ratio. By default,
                a page will not be re-compressed if it ends with the same suffix
                as the method adds (.bz2 for bzip2, .gz for gzip).

  --soft, -S    Change hard-links into soft-links. Use with _caution_ as the
                first encountered file will be used as a reference. Not used
                when in backup mode.

  --hard, -H    Change soft-links into hard-links. Not used when in backup mode.

  --conf=dir, --conf dir
                Specify the location of man.conf. Defaults to /etc.

  --verbose, -v Verbose mode, print the name of the directory being processed.
                Double the flag to turn it even more verbose, and to print the
                name of the file being processed.

  --fake, -f    Fakes it. Print the actual parameters compman will use.

  dirs          A list of space-separated _absolute_ pathname to the man
                directories.
                When empty, and only then, parse ${MAN_CONF}/man.conf for all
                occurrences of MANPATH.

Note about compression
  There has been a discussion on blfs-support about compression ratios of
  both gzip and bzip2 on man pages, taking into account the hosting fs,
  the architecture, etc... On the overall, the conclusion was that gzip
  was much efficient on 'small' files, and bzip2 on 'big' files, small and
  big being very dependent on the content of the files.

  See the original post from Mickael A. Peters, titled "Bootable Utility CD",
  and dated 20030409.1816(+0200), and subsequent posts:
  http://linuxfromscratch.org/pipermail/blfs-support/2003-April/038817.html

  On my system (x86, ext3), man pages were 35564kiB before compression. gzip -9
  compressed them down to 20372kiB (57.28%), bzip2 -9 got down to 19812kiB
  (55.71%). That is a 1.57% gain in space. YMMV.

  What was not taken into consideration was the decompression speed. But does
  it make sense to? You gain fast access with uncompressed man pages, or you
  gain space at the expense of a slight overhead in time. Well, my P4-2.5GHz
  does not even let me notice this... :-)
EOT
) | less
}

# This function checks that the man page is unique amongst bzip2'd, gzip'd and
# uncompressed versions.
#  $1 the directory in which the file resides
#  $2 the file name for the man page
# Returns 0 (true) if the file is the latest and must be taken care of, and 1
# (false) if the file is not the latest (and has therefore been deleted).
function check_unique ()
{
  # NB. When there are hard-links to this file, these are
  # _not_ deleted. In fact, if there are hard-links, they
  # all have the same date/time, thus making them ready
  # for deletion later on.

  # Build the list of all man pages with the same name
  DIR=$1
  BASENAME=`basename "${2}" .bz2`
  BASENAME=`basename "${BASENAME}" .gz`
  GZ_FILE="$BASENAME".gz
  BZ_FILE="$BASENAME".bz2

  # Look for, and keep, the most recent one
  LATEST=`(cd "$DIR"; ls -1rt "${BASENAME}" "${GZ_FILE}" "${BZ_FILE}" 2>/dev/null | tail -n 1)`
  for i in "${BASENAME}" "${GZ_FILE}" "${BZ_FILE}"; do
    [ "$LATEST" != "$i" ] && rm -f "$DIR"/"$i"
  done

  # In case the specified file was the latest, return 0
  [ "$LATEST" = "$2" ] && return 0
  # If the file was not the latest, return 1
  return 1
}

# Name of the script
MY_NAME=`basename $0`

# OK, parse the command-line for arguments, and initialize to some sensible
# state, that is : don't change links state, parse /etc/man.conf, be most
# silent, search man.conf in /etc, and don't force (re-)compression.
COMP_METHOD=
COMP_SUF=
COMP_LVL=
FORCE_OPT=
LN_OPT=
MAN_DIR=
VERBOSE_LVL=0
BACKUP=no
FAKE=no
MAN_CONF=/etc
while [ -n "$1" ]; do
  case $1 in
    --gzip|--gz|-g)
      COMP_SUF=.gz
      COMP_METHOD=$1
      shift
      ;;
    --bzip2|--bz2|-b)
      COMP_SUF=.bz2
      COMP_METHOD=$1
      shift
      ;;
    --decompress|-d)
      COMP_SUF=
      COMP_LVL=
      COMP_METHOD=$1
      shift
      ;;
    -[1-9]|--fast|--best)
      COMP_LVL=$1
      shift
      ;;
    --force|-F)
      FORCE_OPT=-F
      shift
      ;;
    --soft|-S)
      LN_OPT=-S
      shift
      ;;
    --hard|-H)
      LN_OPT=-H
      shift
      ;;
    --conf=*)
      MAN_CONF=`echo $1 | cut -d '=' -f2-`
      shift
      ;;
    --conf)
      MAN_CONF="$2"
      shift 2
      ;;
    --verbose|-v)
      let VERBOSE_LVL++
      shift
      ;;
    --backup)
      BACKUP=yes
      shift
      ;;
    --fake|-f)
      FAKE=yes
      shift
      ;;
    --help|-h)
      help
      exit 0
      ;;
    /*)
      MAN_DIR="${MAN_DIR} ${1}"
      shift
      ;;
    -*)
      help $1
      exit 1
      ;;
    *)
      echo "\"$1\" is not an absolute path name"
      exit 1
      ;;
  esac
done

# Redirections
case $VERBOSE_LVL in
  0)
     # O, be silent
     DEST_FD0=/dev/null
     DEST_FD1=/dev/null
     VERBOSE_OPT=
     ;;
  1)
     # 1, be a bit verbose
     DEST_FD0=/dev/stdout
     DEST_FD1=/dev/null
     VERBOSE_OPT=-v
     ;;
  *)
     # 2 and above, be most verbose
     DEST_FD0=/dev/stdout
     DEST_FD1=/dev/stdout
     VERBOSE_OPT="-v -v"
     ;;
esac

# Note: on my machine, 'man --path' gives /usr/share/man twice, once with a trailing '/', once without.
if [ -z "$MAN_DIR" ]; then
  MAN_DIR=`man --path -C "$MAN_CONF"/man.conf \
            | sed 's/:/\\n/g' \
            | while read foo; do dirname "$foo"/.; done \
            | sort -u \
            | while read bar; do echo -n "$bar "; done`
fi

# If no MANPATH in ${MAN_CONF}/man.conf, abort as well
if [ -z "$MAN_DIR" ]; then
  echo "No directory specified, and no directory found with \`man --path'"
  exit 1
fi

# Fake?
if [ "$FAKE" != "no" ]; then
  echo "Actual parameters used:"
  echo -n "Compression.......: "
  case $COMP_METHOD in
    --bzip2|--bz2|-b) echo -n "bzip2";;
    --gzip|__gz|-g) echo -n "gzip";;
    --decompress|-d) echo -n "decompressing";;
    *) echo -n "unknown";;
  esac
  echo " ($COMP_METHOD)"
  echo "Compression level.: $COMP_LVL"
  echo "Compression suffix: $COMP_SUF"
  echo -n "Force compression.: "
  [ "foo$FORCE_OPT" = "foo-F" ] && echo "yes" || echo "no"
  echo "man.conf is.......: ${MAN_CONF}/man.conf"
  echo -n "Hard-links........: "
  [ "foo$LN_OPT" = "foo-S" ] && echo "convert to soft-links" || echo "leave as is"
  echo -n "Soft-links........: "
  [ "foo$LN_OPT" = "foo-H" ] && echo "convert to hard-links" || echo "leave as is"
  echo "Backup............: $BACKUP"
  echo "Faking (yes!).....: $FAKE"
  echo "Directories.......: $MAN_DIR"
  echo "Verbosity level...: $VERBOSE_LVL"
  exit 0
fi

# If no method was specified, print help
if [ -z "${COMP_METHOD}" -a "${BACKUP}" = "no" ]; then
  help
  exit 1
fi

# In backup mode, do the backup solely
if [ "$BACKUP" = "yes" ]; then
  for DIR in $MAN_DIR; do
    cd "${DIR}/.."
    DIR_NAME=`basename "${DIR}"`
    echo "Backing up $DIR..." > $DEST_FD0
    [ -f "${DIR_NAME}.tar.old" ] && rm -f "${DIR_NAME}.tar.old"
    [ -f "${DIR_NAME}.tar" ] && mv "${DIR_NAME}.tar" "${DIR_NAME}.tar.old"
    tar cfv "${DIR_NAME}.tar" "${DIR_NAME}" > $DEST_FD1
  done
  exit 0
fi

# I know MAN_DIR has only absolute path names
# I need to take into account the localized man, so I'm going recursive
for DIR in $MAN_DIR; do
  MEM_DIR=`pwd`
  cd "$DIR"
  for FILE in *; do
    # Fixes the case were the directory is empty
    if [ "foo$FILE" = "foo*" ]; then continue; fi

    # Fixes the case when hard-links see their compression scheme change
    # (from not compressed to compressed, or from bz2 to gz, or from gz to bz2)
    # Also fixes the case when multiple version of the page are present, which
    # are either compressed or not.
    if [ ! -L "$FILE" -a ! -e "$FILE" ]; then continue; fi

    # Do not compress whatis files
    if [ "$FILE" = "whatis" ]; then continue; fi

    if [ -d "$FILE" ]; then
      cd "${MEM_DIR}"  # Go back to where we ran "$0", in case "$0"=="./compressdoc" ...
      # We are going recursive to that directory
      echo "-> Entering ${DIR}/${FILE}..." > $DEST_FD0
      # I need not pass --conf, as I specify the directory to work on
      # But I need exit in case of error
      "$MY_NAME" ${COMP_METHOD} ${COMP_LVL} ${LN_OPT} ${VERBOSE_OPT} ${FORCE_OPT} "${DIR}/${FILE}" || exit 1
      echo "<- Leaving ${DIR}/${FILE}." > $DEST_FD1
      cd "$DIR"  # Needed for the next iteration of the loop

    else # !dir
      if ! check_unique "$DIR" "$FILE"; then continue; fi

      # Check if the file is already compressed with the specified method
      BASE_FILE=`basename "$FILE" .gz`
      BASE_FILE=`basename "$BASE_FILE" .bz2`
      if [ "${FILE}" = "${BASE_FILE}${COMP_SUF}" -a "foo${FORCE_OPT}" = "foo" ]; then continue; fi

      # If we have a symlink
      if [ -h "$FILE" ]; then
        case "$FILE" in
          *.bz2)
            EXT=bz2 ;;
          *.gz)
            EXT=gz ;;
          *)
            EXT=none ;;
        esac

        if [ ! "$EXT" = "none" ]; then
          LINK=`ls -l "$FILE" | cut -d ">" -f2 | tr -d " " | sed s/\.$EXT$//`
          NEWNAME=`echo "$FILE" | sed s/\.$EXT$//`
          mv "$FILE" "$NEWNAME"
          FILE="$NEWNAME"
        else
          LINK=`ls -l "$FILE" | cut -d ">" -f2 | tr -d " "`
        fi

        if [ "$LN_OPT" = "-H" ]; then
          # Change this soft-link into a hard- one
          rm -f "$FILE" && ln "${LINK}$COMP_SUF" "${FILE}$COMP_SUF"
          chmod --reference "${LINK}$COMP_SUF" "${FILE}$COMP_SUF"
        else
          # Keep this soft-link a soft- one.
          rm -f "$FILE" && ln -s "${LINK}$COMP_SUF" "${FILE}$COMP_SUF"
        fi
        echo "Relinked $FILE" > $DEST_FD1

      # else if we have a plain file
      elif [ -f "$FILE" ]; then
        # Take care of hard-links: build the list of files hard-linked
        # to the one we are {de,}compressing.
        # NB. This is not optimum has the file will eventually be compressed
        # as many times it has hard-links. But for now, that's the safe way.
        inode=`ls -li "$FILE" | awk '{print $1}'`
        HLINKS=`find . \! -name "$FILE" -inum $inode`

        if [ -n "$HLINKS" ]; then
          # We have hard-links! Remove them now.
          for i in $HLINKS; do rm -f "$i"; done
        fi

        # Now take care of the file that has no hard-link
        # We do decompress first to re-compress with the selected
        # compression ratio later on...
        case "$FILE" in
          *.bz2)
            bunzip2 $FILE
            FILE=`basename "$FILE" .bz2`
          ;;
          *.gz)
            gunzip $FILE
            FILE=`basename "$FILE" .gz`
          ;;
        esac

        # Compress the file with the given compression ratio, if needed
        case $COMP_SUF in
          *bz2)
            bzip2 ${COMP_LVL} "$FILE" && chmod 644 "${FILE}${COMP_SUF}"
            echo "Compressed $FILE" > $DEST_FD1
            ;;
          *gz)
            gzip ${COMP_LVL} "$FILE" && chmod 644 "${FILE}${COMP_SUF}"
            echo "Compressed $FILE" > $DEST_FD1
            ;;
          *)
            echo "Uncompressed $FILE" > $DEST_FD1
            ;;
        esac

        # If the file had hard-links, recreate those (either hard or soft)
        if [ -n "$HLINKS" ]; then
          for i in $HLINKS; do
            NEWFILE=`echo "$i" | sed s/\.gz$// | sed s/\.bz2$//`
            if [ "$LN_OPT" = "-S" ]; then
              # Make this hard-link a soft- one
              ln -s "${FILE}$COMP_SUF" "${NEWFILE}$COMP_SUF"
            else
              # Keep the hard-link a hard- one
              ln "${FILE}$COMP_SUF" "${NEWFILE}$COMP_SUF"
            fi
            chmod 644 "${NEWFILE}$COMP_SUF" # Really work only for hard-links. Harmless for soft-links
          done
        fi

      else
        # There is a problem when we get neither a symlink nor a plain file
        # Obviously, we shall never ever come here... :-(
        echo "Whaooo... \"${DIR}/${FILE}\" is neither a symlink nor a plain file. Please check:"
        ls -l "${DIR}/${FILE}"
        exit 1
      fi
    fi
  done # for FILE
done # for DIR
