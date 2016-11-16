#! /bin/bash
# Takes a tab-separated conversion table with the destination directory in 
# the first column, the new file name in the second, the source directory 
# in the third, and the original file name in the fourth and links the
# files to the new directory, replacing the old names with the new.

show_help() {
cat << EOF
Usage: ${0##*/} [-h] [-f FORWARD] [-r REVERSE] [-e EXT] conversion_table
Brazelton Lab file name conversion script

positional arguments:
  infile         input conversion table

optional arguments:
  -h             display this help message and exit
  -f FORWARD     files are paired and the forward file is differentiated
                 from the reverse with FORWARD
  -r REVERSE     files are paired and the reverse file is differentiated
                 from the forward with REVERSE
  -e EXT         file extension for the destination file [default: fastq.gz]
EOF
}

link_files() {
    if [ -f $1 ]; then
        if [ ! -f $2 ]; then
            ln -s $1 $2;
        else
            >&2 echo "$2 already exists ... skipping";
        fi
    else
        >&2 echo "unable to locate $1 ... skipping";
    fi
}

FORWARD='';
REVERSE='';
EXT='fastq.gz';
# parse command line arguments
OPTIND=1;
while getopts "h?f:r:e:" opt; do
    case "$opt" in
        h)
            show_help;
            exit 0
            ;;
        f)  FORWARD=$OPTARG
            ;;
        r)  REVERSE=$OPTARG
            ;;
        e)  EXT=$OPTARG
            ;;
        ?)
            show_help;
            exit 0
            ;;
    esac
done
infile="${@:$OPTIND:1}";

while read -r line || [[ -n "$line" ]]; do
    IFS=$' \t' read newpath newid oldpath oldid <<< $line;
    if [[ ! -z $FORWARD && ! -z $REVERSE ]]; then
        from_f=$oldpath"/"$oldid$FORWARD;
        to_f=$newpath"/"$newid'.forward.'$EXT;
        link_files $from_f $to_f;

        from_r=$oldpath"/"$oldid$REVERSE;
        to_r=$newpath"/"$newid'.reverse.'$EXT;
        link_files $from_r $to_r;
    elif [[ ( -z "$FORWARD"  && ! -z "$REVERSE" ) || ( -z "$REVERSE" && ! -z "$FORWARD" ) ]]; then
        >&2 echo "arguments -f and -r must be used together";
        exit 1
    else
        if [ -w $newpath ]; then
            from="$oldpath/$oldid";
            to=$newpath"/"$newid"."$EXT;
            link_files $from $to;
        else
            >&2 echo "unable to write to $path";
        fi
    fi
done < $infile

exit 0
