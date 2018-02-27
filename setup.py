#!/usr/bin/python

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

from setuptools.command.test import test


def discover_and_run_tests():
    import os
    import sys
    import unittest

    # get setup.py directory
    setup_file = sys.modules['__main__'].__file__
    setup_dir = os.path.abspath(os.path.dirname(setup_file))

    # use the default shared TestLoader instance
    test_loader = unittest.defaultTestLoader

    # use the basic test runner that outputs to sys.stderr
    test_runner = unittest.TextTestRunner()

    # automatically discover all tests
    if sys.version_info < (2, 7):
        raise "Must use python 2.7 or later"
    test_suite = test_loader.discover(setup_dir)

    # run the test suite
    test_runner.run(test_suite)


class DiscoverTest(test):
    def finalize_options(self):
        test.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        discover_and_run_tests()


config = {
    'name': 'sarstats',
    'version': '0.4',
    'author': 'Michele Baldessari',
    'author_email': 'michele@acksyn.org',
    'url': 'http://acksyn.org',
    'license': 'GPLv2',
    'cmdclass': {'test': DiscoverTest},
    'py_modules': ['sar_parser', 'sar_stats', 'sar_metadata',
                   'sar_grapher', 'sos_report'],
    'scripts': ['sarstats'],
    'install_requires': ['dateutils', 'matplotlib', 'reportlab' ],
    'classifiers': [
        "Development Status :: 3 - Alpha",
        "Topic :: Utilities",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
        "Programming Language :: Python",
    ],
}

setup(**config)
