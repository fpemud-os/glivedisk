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
                                         # None means using default profile of the stage3

        self.overlays = None             # list<Overlay>
                                         # defaut is empty list

        self.world_packages = None       # package names in world file, None means no world file should exist
                                         # default is empty list

        self.pkg_use = None              # dict<package-wildcard, use-flag-list>
        self.pkg_masks = None            # list<package-wildcard>
        self.pkg_unmasks = None          # list<package-wildcard>
        self.pkg_accept_keywords = None  # dict<package-wildcard, accept-keyword-list>
        self.pkg_accept_licenses = None  # dict<package-wildcard, accept-license-list>

        self.install_mask = None         # list<install-mask>
        self.pkg_install_mask = None     # dict<package-wildcard, install-mask>

        self.build_opts = None           # BuildOptions
        self.pkg_build_opts = None       # dict<package-wildcard, BuildOptions>

        self.locales = None              # locale list
                                         # None (default value) means build all locales

        self.timezone = None                # timezone
                                            # default is to use UTC

        self.editors = None                 # editor list
                                            # default is to install XX, XX, XX, use nano as the default editor


        # ???
        self.unmerge = None         # list?
        self.rm = None              # list?
        self.vol_id = None


class Overlay:

    def __init__(self):
        self.name = None


class BuildOptions:

    def __init__(self):
        self.common_flags = None
        self.cflags = None
        self.cxxflags = None
        self.fcflags = None
        self.fflags = None
        self.ldflags = None
        self.asflags = None


class HostInfo:

    def __init__(self):
        self.computing_power = None

        self.distfiles_dir = None           # distfiles directory in host system, will be bind mounted in target system
                                            # default: None, means there's no such a directory in host system

        self.packages_dir = None            # packages directory in host system

        self.gentoo_repository_dir = None   # gentoo repository directory in host system

        self.overlays = None                # overlays in host system, will be bind mounted in target system




class HostOverlay:

    def __init__(self):
        self.name = None
        self.dirpath = None


class HostComputingPower:

    def __init__(self):
        self.cpu_core_count = None          # 
        self.memory_size = None
        self.cooling_level = None           # 1-10, less is weaker
