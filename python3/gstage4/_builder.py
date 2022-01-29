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
import re
import json
import enum
import pathlib
import robust_layer.simple_fops
from ._util import Util
from ._prototype import SeedStage
from ._prototype import ManualSyncRepository
from ._prototype import MountRepository
from ._prototype import EmergeSyncRepository
from ._prototype import ScriptInChroot
from ._errors import SettingsError
from ._settings import Settings
from ._settings import TargetSettings
from ._chrooter import Chrooter
from .scripts import ScriptFromBuffer


def Action(*progressStepTuple):
    def decorator(func):
        def wrapper(self, *kargs, **kwargs):
            progressStepList = list(progressStepTuple)
            assert sorted(progressStepList) == list(progressStepList)
            assert self._progress in progressStepList
            self._workDirObj.open_chroot_dir(from_dir_name=self._getChrootDirName())
            func(self, *kargs, **kwargs)
            self._progress = BuildStep(progressStepList[-1] + 1)
            self._workDirObj.close_chroot_dir(to_dir_name=self._getChrootDirName())
        return wrapper
    return decorator


class BuildStep(enum.IntEnum):
    INIT = enum.auto()
    UNPACKED = enum.auto()
    GENTOO_REPOSITORY_CREATED = enum.auto()
    CONFDIR_INITIALIZED = enum.auto()
    OVERLAYS_CREATED = enum.auto()
    WORLD_UPDATED = enum.auto()
    KERNEL_INSTALLED = enum.auto()
    SERVICES_ENABLED = enum.auto()
    SYSTEM_CUSTOMIZED = enum.auto()
    CLEANED_UP = enum.auto()


