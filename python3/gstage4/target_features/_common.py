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
from ..scripts import ScriptPlacingFiles


class SshServer(TargetFeature):

    def update_world_set(self, world_set, dry_run=False):
        if "net-misc/openssh" not in world_set:
            if dry_run:
                raise SettingsError("package \"net-misc/openssh\" is needed")
            else:
                world_set.add("net-misc/openssh")

    def update_service_list(self, service_list, dry_run=False):
        if "sshd" not in service_list:
            if dry_run:
                raise SettingsError("service \"sshd\" is needed")
            else:
                service_list.append("sshd")

    def update_custom_script_list(self, custom_script_list, dry_run=False):
        # FIXME
        pass


class Chrony(TargetFeature):

    def update_world_set(self, world_set, dry_run=False):
        if "net-misc/chrony" not in world_set:
            if dry_run:
                raise SettingsError("package \"net-misc/chrony\" is needed")
            else:
                world_set.add("net-misc/chrony")

    def update_service_list(self, service_list, dry_run=False):
        if "chronyd" not in service_list:
            if dry_run:
                raise SettingsError("service \"chronyd\" is needed")
            else:
                service_list.append("chronyd")


class NetworkManager(TargetFeature):

    def update_world_set(self, world_set, dry_run=False):
        if "net-misc/networkmanager" not in world_set:
            if dry_run:
                raise SettingsError("package \"net-misc/networkmanager\" is needed")
            else:
                world_set.add("net-misc/networkmanager")

    def update_service_list(self, service_list, dry_run=False):
        if "NetworkManager" not in service_list:
            if dry_run:
                raise SettingsError("service \"NetworkManager\" is needed")
            else:
                service_list.append("NetworkManager")


class GettyAutoLogin(TargetFeature):

    def update_custom_script_list(self, custom_script_list, dry_run=False):
        s = ScriptPlacingFiles("Place auto login file")
        s.append_file("/etc/systemd/system/getty@.service.d/getty-autologin.conf",
                      0,
                      0,
                      buf=self._fileContent.strip("\n") + "\n")  # remove all redundant carrage returns)

        if s not in custom_script_list:
            if dry_run:
                raise SettingsError("custom script \"%s\" is needed" % (s.get_description()))
            else:
                custom_script_list.append()

    _fileContent = """
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin root --noclear %I $TERM
"""
