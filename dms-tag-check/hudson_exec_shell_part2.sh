#!/bin/bash -e

bash cm_tools/dms-tag-check/dms_tag_search_part2.sh

export BUILD_DESC=`cat build_description.txt`
curl -s "${BUILD_URL}submitDescription?description=${BUILD_DESC}"
