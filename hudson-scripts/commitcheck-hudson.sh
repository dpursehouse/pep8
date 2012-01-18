#!/bin/bash -ex

# If GERRIT_USER is not specified in the parameters, use the default
if [ -z "$GERRIT_USER" ]; then
    GERRIT_USER="hudson_reviewer"
fi

# Remove the output directory if it already exists, and create it again
OUTDIR="out"
if [ -d $OUTDIR ] ; then
    rm -rf $OUTDIR
fi
mkdir $OUTDIR

# Ignore uploaded changes on PLD gits
curl http://android-ci-platform.sonyericsson.net/job/pld-gits/lastSuccessfulBuild/artifact/pld-gits.txt > $OUTDIR/pld-gits.txt
if [ $(grep -c $GERRIT_PROJECT $OUTDIR/pld-gits.txt) -eq 1 ]; then
    exit 0
fi

# If the cm_tools folder exists, make sure it's up to date.  If it
# does not exist yet, create it.
if [ -d cm_tools ] ; then
    cd cm_tools
    git fetch
    git checkout origin/master
else
    git clone git://review.sonyericsson.net/semctools/cm_tools -b master
    cd cm_tools
fi

# Invoke the commit message checker
python commit_message_check.py \
    --verbose \
    --cache-path ../cache/ \
    --change $GERRIT_CHANGE_NUMBER \
    --project $GERRIT_PROJECT \
    --patchset $GERRIT_PATCHSET_NUMBER \
    --gerrit-user $GERRIT_USER
