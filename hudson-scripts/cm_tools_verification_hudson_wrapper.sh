#!/bin/bash -ex

if [ -z "$WORKSPACE" ]; then
    echo "ERROR: WORKSPACE is not set"
    exit 1
fi

if [ -n "$GERRIT_CHANGE_NUMBER" ]; then
    rm -rf $WORKSPACE
    mkdir $WORKSPACE
    cd $WORKSPACE
    mkdir out

    git clone git://review.sonyericsson.net/semctools/cm_tools -b master
    bash -ex ./cm_tools/hudson-scripts/cm_tools_verification_hudson.sh
fi