class Builder:
    """
    This class does all of the chroot setup, copying of files, etc.
    It is the driver class for pretty much everything that gstage4 does.
    """

    def __init__(self, settings, target_settings, work_dir):
        assert Settings.check_object(settings, raise_exception=False)
        assert TargetSettings.check_object(target_settings, raise_exception=False)
        assert work_dir.verify_existing(raise_exception=False)

        self._s = settings
        if self._s.log_dir is not None:
            os.makedirs(self._s.log_dir, mode=0o750, exist_ok=True)

        self._ts = target_settings
        if self._ts.build_opts.ccache and self._s.host_ccache_dir is None:
            raise SettingsError("ccache is enabled but host ccache directory is not specified")

        self._workDirObj = work_dir

        self._progress = BuildStep.INIT
        self._workDirObj.open_chroot_dir()
        self._workDirObj.close_chroot_dir(to_dir_name=self._getChrootDirName())

    def get_progress(self):
        return self._progress

    @Action(BuildStep.INIT)
    def action_unpack(self, seed_stage):
        assert isinstance(seed_stage, SeedStage)
        assert seed_stage.get_arch() == self._ts.arch

        seed_stage.unpack(self._workDirObj.chroot_dir_path)

        t = TargetFilesAndDirs(self._workDirObj.chroot_dir_path)
        os.makedirs(t.logdir_hostpath, exist_ok=True)
        os.makedirs(t.distdir_hostpath, exist_ok=True)
        os.makedirs(t.binpkgdir_hostpath, exist_ok=True)
        if self._ts.build_opts.ccache:
            os.makedirs(t.ccachedir_hostpath, exist_ok=True)
        with open(t.world_file_hostpath, "w") as f:
            f.write("")

    @Action(BuildStep.UNPACKED)
    def action_create_gentoo_repository(self, repo):
        assert repo.get_name() == "gentoo"

        if isinstance(repo, ManualSyncRepository):
            _MyRepoUtil.createFromManuSyncRepo(repo, True, self._workDirObj.chroot_dir_path)
            repo.sync(os.path.join(self._workDirObj.chroot_dir_path, repo.get_datadir_path()[1:]))
        elif isinstance(repo, EmergeSyncRepository):
            myRepo = _MyRepoUtil.createFromEmergeSyncRepo(repo, True, self._workDirObj.chroot_dir_path)
            assert myRepo.get_sync_type() == "rsync"
            with _MyChrooter(self) as m:
                m.script_exec(ScriptSync(), quiet=self._getQuiet())
        elif isinstance(repo, MountRepository):
            _MyRepoUtil.createFromMountRepo(repo, True, self._workDirObj.chroot_dir_path)
        else:
            assert False

    @Action(BuildStep.GENTOO_REPOSITORY_CREATED)
    def action_init_confdir(self):
        if self._ts.profile is not None:
            with _MyChrooter(self) as m:
                m.shell_call("", "eselect profile set %s" % (self._ts.profile))

        t = TargetConfDirWriter(self._s, self._ts, self._workDirObj.chroot_dir_path)
        t.write_make_conf()
        t.write_package_use()
        t.write_package_mask()
        t.write_package_unmask()
        t.write_package_accept_keywords()
        t.write_package_license()
        t.write_use_mask()

    @Action(BuildStep.CONFDIR_INITIALIZED)
    def action_create_overlays(self, preprocess_script_list=[], overlay_list=[]):
        assert overlay_list is not None
        assert all([Util.isInstanceList(x, ManualSyncRepository, EmergeSyncRepository, MountRepository) for x in overlay_list])
        assert not any([x.get_name() == "gentoo" for x in overlay_list])
        assert len([x.get_name() for x in overlay_list]) == len(set([x.get_name() for x in overlay_list]))        # no duplication
        if len(overlay_list) == 0:
            assert len(preprocess_script_list) == 0

        overlayRecord = dict()
        pkgSet = set()
        for overlay in overlay_list:
            if isinstance(overlay, ManualSyncRepository):
                _MyRepoUtil.createFromManuSyncRepo(overlay, False, self._workDirObj.chroot_dir_path)
            elif isinstance(overlay, EmergeSyncRepository):
                myRepo = _MyRepoUtil.createFromEmergeSyncRepo(overlay, False, self._workDirObj.chroot_dir_path)
                syncType = myRepo.get_sync_type()
                if syncType == "rsync":
                    pass
                elif syncType == "git":
                    pkgSet.add("dev-vcs/git")
                else:
                    assert False
                overlayRecord[overlay.get_name()] = syncType
            elif isinstance(overlay, MountRepository):
                _MyRepoUtil.createFromMountRepo(overlay, False, self._workDirObj.chroot_dir_path)
            else:
                assert False

        if len(preprocess_script_list) > 0 or any([isinstance(repo, EmergeSyncRepository) for repo in overlay_list]):
            with _MyChrooter(self) as m:
                for s in preprocess_script_list:
                    m.script_exec(s, quiet=self._getQuiet())

                installList = [x for x in pkgSet if not Util.portageIsPkgInstalled(self._workDirObj.chroot_dir_path, x)]
                m.script_exec(ScriptInstallPackages(installList, self._s.verbose_level), quiet=self._getQuiet())

                if any([isinstance(repo, EmergeSyncRepository) for repo in overlay_list]):
                    m.script_exec(ScriptSync(), quiet=self._getQuiet())

        for overlay in overlay_list:
            if isinstance(overlay, ManualSyncRepository):
                overlay.sync(os.path.join(self._workDirObj.chroot_dir_path, overlay.get_datadir_path()[1:]))

        self._workDirObj.save_record("overlays", json.dumps(overlayRecord))

    @Action(BuildStep.OVERLAYS_CREATED)
    def action_update_world(self, preprocess_script_list=[], install_list=[], world_set=set()):
        assert len(world_set & set(install_list)) == 0
        assert all([isinstance(s, ScriptInChroot) for s in preprocess_script_list])

        def __pkgNeeded(pkg):
            if pkg not in install_list and pkg not in world_set:
                raise SettingsError("package %s is needed" % (pkg))

        def __worldNeeded(pkg):
            if pkg not in world_set:
                raise SettingsError("package %s is needed" % (pkg))

        # check
        if self._ts.package_manager == "portage":
            __worldNeeded("sys-apps/portage")
        else:
            assert False

        if self._ts.kernel_manager == "none":
            pass
        elif self._ts.kernel_manager == "genkernel":
            __pkgNeeded("sys-kernel/genkernel")
        elif self._ts.kernel_manager == "fake":
            pass
        else:
            assert False

        if self._ts.service_manager == "none":
            pass
        elif self._ts.service_manager == "openrc":
            __worldNeeded("sys-apps/openrc")
        elif self._ts.service_manager == "systemd":
            __worldNeeded("sys-apps/systemd")
        else:
            assert False

        if self._ts.build_opts.ccache:
            __pkgNeeded("dev-util/ccache")

        overlayRecord = json.loads(self._workDirObj.load_record("overlays", default_value=json.dumps({})))
        if "git" in overlayRecord.values():
            __worldNeeded("dev-vcs/git")

        # create installList
        ORDER = [
            "dev-util/ccache",
        ]
        installList = sorted(install_list + list(world_set))
        for pkg in reversed(ORDER):
            if pkg in installList:
                installList.remove(pkg)
                installList.insert(0, pkg)

        # write world file
        t = TargetFilesAndDirs(self._workDirObj.chroot_dir_path)
        with open(t.world_file_hostpath, "w") as f:
            for pkg in world_set:
                f.write("%s\n" % (pkg))

        # preprocess, install packages, update @world
        with _MyChrooter(self) as m:
            for s in preprocess_script_list:
                m.script_exec(s, quiet=self._getQuiet())

            installList = [x for x in installList if not Util.portageIsPkgInstalled(self._workDirObj.chroot_dir_path, x)]
            m.script_exec(ScriptInstallPackages(installList, self._s.verbose_level), quiet=self._getQuiet())

            m.script_exec(ScriptUpdateWorld(self._s.verbose_level), quiet=self._getQuiet())

    @Action(BuildStep.WORLD_UPDATED)
    def action_install_kernel(self, preprocess_script_list=[]):
        assert all([isinstance(s, ScriptInChroot) for s in preprocess_script_list])

        if self._ts.kernel_manager == "none":
            assert len(preprocess_script_list) == 0
            return

        if self._ts.kernel_manager == "genkernel":
            t = TargetConfDirParser(self._workDirObj.chroot_dir_path)
            tj = t.get_make_conf_make_opts_jobs()
            tl = t.get_make_conf_load_average()

            with _MyChrooter(self) as m:
                for s in preprocess_script_list:
                    m.script_exec(s, quiet=self._getQuiet())

                m.shell_call("", "eselect kernel set 1")

                dotConfigFile = "/usr/src/dot-config"
                if not os.path.exists(os.path.join(self._workDirObj.chroot_dir_path, dotConfigFile[1:])):
                    dotConfigFile = None
                m.script_exec(ScriptGenkernel(self._s.verbose_level, tj, tl, self._ts.build_opts.ccache, dotConfigFile), quiet=self._getQuiet())

            return

        if self._ts.kernel_manager == "fake":
            bootDir = os.path.join(self._workDirObj.chroot_dir_path, "boot")
            os.makedirs(bootDir, exist_ok=True)
            with open(os.path.join(bootDir, "vmlinuz"), "w") as f:
                f.write("fake kernel")
            with open(os.path.join(bootDir, "initramfs.img"), "w") as f:
                f.write("fake initramfs")
            return

        assert False

    @Action(BuildStep.WORLD_UPDATED, BuildStep.KERNEL_INSTALLED)
    def action_enable_services(self, preprocess_script_list=[], service_list=[]):
        assert all([isinstance(s, ScriptInChroot) for s in preprocess_script_list])
        if len(service_list) == 0:
            assert len(preprocess_script_list) == 0

        if self._ts.service_manager == "none":
            assert len(preprocess_script_list) == 0
            assert len(service_list) == 0
            return

        if len(service_list) > 0:
            with _MyChrooter(self) as m:
                for s in preprocess_script_list:
                    m.script_exec(s, quiet=self._getQuiet())
                for s in service_list:
                    if self._ts.service_manager == "openrc":
                        m.shell_exec("", "rc-update add %s default > /dev/null" % (s))
                    elif self._ts.service_manager == "systemd":
                        m.shell_exec("", "systemctl enable %s -q" % (s))
                    else:
                        assert False

    @Action(BuildStep.WORLD_UPDATED, BuildStep.KERNEL_INSTALLED, BuildStep.SERVICES_ENABLED)
    def action_customize_system(self, custom_script_list=[]):
        assert all([isinstance(s, ScriptInChroot) for s in custom_script_list])

        if len(custom_script_list) > 0:
            with _MyChrooter(self) as m:
                for s in custom_script_list:
                    m.script_exec(s, quiet=self._getQuiet())

    @Action(BuildStep.CONFDIR_INITIALIZED, BuildStep.OVERLAYS_CREATED, BuildStep.WORLD_UPDATED, BuildStep.KERNEL_INSTALLED, BuildStep.SERVICES_ENABLED, BuildStep.SYSTEM_CUSTOMIZED)
    def action_cleanup(self):
        with _MyChrooter(self) as m:
            if not self._ts.degentoo:
                m.shell_call("", "eselect news read all")
                m.script_exec(ScriptDepClean(self._s.verbose_level), quiet=self._getQuiet())
            else:
                # FIXME
                m.script_exec(ScriptDepClean(self._s.verbose_level), quiet=self._getQuiet())
                # m.shell_exec("", "%s/run-merge.sh -C sys-devel/gcc" % (scriptDirPath))
                # m.shell_exec("", "%s/run-merge.sh -C sys-apps/portage" % (scriptDirPath))

        if not self._ts.degentoo:
            t = TargetConfDirCleaner(self._workDirObj.chroot_dir_path)
            t.cleanup_repos_conf_dir()
            t.cleanup_make_conf()
        else:
            # FIXME
            t = TargetFilesAndDirs(self._workDirObj.chroot_dir_path)
            robust_layer.simple_fops.rm(t.confdir_hostpath)
            robust_layer.simple_fops.rm(t.statedir_hostpath)
            robust_layer.simple_fops.rm(t.pkgdbdir_hostpath)
            robust_layer.simple_fops.rm(t.srcdir_hostpath)
            robust_layer.simple_fops.rm(t.logdir_hostpath)
            robust_layer.simple_fops.rm(t.distdir_hostpath)
            robust_layer.simple_fops.rm(t.binpkgdir_hostpath)

    def _getChrootDirName(self):
        return "%02d-%s" % (self._progress.value, self._progress.name)

    def _getQuiet(self):
        return (self._s.verbose_level == 0)


