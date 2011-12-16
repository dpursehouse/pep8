#!/bin/bash -e

if [ -z "$WORKSPACE" ]; then
    WORKSPACE="./WORKSPACE"
fi

if [ -z "$GERRIT_USER" ]; then
    echo "ERROR: GERRIT_USER is not set"
    exit 1
fi

# Ignore uploaded changes on PLD gits
curl http://android-ci-platform.sonyericsson.net/job/pld-gits/lastSuccessfulBuild/artifact/pld-gits.txt > out/pld-gits.txt
if [ $(grep -c $GERRIT_PROJECT out/pld-gits.txt) -eq 1 ]; then
    exit 0
fi

if [ -d cm_tools ] ; then
    rm -rf cm_tools
fi

git clone git://review.sonyericsson.net/semctools/cm_tools -b master

sleep 120

cd cm_tools
python commit_message_check.py \
    --verbose \
    --cache-path ../cache/ \
    --change $GERRIT_CHANGE_NUMBER \
    --project $GERRIT_PROJECT \
    --patchset $GERRIT_PATCHSET_NUMBER \
    --gerrit-user hudson_reviewer
