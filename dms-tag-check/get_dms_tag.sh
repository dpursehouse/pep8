#!C:/shell.w32-ix86/bash

CURL=/curl-7.21.2-devel-mingw32/bin/curl

#Check if the main JOB_URL exists
if [ -z "$JOB_URL" ]; then
    echo "Please provide the JOB_URL parameter to this job!"
    exit 1
fi

rm -rf result-dir
mkdir result-dir
cd result-dir

echo $JOB_URL
echo $CQ_SITE_LIST
curl -f $JOB_URL/ws/output/DMS_tags.txt -o DMS_tags.txt
curl -f $JOB_URL/ws/cm_tools/dms-tag-check/cq_query_issue.pl -o cq_query_issue.pl

#If $CQ_SITE_LIST is configured in main job,
#then it is passed as an argument to the get_dms_tag.pl file.
if [ -z "$CQ_SITE_LIST" ]; then
    cqperl cq_query_issue.pl
else
    cqperl cq_query_issue.pl --site $CQ_SITE_LIST
fi
