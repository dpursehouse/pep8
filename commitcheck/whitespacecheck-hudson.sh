#!/bin/bash -ex

if [ -z "$WORKSPACE" ]; then
    WORKSPACE="./WORKSPACE"
fi

rm -rf $WORKSPACE
mkdir $WORKSPACE
cd $WORKSPACE

if [ -n "$GERRIT_CHANGE_NUMBER" ]; then
    # Set up folders
    mkdir out
    mkdir temp

    # Download the project
    PROJNAME=$(basename $GERRIT_PROJECT)
    git clone git://review.sonyericsson.net/$GERRIT_PROJECT temp/$PROJNAME

    # Fetch the patch set
    cd temp/$PROJNAME
    git fetch git://review.sonyericsson.net/$GERRIT_PROJECT $GERRIT_REFSPEC

    # Checkout the head
    git checkout FETCH_HEAD

    # Check for whitespace errors
    git diff HEAD^ HEAD --check | tee $WORKSPACE/out/whitespace_log.txt
    WHITESPACE_STATUS=${PIPESTATUS[0]}

    # Exit
    if [ $WHITESPACE_STATUS != 0 ]; then
        exit 1
    fi
fi
