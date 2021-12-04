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
import enum
import robust_layer.simple_fops
from ._util import Util
from ._errors import WorkDirVerifyError
from . import settings


def Action(progress_step):
    def decorator(func):
        def wrapper(self):
            # check
            assert self._progress == progress_step

            # get newChrootDir
            # FIXME: create bcachefs snapshot
            if self._chrootDir is None or self.is_rollback_supported():
                fn = "%02d-%s" % (self._progress.value, BuildProgress(self._progress + 1).name)
                self._chrootDir = os.path.join(self._workDir, fn)
                os.mkdir(self._chrootDir)
                robust_layer.simple_fops.ln(fn, os.path.join(self._workDir, "chroot"))

            # do work
            func(self)

            # do progress
            self._progress = BuildProgress(self._progress + 1)

        return wrapper

    return decorator


class BuildProgress(enum.IntEnum):
    STEP_INIT = enum.auto()
    STEP_UNPACKED = enum.auto()
    STEP_REPOSITORIES_INITIALIZED = enum.auto()
    STEP_CONFDIR_INITIALIZED = enum.auto()
    STEP_SYSTEM_UPDATED = enum.auto()
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

        # check host_info
        if host_info is None:
            host_info = settings.HostInfo()
        assert isinstance(host_info, settings.HostInfo)

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
            os.mkdir(ret._workDir, mode=WorkDir.MODE)
        else:
            WorkDir.checkDir(ret._workDir)
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
        WorkDir.checkDir(work_dir)
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

        self._cm = ChrootMount(self)

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
        if self._cm is not None:
            assert not self._cm.binded
            self._cm = None

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

    @Action(BuildProgress.STEP_UNPACKED)
    def action_init_repositories(self):
        # init gentoo repository
        t = TargetGentooRepo(self._chrootDir)
        t.write_repos_conf()
        t.ensure_datadir()
        t.ensure_distdir()          # we make distdir part of TargetGentooRepo
        t.ensure_pkgdir()           # we make pkgdir part of TargetGentooRepo

        # init host overlays
        if self._hostInfo.overlays is not None:
            for o in self._hostInfo.overlays:
                t = TargetHostOverlay(self._chrootDir, o)
                t.write_repos_conf()
                t.ensure_datadir()

        with self._cm as m:
            m.runCmd("/usr/bin/emerge --sync")

            # init overlays
            # FIXME: use layman
            pass

    @Action(BuildProgress.STEP_REPOSITORIES_INITIALIZED)
    def action_init_confdir(self):
        TargetConfDir.write_make_conf(self._progName, self._chrootDir, self._target)

    @Action(BuildProgress.STEP_CONFDIR_INITIALIZED)
    def action_update_system(self):
        cfgprotect = "CONFIG_PROTECT=\"-* /.glivedisk\""    # the latter is for eliminating "!!! CONFIG_PROTECT is empty" message
        with self._cm as m:
            m.runCmd("", "/usr/bin/emerge -s non-exist-package", flags="stdout")                    # eliminate "Performing Global Updates"
            m.runCmd("", "/usr/bin/eselect news read all", flags="stdout")                          # eliminate gentoo news notification
            m.runCmd(cfgprotect, "/usr/bin/emerge --autounmask-only -uDN @world", flags="stdout")
            m.runCmd(cfgprotect, "/usr/bin/emerge --keep-going -uDN @world")
            m.runCmd(cfgprotect, "/usr/sbin/perl-cleaner --all")

    @Action(BuildProgress.STEP_SYSTEM_UPDATED)
    def action_install_packages(self):
        with self._cm:
            pass

    @Action(BuildProgress.STEP_PACKAGES_INSTALLED)
    def action_gen_kernel_and_initramfs(self):
        with self._cm:
            pass

    @Action(BuildProgress.STEP_KERNEL_AND_INITRAMFS_GENERATED)
    def action_solder_system(self):
        with self._cm:
            pass


