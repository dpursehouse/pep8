#!/bin/bash -ex

# Clone the cm_tools git
git clone git://review.sonyericsson.net/semctools/cm_tools -b master

# Run the update script
./cm_tools/hudson-scripts/cherry_migrate_jenkins.sh
