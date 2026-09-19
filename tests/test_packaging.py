"""What the package page tells a stranger.

The 0.1.1 release went to the package index with no project URLs at all, so
the page carried no route to the source and no route to report a defect, on a
tool that reports regulatory dates. These tests keep that metadata present and
keep the version in one agreed state, because the release workflow reads the
version from the module and the build reads it from ``pyproject.toml``.
"""

import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from on_notice import __version__  # noqa: E402

PYPROJECT = open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8").read()


class TestPackageMetadata(unittest.TestCase):
    def test_pyproject_and_the_module_agree_on_the_version(self):
        declared = re.search(r'(?m)^version = "([^"]+)"', PYPROJECT)
        self.assertIsNotNone(declared, "pyproject.toml declares no version")
        self.assertEqual(declared.group(1), __version__)

    def test_the_package_page_has_a_route_to_the_source(self):
        self.assertIn("https://github.com/Waiga/on-notice", PYPROJECT)

    def test_the_package_page_has_a_route_to_report_a_defect(self):
        self.assertIn("https://github.com/Waiga/on-notice/issues", PYPROJECT)

    def test_those_routes_are_declared_where_the_index_reads_them(self):
        self.assertIn("[project.urls]", PYPROJECT)
        urls = PYPROJECT.split("[project.urls]", 1)[1].split("[", 1)[0]
        self.assertIn("Homepage", urls)
        self.assertIn("Issues", urls)


if __name__ == "__main__":
    unittest.main()
