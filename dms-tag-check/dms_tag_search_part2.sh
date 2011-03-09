#!/bin/bash -e
#-------------------------------------------------------------------------------------
#Part 2: The following job validates the tag value for the tag-only branch
#-------------------------------------------------------------------------------------
FILE_PATH=result-dir/dms_fix_for.txt                 #dms_fix_for.txt file copied from the build artifacts of the other job
TARGET_TAG_LIST=tag_list.txt

echo $DMS_TAG_LIST |sed 's/\,/\n/g'> $TARGET_TAG_LIST
COUNT_DMS_TAG_OK=0
COUNT_DMS_TAG_NOK=0

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
     echo "Fix For:"$FIX_FOR
     if [ "$FIX_FOR" = "Server_error" ];then
         echo "Server connection error"
         exit 1
     else
         RESULT=`grep "$FIX_FOR$" $TARGET_TAG_LIST`
         if [ "$RESULT" != "$FIX_FOR" ]
         then
             COUNT_DMS_TAG_NOK=`expr $COUNT_DMS_TAG_NOK + 1`
         else
             COUNT_DMS_TAG_OK=`expr $COUNT_DMS_TAG_OK + 1`
         fi
     fi
     i=`expr $i + 1`
  done
   MSG=`cat $FILE_PATH`
   # Setting the review message depending on the dms tag found
   if [ $COUNT_DMS_TAG_OK -ne 0 -a $COUNT_DMS_TAG_NOK -eq 0 ]
   then
       MSG="$MSG All DMS issues tagged properly"
   elif [ $COUNT_DMS_TAG_OK -ne 0 -a $COUNT_DMS_TAG_NOK -ne 0 ]
   then
       MSG="$MSG Some DMS issues are not tagged properly"
   else
       MSG="$MSG None of the DMS issues are tagged"
   fi
fi
#Update the gerrit with the review message for the change
ssh -p 29418 review.sonyericsson.net -l $HUDSON_REVIEWER gerrit review \
--project=$GERRIT_PROJECT $GERRIT_PATCHSET_REVISION \
\'--message="$MSG"\'
