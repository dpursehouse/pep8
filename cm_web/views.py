from django.template import RequestContext, loader
from django.http import HttpResponse


def index(request):
    """Show the homepage"""
    t = loader.get_template('index.html')
    c = RequestContext(request, {})

    return HttpResponse(t.render(c))
