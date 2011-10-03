#!/bin/bash -ex

EXIT_STATUS=0

# Set up the git
PROJNAME='temp'/$(basename $GERRIT_PROJECT)
git init $PROJNAME

# Fetch the patch set
git --git-dir=$PROJNAME/.git --work-tree=$PROJNAME fetch git://review.sonyericsson.net/$GERRIT_PROJECT $GERRIT_REFSPEC
git --git-dir=$PROJNAME/.git --work-tree=$PROJNAME checkout FETCH_HEAD

# Create log file
# Workaround to prevent Jenkins error caused by trying to archive non-existent file
echo -e "PEP-8 log:\n" > $WORKSPACE/out/pep8_log.txt

# Find files that have been changed
while IFS= read FILENAME;
do
    # Run pep8 check on Python files
    if grep -q "\.py$" <<<$FILENAME ; then
        python cm_tools/pep8.py -v -r $PROJNAME/$FILENAME | tee -a $WORKSPACE/out/pep8_log.txt
        STATUS=${PIPESTATUS[0]}
        if [ "$STATUS" -ne 0 ]; then
            EXIT_STATUS=`expr $EXIT_STATUS + 1`
        fi
    fi
done< <(git --git-dir=$PROJNAME/.git --work-tree=$PROJNAME diff --name-only --diff-filter=AM HEAD~1..)

exit $EXIT_STATUS