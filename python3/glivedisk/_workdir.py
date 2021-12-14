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
import platform
import robust_layer.simple_fops
from ._util import Util
from ._errors import SettingsError, WorkDirError
from ._settings import MY_NAME


class WorkDir:
    """
    This class manipulates glivecd's working directory.
    """

    MODE = 0o40700

    def __init__(self, path, chroot_uid_map=None, chroot_gid_map=None):
        assert path is not None

        self._path = path

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
        assert self.has_chroot_dir()
        return os.path.realpath(self._chroot_link_path())

    @property
    def chroot_uid_map(self):
        assert self._uidMap is not None
        return self._uidMap

    @property
    def chroot_gid_map(self):
        assert self._gidMap is not None
        return self._gidMap

    def initialize(self):
        if not os.path.exists(self._path):
            os.mkdir(self._path, mode=self.MODE)
        else:
            self._verify_dir(True)
            robust_layer.simple_fops.truncate_dir(self._path)

    def verify_existing(self, raise_exception=None):
        assert raise_exception is not None
        if not self._verify_dir(raise_exception):
            return False
        return True

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

    def get_save_files(self):
        ret = []
        for fn in os.listdir(self._path):
            if os.path.isfile(fn) and fn.endswith(".save"):
                ret.append(fn)
        return ret

    def has_chroot_dir(self):
        return os.path.exists(self._chroot_link_path())

    def get_chroot_dir_names(self):
        linkPath = self._chroot_link_path()
        if not os.path.exists(linkPath):
            assert not any([os.path.isdir(x) for x in os.listdir(self._path)])
            return []
        else:
            cur = os.readlink(linkPath)
            ret = []
            for fn in os.listdir(self._path):
                if fn != "chroot" and fn != cur and os.path.isdir(fn):
                    ret.append(fn)
            ret.append(cur)
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
        dirNames = self.get_chroot_dir_names()
        assert len(dirNames) > 0 and dir_name in dirNames[:-1]

        # FIXME
        raise NotImplementedError()

    def _chroot_link_path(self):
        return os.path.join(self._path, "chroot")

    def _verify_dir(self, raiseException):
        # work directory can be a directory or directory symlink
        # so here we use os.stat() instead of os.lstat()
        s = os.stat(self._path)
        if not stat.S_ISDIR(s.st_mode):
            if raiseException:
                raise WorkDirError("\"%s\" is not a directory" % (self._path))
            else:
                return False
        if s.st_mode != self.MODE:
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
        self._chrootScriptDstDir = os.path.join("/tmp", MY_NAME)
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

        selfDir = os.path.dirname(os.path.realpath(__file__))
        chrootScriptSrcDir = os.path.join(selfDir, "scripts-in-chroot")
        chrootScriptDstDirHostPath = os.path.join(self._workDirObj.chroot_dir_path, self._chrootScriptDstDir[1:])

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

            # copy chroot scripts
            # no clean up needed since these files are in tmpfs
            Util.cmdCall("/bin/cp", "-r", chrootScriptSrcDir, chrootScriptDstDirHostPath)
            Util.shellCall("/bin/chmod -R 755 %s/*" % (chrootScriptDstDirHostPath))
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

    def shell_exec(self, env, cmd, quiet=False):
        # "CLEAN_DELAY=0 /usr/bin/emerge -C sys-fs/eudev" -> "CLEAN_DELAY=0 /usr/bin/chroot /usr/bin/emerge -C sys-fs/eudev"

        # FIXME
        env = "LANG=C.utf8 " + env
        assert self._detectArch() == platform.machine()

        if not quiet:
            print("%s" % (cmd))
            Util.shellExec("%s /usr/bin/chroot \"%s\" %s" % (env, self._workDirObj.chroot_dir_path, cmd))
        else:
            Util.shellCall("%s /usr/bin/chroot \"%s\" %s" % (env, self._workDirObj.chroot_dir_path, cmd))

    def script_exec(self, env, cmd, quiet=False):
        # "CLEAN_DELAY=0 /usr/bin/emerge -C sys-fs/eudev" -> "CLEAN_DELAY=0 /usr/bin/chroot /usr/bin/emerge -C sys-fs/eudev"

        # FIXME
        env = "LANG=C.utf8 " + env
        assert self._detectArch() == platform.machine()

        if not quiet:
            Util.shellExec("%s /usr/bin/chroot \"%s\" %s" % (env, self._workDirObj.chroot_dir_path, os.path.join(self._chrootScriptDstDir, cmd)))
        else:
            Util.shellCall("%s /usr/bin/chroot \"%s\" %s" % (env, self._workDirObj.chroot_dir_path, os.path.join(self._chrootScriptDstDir, cmd)))

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
