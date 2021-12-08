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
from ._errors import SettingsError, SeedStageError, WorkDirVerifyError
from ._workdir import WorkDirChrooter
from . import settings


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
    STEP_SYSTEM_UPDATED = enum.auto()
    STEP_OVERLAYS_INITIALIZED = enum.auto()
    STEP_WORLD_UPDATED = enum.auto()


class UserSpaceBuilder:
    """
    This class does all of the chroot setup, copying of files, etc.
    It is the driver class for pretty much everything that glivedisk does.
    """

    def __init__(self, program_name, seed_stage_stream, work_dir, target, host_info=None, chroot_info=None):
        # check seed_stage_stream
        assert hasattr(seed_stage_stream, "get_chksum") and hasattr(seed_stage_stream, "extractall")

        # check target
        assert isinstance(target, settings.Target)
        target = copy.copy(target)
        if target.overlays is None:
            target.overlays = []
        if target.world_packages is None:
            target.world_packages = []
        if target.pkg_use is None:
            target.pkg_use = dict()
        if target.pkg_masks is None:
            target.pkg_masks = []
        if target.pkg_unmasks is None:
            target.pkg_unmasks = []
        if target.pkg_accept_keywords is None:
            target.pkg_accept_keywords = dict()
        if target.pkg_accept_licenses is None:
            target.pkg_accept_licenses = dict()

        # check host_info
        if host_info is not None:
            assert isinstance(host_info, settings.HostInfo)
        else:
            host_info = settings.HostInfo()
        if host_info.computing_power is not None:
            assert isinstance(host_info.computing_power.cpu_core_count, int) and host_info.computing_power.cpu_core_count >= 1
            assert isinstance(host_info.computing_power.memory_size, int) and host_info.computing_power.memory_size >= 1
            assert isinstance(host_info.computing_power.cooling_level, int) and 1 <= host_info.computing_power.cooling_level <= 10
        else:
            host_info.computing_power = settings.HostComputingPower()
            host_info.computing_power.cpu_core_count = 1        # minimal value
            host_info.computing_power.memory_size = 1           # minimal value
            host_info.computing_power.cooling_level = 1         # minimal value

        # check chroot_info
        if chroot_info is None:
            chroot_info = settings.ChrootInfo()
        assert isinstance(chroot_info, settings.ChrootInfo)
        assert chroot_info.conv_uid_gid(0, 0) == (os.getuid(), os.getgid())

        # create object
        self._progName = program_name
        self._tf = seed_stage_stream
        self._workDirObj = work_dir
        self._target = target
        self._hostInfo = host_info
        self._chrootInfo = chroot_info
        self._progress = UserSpaceBuildProgress.STEP_INIT

        if not os.path.exists(self._workDirObj.path):
            self._workDirObj.initialize()
            Util.saveObj(os.path.join(self._workDirObj.path, "seed_chksum"), self._tf.get_chksum())
            Util.saveObj(os.path.join(self._workDirObj.path, "target.json"), target)
            Util.saveObj(os.path.join(self._workDirObj.path, "host_info.json"), host_info)
            Util.saveObj(os.path.join(self._workDirObj.path, "chroot_info.json"), chroot_info)
            Util.saveEnum(os.path.join(self._workDirObj.path, "ubuilder_progress"), self._progress)
        else:
            try:
                self._workDirObj.verify_existing()
                try:
                    saved_chksum = Util.loadObj(os.path.join(self._workDirObj.path, "seed_chksum"))
                    saved_target = Util.loadObj(os.path.join(self._workDirObj.path, "target.json"))
                    saved_host_info = Util.loadObj(os.path.join(self._workDirObj.path, "host_info.json"))
                    saved_chroot_info = Util.loadObj(os.path.join(self._workDirObj.path, "chroot_info.json"))
                    saved_progress = Util.loadObj(os.path.join(self._workDirObj.path, "ubuilder_progress"))
                except:
                    raise WorkDirVerifyError("")
                if self._tf.get_chksm() != saved_chksum:
                    raise WorkDirVerifyError("")
                if target != saved_target:
                    raise WorkDirVerifyError("")
                if host_info != saved_host_info:
                    raise WorkDirVerifyError("")
                if chroot_info != saved_chroot_info:
                    raise WorkDirVerifyError("")
                if saved_progress < UserSpaceBuildProgress.STEP_UNPACKED:
                    raise WorkDirVerifyError("")
                self._progress = saved_progress
            except WorkDirVerifyError:
                self._workDirObj.initialize()
                Util.saveObj(os.path.join(self._workDirObj.path, "seed_chksum"), self._tf.get_chksum())
                Util.saveObj(os.path.join(self._workDirObj.path, "target.json"), target)
                Util.saveObj(os.path.join(self._workDirObj.path, "host_info.json"), host_info)
                Util.saveObj(os.path.join(self._workDirObj.path, "chroot_info.json"), chroot_info)
                Util.saveEnum(os.path.join(self._workDirObj.path, "ubuilder_progress"), self._progress)

    def get_progress(self):
        return self._progress

    def is_rollback_supported(self):
        return self._workDirObj.is_rollback_supported()

    def rollback_to(self, progress_step):
        assert isinstance(progress_step, UserSpaceBuildProgress)
        dirName = "%02d-%s" % (progress_step.value, UserSpaceBuildProgress(progress_step.value + 1).name)
        self._workDirObj.rollback_to_old_chroot_dir(dirName)

    def dispose(self):
        self._progress = None
        self._chrootInfo = None
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
    def action_update_system(self):
        with _Chrooter(self) as m:
            m.run_chroot_script("", "update-system.sh")

    @Action(UserSpaceBuildProgress.STEP_SYSTEM_UPDATED)
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
    def action_update_world(self):
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
            m.run_chroot_script("", "update-world.sh")


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
            # compile all locales. we use INSTALL_MASK to select locales
            myf.write("*/* compile-locales")

            # write cusom USE flags
            for pkg_wildcard, use_flag_list in self._target.pkg_use.items():
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
