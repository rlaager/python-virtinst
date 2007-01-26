#!/usr/bin/python -tt
#
# Common code for all guests
#
# Copyright 2006-2007  Red Hat, Inc.
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
import urlgrabber.progress as progress
import libvirt

import util

import logging

class VirtualDisk:
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

    def __init__(self, path, size = None, type=None, device=DEVICE_DISK, driverName=None, driverType=None, readOnly=False, sparse=True):
        """@path is the path to the disk image.
           @size is the size of the disk image in gigabytes."""
        self.size = size
        self.sparse = sparse
        self.path = os.path.abspath(path)

        if os.path.isdir(self.path):
            raise ValueError, "Must provide a file, not a directory for the disk"

        if type is None:
            if not os.path.exists(self.path):
                if size is None:
                    raise ValueError, "Must provide a size for non-existent disks"
                self._type = VirtualDisk.TYPE_FILE
            else:
                if stat.S_ISBLK(os.stat(self.path)[stat.ST_MODE]):
                    self._type = VirtualDisk.TYPE_BLOCK
                else:
                    self._type = VirtualDisk.TYPE_FILE
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

    def setup(self, progresscb):
        if self._type == VirtualDisk.TYPE_FILE and not os.path.exists(self.path):
            size_bytes = long(self.size * 1024L * 1024L * 1024L)
            progresscb.start(filename=self.path,size=long(size_bytes), \
                             text="Creating storage file...")
            try: 
                fd = os.open(self.path, os.O_WRONLY | os.O_CREAT)
                if self.sparse:
                    os.lseek(fd, size_bytes, 0)
                    os.write(fd, '\x00')
                    progresscb.update(self.size)
                else:
                    buf = '\x00' * 1024 * 1024 # 1 meg of nulls
                    for i in range(0, long(self.size * 1024L)):
                        os.write(fd, buf)
                        progresscb.update(long(i * 1024L * 1024L))
            finally:
                os.close(fd)
                progresscb.end(size_bytes)
        # FIXME: set selinux context?

    def get_xml_config(self, disknode):
        typeattr = 'file'
        if self.type == VirtualDisk.TYPE_BLOCK:
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

    def __repr__(self):
        return "%s:%s" %(self.type, self.path)

# Back compat class to avoid ABI break
class XenDisk(VirtualDisk):
    pass

class VirtualNetworkInterface:
    def __init__(self, macaddr = None, bridge = None):
        self.macaddr = macaddr
        self.bridge = bridge

    def setup(self):
        if self.macaddr is None:
            self.macaddr = util.randomMAC()
        if not self.bridge:
            self.bridge = util.default_bridge()

    def get_xml_config(self):
        return ("    <interface type='bridge'>\n" + \
                "      <source bridge='%(bridge)s'/>\n" + \
                "      <mac address='%(mac)s'/>\n" + \
                "    </interface>\n") % \
                { "bridge": self.bridge, "mac": self.macaddr }

# Back compat class to avoid ABI break
class XenNetworkInterface(VirtualNetworkInterface):
    pass

class VirtualGraphics:
    def __init__(self, *args):
        self.name = ""

    def get_xml_config(self):
        return ""

# Back compat class to avoid ABI break
class XenGraphics(VirtualGraphics):
    pass

class VNCVirtualGraphics(XenGraphics):
    def __init__(self, *args):
        self.name = "vnc"
        if len(args) >= 1 and args[0]:
            self.port = args[0]
        else:
            self.port = -1

    def get_xml_config(self):
        return "    <graphics type='vnc' port='%d'/>" % (self.port)

# Back compat class to avoid ABI break
class XenVNCGraphics(VNCVirtualGraphics):
    pass

class SDLVirtualGraphics(XenGraphics):
    def __init__(self, *args):
        self.name = "sdl"

    def get_xml_config(self):
        return "    <graphics type='sdl'/>"

# Back compat class to avoid ABI break
class XenSDLGraphics(SDLVirtualGraphics):
    pass

