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
import enum
import pathlib
import robust_layer.simple_fops
from ._util import Util
from ._errors import SettingsError, SeedStageError
from ._settings import Settings, TargetSettings, ComputingPower
from ._prototype import SeedStage, ManualSyncRepository, BindMountRepository, EmergeSyncRepository, CustomScript
from ._workdir import WorkDirChrooter


def Action(*progressStepTuple):
    def decorator(func):
        def wrapper(self, *kargs):
            progressStepList = list(progressStepTuple)
            assert sorted(progressStepList) == list(progressStepList)
            assert self._progress in progressStepList
            self._workDirObj.open_chroot_dir(from_dir_name=self._getChrootDirName())
            func(self, *kargs)
            self._progress = BuildProgress(progressStepList[-1] + 1)
            self._workDirObj.close_chroot_dir(to_dir_name=self._getChrootDirName())
        return wrapper
    return decorator


class BuildProgress(enum.IntEnum):
    STEP_INIT = enum.auto()
    STEP_UNPACKED = enum.auto()
    STEP_REPOSITORIES_INITIALIZED = enum.auto()
    STEP_CONFDIR_INITIALIZED = enum.auto()
    STEP_WORLD_SET_UPDATED = enum.auto()
    STEP_KERNEL_INSTALLED = enum.auto()
    STEP_SERVICES_ENABLED = enum.auto()
    STEP_SYSTEM_CUSTOMIZED = enum.auto()
    STEP_CLEANED_UP = enum.auto()


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

        self._progress = BuildProgress.STEP_INIT
        self._workDirObj.open_chroot_dir()
        self._workDirObj.close_chroot_dir(to_dir_name=self._getChrootDirName())

    def get_progress(self):
        return self._progress

    @Action(BuildProgress.STEP_INIT)
    def action_unpack(self, seed_stage):
        assert isinstance(seed_stage, SeedStage)

        seed_stage.unpack(self._workDirObj.chroot_dir_path)

        t = TargetDirsAndFiles(self._workDirObj.chroot_dir_path)
        os.makedirs(t.logdir_hostpath, exist_ok=True)
        os.makedirs(t.distdir_hostpath, exist_ok=True)
        os.makedirs(t.binpkgdir_hostpath, exist_ok=True)
        if self._ts.build_opts.ccache:
            os.makedirs(t.ccachedir_hostpath, exist_ok=True)

    @Action(BuildProgress.STEP_UNPACKED)
    def action_init_repositories(self):
        for repo in self.repo_list:
            repoOrOverlay = (repo.get_name() == "gentoo")
            if isinstance(repo, ManualSyncRepository):
                _MyRepoUtil.createFromManuSyncRepo(repo, repoOrOverlay, self._workDirObj.chroot_dir_path)
            elif isinstance(repo, BindMountRepository):
                _MyRepoUtil.createFromBindMountRepo(repo, repoOrOverlay, self._workDirObj.chroot_dir_path)
            elif isinstance(repo, EmergeSyncRepository):
                _MyRepoUtil.createFromEmergeSyncRepo(repo, repoOrOverlay, self._workDirObj.chroot_dir_path)
            else:
                assert False

        for repo in self.repo_list:
            if isinstance(repo, ManualSyncRepository):
                repo.sync()

        if any([isinstance(repo, EmergeSyncRepository) for repo in self.repo_list]):
            with _Chrooter(self) as m:
                scriptDirPath, scriptsDirHostPath = m.create_script_dir_in_chroot("scripts")
                Util.shellCall("/bin/cp -r %s/* %s" % (os.path.join(os.path.dirname(os.path.realpath(__file__)), "scripts-in-chroot"), scriptsDirHostPath))
                Util.shellCall("/bin/chmod -R 755 %s/*" % (scriptsDirHostPath))

                m.shell_exec("", "%s/run-merge.sh --sync" % (scriptDirPath))

    @Action(BuildProgress.STEP_REPOSITORIES_INITIALIZED)
    def action_init_confdir(self):
        t = TargetConfDir(self._s, self._ts, self._workDirObj.chroot_dir_path)
        t.write_make_conf()
        t.write_package_use()
        t.write_package_mask()
        t.write_package_unmask()
        t.write_package_accept_keywords()
        t.write_package_license()

    @Action(BuildProgress.STEP_CONFDIR_INITIALIZED)
    def action_update_world_set(self, preprocess_script_list=[]):
        # create installList and write world file
        installList = []
        if True:
            # add from install_list
            for pkg in self._ts.install_list:
                if not Util.portageIsPkgInstalled(self._workDirObj.chroot_dir_path, pkg):
                    installList.append(pkg)
        if True:
            # add from world_set
            t = TargetDirsAndFiles(self._workDirObj.chroot_dir_path)
            with open(t.world_file_hostpath, "w") as f:
                for pkg in self._ts.world_set:
                    if not Util.portageIsPkgInstalled(self._workDirObj.chroot_dir_path, pkg):
                        installList.append(pkg)
                    f.write("%s\n" % (pkg))

        # order installList
        ORDER = [
            "dev-util/ccache",
        ]
        for pkg in reversed(ORDER):
            if pkg in installList:
                installList.remove(pkg)
                installList.insert(0, pkg)

        # install packages, update @world
        with _Chrooter(self) as m:
            for i in range(0, len(preprocess_script_list)):
                m.script_exec("script_%d" % (i), preprocess_script_list[i])

            scriptDirPath, scriptsDirHostPath = m.create_script_dir_in_chroot("scripts")
            Util.shellCall("/bin/cp -r %s/* %s" % (os.path.join(os.path.dirname(os.path.realpath(__file__)), "scripts-in-chroot"), scriptsDirHostPath))
            Util.shellCall("/bin/chmod -R 755 %s/*" % (scriptsDirHostPath))

            for pkg in installList:
                m.shell_exec("", "%s/run-merge.sh -1 %s" % (scriptDirPath, pkg))
            m.shell_exec("", "%s/run-update.sh @world" % (scriptDirPath))

            if m.shell_test("", "which perl-cleaner"):
                out = m.shell_call("", "perl-cleaner --pretend --all")
                if "No package needs to be reinstalled." not in out:
                    raise SeedStageError("perl cleaning is needed, your seed stage is too old")

    @Action(BuildProgress.STEP_WORLD_SET_UPDATED)
    def action_install_kernel(self, preprocess_script_list=[]):
        # FIXME: determine parallelism parameters
        tj = None
        tl = None
        if self._s.host_computing_power.cooling_level <= 1:
            tj = 1
            tl = 1
        else:
            if self._s.host_computing_power.memory_size >= 24 * 1024 * 1024 * 1024:       # >=24G
                tj = self._s.host_computing_power.cpu_core_count + 2
                tl = self._s.host_computing_power.cpu_core_count
            else:
                tj = self._s.host_computing_power.cpu_core_count
                tl = max(1, self._s.host_computing_power.cpu_core_count - 1)

        # FIXME
        with _Chrooter(self) as m:
            for i in range(0, len(preprocess_script_list)):
                m.script_exec("script_%d" % (i), preprocess_script_list[i])

            m.shell_call("", "eselect kernel set 1")

            if self._ts.build_opts.ccache:
                env = "CCACHE_DIR=/var/tmp/ccache"
                opt = "--kernel-cc=/usr/lib/ccache/bin/gcc --utils-cc=/usr/lib/ccache/bin/gcc"
            else:
                env = ""
                opt = ""
            m.shell_exec(env, "genkernel --no-mountboot --makeopts='-j%d -l%d' %s all" % (tj, tl, opt))

    @Action(BuildProgress.STEP_WORLD_SET_UPDATED, BuildProgress.STEP_KERNEL_INSTALLED)
    def action_enable_services(self, preprocess_script_list=[]):
        if len(preprocess_script_list) > 0 or len(self._ts.service_list) > 0:
            with _Chrooter(self) as m:
                for i in range(0, len(preprocess_script_list)):
                    m.script_exec("script_%d" % (i), preprocess_script_list[i])
                for s in self._ts.service_list:
                    m.shell_exec("", "systemctl enable %s" % (s))

    @Action(BuildProgress.STEP_SERVICES_ENABLED)
    def action_customize_system(self, custom_script_list=[]):
        assert all([isinstance(s, CustomScript) for s in custom_script_list])

        if len(custom_script_list) > 0:
            with _Chrooter(self) as m:
                for i in range(0, len(custom_script_list)):
                    m.script_exec("script_%d" % (i), custom_script_list[i])

    @Action(BuildProgress.STEP_SYSTEM_CUSTOMIZED)
    def action_cleanup(self):
        with _Chrooter(self) as m:
            scriptDirPath, scriptsDirHostPath = m.create_script_dir_in_chroot("scripts")
            Util.shellCall("/bin/cp -r %s/* %s" % (os.path.join(os.path.dirname(os.path.realpath(__file__)), "scripts-in-chroot"), scriptsDirHostPath))
            Util.shellCall("/bin/chmod -R 755 %s/*" % (scriptsDirHostPath))

            if not self._ts.degentoo:
                m.shell_call("", "eselect news read all")
                m.shell_exec("", "%s/run-depclean.sh" % (scriptDirPath))
            else:
                # FIXME
                m.shell_exec("", "%s/run-depclean.sh" % (scriptDirPath))
                m.shell_exec("", "%s/run-merge.sh -C sys-devel/gcc" % (scriptDirPath))
                m.shell_exec("", "%s/run-merge.sh -C sys-apps/portage" % (scriptDirPath))

        if not self._ts.degentoo:
            _MyRepoUtil.cleanupReposConfDir(self._workDirObj.chroot_dir_path)
        else:
            # FIXME
            t = TargetDirsAndFiles(self._workDirObj.chroot_dir_path)
            robust_layer.simple_fops.rm(t.confdir_hostpath)
            robust_layer.simple_fops.rm(t.statedir_hostpath)
            robust_layer.simple_fops.rm(t.pkgdbdir_hostpath)
            robust_layer.simple_fops.rm(t.srcdir_hostpath)
            robust_layer.simple_fops.rm(t.logdir_hostpath)
            robust_layer.simple_fops.rm(t.distdir_hostpath)
            robust_layer.simple_fops.rm(t.binpkgdir_hostpath)

    def _getChrootDirName(self):
        return "%02d-%s" % (self._progress.value, self._progress.name)


