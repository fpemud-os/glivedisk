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
import copy
import enum
import pathlib
import robust_layer.simple_fops
from ._util import Util
from ._errors import SettingsError, SeedStageError
from ._settings import HostComputingPower, MY_NAME
from ._prototype import SeedStage
from ._prototype import ManualSyncRepository
from ._prototype import BindMountRepository
from ._prototype import EmergeSyncRepository
from ._prototype import LaymanRepository
from ._workdir import WorkDirChrooter


def Action(progress_step):
    def decorator(func):
        def wrapper(self, *kargs):
            def __createNewChrootDir():
                dirName = "%02d-%s" % (self._progress.value, BuildProgress(self._progress.value + 1).name)
                self._workDirObj.create_new_chroot_dir(dirName)

            # check, ensure chroot dir
            assert self._progress == progress_step
            if not self._workDirObj.has_chroot_dir():
                __createNewChrootDir()

            # do work
            func(self, *kargs)

            # do progress, create new chroot dir for next step
            self._progress = BuildProgress(self._progress + 1)
            __createNewChrootDir()

        return wrapper

    return decorator


class BuildProgress(enum.IntEnum):
    STEP_INIT = enum.auto()
    STEP_UNPACKED = enum.auto()
    STEP_GENTOO_REPOSITORY_INITIALIZED = enum.auto()
    STEP_CONFDIR_INITIALIZED = enum.auto()
    STEP_SYSTEM_SET_UPDATED = enum.auto()
    STEP_OVERLAYS_INITIALIZED = enum.auto()
    STEP_WORLD_SET_UPDATED = enum.auto()
    STEP_KERNEL_INSTALLED = enum.auto()
    STEP_SYSTEM_CONFIGURED = enum.auto()
    STEP_CLEANED_UP = enum.auto()


