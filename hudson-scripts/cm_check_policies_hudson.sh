#!/bin/bash -ex

for m in "$@"
do
    python cm_tools/report_change_impact.py \
        --verbose \
        --change $GERRIT_CHANGE_NUMBER \
        --project $GERRIT_PROJECT \
        --patchset $GERRIT_PATCHSET_NUMBER \
        --branch $GERRIT_BRANCH \
        --revision $GERRIT_PATCHSET_REVISION \
        --manifest-name $m \
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
        --exclude-manifest-ref '-feat(ure)?-' \
        --exclude-manifest-ref '/volatile-' \
        --exclude-manifest-ref '-ux-program$' \
        --exclude-manifest-ref '/ics-blue-att-test-downstream$' \
        --exclude-manifest-ref '/feature-' \
        --exclude-manifest-ref '/odin-8064$'
done