class Guest(object):
    def __init__(self, type=None, hypervisorURI=None):
        if type is None:
            type = "xen"
        self._type = type
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

    def get_type(self):
        return self._type
    def set_type(self, val):
        self._type = type
    type = property(get_type, set_type)


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
                gt = VNCVirtualGraphics(opts)
            elif t == "sdl":
                gt = SDLVirtualGraphics(opts)
            else:
                raise ValueError, "Unknown graphics type"
            self._graphics["type"] = gt

    graphics = property(get_graphics, set_graphics)


    def _create_devices(self,progresscb):
        """Ensure that devices are setup"""
        for disk in self.disks:
            disk.setup(progresscb)
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

    def _get_network_xml(self):
        """Get the network config in the libvirt XML format"""
        ret = ""
        for n in self.nics:
            ret += n.get_xml_config()
        return ret

    def _get_graphics_xml(self):
        """Get the graphics config in the libvirt XML format."""
        ret = ""
        if self.graphics["enabled"] == False:
            return ret
        gt = self.graphics["type"]
        return gt.get_xml_config()

    def _get_device_xml(self):
        return """%(disks)s
%(networks)s
%(graphics)s""" % { "disks": self._get_disk_xml(), \
        "networks": self._get_network_xml(), \
        "graphics": self._get_graphics_xml() }

    def get_config_xml(self, install = True):
        if install:
            osblob = self._get_install_xml()
            action = "destroy"
        else:
            osblob = self._get_runtime_xml()
            action = "restart"

        return """<domain type='%(type)s'>
  <name>%(name)s</name>
  <memory>%(ramkb)s</memory>
  <uuid>%(uuid)s</uuid>
  %(osblob)s
  <on_poweroff>destroy</on_poweroff>
  <on_reboot>%(action)s</on_reboot>
  <on_crash>%(action)s</on_crash>
  <vcpu>%(vcpus)d</vcpu>
  <devices>
%(devices)s
  </devices>
</domain>
""" % { "type": self.type,
        "name": self.name, \
        "vcpus": self.vcpus, \
        "uuid": self.uuid, \
        "ramkb": self.memory * 1024, \
        "devices": self._get_device_xml(), \
        "osblob": osblob, \
        "action": action }


    def start_install(self, consolecb = None, meter = None):
        """Do the startup of the guest installation."""
        self.validate_parms()

        if meter:
            progresscb = meter
        else:
            # BaseMeter does nothing, but saves a lot of null checking
            progresscb = progress.BaseMeter()
        try:
            if self.conn.lookupByName(self.name) is not None:
                raise RuntimeError, "Domain named %s already exists!" %(self.name,)
        except libvirt.libvirtError:
            pass

        self._create_devices(progresscb)
        install_xml = self.get_config_xml()
        logging.debug("Creating guest from '%s'" % ( install_xml ))
        progresscb.start(size=None, text="Creating domain...")
        self.domain = self.conn.createLinux(install_xml, 0)
        if self.domain is None:
            raise RuntimeError, "Unable to create domain for guest, aborting installation!"
        progresscb.end(0)
        child = None
        if consolecb:
            child = consolecb(self.domain)

        # sleep in .25 second increments until either a) we find
        # our domain or b) it's been 5 seconds.  this is so that
        # we can try to gracefully handle domain creation failures
        num = 0
        d = None
        while num < (5 / .25): # 5 seconds, .25 second sleeps
            try:
                d = self.conn.lookupByName(self.name)
                break
            except libvirt.libvirtError:
                pass
            time.sleep(0.25)

        if d is None:
            raise RuntimeError, "It appears that your installation has crashed.  You should be able to find more information in the logs"

        boot_xml = self.get_config_xml(install = False)
        logging.debug("Saving XML boot config '%s'" % ( boot_xml ))
        self.conn.defineXML(boot_xml)

        if child: # if we connected the console, wait for it to finish
            try:
                (pid, status) = os.waitpid(child, 0)
            except OSError, (errno, msg):
                print __name__, "waitpid:", msg

        # ensure there's time for the domain to finish destroying if the
        # install has finished or the guest crashed
        if consolecb:
            time.sleep(1)

        # This should always work, because it'll lookup a config file
        # for inactive guest, or get the still running install..
        return self.conn.lookupByName(self.name)

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

# Back compat class to avoid ABI break
class XenGuest(Guest):
	pass
