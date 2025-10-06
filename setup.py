#!/usr/bin/env python3

from setuptools import setup

# Test discovery is now handled by pytest in tox.ini


config = {
    "name": "sarstats",
    "version": "0.5",
    "author": "Michele Baldessari",
    "author_email": "michele@acksyn.org",
    "url": "http://acksyn.org",
    "license": "GPLv2",
    "python_requires": ">=3.8",
    "py_modules": [
        "sar_parser",
        "sar_stats",
        "sar_metadata",
        "sar_grapher",
        "sos_report",
    ],
    "scripts": ["sarstats"],
    "install_requires": ["python-dateutil", "matplotlib", "reportlab"],
    "classifiers": [
        "Development Status :: 3 - Alpha",
        "Topic :: Utilities",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
    ],
}

setup(**config)
