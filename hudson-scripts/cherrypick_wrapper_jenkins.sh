#!/bin/bash -x

#These 3 environment variables must be set in Jenkins
#CHERRYPICK_SOURCE: source branch name
#CHERRYPICK_TARGET: target branch name
#CHERRYPICK_MANIFEST: valid value is "platform/manifest" or
#"platform/amssmanifest"

#Optional environment variables could be set in Jenkins
#CHERRYPICK_DRY_RUN: used for test job configuration, value is yes
#CHERRYPICK_MAIL_SENDER: define email used to send out notifications
#CHERRYPICK_REVIEWER: define default reviewer(s), use email and
#separate in comma

git config --global user.name Cherry-picker
cat $HOME/.gitconfig

# If the cm_tools git exists, make sure it's up to date.  If it
# does not exist yet, clone it.
if [ -d cm_tools ] ; then
    ( cd cm_tools && git fetch && git checkout origin/master )
else
    git clone git://review.sonyericsson.net/semctools/cm_tools -b master
fi

# Invoke cherry pick script
cm_tools/hudson-scripts/cherrypick_jenkins.sh
