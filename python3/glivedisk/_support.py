
import os


class Chroot:

    def __init__(self, dirpath, chroot_info):
        self._dir = dirpath
        self._chrootInfo = chroot_info

    def conv_uid(self, uid):
        if self.uid_map is None:
            return uid
        else:
            if uid not in self.uid_map:
                raise SeedStageError("uid %d not found in uid map" % (uid))
            else:
                return self.uid_map[uid]

    def conv_gid(self, gid):
        if self.gid_map is None:
            return gid
        else:
            if gid not in self.gid_map:
                raise SeedStageError("gid %d not found in gid map" % (gid))
            else:
                return self.gid_map[gid]

    def conv_uid_gid(self, uid, gid):
        return (self.conv_uid(uid), self.conv_gid(gid))

