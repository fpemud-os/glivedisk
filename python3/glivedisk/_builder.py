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
import robust_layer.simple_fops
from ._util import Util
from ._errors import WorkDirVerifyError, SettingsError
from . import settings


def Action(progress_step):
    def decorator(func):
        def wrapper(self):
            # check
            assert self._progress == progress_step

            # get newChrootDir
            # FIXME: create bcachefs snapshot
            if not self.is_rollback_supported():
                self._chrootDir = os.path.join(self._workDir, "chroot")
                robust_layer.simple_fops.mkdir(self._chrootDir)
            else:
                self._chrootDir = os.path.join(self._workDir, "%02d-%s" % (self._progress.value, BuildProgress(self._progress + 1).name))
                os.mkdir(self._chrootDir)
                robust_layer.simple_fops.ln(os.path.basename(self._chrootDir), os.path.join(self._workDir, "chroot"))

            # do work
            func(self)

            # do progress
            self._progress = BuildProgress(self._progress + 1)

        return wrapper

    return decorator


class BuildProgress(enum.IntEnum):
    STEP_INIT = enum.auto()
    STEP_UNPACKED = enum.auto()
    STEP_GENTOO_REPOSITORY_INITIALIZED = enum.auto()
    STEP_CONFDIR_INITIALIZED = enum.auto()
    STEP_SYSTEM_UPDATED = enum.auto()
    STEP_OVERLAYS_INITIALIZED = enum.auto()
    STEP_PACKAGES_INSTALLED = enum.auto()
    STEP_KERNEL_AND_INITRAMFS_GENERATED = enum.auto()
    STEP_SYSTEM_SOLDERED = enum.auto()


