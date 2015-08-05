#!/bin/bash
#Backup data to the Brazelton Lab file server

# functions
write_log() {
    date=$(date +"%b %-d %k:%M:%S")
    host=$(hostname -s)
    echo "$date $host $script: $1" >> $log_file;
}

show_help() {
cat << EOF
Usage: ${0##*/} [-h] [-r HOST] [-l LOG] [-p PORT] [-e FILES] source destination
Brazelton Lab backup script

positional arguments:
  source          directory to be backed up
  destination     destination on remote machine

optional arguments:
  -h              display this help message and exit
  -r HOST         account on remote host
  -l LOG          log file
  -p PORT         ssh port
  -e FILES        exclude files matching pattern
EOF
}

# variables
ssh=$(which ssh);
basename=$(which basename);
script=$($basename $0)
remote_host='root@baas-becking.biology.utah.edu';
port=53213;
log_file='/var/log/rsync';
exclude='lost+found';

# parse command line arguments
OPTIND=1;
while getopts "h?r:p:l:e:" opt; do
    case "$opt" in
        h)
            show_help;
            exit 0
            ;;
        r)  remote_host=$OPTARG
            ;;
        p)  port=$OPTARG
            ;;
        l)  log_file=$OPTARG
            ;;
        e)  exclude=$OPTARG
            ;;
        ?)
            show_help;
            echo "Unknown option";
            exit 0
    esac
done

if [ $(( $# - $OPTIND )) -lt 1 ]; then
    show_help;
    exit 1;
fi

source_dir="${@:$OPTIND:1}";
dest_dir="${@:$OPTIND+1:1}";

# verify that user input is valid
if [ ! -e "$source_dir" ]; then
    write_log "source $source_dir is not a valid file or directory";
    exit 1;
else
    write_log "starting backup of $source_dir";
fi

# obtain destination link
link=$($ssh -q -p $port $remote_host find $dest_dir -maxdepth 1 -type d | sort -n | tail -1);
if [ -z "$link" ]; then
    write_log "backup failed: unable to obtain a destination link";
    exit 1;
else
    write_log "found destination link: $link";
fi

destination="$dest_dir/$(date -I)";

# verify that destination does not already exist on the remote server
if [ $destination == $link ]; then
    write_log "destination directory $destination already exists on remote machine";
    exit 1;
fi

# backup data
write_log "using rsync to backup data";
sync_err=$(/usr/bin/rsync -e "ssh -q -p $port" -azAO --no-o --no-g --log-file=$log_file --exclude=$exclude --delete --link-dest=$link $source_dir $remote_host:$destination 2>&1 >/dev/null);
if [ -n "$sync_err" ]; then
    write_log "backup failed: $1";
    rmdir_err=$($ssh -q -p $port $remote_host rm -Rf $destination 2>&1 > /dev/null);
    if [ -n "$rmdir_err" ]; then
        write_log "unable to remove $destination: $rmdir_err";
    else
        write_log "destination directory $destination successfully removed";
    fi
    exit 1;
fi

write_log "backup successful";

exit 0;
