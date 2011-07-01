#!/bin/bash -e

bash -x cm_tools/dms-tag-check/dms_tag_search_part2.sh

export BUILD_DESC=`cat build_description.txt | sed 's/ /%20/g' | sed 's/=/%3d/g'`
curl -s "${BUILD_URL}submitDescription?description=${BUILD_DESC}"
