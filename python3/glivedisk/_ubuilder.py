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
import copy
import enum
from ._util import Util
from ._errors import SettingsError, SeedStageError
from ._settings import HostComputingPower
from ._seed import SeedStageArchive
from ._workdir import WorkDirChrooter


def Action(progress_step):
    def decorator(func):
        def wrapper(self):
            # check
            assert self._progress == progress_step

            # create new chroot dir
            dirName = "%02d-%s" % (self._progress.value, UserSpaceBuildProgress(self._progress.value + 1).name)
            self._workDirObj.create_new_chroot_dir(dirName)

            # do work
            func(self)

            # do progress
            self._progress = UserSpaceBuildProgress(self._progress + 1)

        return wrapper

    return decorator


class UserSpaceBuildProgress(enum.IntEnum):
    STEP_INIT = enum.auto()
    STEP_UNPACKED = enum.auto()
    STEP_GENTOO_REPOSITORY_INITIALIZED = enum.auto()
    STEP_CONFDIR_INITIALIZED = enum.auto()
    STEP_SYSTEM_SET_UPDATED = enum.auto()
    STEP_OVERLAYS_INITIALIZED = enum.auto()
    STEP_WORLD_SET_UPDATED = enum.auto()
    STEP_SYSTEM_CONFIGURED = enum.auto()


class UserSpaceBuilder:
    """
    This class does all of the chroot setup, copying of files, etc.
    It is the driver class for pretty much everything that glivedisk does.
    """

    def __init__(self, program_name, host_computing_power, seed_stage_archive, work_dir, settings):
        assert program_name is not None
        assert HostComputingPower.check_object(host_computing_power)
        assert SeedStageArchive.check_object(seed_stage_archive)
        assert work_dir.verify_existing(raise_exception=False)

        settings = copy.deepcopy(settings)

        self._progName = program_name
        self._cpower = host_computing_power
        self._tf = seed_stage_archive
        self._workDirObj = work_dir
        self._target = _SettingTarget(settings)
        self._hostInfo = _SettingHostInfo(settings)
        self._progress = UserSpaceBuildProgress.STEP_INIT

        for k in settings:
            raise SettingsError("redundant key \"%s\" in settings" % (k))

    def get_progress(self): 
        return self._progress

    def dispose(self):
        self._progress = None
        self._hostInfo = None
        self._target = None
        self._workDirObj = None
        self._tf = None

    @Action(UserSpaceBuildProgress.STEP_INIT)
    def action_unpack(self):
        self._tf.extractall(self._workDirObj.chroot_dir_path)

        t = TargetCacheDirs(self._workDirObj.chroot_dir_path)
        t.ensure_distdir()
        t.ensure_pkgdir()

    @Action(UserSpaceBuildProgress.STEP_UNPACKED)
    def action_init_gentoo_repository(self):
        # init gentoo repository
        t = TargetGentooRepo(self._workDirObj.chroot_dir_path, self._hostInfo.gentoo_repository_dir)
        t.write_repos_conf()
        t.ensure_datadir()

        # sync gentoo repository
        if self._hostInfo.gentoo_repository_dir is None:
            with _Chrooter(self) as m:
                m.run_chroot_script("", "/usr/bin/emerge --sync")

    @Action(UserSpaceBuildProgress.STEP_GENTOO_REPOSITORY_INITIALIZED)
    def action_init_confdir(self):
        t = TargetConfDir(self._progName, self._workDirObj.chroot_dir_path, self._target, self._hostInfo)
        t.write_make_conf()
        t.write_package_use()
        t.write_package_mask()
        t.write_package_unmask()
        t.write_package_accept_keyword()
        t.write_package_accept_license()

    @Action(UserSpaceBuildProgress.STEP_CONFDIR_INITIALIZED)
    def action_update_system_set(self):
        with _Chrooter(self) as m:
            m.run_chroot_script("", "update-system-set.sh")

    @Action(UserSpaceBuildProgress.STEP_SYSTEM_SET_UPDATED)
    def action_init_overlays(self):
        # init host overlays
        if self._hostInfo.overlays is not None:
            for o in self._hostInfo.overlays:
                t = TargetHostOverlay(self._workDirObj.chroot_dir_path, o)
                t.write_repos_conf()
                t.ensure_datadir()

        # init overlays
        with _Chrooter(self) as m:
            # FIXME: use layman
            pass

    @Action(UserSpaceBuildProgress.STEP_OVERLAYS_INITIALIZED)
    def action_update_world_set(self):
        fpath = os.path.join(self._workDirObj.chroot_dir_path, "var", "lib", "portage", "world")

        if self._target.world_packages is None:
            if os.path.exists(fpath):
                raise SeedStageError("/var/lib/portage/world should not exist in seed stage")
            return

        # write world file
        os.makedirs(os.path.dirname(fpath))
        with open(fpath, "w") as myf:
            for pkg in self._target.world_packages:
                myf.write("%s\n" % (pkg))

        # update world
        with _Chrooter(self) as m:
            m.run_chroot_script("", "update-world-set.sh")

    @Action(UserSpaceBuildProgress.STEP_WORLD_SET_UPDATED)
    def action_config_system(self):
        with _Chrooter(self) as m:
            # set locale
            m.run_cmd("", "eselect locale set %s" % (self._target.locale), quiet=True)

            # set timezone
            m.run_cmd("", "eselect timezone set %s" % (self._target.timezone), quiet=True)

            # set editor
            m.run_cmd("", "eselect editor set %s" % (self._target.editor), quiet=True)


