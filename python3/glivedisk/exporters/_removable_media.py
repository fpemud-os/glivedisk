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
import pathlib
from .._util import Util
from .._util import TempChdir
from .._util import TmpMount
from .._errors import ExportError


class RemovableMediaExporter:

    def __init__(self, program_name, work_dir, devpath):
        self._usbStickMinSize = 1 * 1024 * 1024 * 1024       # 1GiB
        self._progName = program_name
        self._workDirObj = work_dir
        self._devPath = devpath

    def export(self):
        self._check()

        # create partitions
        Util.initializeDisk(self._devPath, "mbr", [
            ("*", "vfat"),
        ])
        partDevPath = self._devPath + "1"

        # format the new partition and get its UUID
        Util.cmdCall("/usr/sbin/mkfs.vfat", "-F", "32", "-n", "SYSRESC", partDevPath)
        uuid = Util.getBlkDevUuid(partDevPath)
        if uuid == "":
            raise ExportError("can not get FS-UUID for %s" % (partDevPath))

        with TmpMount(partDevPath) as mp:
            # we need a fresh partition
            assert len(os.listdir(mp.mountpoint)) == 0

            rootfsFn = os.path.join(mp.mountpoint, "rescuedisk", "x86_64", "rootfs.sfs")
            rootfsMd5Fn = os.path.join(mp.mountpoint, "rescuedisk", "x86_64", "rootfs.sha512")
            kernelFn = os.path.join(mp.mountpoint, "rescuedisk", "x86_64", "vmlinuz")
            initrdFn = os.path.join(mp.mountpoint, "rescuedisk", "x86_64", "initramfs.img")

            os.makedirs(os.path.join(mp.mountpoint, "rescuedisk", "x86_64"))
            self._squashRootfs(rootfsFn, rootfsMd5Fn, kernelFn, initrdFn)

            # generate grub.cfg
            Util.cmdCall("/usr/sbin/grub-install", "--removable", "--target=x86_64-efi", "--boot-directory=%s" % (os.path.join(mp.mountpoint, "boot")), "--efi-directory=%s" % (mp.mountpoint), "--no-nvram")
            Util.cmdCall("/usr/sbin/grub-install", "--removable", "--target=i386-pc", "--boot-directory=%s" % (os.path.join(mp.mountpoint, "boot")), self._devPath)
            with open(os.path.join(mp.mountpoint, "boot", "grub", "grub.cfg"), "w") as f:
                buf = pathlib.Path(self.grubCfgSrcFile).read_text()
                buf = buf.replace("%UUID%", uuid)
                buf = buf.replace("%BASEDIR%", "/rescuedisk")
                buf = buf.replace("%PREFIX%", "/rescuedisk/x86_64")
                f.write(buf)

    def _check(self):
        if not Util.isBlkDevUsbStick(self._devPath):
            raise ExportError("device %s does not seem to be an usb-stick." % (self._devPath))
        if Util.getBlkDevSize(self._devPath) < self._usbStickMinSize:
            raise ExportError("device %s needs to be at least %d GB." % (self._devPath, self._usbStickMinSize / 1024 / 1024 / 1024))
        if Util.ismount(self._devPath):
            raise ExportError("device %s or any of its partitions is already mounted, umount it first." % (self._devPath))

    def _squashRootfs(self, rootfsDataFile, rootfsMd5File, kernelFile, initcpioFile):
        assert rootfsDataFile.startswith("/")
        assert rootfsMd5File.startswith("/")
        assert kernelFile.startswith("/")
        assert initcpioFile.startswith("/")

        Util.cmdCall("/bin/mv", os.path.join(self._workDirObj.chroot_dir_path, "boot", "vmlinuz"), kernelFile)
        Util.cmdCall("/bin/mv", os.path.join(self._workDirObj.chroot_dir_path, "boot", "initramfs.img"), initcpioFile)
        shutil.rmtree(os.path.join(self._workDirObj.chroot_dir_path, "boot"))

        Util.cmdExec("/usr/bin/mksquashfs", self._workDirObj.chroot_dir_path, rootfsDataFile, "-no-progress", "-noappend", "-quiet")
        with TempChdir(os.path.dirname(rootfsDataFile)):
            Util.shellExec("/usr/bin/sha512sum \"%s\" > \"%s\"" % (os.path.basename(rootfsDataFile), rootfsMd5File))