class _MyRepoUtil:

    @classmethod
    def createFromManuSyncRepo(cls, repo, repoOrOverlay, chrootDir):
        assert isinstance(repo, ManualSyncRepository)

        buf = ""
        buf += "[%s]\n" % (repo.get_name())
        buf += "auto-sync = no\n"
        buf += "location = %s\n" % (repo.get_datadir_path())

        myRepo = _MyRepo(chrootDir, cls._getReposConfFilename(repo, repoOrOverlay))
        myRepo.write_repos_conf_file(buf)
        os.makedirs(myRepo.datadir_hostpath, exist_ok=True)

        return myRepo

    @classmethod
    def createFromMountRepo(cls, repo, repoOrOverlay, chrootDir):
        assert isinstance(repo, MountRepository)

        buf = ""
        buf += "[%s]\n" % (repo.get_name())
        buf += "auto-sync = no\n"
        buf += "location = %s\n" % (repo.get_datadir_path())
        if True:
            src, mntOpts = repo.get_mount_params()
            buf += "mount-params = \"%s\",\"%s\"\n" % (src, mntOpts)

        myRepo = _MyRepo(chrootDir, cls._getReposConfFilename(repo, repoOrOverlay))
        myRepo.write_repos_conf_file(buf)
        os.makedirs(myRepo.datadir_hostpath, exist_ok=True)

        return myRepo

    @classmethod
    def createFromEmergeSyncRepo(cls, repo, repoOrOverlay, chrootDir):
        assert isinstance(repo, EmergeSyncRepository)

        buf = repo.get_repos_conf_file_content()

        myRepo = _MyRepo(chrootDir, cls._getReposConfFilename(repo, repoOrOverlay))
        myRepo.write_repos_conf_file(buf)
        os.makedirs(myRepo.datadir_hostpath, exist_ok=True)

        return myRepo

    @classmethod
    def scanReposConfDir(cls, chrootDir):
        return [_MyRepo(chrootDir, x) for x in os.listdir(cls._getReposConfDir(chrootDir))]

    @classmethod
    def cleanupReposConfDir(cls, chrootDir):
        Util.shellCall("sed '/mount-params = /d' %s/*" % (cls._getReposConfDir(chrootDir)))

    @staticmethod
    def _getReposConfDir(chrootDir):
        return os.path.join(chrootDir, "etc/portage/repos.conf")

    @staticmethod
    def _getReposConfFilename(repo, repoOrOverlay):
        if repoOrOverlay:
            fullname = repo.get_name()
        else:
            fullname = "overlay-" + repo.get_name()
        return fullname + ".conf"


