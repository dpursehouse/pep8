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


class TestRepoXmlManifest(unittest.TestCase):
    """ Test that the RepoXmlManifest data class behaves correctly
    """

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


if __name__ == '__main__':
    unittest.main()
