#!/bin/bash
#Backup data to the Brazelton Lab file server

# store command line arguments
args=("$@")

# utilities
ssh=$(which ssh)

# functions
check_process() {
  if [ -z "$1" ]; then
    logger "$0: backup failed: $2";
    exit 1
  fi
}

remove_failed() {
  if [ -n "$1" ]; then
    logger "$0: backup failed: $1"
    ssh -q -p $PORT $HOST rm -Rf $BACKUP
    /bin/umount $SNAP_DIR
    /sbin/lvremove -f $SNAP_PATH
    exit 1
  fi
}

# show usage if help argument given
for arg in ${args[@]}; do
  if [ $arg == '-h' ] || [ $arg == '--help' ]; then
    printf "Usage: $0 [device_path] [backup_path]\n"
    exit 1
  fi
done

# variables
SRC=${args[0]}
DEST=${args[1]}
HOST='root@baas-becking.biology.utah.edu'
PORT=53213
LOG='/var/log/rsync'
SNAP_DIR='/mnt/snapshot'
SNAP_NAME='lv_snap'
BACKUP=$DEST/$(date -I)

LINK=$($ssh -q -p $PORT $HOST find $DEST -maxdepth 1 -type d | sort -n | \
  tail -1)
FAIL_REASON="unable to obtain backup link"
check_process $LINK $FAIL_REASON

IFS='- ' read -a array <<< $SRC; SNAP_PATH=${array[0]}'-'$SNAP_NAME
if [ ! -d $SNAP_DIR ]; then
  $(which mkdir) $SNAP_DIR;
fi

snap=$(/sbin/lvcreate --size 20GiB --snapshot --name $SNAP_NAME $SRC)
FAIL_REASON="could not create snapshot of $SRC"
check_process $snap $FAIL_REASON

/bin/mount $SNAP_PATH $SNAP_DIR

sync=$(/usr/bin/rsync -e "ssh -q -p $PORT" -azA --log-file=$LOG --exclude="lost+found" \
	--delete --link-dest=$LINK $SNAP_DIR/ $HOST:$BACKUP 2>&1 >/dev/null)
remove_failed $sync

mod_mtime=$($ssh -q -p $PORT $HOST touch $BACKUP 2>&1 >/dev/null)
remove_failed $mod_mtime

/bin/umount $SNAP_DIR
/sbin/lvremove -f $SNAP_PATH

exit 0
