#!/bin/bash -e

if [ -z "$WORKSPACE" ]; then
    WORKSPACE="./WORKSPACE"
fi

if [ -z "$GERRIT_USER" ]; then
    echo "ERROR: GERRIT_USER is not set"
    exit 1
fi

FAIL_MESSAGE="FAILED: Change contains whitespace errors.

See whitespace check log for details:

$BUILD_URL"

PASS_MESSAGE="Whitespace check OK"

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

    # Send the review comment to Gerrit
    if [ $WHITESPACE_STATUS != 0 ]; then
        REVIEW_MESSAGE=$FAIL_MESSAGE
    else
        REVIEW_MESSAGE=$PASS_MESSAGE
    fi
    ssh -p 29418 review.sonyericsson.net -l $GERRIT_USER gerrit review \
    --project=$GERRIT_PROJECT $GERRIT_PATCHSET_REVISION \'--message="$REVIEW_MESSAGE"\'

    # Exit
    exit $WHITESPACE_STATUS
fi
