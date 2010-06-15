#!/bin/bash
# It would be nicer to use smbclient since it has kerberos support,
# but right now it seems very unreliable in our environment

usage() {
    echo "cifscopy CIFSTARGET SOURCE...
    Note, you will be asked to type in your password
    example: cifscopy //seldfil441/terminalsw$/adir afile adirectory"
}

control_c() {
    echo "\nCaught Control-C, cleaning up!"
    umount.cifs $MOUNTDIR
    rmdir $MOUNTDIR
    exit 3
}

trap control_c SIGINT

if [ $# -lt 2 ]; then
    usage
    exit 1
fi

CIFSTARGET=$1
shift

exitstatus=0

MOUNTDIR=`mktemp -d`
if mount.cifs $CIFSTARGET $MOUNTDIR -o username=$USER; then
    if ! cp -vr "$@" $MOUNTDIR; then
        exitstatus=2
    fi
    umount.cifs $MOUNTDIR
else
    exitstatus=1
fi
rmdir $MOUNTDIR

exit $exitstatus
