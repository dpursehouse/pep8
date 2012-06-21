#!/bin/bash -x
CODE_REVIEW=-1
MSG="Build URL-"$BUILD_URL

if [ -z "$HUDSON_REVIEWER" ]; then
    echo "Error:HUDSON_REVIEWER is not defined. Exit."
    exit 1
fi

rm -rf .repo/
basename $WORKSPACE | grep $JOB_NAME
if [ "$?" -eq 0 ];then
    rm -rf ${WORKSPACE}/*
else
    echo "Error:This script is only used on hudsonslave. Exit."
    exit 1
fi
git clone git://review.sonyericsson.net/platform/manifest.git
if [ "$?" -eq 0 ];then
    cd manifest
else
    echo "Error:Clone manifest.git failed. Exit."
    exit 1
fi
git fetch git://review.sonyericsson.net/platform/manifest.git \
${GERRIT_REFSPEC} && git checkout FETCH_HEAD
if [ "$?" -eq 0 ];then
    cd ..
else
    echo "Error:Fetch change from Gerrit failed. Exit."
    exit 1
fi
repo init -u git://review.sonyericsson.net/platform/manifest.git -b \
${GERRIT_BRANCH} --reference=$REPO_MIRROR
if [ "$?" -eq 0 ];then
    cp manifest/default.xml .repo/manifests/default.xml
else
    echo "Error:Repo init failed. Exit."
    exit 1
fi
rm -rf manifest
repo sync --jobs=5
if [ "$?" -eq 0 ];then
    CODE_REVIEW=1
fi
ssh -p 29418 review.sonyericsson.net -l $HUDSON_REVIEWER gerrit review \
--project=$GERRIT_PROJECT $GERRIT_PATCHSET_REVISION --code-review $CODE_REVIEW \
\'--message="$MSG"\'
