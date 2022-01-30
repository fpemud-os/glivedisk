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
        Util.shellCall("cp %s/* %s" % (self._dirpath, script_dir_hostpath))
        Util.shellCall("find \"%s\" -type f | xargs chmod 644" % (script_dir_hostpath))
        Util.shellCall("find \"%s\" -type d | xargs chmod 755" % (script_dir_hostpath))

    def get_description(self):
        return self._desc

    def get_script(self):
        return self._filename


class ScriptFromBuffer(ScriptInChroot):

    def __init__(self, description, content_buffer):
        assert description is not None
        assert content_buffer is not None

        self._desc = description
        self._buf = content_buffer.strip("\n") + "\n"  # remove all redundant carrage returns

    def fill_script_dir(self, script_dir_hostpath):
        fullfn = os.path.join(script_dir_hostpath, _SCRIPT_FILE_NAME)
        with open(fullfn, "w") as f:
            f.write(self._buf)
        os.chmod(fullfn, 0o0755)

    def get_description(self):
        return self._desc

    def get_script(self):
        return _SCRIPT_FILE_NAME


class OneLinerScript(ScriptInChroot):

    def __init__(self, description, cmd, executor="/bin/sh"):
        assert description is not None
        self._desc = description

        assert cmd is not None
        self._cmd = cmd
        self._executor = executor

    def fill_script_dir(self, script_dir_hostpath):
        fullfn = os.path.join(script_dir_hostpath, _SCRIPT_FILE_NAME)
        with open(fullfn, "w") as f:
            f.write("#!%s\n" % (self._executor))
            f.write("%s\n" % (self._cmd))
        os.chmod(fullfn, 0o0755)

    def get_description(self):
        return self._desc

    def get_script(self):
        return _SCRIPT_FILE_NAME


class PlacingFilesScript(ScriptInChroot):

    def __init__(self, description):
        assert description is not None

        self._desc = description
        self._infoList = []

    def append_file(self, target_filepath, buf, owner=0, group=0, mode=0o644):
        assert target_filepath.startswith("/")
        assert isinstance(owner, int)
        assert isinstance(group, int)
        assert 0o000 <= mode <= 0o777
        assert isinstance(buf, str) or isinstance(buf, bytes)

        self._infoList.append(("f", target_filepath, owner, group, mode, buf, None))

    def append_host_file(self, target_filepath, hostpath, owner=0, group=0, mode=0o644):
        assert target_filepath.startswith("/")
        assert hostpath is not None
        assert isinstance(owner, int)
        assert isinstance(group, int)
        assert 0o000 <= mode <= 0o777

        self._infoList.append(("f", target_filepath, owner, group, mode, None, hostpath))

    def append_dir(self, target_dirpath, owner=0, group=0, mode=0o755):
        assert target_dirpath.startswith("/")
        assert isinstance(owner, int)
        assert isinstance(group, int)
        assert 0o000 <= mode <= 0o777

        self._infoList.append(("d", target_dirpath, owner, group, mode, None, None))

    def append_host_dir(self, target_dirpath, hostpath, owner=0, group=0, dmode=0o755, fmode=0o644):
        assert target_dirpath.startswith("/")
        assert hostpath is not None
        assert isinstance(owner, int)
        assert isinstance(group, int)
        assert 0o000 <= dmode <= 0o777
        assert 0o000 <= fmode <= 0o777

        self._infoList.append(("d", target_dirpath, owner, group, dmode, fmode, hostpath))

    def append_symlink(self, target_linkpath, target, owner=0, group=0):
        assert target_linkpath.startswith("/")
        assert isinstance(owner, int)
        assert isinstance(group, int)
        assert target is not None

        self._infoList.append(("s", target_linkpath, owner, group, target, None))

    def append_host_symlink(self, target_linkpath, hostpath, owner=0, group=0):
        assert target_linkpath.startswith("/")
        assert isinstance(owner, int)
        assert isinstance(group, int)
        assert hostpath is not None

        self._infoList.append(("s", target_linkpath, owner, group, None, hostpath))

    def fill_script_dir(self, script_dir_hostpath):
        # establish data directory
        dataDir = os.path.join(script_dir_hostpath, "data")
        os.mkdir(dataDir)
        for info in self._infoList:
            if info[0] == "f":
                t, target_filepath, owner, group, mode, buf, hostpath = info
                fullfn = os.path.join(dataDir, target_filepath[1:])
                if buf is not None:
                    assert hostpath is None
                    if isinstance(buf, str):
                        with open(fullfn, "w") as f:
                            f.write(buf)
                    elif isinstance(buf, bytes):
                        with open(fullfn, "wb") as f:
                            f.write(buf)
                    else:
                        assert False
                else:
                    assert hostpath is not None
                    shutil.copy(hostpath, fullfn)
                os.chown(fullfn, owner, group)
                os.chmod(fullfn, mode)
            elif info[0] == "d":
                t, target_dirpath, owner, group, dmode, fmode, hostpath = info
                fullfn = os.path.join(dataDir, target_dirpath[1:])
                if hostpath is not None:
                    assert fmode is not None
                    self._copytree(hostpath, fullfn, owner, group, dmode, fmode)
                else:
                    assert fmode is None
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
                os.chown(fullfn, owner, group)
            else:
                assert False

        # create script file
        fullfn = os.path.join(script_dir_hostpath, _SCRIPT_FILE_NAME)
        with open(fullfn, "w") as f:
            f.write(self._scriptContent.strip("\n") + "\n")  # remove all redundant carrage returns
        os.chmod(fullfn, 0o0755)

    def get_description(self):
        return self._desc

    def get_script(self):
        return _SCRIPT_FILE_NAME

    def _copytree(self, src, dst, owner, group, dmode, fmode):
        os.mkdir(dst)
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

    _scriptContent = r"""
#!/bin/bash

DATA_DIR=$(dirname $(realpath $0))/data

# merge directories and files
cd $DATA_DIR
find . -type d -exec mkdir -p /\{} \;
find . -type f -exec mv -f \{} /\{} \;
"""


_SCRIPT_FILE_NAME = "main.script"
