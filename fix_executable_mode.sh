#!/bin/sh

git ls-files -oc --exclude-standard | \
    egrep -v '\.(pl|py|sh)$' | \
    while read f ; do
        if ! test -L "$f" && \
            test -x "$f" && ! file -b "$f" | grep -iq executable ; then
            echo "Shouldn't be executable: $f"
            chmod -x "$f"
        fi
    done
