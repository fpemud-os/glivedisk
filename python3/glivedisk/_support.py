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
from ._errors import SeedVerifyError




class Chroot:

    def __init__(self, dirpath, chroot_info):
        self._dir = dirpath
        self._chrootInfo = chroot_info

    def conv_uid(self, uid):
        if self.uid_map is None:
            return uid
        else:
            if uid not in self.uid_map:
                raise SeedStageError("uid %d not found in uid map" % (uid))
            else:
                return self.uid_map[uid]

    def conv_gid(self, gid):
        if self.gid_map is None:
            return gid
        else:
            if gid not in self.gid_map:
                raise SeedStageError("gid %d not found in gid map" % (gid))
            else:
                return self.gid_map[gid]

    def conv_uid_gid(self, uid, gid):
        return (self.conv_uid(uid), self.conv_gid(gid))

