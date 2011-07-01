#!/bin/bash -ex

rm -rf $WORKSPACE
mkdir $WORKSPACE
cd $WORKSPACE

git clone git://review.sonyericsson.net/semctools/cm_tools.git -b master

bash cm_tools/dms-tag-check/dms_tag_search.sh
