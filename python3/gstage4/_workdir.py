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
import platform
import robust_layer.simple_fops
from ._util import Util
from ._errors import WorkDirError
from ._settings import MY_NAME


class WorkDir:
    """
    This class manipulates gstage4's working directory.
    """

    def __init__(self, path, chroot_uid_map=None, chroot_gid_map=None, rollback=False):
        assert path is not None

        self._MODE = 0o40700
        self._CURRENT = "cur"

        self._path = path
        self._rollback = rollback

        # if chroot_uid_map is None:
        #     self._uidMap = None
        # else:
        #     assert chroot_uid_map[0] == os.getuid()
        #     self._uidMap = chroot_uid_map

        # if chroot_gid_map is None:
        #     assert self._uidMap is None
        #     self._gidMap = None
        # else:
        #     assert self._uidMap is not None
        #     assert chroot_gid_map[0] == os.getgid()
        #     self._gidMap = chroot_gid_map

    @property
    def can_rollback(self):
        return self._rollback

    @property
    def path(self):
        return self._path

    @property
    def chroot_dir_path(self):
        curPath = os.path.join(self._path, self._CURRENT)
        assert os.path.lexists(curPath)
        return curPath

    # @property
    # def chroot_uid_map(self):
    #     assert self._uidMap is not None
    #     return self._uidMap

    # @property
    # def chroot_gid_map(self):
    #     assert self._gidMap is not None
    #     return self._gidMap

    def initialize(self):
        if not os.path.exists(self._path):
            os.mkdir(self._path, mode=self._MODE)
        else:
            self._verifyDir(True)
            robust_layer.simple_fops.truncate_dir(self._path)

    def verify_existing(self, raise_exception=None):
        assert raise_exception is not None
        if not self._verifyDir(raise_exception):
            return False
        return True

    # def has_uid_gid_map(self):
    #     return self._uidMap is not None

    # def chroot_conv_uid(self, uid):
    #     if self._uidMap is None:
    #         return uid
    #     else:
    #         if uid not in self._uidMap:
    #             raise SettingsError("uid %d not found in uid map" % (uid))
    #         else:
    #             return self._uidMap[uid]

    # def chroot_conv_gid(self, gid):
    #     if self._gidMap is None:
    #         return gid
    #     else:
    #         if gid not in self._gidMap:
    #             raise SettingsError("gid %d not found in gid map" % (gid))
    #         else:
    #             return self._gidMap[gid]

    # def chroot_conv_uid_gid(self, uid, gid):
    #     return (self.chroot_conv_uid(uid), self.chroot_conv_gid(gid))

    def is_chroot_dir_opened(self):
        curPath = os.path.join(self._path, self._CURRENT)
        return os.path.lexists(curPath)

    def open_chroot_dir(self, from_dir_name=None):
        curPath = os.path.join(self._path, self._CURRENT)
        assert not os.path.lexists(curPath)

        if from_dir_name is not None:
            assert from_dir_name in self.get_old_chroot_dir_names()
            if self._rollback:
                if self._isSnapshotSupported():
                    # snapshot the old chroot directory
                    assert False
                else:
                    # copy the old chroot directory
                    Util.cmdCall("/bin/cp", "-r", os.path.join(self._path, from_dir_name), curPath)
            else:
                # FIXME: change to use python-renameat2
                os.rename(os.path.join(self._path, from_dir_name), curPath)
                with open(os.path.join(self._path, from_dir_name), "w") as f:
                    f.write("")
        else:
            if self._isSnapshotSupported():
                # create sub-volume
                assert False
            else:
                # create directory
                os.mkdir(curPath)

    def close_chroot_dir(self, to_dir_name=None):
        curPath = os.path.join(self._path, self._CURRENT)
        assert os.path.lexists(curPath)

        if to_dir_name is not None:
            assert to_dir_name != self._CURRENT and to_dir_name not in self.get_old_chroot_dir_names()
            robust_layer.simple_fops.mv(curPath, os.path.join(self._path, to_dir_name))
        else:
            robust_layer.simple_fops.rm(curPath)

    def get_old_chroot_dir_names(self):
        ret = []
        for fn in os.listdir(self._path):
            if fn != self._CURRENT and os.path.isdir(os.path.join(self._path, fn)):
                ret.append(fn)
        return ret

    def get_old_chroot_dir_path(self, dir_name):
        assert dir_name in self.get_old_chroot_dir_names()
        return os.path.join(self._path, dir_name)

    def get_save_files(self):
        ret = []
        for fn in os.listdir(self._path):
            if os.path.isfile(fn) and fn.endswith(".save"):
                ret.append(fn)
        return ret

    def _isSnapshotSupported(self):
        return False

    def _verifyDir(self, raiseException):
        # work directory can be a directory or directory symlink
        # so here we use os.stat() instead of os.lstat()
        s = os.stat(self._path)
        if not stat.S_ISDIR(s.st_mode):
            if raiseException:
                raise WorkDirError("\"%s\" is not a directory" % (self._path))
            else:
                return False
        if s.st_mode != self._MODE:
            if raiseException:
                raise WorkDirError("invalid mode for \"%s\"" % (self._path))
            else:
                return False
        if s.st_uid != os.getuid():
            if raiseException:
                raise WorkDirError("invalid uid for \"%s\"" % (self._path))
            else:
                return False
        if s.st_gid != os.getgid():
            if raiseException:
                raise WorkDirError("invalid gid for \"%s\"" % (self._path))
            else:
                return False
        return True


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

            # FIXME: mount /run
            pass

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

    def interactive_shell(self):
        cmd = "/bin/bash"       # FIXME: change to read shell
        return Util.shellExec("/usr/bin/chroot \"%s\" %s" % (self._workDirObj.chroot_dir_path, cmd))

    def shell_call(self, env, cmd):
        # "CLEAN_DELAY=0 /usr/bin/emerge -C sys-fs/eudev" -> "CLEAN_DELAY=0 /usr/bin/chroot /usr/bin/emerge -C sys-fs/eudev"

        # FIXME
        env = "LANG=C.utf8 " + env
        assert self._detectArch() == platform.machine()

        return Util.shellCall("%s /usr/bin/chroot \"%s\" %s" % (env, self._workDirObj.chroot_dir_path, cmd))

    def shell_test(self, env, cmd):
        # FIXME
        env = "LANG=C.utf8 " + env
        assert self._detectArch() == platform.machine()

        return Util.shellCallTestSuccess("%s /usr/bin/chroot \"%s\" %s" % (env, self._workDirObj.chroot_dir_path, cmd))

    def shell_exec(self, env, cmd, quiet=False):
        # FIXME
        env = "LANG=C.utf8 " + env
        assert self._detectArch() == platform.machine()

        if not quiet:
            print("%s" % (cmd))
            Util.shellExec("%s /usr/bin/chroot \"%s\" %s" % (env, self._workDirObj.chroot_dir_path, cmd))
        else:
            Util.shellCall("%s /usr/bin/chroot \"%s\" %s" % (env, self._workDirObj.chroot_dir_path, cmd))

    def _assertDirStatus(self, dir):
        assert dir.startswith("/")
        fullfn = os.path.join(self._workDirObj.chroot_dir_path, dir[1:])
        assert os.path.exists(fullfn)
        assert not Util.isMount(fullfn)

    def _unbind(self):
        def _procOne(fn):
            fullfn = os.path.join(self._workDirObj.chroot_dir_path, fn[1:])
            if os.path.exists(fullfn) and Util.isMount(fullfn):
                Util.cmdCall("/bin/umount", "-l", fullfn)

        _procOne("/tmp")
        _procOne("/dev")
        _procOne("/sys")
        _procOne("/proc")

        robust_layer.simple_fops.rm(os.path.join(self._workDirObj.chroot_dir_path, "etc", "resolv.conf"))

    def _detectArch(self):
        # FIXME: use profile function of pkgwh to get arch from CHOST
        return "x86_64"
