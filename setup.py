#!/usr/bin/env python

import os
import sys
import email.utils
import distutils.util
try:
    # First try to load most advanced setuptools setup.
    from setuptools import setup
except:
    # Fall back if setuptools is not installed.
    from distutils.core import setup

# package metadata
__package__ = 'glivedisk'
__version__ = '0.0.1'

# check linux platform
platform = distutils.util.get_platform()
if not platform.startswith('linux'):
    sys.stderr.write("This module is not available on %s\n" % platform)
    sys.exit(1)

# Do setup
setup(
	name=__package__,
	version=__version__,
	description="A simple python module for gentoo live disk building.",
    author=email.utils.parseaddr(__author__)[0],
    author_email=email.utils.parseaddr(__author__)[1],
	maintainer=email.utils.parseaddr(__maintainer__)[0],
	maintainer_email=email.utils.parseaddr(__maintainer__)[1],
	url='https://github.com/fpemud-os/glivedisk',
	license='GNU General Public License (GPL)',
	platforms=['Linux'],
	classifiers=[
		'Development Status :: 5 - Production/Stable',
		'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
		'Intended Audience :: Developers',
        'Natural Language :: English',
		'Operating System :: POSIX :: Linux',
		'Programming Language :: Python',
		'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Libraries :: Python Modules',
		],
	packages=[
		__package__,
		'{0}.arch'.format(__package__),
		'{0}.base'.format(__package__),
		'{0}.targets'.format(__package__),
		],
    package_dir={
        __package__: os.path.join('python3', __package__),
    },
)
