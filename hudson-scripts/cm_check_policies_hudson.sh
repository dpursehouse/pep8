#!/bin/bash -ex

# To avoid nagging reviewers on every patch set, only check
# the first patch set and then every third patch set.
if [ `expr $GERRIT_PATCHSET_NUMBER % 3` -eq 1 ] ; then

    cd cm_tools
    python report_change_impact.py \
        --policy etc/dms_policy.xml \
        --verbose \
        --cache-path ../cache/ \
        --change $GERRIT_CHANGE_NUMBER \
        --project $GERRIT_PROJECT \
        --patchset $GERRIT_PATCHSET_NUMBER \
        --branch $GERRIT_BRANCH \
        --manifest-path ../manifest \
        --gerrit-user hudson_reviewer \
        --exclude-git '^ia/' \
        --exclude-git '^edu/' \
        --exclude-git '^semctools/(eclipse|hudson)/' \
        --exclude-git '^kernel-2\.6$' \
        --exclude-manifest-ref esea-feat-pldcm-tools \
        --exclude-manifest-ref '/edream4\.0\.1-decoupled$' \
        --exclude-manifest-ref rg-integration \
        --exclude-manifest-ref cherrypick \
        --exclude-manifest-ref '-int$' \
        --exclude-manifest-ref '/ics-blue-qct-mw$' \
        --exclude-manifest-ref '/ics-pitaya-viv$' \
        --exclude-manifest-ref '/ginger-ste-dev(-int2)?$' \
        --exclude-manifest-ref '/ginger-dev$' \
        --exclude-manifest-ref '/test-mogami-yaffs$' \
        --exclude-manifest-ref '/adili-test-script$' \
        --exclude-manifest-ref '-(cupcake|donut)-deckard' \
        --exclude-manifest-ref '/sw-integration' \
        --exclude-manifest-ref '/browser-investigation$' \
        --exclude-manifest-ref '/donut-update$' \
        --exclude-manifest-ref '/homesrcn$' \
        --exclude-manifest-ref '/caf/' \
        --exclude-manifest-ref '/ti/' \
        --exclude-manifest-ref '-feat(ure)$' \
        --exclude-manifest-ref '-feat(ure)?-'
fi