class WorkDir:

    MODE = 0o40700

    def checkDir(workDir):
        s = os.stat(workDir)
        if s.st_mode != WorkDir.MODE:
            raise WorkDirVerifyError("invalid mode for \"%s\"" % (workDir))
        if s.st_uid != os.getuid():
            raise WorkDirVerifyError("invalid uid for \"%s\"" % (workDir))
        if s.st_gid != os.getgid():
            raise WorkDirVerifyError("invalid gid for \"%s\"" % (workDir))


class ChrootMount:

    def __init__(self, parent):
        self._stdMnts = ["/proc", "/sys", "/dev", "/dev/pts", "/tmp"]
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

        # check
        for fn in self._stdMnts + self._getAddlMnts():
            assert fn.startswith("/")
            fullfn = os.path.join(self._parent._chrootDir, fn[1:])
            assert os.path.exists(fullfn)
            assert not Util.ismount(fullfn)

        # copy resolv.conf
        Util.shellCall("/bin/cp -L /etc/resolv.conf \"%s\"" % (os.path.join(self._parent._chrootDir, "etc")))

        # standard mount point
        Util.shellCall("/bin/mount -t proc proc \"%s\"" % (os.path.join(self._parent._chrootDir, "proc")))
        Util.shellCall("/bin/mount --rbind /sys \"%s\"" % (os.path.join(self._parent._chrootDir, "sys")))
        Util.shellCall("/bin/mount --make-rslave \"%s\"" % (os.path.join(self._parent._chrootDir, "sys")))
        Util.shellCall("/bin/mount --rbind /dev \"%s\"" % (os.path.join(self._parent._chrootDir, "dev")))
        Util.shellCall("/bin/mount --make-rslave \"%s\"" % (os.path.join(self._parent._chrootDir, "dev")))
        Util.shellCall("/bin/mount -t tmpfs pts \"%s\" -o gid=5,noexec,nosuid,nodev" % (os.path.join(self._parent._chrootDir, "dev", "pts")))
        Util.shellCall("/bin/mount -t tmpfs tmpfs \"%s\"" % (os.path.join(self._parent._chrootDir, "tmp")))

        # distdir mount point
        if self._parent._hostInfo.distfiles_dir is not None:
            t = TargetGentooRepo(self._parent._chrootDir)
            Util.shellCall("/bin/mount --bind \"%s\" \"%s\"" % (self._parent._hostInfo.distfiles_dir, t.distdir_hostpath))

        # pkgdir mount point
        if self._parent._hostInfo.packages_dir is not None:
            t = TargetGentooRepo(self._parent._chrootDir)
            Util.shellCall("/bin/mount --bind \"%s\" \"%s\"" % (self._parent._hostInfo.packages_dir, t.pkgdir_hostpath))

        # host overlay readonly mount points
        if self._parent._hostInfo.overlays is not None:
            for o in self._parent._hostInfo.overlays:
                t = TargetHostOverlay(self._parent._chrootDir, o)
                Util.shellCall("/bin/mount --bind \"%s\" \"%s\" -o ro" % (o.dirpath, t.datadir_hostpath))

        # change status
        self._bBind = True

    def unbind(self):
        assert self._bBind

        # no exception is allowed
        for fn in reversed(self._stdMnts + self._getAddlMnts()):
            Util.cmdCall("/bin/umount", os.path.join(self._parent._chrootDir, fn))
        robust_layer.simple_fops.rm(os.path.join(self._parent._chrootDir, "etc", "resolv.conf"))
        self._bBind = False

    def runCmd(self, envStr, cmdStr):
        # "CLEAN_DELAY=0 /usr/bin/emerge -C sys-fs/eudev" -> "CLEAN_DELAY=0 /usr/bin/chroot /usr/bin/emerge -C sys-fs/eudev"
        if envStr != "":
            print("%s %s" % (envStr, cmdStr))
        else:
            print("%s" % (cmdStr))
        return Util.shellCall("%s /usr/bin/chroot \"%s\" %s" % (envStr, self._parent._chrootDir, cmdStr))

    def _getAddlMnts(self):
        ret = []

        # distdir mount point
        if self._parent._hostInfo.distfiles_dir is not None:
            t = TargetGentooRepo(self._parent._chrootDir)
            ret.append(t.distdir_path)

        # pkgdir mount point
        if self._parent._hostInfo.packages_dir is not None:
            t = TargetGentooRepo(self._parent._chrootDir)
            ret.append(t.pkgdir_path)

        # host overlay mount points
        if self._parent._hostInfo.overlays is not None:
            for o in self._parent._hostInfo.overlays:
                t = TargetHostOverlay(self._parent._chrootDir, o)
                ret.append(t.datadir_path)

        return ret