class Builder:
    """
    This class does all of the chroot setup, copying of files, etc. It is
    the driver class for pretty much everything that glivedisk does.
    """

    @staticmethod
    def new(program_name, seed_stage_stream, work_dir, target, host_info=None, chroot_info=None):
        # check seed_stage_stream
        assert hasattr(seed_stage_stream, "extractall")

        # check work_dir
        if os.path.exists(work_dir):
            assert os.path.isdir(work_dir)
        else:
            assert os.path.isdir(os.path.dirname(work_dir))

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
        ret = Builder()
        ret._progName = program_name
        ret._tf = seed_stage_stream
        ret._workDir = work_dir
        ret._target = target
        ret._hostInfo = host_info
        ret._chrootInfo = chroot_info
        ret._progress = BuildProgress.STEP_INIT

        # initialize work_dir
        if not os.path.exists(ret._workDir):
            os.mkdir(ret._workDir, mode=WorkDirUtil.MODE)
        else:
            WorkDirUtil.checkDir(ret._workDir)
            robust_layer.simple_fops.truncate_dir(ret._workDir)

        # save parameters
        Util.saveObj(os.path.join(ret._workDir, "target.json"), target)
        Util.saveObj(os.path.join(ret._workDir, "host_info.json"), host_info)
        Util.saveObj(os.path.join(ret._workDir, "chroot_info.json"), chroot_info)
        Util.saveEnum(os.path.join(ret._workDir, "progress"), ret._progress)

        return ret

    @staticmethod
    def revoke(program_name, work_dir):
        ret = Builder()
        ret._progName = program_name
        ret._tf = None

        if not os.path.isdir(work_dir):
            raise WorkDirVerifyError("invalid directory \"%s\"" % (work_dir))
        WorkDirUtil.checkDir(work_dir)
        ret._workDir = work_dir

        fullfn = os.path.join(ret._workDir, "target.json")
        try:
            ret._target = Util.loadObj(fullfn)
        except:
            raise WorkDirVerifyError("invalid parameter file \"%s\"" % (fullfn))

        fullfn = os.path.join(ret._workDir, "host_info.json")
        try:
            ret._hostInfo = Util.loadObj(fullfn)
        except:
            raise WorkDirVerifyError("invalid parameter file \"%s\"" % (fullfn))

        fullfn = os.path.join(ret._workDir, "chroot_info.json")
        try:
            ret._chrootInfo = Util.loadObj(fullfn)
        except:
            raise WorkDirVerifyError("invalid parameter file \"%s\"" % (fullfn))

        fullfn = os.path.join(ret._workDir, "progress")
        try:
            ret._progress = Util.loadEnum(fullfn, BuildProgress)
        except:
            raise WorkDirVerifyError("invalid parameter file \"%s\"" % (fullfn))
        if ret._progress < BuildProgress.STEP_UNPACKED:
            raise WorkDirVerifyError("invalid parameter file \"%s\"" % (fullfn))    # FIXME: change error message

        return ret

    def __init__(self):
        self._progName = None
        self._tf = None
        self._workDir = None
        self._target = None
        self._hostInfo = None
        self._chrootInfo = None

        self._progress = None
        self._chrootDir = None

    def get_progress(self):
        return self._progress

    def get_work_dir(self):
        return self._workDir

    def is_rollback_supported(self):
        return False        # FIXME: support rollback through bcachefs non-priviledged snapshot

    def rollback_to(self, progress_step):
        assert isinstance(progress_step, BuildProgress) and progress_step < self._progress
        assert False        # FIXME: support rollback through bcachefs non-priviledged snapshot

    def dispose(self):
        self._chrootDir = None
        self._progress = None

        self._chrootInfo = None
        self._hostInfo = None
        self._target = None
        if self._workDir is not None:
            robust_layer.simple_fops.rm(self._workDir)
            self._workDir = None
        self._tf = None

    @Action(BuildProgress.STEP_INIT)
    def action_unpack(self):
        self._tf.extractall(self._chrootDir)

        t = TargetCacheDirs(self._chrootDir)
        t.ensure_distdir()
        t.ensure_pkgdir()

    @Action(BuildProgress.STEP_UNPACKED)
    def action_init_gentoo_repository(self):
        # init gentoo repository
        t = TargetGentooRepo(self._chrootDir, self._hostInfo.gentoo_repository_dir)
        t.write_repos_conf()
        t.ensure_datadir()

        # sync gentoo repository
        if self._hostInfo.gentoo_repository_dir is None:
            with Chrooter(self) as m:
                m.runChrootScript("", "/usr/bin/emerge --sync")

    @Action(BuildProgress.STEP_GENTOO_REPOSITORY_INITIALIZED)
    def action_init_confdir(self):
        t = TargetConfDir(self._progName, self._chrootDir, self._target, self._hostInfo)
        t.write_make_conf()
        t.write_package_use()
        t.write_package_mask()
        t.write_package_unmask()
        t.write_package_accept_keyword()
        t.write_package_accept_license()

    @Action(BuildProgress.STEP_CONFDIR_INITIALIZED)
    def action_update_system(self):
        with Chrooter(self) as m:
            m.runChrootScript("", "update-system.sh")
            m.runChrootScript("", "update-world.sh")

    @Action(BuildProgress.STEP_SYSTEM_UPDATED)
    def action_init_overlays(self):
        # init host overlays
        if self._hostInfo.overlays is not None:
            for o in self._hostInfo.overlays:
                t = TargetHostOverlay(self._chrootDir, o)
                t.write_repos_conf()
                t.ensure_datadir()

        # init overlays
        with Chrooter(self) as m:
            # FIXME: use layman
            pass

    @Action(BuildProgress.STEP_OVERLAYS_INITIALIZED)
    def action_install_packages(self):
        with Chrooter(self):
            pass

    @Action(BuildProgress.STEP_PACKAGES_INSTALLED)
    def action_gen_kernel_and_initramfs(self):
        with Chrooter(self):
            pass

    @Action(BuildProgress.STEP_KERNEL_AND_INITRAMFS_GENERATED)
    def action_solder_system(self):
        with Chrooter(self):
            pass


class WorkDirUtil:

    MODE = 0o40700

    @staticmethod
    def checkDir(workDir):
        s = os.stat(workDir)
        if s.st_mode != WorkDirUtil.MODE:
            raise WorkDirVerifyError("invalid mode for \"%s\"" % (workDir))
        if s.st_uid != os.getuid():
            raise WorkDirVerifyError("invalid uid for \"%s\"" % (workDir))
        if s.st_gid != os.getgid():
            raise WorkDirVerifyError("invalid gid for \"%s\"" % (workDir))


