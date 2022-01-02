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
        world_set.add("dev-libs/libisoburn")
        world_set.add("sys-boot/grub")
        world_set.add("sys-fs/mtools")
        if self._memtest:
            world_set.add("sys-apps/memtest86+")

    def get_worker_script(self, rootfs_dir):
        assert rootfs_dir is not None

        return _WorkerScript(self._arch, rootfs_dir, self._name, self._volId, self._memtest)

    def get_result_filename(self):
        return "/result.iso"


class CreateLiveCdOnCdrom:

    def __init__(self, arch, dev_path, cdrom_name, cdrom_vol_id, using_memtest=False):
        assert arch in ["alpha", "amd64", "arm", "arm64", "hppa", "ia64", "m68k", "mips", "ppc", "riscv", "s390", "sh", "sparc", "x86"]
        assert len(cdrom_vol_id) <= 32

        self._arch = arch
        self._devPath = dev_path
        self._name = cdrom_name
        self._volId = cdrom_vol_id
        self._memtest = using_memtest

    def update_world_set(self, world_set):
        # FIXME
        assert False

    def get_worker_script(self, rootfs_dir):
        # FIXME
        assert False


class _WorkerScript(ScriptInChroot):

    def __init__(self, arch, rootfs_dir, name, vol_id, using_memtest):
        self._arch = arch
        self._rootfsDir = rootfs_dir
        self._name = name
        self._label = vol_id
        self._memtest = using_memtest

    def fill_script_dir(self, script_dir_hostpath):
        selfDir = os.path.dirname(os.path.realpath(__file__))

        # create rootfs dir
        baseDir = os.path.join(script_dir_hostpath, "rootfs")
        bootDir = os.path.join(baseDir, "boot")
        os.makedirs(bootDir)

        # create rootfs.sqfs and rootfs.sqfs.sha512
        sqfsFile = os.path.join(baseDir, "rootfs.sqfs")
        sqfsSumFile = os.path.join(baseDir, "rootfs.sqfs.sha512")
        shutil.copy(os.path.join(self._rootfsDir, "boot", "vmlinuz"), bootDir)
        shutil.copy(os.path.join(self._rootfsDir, "boot", "initramfs.img"), bootDir)
        subprocess.check_call("mksquashfs %s %s -no-progress -noappend -quiet -e boot/*" % (self._rootfsDir, sqfsFile), shell=True)
        subprocess.check_call("sha512sum %s > %s" % (sqfsFile, sqfsSumFile), shell=True)
        subprocess.check_call(["sed", "-i", "s#%s/\?##" % (baseDir), sqfsSumFile])   # remove directory prefix in rootfs.sqfs.sha512, sha512sum sucks

        # create script file
        fullfn = os.path.join(script_dir_hostpath, "main.sh")
        with open(fullfn, "w") as f:
            buf = pathlib.Path(os.path.join(selfDir, "main.sh.in")).read_text()
            buf = buf.replace(r"%VOL_ID%", self._label)
            f.write(buf)
        os.chmod(fullfn, 0o0755)

    def get_description(self):
        return "Generate %s" % (self._name)

    def get_script(self):
        return "main.sh"