class _MyRepo:

    def __init__(self, chroot_dir, repos_conf_file_name):
        self._chroot_path = chroot_dir
        self._repos_conf_file_name = repos_conf_file_name

    @property
    def repos_conf_file_hostpath(self):
        return os.path.join(self._chroot_path, self.repos_conf_file_path[1:])

    @property
    def datadir_hostpath(self):
        return os.path.join(self._chroot_path, self.datadir_path[1:])

    @property
    def repos_conf_file_path(self):
        return "/etc/portage/repos.conf/%s" % (self._repos_conf_file_name)

    @property
    def datadir_path(self):
        return re.search(r'location = (\S+)', pathlib.Path(self.repos_conf_file_hostpath).read_text(), re.M).group(1)

    def write_repos_conf_file(self, buf):
        os.makedirs(os.path.dirname(self.repos_conf_file_hostpath), exist_ok=True)
        with open(self.repos_conf_file_hostpath, "w") as f:
            f.write(buf)

    def get_sync_type(self):
        m = re.search(r'sync-type = (\S+)', pathlib.Path(self.repos_conf_file_hostpath).read_text(), re.M)
        return m.group(1) if m is not None else None

    def get_mount_params(self):
        m = re.search(r'mount-params = "(.*)","(.*)"', pathlib.Path(self.repos_conf_file_hostpath).read_text(), re.M)
        return (m.group(1), m.group(2)) if m is not None else None


class _MyChrooter(Chrooter):

    def __init__(self, parent):
        super().__init__(parent._workDirObj.chroot_dir_path)
        self._p = parent
        self._w = parent._workDirObj
        self._bindMountList = []

    def bind(self):
        super().bind()
        try:
            t = TargetFilesAndDirs(self._w.chroot_dir_path)

            # log directory mount point
            if self._p._s.log_dir is not None:
                assert os.path.exists(t.logdir_hostpath) and not Util.isMount(t.logdir_hostpath)
                Util.shellCall("mount --bind \"%s\" \"%s\"" % (self._p._s.log_dir, t.logdir_hostpath))
                self._bindMountList.append(t.logdir_hostpath)

            # distdir mount point
            if self._p._s.host_distfiles_dir is not None:
                assert os.path.exists(t.distdir_hostpath) and not Util.isMount(t.distdir_hostpath)
                Util.shellCall("mount --bind \"%s\" \"%s\"" % (self._p._s.host_distfiles_dir, t.distdir_hostpath))
                self._bindMountList.append(t.distdir_hostpath)

            # pkgdir mount point
            if self._p._s.host_packages_dir is not None:
                assert os.path.exists(t.binpkgdir_hostpath) and not Util.isMount(t.binpkgdir_hostpath)
                Util.shellCall("mount --bind \"%s\" \"%s\"" % (self._p._s.host_packages_dir, t.binpkgdir_hostpath))
                self._bindMountList.append(t.binpkgdir_hostpath)

            # ccachedir mount point
            if self._p._s.host_ccache_dir is not None and os.path.exists(t.ccachedir_hostpath):
                assert os.path.exists(t.ccachedir_hostpath) and not Util.isMount(t.ccachedir_hostpath)
                Util.shellCall("mount --bind \"%s\" \"%s\"" % (self._p._s.host_ccache_dir, t.ccachedir_hostpath))
                self._bindMountList.append(t.ccachedir_hostpath)

            # mount points for MountRepository
            for myRepo in _MyRepoUtil.scanReposConfDir(self._w.chroot_dir_path):
                mp = myRepo.get_mount_params()
                if mp is not None:
                    assert os.path.exists(myRepo.datadir_hostpath) and not Util.isMount(myRepo.datadir_hostpath)
                    Util.shellCall("mount \"%s\" \"%s\" -o %s" % (mp[0], myRepo.datadir_hostpath, (mp[1] + ",ro") if mp[1] != "" else "ro"))
                    self._bindMountList.append(myRepo.datadir_hostpath)
        except BaseException:
            self.unbind(remove_scripts=False)
            raise

    def unbind(self):
        for fullfn in reversed(self._bindMountList):
            Util.cmdCall("umount", "-l", fullfn)
        self._bindMountList = []
        super().unbind()


