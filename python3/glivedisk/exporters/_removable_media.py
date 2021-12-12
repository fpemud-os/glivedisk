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
import pathlib
from .._util import Util
from .._util import TmpMount
from .._errors import ExportError


class RemovableMediaExporter:

    def __init__(self, work_dir, target, **kwargs):
        self.usbStickMinSize = 1 * 1024 * 1024 * 1024       # 1GiB
        self.devPath = kwargs["devpath"]

    def check(self):
        if not Util.isBlkDevUsbStick(self.devPath):
            raise ExportError("device %s does not seem to be an usb-stick." % (self.devPath))
        if Util.getBlkDevSize(self.devPath) < self.usbStickMinSize:
            raise ExportError("device %s needs to be at least %d GB." % (self.devPath, self.usbStickMinSize / 1024 / 1024 / 1024))
        if Util.ismount(self.devPath):
            raise ExportError("device %s or any of its partitions is already mounted, umount it first." % (self.devPath))

    def export(self):
        # create partitions
        Util.initializeDisk(self.devPath, "mbr", [
            ("*", "vfat"),
        ])
        partDevPath = self.devPath + "1"

        # format the new partition and get its UUID
        Util.cmdCall("/usr/sbin/mkfs.vfat", "-F", "32", "-n", "SYSRESC", partDevPath)
        uuid = Util.getBlkDevUuid(partDevPath)
        if uuid == "":
            raise ExportError("can not get FS-UUID for %s" % (partDevPath))

        with TmpMount(partDevPath) as mp:
            # we need a fresh partition
            assert len(os.listdir(mp.mountpoint)) == 0

            rootfsFn = os.path.join(mp.mountpoint, "rescuedisk", "x86_64", "airootfs.sfs")
            rootfsMd5Fn = os.path.join(mp.mountpoint, "rescuedisk", "x86_64", "airootfs.sha512")
            kernelFn = os.path.join(mp.mountpoint, "rescuedisk", "x86_64", "vmlinuz")
            initrdFn = os.path.join(mp.mountpoint, "rescuedisk", "x86_64", "initcpio.img")

            os.makedirs(os.path.join(mp.mountpoint, "rescuedisk", "x86_64"))
            self.builder.squashRootfs(rootfsFn, rootfsMd5Fn, kernelFn, initrdFn)

            # generate grub.cfg
            Util.cmdCall("/usr/sbin/grub-install", "--removable", "--target=x86_64-efi", "--boot-directory=%s" % (os.path.join(mp.mountpoint, "boot")), "--efi-directory=%s" % (mp.mountpoint), "--no-nvram")
            Util.cmdCall("/usr/sbin/grub-install", "--removable", "--target=i386-pc", "--boot-directory=%s" % (os.path.join(mp.mountpoint, "boot")), self.devPath)
            with open(os.path.join(mp.mountpoint, "boot", "grub", "grub.cfg"), "w") as f:
                buf = pathlib.Path(self.grubCfgSrcFile).read_text()
                buf = buf.replace("%UUID%", uuid)
                buf = buf.replace("%BASEDIR%", "/rescuedisk")
                buf = buf.replace("%PREFIX%", "/rescuedisk/x86_64")
                f.write(buf)
