#!/bin/bash -ex

# If the cm_tools folder exists, make sure it's up to date.  If it
# does not exist yet, create it.
if [ -d cm_tools ] ; then
    cd cm_tools
    git fetch
    git checkout origin/master
    cd ..
else
    git clone git://review.sonyericsson.net/semctools/cm_tools -b master
fi

# Invoke the commit message checker
cm_tools/hudson-scripts/commitcheck-hudson.sh 2>&1
