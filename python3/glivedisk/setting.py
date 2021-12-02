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


class Target:

    def __init__(self):
        self.arch = None                 # the arch to be built
                                         # default: the same as the host system

        self.variant = None              # the variant to be built

        self.profile = None              # this is the system profile to be used for the live disk
                                         # it is specified as a relative path and must be set to one of the system profiles available at /var/db/repos/gentoo/profiles

        self.repositories = None         # list<Repository>

        self.packages = None             # list<Package>




        self.use = None             # list?
        self.unmerge = None         # list?
        self.rm = None              # list?
        self.vol_id = None

        # FIXME
        self.empty = None
        self.target = None          # FIXME




class Repository:

    def __init__(self):
        self.name = None
        self.host_dir = None


class Package:

    def __init__(self):
        self.name = None
        self.build_opts = None


class BuildOptions:

    def __init__(self):
        self.cflags = None
        self.cxxflags = None
        self.fcflags = None
        self.fflags = None
        self.ldflags = None
        self.asflags = None
        self.common_flags = None




class ChrootInfo:

    def __init__(self):
        self.uid_map = None
        self.gid_map = None




class HostInfo:

    def __init__(self):
        self.host_distfiles_cache_dir = None    # distfiles cache directory in host system, will be bind mounted as "/var/cache/portage/distfiles" in target system
                                                # default: None, means there's no such 



