#!/bin/bash -ex

if [ -z "$WORKSPACE" ]; then
    echo "ERROR: WORKSPACE is not set"
    exit 1
fi

if [ -n "$GERRIT_CHANGE_NUMBER" ]; then
    rm -rf $WORKSPACE
    mkdir $WORKSPACE
    cd $WORKSPACE

    git clone git://review.sonyericsson.net/semctools/cm_tools -b master
    cd cm_tools/hudson-scripts
    bash -ex ./cm_tools_verification_hudson.sh
fi
