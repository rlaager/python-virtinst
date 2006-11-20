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
import re

import libvirt

import util

import logging


class XenDisk:
    DRIVER_FILE = "file"
    DRIVER_PHY = "phy"
    DRIVER_TAP = "tap"

    DRIVER_TAP_RAW = "aio"
    DRIVER_TAP_QCOW = "qcow"
    DRIVER_TAP_VMDK = "vmdk"

    DEVICE_DISK = "disk"
    DEVICE_CDROM = "cdrom"
    DEVICE_FLOPPY = "floppy"

    TYPE_FILE = "file"
    TYPE_BLOCK = "block"

    def __init__(self, path, size = None, type=None, device=DEVICE_DISK, driverName=None, driverType=None, readOnly=False):
        """@path is the path to the disk image.
           @size is the size of the disk image in gigabytes."""
        self.size = size
        self.path = os.path.abspath(path)

        if os.path.isdir(self.path):
            raise ValueError, "Must provide a file, not a directory for the disk"

        if type is None:
            if not os.path.exists(self.path):
                if size is None:
                    raise ValueError, "Must provide a size for non-existent disks"
                self._type = XenDisk.TYPE_FILE
            else:
                if stat.S_ISBLK(os.stat(self.path)[stat.ST_MODE]):
                    self._type = XenDisk.TYPE_BLOCK
                else:
                    self._type = XenDisk.TYPE_FILE
        else:
            self._type = type

        self._readOnly = readOnly
        self._device = device
        self._driverName = driverName
        self._driverType = driverType

    def get_type(self):
        return self._type
    type = property(get_type)

    def get_device(self):
        return self._device
    device = property(get_device)

    def get_driver_name(self):
        return self._driverName
    driver_name = property(get_driver_name)

    def get_driver_type(self):
        return self._driverType
    driver_type = property(get_driver_type)

    def get_read_only(self):
        return self._readOnly
    read_only = property(get_read_only)

    def setup(self):
        if self._type == XenDisk.TYPE_FILE and not os.path.exists(self.path):
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT)
            off = long(self.size * 1024L * 1024L * 1024L)
            os.lseek(fd, off, 0)
            os.write(fd, '\x00')
            os.close(fd)
        # FIXME: set selinux context?

    def get_xml_config(self, disknode):
        typeattr = 'file'
        if self.type == XenDisk.TYPE_BLOCK:
            typeattr = 'dev'

        ret = "    <disk type='%(type)s' device='%(device)s'>\n" % { "type": self.type, "device": self.device }
        if not(self.driver_name is None):
            if self.driver_type is None:
                ret += "      <driver name='%(name)s'/>\n" % { "name": self.driver_name }
            else:
                ret += "      <driver name='%(name)s' type='%(type)s'/>\n" % { "name": self.driver_name, "type": self.driver_type }
        ret += "      <source %(typeattr)s='%(disk)s'/>\n" % { "typeattr": typeattr, "disk": self.path }
        ret += "      <target dev='%(disknode)s'/>\n" % { "disknode": disknode }
        if self.read_only:
            ret += "      <readonly/>\n"
        ret += "    </disk>\n"
        return ret

    def get_xen_config(self, disknode):
        disktype = "file"
        if self.driver_name is None:
            if self.type == XenDisk.TYPE_BLOCK:
                disktype = "phy"
        elif self.driver_name == XenDisk.DRIVER_TAP:
            if self.driver_type is None:
                disktype = self.driver_name + ":aio"
            else:
                disktype = self.driver_name + ":" + self.driver_type
        else:
            disktype = self.driver_name

        mode = "w"
        if self.read_only:
            mode = "r"
        return "'%(disktype)s:%(disk)s,%(disknode)s,%(mode)s'" \
               % {"disktype": disktype, "disk": self.path, "disknode": disknode, "mode": mode}

    def __repr__(self):
        return "%s:%s" %(self.type, self.path)

class XenNetworkInterface:
    def __init__(self, macaddr = None, bridge = None):
        self.macaddr = macaddr
        self.bridge = bridge

    def setup(self):
        if self.macaddr is None:
            self.macaddr = util.randomMAC()
        if not self.bridge:
            self.bridge = util.default_bridge()

class XenGraphics:
    def __init__(self, *args):
        self.name = ""
        
class XenVNCGraphics(XenGraphics):
    def __init__(self, *args):
        self.name = "vnc"
        if len(args) >= 1 and args[0]:
            self.port = args[0]
        else:
            self.port = -1

class XenSDLGraphics(XenGraphics):
    def __init__(self, *args):
        self.name = "sdl"
    

