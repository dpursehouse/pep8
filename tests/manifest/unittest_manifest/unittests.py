#! /usr/bin/env python

import os
import unittest
from manifest import ManifestParseError, RepoXmlManifest

# Construction for making test possible both with the test framework and in
# a debugger env
if (os.getenv("TESTDIR")):
    _TEST_MANIFEST = os.path.join(os.getenv("TESTDIR"), "manifest_static.xml")
else:
    _TEST_MANIFEST = "manifest_static.xml"
STR_NAME = "name"
STR_PATH = "path"
STR_PROJECT = "project"
STR_REVISION = "revision"
START_NODE = "start"


class TestRepoXmlManifest(unittest.TestCase):
    """ Test that the RepoXmlManifest data class behaves correctly
    """

    def _get_manifest(self, manifest_file):
        """ Creates 'RepoXmlManifest' object based on `manifest_file`"""
        file_path = os.path.join(os.getenv("TESTDIR"), manifest_file)
        with open(file_path) as f:
            file_manifest = RepoXmlManifest(f)
        return file_manifest

    def setUp(self):
        """ Constructor """
        self.manifest_file = _TEST_MANIFEST
        with open(self.manifest_file) as f:
            self.manifest_string = f.read()

    def test_fileobj_parsing(self):
        """ Tests that the parsing in the class gives the same result if a file
            object or an xml string is passed as argument.
        """
        with open(self.manifest_file) as f:
            file_manifest = RepoXmlManifest(f)
        string_manifest = RepoXmlManifest(self.manifest_string)
        self.assertEqual(file_manifest.projects, string_manifest.projects)

    def test_faulty_xml_syntax(self):
        """ Tests that the correct exception is raised when passing faulty xml
            data to the parser
        """
        self.assertRaises(ManifestParseError, RepoXmlManifest, "xxxxxxxxx")

    def test_mutable(self):
        """ Test whether exception is raised while modifying a mutable
            object.
        """
        static_manifest = RepoXmlManifest(self.manifest_string)
        projects = static_manifest.projects.keys()
        self.assertRaises(TypeError, static_manifest.update_revision,
                          projects[0], "test")

    def test_path_revision(self):
        """ Test if 'path' and 'revision' field values are added if not
            present in the manifest file."""
        default_manifest = \
            self._get_manifest("manifest_path_revision_check.xml")
        project_nodes = \
            default_manifest.manifest.getElementsByTagName(STR_PROJECT)
        for node in project_nodes:
            project = node.getAttribute(STR_NAME)
            path = node.getAttribute(STR_PATH)
            if not path:
                path = project
            revision = node.getAttribute(STR_REVISION)
            if not revision:
                revision = default_manifest.default_rev
            self.assertEqual(default_manifest.projects[project][STR_PATH],
                             path)
            self.assertEqual(default_manifest.projects[project][STR_REVISION],
                             revision)

    def test_add_new_project(self):
        """Test if the project details are updated properly while a new
            git is added."""
        new_project = {STR_NAME: "git/trial", STR_PATH: "path/trial"}
        new_category = "category_test"
        default_manifest = \
            self._get_manifest("manifest_add_new_project.xml")
        default_manifest.set_mutable(True)
        default_manifest.add_new_project(new_project, new_category)
        # Check `project` dictionary is updated properly.
        self.assertEqual(new_project[STR_PATH],
                         default_manifest.projects["git/trial"][STR_PATH])
        category = default_manifest.get_category("git/trial")
        self.assertEqual(category, new_category)
        node = default_manifest.categories[category]["path/trial"]
        # Check xml dom object is updated.
        path = node.getAttribute(STR_PATH)
        self.assertEqual(new_project[STR_PATH], path)
        # Check category node exist.
        node = default_manifest.category_info[new_category][START_NODE]
        comment = node.nodeValue.strip()
        self.assertEqual(comment, new_category)

    def test_remove_project(self):
        """ Test if projet details are removed properly."""
        default_manifest = \
            self._get_manifest("manifest_remove_project.xml")
        default_manifest.set_mutable(True)
        project = default_manifest.projects.keys()[0]
        category = default_manifest.get_category(project)
        path = default_manifest.projects[project][STR_PATH]
        node = default_manifest.categories[category][path]
        default_manifest.remove_project(project)
        # Check project is removed from project dictionary.
        self.assertFalse(project in default_manifest.projects)
        # Check category is removed from cateogty info dictionary.
        self.assertFalse(category in default_manifest.categories)
        self.assertRaises(TypeError, node.getAttribute, STR_PATH)
        self.assertFalse(category in default_manifest.category_info)

    def test_update_revision(self):
        """Test the revision is properly updated."""
        new_revision = "trial"
        default_manifest = \
            self._get_manifest("manifest_update_revision.xml")
        default_manifest.set_mutable(True)
        project = default_manifest.projects.keys()[0]
        default_manifest.update_revision(project, new_revision)
        # Check revision is updated in project dictionary
        self.assertEqual(default_manifest.projects[project][STR_REVISION],
                         new_revision)
        category = default_manifest.get_category(project)
        path = default_manifest.projects[project][STR_PATH]
        node = default_manifest.categories[category][path]
        # Check xml dom object's revision field is updated.
        revision = node.getAttribute(STR_REVISION)
        self.assertEqual(revision, new_revision)


if __name__ == '__main__':
    unittest.main()
