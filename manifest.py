import re
import xml.dom
import xml.dom.minidom
from xml.parsers.expat import ExpatError

import git
from mutable import *

STR_NAME = "name"
STR_PATH = "path"
STR_PROJECT = "project"
STR_REVISION = "revision"


class ManifestParseError(Exception):
    """Exception class for manifest parse errors."""


class ManifestError(Exception):
    """Exception class for errors in manifest functionalities."""


class RepoXmlManifest(Immutable):
    """Returns an object with the info from a repo manifest.

    Takes the string containing manifest data. The object returned contains:

    projects: A dict with format name:{name: "", path: "", revision: ""}.
              This dict always contains the keys "path", "revision" and "name".
    default_rev: the default revision as specified in the manifest.

    """
    def __init__(self, manifestdata):
        """Initialization method.

        Arguments:
        manifestdata: string containing manifest data or a file object.

        """
        super(RepoXmlManifest, self).__init__()
        self._intialize_manifest(manifestdata)

    @make_mutable
    def _intialize_manifest(self, manifestdata):
        """Initialize instance attributes and parse manifest."""
        # Default revision
        self.default_rev = ""
        # Project dictionary.
        # Format - name:{name: "", path: "", revision: ""}
        self.projects = {}
        # Child nodes w.r.t git name.
        # Format - name: {src: "", dst: ""}
        self.child_nodes = {}
        # Categories.
        # Format - category:{node: "", "path": "node", "path": "node" ... }
        self.categories = {}
        self.manifestdata = manifestdata

        self._parse_manifest()

    def _parse_manifest(self):
        """ Parses manifest file.

        Parses the manifest file and stores the information in:
        projects: 'project' node data
        categories: categories mentioned in manifest file.
            Comment node that starts with either of the following is
            considered as start of category
            "Start of"/"PLD:"/"ASW:"/"Uncategorized".
        child_nodes: Details of child nodes(if any).

        Exception raised: ManifestParseError
        Exception cases:
            - Missing revision field in 'default' node.
            - Multiple 'default' xml nodes.

        """
        # Check whether 'manifestdata' is a file object or not.
        if hasattr(self.manifestdata, "read") and \
               callable(self.manifestdata.read):
            self.manifestdata = self.manifestdata.read()
        # Removing spaces and newlines from the input string as those
        # will be added while writing the xml file.
        self.manifestdata = re.sub("> *\n", ">", self.manifestdata)
        self.manifestdata = re.sub("  +<", "<", self.manifestdata)

        try:
            self.manifest = xml.dom.minidom.parseString(self.manifestdata)
        except ExpatError, e:
            raise ManifestParseError(e)
        default = self.manifest.getElementsByTagName("default")
        if default and len(default) == 1:
            if default[0].hasAttribute(STR_REVISION):
                self.default_rev = default[0].attributes[STR_REVISION].nodeValue
            else:
                raise ManifestParseError("Missing revision attribute "
                                         "on the default tag.")
        elif len(default) > 1:
            raise ManifestParseError("Multiple default tags not allowed.")
        else:
            raise ManifestParseError("Missing default tag.")
        # Pattern to be considered as start of category.
        start_pattern = re.compile(r"Start of|PLD:|ASW:|Uncategorized")
        # Pattern to be considered as end of category.
        end_pattern = re.compile(r"End of|End")
        category = "Uncategorized"
        self.categories[category] = {}

        for node in self.manifest.childNodes[0].childNodes:
            if node.nodeName == "remote" or node.nodeName == "default":
                continue
            elif node.nodeType is xml.dom.Node.COMMENT_NODE:
                # Comment node: can be normal comment or category (start/end).
                comment = node.nodeValue.strip()
                # Check for start of category.
                if start_pattern.match(comment):
                    category = comment
                    # Add the new category to the list (if not in list).
                    if category not in self.categories:
                        # Initialize dict and add the node value.
                        self.categories[category] = {"node": node}
                # Check for end of category. End of category is not mandatory
                # to be present in manifest, as start of new category is taken
                # as end of category for the previous.
                elif end_pattern.match(comment):
                    category = "Uncategorized"
            elif node.nodeType is xml.dom.Node.ELEMENT_NODE and \
                    node.nodeName == STR_PROJECT:
                project = node.attributes[STR_NAME].value
                self.projects[project] = {}
                project_dict = self.projects[project]
                if node.hasChildNodes():
                    childnode = node.getElementsByTagName("copyfile")
                    self.child_nodes[project] = {}
                    self.child_nodes[project].update(
                        self.parse_node(childnode[0]))
                # Save the node elements as a dictionary.
                project_dict.update(self.parse_node(node))
                #Add path and revision if not present.
                if STR_PATH not in project_dict:
                    project_dict[STR_PATH] = project
                if STR_REVISION not in project_dict:
                    project_dict[STR_REVISION] = self.default_rev
                self.categories[category][project_dict[STR_PATH]] = node

    @require_mutable
    def add_new_project(self, proj_dict, category=None, child_dict=None):
        """Add the specified project to the project list.

        proj_dict: dictionary object that contains the set of
                   attributes for the specified project.
        category: Name of category. If no category specified, the node
                  is added at the end of the xml file.
        child_dict: dictionary for child node.

        Exception raised: ManifestError
        Exception cases:
            - 'name' already in manifest file.
            - 'name' not in input dictionary
        Exception raised: TypeError
        Exception case:
            - 'read-only' manifest file

        """
        ref_proj_dict = proj_dict.copy()
        try:
            project = proj_dict[STR_NAME]
        except:
            raise ManifestError("'name' not in project dictionary")
        # Check whether 'project' already exists
        if project in self.projects:
            raise ManifestError("Project %s is already in manifest." % project)
        if STR_PATH not in proj_dict:
            proj_dict[STR_PATH] = project
        if STR_REVISION not in proj_dict:
            proj_dict[STR_REVISION] = self.default_rev

        git_path = proj_dict[STR_PATH]
        ref_node = None
        if (not category) or (category == "Uncategorized"):
            # If category is 'None', or categroy mentioned is 'Uncategorized'
            # add the git to end of xml.
            ref_node = self.manifest.childNodes[0].lastChild
            category = "Uncategorized"
        elif category not in self.categories:
            # If category not present add category comment node.
            doc = xml.dom.minidom.Document()
            comment = doc.createComment(category)
            self.manifest.childNodes[0].appendChild(comment)
            newline = doc.createTextNode("\n")
            self.manifest.childNodes[0].appendChild(newline)
            # Initialize dict and add the node value.
            self.categories[category] = {"node": comment}
            ref_node = newline
        else:
            # Find the location for the new git w.r.t 'path' in category.
            pathlist = filter(lambda a: git_path < a,
                              self.categories[category])
            if len(pathlist):
                pathlist.sort()
                ref_node = self.categories[category][pathlist[0]]
            else:
                # Add git to the end of the category.
                pathlist = self.categories[category].keys()
                pathlist.sort()
                pathlist.reverse()
                ref_node = self.categories[category][pathlist[0]].nextSibling
        # Create the node.
        node = self.create_element("project", ref_proj_dict)
        if child_dict:
            child = self.create_element("copyfile", child_dict)
            node.appendChild(child)
        # Add new node to xml node. If 'ref_node' in None, then the
        # project will be added to the end.
        try:
            self.manifest.childNodes[0].insertBefore(node, ref_node)
        except ValueError, err:
            raise ManifestError("Error adding the project: %s" % err)
        # Add the project to the 'projects' list.
        self.projects[project] = proj_dict
        if child_dict:
            self.child_nodes[project] = child_dict
        self.categories[category][git_path] = node

    def create_element(self, node, attribute):
        """ Create an xml node."""
        doc = xml.dom.minidom.Document()
        temp = doc.createElement(node)
        for (key, value) in attribute.iteritems():
            temp.setAttribute(key, value)
        return temp

    def get_branched_out_gits(self):
        """ Returns all the git names whose revision is a branch."""
        return filter(lambda a:
                      not git.is_sha1_or_tag(self.projects[a][STR_REVISION]),
                      self.projects)

    def get_category(self, project):
        """ Returns the category value where the 'project' belongs to.

        Return:
            If the 'project' exists in any category list, returns category name
            else, returns empty string.

        """
        if project in self.projects:
            path = self.projects[project][STR_PATH]
            category = filter(lambda a: path in self.categories[a],
                              self.categories)
            return category[0]
        else:
            return ""

    def get_static_gits(self):
        """ Returns all the git names whose revision is a sha1."""
        return filter(lambda a: git.is_sha1(self.projects[a][STR_REVISION]),
                      self.projects)

    def parse_node(self, src_node):
        """Parses the xml node

        Creates a dictionary from the xml node attributes and returns
        the dictionary variable.

        """
        dst_dict = {}
        if src_node:
            for index in range(src_node.attributes.length):
                attr = src_node.attributes.item(index)
                dst_dict[attr.name] = attr.value
        return dst_dict

    def write_to_xml(self, output_file):
        """Writes the content of manifest object to xml.

        Writes the content of the manifest object to the specified
        output file in XML format.

        Exception raised: ManifestError
        Exception case: Not able to write to output xml file.
        Exception raised: IOError
        Exception case: Error while opening/closing output xml file.

        """
        with open(output_file, "w") as fd:
            try:
                out_string = self.manifest.toprettyxml(indent="  ",
                                                       encoding="UTF-8")
                fd.write(re.sub("  \n", "", out_string))
            except Exception, err:
                raise ManifestError("Error writing to output "
                                    "file %s: %s." % (output_file, err))

    @require_mutable
    def remove_project(self, project):
        """Removes the specified `project` from the projects list.

        Exception raised: ManifestError
        Exception cases:
            - 'project' not in the manifest file.
        Exception raised: TypeError
        Exception case:
            - 'read-only' manifest file

        """
        if not project in self.projects:
            raise ManifestError("Project %s is not in the manifest." % project)
        node = ""
        # Search in each category to find the node.
        category = self.get_category(project)
        path = self.projects[project][STR_PATH]
        node = self.categories[category][path]
        try:
            self.manifest.childNodes[0].removeChild(node)
        except ValueError, err:
            raise ManifestError("Error removing the node: %s" % err)
        node.unlink()
        del self.categories[category][path]
        del self.projects[project]
        # If all the projects are removed from this category
        # remove the category itself. One element will be there
        # with 'node' value. So checking for > 1.
        if (not len(self.categories[category]) > 1) and \
               (category != "Uncategorized"):
            node = self.categories[category]["node"]
            prev_node = node.previousSibling
            self.manifest.childNodes[0].removeChild(node)
            del self.categories[category]
            node.unlink()
            # Remove the newline before the category comment line.
            if prev_node.nodeType is xml.dom.Node.TEXT_NODE and \
               prev_node.nodeValue == "\n":
                self.manifest.childNodes[0].removeChild(prev_node)
                prev_node.unlink()

    @require_mutable
    def update_revision(self, project, revision):
        """Updates the revision part of the given project.

        Exception raised: ManifestError
        Exception cases:
            - 'project' not in the manifest file.
        Exception raised: TypeError
        Exception case:
            - 'read-only' manifest file

        """
        if project in self.projects:
            category = self.get_category(project)
            path = self.projects[project][STR_PATH]
            node = self.categories[category][path]
            node.setAttribute(STR_REVISION, revision)
            self.projects[project][STR_REVISION] = revision
        else:
            raise ManifestError("Cannot update revision. Project %s "
                                "not found." % project)