class XenGuest(object):
    def __init__(self, hypervisorURI=None):
        self.disks = []
        self.nics = []
        self._name = None
        self._uuid = None
        self._memory = None
        self._vcpus = None
        self._graphics = { "enabled": False }

        self.domain = None
        self.conn = libvirt.open(hypervisorURI)
        if self.conn == None:
            raise RuntimeError, "Unable to connect to hypervisor, aborting installation!"

        self.disknode = None # this needs to be set in the subclass

    # Domain name of the guest
    def get_name(self):
        return self._name
    def set_name(self, val):
        # FIXME: need some validation here
        if re.match("^[a-zA-Z0-9_]*$", val) == None: 
            raise ValueError, "Domain name must be alphanumeric or _"
        if len(val) > 50:
            raise ValueError, "Domain name must be less than 50 characters"
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
            disknode = "%(disknode)s%(dev)c" % { "disknode": self.disknode, "dev": ord('a') + count }
            ret += d.get_xml_config(disknode)
            count += 1
        return ret

    def _get_disk_xen(self):
        """Get the disk config in the xend python format"""        
        if len(self.disks) == 0: return ""
        ret = "disk = [ "
        count = 0
        for d in self.disks:
            disknode = "%(disknode)s%(dev)c" % { "disknode": self.disknode, "dev": ord('a') + count }
            ret += d.get_xen_config(disknode)
            ret += ", "
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
            if gt.port and gt.port >= 5900:
                ret += "\nvncdisplay=%d" %(gt.port - 5900,)
                ret += "\nvncunused=0"
            elif gt.port and gt.port == -1:
                ret += "\nvncunused=1"
        elif gt.name == "sdl":
            ret += "sdl=1"
        return ret
        

    def start_install(self, consolecb = None):
        """Do the startup of the guest installation."""
        self.validate_parms()

        try:
            if self.conn.lookupByName(self.name) is not None:
                raise RuntimeError, "Domain named %s already exists!" %(self.name,)
        except libvirt.libvirtError:
            pass

        self._create_devices()
        cxml = self._get_config_xml()
        logging.debug("Creating guest from '%s'" % ( cxml ))
        self.domain = self.conn.createLinux(cxml, 0)
        if self.domain is None:
            raise RuntimeError, "Unable to create domain for guest, aborting installation!"

        child = None
        if consolecb:
            child = consolecb(self.domain)

        time.sleep(2)
        # FIXME: if the domain doesn't exist now, it almost certainly crashed.
        # it'd be nice to know that for certain...
        try:
            d = self.conn.lookupByName(self.name)
        except libvirt.libvirtError:
            raise RuntimeError, "It appears that your installation has crashed.  You should be able to find more information in the xen logs"
        

        cf = "/etc/xen/%s" %(self.name,)
        f = open(cf, "w+")
        xmc = self._get_config_xen()
        logging.debug("Saving XM config file '%s'" % ( xmc ))
        f.write(xmc)
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
            d = self.conn.lookupByName(self.name)
            return d
        except libvirt.libvirtError, e:
            pass

        # domain isn't running anymore
        return None

    def start_from_disk(self, consolecb = None):
        """Restart the guest from its disks."""
        try:
            if self.conn.lookupByName(self.name) is not None:
                raise RuntimeError, "Domain named %s already exists!" %(self.name,)
        except libvirt.libvirtError:
            pass

        self._set_defaults()
        self._create_devices()
        cxml = self._get_config_xml(install = False)
        logging.debug("Starting guest from '%s'" % ( cxml ))
        self.domain = self.conn.createLinux(cxml, 0)
        if self.domain is None:
            raise RuntimeError, "Unable to create domain for guest, aborting installation!"

        child = None
        if consolecb:
            child = consolecb(self.domain)

        time.sleep(2)
        # FIXME: if the domain doesn't exist now, it almost certainly crashed.
        # it'd be nice to know that for certain...
        try:
            d = self.conn.lookupByName(self.name)
        except libvirt.libvirtError:
            raise RuntimeError, "It appears that your domain has crashed.  You should be able to find more information in the xen logs"
        

        if child: # if we connected the console, wait for it to finish
            try:
                (pid, status) = os.waitpid(child, 0)
            except OSError, (errno, msg):
                print __name__, "waitpid:", msg

    def validate_parms(self):
        if self.domain is not None:
            raise RuntimeError, "Domain already started!"
        self._set_defaults()

    def _set_defaults(self):
        if self.uuid is None:
            self.uuid = util.uuidToString(util.randomUUID())
        if self.vcpus is None:
            self.vcpus = 1
        if self.name is None or self.memory is None:
            raise RuntimeError, "Name and memory must be specified for all guests!"
