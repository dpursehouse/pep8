#!/usr/bin/env python

import os
import sys
from xml.parsers.expat import ExpatError

from branch_policies import BranchPolicies, BranchPolicyError


try:
    BranchPolicies(sys.argv[1])
    sys.exit(0)
except (BranchPolicyError, ExpatError, IOError), err:
    print >>sys.stderr, "Error reading %s: %s: %s" % (sys.argv[1],
                                                      err.__class__.__name__,
                                                      err)
    sys.exit(1)
