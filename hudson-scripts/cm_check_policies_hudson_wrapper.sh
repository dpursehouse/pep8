#!/bin/bash -ex

# If the cm_tools git exists, make sure it's up to date.  If it
# does not exist yet, clone it.
if [ -d cm_tools ] ; then
    ( cd cm_tools && git fetch && git checkout origin/master )
else
    git clone git://review.sonyericsson.net/semctools/cm_tools -b master
fi

# If the manifest gits exist, make sure they are up to date.  If they
# do not exist yet, clone them.
CM_CHECK_MANIFESTS=("manifest" "amssmanifest")
for m in "${CM_CHECK_MANIFESTS[@]}"
do
    if [ -d $m ] ; then
        ( cd $m && git fetch && git remote prune origin )
    else
        git clone git://review.sonyericsson.net/platform/$m
    fi
done

# Invoke the cm policies checker
cm_tools/hudson-scripts/cm_check_policies_hudson.sh ${CM_CHECK_MANIFESTS[@]} 2>&1
