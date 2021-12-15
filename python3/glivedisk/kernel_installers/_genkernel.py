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
from .. import MY_NAME
from .. import HostComputingPower
from .. import SettingsError
from .. import KernelInstaller
from .. import WorkDirChrooter
from .._util import Util


class GenKernel(KernelInstaller):
    """
    Gentoo has no standard way to build a kernel, this class uses sys-kernel/genkernel to build kernel and initramfs
    """

    def install(self, settings, host_computing_power, work_dir):
        assert HostComputingPower.check_object(host_computing_power)

        self._settings = settings

        self._target = _SettingTarget(self._settings)
        self._hostInfo = _SettingHostInfo(self._settings)

        # determine parallelism parameters
        tj = None
        tl = None
        if host_computing_power.cooling_level <= 1:
            tj = 1
            tl = 1
        else:
            if host_computing_power.memory_size >= 24 * 1024 * 1024 * 1024:       # >=24G
                tj = host_computing_power.cpu_core_count + 2
                tl = host_computing_power.cpu_core_count
            else:
                tj = host_computing_power.cpu_core_count
                tl = max(1, host_computing_power.cpu_core_count - 1)

        # do work
        with _Chrooter(work_dir) as m:
            m.shell_call("", "eselect kernel set 1")

            if self._target.build_opts.ccache:
                opt = "--kernel-cc=ccache"
            else:
                opt = ""
            m.shell_exec("", "genkernel --no-mountboot --makeopts='-j%d -l%d' %s all" % (tj, tl, opt))


class _SettingTarget:

    def __init__(self, settings):
        if "build_opts" in settings:
            self.build_opts = _SettingBuildOptions("build_opts", settings["build_opts"])  # list<build-opts>
            if self.build_opts.ccache is None:
                self.build_opts.ccache = False
        else:
            self.build_opts = _SettingBuildOptions("build_opts", dict())

        if "kern_build_opts" in settings:
            self.kern_build_opts = _SettingBuildOptions("kern_build_opts", settings["kern_build_opts"])  # list<build-opts>
            if self.kern_build_opts.ccache is not None:
                raise SettingsError("invalid value for key \"ccache\" in kern_build_opts")       # ccache is only allowed in global build options
        else:
            self.kern_build_opts = _SettingBuildOptions("kern_build_opts", dict())


class _SettingBuildOptions:

    def __init__(self, name, settings):
        if "common_flags" in settings:
            self.common_flags = list(settings["common_flags"])
        else:
            self.common_flags = []

        if "cflags" in settings:
            self.cflags = list(settings["cflags"])
        else:
            self.cflags = []

        if "cxxflags" in settings:
            self.cxxflags = list(settings["cxxflags"])
        else:
            self.cxxflags = []

        if "fcflags" in settings:
            self.fcflags = list(settings["fcflags"])
        else:
            self.fcflags = []

        if "fflags" in settings:
            self.fflags = list(settings["fflags"])
        else:
            self.fflags = []

        if "ldflags" in settings:
            self.ldflags = list(settings["ldflags"])
        else:
            self.ldflags = []

        if "asflags" in settings:
            self.asflags = list(settings["asflags"])
        else:
            self.asflags = []

        if "ccache" in settings:
            self.ccache = settings["ccache"]
            if not isinstance(self.ccache, bool):
                raise SettingsError("invalid value for key \"ccache\" in %s" % (name))
        else:
            self.ccache = None


class _SettingHostInfo:

    def __init__(self, settings):
        # log directory in host system, will be bind mounted in target system
        if "log_dir" in settings:
            self.log_dir = settings["log_dir"]
        else:
            self.log_dir = os.path.join("/var", "log", MY_NAME)

        # ccache directory in host system
        if "host_ccache_dir" in settings:
            self.ccache_dir = settings["host_ccache_dir"]
        else:
            self.ccache_dir = None


class _Chrooter(WorkDirChrooter):

    def __init__(self, parent):
        self._parent = parent
        super().__init__(self._parent._workDirObj)

    def bind(self):
        super().bind()
        try:
            self._bindMountList = []

            logdir_path = "/var/log/portage"
            logdir_hostpath = os.path.join(self._parent._workDirObj.chroot_dir_path, logdir_path)
            ccachedir_path = "/var/tmp/ccache"
            ccachedir_hostpath = os.path.join(self._parent._workDirObj.chroot_dir_path, ccachedir_path)

            # log_dir mount point
            super()._assertDirStatus(logdir_path)
            Util.shellCall("/bin/mount --bind \"%s\" \"%s\"" % (self._parent._hostInfo.log_dir, logdir_hostpath))
            self._bindMountList.append(logdir_hostpath)

            # ccachedir mount point
            if self._parent._hostInfo.ccache_dir is not None and os.path.exists(ccachedir_hostpath):
                super()._assertDirStatus(ccachedir_path)
                Util.shellCall("/bin/mount --bind \"%s\" \"%s\"" % (self._parent._hostInfo.ccache_dir, ccachedir_hostpath))
                self._bindMountList.append(ccachedir_hostpath)
        except BaseException:
            self.unbind()
            raise

    def unbind(self):
        if hasattr(self, "_bindMountList"):
            for fullfn in reversed(self._bindMountList):
                Util.cmdCall("/bin/umount", "-l", fullfn)
            del self._bindMountList
        super().unbind()