class TargetFilesAndDirs:

    def __init__(self, chrootDir):
        self._chroot_path = chrootDir

    @property
    def confdir_path(self):
        return "/etc/portage"

    @property
    def statedir_path(self):
        return "/var/lib/portage"

    @property
    def pkgdbdir_path(self):
        return "/var/db/pkg"

    @property
    def logdir_path(self):
        return "/var/log/portage"

    @property
    def distdir_path(self):
        return "/var/cache/distfiles"

    @property
    def binpkgdir_path(self):
        return "/var/cache/binpkgs"

    @property
    def ccachedir_path(self):
        return "/var/tmp/ccache"

    @property
    def srcdir_path(self):
        return "/usr/src"

    @property
    def world_file_path(self):
        return "/var/lib/portage/world"

    @property
    def confdir_hostpath(self):
        return os.path.join(self._chroot_path, self.confdir_path[1:])

    @property
    def statedir_hostpath(self):
        return os.path.join(self._chroot_path, self.statedir_path[1:])

    @property
    def pkgdbdir_hostpath(self):
        return os.path.join(self._chroot_path, self.pkgdbdir_path[1:])

    @property
    def logdir_hostpath(self):
        return os.path.join(self._chroot_path, self.logdir_path[1:])

    @property
    def distdir_hostpath(self):
        return os.path.join(self._chroot_path, self.distdir_path[1:])

    @property
    def binpkgdir_hostpath(self):
        return os.path.join(self._chroot_path, self.binpkgdir_path[1:])

    @property
    def ccachedir_hostpath(self):
        return os.path.join(self._chroot_path, self.ccachedir_path[1:])

    @property
    def srcdir_hostpath(self):
        return os.path.join(self._chroot_path, self.srcdir_path[1:])

    @property
    def world_file_hostpath(self):
        return os.path.join(self._chroot_path, self.world_file_path[1:])