class _SettingTarget:

    def __init__(self, settings):
        if "profile" in settings:
            self.profile = settings["profile"]
            del settings["profile"]
        else:
            self.profile = None

        if "overlays" in settings:
            self.overlays = {k: _SettingTargetOverlay("data of overlay %s" % (k), v) for k, v in settings["overlays"].items()}  # dict<overlay-name, overlay-data>
            del settings["overlays"]
        else:
            self.overlays = dict()

        if "world_packages" in settings:
            self.world_packages = list(settings["world_packages"])
            del settings["world_package"] 
        else:
            self.world_packages = []

        if "pkg_use" in settings:
            self.pkg_use = dict(settings["pkg_use"])                        # dict<package-wildcard, use-flag-list>
            del settings["pkg_use"] 
        else:
            self.pkg_use = dict()

        if "pkg_mask" in settings:
            self.pkg_mask = dict(settings["pkg_mask"])                      # list<package-wildcard>
            del settings["pkg_mask"] 
        else:
            self.pkg_mask = []

        if "pkg_unmask" in settings:
            self.pkg_unmask = dict(settings["pkg_unmask"])                  # list<package-wildcard>
            del settings["pkg_unmask"] 
        else:
            self.pkg_unmask = []

        if "pkg_accept_keyword" in settings:
            self.pkg_accept_keyword = dict(settings["pkg_accept_keyword"])  # dict<package-wildcard, accept-keyword-list>
            del settings["pkg_accept_keyword"] 
        else:
            self.pkg_accept_keyword = dict()

        if "pkg_accept_license" in settings:
            self.pkg_accept_license = dict(settings["pkg_accept_license"])  # dict<package-wildcard, accept-license-list>
            del settings["pkg_accept_license"] 
        else:
            self.pkg_accept_license = dict()

        if "install_mask" in settings:
            self.install_mask = dict(settings["install_mask"])              # list<install-mask>
            del settings["install_mask"] 
        else:
            self.install_mask = []

        if "pkg_install_mask" in settings:
            self.pkg_install_mask = dict(settings["pkg_install_mask"])      # dict<package-wildcard, install-mask>
            del settings["pkg_install_mask"] 
        else:
            self.pkg_install_mask = dict()

        if "build_opts" in settings:
            self.build_opts = _SettingBuildOptions("build_opts", settings["build_opts"])  # list<build-opts>
            del settings["build_opts"] 
        else:
            self.build_opts = []

        if "pkg_build_opts" in settings:
            self.pkg_build_opts = {k: _SettingBuildOptions("build_opts of %s" % (k), v) for k, v in settings["pkg_build_opts"].items()}   # dict<package-wildcard, build-opts>
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


