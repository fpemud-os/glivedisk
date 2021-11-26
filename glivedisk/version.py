#!/usr/bin/env python3

# Copyright (c) 2020-2021 Fpemud <fpemud@sina.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

'''Version information and/or git version information
'''

import os

from snakeoil.version import get_git_version as get_ver

__version__= "3.0.20"
_ver = None


def get_git_version(version=__version__):
	"""Return: a string describing our version."""
	# pylint: disable=global-statement
	global _ver
	cwd = os.path.dirname(os.path.abspath(__file__))
	version_info = get_ver(cwd)

	if not version_info:
		s = "extended version info unavailable"
	elif version_info['tag'] == __version__:
		s = 'released %s' % (version_info['date'],)
	else:
		s = ('vcs version %s, date %s' %
			 (version_info['rev'], version_info['date']))

	_ver = 'Catalyst %s\n%s' % (version, s)

	return _ver


def get_version(reset=False):
	'''Returns a saved release version string or the
	generated git release version.
	'''
	# pylint: disable=global-statement
	global __version__, _ver
	if _ver and not reset:
		return _ver
	try: # getting the fixed version
		from .verinfo import version
		_ver = version
		__version__ = version.split('\n')[0].split()[1]
	except ImportError: # get the live version
		version = get_git_version()
	return version



def set_release_version(version, root=None):
	'''Saves the release version along with the
	git log release information

	@param version: string
	@param root: string, optional alternate root path to save to
	'''
	#global __version__
	filename = "verinfo.py"
	if not root:
		path = os.path.join(os.path.dirname(__file__), filename)
	else:
		path = os.path.join(root, filename)
	#__version__ = version
	ver = get_git_version(version)
	with open(path, 'w') as f:
		f.write("version = {0!r}".format(ver))