class Chrooter:

    def __init__(self, parent):
        self._parent = parent
        self._bBind = False

    def __enter__(self):
        self.bind()
        return self

    def __exit__(self, type, value, traceback):
        self.unbind()

    @property
    def binded(self):
        return self._bBind

    def bind(self):
        assert not self._bBind

        try:
            # modify /etc/locale.gen, emerge may revert it to original default
            with open(os.path.join(self._parent._chrootDir, "etc", "locale.gen"), "w") as f:
                f.write("C.UTF8 UTF-8\n")

            # copy resolv.conf
            Util.shellCall("/bin/cp -L /etc/resolv.conf \"%s\"" % (os.path.join(self._parent._chrootDir, "etc")))

            # mount /proc
            self._assertDirStatus("/proc")
            Util.shellCall("/bin/mount -t proc proc \"%s\"" % (os.path.join(self._parent._chrootDir, "proc")))

            # mount /sys
            self._assertDirStatus("/sys")
            Util.shellCall("/bin/mount --rbind /sys \"%s\"" % (os.path.join(self._parent._chrootDir, "sys")))
            Util.shellCall("/bin/mount --make-rslave \"%s\"" % (os.path.join(self._parent._chrootDir, "sys")))

            # mount /dev
            self._assertDirStatus("/dev")
            Util.shellCall("/bin/mount --rbind /dev \"%s\"" % (os.path.join(self._parent._chrootDir, "dev")))
            Util.shellCall("/bin/mount --make-rslave \"%s\"" % (os.path.join(self._parent._chrootDir, "dev")))

            # mount /tmp
            self._assertDirStatus("/tmp")
            Util.shellCall("/bin/mount -t tmpfs tmpfs \"%s\"" % (os.path.join(self._parent._chrootDir, "tmp")))

            # distdir and pkgdir mount point
            t = TargetCacheDirs(self._parent._chrootDir)
            if self._parent._hostInfo.distfiles_dir is not None and os.path.exists(t.distdir_hostpath):
                self._assertDirStatus(t.distdir_path)
                Util.shellCall("/bin/mount --bind \"%s\" \"%s\"" % (self._parent._hostInfo.distfiles_dir, t.distdir_hostpath))
            if self._parent._hostInfo.packages_dir is not None and os.path.exists(t.pkgdir_hostpath):
                self._assertDirStatus(t.pkgdir_path)
                Util.shellCall("/bin/mount --bind \"%s\" \"%s\"" % (self._parent._hostInfo.packages_dir, t.pkgdir_hostpath))

            # gentoo repository mount point
            if self._parent._hostInfo.gentoo_repository_dir is not None:
                t = TargetGentooRepo(self._parent._chrootDir, self._parent._hostInfo.gentoo_repository_dir)
                if os.path.exists(t.datadir_hostpath):
                    self._assertDirStatus(t.datadir_path)
                    Util.shellCall("/bin/mount --bind \"%s\" \"%s\" -o ro" % (t.datadir_path, t.datadir_hostpath))

            # host overlay readonly mount points
            if self._parent._hostInfo.overlays is not None:
                for o in self._parent._hostInfo.overlays:
                    t = TargetHostOverlay(self._parent._chrootDir, o)
                    if os.path.exists(t.datadir_hostpath):
                        self._assertDirStatus(t.datadir_path)
                        Util.shellCall("/bin/mount --bind \"%s\" \"%s\" -o ro" % (o.dirpath, t.datadir_hostpath))
        except BaseException:
            self._unbind()
            raise

        # change status
        self._bBind = True

    def unbind(self):
        assert self._bBind
        self._unbind()
        self._bBind = False

    def runCmd(self, envStr, cmdStr, quiet=False):
        # "CLEAN_DELAY=0 /usr/bin/emerge -C sys-fs/eudev" -> "CLEAN_DELAY=0 /usr/bin/chroot /usr/bin/emerge -C sys-fs/eudev"
        if not quiet:
            print("%s" % (cmdStr))
            return Util.shellExec("%s /usr/bin/chroot \"%s\" %s" % (envStr, self._parent._chrootDir, cmdStr))
        else:
            return Util.shellCall("%s /usr/bin/chroot \"%s\" %s" % (envStr, self._parent._chrootDir, cmdStr))

    def runChrootScript(self, envStr, cmdStr, quiet=False):
        # "CLEAN_DELAY=0 /usr/bin/emerge -C sys-fs/eudev" -> "CLEAN_DELAY=0 /usr/bin/chroot /usr/bin/emerge -C sys-fs/eudev"

        selfDir = os.path.dirname(os.path.realpath(__file__))
        chrootScriptSrcDir = os.path.join(selfDir, "scripts-in-chroot")
        chrootScriptDstDir = os.path.join(self._parent._chrootDir, "tmp", "glivedisk")

        Util.cmdCall("/bin/cp", "-r", chrootScriptSrcDir, chrootScriptDstDir)
        Util.shellCall("/bin/chmod -R %s/*" % (chrootScriptDstDir))

        try:
            if not quiet:
                return Util.shellExec("%s /usr/bin/chroot \"%s\" %s" % (envStr, self._parent._chrootDir, cmdStr))
            else:
                return Util.shellCall("%s /usr/bin/chroot \"%s\" %s" % (envStr, self._parent._chrootDir, cmdStr))
        finally:
            robust_layer.simple_fops.rm(chrootScriptDstDir)

    def _assertDirStatus(self, dir):
        assert dir.startswith("/")
        fullfn = os.path.join(self._parent._chrootDir, dir[1:])
        assert os.path.exists(fullfn)
        assert not Util.ismount(fullfn)

    def _getAddlMnts(self):
        ret = []

        # distdir and pkgdir mount point
        t = TargetCacheDirs(self._parent._chrootDir)
        if self._parent._hostInfo.distfiles_dir is not None and os.path.exists(t.distdir_hostpath):
            ret.append(t.distdir_path)
        if self._parent._hostInfo.packages_dir is not None and os.path.exists(t.pkgdir_hostpath):
            ret.append(t.pkgdir_path)

        # gentoo repository mount point
        if self._parent._hostInfo.gentoo_repository_dir is not None:
            t = TargetGentooRepo(self._parent._chrootDir, self._parent._hostInfo.gentoo_repository_dir)
            if os.path.exists(t.datadir_hostpath):
                ret.append(t.datadir_path)

        # host overlay mount points
        if self._parent._hostInfo.overlays is not None:
            for o in self._parent._hostInfo.overlays:
                t = TargetHostOverlay(self._parent._chrootDir, o)
                if os.path.exists(t.datadir_hostpath):
                    ret.append(t.datadir_path)

        return ret

    def _unbind(self):
        def _procOne(fn):
            fullfn = os.path.join(self._parent._chrootDir, fn[1:])
            if os.path.exists(fullfn) and Util.ismount(fullfn):
                Util.cmdCall("/bin/umount", "-l", fullfn)

        # host overlay mount points
        if self._parent._hostInfo.overlays is not None:
            for o in self._parent._hostInfo.overlays:
                t = TargetHostOverlay(self._parent._chrootDir, o)
                _procOne(t.datadir_path)

        # gentoo repository mount point
        if self._parent._hostInfo.gentoo_repository_dir is not None:
            t = TargetGentooRepo(self._parent._chrootDir, self._parent._hostInfo.gentoo_repository_dir)
            _procOne(t.datadir_path)

        # distdir and pkgdir mount point
        t = TargetCacheDirs(self._parent._chrootDir)
        if self._parent._hostInfo.distfiles_dir is not None and os.path.exists(t.distdir_hostpath):
            _procOne(t.distdir_path)
        if self._parent._hostInfo.packages_dir is not None and os.path.exists(t.pkgdir_hostpath):
            _procOne(t.pkgdir_path)

        _procOne("/tmp")
        _procOne("/dev")
        _procOne("/sys")
        _procOne("/proc")

        robust_layer.simple_fops.rm(os.path.join(self._parent._chrootDir, "etc", "resolv.conf"))


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
            for pkg_wildcard, use_flag_list in self._target.use_flags.items():
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
