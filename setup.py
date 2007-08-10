#!/usr/bin/env python
"""Distutils setup file"""
import ez_setup
ez_setup.use_setuptools()
from setuptools import setup

# Metadata
PACKAGE_NAME = "Trellis"
PACKAGE_VERSION = "0.5b1"
PACKAGES = ['peak', 'peak.events']
def get_description():
    # Get our long description from the documentation
    f = file('README.txt')
    lines = []
    for line in f:
        if not line.strip():
            break     # skip to first blank line
    for line in f:
        if line.startswith('.. contents::'):
            break     # read to table of contents
        lines.append(line)
    f.close()
    return ''.join(lines)

setup(
    name=PACKAGE_NAME,
    version=PACKAGE_VERSION,
    url = "http://peak.telecommunity.com/DevCenter/Trellis",
    description='A simple "untwisted" approach to event-driven programming',
    long_description = get_description(),
    author="Phillip J. Eby",
    author_email="peak@eby-sarna.com",
    license="PSF or ZPL",
    test_suite = 'test_trellis',
    packages = PACKAGES,
    namespace_packages = PACKAGES,
    install_requires = [
        'SymbolType>=1.0', 'ObjectRoles>=0.6', 'DecoratorTools>=1.5',
    ],
)