class TargetConfDirWriter:

    def __init__(self, settings, targetSettings, chrootDir):
        self._s = settings
        self._ts = targetSettings
        self._dir = TargetFilesAndDirs(chrootDir).confdir_hostpath

    def write_make_conf(self):
        # determine parallelism parameters
        paraMakeOpts = None
        paraEmergeOpts = None
        if True:
            if self._s.host_computing_power.cooling_level <= 1:
                jobcountMake = 1
                jobcountEmerge = 1
                loadavg = 1
            else:
                if self._s.host_computing_power.memory_size >= 24 * 1024 * 1024 * 1024:       # >=24G
                    jobcountMake = self._s.host_computing_power.cpu_core_count + 2
                    jobcountEmerge = self._s.host_computing_power.cpu_core_count
                    loadavg = self._s.host_computing_power.cpu_core_count
                else:
                    jobcountMake = self._s.host_computing_power.cpu_core_count
                    jobcountEmerge = self._s.host_computing_power.cpu_core_count
                    loadavg = max(1, self._s.host_computing_power.cpu_core_count - 1)

            paraMakeOpts = ["--jobs=%d" % (jobcountMake), "--load-average=%d" % (loadavg), "-j%d" % (jobcountMake), "-l%d" % (loadavg)]     # for bug 559064 and 592660, we need to add -j and -l, it sucks
            paraEmergeOpts = ["--jobs=%d" % (jobcountEmerge), "--load-average=%d" % (loadavg)]

        # define helper functions
        def __flagsWrite(flags, value):
            if value is None:
                if self._ts.build_opts.common_flags is None:
                    pass
                else:
                    myf.write('%s="${COMMON_FLAGS}"\n' % (flags))
            else:
                if isinstance(value, list):
                    myf.write('%s="%s"\n' % (flags, ' '.join(value)))
                else:
                    myf.write('%s="%s"\n' % (flags, value))

        # Modify and write out make.conf (in chroot)
        makepath = os.path.join(self._dir, "make.conf")
        with open(makepath, "w") as myf:
            myf.write("# These settings were set by %s that automatically built this stage.\n" % (self._s.program_name))
            myf.write("# Please consult /usr/share/portage/config/make.conf.example for a more detailed example.\n")
            myf.write("\n")

            # features
            featureList = []
            if self._ts.build_opts.ccache:
                featureList.append("ccache")
            if len(featureList) > 0:
                myf.write('FEATURES="%s"\n' % (" ".join(featureList)))
                myf.write('\n')

            # flags
            if self._ts.build_opts.common_flags is not None:
                myf.write('COMMON_FLAGS="%s"\n' % (' '.join(self._ts.build_opts.common_flags)))
            __flagsWrite("CFLAGS", self._ts.build_opts.cflags)
            __flagsWrite("CXXFLAGS", self._ts.build_opts.cxxflags)
            __flagsWrite("FCFLAGS", self._ts.build_opts.fcflags)
            __flagsWrite("FFLAGS", self._ts.build_opts.fflags)
            __flagsWrite("LDFLAGS", self._ts.build_opts.ldflags)
            __flagsWrite("ASFLAGS", self._ts.build_opts.asflags)
            myf.write('\n')

            # set default locale for system responses. #478382
            myf.write('LC_MESSAGES=C\n')
            myf.write('\n')

            # set MAKEOPTS and EMERGE_DEFAULT_OPTS
            myf.write('MAKEOPTS="%s"\n' % (' '.join(paraMakeOpts)))
            myf.write('EMERGE_DEFAULT_OPTS="--quiet-build=y --autounmask --autounmask-continue --autounmask-license=y %s"\n' % (' '.join(paraEmergeOpts)))
            myf.write('\n')

    def write_package_use(self):
        # Modify and write out package.use (in chroot)
        fpath = os.path.join(self._dir, "package.use")
        robust_layer.simple_fops.rm(fpath)

        # generate main file content
        # buf = "*/* compile-locales\n"   # compile all locales
        buf = ""
        for pkg_wildcard, use_flag_list in self._ts.pkg_use.items():
            if "compile-locales" in use_flag_list:
                raise SettingsError("USE flag \"compile-locales\" is not allowed")
            if "-compile-locales" in use_flag_list:
                raise SettingsError("USE flag \"-compile-locales\" is not allowed")
            buf += "%s %s\n" % (pkg_wildcard, " ".join(use_flag_list))

        if len(self._ts.pkg_use_files) > 0:
            # create directory
            os.mkdir(fpath)
            for file_name, file_content in self._ts.pkg_use_files.items():
                with open(os.path.join(fpath, file_name), "w") as myf:
                    myf.write(file_content)
            with open(os.path.join(fpath, "90-main"), "w") as myf:
                # create this file even if content is empty
                myf.write(buf)
            with open(os.path.join(fpath, "99-autouse"), "w") as myf:
                myf.write("")
        else:
            # create file
            with open(fpath, "w") as myf:
                myf.write(buf)

    def write_package_mask(self):
        # Modify and write out package.mask (in chroot)
        fpath = os.path.join(self._dir, "package.mask")
        robust_layer.simple_fops.rm(fpath)

        # generate main file content
        buf = ""
        for pkg_wildcard in self._ts.pkg_mask:
            buf += "%s\n" % (pkg_wildcard)

        if len(self._ts.pkg_mask_files) > 0:
            # create directory
            os.mkdir(fpath)
            for file_name, file_content in self._ts.pkg_mask_files.items():
                with open(os.path.join(fpath, file_name), "w") as myf:
                    myf.write(file_content)
            with open(os.path.join(fpath, "90-main"), "w") as myf:
                # create this file even if content is empty
                myf.write(buf)
            with open(os.path.join(fpath, "99-bugmask"), "w") as myf:
                myf.write("")
        else:
            # create file
            with open(fpath, "w") as myf:
                myf.write(buf)

    def write_package_unmask(self):
        # Modify and write out package.unmask (in chroot)
        fpath = os.path.join(self._dir, "package.unmask")
        robust_layer.simple_fops.rm(fpath)

        # generate main file content
        buf = ""
        for pkg_wildcard in self._ts.pkg_unmask:
            buf += "%s\n" % (pkg_wildcard)

        if len(self._ts.pkg_unmask_files) > 0:
            # create directory
            os.mkdir(fpath)
            for file_name, file_content in self._ts.pkg_unmask_files.items():
                with open(os.path.join(fpath, file_name), "w") as myf:
                    myf.write(file_content)
            with open(os.path.join(fpath, "90-main"), "w") as myf:
                # create this file even if content is empty
                myf.write(buf)
        else:
            # create file
            with open(fpath, "w") as myf:
                myf.write(buf)

    def write_package_accept_keywords(self):
        # Modify and write out package.accept_keywords (in chroot)
        fpath = os.path.join(self._dir, "package.accept_keywords")
        robust_layer.simple_fops.rm(fpath)

        # generate main file content
        buf = ""
        for pkg_wildcard, keyword_list in self._ts.pkg_accept_keywords.items():
            buf += "%s %s\n" % (pkg_wildcard, " ".join(keyword_list))

        if len(self._ts.pkg_accept_keywords_files) > 0:
            # create directory
            os.mkdir(fpath)
            for file_name, file_content in self._ts.pkg_accept_keywords_files.items():
                with open(os.path.join(fpath, file_name), "w") as myf:
                    myf.write(file_content)
            with open(os.path.join(fpath, "90-main"), "w") as myf:
                # create this file even if content is empty
                myf.write(buf)
            with open(os.path.join(fpath, "99-autokeyword"), "w") as myf:
                myf.write("")
        else:
            # create this file only if content is not empty
            with open(fpath, "w") as myf:
                myf.write(buf)

    def write_package_license(self):
        # Modify and write out package.license (in chroot)
        fpath = os.path.join(self._dir, "package.license")
        robust_layer.simple_fops.rm(fpath)

        # generate main file content
        buf = ""
        for pkg_wildcard, license_list in self._ts.pkg_license.items():
            buf += "%s %s\n" % (pkg_wildcard, " ".join(license_list))

        if len(self._ts.pkg_license_files) > 0:
            # create directory
            os.mkdir(fpath)
            for file_name, file_content in self._ts.pkg_license_files.items():
                with open(os.path.join(fpath, file_name), "w") as myf:
                    myf.write(file_content)
            with open(os.path.join(fpath, "90-main"), "w") as myf:
                # create this file even if content is empty
                myf.write(buf)
            with open(os.path.join(fpath, "99-autolicense"), "w") as myf:
                myf.write("")
        else:
            # create this file only if content is not empty
            if buf != "":
                with open(fpath, "w") as myf:
                    myf.write(buf)

    def write_use_mask(self):
        # Modify and write out use.mask (in chroot)
        if len(self._ts.use_mask) > 0:
            fpath = os.path.join(self._dir, "profile", "use.mask")
            os.makedirs(os.path.dirname(fpath), exist_ok=True)
            with open(fpath, "w") as myf:
                for use_flag in self._ts.use_mask:
                    myf.write("%s\n" % (use_flag))


