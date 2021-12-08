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
import stat
import robust_layer.simple_fops
from ._util import Util
from ._errors import WorkDirVerifyError


class WorkDir:
    """
    This class manipulates glivecd's working directory.
    """

    MODE = 0o40700

    def __init__(self, path):
        self._path = path
        self._bPrepared = False

    @property
    def path(self):
        return self._path

    @property
    def chroot_dir_path(self):
        ret = os.path.normpath(os.readlink(os.path.join(self._path, "chroot")))
        assert os.path.exists(ret)
        return ret

    def initialize(self):
        if not os.path.exists(self._path):
            os.mkdir(self._path, mode=self.MODE)
        else:
            self.verify_existing()
            robust_layer.simple_fops.truncate_dir(self._path)

    def verify_empty(self):
        self._verify()
        if len(os.listdir(self._path)) > 0:
            raise WorkDirVerifyError("\"%s\" is not empty" % (self._path))

    def verify_existing(self):
        self._verify()

    def destroy(self):
        robust_layer.simple_fops.rm(self._path)

    def is_rollback_supported(self):
        return False

    def has_chroot_dir(self, dir_name):
        return os.path.exists(self._path, dir_name)

    def create_new_chroot_dir(self, dir_name):
        # create the first chroot directory
        if not os.path.exists(self.chroot_dir_path):
            os.mkdir(os.path.join(self._path, dir_name))
            os.symlink(dir_name, self.chroot_dir_path)
            return

        # snapshot the previous chroot directory
        if self.is_rollback_supported():
            robust_layer.simple_fops.ln(dir_name, self.chroot_dir_path)

    def rollback_to_old_chroot_dir(self, dir_name):
        assert self.is_rollback_supported()
        assert self.has_chroot_dir(dir_name) and dir_name != os.path.basename(self.chroot_dir_path)

        # FIXME
        raise NotImplementedError()

    def _verify(self):
        # work directory can be a directory or directory symlink
        # so here we use os.stat() instead of os.lstat()
        s = os.stat(self._path)
        if not stat.S_ISDIR(s.st_mode):
            raise WorkDirVerifyError("\"%s\" is not a directory" % (self._path))
        if s.st_mode != self.MODE:
            raise WorkDirVerifyError("invalid mode for \"%s\"" % (self._path))
        if s.st_uid != os.getuid():
            raise WorkDirVerifyError("invalid uid for \"%s\"" % (self._path))
        if s.st_gid != os.getgid():
            raise WorkDirVerifyError("invalid gid for \"%s\"" % (self._path))


class WorkDirChrooter:

    def __init__(self, work_dir):
        self._workDirObj = work_dir
        self._bBind = False

    def __enter__(self):
        self.bind()
        return self

    def __exit__(self, type, value, traceback):
        self.unbind()

    @property
    def binded(self):
        return self._bBind

    def bind(self):
        assert not self._bBind

        try:
            # copy resolv.conf
            Util.shellCall("/bin/cp -L /etc/resolv.conf \"%s\"" % (os.path.join(self._workDirObj.chroot_dir_path, "etc")))

            # mount /proc
            self._assertDirStatus("/proc")
            Util.shellCall("/bin/mount -t proc proc \"%s\"" % (os.path.join(self._workDirObj.chroot_dir_path, "proc")))

            # mount /sys
            self._assertDirStatus("/sys")
            Util.shellCall("/bin/mount --rbind /sys \"%s\"" % (os.path.join(self._workDirObj.chroot_dir_path, "sys")))
            Util.shellCall("/bin/mount --make-rslave \"%s\"" % (os.path.join(self._workDirObj.chroot_dir_path, "sys")))

            # mount /dev
            self._assertDirStatus("/dev")
            Util.shellCall("/bin/mount --rbind /dev \"%s\"" % (os.path.join(self._workDirObj.chroot_dir_path, "dev")))
            Util.shellCall("/bin/mount --make-rslave \"%s\"" % (os.path.join(self._workDirObj.chroot_dir_path, "dev")))

            # mount /tmp
            self._assertDirStatus("/tmp")
            Util.shellCall("/bin/mount -t tmpfs tmpfs \"%s\"" % (os.path.join(self._workDirObj.chroot_dir_path, "tmp")))
        except BaseException:
            self._unbind()
            raise

        # change status
        self._bBind = True

    def unbind(self):
        assert self._bBind
        self._unbind()
        self._bBind = False

    def run_cmd(self, env, cmd, quiet=False):
        # "CLEAN_DELAY=0 /usr/bin/emerge -C sys-fs/eudev" -> "CLEAN_DELAY=0 /usr/bin/chroot /usr/bin/emerge -C sys-fs/eudev"
        if not quiet:
            print("%s" % (cmd))
            return Util.shellExec("%s /usr/bin/chroot \"%s\" %s" % (env, self._parent._workDir.chroot_dir_path, cmd))
        else:
            return Util.shellCall("%s /usr/bin/chroot \"%s\" %s" % (env, self._parent._workDir.chroot_dir_path, cmd))

    def run_chroot_script(self, env, cmd, quiet=False):
        # "CLEAN_DELAY=0 /usr/bin/emerge -C sys-fs/eudev" -> "CLEAN_DELAY=0 /usr/bin/chroot /usr/bin/emerge -C sys-fs/eudev"

        selfDir = os.path.dirname(os.path.realpath(__file__))
        chrootScriptSrcDir = os.path.join(selfDir, "scripts-in-chroot")
        chrootScriptDstDir = os.path.join(self._parent._workDir.chroot_dir_path, "tmp", "glivecd")

        Util.cmdCall("/bin/cp", "-r", chrootScriptSrcDir, chrootScriptDstDir)
        Util.shellCall("/bin/chmod -R %s/*" % (chrootScriptDstDir))

        try:
            if not quiet:
                return Util.shellExec("%s /usr/bin/chroot \"%s\" %s" % (env, self._parent._workDir.chroot_dir_path, cmd))
            else:
                return Util.shellCall("%s /usr/bin/chroot \"%s\" %s" % (env, self._parent._workDir.chroot_dir_path, cmd))
        finally:
            robust_layer.simple_fops.rm(chrootScriptDstDir)

    def _assertDirStatus(self, dir):
        assert dir.startswith("/")
        fullfn = os.path.join(self._workDirObj.chroot_dir_path, dir[1:])
        assert os.path.exists(fullfn)
        assert not Util.ismount(fullfn)

    def _unbind(self):
        def _procOne(fn):
            fullfn = os.path.join(self._workDirObj.chroot_dir_path, fn[1:])
            if os.path.exists(fullfn) and Util.ismount(fullfn):
                Util.cmdCall("/bin/umount", "-l", fullfn)

        _procOne("/tmp")
        _procOne("/dev")
        _procOne("/sys")
        _procOne("/proc")

        robust_layer.simple_fops.rm(os.path.join(self._workDirObj.chroot_dir_path, "etc", "resolv.conf"))
