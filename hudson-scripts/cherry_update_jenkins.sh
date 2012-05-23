#!/bin/bash -ex

# Set $CHERRY_UPDATE_EXTRA_PARAM in the Jenkins configuration to
# pass any other parameters to the update script.

# Update cherry pick status
python ./cm_tools/cherry_update.py -v $CHERRY_UPDATE_EXTRA_PARAM
