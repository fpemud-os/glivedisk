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


import copy
from .. import KernelInstaller
from .. import WorkDirChrooter


class GenKernel(KernelInstaller):
    """
    Gentoo has no standard way to build a kernel, this class uses sys-kernel/genkernel to build kernel and initramfs
    """

    def __init__(self, settings):
        settings = copy.deepcopy(settings)

        self._target = _SettingTarget(settings)
        self._hostInfo = _SettingHostInfo(settings)

    def install(self, program_name, host_computing_power, work_dir):
        with _Chrooter(work_dir) as m:
            m.run_cmd("", "")

    def _get_args(self):
        pass

    # # default genkernel args
    # GK_ARGS=(
    #     "${clst_kernel_gk_kernargs[@]}"
    #     --cachedir=/tmp/kerncache/${clst_kname}-genkernel_cache-${clst_version_stamp}
    #     --no-mountboot
    #     --kerneldir=/usr/src/linux
    #     --modulespackage=/tmp/kerncache/${clst_kname}-modules-${clst_version_stamp}.tar.bz2
    #     --minkernpackage=/tmp/kerncache/${clst_kname}-kernel-initrd-${clst_version_stamp}.tar.bz2 all
    # )
    # # extra genkernel options that we have to test for
    # if [ -n "${clst_gk_mainargs}" ]
    # then
    #     GK_ARGS+=(${clst_gk_mainargs})
    # fi
    # if [ -n "${clst_KERNCACHE}" ]
    # then
    #     GK_ARGS+=(--kerncache=/tmp/kerncache/${clst_kname}-kerncache-${clst_version_stamp}.tar.bz2)
    # fi
    # if [ -e /var/tmp/${clst_kname}.config ]
    # then
    #     GK_ARGS+=(--kernel-config=/var/tmp/${clst_kname}.config)
    # fi

    # if [ -n "${clst_splash_theme}" ]
    # then
    #     GK_ARGS+=(--splash=${clst_splash_theme})
    #     # Setup case structure for livecd_type
    #     case ${clst_livecd_type} in
    #         gentoo-release-minimal|gentoo-release-universal)
    #             case ${clst_hostarch} in
    #                 amd64|x86)
    #                     GK_ARGS+=(--splash-res=1024x768)
    #                 ;;
    #             esac
    #         ;;
    #     esac
    # fi

    # if [ -d "/tmp/initramfs_overlay/${clst_initramfs_overlay}" ]
    # then
    #     GK_ARGS+=(--initramfs-overlay=/tmp/initramfs_overlay/${clst_initramfs_overlay})
    # fi
    # if [ -n "${clst_CCACHE}" ]
    # then
    #     GK_ARGS+=(--kernel-cc=/usr/lib/ccache/bin/gcc --utils-cc=/usr/lib/ccache/bin/gcc)
    # fi

    # if [ -n "${clst_linuxrc}" ]
    # then
    #     GK_ARGS+=(--linuxrc=/tmp/linuxrc)
    # fi

    # if [ -n "${clst_busybox_config}" ]
    # then
    #     GK_ARGS+=(--busybox-config=/tmp/busy-config)
    # fi

    # if [ "${clst_target}" == "netboot2" ]
    # then
    #     GK_ARGS+=(--netboot)

    #     if [ -n "${clst_merge_path}" ]
    #     then
    #         GK_ARGS+=(--initramfs-overlay="${clst_merge_path}")
    #     fi
    # fi

    # if [[ "${clst_VERBOSE}" == "true" ]]
    # then
    #     GK_ARGS+=(--loglevel=2)
    # fi


class _SettingTarget:

    def __init__(self, settings):
        pass


class _SettingHostInfo:

    def __init__(self, settings):
        pass


class _Chrooter(WorkDirChrooter):

    def __init__(self, workDirObj):
        super().__init__(workDirObj)
