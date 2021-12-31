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
import pathlib
import subprocess
from gstage4 import ScriptInChroot


class CreateLiveCdOnRemovableMedia:

    """
    Creates livecd on remoable media, such as USB stick.
    This class needs "blkid", "parted", "mkfs.vfat" executables in host system.
    """

    def __init__(self, dev_path, disk_name, disk_label):
        assert dev_path is not None
        assert disk_name is not None
        assert disk_label is not None

        self._devPath = dev_path
        self._name = disk_name
        self._label = disk_label

    def update_world_set(self, world_set):
        world_set.add("sys-boot/grub")

    def prepare_target_device(self):
        subprocess.check_call(["parted", "--script", self._devPath, "mklabel", "msdos", "mkpart", "primary", "fat32", r"0%", r"100%"])
        subprocess.check_call(["mkfs.vfat", "-F", "32", "-n", self._label, self._devPath])

    def get_worker_script(self, rootfs_dir):
        assert rootfs_dir is not None

        uuid = subprocess.check_output(["blkid", "-s", "UUID", "-o", "value", self._devPath]).rstrip("\n")
        return _WorkerScript(rootfs_dir, self._devPath, uuid, self._name, self._label)


class _WorkerScript(ScriptInChroot):

    def __init__(self, rootfs_dir, dev_path, dev_uuid, name, label):
        self._rootfsDir = rootfs_dir
        self._devPath = dev_path
        self._devUuid = dev_uuid
        self._name = name
        self._label = label

    def fill_script_dir(self, script_dir_hostpath):
        selfDir = os.path.dirname(os.path.realpath(__file__))

        # create rootfs.sqfs and rootfs.sqfs.sha512
        sqfsFile = os.path.join(script_dir_hostpath, "rootfs.sqfs")
        sqfsSumFile = os.path.join(script_dir_hostpath, "rootfs.sqfs.sha512")
        shutil.copy(os.path.join(self._rootfsDir, "boot", "vmlinuz"), script_dir_hostpath)
        shutil.copy(os.path.join(self._rootfsDir, "boot", "initramfs.img"), script_dir_hostpath)
        subprocess.check_call(["mksquashfs", self._rootfsDir, sqfsFile, "-ef", os.path.join(self._rootfsDir, "boot", "*"), "-wildcards", "-no-progress", "-noappend", "-quiet"])
        subprocess.check_call("sha512sum %s > %s" % (sqfsFile, sqfsSumFile), shell=True)
        subprocess.check_call(["sed", "-i", "s#%s/\?##" % (script_dir_hostpath), sqfsSumFile])   # remove directory prefix in rootfs.sqfs.sha512, sha512sum sucks

        # create grub.cfg.in file
        buf = self._grubCfgContent
        buf = buf.replace(r"%NAME%", self._name)
        buf = buf.replace(r"%ARCH%", "x86_64")   # FIXME
        buf = buf.replace(r"%UUID%", self._devUuid)
        with open(os.path.join(script_dir_hostpath, "grub.cfg.in"), "w") as f:
            f.write(buf)

        # generate script content
        buf = pathlib.Path(os.path.join(selfDir, "main.sh.in")).read_text()
        buf = buf.strip("\n") + "\n"            # remove all redundant carrage returns
        buf = buf.replace(r"%DEV_PATH%", self._devPath)
        buf = buf.replace(r"%LABEL%", self._label)
        buf = buf.replace(r"%ARCH%", "x86_64")   # FIXME

        # create script file
        fullfn = os.path.join(script_dir_hostpath, self._scriptDirScriptName)
        with open(os.path.join(script_dir_hostpath, self._scriptDirScriptName), "w") as f:
            f.write(buf)
        os.chmod(fullfn, 0o0755)

    def get_description(self):
        return "Generate %s" % (self._name)

    def get_script(self):
        return self._scriptDirScriptName

    _scriptDirScriptName = "main.sh"

    _grubCfgContent = """
# Global settings
set default=0
set timeout=90

# Display settings
set gfxmode=auto
insmod efi_gop
insmod efi_uga
insmod gfxterm
insmod all_video
insmod videotest
insmod videoinfo
terminal_output gfxterm

# Menu
menuentry "Boot %NAME%" {
    search --no-floppy --fs-uuid --set %UUID%
    linux /data/%ARCH%/vmlinuz dev_uuid=%UUID% basedir=/data
    initrd /data/%ARCH%/initramfs.img
}

# Menu
menuentry "Boot existing OS" {
    set root=(hd0)
    chainloader +1
}

# menuentry "Run Memtest86+ (RAM test)" {
#     linux /data/%ARCH%/memtest
# }

# menuentry "Hardware Information (HDT)" {
#     linux /data/%ARCH%/hdt
# }

# Menu
menuentry "Restart" {
    reboot
}

# Menu
menuentry "Power Off" {
    halt
}
"""
