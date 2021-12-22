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
import abc
from .. import TargetScript
from .._util import Util


class TargetScriptFromHostFile(TargetScript):

    def __init__(self, description, script_filepath):
        assert description is not None
        assert script_filepath is not None

        self._desc = description
        self._filepath = script_filepath

    @abc.abstractmethod
    def fill_script_dir(self, script_dir_hostpath):
        os.copy(self._filepath, script_dir_hostpath)
        os.chmod(os.path.join(script_dir_hostpath, os.path.basename(self._filepath)), 0o0755)

    @abc.abstractmethod
    def get_description(self):
        return self._desc

    @abc.abstractmethod
    def get_script(self):
        return os.path.basename(self._filepath)


class TargetScriptFromHostDir(TargetScript):

    def __init__(self, description, dirpath, script_filename):
        assert description is not None
        assert dirpath is not None
        assert "/" not in script_filename

        self._desc = description
        self._dirpath = dirpath
        self._filename = script_filename

    @abc.abstractmethod
    def fill_script_dir(self, script_dir_hostpath):
        Util.shellCall("/bin/cp %s/* %s" % (self._dirpath, script_dir_hostpath))
        Util.shellCall("/usr/bin/find \"%s\" -type f | xargs /bin/chmod 644" % (script_dir_hostpath))
        Util.shellCall("/usr/bin/find \"%s\" -type d | xargs /bin/chmod 755" % (script_dir_hostpath))

    @abc.abstractmethod
    def get_description(self):
        return self._desc

    @abc.abstractmethod
    def get_script(self):
        return self._filename


class GeneratedTargetScript(TargetScript):

    def __init__(self, description, script_filename, script_content):
        assert description is not None
        assert "/" not in script_filename
        assert script_content is not None

        self._desc = description
        self._filename = script_filename
        self._buf = script_content

    @abc.abstractmethod
    def fill_script_dir(self, script_dir_hostpath):
        fullfn = os.path.join(script_dir_hostpath, self._filename)
        with open(fullfn, "w") as f:
            f.write(self._scriptContent)
        os.chmod(fullfn, 0o0755)

    @abc.abstractmethod
    def get_description(self):
        return self._desc

    @abc.abstractmethod
    def get_script(self):
        return self._filename