class TargetConfDirParser:

    def __init__(self, chrootDir):
        self._dir = TargetFilesAndDirs(chrootDir).confdir_hostpath

    def get_make_conf_make_opts_jobs(self):
        buf = pathlib.Path(os.path.join(self._dir, "make.conf")).read_text()

        m = re.search("MAKEOPTS=\".*--jobs=([0-9]+).*\"", buf, re.M)
        if m is not None:
            return int(m.group(1))

        m = re.search("MAKEOPTS=\".*-j([0-9]+).*\"", buf, re.M)
        if m is not None:
            return int(m.group(1))

        assert False

    def get_make_conf_load_average(self):
        buf = pathlib.Path(os.path.join(self._dir, "make.conf")).read_text()
        m = re.search("EMERGE_DEFAULT_OPTS=\".*--load-average=([0-9]+).*\"", buf, re.M)
        if m is not None:
            return int(m.group(1))
        assert False


class TargetConfDirCleaner:

    def __init__(self, chrootDir):
        self._dir = TargetFilesAndDirs(chrootDir).confdir_hostpath

    def cleanup_repos_conf_dir(self):
        Util.shellCall("sed -i '/mount-params = /d' %s/repos.conf/*" % (self._dir))

    def cleanup_make_conf(self):
        # FIXME: remove remaining spaces
        Util.shellCall("sed -i 's/--autounmask-continue//g' %s/make.conf" % (self._dir))
        Util.shellCall("sed -i 's/--autounmask-license=y//g' %s/make.conf" % (self._dir))
        Util.shellCall("sed -i 's/--autounmask//g' %s/make.conf" % (self._dir))


class ScriptSync(ScriptFromBuffer):

    def __init__(self):
        super().__init__("Sync repositories", self._scriptContent)

    _scriptContent = """
#!/bin/bash

export EMERGE_WARNING_DELAY=0
export CLEAN_DELAY=0
export EBEEP_IGNORE=0
export EPAUSE_IGNORE=0

emerge --sync || exit 1
"""


