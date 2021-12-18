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
import re
import multiprocessing
from ._errors import SettingsError


MY_NAME = "gstage4"


class Settings(dict):

    def __init__(self):
        self.program_name = None

        self.log_dir = None

        self.verbose = False

        self.host_computing_power = None

        # distfiles directory in host system, will be bind mounted in target system
        self.host_distfiles_dir = None

        # packages directory in host system
        self.host_packages_dir = None

        # ccache directory in host system
        self.host_ccache_dir = None

    @classmethod
    def check_object(cls, obj, raise_exception=None):
        assert raise_exception is not None

        if not isinstance(obj, cls):
            if raise_exception:
                raise SettingsError("invalid object type")
            else:
                return False

        if not isinstance(obj.program_name, str):
            if raise_exception:
                raise SettingsError("invalid value for key \"program_name\"")
            else:
                return False

        if obj.log_dir is not None and not isinstance(obj.log_dir, str):
            if raise_exception:
                raise SettingsError("invalid value for key \"log_dir\"")
            else:
                return False

        if not isinstance(obj.verbose, bool):
            if raise_exception:
                raise SettingsError("invalid value for key \"verbose\"")
            else:
                return False

        if obj.host_computing_power is None or not ComputingPower.check_object(obj.host_computing_power, raise_exception=raise_exception):
            if raise_exception:
                raise SettingsError("invalid value for key \"host_computing_power\"")
            else:
                return False

        if obj.host_distfiles_dir is not None and not os.path.isdir(obj.host_distfiles_dir):
            if raise_exception:
                raise SettingsError("invalid value for key \"host_distfiles_dir\"")
            else:
                return False

        if obj.host_packages_dir is not None and not os.path.isdir(obj.host_packages_dir):
            if raise_exception:
                raise SettingsError("invalid value for key \"host_packages_dir\"")
            else:
                return False

        if obj.host_ccache_dir is not None and not os.path.isdir(obj.host_ccache_dir):
            if raise_exception:
                raise SettingsError("invalid value for key \"host_ccache_dir\"")
            else:
                return False

        return True


class TargetSettings(dict):

    def __init__(self):
        self.profile = None

        self.install_list = []

        self.world_set = []

        self.pkg_use = dict()              # dict<package-wildcard, use-flag-list>
        self.pkg_mask = []                 # list<package-wildcard>
        self.pkg_unmask = []               # list<package-wildcard>
        self.pkg_accept_keywords = dict()  # dict<package-wildcard, accept-keyword-list>
        self.pkg_license = dict()          # dict<package-wildcard, license-list>

        self.install_mask = []             # list<install-mask>
        self.pkg_install_mask = dict()     # dict<package-wildcard, install-mask>

        self.build_opts = TargetSettingsBuildOpts("build_opts")
        self.build_opts.ccache = False

        self.kern_build_opts = TargetSettingsBuildOpts("kern_build_opts")

        self.pkg_build_opts = dict()

        self.degentoo = False

    @classmethod
    def check_object(cls, obj, raise_exception=None):
        assert raise_exception is not None

        if not isinstance(obj, cls):
            if raise_exception:
                raise SettingsError("invalid object type")
            else:
                return False

        if obj.install_list is None or not isinstance(obj.install_list, list):
            if raise_exception:
                raise SettingsError("invalid value for \"install_list\"")
            else:
                return False

        if obj.world_set is None or not isinstance(obj.world_set, list):
            if raise_exception:
                raise SettingsError("invalid value for \"world_set\"")
            else:
                return False
        if len(set(obj.world_set) & set(obj.install_list)) > 0:
            if raise_exception:
                raise SettingsError("same element found in install_list and world_set")
            else:
                return False

        if obj.pkg_use is None or not isinstance(obj.pkg_use, dict):
            if raise_exception:
                raise SettingsError("invalid value for \"pkg_use\"")
            else:
                return False
        if obj.pkg_mask is None or not isinstance(obj.pkg_mask, list):
            if raise_exception:
                raise SettingsError("invalid value for \"pkg_mask\"")
            else:
                return False
        if obj.pkg_unmask is None or not isinstance(obj.pkg_unmask, list):
            if raise_exception:
                raise SettingsError("invalid value for \"pkg_unmask\"")
            else:
                return False
        if obj.pkg_accept_keywords is None or not isinstance(obj.pkg_accept_keywords, dict):
            if raise_exception:
                raise SettingsError("invalid value for \"pkg_accept_keywords\"")
            else:
                return False
        if obj.pkg_license is None or not isinstance(obj.pkg_license, dict):
            if raise_exception:
                raise SettingsError("invalid value for \"pkg_license\"")
            else:
                return False

        if obj.install_mask is None or not isinstance(obj.install_mask, list):
            if raise_exception:
                raise SettingsError("invalid value for \"install_mask\"")
            else:
                return False
        if obj.pkg_install_mask is None or not isinstance(obj.pkg_install_mask, dict):
            if raise_exception:
                raise SettingsError("invalid value for \"pkg_install_mask\"")
            else:
                return False

        if obj.build_opts is None or not TargetSettingsBuildOpts.check_object(obj.build_opts, raise_exception=raise_exception):
            if raise_exception:
                raise SettingsError("invalid value for \"build_opts\"")
            else:
                return False
        if obj.build_opts.ccache is None:
            if raise_exception:
                raise SettingsError("invalid value for key \"ccache\" in build_opts")
            else:
                return False

        if obj.kern_build_opts is None or not TargetSettingsBuildOpts.check_object(obj.kern_build_opts, raise_exception=raise_exception):
            if raise_exception:
                raise SettingsError("invalid value for \"kern_build_opts\"")
            else:
                return False
        if obj.kern_build_opts.ccache is not None:
            if raise_exception:
                raise SettingsError("invalid value for key \"ccache\" in kern_build_opts")  # ccache is only allowed in global build options
            else:
                return False

        if obj.pkg_build_opts is None or not isinstance(obj.pkg_build_opts, dict):
            if raise_exception:
                raise SettingsError("invalid value for \"pkg_build_opts\"")
            else:
                return False
        for k, v in obj.pkg_build_opts.items():
            if v is None or not TargetSettingsBuildOpts.check_object(v, raise_exception=raise_exception):
                if raise_exception:
                    raise SettingsError("invalid value for \"build_opts\" of package %s" % (k))
                else:
                    return False
            if v.ccache is not None:
                if raise_exception:
                    raise SettingsError("invalid value for key \"ccache\" in build_opts of package" % (k))  # ccache is only allowed in global build options
                else:
                    return False

        if obj.degentoo is None or not isinstance(obj.degentoo, bool):
            if raise_exception:
                raise SettingsError("invalid value for key \"degentoo\"")
            else:
                return False

        return True


