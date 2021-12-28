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

from gstage4.scripts import ScriptPlacingFiles


class DoNotUseDeprecated:

    def update_target_settings(self, target_settings):
        assert "00-no-deprecated" not in target_settings.pkg_use_files
        target_settings.pkg_use_files["00-no-deprecated"] = _useFileContent

    _useFileContent = """
# disable deprecated functions
*/*    -deprecated
*/*    -fallback

# media-libs/libquvi depends on dev-lang/lua[deprecated]
*/*    -quvi

# media-libs/libdv depends on libsdl-version-1, which is deprecated
*/*    -dv

# framebuffer device is deprecated by DRM
*/*    -fbdev

# "wpa_supplicant" is deprecated by "iwd", "nss" is deprecated by "gnutls", "wext" is deprecated
net-misc/networkmanager    iwd -nss -wext
"""


class SshServer:

    def update_world_set(self, world_set):
        world_set.add("net-misc/openssh")

    def update_service_list(self, service_list):
        if "sshd" not in service_list:
            service_list.append("sshd")

    def update_custom_script_list(self, custom_script_list):
        # FIXME
        pass


class ChronyDaemon:

    def update_world_set(self, world_set):
        world_set.add("net-misc/chrony")

    def update_service_list(self, service_list):
        if "chronyd" not in service_list:
            service_list.append("chronyd")


class NetworkManager:

    def update_world_set(self, world_set):
        world_set.add("net-misc/networkmanager")

    def update_service_list(self, service_list):
        if "NetworkManager" not in service_list:
            service_list.append("NetworkManager")


class GettyAutoLogin:

    def update_custom_script_list(self, custom_script_list):
        s = ScriptPlacingFiles("Place auto login file")
        s.append_file("/etc/systemd/system/getty@.service.d/getty-autologin.conf",
                      0,
                      0,
                      buf=self._fileContent.strip("\n") + "\n")  # remove all redundant carrage returns)

        assert s not in custom_script_list
        custom_script_list.append(s)

    _fileContent = """
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin root --noclear %I $TERM
"""