class _SettingTargetOverlay:

    def __init__(self, settings):
        pass


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
        # distfiles directory in host system, will be bind mounted in target system
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

        # gentoo repository directory in host system, will be read-only bind mounted in target system
        if "host_gentoo_repository_dir" in settings:
            self.gentoo_repository_dir = settings["host_gentoo_repository_dir"]
            del settings["host_gentoo_repository_dir"]
        else:
            self.gentoo_repository_dir = None

        # overlays in host system, will be read-only bind mounted in target system
        if "host_overlays" in settings:
            self.overlays = dict(settings["host_overlays"])     # dict<overlay-name, overlay-dir>
            del settings["host_overlays"]
        else:
            self.overlays = None


class _Chrooter:

    def __init__(self, parent):
        self._parent = parent
        self._chrooter = WorkDirChrooter(self._parent._workDirObj)
        self._bBind = False

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
            # distdir and pkgdir mount point
            t = TargetCacheDirs(self._parent._workDirObj.chroot_dir_path)
            if self._parent._hostInfo.distfiles_dir is not None and os.path.exists(t.distdir_hostpath):
                self._chrooter._assertDirStatus(t.distdir_path)
                Util.shellCall("/bin/mount --bind \"%s\" \"%s\"" % (self._parent._hostInfo.distfiles_dir, t.distdir_hostpath))
            if self._parent._hostInfo.packages_dir is not None and os.path.exists(t.pkgdir_hostpath):
                self._chrooter._assertDirStatus(t.pkgdir_path)
                Util.shellCall("/bin/mount --bind \"%s\" \"%s\"" % (self._parent._hostInfo.packages_dir, t.pkgdir_hostpath))

            # gentoo repository mount point
            if self._parent._hostInfo.gentoo_repository_dir is not None:
                t = TargetGentooRepo(self._parent._workDirObj.chroot_dir_path, self._parent._hostInfo.gentoo_repository_dir)
                if os.path.exists(t.datadir_hostpath):
                    self._chrooter._assertDirStatus(t.datadir_path)
                    Util.shellCall("/bin/mount --bind \"%s\" \"%s\" -o ro" % (t.datadir_path, t.datadir_hostpath))

            # host overlay readonly mount points
            if self._parent._hostInfo.overlays is not None:
                for o in self._parent._hostInfo.overlays:
                    t = TargetHostOverlay(self._parent._workDirObj.chroot_dir_path, o)
                    if os.path.exists(t.datadir_hostpath):
                        self._chrooter._assertDirStatus(t.datadir_path)
                        Util.shellCall("/bin/mount --bind \"%s\" \"%s\" -o ro" % (o.dirpath, t.datadir_hostpath))
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

    def run_cmd(self, env, cmd, quiet=False):
        return self._chrooter.run_cmd(env, cmd, quiet)

    def run_chroot_script(self, env, cmd, quiet=False):
        return self._chrooter.run_chroot_script(env, cmd, quiet)

    def _unbind(self):
        def _procOne(fn):
            fullfn = os.path.join(self._parent._workDirObj.chroot_dir_path, fn[1:])
            if os.path.exists(fullfn) and Util.ismount(fullfn):
                Util.cmdCall("/bin/umount", "-l", fullfn)

        # host overlay mount points
        if self._parent._hostInfo.overlays is not None:
            for o in self._parent._hostInfo.overlays:
                t = TargetHostOverlay(self._parent._workDirObj.chroot_dir_path, o)
                _procOne(t.datadir_path)

        # gentoo repository mount point
        if self._parent._hostInfo.gentoo_repository_dir is not None:
            t = TargetGentooRepo(self._parent._workDirObj.chroot_dir_path, self._parent._hostInfo.gentoo_repository_dir)
            _procOne(t.datadir_path)

        # distdir and pkgdir mount point
        t = TargetCacheDirs(self._parent._workDirObj.chroot_dir_path)
        if self._parent._hostInfo.distfiles_dir is not None and os.path.exists(t.distdir_hostpath):
            _procOne(t.distdir_path)
        if self._parent._hostInfo.packages_dir is not None and os.path.exists(t.pkgdir_hostpath):
            _procOne(t.pkgdir_path)


