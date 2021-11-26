#!/usr/bin/env python

import sys
import distutils.util
try:
    # First try to load most advanced setuptools setup.
    from setuptools import setup
except:
    # Fall back if setuptools is not installed.
    from distutils.core import setup
from glivedisk import __version__, __maintainer__


__package_name__ = 'glidevdisk'

# check linux platform
platform = distutils.util.get_platform()
if not platform.startswith('linux'):
    sys.stderr.write("This module is not available on %s\n" % platform)
    sys.exit(1)

# Do setup
setup(
	name=__package_name__,
	version=__version__,
	description="A simple python module for gentoo live disk building.",
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
		__package_name__,
		'{0}.arch'.format(__package_name__),
		'{0}.base'.format(__package_name__),
		'{0}.targets'.format(__package_name__),
		],
    package_dir={
        __package_name__: os.path.join('python3', __package_name__),
    },
)
