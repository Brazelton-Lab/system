#!/bin/bash
#Backup data to the Brazelton Lab file server

# functions
write_log() {
    TIMESTAMP=$(date +"%b %-d %k:%M:%S");
    LHOST=$(hostname -s);
    SCRIPT=$(basename $0);
    if [ ! -z $LOG ]; then
        echo "$TIMESTAMP $LHOST $SCRIPT: $1" >> $LOG;
    else
        echo "$TIMESTAMP $LHOST $SCRIPT: $1"
    fi
}

show_help() {
cat << EOF
Usage: ${0##*/} [-h] [-d] [-r HOST] [-l LOG] [-p PORT] [-e FILES] [-v LV] \
    [-g VG] [-s SIZE] source destination
Brazelton Lab backup script

positional arguments:
  source          directory to be backed up
  destination     destination directory on remote machine

optional arguments:
  -h              display this help message and exit
  -d              do not require a destination link [default: link required]
  -r HOST         account on remote host (user@remote_address)
  -l LOG          log file
  -p PORT         ssh port on remote machine [default: 22]
  -e FILE         text file of excludes
  -v LV           lvm logical volume
  -g VG           lvm volume group
  -s SIZE         snapshot size [default: 200GiB]
EOF
}

remove_snapshot() { 
    write_log "cleaning up snapshot $1";
    if ! lvremove -f $1 >/dev/null 2>&1; then
        write_log "error: cannot remove the lvm snapshot";
        exit 1
    else
        write_log "snapshot successfully removed";
    fi
}

PATH="${PATH}:/usr/sbin:/sbin:/usr/bin:/bin";

# variables
RHOST='';
PORT=22;
LOG='';
EXCLUDES='';
LOGVOL='';
VOLGROUP='';
REQUIRE_LINK=true;
SNAPSIZE='200GiB';

# parse command line arguments
OPTIND=1;
while getopts "h?d:r:p:l:e:v:g:s:" opt; do
    case "$opt" in
        h)
            show_help;
            exit 0
            ;;
        d)  REQUIRE_LINK=false
            ;;
        r)  RHOST=$OPTARG
            ;;
        p)  PORT=$OPTARG
            ;;
        l)  LOG=$OPTARG
            ;;
        e)  EXCLUDES=$OPTARG
            ;;
        v)  LOGVOL=$OPTARG
            ;;
        g)  VOLGROUP=$OPTARG
            ;;
        s)  SNAPSIZE=$OPTARG
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

start_time=$(date +"%Y%m%dH%M.%S")

# verify that the log file exists and is writable
if [ ! -z "$LOG" ]; then
    if [ ! -e "$LOG" ]; then
        if ! touch $LOG; then
            echo "error: unable to create $LOG";
            exit 1
        fi
    else
        if [ ! -w "$LOG" ]; then
            echo "error: unable to write to log file $LOG";
            exit 1
        fi
    fi
fi

write_log "starting backup of $source_dir";

# verify that dependant arguments are used together
if [[ ( -z "$VOLGROUP"  && ! -z "$LOGVOL" ) || ( -z "$LOGVOL" && ! -z "$VOLGROUP" ) ]]; then
    write_log "error: arguments -g and -v must be used together";
    exit 1
fi

# set the destination
destination="$dest_dir/$(date -I)";

# obtain destination link
link=$(/usr/bin/ssh -q -p $PORT $RHOST find $dest_dir -maxdepth 1 -type d | sort -n | tail -1 2>/dev/null);
if [ -z "$link" ]; then
    if [ "$REQUIRE_LINK" == true ]; then
        write_log "error: unable to obtain a destination link";
        exit 1
    else
        write_log "warning: destination link not found but require destination link is set to false. Will perform a full backup";
        link_dest='';
    fi
else
    write_log "using destination link ${link} for incremental backup";
    link_dest="--link-dest=${link}";
fi

# verify that destination is not also the link (in case backup occurs twice in one day)
if [ $destination == $link ]; then
    write_log "error: destination directory $destination already exists on the remote machine";
    exit 1
fi

# if requested, create the snapshot and mount it at the source directory
if [ ! -z "${LOGVOL}" ]; then
    snapname="${LOGVOL}_snap";
    snapshot="/dev/${VOLGROUP}/${snapname}";
    # check that the snapshot does not already exist
    if [ -e "$snapshot" ]; then
        write_log "error: snapshot $snapname already exists";
        exit 1
    else
        write_log "creating snapshot $snapshot and mounting it at $source_dir"
    fi
    # create the snapshot
    if ! lvcreate --size ${SNAPSIZE} --snapshot --name ${snapname} /dev/${VOLGROUP}/${LOGVOL} >/dev/null 2>&1; then
        write_log "error: unable to create a snapshot of ${LOGVOL}";
        exit 1
    fi
    # mount snapshot at source
    if [ -d "$source_dir" ]; then # check existence
         if [ "$(ls -A $source_dir)" ]; then # fail if not empty
             write_log "error: source directory ${source_dir} already exists and is non-empty";
             remove_snapshot ${snapshot};
             exit 1
         fi
    else
        if ! mkdir ${source_dir}; then 
            write_log "error: unable to create the source directory $source";
            remove_snapshot ${snapshot};
            exit 1
        fi
    fi
    if ! mount ${snapshot} ${source_dir} >/dev/null 2>&1; then
        write_log "error: unable to mount $snapshot at $source_dir";
        remove_snapshot ${snapshot};
        exit 1
    fi
else
    # otherwise verify that source is a valid file or directory
    if [ ! -e "$source_dir" ]; then
        write_log "error: source $source_dir is not a valid file or directory";
        exit 1
    fi
fi

# set rsync arguments
RSYNCOPTS=(-azAX --no-o --no-g --delete ${link_dest});
if [ ! -z $EXCLUDES ]; then
    RSYNCOPTS+=(--exclude-from=${EXCLUDES});
fi

if [ ! -z $LOG ]; then
    RSYNCOPTS+=(--log-file=${LOG});
fi

if [ ! -z $RHOST ]; then
    RSYNCOPTS+=(--rsh="ssh -q -p ${PORT}");
    backup_dest="${RHOST}:${destination}";
else
    backup_dest=$destination
fi

# backup data
sync_err=$(rsync "${RSYNCOPTS[@]}" ${source_dir} ${backup_dest} 2>&1 >/dev/null);

# modify the timestamp to reflect the date and time of the backup
update_time=$(/usr/bin/ssh -q -p $PORT $RHOST touch --date="$start_time" ${backup_dest});

# remove snapshot if it exists
if [ ! -z $snapshot ]; then
    umount -f ${source_dir};
    remove_snapshot ${snapshot};
fi

write_log "backup finished";

exit 0