class TargetCacheDirs:

    def __init__(self, chrootDir):
        self._chroot_path = chrootDir

    @property
    def distdir_hostpath(self):
        return os.path.join(self._chroot_path, self.distdir_path[1:])

    @property
    def pkgdir_hostpath(self):
        return os.path.join(self._chroot_path, self.pkgdir_path[1:])

    @property
    def distdir_path(self):
        return "/var/cache/portage/distfiles"

    @property
    def pkgdir_path(self):
        return "/var/cache/portage/packages"

    def ensure_distdir(self):
        os.makedirs(self.distdir_hostpath)

    def ensure_pkgdir(self):
        os.makedirs(self.pkgdir_hostpath)


class TargetGentooRepo:

    def __init__(self, chrootDir, hostGentooRepoDir):
        self._chrootDir = chrootDir
        self._hostGentooRepoDir = hostGentooRepoDir

    @property
    def repos_conf_file_hostpath(self):
        return os.path.join(self._chrootDir, self.repos_conf_file_path[1:])

    @property
    def datadir_hostpath(self):
        return os.path.join(self._chrootDir, self.datadir_path[1:])

    @property
    def repos_conf_file_path(self):
        return "/etc/portage/repos.conf/gentoo.conf"

    @property
    def datadir_path(self):
        return "/var/db/repos/gentoo"

    def write_repos_conf(self):
        url = "rsync://mirrors.tuna.tsinghua.edu.cn/gentoo-portage"

        os.makedirs(os.path.dirname(self.repos_conf_file_hostpath), exist_ok=True)

        with open(self.repos_conf_file_hostpath, "w") as f:
            if self._hostGentooRepoDir is not None:
                f.write("[gentoo]\n")
                f.write("auto-sync = no\n")
                f.write("location = %s\n" % (self.datadir_path))
            else:
                # from Gentoo AMD64 Handbook
                f.write("[DEFAULT]\n")
                f.write("main-repo = gentoo\n")
                f.write("\n")
                f.write("[gentoo]\n")
                f.write("location = %s\n" % (self.datadir_path))
                f.write("sync-type = rsync\n")
                f.write("sync-uri = %s\n" % (url))
                f.write("auto-sync = yes\n")
                f.write("sync-rsync-verify-jobs = 1\n")
                f.write("sync-rsync-verify-metamanifest = yes\n")
                f.write("sync-rsync-verify-max-age = 24\n")
                f.write("sync-openpgp-key-path = /usr/share/openpgp-keys/gentoo-release.asc\n")
                f.write("sync-openpgp-key-refresh-retry-count = 40\n")
                f.write("sync-openpgp-key-refresh-retry-overall-timeout = 1200\n")
                f.write("sync-openpgp-key-refresh-retry-delay-exp-base = 2\n")
                f.write("sync-openpgp-key-refresh-retry-delay-max = 60\n")
                f.write("sync-openpgp-key-refresh-retry-delay-mult = 4\n")

    def ensure_datadir(self):
        os.makedirs(self.datadir_hostpath)


class TargetHostOverlay:

    def __init__(self, chrootDir, hostOverlay):
        self._chroot_path = chrootDir
        self._name = hostOverlay.name

    @property
    def repos_conf_file_hostpath(self):
        return os.path.join(self._chroot_path, self.repos_conf_file_path[1:])

    @property
    def datadir_hostpath(self):
        return os.path.join(self._chroot_path, self.datadir_path[1:])

    @property
    def repos_conf_file_path(self):
        return "/etc/portage/repos.conf/overlay-%s.conf" % (self._name)

    @property
    def datadir_path(self):
        return "/var/db/overlays/%s" % (self._name)

    def write_repos_conf(self):
        os.makedirs(os.path.dirname(self.repos_conf_file_hostpath), exist_ok=True)
        with open(self.repos_conf_file_hostpath, "w") as f:
            f.write("[%s]\n" % (self._name))
            f.write("auto-sync = no\n")
            f.write("location = %s\n" % (self.datadir_path))

    def ensure_datadir(self):
        os.makedirs(self.datadir_hostpath)


