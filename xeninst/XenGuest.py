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
import stat, time

import libvirt

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
        self.macaddr = macaddr
        self.bridge = bridge

    def setup(self):
        if self.macaddr is None:
            self.macaddr = util.randomMAC()

class XenGraphics:
    def __init__(self, *args):
        self.name = ""
        
class XenVNCGraphics(XenGraphics):
    def __init__(self, *args):
        self.name = "vnc"
        if len(args) >= 1 and args[0]:
            self.port = args[0]
        else:
            self.port = None

class XenSDLGraphics(XenGraphics):
    def __init__(self, *args):
        self.name = "sdl"
    

class XenGuest(object):
    def __init__(self):
        self.disks = []
        self.nics = []
        self._name = None
        self._uuid = None
        self._memory = None
        self._vcpus = None
        self._graphics = { "enabled": False }

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


    # graphics setup
    def get_graphics(self):
        return self._graphics
    def set_graphics(self, val):
        opts = None
        t = None
        if type(val) == dict:
            if not val.has_key("enabled"):
                raise ValueError, "Must specify whether graphics are enabled"
            self._graphics["enabled"] = val["enabled"]
            if val.has_key("type"):
                t = val["type"]
                if val.has_key("opts"):
                    opts = val["opts"]
        elif type(val) == tuple:
            if len(val) >= 1: self._graphics["enabled"] = val[0]
            if len(val) >= 2: t = val[1]
            if len(val) >= 3: opts = val[2]
        else:
            if val in ("vnc", "sdl"):
                t = val
                self._graphics["enabled"] = True
            else:
                self._graphics["enabled"] = val

        if self._graphics["enabled"] not in (True, False):
            raise ValueError, "Graphics enabled must be True or False"

        if self._graphics["enabled"] == True:
            if t == "vnc":
                gt = XenVNCGraphics(opts)
            elif t == "sdl":
                gt = XenSDLGraphics(opts)
            else:
                raise ValueError, "Unknown graphics type"
            self._graphics["type"] = gt
                
    graphics = property(get_graphics, set_graphics)


    def _create_devices(self):
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

    def _get_graphics_xml(self):
        """Get the graphics config in the libvirt XML format."""
        ret = ""
        if self.graphics["enabled"] == False:
            return ret
        gt = self.graphics["type"]
        if gt.name == "vnc":
            ret += "<graphics type='vnc'"
            if gt.port is not None:
                print "gt.port is ", gt.port
                ret += " port='%d'" %(gt.port,)
            ret += "/>"
        elif gt.name == "sdl":
            ret += "<graphics type='sdl'/>"
        return ret

    def _get_graphics_xen(self):
        """Get the graphics config in the xend python format"""
        if self.graphics["enabled"] == False:
            return "nographic=1"
        ret = ""
        gt = self.graphics["type"]
        if gt.name == "vnc":
            ret += "vnc=1"
            if gt.port:
                ret += "\nvncdisplay=%d" %(gt.port - 5900,)
        elif gt.name == "sdl":
            ret += "sdl=1"
        return ret
        

    def start_install(self, consolecb = None):
        """Do the startup of the guest installation."""
        self.validate_parms()

        conn = libvirt.open(None)
        if conn == None:
            raise RuntimeError, "Unable to connect to hypervisor, aborting installation!"
        try:
            if conn.lookupByName(self.name) is not None:
                raise RuntimeError, "Domain named %s already exists!" %(self.name,)
        except libvirt.libvirtError:
            pass

        self._create_devices()
        cxml = self._get_config_xml()
        self.domain = conn.createLinux(cxml, 0)
        if self.domain is None:
            raise RuntimeError, "Unable to create domain for guest, aborting installation!"

        child = None
        if consolecb:
            child = consolecb(self.domain)

        time.sleep(2)
        # FIXME: if the domain doesn't exist now, it almost certainly crashed.
        # it'd be nice to know that for certain...
        try:
            d = conn.lookupByID(self.domain.ID())
        except libvirt.libvirtError:
            raise RuntimeError, "It appears that your installation has crashed.  You should be able to find more information in the xen logs"


        cf = "/etc/xen/%s" %(self.name,)
        f = open(cf, "w+")
        f.write(self._get_config_xen())
        f.close()

        if child: # if we connected the console, wait for it to finish
            try:
                (pid, status) = os.waitpid(child, 0)
            except OSError, (errno, msg):
                print __name__, "waitpid:", msg

            # ensure there's time for the domain to finish destroying if the
            # install has finished or the guest crashed
            time.sleep(1)
            try:
                d = conn.lookupByID(self.domain.ID())                
            except libvirt.libvirtError:
                return None
            else:
                return d

        return
        

    def validate_parms(self):
        if self.domain is not None:
            raise RuntimeError, "Domain already started!"
        if self.uuid is None:
            self.uuid = util.uuidToString(util.randomUUID())
        if self.vcpus is None:
            self.vcpus = 1
        if self.name is None or self.memory is None:
            raise RuntimeError, "Name and memory must be specified for all guests!"
