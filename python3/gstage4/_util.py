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
import time
import pickle
import tempfile
import subprocess


class Util:

    def saveObj(filepath, obj):
        with open(filepath, 'wb') as fh:
            pickle.dump(obj, fh)

    def loadObj(filepath, klass):
        with open(filepath, "rb") as fh:
            return pickle.load(fh)

    def saveEnum(filepath, obj):
        Util.saveObj(filepath, obj)

    def loadEnum(filepath, klass):
        return Util.loadObj(filepath)

    @staticmethod
    def pathCompare(path1, path2):
        # Change double slashes to slash
        path1 = re.sub(r"//", r"/", path1)
        path2 = re.sub(r"//", r"/", path2)
        # Removing ending slash
        path1 = re.sub("/$", "", path1)
        path2 = re.sub("/$", "", path2)

        if path1 == path2:
            return 1
        return 0

    @staticmethod
    def isMount(path):
        """Like os.path.ismount, but also support bind mounts"""
        if os.path.ismount(path):
            return 1
        a = os.popen("mount")
        mylines = a.readlines()
        a.close()
        for line in mylines:
            mysplit = line.split()
            if Util.pathCompare(path, mysplit[2]):
                return 1
        return 0

    @staticmethod
    def isInstanceList(obj, *instances):
        for inst in instances:
            if isinstance(obj, inst):
                return True
        return False

    @staticmethod
    def cmdCall(cmd, *kargs):
        # call command to execute backstage job
        #
        # scenario 1, process group receives SIGTERM, SIGINT and SIGHUP:
        #   * callee must auto-terminate, and cause no side-effect
        #   * caller must be terminated by signal, not by detecting child-process failure
        # scenario 2, caller receives SIGTERM, SIGINT, SIGHUP:
        #   * caller is terminated by signal, and NOT notify callee
        #   * callee must auto-terminate, and cause no side-effect, after caller is terminated
        # scenario 3, callee receives SIGTERM, SIGINT, SIGHUP:
        #   * caller detects child-process failure and do appopriate treatment

        ret = subprocess.run([cmd] + list(kargs),
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             universal_newlines=True)
        if ret.returncode > 128:
            # for scenario 1, caller's signal handler has the oppotunity to get executed during sleep
            time.sleep(1.0)
        if ret.returncode != 0:
            print(ret.stdout)
            ret.check_returncode()
        return ret.stdout.rstrip()

    @staticmethod
    def shellCall(cmd):
        # call command with shell to execute backstage job
        # scenarios are the same as FmUtil.cmdCall

        ret = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             shell=True, universal_newlines=True)
        if ret.returncode > 128:
            # for scenario 1, caller's signal handler has the oppotunity to get executed during sleep
            time.sleep(1.0)
        if ret.returncode != 0:
            print(ret.stdout)
            ret.check_returncode()
        return ret.stdout.rstrip()

    @staticmethod
    def shellCallTestSuccess(cmd):
        ret = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             shell=True, universal_newlines=True)
        if ret.returncode > 128:
            time.sleep(1.0)
        return (ret.returncode == 0)

    @staticmethod
    def shellExec(cmd):
        ret = subprocess.run(cmd, shell=True, universal_newlines=True)
        if ret.returncode > 128:
            time.sleep(1.0)
        ret.check_returncode()

    @staticmethod
    def portageIsPkgInstalled(rootDir, pkg):
        dir = os.path.join(rootDir, "var", "db", "pkg", os.path.dirname(pkg))
        if os.path.exists(dir):
            for fn in os.listdir(dir):
                if fn.startswith(os.path.basename(pkg)):
                    return True
        return False


class TempChdir:

    def __init__(self, dirname):
        self.olddir = os.getcwd()
        os.chdir(dirname)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        os.chdir(self.olddir)