class TargetSettingsBuildOpts:

    def __init__(self, name):
        self.name = name

        self.common_flags = []
        self.cflags = []
        self.cxxflags = []
        self.fcflags = []
        self.fflags = []
        self.ldflags = []
        self.asflags = []

        self.ccache = None

    @classmethod
    def check_object(cls, obj, raise_exception=None):
        assert raise_exception is not None

        if not isinstance(obj, cls):
            if raise_exception:
                raise SettingsError("invalid object type")
            else:
                return False

        if obj.common_flags is None or not isinstance(obj.common_flags, list):
            if raise_exception:
                raise SettingsError("invalid value for \"common_flags\" of %s" % (obj.name))
            else:
                return False

        if obj.cflags is None or not isinstance(obj.cflags, list):
            if raise_exception:
                raise SettingsError("invalid value for \"cflags\" of %s" % (obj.name))
            else:
                return False

        if obj.cxxflags is None or not isinstance(obj.cxxflags, list):
            if raise_exception:
                raise SettingsError("invalid value for \"cxxflags\" of %s" % (obj.name))
            else:
                return False

        if obj.fcflags is None or not isinstance(obj.fcflags, list):
            if raise_exception:
                raise SettingsError("invalid value for \"fcflags\" of %s" % (obj.name))
            else:
                return False

        if obj.fflags is None or not isinstance(obj.fflags, list):
            if raise_exception:
                raise SettingsError("invalid value for \"fflags\" of %s" % (obj.name))
            else:
                return False

        if obj.ldflags is None or not isinstance(obj.ldflags, list):
            if raise_exception:
                raise SettingsError("invalid value for \"ldflags\" of %s" % (obj.name))
            else:
                return False

        if obj.asflags is None or not isinstance(obj.asflags, list):
            if raise_exception:
                raise SettingsError("invalid value for \"asflags\" of %s" % (obj.name))
            else:
                return False

        if obj.asflags is not None and not isinstance(obj.ccache, bool):
            if raise_exception:
                raise SettingsError("invalid value for \"ccache\" of %s" % (obj.name))
            else:
                return False

        return True


class ComputingPower:

    def __init__(self):
        self.cpu_core_count = None
        self.memory_size = None             # in byte
        self.cooling_level = None           # 1-10, less is weaker

    @staticmethod
    def new(cpu_core_count, memory_size, cooling_level):
        assert cpu_core_count > 0
        assert memory_size > 0
        assert 1 <= cooling_level <= 10

        ret = ComputingPower()
        ret.cpu_core_count = cpu_core_count
        ret.memory_size = memory_size
        ret.cooling_level = cooling_level
        return ret

    @staticmethod
    def auto_detect():
        ret = ComputingPower()

        # cpu_core_count
        ret.cpu_core_count = multiprocessing.cpu_count()

        # memory_size
        with open("/proc/meminfo", "r") as f:
            # Since the memory size shown in /proc/meminfo is always a
            # little less than the real size because various sort of
            # reservation, so we do a "+1GB"
            m = re.search("^MemTotal:\\s+(\\d+)", f.read())
            ret.memory_size = (int(m.group(1)) // 1024 // 1024 + 1) * 1024 * 1024

        # cooling_level
        ret.cooling_level = 5

        return ret

    @classmethod
    def check_object(cls, obj, raise_exception=None):
        assert raise_exception is not None

        if not isinstance(obj, cls):
            if raise_exception:
                raise SettingsError("invalid object type")
            else:
                return False

        if obj.cpu_core_count <= 0:
            if raise_exception:
                raise SettingsError("invalid value of \"cpu_core_count\"")
            else:
                return False

        if obj.memory_size <= 0:
            if raise_exception:
                raise SettingsError("invalid value of \"memory_size\"")
            else:
                return False

        if not (1 <= obj.cooling_level <= 10):
            if raise_exception:
                raise SettingsError("invalid value of \"cooling_level\"")
            else:
                return False

        return True
