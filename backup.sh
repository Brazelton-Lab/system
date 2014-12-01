#!/bin/bash
#Backup data to the Brazelton Lab file server

# store command line arguments
args=("$@")

# utilities used
ssh=$(which ssh)
rsync=$(which rsync)
mount=$(which mount)
umount=$(which umount)
lvcreate=$(which lvcreate)
lvremove=$(which lvremove)

# show usage if help argument given
for arg in ${args[@]}; do
  if [ $arg == '-h' ] || [ $arg == '--help' ]; then
    printf "Usage: $0 [device_path] [backup_path]\n"
    exit 1
  fi
done

SRC=${args[0]}
DEST=${args[1]}
EXCLUDE='"lost+found"'
HOST='root@baas-becking.biology.utah.edu'
PORT=53213
LOG='/var/log/rsync'
SNAP_DIR='/mnt/snapshot'
SNAP_NAME='lv_snap'

BACKUP=$DEST/$(date -I)
LINK=$($ssh -q -p $PORT $HOST find $DEST -maxdepth 1 -type d | sort -n | \
  tail -1)
if [ -z "$LINK" ]; then
  logger "Backup Failed: Unable to obtain a backup link"
  exit 1
fi
IFS='- ' read -a array <<< $SRC; SNAP_PATH=${array[0]}'-'$SNAP_NAME
if [ ! -d $SNAP_DIR ]; then
  $(which mkdir) $SNAP_DIR;
fi

$lvcreate --size 10GiB --snapshot --name $SNAP_NAME $SRC
$mount $SNAP_PATH $SNAP_DIR

sync=$($rsync -e "ssh -q -p $PORT" -azAX --log-file=$LOG --exclude={$EXCLUDE} \
	--delete --link-dest=$LINK $SNAP_DIR/* $HOST:$BACKUP 2>&1 >/dev/null)
if [ -n "$sync" ]; then
  logger "$sync";
  ssh -q -p $PORT $HOST rm -Rf $BACKUP
fi

$umount $SNAP_DIR
$lvremove -f $SNAP_PATH

exit 0
