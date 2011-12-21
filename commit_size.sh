#!/bin/sh

# Print the size of the commit in kilobytes

SIZE_B=`git diff-tree -r -c -M -C --no-commit-id HEAD | \
    awk '{print $4}' | \
        git cat-file --batch-check | \
            awk '{SUM += $3} END {print SUM}'`
SIZE_KB=`echo "$SIZE_B / 1024" | bc`
echo $SIZE_KB
