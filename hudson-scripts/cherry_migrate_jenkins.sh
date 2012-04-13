#!/bin/bash -ex

# Migrate any new cherry picks from the old server to the new one
python ./cm_tools/cherry_migrate.py --old-server android-cm-web.sonyericsson.net --new-server cmweb.sonyericsson.net --source ginger-fuji --target edream6.0-fuji-r2-release
python ./cm_tools/cherry_migrate.py --old-server android-cm-web.sonyericsson.net --new-server cmweb.sonyericsson.net --source ginger-fuji --target edream6.0-fuji-r2-row-release
python ./cm_tools/cherry_migrate.py --old-server android-cm-web.sonyericsson.net --new-server cmweb.sonyericsson.net --source ginger-ste --target edream6.0-riogrande-release
python ./cm_tools/cherry_migrate.py --old-server android-cm-web.sonyericsson.net --new-server cmweb.sonyericsson.net --source edream6.0-riogrande-release --target edream6.0-riogrande-plus-release
