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
from .. import Settings, TargetSettings, ComputingPower
from .. import SettingsError
from .. import KernelInstaller
from .. import WorkDirChrooter
from .._util import Util


class GenKernel(KernelInstaller):
    """
    Gentoo has no standard way to build a kernel, this class uses sys-kernel/genkernel to build kernel and initramfs
    """

    def install(self, settings, target_settings, work_dir):
        assert isinstance(settings, Settings)
        assert isinstance(target_settings, TargetSettings)

        self._s = _Settings(settings)
        self._ts = _TargetSettings(target_settings)

        # determine parallelism parameters
        tj = None
        tl = None
        if self._s.host_computing_power.cooling_level <= 1:
            tj = 1
            tl = 1
        else:
            if self._s.host_computing_power.memory_size >= 24 * 1024 * 1024 * 1024:       # >=24G
                tj = self._s.host_computing_power.cpu_core_count + 2
                tl = self._s.host_computing_power.cpu_core_count
            else:
                tj = self._s.host_computing_power.cpu_core_count
                tl = max(1, self._s.host_computing_power.cpu_core_count - 1)

        # FIXME
        self._workDirObj = work_dir

        # do work
        with _Chrooter(self) as m:
            m.shell_call("", "eselect kernel set 1")

            if self._ts.build_opts.ccache:
                opt = "--kernel-cc=/usr/lib/ccache/bin/gcc --utils-cc=/usr/lib/ccache/bin/gcc"
            else:
                opt = ""
            m.shell_exec("", "genkernel --no-mountboot --makeopts='-j%d -l%d' %s all" % (tj, tl, opt))


class _Settings:

    def __init__(self, settings):
        self.prog_name = settings["program_name"]

        self.logdir = settings["logdir"]

        self.verbose = settings["verbose"]

        self.host_computing_power = ComputingPower.new(settings["host_computing_power"]["cpu_core_count"],
                                                       settings["host_computing_power"]["memory_size"],
                                                       settings["host_computing_power"]["cooling_level"])

        self.host_ccache_dir = settings.get("host_ccache_dir", None)


class _TargetSettings:

    def __init__(self, settings):
        if "build_opts" in settings:
            self.build_opts = _TargetSettingsBuildOpts("build_opts", settings["build_opts"])  # list<build-opts>
            if self.build_opts.ccache is None:
                self.build_opts.ccache = False
        else:
            self.build_opts = _TargetSettingsBuildOpts("build_opts", dict())

        if "kern_build_opts" in settings:
            self.kern_build_opts = _TargetSettingsBuildOpts("kern_build_opts", settings["kern_build_opts"])  # list<build-opts>
            if self.kern_build_opts.ccache is not None:
                raise SettingsError("invalid value for key \"ccache\" in kern_build_opts")       # ccache is only allowed in global build options
        else:
            self.kern_build_opts = _TargetSettingsBuildOpts("kern_build_opts", dict())


class _TargetSettingsBuildOpts:

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
            Util.shellCall("/bin/mount --bind \"%s\" \"%s\"" % (self._parent._s.logdir, logdir_hostpath))
            self._bindMountList.append(logdir_hostpath)

            # ccachedir mount point
            if self._parent._s.host_ccache_dir is not None and os.path.exists(ccachedir_hostpath):
                super()._assertDirStatus(ccachedir_path)
                Util.shellCall("/bin/mount --bind \"%s\" \"%s\"" % (self._parent._s.host_ccache_dir, ccachedir_hostpath))
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
