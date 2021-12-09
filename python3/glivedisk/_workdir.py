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
import pathlib
import robust_layer.simple_fops
from ._util import Util
from ._errors import SettingsError, WorkDirVerifyError


class WorkDir:
    """
    This class manipulates glivecd's working directory.
    """

    MODE = 0o40700

    def __init__(self, path, arch=None, chroot_uid_map=None, chroot_gid_map=None):
        assert path is not None

        self._path = path

        if arch is None:
            self._arch = "amd64"        # FIXME: should be same as the host system
        else:
            self._arch = arch

        if chroot_uid_map is None:
            self._uidMap = None
        else:
            assert chroot_uid_map[0] == os.getuid()
            self._uidMap = chroot_uid_map

        if chroot_gid_map is None:
            assert self._uidMap is None
            self._gidMap = None
        else:
            assert self._uidMap is not None
            assert chroot_gid_map[0] == os.getgid()
            self._gidMap = chroot_gid_map

        self._bPrepared = False

    @property
    def path(self):
        return self._path

    @property
    def chroot_dir_path(self):
        ret = os.path.realpath(self._chroot_link_path())
        assert os.path.exists(ret)
        return ret

    @property
    def chroot_uid_map(self):
        assert self._uidMap is not None
        return self._uidMap

    @property
    def chroot_gid_map(self):
        assert self._gidMap is not None
        return self._gidMap

    @property
    def arch(self):
        return self._arch

    def initialize(self):
        if not os.path.exists(self._path):
            os.mkdir(self._path, mode=self.MODE)
            self._save_arch()
        else:
            self.verify_existing()
            robust_layer.simple_fops.truncate_dir(self._path)

    def verify_existing(self):
        self._verify_dir()
        self._verify_arch()

    def is_rollback_supported(self):
        return False

    def has_uid_gid_map(self):
        return self._uidMap is not None

    def chroot_conv_uid(self, uid):
        if self._uidMap is None:
            return uid
        else:
            if uid not in self._uidMap:
                raise SettingsError("uid %d not found in uid map" % (uid))
            else:
                return self._uidMap[uid]

    def chroot_conv_gid(self, gid):
        if self._gidMap is None:
            return gid
        else:
            if gid not in self._gidMap:
                raise SettingsError("gid %d not found in gid map" % (gid))
            else:
                return self._gidMap[gid]

    def chroot_conv_uid_gid(self, uid, gid):
        return (self.chroot_conv_uid(uid), self.chroot_conv_gid(gid))

    def has_old_chroot_dir(self, dir_name):
        ret = os.path.exists(self._path, dir_name)
        if ret:
            # dir_name should not be the current chroot directory
            assert dir_name != os.path.basename(self.chroot_dir_path)
        return ret

    def create_new_chroot_dir(self, dir_name):
        linkPath = self._chroot_link_path()
        newChrootDir = os.path.join(self._path, dir_name)

        if not os.path.exists(linkPath):
            # create the first chroot directory
            os.mkdir(newChrootDir)
            os.symlink(dir_name, linkPath)
        else:
            if self.is_rollback_supported():
                # snapshot the old chroot directory
                assert False
            else:
                # move the old chroot directory to new chroot directory, record the old chroot directory as a file
                oldChrootDir = self.chroot_dir_path
                os.rename(oldChrootDir, newChrootDir)
                robust_layer.simple_fops.ln(dir_name, linkPath)
                pathlib.Path(oldChrootDir).touch()

    def rollback_to_old_chroot_dir(self, dir_name):
        assert self.is_rollback_supported()
        assert self.has_old_chroot_dir(dir_name) and dir_name != os.path.basename(self.chroot_dir_path)

        # FIXME
        raise NotImplementedError()

    def _chroot_link_path(self):
        return os.path.join(self._path, "chroot")

    def _arch_record_path(self):
        return os.path.join(self._path, "arch.save")

    def _verify_dir(self):
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

    def _save_arch(self):
        with open(self._arch_record_path(), "w") as f:
            f.write(self._arch + "\n")

    def _verify_arch(self):
        if not os.path.exists(self._arch_record_path()):
            raise WorkDirVerifyError("arch is not saved")
        if pathlib.Path(self._arch_record_path()).read_text().rstrip("\n") != self._arch:
            raise WorkDirVerifyError("arch is invalid")


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
            return Util.shellExec("%s /usr/bin/chroot \"%s\" %s" % (env, self._workDirObj.chroot_dir_path, cmd))
        else:
            return Util.shellCall("%s /usr/bin/chroot \"%s\" %s" % (env, self._workDirObj.chroot_dir_path, cmd))

    def run_chroot_script(self, env, cmd, quiet=False):
        # "CLEAN_DELAY=0 /usr/bin/emerge -C sys-fs/eudev" -> "CLEAN_DELAY=0 /usr/bin/chroot /usr/bin/emerge -C sys-fs/eudev"

        selfDir = os.path.dirname(os.path.realpath(__file__))
        chrootScriptSrcDir = os.path.join(selfDir, "scripts-in-chroot")
        chrootScriptDstDir = os.path.join(self._workDirObj.chroot_dir_path, "tmp", "glivecd")

        Util.cmdCall("/bin/cp", "-r", chrootScriptSrcDir, chrootScriptDstDir)
        Util.shellCall("/bin/chmod -R 755 %s/*" % (chrootScriptDstDir))

        try:
            if not quiet:
                return Util.shellExec("%s /usr/bin/chroot \"%s\" %s" % (env, self._workDirObj.chroot_dir_path, cmd))
            else:
                return Util.shellCall("%s /usr/bin/chroot \"%s\" %s" % (env, self._workDirObj.chroot_dir_path, cmd))
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
