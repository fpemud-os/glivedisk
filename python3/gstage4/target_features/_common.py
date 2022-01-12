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


class UsePortage:

    def update_target_settings(self, target_settings):
        target_settings.package_manager = "portage"

    def update_world_set(self, world_set):
        world_set.add("sys-apps/portage")


class UseGenkernel:

    def update_target_settings(self, target_settings):
        target_settings.kernel_manager = "genkernel"

    def update_world_set(self, world_set):
        world_set.add("sys-kernel/genkernel")


class UseOpenrc:

    def update_target_settings(self, target_settings):
        target_settings.service_manager = "openrc"

    def update_world_set(self, world_set):
        world_set.add("sys-apps/openrc")


class UseSystemd:

    def update_target_settings(self, target_settings):
        target_settings.service_manager = "systemd"

    def update_world_set(self, world_set):
        world_set.add("sys-apps/systemd")


class DoNotUseDeprecatedPackagesAndFunctions:

    def update_target_settings(self, target_settings):
        assert "10-no-deprecated" not in target_settings.pkg_use_files
        assert "10-no-deprecated" not in target_settings.pkg_mask_files

        target_settings.pkg_use_files["10-no-deprecated"] = self._useFileContent.strip("\n") + "\n"
        target_settings.pkg_mask_files["10-no-deprecated"] = self._maskFileContent.strip("\n") + "\n"

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
net-misc/networkmanager    iwd gnutls -nss -wext
"""

    _maskFileContent = """
# deprecated gnome libs
gnome-base/gconf
gnome-base/gnome-vfs

# these packages depends on dev-lang/lua[deprecated]
media-libs/libquvi
media-libs/libquvi-scripts

# FUSE2 is deprecated
sys-fs/fuse:0

# replaced by net-wireless/iwd
net-wireless/wpa_supplicant

# libstdc++ is integrated in gcc
sys-libs/libstdc++-v3
"""


class PreferGnuAndGpl:

    def update_target_settings(self, target_settings):
        assert "10-prefer-gnu-and-gpl" not in target_settings.pkg_use_files
        assert "10-prefer-gnu-and-gpl" not in target_settings.pkg_mask_files

        target_settings.pkg_use_files["10-prefer-gnu-and-gpl"] = self._useFileContent.strip("\n") + "\n"
        target_settings.pkg_mask_files["10-prefer-gnu-and-gpl"] = self._maskFileContent.strip("\n") + "\n"

    _useFileContent = """
# no need to use dev-libs/libedit
*/*         readline

# use sys-libs/ncurses, why sys-libs/slang?
*/*         -slang
"""

    _maskFileContent = """
# no, we prefer sys-libs/readline
dev-libs/libedit
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
        s.append_dir("/etc", 0, 0)
        s.append_dir("/etc/systemd", 0, 0)
        s.append_dir("/etc/systemd/system", 0, 0)
        s.append_dir("/etc/systemd/system/getty@.service.d", 0, 0)
        s.append_file("/etc/systemd/system/getty@.service.d/getty-autologin.conf", 0, 0,
                      buf=self._fileContent.strip("\n") + "\n")  # remove all redundant carrage returns)

        assert s not in custom_script_list
        custom_script_list.append(s)

    _fileContent = """
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin root --noclear %I $TERM
"""
