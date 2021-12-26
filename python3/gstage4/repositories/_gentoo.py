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


import tarfile
from .. import ManualSyncRepository
from .. import EmergeSyncRepository
from .. import BindMountRepository


class GentooRsync(EmergeSyncRepository):

    def get_name(self):
        return "gentoo"

    def get_repos_conf_file_content(self):
        url = "rsync://mirrors.tuna.tsinghua.edu.cn/gentoo-portage"

        # from Gentoo AMD64 Handbook
        # the commented part is not needed, I have tested it
        buf = ""
        # buf += "[DEFAULT]\n"
        # buf += "main-repo = gentoo\n"
        # buf += "\n"
        buf += "[gentoo]\n"
        buf += "location = %s\n" % (self.get_datadir_path())
        buf += "sync-type = rsync\n"
        buf += "sync-uri = %s\n" % (url)
        buf += "auto-sync = yes\n"
        buf += "sync-rsync-verify-jobs = 1\n"
        buf += "sync-rsync-verify-metamanifest = yes\n"
        buf += "sync-rsync-verify-max-age = 24\n"
        buf += "sync-openpgp-key-path = /usr/share/openpgp-keys/gentoo-release.asc\n"
        buf += "sync-openpgp-key-refresh-retry-count = 40\n"
        buf += "sync-openpgp-key-refresh-retry-overall-timeout = 1200\n"
        buf += "sync-openpgp-key-refresh-retry-delay-exp-base = 2\n"
        buf += "sync-openpgp-key-refresh-retry-delay-max = 60\n"
        buf += "sync-openpgp-key-refresh-retry-delay-mult = 4\n"
        return buf

    def get_datadir_path(self):
        return "/var/db/repos/gentoo"


class GentooSnapshot(ManualSyncRepository):

    def __init__(self, date=None):
        if date is not None:
            self._date = date.strftime("%Y%m%d")
        else:
            self._date = "latest"

    def get_name(self):
        return "gentoo"

    def get_datadir_path(self):
        return "/var/db/repos/gentoo"

    def sync(self, datadir_hostpath):
        assert False


class GentooSnapshotArchive(ManualSyncRepository):

    def __init__(self, filepath, digest_filepath=None):
        self._path = filepath
        if self._path.endswith(".lzo.sqfs"):
            self._hashPath = None
        elif self._path.endswith(".xz.sqfs"):
            self._hashPath = None
        elif self._path.endswith(".tar.xz"):
            assert digest_filepath.endswith(".tar.xz.gpgsig") or digest_filepath.endswith(".tar.xz.md5sum") or digest_filepath.endswith(".tar.xz.umd5sum")
            self._hashPath = digest_filepath
        else:
            # FIXME?
            assert False

    def get_name(self):
        return "gentoo"

    def get_datadir_path(self):
        return "/var/db/repos/gentoo"

    def sync(self, datadir_hostpath):
        if self._path.endswith(".lzo.sqfs"):
            assert False
        elif self._path.endswith(".xz.sqfs"):
            assert False
        elif self._path.endswith(".tar.xz"):
            with tarfile.open(self._path, mode="r:xz") as tf:
                tf.extractall(datadir_hostpath)
        else:
            assert False


class GentooFromHost(BindMountRepository):

    def __init__(self, hostdir):
        self._hostDir = hostdir

    def get_name(self):
        return "gentoo"

    def get_datadir_path(self):
        return "/var/db/repos/gentoo"

    def get_hostdir_path(self):
        return self._hostDir