class TargetConfDir:

    def __init__(self, program_name, chrootDir, target, hostInfo):
        self._progName = program_name
        self._dir = chrootDir
        self._target = target
        self._hostInfo = hostInfo

    def write_make_conf(self):
        # determine parallelism parameters
        paraMakeOpts = None
        paraEmergeOpts = None
        if True:
            if self._hostInfo.computing_power.cooling_level <= 1:
                jobcountMake = 1
                jobcountEmerge = 1
                loadavg = 1
            else:
                if self._hostInfo.computing_power.memory_size >= 24 * 1024 * 1024 * 1024:       # >=24G
                    jobcountMake = self._hostInfo.computing_power.cpu_core_count + 2
                    jobcountEmerge = self._hostInfo.computing_power.cpu_core_count
                    loadavg = self._hostInfo.computing_power.cpu_core_count
                else:
                    jobcountMake = self._hostInfo.computing_power.cpu_core_count
                    jobcountEmerge = self._hostInfo.computing_power.cpu_core_count
                    loadavg = max(1, self._hostInfo.computing_power.cpu_core_count - 1)

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
        # Modify and write out packages.use (in chroot)
        fpath = os.path.join(self._dir, "etc", "portage", "packages.use")
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
        # Modify and write out packages.use (in chroot)
        fpath = os.path.join(self._dir, "etc", "portage", "packages.mask")
        with open(fpath, "w") as myf:
            myf.write("")

    def write_package_unmask(self):
        # Modify and write out packages.use (in chroot)
        fpath = os.path.join(self._dir, "etc", "portage", "packages.unmask")
        with open(fpath, "w") as myf:
            myf.write("")

    def write_package_accept_keyword(self):
        # Modify and write out packages.use (in chroot)
        fpath = os.path.join(self._dir, "etc", "portage", "packages.accept_keywords")
        with open(fpath, "w") as myf:
            myf.write("")

    def write_package_accept_license(self):
        # Modify and write out packages.use (in chroot)
        fpath = os.path.join(self._dir, "etc", "portage", "packages.accept_license")
        with open(fpath, "w") as myf:
            myf.write("")






# self._settingsFile = os.path.join(self._workDirObj.path, "ubuild_settings.save")
# self._chksumFile = os.path.join(self._workDirObj.path, "ubuild_seed_stage_archive_chksum.save")

# if not os.path.exists(self._settingsFile):
#     # new directory
#     if any([x.startswith("ubuild_") for x in self._workDirObj.get_save_files()]):
#         raise WorkDirVerifyError("no ubuild save file should exist")
#     if len(self._workDirObj.get_chroot_dir_names()) > 0:
#         raise WorkDirVerifyError("no chroot directory should exist")

#     self._progress = UserSpaceBuildProgress.STEP_INIT
# else:
#     # old directory
#     with open(self._settingsFile) as f:
#         if settings != json.load(f):
#             raise WorkDirVerifyError("settings is not same with the saved data")
#     if os.path.exists(self._chksumFile):
#         with open(self._settingsFile) as f:
#             if self._tf.get_chksum() != f.read().rstrip("\n"):
#                 raise WorkDirVerifyError("seed stage archive checksum verification failed")
#         if len(self._workDirObj.get_chroot_dir_names()) == 0:
#             raise WorkDirVerifyError("no chroot directory found")
#     else:
#         if len(self._workDirObj.get_chroot_dir_names()) > 0:
#             raise WorkDirVerifyError("no chroot directory should exist")