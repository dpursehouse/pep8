#!/bin/bash -e

if [ -z "$WORKSPACE" ]; then
    WORKSPACE="./WORKSPACE"
fi

# Clean workspace
rm -rf $WORKSPACE
mkdir $WORKSPACE
cd $WORKSPACE

git clone git://review.sonyericsson.net/semctools/cm_tools.git -b master

bash -x cm_tools/dms-tag-check/dms_tag_search.sh
