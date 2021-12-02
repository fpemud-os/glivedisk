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
import time
import pickle
import parted
import pathlib
import subprocess


class Util:

    def saveObj(filepath, obj):
        with open(filepath, 'wb') as fh:
            pickle.dump(obj, fh)

    def loadObj(filepath, klass):
        with open(filepath, "rb") as fh:
            return pickle.load(fh)

    def saveEnum(filepath, obj):
        Util.saveObj(filepath, obj)

    def loadEnum(filepath, klass):
        return Util.loadObj(filepath)

    def pathcompare(path1, path2):
        # Change double slashes to slash
        path1 = re.sub(r"//", r"/", path1)
        path2 = re.sub(r"//", r"/", path2)
        # Removing ending slash
        path1 = re.sub("/$", "", path1)
        path2 = re.sub("/$", "", path2)

        if path1 == path2:
            return 1
        return 0

    def ismount(path):
        """Like os.path.ismount, but also support bind mounts"""
        if os.path.ismount(path):
            return 1
        a = os.popen("mount")
        mylines = a.readlines()
        a.close()
        for line in mylines:
            mysplit = line.split()
            if Util.pathcompare(path, mysplit[2]):
                return 1
        return 0

    @staticmethod
    def cmdCall(cmd, *kargs):
        # call command to execute backstage job
        #
        # scenario 1, process group receives SIGTERM, SIGINT and SIGHUP:
        #   * callee must auto-terminate, and cause no side-effect
        #   * caller must be terminated by signal, not by detecting child-process failure
        # scenario 2, caller receives SIGTERM, SIGINT, SIGHUP:
        #   * caller is terminated by signal, and NOT notify callee
        #   * callee must auto-terminate, and cause no side-effect, after caller is terminated
        # scenario 3, callee receives SIGTERM, SIGINT, SIGHUP:
        #   * caller detects child-process failure and do appopriate treatment

        ret = subprocess.run([cmd] + list(kargs),
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             universal_newlines=True)
        if ret.returncode > 128:
            # for scenario 1, caller's signal handler has the oppotunity to get executed during sleep
            time.sleep(1.0)
        if ret.returncode != 0:
            print(ret.stdout)
            ret.check_returncode()
        return ret.stdout.rstrip()

    @staticmethod
    def shellCall(cmd):
        # call command with shell to execute backstage job
        # scenarios are the same as FmUtil.cmdCall

        ret = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             shell=True, universal_newlines=True)
        if ret.returncode > 128:
            # for scenario 1, caller's signal handler has the oppotunity to get executed during sleep
            time.sleep(1.0)
        if ret.returncode != 0:
            print(ret.stdout)
            ret.check_returncode()
        return ret.stdout.rstrip()

    @staticmethod
    def isBlkDevUsbStick(devPath):
        devName = os.path.basename(devPath)

        remfile = "/sys/block/%s/removable" % (devName)
        if not os.path.exists(remfile):
            return False
        if pathlib.Path(remfile).read_text().rstrip("\n") != "1":
            return False

        ueventFile = "/sys/block/%s/device/uevent" % (devName)
        if "DRIVER=sd" not in pathlib.Path(ueventFile).read_text().split("\n"):
            return False

        return True

    @staticmethod
    def isBlkDevUsbStick(devPath):
        devName = os.path.basename(devPath)

        remfile = "/sys/block/%s/removable" % (devName)
        if not os.path.exists(remfile):
            return False
        if pathlib.Path(remfile).read_text().rstrip("\n") != "1":
            return False

        ueventFile = "/sys/block/%s/device/uevent" % (devName)
        if "DRIVER=sd" not in pathlib.Path(ueventFile).read_text().split("\n"):
            return False

        return True

    @staticmethod
    def initializeDisk(devPath, partitionTableType, partitionInfoList):
        assert partitionTableType in ["mbr", "gpt"]
        assert len(partitionInfoList) >= 1

        if partitionTableType == "mbr":
            partitionTableType = "msdos"

        def _getFreeRegion(disk):
            region = None
            for r in disk.getFreeSpaceRegions():
                if r.length <= disk.device.optimumAlignment.grainSize:
                    continue                                                # ignore alignment gaps
                if region is not None:
                    assert False                                            # there should be only one free region
                region = r
            if region.start < 2048:
                region.start = 2048
            return region

        def _addPartition(disk, pType, pStart, pEnd):
            region = parted.Geometry(device=disk.device, start=pStart, end=pEnd)
            if pType == "":
                partition = parted.Partition(disk=disk, type=parted.PARTITION_NORMAL, geometry=region)
            elif pType == "esp":
                assert partitionTableType == "gpt"
                partition = parted.Partition(disk=disk,
                                             type=parted.PARTITION_NORMAL,
                                             fs=parted.FileSystem(type="fat32", geometry=region),
                                             geometry=region)
                partition.setFlag(parted.PARTITION_ESP)     # which also sets flag parted.PARTITION_BOOT
            elif pType == "bcache":
                assert partitionTableType == "gpt"
                partition = parted.Partition(disk=disk, type=parted.PARTITION_NORMAL, geometry=region)
            elif pType == "swap":
                partition = parted.Partition(disk=disk, type=parted.PARTITION_NORMAL, geometry=region)
                if partitionTableType == "mbr":
                    partition.setFlag(parted.PARTITION_SWAP)
                elif partitionTableType == "gpt":
                    pass            # don't know why, it says gpt partition has no way to setFlag(SWAP)
                else:
                    assert False
            elif pType == "lvm":
                partition = parted.Partition(disk=disk, type=parted.PARTITION_NORMAL, geometry=region)
                partition.setFlag(parted.PARTITION_LVM)
            elif pType == "vfat":
                partition = parted.Partition(disk=disk,
                                             type=parted.PARTITION_NORMAL,
                                             fs=parted.FileSystem(type="fat32", geometry=region),
                                             geometry=region)
            elif pType in ["ext2", "ext4", "btrfs"]:
                partition = parted.Partition(disk=disk,
                                             type=parted.PARTITION_NORMAL,
                                             fs=parted.FileSystem(type=pType, geometry=region),
                                             geometry=region)
            else:
                assert False
            disk.addPartition(partition=partition,
                              constraint=disk.device.optimalAlignedConstraint)

        def _erasePartitionSignature(devPath, pStart, pEnd):
            # fixme: this implementation is very limited
            with open(devPath, "wb") as f:
                f.seek(pStart * 512)
                if pEnd - pStart + 1 < 32:
                    f.write(bytearray((pEnd - pStart + 1) * 512))
                else:
                    f.write(bytearray(32 * 512))

        # partitionInfoList => preList & postList
        preList = None
        postList = None
        for i in range(0, len(partitionInfoList)):
            pSize, pType = partitionInfoList[i]
            if pSize == "*":
                assert preList is None
                preList = partitionInfoList[:i]
                postList = partitionInfoList[i:]
        if preList is None:
            preList = partitionInfoList
            postList = []

        # delete all partitions
        disk = parted.freshDisk(parted.getDevice(devPath), partitionTableType)
        disk.commit()

        # process preList
        for pSize, pType in preList:
            region = _getFreeRegion(disk)
            constraint = parted.Constraint(maxGeom=region).intersect(disk.device.optimalAlignedConstraint)
            pStart = constraint.startAlign.alignUp(region, region.start)
            pEnd = constraint.endAlign.alignDown(region, region.end)

            m = re.fullmatch("([0-9]+)(MiB|GiB|TiB)", pSize)
            assert m is not None
            sectorNum = parted.sizeToSectors(int(m.group(1)), m.group(2), disk.device.sectorSize)
            if pEnd < pStart + sectorNum - 1:
                raise Exception("not enough space")

            _addPartition(disk, pType, pStart, pStart + sectorNum - 1)
            _erasePartitionSignature(devPath, pStart, pEnd)

        # process postList
        for pSize, pType in postList:
            region = _getFreeRegion(disk)
            constraint = parted.Constraint(maxGeom=region).intersect(disk.device.optimalAlignedConstraint)
            pStart = constraint.startAlign.alignUp(region, region.start)
            pEnd = constraint.endAlign.alignDown(region, region.end)

            if pSize == "*":
                _addPartition(disk, pType, pStart, pEnd)
                _erasePartitionSignature(devPath, pStart, pEnd)
            else:
                assert False

        # commit and notify kernel (don't wait kernel picks up this change by itself)
        disk.commit()
        Util.cmdCall("/sbin/partprobe")


class TempChdir:

    def __init__(self, dirname):
        self.olddir = os.getcwd()
        os.chdir(dirname)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        os.chdir(self.olddir)


class TmpMount:

    def __init__(self, path, options=None):
        self._path = path
        self._tmppath = tempfile.mkdtemp()

        try:
            cmd = ["/bin/mount"]
            if options is not None:
                cmd.append("-o")
                cmd.append(options)
            cmd.append(self._path)
            cmd.append(self._tmppath)
            subprocess.run(cmd, check=True, universal_newlines=True)
        except BaseException:
            os.rmdir(self._tmppath)
            raise

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    @property
    def mountpoint(self):
        return self._tmppath

    def close(self):
        subprocess.run(["/bin/umount", self._tmppath], check=True, universal_newlines=True)
        os.rmdir(self._tmppath)
