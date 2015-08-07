#!/bin/bash
#Backup data to the Brazelton Lab file server

# functions
write_log() {
    TIMESTAMP=$(date +"%b %-d %k:%M:%S");
    LHOST=$(hostname -s);
    SCRIPT=$(basename $0);
    echo "$TIMESTAMP $LHOST $SCRIPT: $1" >> $LOG;
}

show_help() {
cat << EOF
Usage: ${0##*/} [-h] [-r HOST] [-l LOG] [-p PORT] [-e FILES] [-v LV] [-g VG] source destination
Brazelton Lab backup script

positional arguments:
  source          directory to be backed up
  destination     destination on remote machine

optional arguments:
  -h              display this help message and exit
  -r HOST         account on remote host
  -l LOG          log file
  -p PORT         ssh port
  -e FILE         text file of excludes
  -v LV           lvm logical volume
  -g VG           lvm volume group
EOF
}

remove_snapshot() { 
    if ! lvremove -f $1 >/dev/null 2>&1; then
        write_log "cannot remove the lvm snapshot";
    fi
}

PATH="${PATH}:/usr/sbin:/sbin:/usr/bin:/bin";

# variables
RHOST='root@baas-becking.biology.utah.edu';
PORT=53213;
LOG='/var/log/rsync';
EXCLUDE='/usr/local/etc/excludes.txt';
LOGVOL='';
VOLGROUP='vg_winogradsky';
SNAPSIZE='40GiB';
SNAPNAME='lv_snap';

# parse command line arguments
OPTIND=1;
while getopts "h?r:p:l:e:v:g:" opt; do
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
            exit 0
            ;;
    esac
done
if [ $(( $# - $OPTIND )) -lt 1 ]; then
    show_help;
    exit 1;
fi
source_dir="${@:$OPTIND:1}";
dest_dir="${@:$OPTIND+1:1}";

# verify that source is a valid object
if [ ! -e "$source_dir" ]; then
    write_log "source $source_dir is not a valid file or directory";
    exit 1;
else
    write_log "starting backup of $source_dir";
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

if [ ! -z "${LOGVOL}" ]; then
    snapshot="/dev/${VOLGROUP}/${SNAPNAME}";
    # check that the snapshot does not already exist
    if [ -e "$snapshot" ]; then
        write_log "backup failed: snapshot $SNAPNAME already exists";
        exit 1;
    else
        write_log "creating snapshot $snapshot and mounting it at $source_dir";
    fi
    # create the snapshot
    if ! lvcreate --size ${SNAPSIZE} --snapshot --name ${SNAPNAME} /dev/${VOLGROUP}/${LOGVOL} >/dev/null 2>&1; then
        write_log "backup failed: unable to create snapshot of /dev/${VOLGROUP}/${LOGVOL}";
        exit 1;
    fi
    # mount snapshot at source
    if ! mount $snapshot $source_dir >/dev/null 2>&1; then
        write_log "backup failed: unable to mount $snapshot at $source_dir";
        remove_snapshot $snapshot;
        exit 1;
    fi
fi

# backup data
sync_err=$(rsync -e "ssh -q -p $PORT" -azAO --no-o --no-g --log-file=$LOG --exclude-from=$EXCLUDE --delete --link-dest=$link $source_dir $RHOST:$destination 2>&1 >/dev/null);

write_log "backup finished";
if [ ! -z $snapshot ]; then
    umount -f $source_dir;
    remove_snapshot $snapshot;
fi

exit 0
