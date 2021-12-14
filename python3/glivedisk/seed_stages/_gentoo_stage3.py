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


import pathlib
import tarfile
from .. import SeedStage


class GentooStage3Archive(SeedStage):

    def __init__(self, filepath, digest_filepath=None):
        self._path = filepath
        self._hashPath = digest_filepath if digest_filepath is not None else self._path + ".DIGESTS"

        self._tf = tarfile.open(self._path, mode="r:xz")
        self._hash = pathlib.Path(self._hashPath).read_text()

    @property
    def arch(self):
        # FIXME
        assert False

    @property
    def variant(self):
        # FIXME
        assert False

    @property
    def filepath(self):
        return self._path

    @property
    def digest_filepath(self):
        return self._hashPath

    def unpack(self, target_dir):
        self._tf.extractall(target_dir)

    def get_digest(self):
        return self._hash

    def close(self):
        if self._tf is not None:
            self._tf.close()
            self._tf = None
        self._hash = None
