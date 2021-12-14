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


from .. import KernelInstaller
from .. import WorkDirChrooter


class GenKernel(KernelInstaller):
    """
    Gentoo has no standard way to build a kernel, this class uses sys-kernel/genkernel to build kernel and initramfs
    """

    def __init__(self, settings):
        pass

    def install(self, program_name, host_computing_power, work_dir):
        # determine parallelism parameters
        tj = None
        tl = None
        if host_computing_power.cooling_level <= 1:
            tj = 1
            tl = 1
        else:
            if host_computing_power.memory_size >= 24 * 1024 * 1024 * 1024:       # >=24G
                tj = host_computing_power.cpu_core_count + 2
                tl = host_computing_power.cpu_core_count
            else:
                tj = host_computing_power.cpu_core_count
                tl = max(1, host_computing_power.cpu_core_count - 1)

        with _Chrooter(work_dir) as m:
            m.shell_call("", "eselect kernel set 1")
            m.shell_exec("", "genkernel --quiet --no-mountboot --makeopts='-j%d -l%d' all" % (tj, tl))


class _Chrooter(WorkDirChrooter):

    def __init__(self, workDirObj):
        super().__init__(workDirObj)
