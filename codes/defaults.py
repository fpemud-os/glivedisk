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


import os

from DeComp.definitions import DECOMPRESSOR_SEARCH_ORDER
from DeComp.definitions import COMPRESSOR_PROGRAM_OPTIONS, XATTRS_OPTIONS
from DeComp.definitions import DECOMPRESSOR_PROGRAM_OPTIONS, LIST_XATTRS_OPTIONS

# Used for the (de)compressor definitions
if os.uname()[0] in  ["Linux", "linux"]:
	TAR = 'linux'
else:
	TAR = 'bsd'


# set our base defaults here to keep them in one location.
BASE_GENTOO_DIR = "/var/gentoo"
REPODIR = BASE_GENTOO_DIR + "/repos"
DISTDIR = BASE_GENTOO_DIR + "/distfiles"
PKGDIR = BASE_GENTOO_DIR + "/packages"
MAINREPO = "gentoo"
PORTDIR = REPODIR + "/" + MAINREPO

confdefaults={
	"archdir": "%(PythonDir)s/arch",
	"comp_prog": COMPRESSOR_PROGRAM_OPTIONS[TAR],
	"compression_mode": 'lbzip2',
	"compressor_arch": None,
	"compressor_options": XATTRS_OPTIONS[TAR],
	"decomp_opt": DECOMPRESSOR_PROGRAM_OPTIONS[TAR],
	"decompressor_search_order": DECOMPRESSOR_SEARCH_ORDER,
	"distdir": DISTDIR[:],
	"hash_function": "crc32",
	'list_xattrs_opt': LIST_XATTRS_OPTIONS[TAR],
	"local_overlay": REPODIR[:] + "/local",
	"port_conf": "/etc/portage",
	"make_conf": "%(port_conf)s/make.conf",
	"options": set(),
	"packagedir": PKGDIR[:],
	"portdir": PORTDIR[:],
	"PythonDir": "./catalyst",
	"repo_basedir": REPODIR[:],
	"repo_name": MAINREPO[:],
	"sharedir": "/usr/share/catalyst",
	"shdir": "/usr/share/catalyst/targets/",
	"source_matching": "strict",
	"storedir": "/var/tmp/catalyst",
	"target_distdir": DISTDIR[:],
	"target_pkgdir": PKGDIR[:],
	"fstype": "normal",
}

PORT_LOGDIR_CLEAN = \
	'find "${PORT_LOGDIR}" -type f ! -name "summary.log*" -mtime +30 -delete'

TARGET_MOUNT_DEFAULTS = {
	"dev": "/dev",
	"devpts": "/dev/pts",
	"distdir": DISTDIR[:],
	"kerncache": "/tmp/kerncache",
	"packagedir": PKGDIR[:],
	"portdir": PORTDIR[:],
	"port_logdir": "/var/log/portage",
	"proc": "/proc",
	"shm": "/dev/shm",
	"run": "/run",
}

SOURCE_MOUNT_DEFAULTS = {
	"dev": "/dev",
	"devpts": "/dev/pts",
	"distdir": DISTDIR[:],
	"portdir": PORTDIR[:],
	"proc": "/proc",
	"shm": "shmfs",
	"run": "tmpfs",
}

# legend:  key: message
option_messages = {
	"autoresume": "Autoresuming support enabled.",
	"clear-autoresume": "Cleaning autoresume flags support enabled.",
	#"compress": "Compression enabled.",
	"kerncache": "Kernel cache support enabled.",
	"pkgcache": "Package cache support enabled.",
	"purge": "Purge support enabled.",
	"seedcache": "Seed cache support enabled.",
	#"tarball": "Tarball creation enabled.",
}
