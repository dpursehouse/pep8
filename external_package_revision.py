import urllib
from xml.dom import minidom
from xml.parsers.expat import ExpatError


class XmlParseError(Exception):
    """
       XmlParseError exceptions indicate that the xml file couldn't be parsed.
       This can happen if the xml file doesn't exist or its format is incorrect
       or whatever reasons.
    """

    def __init__(self, problem):
        self.problem = problem

    def __str__(self):
        return 'Failed to parse xml:%s' % self.problem


def get_external_package_info(xml_file):
    """
        Parse xml file of external packages or decoupled packages,
        Return a dictionary of package names and revisions.
    """

    pkg_revision_map = {}
    try:
        xml = minidom.parse(urllib.urlopen(xml_file))
    except ExpatError, e:
        raise XmlParseError('[FormatError] %s' % e)
    package = ""
    revision = ""
    root = xml.documentElement
    for node in root.childNodes:
        if node.nodeType == node.ELEMENT_NODE:
            if node.nodeName == 'package-group':
                if node.hasAttribute('revision'):
                    revision = node.getAttribute('revision')
                else:
                    raise XmlParseError('Missing "revision" attribute in '
                                        'package-group.')
                for sub_node in node.childNodes:
                    if (sub_node.nodeType == node.ELEMENT_NODE and
                        sub_node.nodeName == 'package'):
                        if sub_node.hasAttribute('name'):
                            package = sub_node.getAttribute('name')
                        else:
                            raise XmlParseError('Missing "name" attribute for '
                                                'a package in package-group.')

                        if sub_node.hasAttribute('revision'):
                            local_rev = sub_node.getAttribute('revision')
                        else:
                            local_rev = revision

                        if package in pkg_revision_map:
                            if local_rev != pkg_revision_map[package]:
                                raise XmlParseError('Duplicate package "%s" '
                                                    'with different revisions.'
                                                    % package)
                        else:
                            pkg_revision_map[package] = local_rev
            elif node.nodeName == 'package':
                if node.hasAttribute('name'):
                    package = node.getAttribute('name')
                else:
                    raise XmlParseError('Missing "name" attribute in package.')
                if node.hasAttribute('revision'):
                    local_rev = node.getAttribute('revision')
                    if package in pkg_revision_map:
                        if local_rev != pkg_revision_map[package]:
                            raise XmlParseError('Duplicate package "%s" '
                                                'with different revisions.'
                                                % package)
                    else:
                        pkg_revision_map[package] = local_rev
                else:
                    raise XmlParseError('Missing "revision" attribute in '
                                        'package, %s.' % package)
    return pkg_revision_map