class TmpMount:

    def __init__(self, path, options=None):
        self._path = path
        self._tmppath = tempfile.mkdtemp()

        try:
            cmd = ["mount"]
            if options is not None:
                cmd.append("-o")
                cmd.append(options)
            cmd.append(self._path)
            cmd.append(self._tmppath)
            subprocess.run(cmd, check=True, universal_newlines=True)
        except BaseException:
            os.rmdir(self._tmppath)
            raise

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    @property
    def mountpoint(self):
        return self._tmppath

    def close(self):
        subprocess.run(["umount", self._tmppath], check=True, universal_newlines=True)
        os.rmdir(self._tmppath)


# class NewMountNamespace:

#     _CLONE_NEWNS = 0x00020000               # <linux/sched.h>
#     _MS_REC = 16384                         # <sys/mount.h>
#     _MS_PRIVATE = 1 << 18                   # <sys/mount.h>
#     _libc = None
#     _mount = None
#     _setns = None
#     _unshare = None

#     def __init__(self):
#         if self._libc is None:
#             self._libc = ctypes.CDLL('libc.so.6', use_errno=True)
#             self._mount = self._libc.mount
#             self._mount.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_char_p]
#             self._mount.restype = ctypes.c_int
#             self._setns = self._libc.setns
#             self._unshare = self._libc.unshare

#         self.parentfd = None

#     def open(self):
#         assert self.parentfd is None

#         self.parentfd = open("/proc/%d/ns/mnt" % (os.getpid()), 'r')

#         # copied from unshare.c of util-linux
#         try:
#             if self._unshare(self._CLONE_NEWNS) != 0:
#                 e = ctypes.get_errno()
#                 raise OSError(e, errno.errorcode[e])

#             srcdir = ctypes.c_char_p("none".encode("utf_8"))
#             target = ctypes.c_char_p("/".encode("utf_8"))
#             if self._mount(srcdir, target, None, (self._MS_REC | self._MS_PRIVATE), None) != 0:
#                 e = ctypes.get_errno()
#                 raise OSError(e, errno.errorcode[e])
#         except BaseException:
#             self.parentfd.close()
#             self.parentfd = None
#             raise

#     def close(self):
#         assert self.parentfd is not None

#         self._setns(self.parentfd.fileno(), 0)
#         self.parentfd.close()
#         self.parentfd = None

#     def __enter__(self):
#         return self

#     def __exit__(self, *_):
#         self.close()

# class FakeChroot:

#     """
#     This class use a mounted ext4-fs image, mount/pid/user container to create a chroot environment
#     """

#     @staticmethod
#     def create_image(imageFilePath, imageSize):
#         assert imageSize % (1024 * 1024) == 0
#         Util.shellCall("dd if=/dev/zero of=%s bs=%d count=%d conv=sparse" % (imageFilePath, 1024 * 1024, imageSize // (1024 * 1024)))
#         Util.shellCall("/sbin/mkfs.ext4 -O ^has_journal %s" % (imageFilePath))

#     def __init__(self, imageFilePath, iAmRoot, mountDir):
#         self._imageFile = imageFilePath
#         self._mntdir = mountDir
#         self._iAmRoot = iAmRoot

#         try:
#             if self._iAmRoot:
#                 Util.shellCall("mount -t ext4 %s %s" % (self._imageFile, self._mntdir))
#                 self._fuseProc = None
#             else:
#                 self._fuseProc = subprocess.Popen(["fuse2fs", "-f", self._imageFile, self._mntdir])
#         except BaseException:
#             self.dispose()
#             raise

#     def dispose(self):
#         if self._iAmRoot:
#             if Util.ismount(self._mntdir):
#                 Util.shellCall("umount %s" % (self._mntdir))
#         else:
#             if self._fuseProc is not None:
#                 self._fuseProc.terminate()
#                 self._fuseProc.wait()
#                 self._fuseProc = None

#     def run_cmd(self):
#         pass

#     def __enter__(self):
#         return self

#     def __exit__(self, type, value, traceback):
#         self.dispose()
