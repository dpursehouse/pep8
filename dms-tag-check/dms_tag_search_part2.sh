#!/bin/bash -e
#-------------------------------------------------------------------------------------
#Part 2: The following job validates the tag value for the tag-only branch
#-------------------------------------------------------------------------------------
FILE_PATH=result-dir/dms_fix_for.txt                 #dms_fix_for.txt file copied from the build artifacts of the other job
TARGET_TAG_LIST=tag_list.txt
RESULT_FILE=result.txt

echo $DMS_TAG_LIST |sed 's/\,/\n/g'> $TARGET_TAG_LIST
COUNT_DMS_TAG_OK=0
COUNT_DMS_TAG_NOK=0
CODE_REVIEW=-1
#Check if the commit message has DMS issue
DMS_FOUND=`cat $FILE_PATH`
if [ -z "$DMS_FOUND" ];then
    MSG="Commit message does not include the FIX=DMS tag"
else
    DMS_COUNT=`cat $FILE_PATH |wc -l`
    i=1
    echo $DMS_COUNT
    while [ $i -le $DMS_COUNT ]
    do
        FIX_FOR=`cat $FILE_PATH | head -$i | tail -1 | sed 's/.*://' | sed 's/.$//'`
        DMS_TAG=`cat $FILE_PATH | head -$i | tail -1 | sed 's/.$//'`
        echo "Fix For:"$FIX_FOR
        if [ "$FIX_FOR" = "Server_error" ];then
            echo "Server connection error"
            exit 1
        else
            if [ "`grep "$FIX_FOR$" $TARGET_TAG_LIST`" != "" ]
            then
                RESULT="`grep "$FIX_FOR$" $TARGET_TAG_LIST`"
            else
                RESULT=""
            fi
            if [ "$RESULT" != "$FIX_FOR" ]
            then
                if [ "$FIX_FOR" = "Not found" ]
                then
                    echo -e "$DMS_TAG : Tag Not Found \n" >> $RESULT_FILE
                else
                    echo -e "$DMS_TAG : Invalid tag \n" >> $RESULT_FILE
                fi
                COUNT_DMS_TAG_NOK=`expr $COUNT_DMS_TAG_NOK + 1`
            else
                echo -e "$DMS_TAG : Valid tag \n" >> $RESULT_FILE
                COUNT_DMS_TAG_OK=`expr $COUNT_DMS_TAG_OK + 1`
            fi
        fi
        i=`expr $i + 1`
    done
    # Setting the review message depending on the dms tag found
    if [ $COUNT_DMS_TAG_OK -ne 0 -a $COUNT_DMS_TAG_NOK -eq 0 ]
    then
        echo "All DMS tags are valid for $GERRIT_BRANCH" >> $RESULT_FILE
        CODE_REVIEW=0
    elif [ $COUNT_DMS_TAG_OK -ne 0 -a $COUNT_DMS_TAG_NOK -ne 0 ]
    then
        echo "Some DMS tags are not Valid for $GERRIT_BRANCH" >> $RESULT_FILE
    else
        echo "None of the DMS are tagged" >> $RESULT_FILE
    fi
    MSG=`cat $RESULT_FILE`
fi
#Update the gerrit with the review message for the change
ssh -p 29418 review.sonyericsson.net -l $HUDSON_REVIEWER gerrit review \
--project=$GERRIT_PROJECT $GERRIT_PATCHSET_REVISION --code-review $CODE_REVIEW \
\'--message="$MSG"\'
