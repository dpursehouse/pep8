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

# Check for whitespace errors
$GIT_COMMAND diff HEAD^ HEAD --check | tee $WORKSPACE/out/whitespace_log.txt
WHITESPACE_STATUS=${PIPESTATUS[0]}
if [ "$WHITESPACE_STATUS" -ne 0 ]; then
    EXIT_STATUS=`expr $EXIT_STATUS + 1`
fi

# Iterate over all files that have been changed
while IFS= read FILENAME;
do
    # Run PEP-8 check on Python files
    if grep -q "\.py$" <<<$FILENAME ; then
        python cm_tools/pep8.py -v -r $PROJNAME/$FILENAME | tee -a $WORKSPACE/out/pep8_log.txt
        STATUS=${PIPESTATUS[0]}
        if [ "$STATUS" -ne 0 ]; then
            EXIT_STATUS=`expr $EXIT_STATUS + 1`
        fi
    fi
done< <($GIT_COMMAND diff --name-only --diff-filter=AM HEAD~1..)

# Run unit tests
TESTDIR="$PROJNAME/tests"
if [ -d "$TESTDIR" ]; then
    make --directory $TESTDIR
    EXIT_STATUS=`expr $EXIT_STATUS + $?`
fi

exit $EXIT_STATUS
