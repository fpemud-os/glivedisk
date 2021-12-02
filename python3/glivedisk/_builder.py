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
import enum
import robust_layer.simple_fops
from ._util import Util
from ._support import Chroot
from ._errors import WorkDirVerifyError
from . import settings


class Builder:
    """
    This class does all of the chroot setup, copying of files, etc. It is
    the driver class for pretty much everything that glivedisk does.
    """

    @staticmethod
    def new(seed_stage_stream, target, work_dir=None, host_info=None, chroot_info=None):
        # check seed_stage_stream
        assert hasattr(seed_stage_stream, "extractall")

        # check target
        assert isinstance(target, settings.Target)

        # check work_dir
        if work_dir is None:
            work_dir = "/var/tmp/glivedisk"
        if os.path.exists(work_dir):
            assert os.path.isdir(work_dir)
        else:
            assert os.path.isdir(os.path.dirname(work_dir))

        # check host_info
        if host_info is not None:
            assert isinstance(host_info, settings.HostInfo)
        
        # check chroot_info
        if chroot_info is None:
            chroot_info = settings.ChrootInfo()
        assert isinstance(chroot_info, settings.ChrootInfo)

        # create object
        ret = Builder()
        ret._tf = seed_stage_stream
        ret._workDir = work_dir
        ret._target = target
        ret._hostInfo = host_info
        ret._chroot = Chroot(chroot_info)
        ret._progress = BuildProgress.INIT

        # initialize work_dir
        if not os.path.exists(ret._workDir):
            os.mkdir(ret._workDir, mode=0o0700)
        else:
            s = os.stat(ret._workDir)
            if s.st_mode != 0o0700:
                raise WorkDirVerifyError("invalid mode for \"%s\"" % (ret._workDir))
            if s.st_uid != os.getuid():
                raise WorkDirVerifyError("invalid uid for \"%s\"" % (ret._workDir))
            if s.st_gid != os.getgid():
                raise WorkDirVerifyError("invalid gid for \"%s\"" % (ret._workDir))
            robust_layer.simple_fops.truncate_dir(ret._workDir)

        # save parameters
        Util.saveObj(os.path.join(ret._workDir, "target.json"), target)
        Util.saveObj(os.path.join(ret._workDir, "host_info.json", host_info))
        Util.saveObj(os.path.join(ret._workDir, "chroot_info.json", chroot_info))
        Util.saveEnum(os.path.join(ret._workDir, "progress", ret._progress))

        return ret

    @staticmethod
    def revoke(work_dir):
        ret = Builder()
        ret._tf = None

        if not os.path.isdir(work_dir):
            raise WorkDirVerifyError("invalid directory \"%s\"" % (work_dir))
        ret._workDir = work_dir

        fullfn = os.path.join(ret._workDir, "target.json")
        try:
            ret._target = Util.loadObj(fullfn)
        except:
            raise WorkDirVerifyError("invalid parameter file \"%s\"" % (fullfn))

        fullfn = os.path.join(ret._workDir, "host_info.json")
        try:
            ret._hostInfo = Util.loadObj(fullfn)
        except:
            raise WorkDirVerifyError("invalid parameter file \"%s\"" % (fullfn))

        fullfn = os.path.join(ret._workDir, "chroot_info.json")
        try:
            ret._chroot = Chroot(Util.loadObj(fullfn))
        except:
            raise WorkDirVerifyError("invalid parameter file \"%s\"" % (fullfn))

        fullfn = os.path.join(ret._workDir, "progress")
        try:
            ret._progress = Util.loadEnum(fullfn, BuildProgress)
        except:
            raise WorkDirVerifyError("invalid parameter file \"%s\"" % (fullfn))

        return ret

    def __init__(self):
        self._tf = None
        self._workDir = None
        self._target = None
        self._hostInfo = None
        self._chroot = None
        self._progress = None

    def get_progress(self):
        return self._progress

    def get_work_dir(self):
        return self._workDir

    def support_rollback(self):
        return False        # FIXME: support rollback through bcachefs non-priviledged snapshot

    def rollback_to(self, step):
        assert isinstance(step, BuildProgress) and step < self._progress
        assert False        # FIXME: support rollback through bcachefs non-priviledged snapshot

    def dispose(self):
        self._progress = None
        self._chroot = None
        self._hostInfo = None
        self._target = None
        if self._workDir is not None:
            robust_layer.simple_fops.rm(self._workDir)
            self._workDir = None
        self._tf = None

    def action_unpack(self):
        pass

    def action_init_repositories(self):
        pass

    def action_init_confdir(self):
        pass

    def action_update_system(self):
        pass

    def action_install_packages(self):
        pass

    def action_gen_kernel_and_initramfs(self):
        pass

    def action_solder_system(self):
        pass


class BuildProgress(enum.Enum):
    INIT = enum.auto()
    UNPACKED = enum.auto()
    REPOSITORIES_INITIALIZED = enum.auto()
    CONFDIR_INITIALIZED = enum.auto()
    SYSTEM_UPDATED = enum.auto()
    PACKAGES_INSTALLED = enum.auto()
    KERNEL_AND_INITRAMFS_GENERATED = enum.auto()
    SYSTEM_SOLDERED = enum.auto()
