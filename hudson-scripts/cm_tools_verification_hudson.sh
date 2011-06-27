#!/bin/bash -ex

EXIT_STATUS=0

# Download the project
git clone git://review.sonyericsson.net/semctools/cm_tools

# Fetch the patch set
cd cm_tools
git fetch git://review.sonyericsson.net/semctools/cm_tools $GERRIT_REFSPEC

# Check out the head
git checkout FETCH_HEAD

# Find files that have been changed
while IFS= read FILENAME;
do
    # Run pep8 check on Python files
    if grep -q "\.py$" <<<$FILENAME ; then
        python pep8.py -r $FILENAME | tee temp.txt
        STATUS=${PIPESTATUS[0]}
        if [ "$STATUS" -ne 0 ]; then
            EXIT_STATUS=`expr $EXIT_STATUS + 1`
            echo $EXIT_STATUS
        fi
    fi
done< <(git diff --name-only --diff-filter=AM HEAD~1..)

exit $EXIT_STATUS