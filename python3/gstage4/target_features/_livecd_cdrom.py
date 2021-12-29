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
from gstage4 import ScriptInChroot


class CreateLiveCdAsIsoFile:

    def __init__(self, arch, cdrom_name, cdrom_vol_id, using_zisofs=False):
        assert arch in ["alpha", "amd64", "arm", "arm64", "hppa", "ia64", "m68k", "mips", "ppc", "riscv", "s390", "sh", "sparc", "x86"]
        assert len(cdrom_vol_id) <= 32

        self._arch = arch
        self._name = cdrom_name
        self._volId = cdrom_vol_id
        self._zisofs = using_zisofs

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
            world_set.add("sys-boot/syslinux")
            world_set.add("app-cdr/cdrtools")

    def get_worker_script(self, rootfs_dir, filepath):
        assert rootfs_dir is not None
        assert filepath is not None

        return _WorkerScript(self._arch, rootfs_dir, filepath, self._name, self._volId, self._zisofs)


class CreateLiveCdOnCdrom:

    def __init__(self, arch, cdrom_name, cdrom_vol_id, using_zisofs=False):
        assert arch in ["alpha", "amd64", "arm", "arm64", "hppa", "ia64", "m68k", "mips", "ppc", "riscv", "s390", "sh", "sparc", "x86"]
        assert len(cdrom_vol_id) <= 32

        self._arch = arch
        self._name = cdrom_name
        self._volId = cdrom_vol_id
        self._zisofs = using_zisofs

    def update_world_set(self, world_set):
        # FIXME
        assert False

    def get_worker_script(self, rootfs_work_dir, dev_path):
        # FIXME
        assert False


class _WorkerScript(ScriptInChroot):

    def __init__(self, arch, rootfs_dir, filepath, name, vol_id, using_zisofs):
        self._arch = arch
        self._rootfsDir = rootfs_dir
        self._devPath = filepath
        self._name = name
        self._label = vol_id
        self._mkisofs_zisofs_opts = "-z" if using_zisofs else ""

    def fill_script_dir(self, script_dir_hostpath):
        # create rootfs dir
        fullfn = os.path.join(script_dir_hostpath, self._scriptDirRootfsDirName)
        shutil.copytree(self._rootfsDir, fullfn, symlinks=True)

        # create script file
        if self._arch == "alpha":
            buf = self._scriptContentAlpha
        elif self._arch == "hppa":
            buf = self._scriptContentHppa
        elif self._arch == "sparc":
            buf = self._scriptContentSparc
        elif self._arch == "mips":
            buf = self._scriptContentMips
        elif self._arch in ["amd64", "x86"]:
            buf = self._scriptContentIsoLinux
        else:
            buf = self._scriptContentGrubRescue
        buf = buf.strip("\n") + "\n"            # remove all redundant carrage returns
        buf = buf.replace(r"%MKISOFS_ZISOFS_OPTS%", self._mkisofs_zisofs_opts)
        buf = buf.replace(r"%VOL_ID%", self._label)
        buf = buf.replace(r"%FILEPATH%", self._devPath)
        buf = buf.replace(r"%TARGET_PATH%", self._rootfsDir)
        with open(os.path.join(script_dir_hostpath, self._scriptDirScriptName), "w") as f:
            f.write(buf)

    def get_description(self):
        return "Generate %s" % (self._name)

    def get_script(self):
        return self._scriptDirScriptName

    _scriptDirScriptName = "main.sh"

    _scriptDirRootfsDirName = "rootfs"

    _scriptContentAlpha = """
#!/bin/bash

die() {
    echo "$1"
    exit 1
}

xorriso -as genisofs -alpha-boot boot/bootlx -R -l -J %MKISOFS_ZISOFS_OPTS% -V "%VOL_ID%" -o "%FILEPATH%" "%TARGET_PATH%" || die "Cannot make ISO image"
"""

    _scriptContentHppa = """
#!/bin/bash

die() {
    echo "$1"
    exit 1
}

mkisofs -R -l -J %MKISOFS_ZISOFS_OPTS% -V "%VOL_ID%" -o "%FILEPATH%" "%TARGET_PATH%"/ || die "Cannot make ISO image"
# pushd "${clst_target_path}/"
# palo -f boot/palo.conf -C "${1}"
# popd
"""

    _scriptContentSparc = """
#!/bin/bash
grub-mkrescue --sparc-boot -o "%FILEPATH%" ""%TARGET_PATH%""
"""

    # FIXME
    _scriptContentMips = """
#!/bin/bash

[ ! -d "%TARGET_PATH%/loopback" ] && mkdir "%TARGET_PATH%/loopback"
[ ! -d "%TARGET_PATH%/sgibootcd" ] && mkdir "%TARGET_PATH%/sgibootcd"

# Setup variables
[ -f "%TARGET_PATH%/livecd" ] && rm -f "%TARGET_PATH%/livecd"
img="%TARGET_PATH%/loopback/image.squashfs"
knl="%TARGET_PATH%/kernels"
arc="%TARGET_PATH%/arcload"
cfg="%TARGET_PATH%/sgibootcd/sgibootcd.cfg"
echo "" > "${cfg}"

# If the image file exists in $clst_target_path, move it to the loopback dir
[ -e "%TARGET_PATH%/image.squashfs" ] \
    && mv -f "%TARGET_PATH%/image.squashfs" "%TARGET_PATH%/loopback"

# An sgibootcd config is essentially a collection of commandline params
# stored in a text file.  We could pass these on the command line, but it's
# far easier to generate a config file and pass it to sgibootcd versus using a
# ton of commandline params.
#
# f=	indicates files to go into DVH (disk volume header) in an SGI disklabel
#	    format: f=</path/to/file>@<DVH name>
# p0=	the first partition holds the LiveCD rootfs image
#	    format: p0=</path/to/image>
# p8=	the eighth partition is the DVH partition
# p10=	the tenth partition is the disk volume partition
#	    format: p8= is always "#dvh" and p10= is always "#volume"

# Add the kernels to the sgibootcd config
for x in ${clst_boot_kernel}; do
    echo -e "f=${knl}/${x}@${x}" >> ${cfg}
done

# Next, the bootloader binaries and config
echo -e "f=${arc}/sash64@sash64" >> ${cfg}
echo -e "f=${arc}/sashARCS@sashARCS" >> ${cfg}
echo -e "f=${arc}/arc.cf@arc.cf" >> ${cfg}

# Next, the Loopback Image
echo -e "p0=${img}" >> ${cfg}

# Finally, the required SGI Partitions (dvh, volume)
echo -e "p8=#dvh" >> ${cfg}
echo -e "p10=#volume" >> ${cfg}

# All done; feed the config to sgibootcd and end up with an image
# c=	the config file
# o=	output image (burnable to CD; readable by fdisk)
/usr/bin/sgibootcd c=${cfg} o=${clst_iso}
"""

    _scriptContentGrubRescue = """
#!/bin/bash
grub-mkrescue -o "%FILEPATH%" ""%TARGET_PATH%""
"""

    _scriptContentIsoLinux = """
#!/bin/bash
mkisofs -J -R -l %MKISOFS_ZISOFS_OPTS% -V "%VOL_ID%" -o "%FILEPATH%" -b isolinux/isolinux.bin -c isolinux/boot.cat -no-emul-boot -boot-load-size 4 -boot-info-table "%TARGET_PATH%"/
isohybrid "%FILEPATH%"
"""
