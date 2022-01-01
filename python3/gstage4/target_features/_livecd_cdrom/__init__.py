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
import glob
import pathlib
import shutil
import subprocess
from gstage4 import ScriptInChroot


class CreateLiveCdAsIsoFile:

    def __init__(self, arch, cdrom_name, cdrom_vol_id, using_memtest=False):
        assert arch in ["alpha", "amd64", "arm", "arm64", "hppa", "ia64", "m68k", "mips", "ppc", "riscv", "s390", "sh", "sparc", "x86"]
        assert len(cdrom_vol_id) <= 32

        self._arch = arch
        self._name = cdrom_name
        self._volId = cdrom_vol_id
        self._memtest = using_memtest

    def update_world_set(self, world_set):
        if self._arch == "alpha":
            world_set.add("dev-libs/libisoburn")
        elif self._arch == "ia64":
            world_set.add("sys-fs/mtools")
            world_set.add("dev-libs/libisoburn")
            world_set.add("sys-boot/grub")
        elif self._arch == "mips":
            world_set.add("sys-boot/sgibootcd")
        else:
            world_set.add("sys-apps/hwdata")
            world_set.add("sys-boot/syslinux")
            world_set.add("app-cdr/cdrtools")

        if self._memtest:
            world_set.add("sys-apps/memtest86+")

    def get_worker_script(self, rootfs_dir, filepath):
        assert rootfs_dir is not None
        assert filepath is not None

        return _WorkerScript(self._arch, rootfs_dir, filepath, self._name, self._volId, self._memtest)


class CreateLiveCdOnCdrom:

    def __init__(self, arch, cdrom_name, cdrom_vol_id, using_memtest=False):
        assert arch in ["alpha", "amd64", "arm", "arm64", "hppa", "ia64", "m68k", "mips", "ppc", "riscv", "s390", "sh", "sparc", "x86"]
        assert len(cdrom_vol_id) <= 32

        self._arch = arch
        self._name = cdrom_name
        self._volId = cdrom_vol_id
        self._memtest = using_memtest

    def update_world_set(self, world_set):
        # FIXME
        assert False

    def get_worker_script(self, rootfs_work_dir, dev_path):
        # FIXME
        assert False


