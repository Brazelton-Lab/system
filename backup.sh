#!/bin/bash
#Backup data to the Brazelton Lab file server

# functions
write_log() {
    TIMESTAMP=$(date +"%b %-d %k:%M:%S")
    LHOST=$(hostname -s)
    SCRIPT=$(basename $0);
    echo "$TIMESTAMP $LHOST $SCRIPT: $1";
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

remove_snapshot() {  
    if ! lvremove -f $1 >/dev/null 2>&1; then
        write_log "cannot remove the lvm snapshot"
    fi
    exit $2
}

PATH="${PATH}:/usr/sbin:/sbin:/usr/bin:/bin";

# only run as root
if [ "$(id -u)" != '0' ]; then
    echo "this script has to be run as root";
    exit 1
fi

# variables
RHOST='root@baas-becking.biology.utah.edu';
PORT=53213;
LOG='/var/log/rsync';
EXCLUDE='lost+found';
LOGVOL='';
VOLGROUP='vg_winogradsky';
SNAPSIZE='40GiB';
SNAPNAME='lv_snap';

# parse command line arguments
OPTIND=1;
while getopts "h?r:p:l:e:" opt; do
    case "$opt" in
        h)
            show_help;
            exit 0
            ;;
        r)  RHOST=$OPTARG
            ;;
        p)  PORT=$OPTARG
            ;;
        l)  LOG=$OPTARG
            ;;
        e)  EXCLUDE=$OPTARG
            ;;
        v)  LOGVOL=$OPTARG
            ;;
        g)  VOLGROUP=$OPTARG
            ;;
        ?)
            show_help;
            echo "Unknown option";
            exit 0
    esac
done

if [ $(( $# - $OPTIND )) -lt 1 ]; then
    show_help;
    exit 1
fi

source_dir="${@:$OPTIND:1}";
dest_dir="${@:$OPTIND+1:1}";

# verify that source is a valid object
if [ ! -e "$source_dir" ]; then
    write_log "source $source_dir is not a valid file or directory";
    exit 1
else
    write_log "starting backup of $source_dir"
fi

# obtain destination link
link=$(/usr/bin/ssh -q -p $PORT $RHOST find $dest_dir -maxdepth 1 -type d | sort -n | tail -1 2>/dev/null);
if [ -z "$link" ]; then
    write_log "backup failed: unable to obtain a destination link";
    exit 1;
else
    write_log "found destination link: $link";
fi

destination="$dest_dir/$(date -I)";

# verify that destination does not already exist on the remote server
if [ $destination == $link ]; then
    write_log "backup failed: destination directory $destination already exists on remote machine";
    exit 1;
fi

if [ ! -z "$LOGVOL"]; then
    snapshot="/dev/${VOLGROUP}/${SNAPNAME}";
    # check that the snapshot does not already exist
    if [ -e "$snapshot" ]; then
        write_log "backup failed: snapshot $SNAPNAME already exists";
        exit 1;
    else
        write_log "creating snapshot $snapshot and mounting it at $source_dir";
    fi
    # create the snapshot
    if ! lvcreate --size ${SNAPSIZE} --snapshot --name ${SNAPNAME} $snapshot >/dev/null 2>&1; then
        write_log "backup failed: unable to create snapshot of /dev/${VOLGROUP}/${LOGVOL}";
        exit 1;
    fi
    # mount snapshot at source
    if ! mount -ro $snapshot $source_dir >/dev/null 2>&1; then
        write_log "backup failed: unable to mount $snapshot at $source_dir";
        remove_snapshot $snapshot 1;
    fi
fi

# backup data
sync_err=$(rsync -e "ssh -q -p $PORT" -azAO --no-o --no-g --log-file=$LOG --exclude=$EXCLUDE --delete --link-dest=$link $source_dir $RHOST:$destination 2>&1 >/dev/null);
if [ -n "$sync_err" ]; then
    write_log "backup failed: $1";
    rmdir_err=$(ssh -q -p $PORT $RHOST rm -Rf $destination 2>&1 > /dev/null);
    if [ -n "$rmdir_err" ]; then
        write_log "unable to remove $destination: $rmdir_err";
    else
        write_log "destination directory $destination successfully removed";
    fi
    if [ ! -z $snapshot ]; then
        remove_snapshot $snapshot 1;
    else
        exit 1;
fi

write_log "backup successful";
if [ ! -z $snapshot ]; then
    remove_snapshot $snapshot 0;
else
    exit 0;
