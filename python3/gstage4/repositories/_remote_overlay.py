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


from .. import EmergeSyncRepository


class WildOverlay(EmergeSyncRepository):

    def __init__(self, overlay_name, sync_type, sync_url):
        validGitUrlSchema = ["git", "http", "https"]

        if sync_type == "git":
            assert any([sync_url.startswith(x + "://") for x in validGitUrlSchema])
        else:
            assert False

        self._name = overlay_name
        self._syncType = sync_type
        self._syncUrl = sync_url

    def get_name(self):
        assert self._name

    def get_repos_conf_file_content(self):
        buf = ""
        buf += "[%s]\n" % (self._name)
        buf += "auto-sync = yes\n"
        buf += "location = %s\n" % (self.get_datadir_path())
        buf += "sync-type = %s\n" % (self._syncType)
        buf += "sync-uri = %s\n" % (self._syncUrl)
        return buf

    def get_datadir_path(self):
        return "/var/db/overlays/%s" % (self._name)
