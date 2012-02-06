#!/usr/bin/env python

import datetime
import logging
import os
import sys
import time


PATH_CM_WEB_PARENT = os.path.dirname(os.path.dirname
                         (os.path.dirname(os.path.abspath(__file__))))
if PATH_CM_WEB_PARENT not in sys.path:
    sys.path.insert(0, PATH_CM_WEB_PARENT)

os.environ['DJANGO_SETTINGS_MODULE'] = 'cm_web.settings'

from django.conf import settings

# From cm_tools
import processes


# How many seconds to sleep after a sync from git/gerrit server.
SLEEP_TIME = 600

LOG_FILENAME = "cm_web_backend_%s.log" % datetime.datetime.now()
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s [%(levelname)s] %(message)s',
                    filename=LOG_FILENAME,
                    filemode='w')

while(1):
    logging.debug('Fetch start.')
    try:
        code, out, err = processes.run_cmd("git", "fetch",
                                           path=settings.PATH_MANIFEST_GIT)
        logging.debug(out)
    except Exception as error:
        logging.error(error)
    logging.debug('Fetch done.')
    time.sleep(SLEEP_TIME)