class Builder:
    """
    This class does all of the chroot setup, copying of files, etc.
    It is the driver class for pretty much everything that glivedisk does.
    """

    def __init__(self, program_name, host_computing_power, seed_stage, work_dir, settings, verbose=False):
        assert program_name is not None
        assert HostComputingPower.check_object(host_computing_power)
        assert isinstance(seed_stage, SeedStage)
        assert work_dir.verify_existing(raise_exception=False)

        settings = copy.deepcopy(settings)

        self._progName = program_name
        self._cpower = host_computing_power
        self._tf = seed_stage
        self._workDirObj = work_dir
        self._target = _SettingTarget(settings)
        self._hostInfo = _SettingHostInfo(settings)
        self._bVerbose = verbose
        self._progress = BuildProgress.STEP_INIT

        for k in settings:
            raise SettingsError("redundant key \"%s\" in settings" % (k))

        os.makedirs(self._hostInfo.log_dir, mode=0o750, exist_ok=True)

    def get_progress(self):
        return self._progress

    @Action(BuildProgress.STEP_INIT)
    def action_unpack(self):
        self._tf.unpack(self._workDirObj.chroot_dir_path)

        t = TargetDirs(self._workDirObj.chroot_dir_path)
        t.ensure_logdir()
        t.ensure_distdir()
        t.ensure_pkgdir()

    @Action(BuildProgress.STEP_UNPACKED)
    def action_init_gentoo_repository(self, repo):
        if repo.get_name() != "gentoo":
            raise SettingsError("invalid repository")

        if isinstance(repo, ManualSyncRepository):
            _MyRepoUtil.createFromManuSyncRepo(repo, True, self._workDirObj.chroot_dir_path)
            repo.sync()
        elif isinstance(repo, BindMountRepository):
            _MyRepoUtil.createFromBindMountRepo(repo, True, self._workDirObj.chroot_dir_path)
        elif isinstance(repo, EmergeSyncRepository):
            _MyRepoUtil.createFromEmergeSyncRepo(repo, True, self._workDirObj.chroot_dir_path)
            with _Chrooter(self) as m:
                m.script_exec("", "emaint sync -f %s" % (repo.get_name()))
        else:
            assert False

    @Action(BuildProgress.STEP_GENTOO_REPOSITORY_INITIALIZED)
    def action_init_confdir(self):
        t = TargetConfDir(self._progName, self._workDirObj.chroot_dir_path, self._target, self._cpower)
        t.write_make_conf()
        t.write_package_use()
        t.write_package_mask()
        t.write_package_unmask()
        t.write_package_accept_keywords()
        t.write_package_license()

    @Action(BuildProgress.STEP_CONFDIR_INITIALIZED)
    def action_update_system_set(self):
        with _Chrooter(self) as m:
            m.script_exec("", "run-merge.sh -uDN --with-bdeps=y @system")

    @Action(BuildProgress.STEP_SYSTEM_SET_UPDATED)
    def action_init_overlays(self, overlays):
        for o in overlays:
            if isinstance(o, ManualSyncRepository):
                _MyRepoUtil.createFromManuSyncRepo(o, False, self._workDirObj.chroot_dir_path)
                o.sync()
            elif isinstance(o, BindMountRepository):
                _MyRepoUtil.createFromBindMountRepo(o, False, self._workDirObj.chroot_dir_path)
            elif isinstance(o, EmergeSyncRepository):
                _MyRepoUtil.createFromEmergeSyncRepo(o, False, self._workDirObj.chroot_dir_path)
            elif isinstance(o, LaymanRepository):
                pass
            else:
                assert False

        with _Chrooter(self) as m:
            if any([isinstance(o, LaymanRepository) for o in overlays]):
                m.script_exec("", "run_merge app-portage/layman")
                m.shell_exec("", "layman -f")

            for o in overlays:
                if isinstance(o, ManualSyncRepository):
                    pass
                elif isinstance(o, BindMountRepository):
                    pass
                elif isinstance(o, EmergeSyncRepository):
                    m.shell_exec("", "emaint sync -f %s" % (o.get_name()))
                elif isinstance(o, LaymanRepository):
                    m.shell_exec("", "layman -a %s" % (o.get_name()))
                else:
                    assert False

    @Action(BuildProgress.STEP_OVERLAYS_INITIALIZED)
    def action_update_world_set(self):
        if len(self._target.world_set) == 0:
            return

        installList = []
        for pkg in self._target.world_set:
            if not Util.portageIsPkgInstalled(self._workDirObj.chroot_dir_path, pkg):
                installList.append(pkg)

        with _Chrooter(self) as m:
            for pkg in installList:
                m.script_exec("", "run-merge.sh %s" % (pkg))
            m.script_exec("", "run-merge.sh -uDN --with-bdeps=y @world")

            if m.shell_test("", "which perl-cleaner"):
                out = m.shell_call("", "perl-cleaner --pretend --all")
                if "No package needs to be reinstalled." not in out:
                    raise SeedStageError("perl cleaning is needed, your seed stage is too old")

    @Action(BuildProgress.STEP_WORLD_SET_UPDATED)
    def action_install_kernel(self, kernel_installer):
        kernel_installer.install(self._progName, self._cpower, self._workDirObj)

    @Action(BuildProgress.STEP_KERNEL_INSTALLED)
    def action_config_system(self):
        with _Chrooter(self) as m:
            # set locale
            m.shell_call("", "eselect locale set %s" % (self._target.locale))

            # set timezone
            m.shell_call("", "eselect timezone set %s" % (self._target.timezone))

            # set editor
            m.shell_call("", "eselect editor set %s" % (self._target.editor))

    @Action(BuildProgress.STEP_SYSTEM_CONFIGURED)
    def action_cleanup(self):
        with _Chrooter(self) as m:
            m.shell_call("", "eselect news read all")
            m.script_exec("", "run-depclean.sh")

        _MyRepoUtil.cleanupReposConfDir(self._workDirObj.chroot_dir_path)


