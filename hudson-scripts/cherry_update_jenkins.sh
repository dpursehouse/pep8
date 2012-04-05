#!/bin/bash -ex

# Following parameters must be exported by the Jenkins job
if [ -z "$CHERRY_SOURCE_BRANCH" ]; then
    echo "ERROR: CHERRY_SOURCE_BRANCH is not set"
    exit 1
fi

if [ -z "$CHERRY_TARGET_BRANCH" ]; then
    echo "ERROR: CHERRY_TARGET_BRANCH is not set"
    exit 1
fi

if [ -z "$CHERRY_MANIFEST" ]; then
    echo "ERROR: CHERRY_MANIFEST is not set"
    exit 1
fi

# Update cherry pick status
python ./cm_tools/cherry_update.py \
  --source $CHERRY_SOURCE_BRANCH \
  --target $CHERRY_TARGET_BRANCH \
  --manifest $CHERRY_MANIFEST