class ScriptInstallPackages(ScriptFromBuffer):

    def __init__(self, pkgList, verbose_level):
        buf = self._scriptContentFirstHalf
        if verbose_level == 0:
            buf += self._scriptContentSecondHalfVerboseLv0
        elif verbose_level == 1:
            buf += self._scriptContentSecondHalfVerboseLv1
        elif verbose_level == 2:
            buf += self._scriptContentSecondHalfVerboseLv2
        else:
            assert False
        buf = buf.replace("@@PKG_NAME@@", " ".join(pkgList))

        if len(pkgList) > 1:
            desc = "Install %d packages" % (len(pkgList))
        else:
            desc = "Install package %s" % (pkgList[0])

        super().__init__(desc, buf)

    _scriptContentFirstHalf = """
#!/bin/bash

export EMERGE_WARNING_DELAY=0
export CLEAN_DELAY=0
export EBEEP_IGNORE=0
export EPAUSE_IGNORE=0
export CONFIG_PROTECT="-* .x"
"""

    _scriptContentSecondHalfVerboseLv0 = """
emerge --color=y -1 @@PKG_NAME@@ > /var/log/portage/run-merge.log 2>&1 || exit 1
"""

    _scriptContentSecondHalfVerboseLv1 = """
# using grep to only show:
#   >>> Emergeing ...
#   >>> Installing ...
#   >>> Uninstalling ...
emerge --color=y -1 @@PKG_NAME@@ 2>&1 | tee /var/log/portage/run-merge.log | grep -E --color=never "^>>> .*\\(.*[0-9]+.*of.*[0-9]+.*\\)"
test ${PIPESTATUS[0]} -eq 0 || exit 1
"""

    _scriptContentSecondHalfVerboseLv2 = """
emerge --color=y -1 @@PKG_NAME@@ 2>&1 | tee /var/log/portage/run-update.log
test ${PIPESTATUS[0]} -eq 0 || exit 1
"""


class ScriptUpdateWorld(ScriptFromBuffer):

    def __init__(self, verbose_level):
        buf = self._scriptContentFirstHalf
        if verbose_level == 0:
            buf += self._scriptContentSecondHalfVerboseLv0
        elif verbose_level == 1:
            buf += self._scriptContentSecondHalfVerboseLv1
        elif verbose_level == 2:
            buf += self._scriptContentSecondHalfVerboseLv2
        else:
            assert False
        buf += self._scriptContentThirdHalf

        super().__init__("Update @world", buf)

    _scriptContentFirstHalf = """
#!/bin/bash

die() {
    echo "$1"
    exit 1
}

export EMERGE_WARNING_DELAY=0
export CLEAN_DELAY=0
export EBEEP_IGNORE=0
export EPAUSE_IGNORE=0
export CONFIG_PROTECT="-* .x"
"""

    _scriptContentSecondHalfVerboseLv0 = """
emerge --color=y -uDN --with-bdeps=y @world > /var/log/portage/run-update.log 2>&1 || exit 1
"""

    _scriptContentSecondHalfVerboseLv1 = """
# using grep to only show:
#   >>> Emergeing ...
#   >>> Installing ...
#   >>> Uninstalling ...
#   >>> No outdated packages were found on your system.
emerge --color=y -uDN --with-bdeps=y @world 2>&1 | tee /var/log/portage/run-update.log | grep -E --color=never "^>>> (.*\\(.*[0-9]+.*of.*[0-9]+.*\\)|No outdated packages .*)"
test ${PIPESTATUS[0]} -eq 0 || exit 1
"""

    _scriptContentSecondHalfVerboseLv2 = """
emerge --color=y -uDN --with-bdeps=y @world 2>&1 | tee /var/log/portage/run-update.log
test ${PIPESTATUS[0]} -eq 0 || exit 1
"""

    _scriptContentThirdHalf = """
perl-cleaner --pretend --all >/dev/null 2>&1 || die "perl cleaning is needed, your seed stage is too old"
"""


class ScriptGenkernel(ScriptFromBuffer):

    def __init__(self, verbose_level, tj, tl, ccache, customDotConfigFile):
        buf = "#!/bin/bash\n"
        buf += "\n"

        if ccache:
            buf += "export CCACHE_DIR=/var/tmp/ccache\n"
            buf += "\n"

        cmd = ""
        if True:
            cmd += "genkernel --color --no-mountboot "
            if customDotConfigFile is not None:
                cmd += "--kernel-config=%s " % (customDotConfigFile)
            cmd += "--kernel-filename=vmlinuz --initramfs-filename=initramfs.img --kernel-config-filename=kernel-config "
            cmd += "--all-ramdisk-modules "
            cmd += "--makeopts='-j%d -l%d' " % (tj, tl)
            if ccache:
                cmd += "--kernel-cc=/usr/lib/ccache/bin/gcc --utils-cc=/usr/lib/ccache/bin/gcc "
            cmd += "all"

        if verbose_level == 0:
            buf += cmd + " > /var/log/portage/genkernel.log 2>&1\n"
        elif verbose_level in [1, 2]:
            buf += cmd + " 2>&1 | tee /var/log/portage/genkernel.log\n"
        else:
            assert False

        super().__init__("Install kernel", buf)


class ScriptDepClean(ScriptFromBuffer):

    def __init__(self, verbose_level):
        buf = self._scriptContent
        if verbose_level == 0:
            buf = buf.replace("%OUTPUT%", "> /var/log/portage/run-depclean.log 2>&1")
        elif verbose_level in [1, 2]:
            buf = buf.replace("%OUTPUT%", "2>&1 | tee /var/log/portage/run-depclean.log")
        else:
            assert False

        super().__init__("Clean system", buf)

    _scriptContent = """
#!/bin/bash

export EMERGE_WARNING_DELAY=0
export CLEAN_DELAY=0
export EBEEP_IGNORE=0
export EPAUSE_IGNORE=0
export CONFIG_PROTECT="-* .x"

emerge --depclean %OUTPUT%
"""
