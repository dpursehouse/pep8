#!/bin/bash -ex

# If GERRIT_USER is not specified in the parameters, use the default
if [ -z "$GERRIT_USER" ]; then
    GERRIT_USER="hudson_reviewer"
fi

# Remove the output directory if it already exists, and create it again
OUTDIR=$PWD"/out"
if [ -d $OUTDIR ] ; then
    rm -rf $OUTDIR
fi
mkdir $OUTDIR

# Get list of PLD gits
PLD_GITS=$(cat <<EOF
http://android-ci-platform.sonyericsson.net/job/pld-gits/lastSuccessfulBuild/\
artifact/pld-gits.txt
EOF
)
curl $PLD_GITS | tee $OUTDIR/pld-gits.txt > /dev/null
CURL_STATUS=${PIPESTATUS[0]}
if [ 0 -eq "$CURL_STATUS" ]; then
    # Ignore uploaded changes on PLD gits
    if [ $(grep -c ^$GERRIT_PROJECT$ $OUTDIR/pld-gits.txt) -eq 1 ]; then
        exit 0
    fi
fi

EXTRA_PARAMS=""
if [ ! -z "$EXCLUDED_GITS" ]; then
    arr=$(echo $EXCLUDED_GITS | tr -s "," "\n")
    for git in $arr; do
        EXTRA_PARAMS="$EXTRA_PARAMS --exclude-git $git"
    done
fi

cd cm_tools

# Invoke the commit message checker
python commit_message_check.py \
    --verbose \
    --change $GERRIT_CHANGE_NUMBER \
    --project $GERRIT_PROJECT \
    --patchset $GERRIT_PATCHSET_NUMBER \
    --revision $GERRIT_PATCHSET_REVISION \
    --gerrit-user $GERRIT_USER $EXTRA_PARAMS
