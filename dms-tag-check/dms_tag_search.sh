#!/bin/bash -e

#-------------------------------------------------------------------------------------
#Part 1: This job will prepare the environment and extract the DMS from the commit message
#-------------------------------------------------------------------------------------

if [ -z "$WORKSPACE" ]; then
    WORKSPACE="./WORKSPACE"
fi

if [ -z "$DMS_TAG_LIST" ]; then
    echo "No DMS Tag list defined to validate. Exiting.."
    exit 1
fi

if [ -z "$HUDSON_REVIEWER" ]; then
    echo "No Hudson reviewer defined to review. Exiting.."
    exit 1
fi

# Clean workspace
rm -rf $WORKSPACE
mkdir $WORKSPACE
cd $WORKSPACE

mkdir output
MSG_COMMIT_FILE=$WORKSPACE/output/msg_commit.txt

git clone git://review.sonyericsson.net/semctools/cm_tools.git -b master

if [ -n "$GERRIT_CHANGE_NUMBER" ]; then

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