class _MyRepoUtil:

    @classmethod
    def createFromManuSyncRepo(cls, repo, repoOrOverlay, chrootDir):
        assert isinstance(repo, ManualSyncRepository)

        myRepo = _MyRepo(chrootDir, cls._getReposConfFilename(repo, repoOrOverlay))

        buf = ""
        buf += "[%s]\n" % (repo.get_name())
        buf += "auto-sync = no\n"
        buf += "location = %s\n" % (repo.get_datadir_path())
        cls._writeReposConfFile(myRepo, buf)

        os.makedirs(myRepo.datadir_hostpath, exist_ok=True)

        return myRepo

    @classmethod
    def createFromBindMountRepo(cls, repo, repoOrOverlay, chrootDir):
        assert isinstance(repo, BindMountRepository)

        myRepo = _MyRepo(chrootDir, cls._getReposConfFilename(repo, repoOrOverlay))

        buf = ""
        buf += "[%s]\n" % (repo.get_name())
        buf += "auto-sync = no\n"
        buf += "location = %s\n" % (repo.get_datadir_path())
        buf += "host-dir = %s\n" % (repo.get_hostdir_path())
        cls._writeReposConfFile(myRepo, buf)

        os.makedirs(myRepo.datadir_hostpath, exist_ok=True)

        return myRepo

    @classmethod
    def createFromEmergeSyncRepo(cls, repo, repoOrOverlay, chrootDir):
        assert isinstance(repo, EmergeSyncRepository)

        myRepo = _MyRepo(chrootDir, cls._getReposConfFilename(repo, repoOrOverlay))

        buf = repo.get_repos_conf_file_content()
        cls._writeReposConfFile(myRepo, buf)

        os.makedirs(myRepo.datadir_hostpath, exist_ok=True)

        return myRepo

    @classmethod
    def scanReposConfDir(cls, chrootDir):
        return [_MyRepo(chrootDir, x) for x in os.listdir(cls._getReposConfDir(chrootDir))]

    @classmethod
    def cleanupReposConfDir(cls, chrootDir):
        Util.shellCall("/bin/sed '/host-dir = /d' %s/*" % (cls._getReposConfDir(chrootDir)))

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

    @staticmethod
    def _writeReposConfFile(myRepo, buf):
        os.makedirs(os.path.dirname(myRepo.repos_conf_file_hostpath), exist_ok=True)
        with open(myRepo.repos_conf_file_hostpath, "w") as f:
            f.write(buf)


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

    def get_hostdir(self):
        m = re.search(r'host-dir = (\S+)', pathlib.Path(self.repos_conf_file_hostpath).read_text(), re.M)
        return m.group(1) if m is not None else None