class _SettingTarget:

    def __init__(self, settings):
        if "profile" in settings:
            self.profile = settings["profile"]
            del settings["profile"]
        else:
            self.profile = None

        if "world_set" in settings:
            self.world_set = list(settings["world_set"])
            del settings["world_set"]
        else:
            self.world_set = []

        if "pkg_use" in settings:
            self.pkg_use = dict(settings["pkg_use"])  # dict<package-wildcard, use-flag-list>
            del settings["pkg_use"]
        else:
            self.pkg_use = dict()

        if "pkg_mask" in settings:
            self.pkg_mask = dict(settings["pkg_mask"])  # list<package-wildcard>
            del settings["pkg_mask"]
        else:
            self.pkg_mask = []

        if "pkg_unmask" in settings:
            self.pkg_unmask = dict(settings["pkg_unmask"])  # list<package-wildcard>
            del settings["pkg_unmask"]
        else:
            self.pkg_unmask = []

        if "pkg_accept_keywords" in settings:
            self.pkg_accept_keywords = dict(settings["pkg_accept_keywords"])  # dict<package-wildcard, accept-keyword-list>
            del settings["pkg_accept_keywords"]
        else:
            self.pkg_accept_keywords = dict()

        if "pkg_license" in settings:
            self.pkg_license = dict(settings["pkg_license"])  # dict<package-wildcard, license-list>
            del settings["pkg_license"]
        else:
            self.pkg_license = dict()

        if "install_mask" in settings:
            self.install_mask = dict(settings["install_mask"])  # list<install-mask>
            del settings["install_mask"]
        else:
            self.install_mask = []

        if "pkg_install_mask" in settings:
            self.pkg_install_mask = dict(settings["pkg_install_mask"])  # dict<package-wildcard, install-mask>
            del settings["pkg_install_mask"]
        else:
            self.pkg_install_mask = dict()

        if "build_opts" in settings:
            self.build_opts = _SettingBuildOptions("build_opts", settings["build_opts"])  # list<build-opts>
            del settings["build_opts"]
        else:
            self.build_opts = None

        if "pkg_build_opts" in settings:
            self.pkg_build_opts = {k: _SettingBuildOptions("build_opts of %s" % (k), v) for k, v in settings["pkg_build_opts"].items()}  # dict<package-wildcard, build-opts>
            del settings["pkg_build_opts"]
        else:
            self.pkg_build_opts = dict()

        if "locale" in settings:
            self.locale = settings["locale"]
            if self.locale is None:
                raise SettingsError("Invalid value for key \"locale\"")
            del settings["locale"]
        else:
            self.locale = "C.utf8"

        if "timezone" in settings:
            self.timezone = settings["timezone"]
            if self.timezone is None:
                raise SettingsError("Invalid value for key \"timezone\"")
            del settings["timezone"]
        else:
            self.timezone = "UTC"

        if "editor" in settings:
            self.editor = settings["editor"]
            if self.editor is None:
                raise SettingsError("Invalid value for key \"editor\"")
            del settings["editor"]
        else:
            self.editor = "nano"


class _SettingBuildOptions:

    def __init__(self, name, settings):
        if "common_flags" in settings:
            self.common_flags = list(settings["common_flags"])
            del settings["common_flags"]
        else:
            self.common_flags = []

        if "cflags" in settings:
            self.cflags = list(settings["cflags"])
            del settings["cflags"]
        else:
            self.cflags = []

        if "cxxflags" in settings:
            self.cxxflags = list(settings["cxxflags"])
            del settings["cxxflags"]
        else:
            self.cflags = []

        if "fcflags" in settings:
            self.fcflags = list(settings["fcflags"])
            del settings["fcflags"]
        else:
            self.fcflags = []

        if "fflags" in settings:
            self.fflags = list(settings["fflags"])
            del settings["fflags"]
        else:
            self.fflags = []

        if "ldflags" in settings:
            self.ldflags = list(settings["ldflags"])
            del settings["ldflags"]
        else:
            self.ldflags = []

        if "asflags" in settings:
            self.asflags = list(settings["asflags"])
            del settings["asflags"]
        else:
            self.asflags = []

        for k in settings:
            raise SettingsError("redundant key \"%s\" in %s" % (k, name))


class _SettingHostInfo:

    def __init__(self, settings):
        # log directory in host system, will be bind mounted in target system
        if "log_dir" in settings:
            self.log_dir = settings["log_dir"]
            del settings["log_dir"]
        else:
            self.log_dir = os.path.join("/var", "log", MY_NAME)

        # distfiles directory in host system
        if "host_distfiles_dir" in settings:
            self.distfiles_dir = settings["host_distfiles_dir"]
            del settings["host_distfiles_dir"]
        else:
            self.distfiles_dir = None

        # packages directory in host system
        if "host_packages_dir" in settings:
            self.packages_dir = settings["host_packages_dir"]
            del settings["host_packages_dir"]
        else:
            self.packages_dir = None


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


