#!/usr/bin/python -tt
#
# Common code for all Xen guests
#
# Copyright 2006  Red Hat, Inc.
# Jeremy Katz <katzj@redhat.com>
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import os
import stat

import util

TYPE_PHY = 1
TYPE_FILE = 2
class XenDisk:
    def __init__(self, path, size = None):
        """@path is the path to the disk image.
           @size is the size of the disk image in gigabytes."""
        self.size = size
        self.path = os.path.abspath(path)

        if os.path.isdir(self.path):
            raise ValueError, "Must provide a file, not a directory for the disk"
        
        if not os.path.exists(self.path):
            if size is None:
                raise ValueError, "Must provide a size for non-existent disks"
            self._type = TYPE_FILE
        else:
            if stat.S_ISBLK(os.stat(self.path)[stat.ST_MODE]):
                self._type = TYPE_PHY
            else:
                self._type = TYPE_FILE

    def get_typestr(self):
        if self._type == TYPE_PHY:
            return "phy"
        else:
            return "file"
    type = property(get_typestr)

    def setup(self):
        if self._type == TYPE_FILE and not os.path.exists(self.path):
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT)
            off = long(self.size * 1024L * 1024L * 1024L)
            os.lseek(fd, off, 0)
            os.write(fd, '\x00')
            os.close(fd)
        # FIXME: set selinux context?

    def __repr__(self):
        return "%s:%s" %(self.type, self.path)

class XenNetworkInterface:
    def __init__(self, macaddr = None, bridge = "xenbr0"):
        self.macaddr = None
        self.bridge = bridge

    def setup(self):
        if self.macaddr is None:
            self.macaddr = util.randomMAC()
        

class XenGuest(object):
    def __init__(self):
        self.disks = []
        self.nics = []
        self._name = None
        self._uuid = None
        self._memory = None
        self._vcpus = None

        self.domain = None

        self.disknode = None # this needs to be set in the subclass

    # Domain name of the guest
    def get_name(self):
        return self._name
    def set_name(self, val):
        # FIXME: need some validation here
        if val.find(" ") != -1:
            raise ValueError, "Domain name cannot contain spaces"
        if type(val) != type("string"):
            raise ValueError, "Domain name must be a string"
        self._name = val
    name = property(get_name, set_name)


    # Memory allocated to the guest.  Should be given in MB
    def get_memory(self):
        return self._memory
    def set_memory(self, val):
        self._memory = val
    memory = property(get_memory, set_memory)


    # UUID for the guest
    def get_uuid(self):
        return self._uuid
    def set_uuid(self, val):
        # need better validation
        if type(val) == type("str"):
            self._uuid = val
        elif type(val) == type(123):
            self._uuid = util.uuidToString(val)
        else:
            raise ValueError, "Invalid value for UUID"
    uuid = property(get_uuid, set_uuid)


    # number of vcpus for the guest
    def get_vcpus(self):
        return self._vcpus
    def set_vcpus(self, val):
        self._vcpus = val
    vcpus = property(get_vcpus, set_vcpus)


    def _createDevices(self):
        """Ensure that devices are setup"""
        for disk in self.disks:
            disk.setup()
        for nic in self.nics:
            nic.setup()

    def _get_disk_xml(self):
        """Get the disk config in the libvirt XML format"""
        ret = ""
        count = 0
        for d in self.disks:
            ret += "<disk type='%(disktype)s'><source file='%(disk)s'/><target dev='%(disknode)s%(dev)c'/></disk>\n" %{"disktype": d.type, "disk": d.path, "dev": ord('a') + count, "disknode": self.disknode}
            count += 1
        return ret

    def _get_disk_xen(self):
        """Get the disk config in the xend python format"""        
        if len(self.disks) == 0: return ""
        ret = "disk = [ "
        count = 0
        for d in self.disks:
            ret += "'%(disktype)s:%(disk)s,%(disknode)s%(dev)c,w', " %{"disktype": d.type, "disk": d.path, "dev": ord('a') + count, "disknode": self.disknode}
            count += 1
        ret += "]"
        return ret

    def _get_network_xml(self):
        """Get the network config in the libvirt XML format"""
        ret = ""
        for n in self.nics:
            ret += "<interface type='bridge'><source bridge='%(bridge)s'/><mac address='%(mac)s'/><script path='/etc/xen/scripts/vif-bridge'/></interface>\n" % { "bridge": n.bridge, "mac": n.macaddr }
        return ret

    def _get_network_xen(self):
        """Get the network config in the xend python format"""        
        if len(self.nics) == 0: return ""
        ret = "vif = [ "
        for n in self.nics:
            ret += "'mac=%(mac)s, bridge=%(bridge)s', " % { "bridge": n.bridge, "mac": n.macaddr }
        ret += "]"
        return ret


    def start_install(self):
        """Do the startup of the guest installation.  Note that the majority
        of the grunt work for this is in the specific PV and FV methods."""
        raise RuntimeError, "Guest type doesn't implement guest install!"

    def validateParms(self):
        if self.domain is not None:
            raise RuntimeError, "Domain already started!"
        if self.uuid is None:
            self.uuid = util.uuidToString(util.randomUUID())
        if self.vcpus is None:
            self.vcpus = 1
        if self.name is None or self.memory is None:
            raise RuntimeError, "Name and memory must be specified for all guests!"
