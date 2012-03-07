#!/bin/bash -ex

EXIT_STATUS=0

# Set up the git
PROJNAME='temp'/$(basename $GERRIT_PROJECT)
git init $PROJNAME
GIT_COMMAND='git --git-dir='$PROJNAME'/.git --work-tree='$PROJNAME

# Fetch the patch set
$GIT_COMMAND fetch git://review.sonyericsson.net/$GERRIT_PROJECT $GERRIT_REFSPEC
$GIT_COMMAND checkout FETCH_HEAD

# Create PEP-8 log file
echo -e "PEP-8 log:\n" > $WORKSPACE/out/pep8_log.txt

# Iterate over all files that have been changed
while IFS= read FILENAME;
do
    # Exclude external modules
    if grep -v "^external/" <<<$FILENAME ; then
        # Check for whitespace errors
        $GIT_COMMAND diff --check HEAD~1.. -- $FILENAME \
            | tee -a $WORKSPACE/out/whitespace_log.txt
        WHITESPACE_STATUS=${PIPESTATUS[0]}
        if [ "$WHITESPACE_STATUS" -ne 0 ]; then
            EXIT_STATUS=`expr $EXIT_STATUS + 1`
        fi

        # Run PEP-8 check on Python files
        if grep -q "\.py$" <<<$FILENAME ; then
            python cm_tools/pep8.py -v -r --show-source --show-pep8 \
                $PROJNAME/$FILENAME | tee -a $WORKSPACE/out/pep8_log.txt
            STATUS=${PIPESTATUS[0]}
            if [ "$STATUS" -ne 0 ]; then
                EXIT_STATUS=`expr $EXIT_STATUS + 1`
            fi
        fi
    fi
done< <($GIT_COMMAND diff --name-only --diff-filter=AM HEAD~1..)

# Run unit tests
TESTDIR="$PROJNAME/tests"
if [ -d "$TESTDIR" ]; then
    make --directory $TESTDIR 2>&1 | tee -a $WORKSPACE/out/unit_test_log.txt
    UNIT_TEST_STATUS=${PIPESTATUS[0]}
    if [ "$UNIT_TEST_STATUS" -ne 0 ]; then
        EXIT_STATUS=`expr $EXIT_STATUS + 1`
    fi
fi

exit $EXIT_STATUS
