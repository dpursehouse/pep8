import os
import sys

from django.conf import settings
from django.http import HttpResponse
from django.template import RequestContext, loader

# From cm_tools
import include_exclude_matcher
import manifestbranches

from cm_web.matrix.models import SystemBranch


def index(request):
    """Show all system branches to user to select"""
    sys_branches = SystemBranch.objects.all().order_by('name')
    t = loader.get_template('matrix/index.html')
    c = RequestContext(request, {
        'sys_branches': sys_branches,
    })

    return HttpResponse(t.render(c))


def result(request):
    """Show matrix as result"""
    sys_branches = []
    for sys_branch in request.POST.values():
        sys_branches += manifestbranches.get_manifests(
                        sys_branch, settings.PATH_MANIFEST)

    pattern_matcher = include_exclude_matcher.IncludeExcludeMatcher(
                      [r"^"], None)
    data = manifestbranches.get_branches_html(
           sys_branches, pattern_matcher.match)

    return HttpResponse(data)
