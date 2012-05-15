#!/bin/bash -x

#Check mandatory variables of cherrypick.py
if [ -z "$CHERRYPICK_MANIFEST" ]; then
    echo "Error: environment variable CHERRYPICK_MANIFEST must be set."
    exit 1
fi
if [ -z "$CHERRYPICK_TARGET" ]; then
    echo "Error: environment variable CHERRYPICK_TARGET must be set."
    exit 1
fi
if [ -z "$CHERRYPICK_SOURCE" ]; then
    echo "Error: environment variable CHERRYPICK_SOURCE must be set."
    exit 1
fi

#check optional variables of cherrypick.py
if [ -n "$CHERRYPICK_DRY_RUN" ]; then
    CMD="--dry-run"
fi
if [ -n "$CHERRYPICK_MAIL_SENDER" ]; then
    CMD=$CMD" --mail-sender $CHERRYPICK_MAIL_SENDER"
fi
if [ -n "$CHERRYPICK_REVIEWER" ]; then
    CMD="$CMD -r $CHERRYPICK_REVIEWER"
fi

if [ ! -d result-dir ]; then
    mkdir result-dir
fi

cd result-dir

if [ -d .repo ]; then
    echo "Repo already initialized"
    rm -rf .repo/project.list
else
    time repo init -u \
    git://review.sonyericsson.net/platform/manifest.git -b \
    $CHERRYPICK_SOURCE
fi

time repo sync -d --jobs=5

cd $WORKSPACE

#invoke cherrypick script
python cm_tools/cherrypick.py -s $CHERRYPICK_SOURCE -t \
    $CHERRYPICK_TARGET -m $CHERRYPICK_MANIFEST \
    -w $WORKSPACE/result-dir -vv $CMD