class _Chrooter(WorkDirChrooter):

    def __init__(self, parent):
        self._p = parent
        self._w = parent._workDirObj
        super().__init__(self._w)

    def bind(self):
        super().bind()
        try:
            self._bindMountList = []
            self._scriptDirList = []

            t = TargetDirsAndFiles(self._w.chroot_dir_path)

            # log directory mount point
            if self._p._s.log_dir is not None:
                assert os.path.exists(t.logdir_hostpath) and not Util.isMount(t.logdir_hostpath)
                Util.shellCall("/bin/mount --bind \"%s\" \"%s\"" % (self._p._s.log_dir, t.logdir_hostpath))
                self._bindMountList.append(t.logdir_hostpath)

            # distdir mount point
            if self._p._s.host_distfiles_dir is not None:
                assert os.path.exists(t.distdir_hostpath) and not Util.isMount(t.distdir_hostpath)
                Util.shellCall("/bin/mount --bind \"%s\" \"%s\"" % (self._p._s.host_distfiles_dir, t.distdir_hostpath))
                self._bindMountList.append(t.distdir_hostpath)

            # pkgdir mount point
            if self._p._s.host_packages_dir is not None:
                assert os.path.exists(t.binpkgdir_hostpath) and not Util.isMount(t.binpkgdir_hostpath)
                Util.shellCall("/bin/mount --bind \"%s\" \"%s\"" % (self._p._s.host_packages_dir, t.binpkgdir_hostpath))
                self._bindMountList.append(t.binpkgdir_hostpath)

            # ccachedir mount point
            if self._p._s.host_ccache_dir is not None and os.path.exists(t.ccachedir_hostpath):
                assert os.path.exists(t.ccachedir_hostpath) and not Util.isMount(t.ccachedir_hostpath)
                Util.shellCall("/bin/mount --bind \"%s\" \"%s\"" % (self._p._s.host_ccache_dir, t.ccachedir_hostpath))
                self._bindMountList.append(t.ccachedir_hostpath)

            # mount points for BindMountRepository
            for myRepo in _MyRepoUtil.scanReposConfDir(self._w.chroot_dir_path):
                if myRepo.get_hostdir() is not None:
                    assert os.path.exists(myRepo.datadir_hostpath) and not Util.isMount(myRepo.datadir_hostpath)
                    Util.shellCall("/bin/mount --bind \"%s\" \"%s\" -o ro" % (myRepo.get_hostdir(), myRepo.datadir_hostpath))
                    self._bindMountList.append(myRepo.datadir_hostpath)
        except BaseException:
            self.unbind()
            raise

    def unbind(self):
        if hasattr(self, "_scriptDirList"):
            # exec directories are in tmpfs, no need to delete
            del self._scriptDirList
        if hasattr(self, "_bindMountList"):
            for fullfn in reversed(self._bindMountList):
                Util.cmdCall("/bin/umount", "-l", fullfn)
            del self._bindMountList
        super().unbind()

    def create_script_dir_in_chroot(self, dir_name):
        assert self.binded
        path = os.path.join("/tmp", dir_name)
        hostPath = os.path.join(self._w.chroot_dir_path, path[1:])

        assert not os.path.exists(hostPath)
        os.makedirs(hostPath, mode=0o755)

        self._scriptDirList.append(hostPath)
        return path, hostPath

    def script_exec(self, dir_name, scriptObj):
        print(scriptObj.get_description())
        scriptDirPath, scriptsDirHostPath = self.create_script_dir_in_chroot("script_%s" % (dir_name))
        scriptObj.fill_script_dir(scriptsDirHostPath)
        self.shell_exec("", os.path.join(scriptDirPath, scriptObj.get_script()))


