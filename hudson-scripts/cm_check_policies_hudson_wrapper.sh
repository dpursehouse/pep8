#!/bin/bash -ex

sleep 120

# If the cm_tools folder exists, make sure it's up to date.  If it
# does not exist yet, create it.
if [ -d cm_tools ] ; then
    ( cd cm_tools && git fetch && git checkout origin/master )
else
    git clone git://review.sonyericsson.net/semctools/cm_tools -b master
fi

# If the manifest folder exists, make sure it's up to date.  If it
# does not exist yet, create it.
if [ -d manifest ] ; then
    ( cd manifest && git fetch && git remote prune origin )
else
    git clone git://review.sonyericsson.net/platform/manifest
fi

# Invoke the cm policies checker
cm_tools/hudson-scripts/cm_check_policies_hudson.sh 2>&1
