#!/bin/bash -e

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

PROJ_DIR=
FILES=
if [ `echo $GERRIT_PROJECT | grep 'decoupled-deliveries/.*'` ] ; then
    PROJ_DIR=`echo $GERRIT_PROJECT | sed 's#^.*/\(decoupled-deliveries/.*\)#\1#'`
    FILES='*.xml'
else
    PROJ_DIR=`echo $GERRIT_PROJECT | sed 's#^.*/##'`
    FILES='package-files/*.xml'
fi

rm -rf $PROJ_DIR
mkdir -p $PROJ_DIR
cd $PROJ_DIR
git init
git pull git://review.sonyericsson.net/$GERRIT_PROJECT $GERRIT_REFSPEC
cd $WORKSPACE

# List all the files that will be included in the test cases
ls -x $PROJ_DIR/$FILES

git clone git://review.sonyericsson.net/semctools/semcsystem -b ginger-common
cd semcsystem
if [ -d tests ]; then
    make -C tests external-packages
fi
