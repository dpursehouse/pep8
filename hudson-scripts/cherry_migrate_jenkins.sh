#!/bin/bash -x

# Migrate any new cherry picks from the old server to the new one

migrate(){
    ./cm_tools/cherry_migrate.py --old-server android-cm-web.sonyericsson.net \
    --new-server cmweb.sonyericsson.net --source $1 --target $2
    return $?
}

EXIT_STATUS=0

migrate ginger-fuji edream6.0-fuji-r2-release
EXIT_STATUS=`expr $EXIT_STATUS + $?`
migrate ginger-fuji edream6.0-fuji-r2-row-release
EXIT_STATUS=`expr $EXIT_STATUS + $?`
migrate ginger-ste edream6.0-riogrande-release
EXIT_STATUS=`expr $EXIT_STATUS + $?`
migrate edream6.0-riogrande-release edream6.0-riogrande-plus-release
EXIT_STATUS=`expr $EXIT_STATUS + $?`
migrate ics-fuji edream6.1-fuji-release
EXIT_STATUS=`expr $EXIT_STATUS + $?`
migrate ics-fuji edream6.1-fuji-r2-att-release
EXIT_STATUS=`expr $EXIT_STATUS + $?`
migrate ics-fuji-kddi edream6.1-fuji-kddi-release
EXIT_STATUS=`expr $EXIT_STATUS + $?`

exit $EXIT_STATUS
