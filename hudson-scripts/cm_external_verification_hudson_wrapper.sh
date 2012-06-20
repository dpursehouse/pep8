#!/bin/bash -ex

if [ -z "$WORKSPACE" ]; then
    echo "ERROR: WORKSPACE is not set"
    exit 1
fi

rm -rf ~/.c2d/repository_config.properties
rm -rf $WORKSPACE
mkdir $WORKSPACE
cd $WORKSPACE

sleep 30

#The python scripts used in the test cases are present in semcsystem git.
#Hence it is required to have the semcsystem git for the tests to run successfully

PROJ_DIR=`echo $GERRIT_PROJECT | sed 's#^.*/##'`
rm -rf $PROJ_DIR
mkdir -p $PROJ_DIR
cd $PROJ_DIR
git init
git pull git://review.sonyericsson.net/$GERRIT_PROJECT $GERRIT_REFSPEC
cd ..

git clone git://review.sonyericsson.net/semctools/semcsystem -b ginger-common
cd semcsystem

if [ -d tests ]; then
    make -C tests external-packages
fi