class TargetGentooRepo:

    def __init__(self, chrootDir):
        self._chroot_path = chrootDir

    @property
    def repos_conf_file_hostpath(self):
        return os.path.join(self._chroot_path, self.repos_conf_file_path[1:])

    @property
    def datadir_hostpath(self):
        return os.path.join(self._chroot_path, self.datadir_path[1:])

    @property
    def distdir_hostpath(self):
        return os.path.join(self._chroot_path, self.distdir_path)

    @property
    def pkgdir_hostpath(self):
        return os.path.join(self._chroot_path, self.pkgdir_path)

    @property
    def repos_conf_file_path(self):
        return "/etc/portage/repos.conf/gentoo.conf"

    @property
    def datadir_path(self):
        return "/var/db/repos/gentoo"

    @property
    def distdir_path(self):
        return "/var/cache/portage/distfiles"

    @property
    def pkgdir_path(self):
        return "/var/cache/portage/packages"

    def write_repos_conf(self):
        os.makedirs(os.path.dirname(self.repos_conf_file_hostpath), exist_ok=True)
        with open(self.repos_conf_file_hostpath, "w") as f:
            # from Gentoo AMD64 Handbook
            f.write("[DEFAULT]\n")
            f.write("main-repo = gentoo\n")
            f.write("\n")
            f.write("[gentoo]\n")
            f.write("location = %s\n" % (self.datadir_path))
            f.write("sync-type = rsync\n")
            f.write("sync-uri = rsync://rsync.gentoo.org/gentoo-portage\n")
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

    def ensure_distdir(self):
        os.makedirs(self.distdir_hostpath)

    def ensure_pkgdir(self):
        os.makedirs(self.pkgdir_hostpath)


class TargetHostOverlay:

    def __init__(self, chrootDir, hostOverlay):
        self._chroot_path = chrootDir
        self._name = hostOverlay.name
        self._hostDir = hostOverlay.dirpath

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
            f.write("[gentoo]\n")
            f.write("auto-sync = no\n")
            f.write("location = %s\n" % (self.datadir_path))

    def ensure_datadir(self):
        os.makedirs(self.datadir_hostpath)


class TargetConfDir:

    @staticmethod
    def write_make_conf(program_name, chroot_path, target):
        def __write(flags, value):
            if value is None and target.build_opts.common_flags is not None:
                myf.write('%s="${COMMON_FLAGS}"\n' % (flags))
            else:
                if isinstance(value, list):
                    myf.write('%s="%s"\n' % (flags, ' '.join(value)))
                else:
                    myf.write('%s="%s"\n' % (flags, value))

        # Modify and write out make.conf (for the chroot)
        makepath = os.path.join(chroot_path, "etc", "portage", "make.conf")
        with open(makepath, "w") as myf:
            myf.write("# These settings were set by %s that automatically built this stage.\n" % (program_name))
            myf.write("# Please consult /usr/share/portage/config/make.conf.example for a more detailed example.\n")
            myf.write("\n")

            if target.build_opts is not None:
                # COMMON_FLAGS
                if target.build_opts.common_flags is not None:
                    myf.write('COMMON_FLAGS="%s"\n' % (' '.join(target.build_opts.common_flags)))

                # foobar FLAGS
                __write("CFLAGS", target.build_opts.cflags)
                __write("CXXFLAGS", target.build_opts.cxxflags)
                __write("FCFLAGS", target.build_opts.fcflags)
                __write("FFLAGS", target.build_opts.fflags)
                __write("LDFLAGS", target.build_opts.ldflags)
                __write("ASFLAGS", target.build_opts.asflags)

            # Set default locale for system responses. #478382
            myf.write('\n')
            myf.write('# This sets the language of build output to English.\n')
            myf.write('# Please keep this setting intact when reporting bugs.\n')
            myf.write('LC_MESSAGES=C\n')
