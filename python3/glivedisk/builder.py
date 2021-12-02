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
import robust_layer.simple_fops
from .util import Util
from .setting import Target, HostInfo, ChrootInfo
from .errors import WorkDirVerifyError
from .support import Chroot



class Builder:
    """
    This class does all of the chroot setup, copying of files, etc. It is
    the driver class for pretty much everything that glivedisk does.
    """

    @staticmethod
    def new(seed_stage_stream, target, work_dir=None, host_info=None, chroot_info=None):
        # check seed_stage_stream
        assert hasattr(seed_stage_stream, "extractall")

        # check target
        assert isinstance(target, Target)

        # check work_dir
        if work_dir is None:
            work_dir = "/var/tmp/glivedisk"
        if os.path.exists(work_dir):
            assert os.path.isdir(work_dir)
        else:
            assert os.path.isdir(os.path.dirname(work_dir))

        # check host_info
        if host_info is not None:
            assert isinstance(host_info, HostInfo)
        
        # check chroot_info
        if chroot_info is None:
            chroot_info = ChrootInfo()
        assert isinstance(chroot_info, ChrootInfo)

        # create object
        ret = Builder()
        ret._tf = seed_stage_stream
        ret._workDir = work_dir
        ret._target = target
        ret._hostInfo = host_info
        ret._chroot = Chroot(chroot_info)

        # initialize work_dir
        if not os.path.exists(ret._workDir):
            os.mkdir(ret._workDir, mode=0o0700)
        else:
            s = os.stat(ret._workDir)
            if s.st_mode != 0o0700:
                raise WorkDirVerifyError("invalid mode for \"%s\"" % (ret._workDir))
            if s.st_uid != os.getuid():
                raise WorkDirVerifyError("invalid uid for \"%s\"" % (ret._workDir))
            if s.st_gid != os.getgid():
                raise WorkDirVerifyError("invalid gid for \"%s\"" % (ret._workDir))
            robust_layer.simple_fops.truncate_dir(ret._workDir)

        # save parameters
        Util.saveObj(os.path.join(ret._workDir, "target.json"), target)
        Util.saveObj(os.path.join(ret._workDir, "host_info.json", host_info))
        Util.saveObj(os.path.join(ret._workDir, "chroot_info.json", chroot_info))

        return ret

    @staticmethod
    def revoke(work_dir):
        # create object
        ret = Builder()
        ret._tf = None
        ret._workDir = work_dir
        ret._target = Util.loadObj(os.path.join(ret._workDir, "target.json"))
        ret._hostInfo = Util.loadObj(os.path.join(ret._workDir, "host_info.json"))
        ret._chroot = Chroot(Util.loadObj(os.path.join(ret._workDir, "chroot_info.json")))
        return ret

    def __init__(self):
        self._tf = None
        self._workDir = None
        self._target = None
        self._hostInfo = None
        self._chroot = None





        self.settings = settings
        self.env = {
            'PATH': '/bin:/sbin:/usr/bin:/usr/sbin',
            'TERM': os.getenv('TERM', 'dumb'),
        }

    def 

