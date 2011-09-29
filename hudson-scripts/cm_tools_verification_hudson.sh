#!/bin/bash -ex

EXIT_STATUS=0

# Set up the git
PROJNAME='temp'/$(basename $GERRIT_PROJECT)
git init $PROJNAME

# Fetch the patch set
git --git-dir=$PROJNAME/.git --work-tree=$PROJNAME fetch git://review.sonyericsson.net/$GERRIT_PROJECT $GERRIT_REFSPEC
git --git-dir=$PROJNAME/.git --work-tree=$PROJNAME checkout FETCH_HEAD

# Find files that have been changed
while IFS= read FILENAME;
do
    # Run pep8 check on Python files
    if grep -q "\.py$" <<<$FILENAME ; then
        python cm_tools/pep8.py -r $PROJNAME/$FILENAME | tee pep8_log.txt
        STATUS=${PIPESTATUS[0]}
        if [ "$STATUS" -ne 0 ]; then
            EXIT_STATUS=`expr $EXIT_STATUS + 1`
        fi
    fi
done< <(git --git-dir=$PROJNAME/.git --work-tree=$PROJNAME diff --name-only --diff-filter=AM HEAD~1..)

exit $EXIT_STATUS