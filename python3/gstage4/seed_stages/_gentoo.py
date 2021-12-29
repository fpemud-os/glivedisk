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
import tarfile
import pathlib
import urllib.request
from .. import SeedStage


class CloudGentooStage3Archive(SeedStage):

    def __init__(self, arch, variant):
        self._arch = arch
        self._variant = variant

        self._stage3FileUrl = None
        self._stage3HashFileUrl = None

        self._resp = None
        self._tf = None

        if self._arch == "alpha":
            assert False
        elif self._arch == "amd64":
            assert self._variant in ["musl", "no-multilib-openrc", "no-multilib-systemd", "openrc", "systemd"]
        elif self._arch == "arm":
            assert False
        elif self._arch == "arm64":
            assert False
        elif self._arch == "hppa":
            assert False
        elif self._arch == "ia64":
            assert False
        elif self._arch == "m68k":
            assert False
        elif self._arch == "mips":
            assert False
        elif self._arch == "ppc":
            assert False
        elif self._arch == "riscv":
            assert False
        elif self._arch == "s390":
            assert False
        elif self._arch == "sh":
            assert False
        elif self._arch == "sparc":
            assert False
        elif self._arch == "x86":
            assert False
        else:
            assert False

    def connect(self):
        if self._arch == "alpha":
            assert False
        elif self._arch == "amd64":
            indexFileName = "latest-stage3-amd64-%s.txt" % (self._variant)
        elif self._arch == "arm":
            assert False
        elif self._arch == "arm64":
            assert False
        elif self._arch == "hppa":
            assert False
        elif self._arch == "ia64":
            assert False
        elif self._arch == "m68k":
            assert False
        elif self._arch == "mips":
            assert False
        elif self._arch == "ppc":
            assert False
        elif self._arch == "riscv":
            assert False
        elif self._arch == "s390":
            assert False
        elif self._arch == "sh":
            assert False
        elif self._arch == "sparc":
            assert False
        elif self._arch == "x86":
            assert False
        else:
            assert False

        baseUrl = "https://mirrors.tuna.tsinghua.edu.cn/gentoo"
        autoBuildsUrl = os.path.join(baseUrl, "releases", self._arch, "autobuilds")

        self._stage3FileUrl = None
        with urllib.request.urlopen(os.path.join(autoBuildsUrl, indexFileName)) as resp:
            m = re.search(r'^(\S+) [0-9]+', resp.read().decode("UTF-8"), re.M)
            self._stage3FileUrl = os.path.join(autoBuildsUrl, m.group(1))

        self._stage3HashFileUrl = self._stage3FileUrl + ".DEGISTS"

        self._resp = urllib.request.urlopen(self._stage3FileUrl)
        try:
            self._tf = tarfile.open(fileobj=resp, mode="r:xz")
        except BaseException:
            self._resp.close()
            self._resp = None
            raise

    def get_arch(self):
        return self._arch

    def get_digest(self):
        with urllib.request.urlopen(self._stage3HashFileUrl) as resp:
            return resp.read()

    def unpack(self, target_dir):
        self._tf.extractall(target_dir)

    def close(self):
        if self._tf is not None:
            self._tf.close()
            self._tf = None
        if self._resp is not None:
            self._resp.close()
            self._resp = None

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()


class GentooStage3Archive(SeedStage):

    def __init__(self, filepath, digest_filepath=None):
        self._path = filepath
        self._hashPath = digest_filepath if digest_filepath is not None else self._path + ".DIGESTS"

        self._tf = tarfile.open(self._path, mode="r:xz")
        self._hash = pathlib.Path(self._hashPath).read_text()

    @property
    def file_name(self):
        return self._path

    @property
    def digest_file_name(self):
        return self._hashPath

    def get_arch(self):
        # FIXME: stage3-amd64-blabla.tar.xz
        return os.path.basename(self._path).split("-")[1]

    def get_digest(self):
        return self._hash

    def unpack(self, target_dir):
        self._tf.extractall(target_dir)

    def close(self):
        if self._tf is not None:
            self._tf.close()
            self._tf = None
        self._hash = None

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()
