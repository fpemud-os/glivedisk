#!/usr/bin/env python3

# glivedisk - gentoo live disk building
#
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
from .._util import Util
from .._util import TempChdir


class SquashfsExporter:

    def __init__(self, work_dir, target, **kwargs):
        self.rootfsDir = os.path.join(work_dir, "chroot")
        self.rootfsDataFile = kwargs["rootfs_file"]
        self.rootfsMd5File = kwargs["rootfs_md5_file"]
        self.kernelFile = kwargs["kernel_file"]
        self.initramfsFile = kwargs["initramfs_file"]

    def check(self):
        pass

    def export(self):
        assert self.rootfsDataFile.startswith("/")
        assert self.rootfsMd5File.startswith("/")
        assert self.kernelFile.startswith("/")
        assert self.initramfsFile.startswith("/")

        Util.cmdCall("/bin/mv", os.path.join(self.rootfsDir, "boot", "vmlinuz-linux-lts"), self.kernelFile)
        Util.cmdCall("/bin/mv", os.path.join(self.rootfsDir, "boot", "initramfs-linux-lts-fallback.img"), self.initramfsFile)
        shutil.rmtree(os.path.join(self.rootfsDir, "boot"))

        Util.cmdExec("/usr/bin/mksquashfs", self.rootfsDir, self.rootfsDataFile, "-no-progress", "-noappend", "-quiet")
        with TempChdir(os.path.dirname(self.rootfsDataFile)):
            Util.shellExec("/usr/bin/sha512sum \"%s\" > \"%s\"" % (os.path.basename(self.rootfsDataFile), self.rootfsMd5File))