class _Chrooter:

    def __init__(self, parent):
        self._parent = parent
        self._chrooter = WorkDirChrooter(self._parent._workDirObj)

        self._bBind = False
        self._bindMountList = []

    def __enter__(self):
        self.bind()
        return self

    def __exit__(self, type, value, traceback):
        self.unbind()

    @property
    def binded(self):
        return self._chrooter.binded

    def bind(self):
        self._chrooter.bind()

        assert not self._bBind
        try:
            t = TargetDirs(self._parent._workDirObj.chroot_dir_path)

            # log_dir mount point
            self._chrooter._assertDirStatus(t.logdir_path)
            Util.shellCall("/bin/mount --bind \"%s\" \"%s\"" % (self._parent._hostInfo.log_dir, t.logdir_hostpath))
            self._bindMountList.append(t.logdir_hostpath)

            # distdir mount point
            if self._parent._hostInfo.distfiles_dir is not None:
                self._chrooter._assertDirStatus(t.distdir_path)
                Util.shellCall("/bin/mount --bind \"%s\" \"%s\"" % (self._parent._hostInfo.distfiles_dir, t.distdir_hostpath))
                self._bindMountList.append(t.distdir_hostpath)

            # pkgdir mount point
            if self._parent._hostInfo.packages_dir is not None:
                self._chrooter._assertDirStatus(t.pkgdir_path)
                Util.shellCall("/bin/mount --bind \"%s\" \"%s\"" % (self._parent._hostInfo.packages_dir, t.pkgdir_hostpath))
                self._bindMountList.append(t.pkgdir_hostpath)

            # mount points for BindMountRepository
            for myRepo in _MyRepoUtil.scanReposConfDir(self._parent._workDirObj.chroot_dir_path):
                hostDir = myRepo.get_hostdir()
                if hostDir is not None:
                    self._chrooter._assertDirStatus(myRepo.datadir_path)
                    Util.shellCall("/bin/mount --bind \"%s\" \"%s\" -o ro" % (hostDir, myRepo.datadir_hostpath))
                    self._bindMountList.append(myRepo.datadir_hostpath)
        except BaseException:
            self._unbind()
            self._chrooter.unbind()
            raise
        self._bBind = True

    def unbind(self):
        assert self._bBind
        self._unbind()
        self._bBind = False

        self._chrooter.unbind()

    def shell_call(self, env, cmd):
        self._chrooter.shell_call(env, cmd)

    def shell_test(self, env, cmd):
        self._chrooter.shell_test(env, cmd)

    def shell_exec(self, env, cmd, quiet=False):
        self._chrooter.shell_exec(env, cmd, quiet)

    def script_exec(self, env, cmd, quiet=False):
        self._chrooter.script_exec(env, cmd, quiet)

    def _unbind(self):
        for fullfn in self._bindMountList:
            Util.cmdCall("/bin/umount", "-l", fullfn)
        self._bindMountList = []


class TargetDirs:

    def __init__(self, chrootDir):
        self._chroot_path = chrootDir

    @property
    def logdir_hostpath(self):
        return os.path.join(self._chroot_path, self.logdir_path[1:])

    @property
    def distdir_hostpath(self):
        return os.path.join(self._chroot_path, self.distdir_path[1:])

    @property
    def pkgdir_hostpath(self):
        return os.path.join(self._chroot_path, self.pkgdir_path[1:])

    @property
    def logdir_path(self):
        return "/var/log/portage"

    @property
    def distdir_path(self):
        return "/var/cache/distfiles"

    @property
    def pkgdir_path(self):
        return "/var/cache/binpkgs"

    def ensure_logdir(self):
        os.makedirs(self.logdir_hostpath, exist_ok=True)

    def ensure_distdir(self):
        os.makedirs(self.distdir_hostpath, exist_ok=True)

    def ensure_pkgdir(self):
        os.makedirs(self.pkgdir_hostpath, exist_ok=True)


