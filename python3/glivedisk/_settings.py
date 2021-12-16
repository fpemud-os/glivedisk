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


import re
import multiprocessing


MY_NAME = "glivecd"


class Settings(dict):

    def __init__(self):
        super().__init__()

    def get_program_name(self):
        return self["program_name"]

    def get_host_computing_power(self):
        return self["host_computing_power"]


class HostComputingPower:

    @staticmethod
    def check_object(obj):
        if not isinstance(obj, HostComputingPower):
            return False
        return obj.cpu_core_count > 0 and obj.memory_size > 0 and 1 <= obj.cooling_level <= 10

    @staticmethod
    def new(cpu_core_count, memory_size, cooling_level):
        assert cpu_core_count > 0
        assert memory_size > 0
        assert 1 <= cooling_level <= 10

        ret = HostComputingPower()
        ret.cpu_core_count = cpu_core_count
        ret.memory_size = memory_size
        ret.cooling_level = cooling_level
        return ret

    @staticmethod
    def auto_detect():
        ret = HostComputingPower()

        # cpu_core_count
        ret.cpu_core_count = multiprocessing.cpu_count()

        # memory_size
        with open("/proc/meminfo", "r") as f:
            # Since the memory size shown in /proc/meminfo is always a
            # little less than the real size because various sort of
            # reservation, so we do a "+1GB"
            m = re.search("^MemTotal:\\s+(\\d+)", f.read())
            ret.memory_size = (int(m.group(1)) // 1024 // 1024 + 1) * 1024 * 1024

        # cooling_level
        ret.cooling_level = 5

        return ret

    def __init__(self):
        self.cpu_core_count = None
        self.memory_size = None             # in byte
        self.cooling_level = None           # 1-10, less is weaker
