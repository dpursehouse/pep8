#!/usr/bin/env python

import gerrit

g = gerrit.GerritSshConnection("review.sonyericsson.net")
g.run_gerrit_command(["ls-projects"])
