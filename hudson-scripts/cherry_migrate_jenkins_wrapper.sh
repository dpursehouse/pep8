#!/bin/bash -ex

# If the cm_tools folder exists, make sure it's up to date.  If it
# does not exist yet, create it.
if [ -d cm_tools ] ; then
    ( cd cm_tools && git fetch && git checkout origin/master )
else
    git clone git://review.sonyericsson.net/semctools/cm_tools -b master
fi

# Run the update script
./cm_tools/hudson-scripts/cherry_migrate_jenkins.sh
