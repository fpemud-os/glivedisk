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


import abc


class SeedStage(abc.ABC):

    @abc.abstractmethod
    def get_digest(self):
        pass

    @abc.abstractmethod
    def unpack(self, target_dir):
        pass


class ManualSyncRepository(abc.ABC):

    @abc.abstractmethod
    def get_name(self):
        pass

    @abc.abstractmethod
    def get_datadir_path(self):
        pass

    @abc.abstractmethod
    def sync(self, datadir_hostpath):
        pass


class BindMountRepository(abc.ABC):

    @abc.abstractmethod
    def get_name(self):
        pass

    @abc.abstractmethod
    def get_datadir_path(self):
        pass

    @abc.abstractmethod
    def get_hostdir_path(self):
        pass


class EmergeSyncRepository(abc.ABC):

    @abc.abstractmethod
    def get_name(self):
        pass

    @abc.abstractmethod
    def get_repos_conf_file_content(self):
        pass

    @abc.abstractmethod
    def get_datadir_path(self):
        pass


class ScriptInChroot(abc.ABC):

    @abc.abstractmethod
    def fill_script_dir(self, script_dir_hostpath):
        pass

    @abc.abstractmethod
    def get_description(self):
        pass

    @abc.abstractmethod
    def get_script(self):
        pass

    def __eq__(self, other):
        if not isinstance(other, ScriptInChroot):
            return False
        if self.get_description() != other.get_description():
            return False
        return True

    def __ne__(self, other):
        return (not self.__eq__(other))


class TargetFeature:

    # def __init__(self):
    #     protoMethodList = [{x[2:]:inspect.signature() for x in dir(self) if x.startswith("__update")]
    #     methodList = [x for x in v if not x.startswith("_") and callable(x)]

    #     for m in methodList:
    #         if m in protoMethodList:

    #     print(dir(MyClass))

    # it's more like a convension, not interface definition
    # we don't encourage using preprocessing scripts

    def __update_target_settings(self, target_settings, dry_run=False):
        pass

    def __update_repositories(self, repo_list, dry_run=False):
        pass

    def __update_install_list(self, install_list, dry_run=False):
        pass

    def __update_world_set(self, world_set, dry_run=False):
        pass

    def __update_service_list(self, service_list, dry_run=False):
        pass

    def __update_custom_script_list(self, custom_script_list, dry_run=False):
        pass
