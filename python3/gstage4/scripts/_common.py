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
import shutil
from .. import ScriptInChroot
from .._util import Util


class ScriptFromHostFile(ScriptInChroot):

    def __init__(self, description, script_filepath):
        assert description is not None
        assert script_filepath is not None

        self._desc = description
        self._filepath = script_filepath

    def fill_script_dir(self, script_dir_hostpath):
        os.copy(self._filepath, script_dir_hostpath)
        os.chmod(os.path.join(script_dir_hostpath, os.path.basename(self._filepath)), 0o0755)

    def get_description(self):
        return self._desc

    def get_script(self):
        return os.path.basename(self._filepath)


class ScriptFromHostDir(ScriptInChroot):

    def __init__(self, description, dirpath, script_filename):
        assert description is not None
        assert dirpath is not None
        assert "/" not in script_filename

        self._desc = description
        self._dirpath = dirpath
        self._filename = script_filename

    def fill_script_dir(self, script_dir_hostpath):
        Util.shellCall("/bin/cp %s/* %s" % (self._dirpath, script_dir_hostpath))
        Util.shellCall("/usr/bin/find \"%s\" -type f | xargs /bin/chmod 644" % (script_dir_hostpath))
        Util.shellCall("/usr/bin/find \"%s\" -type d | xargs /bin/chmod 755" % (script_dir_hostpath))

    def get_description(self):
        return self._desc

    def get_script(self):
        return self._filename


class ScriptFromBuffer(ScriptInChroot):

    def __init__(self, description, content_buffer):
        assert description is not None
        assert content_buffer is not None

        self._desc = description
        self._filename = "main.sh"
        self._buf = content_buffer.strip("\n") + "\n"  # remove all redundant carrage returns

    def fill_script_dir(self, script_dir_hostpath):
        fullfn = os.path.join(script_dir_hostpath, self._filename)
        with open(fullfn, "w") as f:
            f.write(self._buf)
        os.chmod(fullfn, 0o0755)

    def get_description(self):
        return self._desc

    def get_script(self):
        return self._filename


class ScriptPlacingFiles(ScriptInChroot):

    def __init__(self, description):
        assert description is not None

        self._desc = description
        self._filename = "main.sh"
        self._infoList = []

    def append_file(self, target_filepath, owner, group, mode=None, buf=None, hostpath=None):
        assert target_filepath.startswith("/")
        assert isinstance(owner, int) and isinstance(group, int)
        if mode is not None:
            assert 0o000 <= mode <= 0o777
        else:
            mode = 0o644
        if buf is not None:
            assert hostpath is None
            assert isinstance(buf, str) or isinstance(buf, bytes)
        else:
            assert hostpath is not None

        self._infoList.append(("f", target_filepath, owner, group, mode, buf, hostpath))

    def append_dir(self, target_dirpath, owner, group, dmode=None, fmode=None, hostpath=None, recursive=False):
        assert target_dirpath.startswith("/")
        assert isinstance(owner, int) and isinstance(group, int)
        assert isinstance(owner, int) and isinstance(group, int)
        if dmode is not None:
            assert 0o000 <= dmode <= 0o777
        else:
            dmode = 0o755
        if fmode is not None:
            assert 0o000 <= fmode <= 0o777
        else:
            fmode = 0o644
        if hostpath is None:
            assert not recursive

        self._infoList.append(("d", target_dirpath, owner, group, dmode, fmode, hostpath, recursive))

    def append_symlink(self, target_linkpath, owner, group, target=None, hostpath=None):
        assert target_linkpath.startswith("/")
        assert isinstance(owner, int) and isinstance(group, int)
        assert (target is not None and hostpath is None) or (target is None and hostpath is not None)

        self._infoList.append(("s", target_linkpath, owner, group, target, hostpath))

    def fill_script_dir(self, script_dir_hostpath):
        # establish data directory
        dataDir = os.path.join(script_dir_hostpath, "data")
        os.mkdir(dataDir)
        for info in self._infoList:
            if info[0] == "f":
                t, target_filepath, owner, group, mode, buf, hostpath = info
                fullfn = os.path.join(dataDir, target_filepath[1:])
                if buf is not None:
                    if isinstance(buf, str):
                        with open(fullfn, "w") as f:
                            f.write(buf)
                    elif isinstance(buf, bytes):
                        with open(fullfn, "wb") as f:
                            f.write(buf)
                    else:
                        assert False
                else:
                    shutil.copy(hostpath, fullfn)
                os.chown(fullfn, owner, group)
                os.chmod(fullfn, mode)
            elif info[0] == "d":
                t, target_dirpath, owner, group, dmode, fmode, hostpath, recursive = info
                fullfn = os.path.join(dataDir, target_dirpath[1:])
                if hostpath is not None:
                    if not recursive:
                        os.mkdir(fullfn)
                        os.chown(fullfn, owner, group)
                        os.chmod(fullfn, dmode)
                    else:
                        self._copytree(hostpath, target_dirpath, owner, group, dmode, fmode)
                else:
                    os.mkdir(fullfn)
                    os.chown(fullfn, owner, group)
                    os.chmod(fullfn, dmode)
            elif info[0] == "s":
                t, target_linkpath, owner, group, target, hostpath = info
                fullfn = os.path.join(dataDir, target_linkpath[1:])
                if target is not None:
                    os.symlink(target, fullfn)
                else:
                    os.symlink(os.readlink(hostpath), fullfn)
            else:
                assert False

        # create script file
        fullfn = os.path.join(script_dir_hostpath, self._filename)
        with open(fullfn, "w") as f:
            f.write(self._scriptContent.strip("\n") + "\n")  # remove all redundant carrage returns
        os.chmod(fullfn, 0o0755)

    def get_description(self):
        return self._desc

    def get_script(self):
        return self._filename

    def _copytree(self, src, dst, owner, group, dmode, fmode):
        os.makedirs(dst)
        os.chown(dst, owner, group)
        os.chmod(dst, dmode)
        for name in os.listdir(src):
            srcname = os.path.join(src, name)
            dstname = os.path.join(dst, name)
            if os.path.islink(srcname):
                os.symlink(os.readlink(srcname), dstname)
            elif os.path.isdir(srcname):
                self._copytree(srcname, dstname, owner, group, dmode, fmode)
            else:
                shutil.copy(srcname, dstname)
                os.chown(dstname, owner, group)
                os.chmod(dstname, fmode)

    _scriptContent = """
#!/bin/bash

DATA_DIR=$(dirname $(realpath $0))/data

# merge directories and files
find $DATA_DIR -name '*' -type d -exec mv -f {} / \\;
find $DATA_DIR -name '*' -type f -exec mv -f {} / \\;
"""