class TargetConfDir:

    def __init__(self, program_name, chrootDir, target, host_computing_power):
        self._progName = program_name
        self._dir = chrootDir
        self._target = target
        self._computing_power = host_computing_power

    def write_make_conf(self):
        # determine parallelism parameters
        paraMakeOpts = None
        paraEmergeOpts = None
        if True:
            if self._computing_power.cooling_level <= 1:
                jobcountMake = 1
                jobcountEmerge = 1
                loadavg = 1
            else:
                if self._computing_power.memory_size >= 24 * 1024 * 1024 * 1024:       # >=24G
                    jobcountMake = self._computing_power.cpu_core_count + 2
                    jobcountEmerge = self._computing_power.cpu_core_count
                    loadavg = self._computing_power.cpu_core_count
                else:
                    jobcountMake = self._computing_power.cpu_core_count
                    jobcountEmerge = self._computing_power.cpu_core_count
                    loadavg = max(1, self._computing_power.cpu_core_count - 1)

            paraMakeOpts = ["--jobs=%d" % (jobcountMake), "--load-average=%d" % (loadavg), "-j%d" % (jobcountMake), "-l%d" % (loadavg)]     # for bug 559064 and 592660, we need to add -j and -l, it sucks
            paraEmergeOpts = ["--jobs=%d" % (jobcountEmerge), "--load-average=%d" % (loadavg)]

        # define helper functions
        def __flagsWrite(flags, value):
            if value is None and self._target.build_opts.common_flags is not None:
                myf.write('%s="${COMMON_FLAGS}"\n' % (flags))
            else:
                if isinstance(value, list):
                    myf.write('%s="%s"\n' % (flags, ' '.join(value)))
                else:
                    myf.write('%s="%s"\n' % (flags, value))

        # Modify and write out make.conf (in chroot)
        makepath = os.path.join(self._dir, "etc", "portage", "make.conf")
        with open(makepath, "w") as myf:
            myf.write("# These settings were set by %s that automatically built this stage.\n" % (self._progName))
            myf.write("# Please consult /usr/share/portage/config/make.conf.example for a more detailed example.\n")
            myf.write("\n")

            # flags
            if self._target.build_opts is not None:
                if self._target.build_opts.common_flags is not None:
                    myf.write('COMMON_FLAGS="%s"\n' % (' '.join(self._target.build_opts.common_flags)))
                __flagsWrite("CFLAGS", self._target.build_opts.cflags)
                __flagsWrite("CXXFLAGS", self._target.build_opts.cxxflags)
                __flagsWrite("FCFLAGS", self._target.build_opts.fcflags)
                __flagsWrite("FFLAGS", self._target.build_opts.fflags)
                __flagsWrite("LDFLAGS", self._target.build_opts.ldflags)
                __flagsWrite("ASFLAGS", self._target.build_opts.asflags)
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
        fpath = os.path.join(self._dir, "etc", "portage", "package.use")
        robust_layer.simple_fops.rm(fpath)
        with open(fpath, "w") as myf:
            # compile all locales
            myf.write("*/* compile-locales")

            # write cusom USE flags
            for pkg_wildcard, use_flag_list in self._target.pkg_use.items():
                if "compile-locales" in use_flag_list:
                    raise SettingsError("USE flag \"compile-locales\" is not allowed")
                if "-compile-locales" in use_flag_list:
                    raise SettingsError("USE flag \"-compile-locales\" is not allowed")
                myf.write("%s %s\n" % (pkg_wildcard, " ".join(use_flag_list)))

    def write_package_mask(self):
        # Modify and write out package.mask (in chroot)
        fpath = os.path.join(self._dir, "etc", "portage", "package.mask")
        robust_layer.simple_fops.rm(fpath)
        with open(fpath, "w") as myf:
            for pkg_wildcard in self._target.pkg_mask:
                myf.write("%s\n" % (pkg_wildcard))

    def write_package_unmask(self):
        # Modify and write out package.unmask (in chroot)
        fpath = os.path.join(self._dir, "etc", "portage", "package.unmask")
        robust_layer.simple_fops.rm(fpath)
        with open(fpath, "w") as myf:
            for pkg_wildcard in self._target.pkg_unmask:
                myf.write("%s\n" % (pkg_wildcard))

    def write_package_accept_keywords(self):
        # Modify and write out package.accept_keywords (in chroot)
        fpath = os.path.join(self._dir, "etc", "portage", "package.accept_keywords")
        robust_layer.simple_fops.rm(fpath)
        with open(fpath, "w") as myf:
            for pkg_wildcard, keyword_list in self._target.pkg_accept_keywords.items():
                myf.write("%s %s\n" % (pkg_wildcard, " ".join(keyword_list)))

    def write_package_license(self):
        # Modify and write out package.license (in chroot)
        fpath = os.path.join(self._dir, "etc", "portage", "package.license")
        robust_layer.simple_fops.rm(fpath)
        with open(fpath, "w") as myf:
            for pkg_wildcard, license_list in self._target.pkg_license.items():
                myf.write("%s %s\n" % (pkg_wildcard, " ".join(license_list)))
