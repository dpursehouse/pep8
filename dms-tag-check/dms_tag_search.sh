#!/bin/bash -ex

#-------------------------------------------------------------------------------------
#Part 1: This job will prepare the environment and extract the DMS from the commit message
#-------------------------------------------------------------------------------------

if [ -z "$DMS_TAG_LIST" ]; then
    echo "Error: DMS_TAG_LIST is not defined."
    exit 1
fi

if [ -z "$HUDSON_REVIEWER" ]; then
    echo "Error: HUDSON_REVIEWER is not defined."
    exit 1
fi

if [ -n "$GERRIT_CHANGE_NUMBER" ]; then
    mkdir output
    MSG_COMMIT_FILE=$WORKSPACE/output/msg_commit.txt

    #Setup workspace
    git clone git://review.sonyericsson.net/$GERRIT_PROJECT.git
    FOLDER=$(basename $GERRIT_PROJECT)
    cd $FOLDER

    #Get the commit message
    git fetch git://review.sonyericsson.net/$GERRIT_PROJECT $GERRIT_REFSPEC
    git checkout FETCH_HEAD

    #Search the commit message for FIX=DMS
    git cat-file -p HEAD > $MSG_COMMIT_FILE
    grep -i 'FIX=.*DMS*' $MSG_COMMIT_FILE |tr '[a-z]' '[A-Z]' | sed s/^.*FIX=// \
| sed 's/,/\n/g' | sed 's/ //g' >$WORKSPACE/output/DMS_tags.txt
else
    exit 1
fi
