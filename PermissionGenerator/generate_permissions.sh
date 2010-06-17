#!/bin/bash
ROOT=`pwd`
LOG=$ROOT/out.html
PERMGEN=$ROOT/PermissionGenerate.jar
BRANCH="$1"

if [ -z "$2" ]
then
    REPO_DIR="$$.tmp"
else
    REPO_DIR="$2"
fi

cat  > $LOG << EOF
<html lang="en">
<head>
  <title>Permission Summary</title>
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
  <style type="text/css">
  </style>
</head>
<body>
<table>
<tr>
<th style=\"font-family:verdana;font-size:80%;color:green\" align=\"left\">Permission Name</th>
<th style=\"font-family:verdana;font-size:80%;color:green\" align=\"left\">Description</th>
<th style=\"font-family:verdana;font-size:80%;color:green\" align=\"left\">Label</th>
<th style=\"font-family:verdana;font-size:80%;color:green\" align=\"left\">Permission Group</th>
<th style=\"font-family:verdana;font-size:80%;color:green\" align=\"left\">Protection Level</th>
</tr>
EOF

function process_create_repo_and_sync() {
    REPO_INIT_CMD="repo init -u git://review.sonyericsson.net/platform/manifest.git -b $BRANCH"
    mkdir $REPO_DIR
    cd $REPO_DIR
    $REPO_INIT_CMD
    repo sync
    if [ $? != 0 ]; then
	echo "Error synchronizing repository...exiting" 2>&1
	exit 1
    fi
}

function process_git() {
    if [ -f "AndroidManifest.xml" ]; then
        CMD="java -jar $PERMGEN -t `pwd` -m AndroidManifest.xml -r res/values"
        echo `pwd`
        echo $CMD
        $CMD >> $LOG
    fi
}

function process_repo() {
    for i in `find * -name AndroidManifest.xml -type f` ; do
        ( cd `dirname $i` && process_git )
    done
}

make clean
make
process_create_repo_and_sync
process_repo

cat >> $LOG << EOF
</table>
</body>
</html>
EOF
