import os
import sys

PATH_CM_WEB_PARENT = os.path.dirname(os.path.dirname
                       (os.path.dirname(os.path.abspath(__file__))))
if PATH_CM_WEB_PARENT not in sys.path:
    sys.path.insert(0, PATH_CM_WEB_PARENT)

os.environ['DJANGO_SETTINGS_MODULE'] = 'cm_web.settings'

import django.core.handlers.wsgi
application = django.core.handlers.wsgi.WSGIHandler()