class TargetDirsAndFiles:

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


class TargetConfDir:

    def __init__(self, settings, targetSettings, chrootDir):
        self._s = settings
        self._ts = targetSettings
        self._dir = TargetDirsAndFiles(chrootDir).confdir_hostpath

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
            myf.write('EMERGE_DEFAULT_OPTS="--quiet-build=y %s"\n' % (' '.join(paraEmergeOpts)))
            myf.write('\n')

    def write_package_use(self):
        # Modify and write out package.use (in chroot)
        fpath = os.path.join(self._dir, "package.use")
        robust_layer.simple_fops.rm(fpath)
        with open(fpath, "w") as myf:
            # compile all locales
            myf.write("*/* compile-locales")

            # write cusom USE flags
            for pkg_wildcard, use_flag_list in self._ts.pkg_use.items():
                if "compile-locales" in use_flag_list:
                    raise SettingsError("USE flag \"compile-locales\" is not allowed")
                if "-compile-locales" in use_flag_list:
                    raise SettingsError("USE flag \"-compile-locales\" is not allowed")
                myf.write("%s %s\n" % (pkg_wildcard, " ".join(use_flag_list)))

    def write_package_mask(self):
        # Modify and write out package.mask (in chroot)
        fpath = os.path.join(self._dir, "package.mask")
        robust_layer.simple_fops.rm(fpath)
        with open(fpath, "w") as myf:
            for pkg_wildcard in self._ts.pkg_mask:
                myf.write("%s\n" % (pkg_wildcard))

    def write_package_unmask(self):
        # Modify and write out package.unmask (in chroot)
        fpath = os.path.join(self._dir, "package.unmask")
        robust_layer.simple_fops.rm(fpath)
        with open(fpath, "w") as myf:
            for pkg_wildcard in self._ts.pkg_unmask:
                myf.write("%s\n" % (pkg_wildcard))

    def write_package_accept_keywords(self):
        # Modify and write out package.accept_keywords (in chroot)
        fpath = os.path.join(self._dir, "package.accept_keywords")
        robust_layer.simple_fops.rm(fpath)
        with open(fpath, "w") as myf:
            for pkg_wildcard, keyword_list in self._ts.pkg_accept_keywords.items():
                myf.write("%s %s\n" % (pkg_wildcard, " ".join(keyword_list)))

    def write_package_license(self):
        # Modify and write out package.license (in chroot)
        fpath = os.path.join(self._dir, "package.license")
        robust_layer.simple_fops.rm(fpath)
        with open(fpath, "w") as myf:
            for pkg_wildcard, license_list in self._ts.pkg_license.items():
                myf.write("%s %s\n" % (pkg_wildcard, " ".join(license_list)))
