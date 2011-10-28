#!/bin/bash -e

if [ -z "$WORKSPACE" ]; then
    WORKSPACE="./WORKSPACE"
fi

if [ -z "$GERRIT_USER" ]; then
    echo "ERROR: GERRIT_USER is not set"
    exit 1
fi

FAIL_MESSAGE="FAILED: Commit message does not follow the guideline:

https://wiki.sonyericsson.net/androiki/Commit_messages

See commit message check log for details:

$BUILD_URL"

rm -rf $WORKSPACE
mkdir $WORKSPACE
cd $WORKSPACE

if [ -n "$GERRIT_CHANGE_NUMBER" ]; then
    # Set up folders
    mkdir out
    mkdir temp

    # Ignore uploaded changes on PLD gits
    curl http://android-ci-platform.sonyericsson.net/job/pld-gits/lastSuccessfulBuild/artifact/pld-gits.txt > out/pld-gits.txt
    if [ $(grep -c $GERRIT_PROJECT out/pld-gits.txt) -eq 1 ]; then
        exit 0
    fi

    # Download the tools git
    git clone git://review.sonyericsson.net/semctools/cm_tools -b master

    # Download the project
    PROJNAME=$(basename $GERRIT_PROJECT)
    git clone git://review.sonyericsson.net/$GERRIT_PROJECT temp/$PROJNAME

    # Fetch the patch set
    cd temp/$PROJNAME
    git fetch git://review.sonyericsson.net/$GERRIT_PROJECT $GERRIT_REFSPEC

    # Checkout the head
    git checkout FETCH_HEAD

    # Get the commit message
    git cat-file -p HEAD > $WORKSPACE/out/commit_message.txt

    # Run the commit message check tool
    cd $WORKSPACE
    python cm_tools/commit_message_check.py < out/commit_message.txt | tee out/commit_message_check_log.txt
    COMMIT_MESSAGE_STATUS=${PIPESTATUS[0]}

    # If commit message check failed, send a review comment to Gerrit
    if [ 0 -ne "$COMMIT_MESSAGE_STATUS" ]; then
        ssh -p 29418 review.sonyericsson.net -l $GERRIT_USER gerrit review \
        --project=$GERRIT_PROJECT $GERRIT_PATCHSET_REVISION \'--message="$FAIL_MESSAGE"\'
    fi

    # Exit
    exit $COMMIT_MESSAGE_STATUS
fi
