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
import subprocess
from gstage4 import WorkDir
from gstage4 import ScriptInChroot


class CreateLiveCdOnRemovableMedia:

    def update_world_set(self, world_set):
        world_set.add("sys-boot/grub")
        world_set.add("sys-fs/dosfstools")
        world_set.add("sys-fs/parted")
        world_set.add("sys-fs/squashfs-tools")

    def get_worker_script(self, rootfs_dir, dev_path, usb_stick_name, usb_stick_label):
        return _WorkerScript(rootfs_dir, dev_path, usb_stick_name, usb_stick_label)


class _WorkerScript(ScriptInChroot):

    def __init__(self, rootfs_dir, dev_path, name, label):
        assert isinstance(rootfs_dir, WorkDir)
        assert dev_path is not None
        assert name is not None
        assert label is not None

        self._rootfsDir = rootfs_dir
        self._devPath = dev_path
        self._name = name
        self._label = label

    def fill_script_dir(self, script_dir_hostpath):
        # create rootfs dir
        fullfn = os.path.join(script_dir_hostpath, self._scriptDirRootfsDirName)
        subprocess.check_call("cp", "-r", self._rootfsDir, fullfn)

        # create grub.cfg.in file
        buf = self._grubCfgContent
        buf = buf.replace("%NAME%", self._name)
        buf = buf.replace("%ARCH%", "x86_64")   # FIXME
        with open(os.path.join(script_dir_hostpath, self._scriptDirGrubCfgFileName), "w") as f:
            f.write(buf)

        # create script file
        buf = self._scriptContent
        buf = buf.strip("\n") + "\n"            # remove all redundant carrage returns
        buf = buf.replace("%DEV_PATH%", self._devPath)
        buf = buf.replace("%LABEL%", self._label)
        buf = buf.replace("%ARCH%", "x86_64")   # FIXME
        with open(os.path.join(script_dir_hostpath, self._scriptDirScriptName), "w") as f:
            f.write(buf)

    def get_description(self):
        return "Generate %s" % (self._name)

    def get_script(self):
        return self._scriptDirScriptName

    _scriptDirScriptName = "main.py"

    _scriptDirRootfsDirName = "rootfs"

    _scriptDirGrubCfgFileName = "grub.cfg.in"

    _scriptContent = """
#!/bin/bash

FILES_DIR=$(dirname $(realpath $0))

parted --script %DEV_PATH% \
    mklabel msdos \
    mkpart primary fat32 0% 100%
mkfs.vfat -F 32 -n %LABEL% %DEV_PATH%

UUID=`blkid %DEV_PATH% -s UUID -o value`
BASE_DIR=/mnt
BOOT_DIR=${BASE_DIR}/boot
DATA_DIR=${BASE_DIR}/data/%ARCH%

mount %DEV_PATH%1 ${BASE_DIR}
mkdir -p ${BOOT_DIR} ${DATA_DIR}

mv ${FILES_DIR}/rootfs/boot/vmlinuz ${BOOT_DIR}
mv ${FILES_DIR}/rootfs/boot/initramfs.img ${BOOT_DIR}
mksquashfs ${FILESDIR}/rootfs ${DATA_DIR}/rootfs.sqfs -no-progress -noappend -quiet
sha512sum ${DATA_DIR}/rootfs.sqfs > ${DATA_DIR}/rootfs.sqfs.sha512                          # FIXME: remove directory prefix in rootfs.sqfs.sha512

grub-install --removable --target=x86_64-efi --boot-directory=${BOOT_DIR} --efi-directory=${BASE_DIR} --no-nvram
grub-install --removable --target=i386-pc --boot-directory=${BOOT_DIR}
sed "s/%UUID%/${UUID}/g" ${FILES_DIR}/grub.cfg.in > ${BOOT_DIR}/grub/grub.cfg
"""

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