class _WorkerScript(ScriptInChroot):

    def __init__(self, arch, rootfs_dir, filepath, name, vol_id, using_memtest):
        self._arch = arch
        self._rootfsDir = rootfs_dir
        self._devPath = filepath
        self._name = name
        self._label = vol_id
        self._memtest = using_memtest

    def fill_script_dir(self, script_dir_hostpath):
        selfDir = os.path.dirname(os.path.realpath(__file__))

        # create rootfs dir
        fullfn = os.path.join(script_dir_hostpath, "rootfs")
        bootDir = os.path.join(fullfn, "boot")
        os.mkdir(bootDir)

        # create rootfs.sqfs and rootfs.sqfs.sha512
        sqfsFile = os.path.join(fullfn, "rootfs.sqfs")
        sqfsSumFile = os.path.join(fullfn, "rootfs.sqfs.sha512")
        shutil.copy(os.path.join(self._rootfsDir, "boot", "vmlinuz"), bootDir)
        shutil.copy(os.path.join(self._rootfsDir, "boot", "initramfs.img"), bootDir)
        subprocess.check_call("mksquashfs %s %s -no-progress -noappend -quiet -e boot/*" % (self._rootfsDir, sqfsFile), shell=True)
        subprocess.check_call("sha512sum %s > %s" % (sqfsFile, sqfsSumFile), shell=True)
        subprocess.check_call(["sed", "-i", "s#%s/\?##" % (fullfn), sqfsSumFile])   # remove directory prefix in rootfs.sqfs.sha512, sha512sum sucks

        self._generate_script(script_dir_hostpath, "main.sh.grub.in")


        # subprocess.check_call(["cp", "-a", self._rootfsDir, fullfn])      # shutil.copytree() does not support device nodes


        # # generate script
        # if self._arch == "alpha":
        #     self._generate_script(script_dir_hostpath, "main.sh.alpha.in")
        # elif self._arch == "hppa":
        #     self._generate_script(script_dir_hostpath, "main.sh.hppa.in")
        # elif self._arch == "sparc":
        #     self._generate_script(script_dir_hostpath, "main.sh.sparc.in")
        # elif self._arch == "mips":
        #     self._generate_script(script_dir_hostpath, "main.sh.mips.in")
        # elif self._arch in ["amd64", "x86"]:
        #     isolinuxDir = os.path.join(script_dir_hostpath, "isolinux")
        #     os.mkdir(isolinuxDir)

        #     with open(os.path.join(isolinuxDir, "isolinux.cfg"), "w") as f:
        #         f.write("default %s\n" % (self._name))
        #         f.write("timeout 150\n")
        #         f.write("ontimeout localhost\n")
        #         f.write("prompt 1\n")
        #         f.write("\n")
        #         f.write("display boot.msg\n")
        #         f.write("F1 kernels.msg\n")
        #         f.write("F2 F2.msg\n")
        #         f.write("F3 F3.msg\n")
        #         f.write("F4 F4.msg\n")
        #         f.write("F5 F5.msg\n")
        #         f.write("F6 F6.msg\n")
        #         f.write("F7 F7.msg\n")
        #         f.write("\n")
        #         f.write("label %s\n" % (self._name))
        #         f.write("  kernel /boot/vmlinuz\n")
        #         f.write("  append root=/dev/ram0 init=/linuxrc dokeymap looptype=squashfs loop=/image.squashfs cdroot initrd=/boot/initramfs.img vga=791\n")
        #         f.write("\n")
        #         f.write("label %s-nofb\n" % (self._name))
        #         f.write("  kernel /boot/vmlinuz\n")
        #         f.write("  append root=/dev/ram0 init=/linuxrc dokeymap looptype=squashfs loop=/image.squashfs cdroot initrd=/boot/initramfs.img\n")
        #         f.write("\n")
        #         if self._memtest:
        #             f.write("label memtest86\n")
        #             f.write("  kernel memtest86\n")
        #             f.write("\n")
        #         f.write("label localhost\n")
        #         f.write("  localboot -1\n")
        #         f.write("  MENU HIDE\n")

        #     with open(os.path.join(isolinuxDir, "boot.msg"), "w") as f:
        #         f.write("%s\n" % (self._name))
        #         f.write("Enter to boot; F1 for kernels  F2 for options.\n")
        #         f.write("Press any key in the next 15 seconds or we'll try to boot from disk.\n")

        #     with open(os.path.join(isolinuxDir, "kernels.msg"), "w") as f:
        #         f.write("Available kernels:\n")
        #         f.write("  %s\n" % (self._name))
        #         f.write("  %s-nofb\n" % (self._name))
        #         if self._memtest:
        #             f.write("  memtest86\n")

        #     for fullfn in glob.glob(os.path.join(selfDir, "x86-F*.msg")):
        #         shutil.copy(fullfn, os.path.join(isolinuxDir, os.path.basename(fullfn).replace("x86-", "")))

        #     self._generate_script(script_dir_hostpath, "main.sh.isolinux.in")
        # else:
        #     self._generate_script(script_dir_hostpath, "main.sh.grub.in")

    def get_description(self):
        return "Generate %s" % (self._name)

    def get_script(self):
        return "main.sh"

    def _generate_script(self, script_dir_hostpath, filename):
        selfDir = os.path.dirname(os.path.realpath(__file__))

        # generate script content
        buf = pathlib.Path(os.path.join(selfDir, filename)).read_text()
        buf = buf.replace(r"%VOL_ID%", self._label)
        buf = buf.replace(r"%FILEPATH%", self._devPath)

        # create script file
        fullfn = os.path.join(script_dir_hostpath, "main.sh")
        with open(fullfn, "w") as f:
            f.write(buf)
        os.chmod(fullfn, 0o0755)
