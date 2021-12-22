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

from .. import TargetFeature
from .. import SettingsError
from ..scripts import ScriptFromBuffer


class SshServer(TargetFeature):

    def update_world_set(self, world_set, dry_run=False):
        if dry_run:
            if "net-misc/openssh" not in world_set:
                raise SettingsError("package net-misc/openssh is needed")
        else:
            world_set.add("net-misc/openssh")

    def update_service_list(self, service_list, dry_run=False):
        if dry_run:
            if "sshd" not in service_list:
                raise SettingsError("service sshd is needed")
        else:
            if "sshd" not in service_list:
                service_list.append("sshd")

    def update_custom_script_list(self, custom_script_list, dry_run=False):
        # FIXME
        pass


class GettyAutoLogin(TargetFeature):

    def update_custom_script_list(self, custom_script_list, dry_run=False):
        class _MyScript(ScriptFromBuffer):
            def __init__(self):
                super().__init__("Place auto login file", script_content)

        s = _MyScript()
        if dry_run:
            if s not in custom_script_list:
                raise SettingsError("custom script %s is needed" % (s.get_description()))
        else:
            if s not in custom_script_list:
                custom_script_list.append(s)

