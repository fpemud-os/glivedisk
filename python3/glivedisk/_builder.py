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


def Action(progress_step):
    def decorator(func):
        def wrapper(self):
            # check
            assert self._progress == progress_step

            # get newChrootDir
            # FIXME: create bcachefs snapshot
            if self._chrootDir is None or self.is_rollback_supported():
                newChrootDir = os.path.join(self._workDir, "%02d-%s" % (progress_step, progress_step + 1))
                os.mkdir(newChrootDir)
            else:
                newChrootDir = self._chrootDir

            # do work
            func(self, newChrootDir)

            # do progress
            self._progress = progress_step + 1
            self._chrootDir = newChrootDir

        return wrapper

    return decorator


class BuildProgress(enum.Enum):
    STEP_INIT = enum.auto()
    STEP_UNPACKED = enum.auto()
    STEP_REPOSITORIES_INITIALIZED = enum.auto()
    STEP_CONFDIR_INITIALIZED = enum.auto()
    STEP_SYSTEM_UPDATED = enum.auto()
    STEP_PACKAGES_INSTALLED = enum.auto()
    STEP_KERNEL_AND_INITRAMFS_GENERATED = enum.auto()
    STEP_SYSTEM_SOLDERED = enum.auto()


class Builder:
    """
    This class does all of the chroot setup, copying of files, etc. It is
    the driver class for pretty much everything that glivedisk does.
    """

    @staticmethod
    def new(program_name, seed_stage_stream, work_dir, target, host_info=None, chroot_info=None):
        # check seed_stage_stream
        assert hasattr(seed_stage_stream, "extractall")

        # check work_dir
        if os.path.exists(work_dir):
            assert os.path.isdir(work_dir)
        else:
            assert os.path.isdir(os.path.dirname(work_dir))

        # check target
        assert isinstance(target, settings.Target)

        # check host_info
        if host_info is None:
            host_info = settings.HostInfo()
        assert isinstance(host_info, settings.HostInfo)
        
        # check chroot_info
        if chroot_info is None:
            chroot_info = settings.ChrootInfo()
        assert isinstance(chroot_info, settings.ChrootInfo)
        assert chroot_info.conv_uid_gid(0, 0) == (os.getuid(), os.getgid())

        # create object
        ret = Builder()
        ret._progName = program_name
        ret._tf = seed_stage_stream
        ret._workDir = work_dir
        ret._target = target
        ret._hostInfo = host_info
        ret._chroot = Chroot(chroot_info)
        ret._progress = BuildProgress.STEP_INIT

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
    def revoke(program_name, work_dir):
        ret = Builder()
        ret._progName = program_name
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
        if ret._progress < BuildProgress.STEP_UNPACKED:
            raise WorkDirVerifyError("invalid parameter file \"%s\"" % (fullfn))    # FIXME: change error message

        return ret

    def __init__(self):
        self._progName = None
        self._tf = None
        self._workDir = None
        self._target = None
        self._hostInfo = None
        self._chroot = None

        self._progress = None
        self._chrootDir = None

    def get_progress(self):
        return self._progress

    def get_work_dir(self):
        return self._workDir

    def is_rollback_supported(self):
        return False        # FIXME: support rollback through bcachefs non-priviledged snapshot

    def rollback_to(self, progress_step):
        assert isinstance(progress_step, BuildProgress) and progress_step < self._progress
        assert False        # FIXME: support rollback through bcachefs non-priviledged snapshot

    def dispose(self):
        self._chrootDir = None
        self._progress = None
        self._chroot = None
        self._hostInfo = None
        self._target = None
        if self._workDir is not None:
            robust_layer.simple_fops.rm(self._workDir)
            self._workDir = None
        self._tf = None

    @Action(BuildProgress.STEP_INIT)
    def action_unpack(self, newChrootDir):
        self._tf.extractall(newChrootDir)

    @Action(BuildProgress.STEP_UNPACKED)
    def action_init_repositories(self, newChrootDir):
        pass

    @Action(BuildProgress.STEP_REPOSITORIES_INITIALIZED)
    def action_init_confdir(self, newChrootDir):
        ConfDir.write_make_conf(self._progName, newChrootDir, self._target)

    @Action(BuildProgress.STEP_CONFDIR_INITIALIZED)
    def action_update_system(self, newChrootDir):
        pass

    @Action(BuildProgress.STEP_SYSTEM_UPDATED)
    def action_install_packages(self, newChrootDir):
        pass

    @Action(BuildProgress.STEP_PACKAGES_INSTALLED)
    def action_gen_kernel_and_initramfs(self, newChrootDir):
        pass

    @Action(BuildProgress.STEP_KERNEL_AND_INITRAMFS_GENERATED)
    def action_solder_system(self, newChrootDir):
        pass


class ConfDir:

    @staticmethod
    def write_make_conf(program_name, chroot_path, target):
        def __write(flags, value):
            if value is None and target.build_opts.common_flags is not None:
                myf.write('%s="${COMMON_FLAGS}"\n' % (flags))
            else:
                if isinstance(value, list):
                    myf.write('%s="%s"\n' % (flags, ' '.join(value)))
                else:
                    myf.write('%s="%s"\n' % (flags, value))

        # Modify and write out make.conf (for the chroot)
        makepath = os.path.join(chroot_path, "etc", "portage", "make.conf")
        with open(makepath, "w") as myf:
            myf.write("# These settings were set by %s that automatically built this stage.\n" % (program_name))
            myf.write("# Please consult /usr/share/portage/config/make.conf.example for a more detailed example.\n")
            myf.write("\n")

            # COMMON_FLAGS
            if target.build_opts.common_flags is not None:
                myf.write('COMMON_FLAGS="%s"\n' % (' '.join(target.build_opts.common_flags)))

            # foobar FLAGS
            __write("CFLAGS", target.build_opts.cflags)
            __write("CXXFLAGS", target.build_opts.cxxflags)
            __write("FCFLAGS", target.build_opts.fcflags)
            __write("FFLAGS", target.build_opts.fflags)
            __write("LDFLAGS", target.build_opts.ldflags)
            __write("ASFLAGS", target.build_opts.asflags)

            # Set default locale for system responses. #478382
            myf.write('\n')
            myf.write('# This sets the language of build output to English.\n')
            myf.write('# Please keep this setting intact when reporting bugs.\n')
            myf.write('LC_MESSAGES=C\n')


