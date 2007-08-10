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

import os, os.path
import stat, sys, time
import re
import libxml2
import urlgrabber.progress as progress
import util
import libvirt
from virtinst import _virtinst as _

import logging


#print "YO %s" % (virtinst.gettext_virtinst("YO"))

#def _(msg):
#    gettext_virtinst(msg)

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

    def __init__(self, path, size = None, transient=False, type=None, device=DEVICE_DISK, driverName=None, driverType=None, readOnly=False, sparse=True):
        """@path is the path to the disk image.
           @size is the size of the disk image in gigabytes."""
        self.size = size
        self.sparse = sparse
        self.transient = transient
        self.path = os.path.abspath(path)

        if os.path.isdir(self.path):
            raise ValueError, \
                _("The disk path must be a file or a device, not a directory")

        if not self.path.startswith("/"):
            raise ValueError, \
                _("The disk path must be an absolute path location, beginning with '/'")

        if type is None:
            if not os.path.exists(self.path):
                logging.debug("Disk path not found: Assuming file disk type.");
                self._type = VirtualDisk.TYPE_FILE
            else:
                if stat.S_ISBLK(os.stat(self.path)[stat.ST_MODE]):
                    logging.debug(\
                        "Path is block file: Assuming Block disk type.");
                    self._type = VirtualDisk.TYPE_BLOCK
                else:
                    self._type = VirtualDisk.TYPE_FILE
        else:
            self._type = type

        if self._type == VirtualDisk.TYPE_FILE:
            if size is None and not os.path.exists(self.path):
                raise ValueError, \
                    _("A size must be provided for non-existent disks")
            if size is not None and size <= 0:
                raise ValueError, \
                    _("The size of the disk image must be greater than 0")
        elif self._type == VirtualDisk.TYPE_BLOCK:
            if not os.path.exists(self.path):
                raise ValueError, _("The specified block device does not exist.")
            if not stat.S_ISBLK(os.stat(self.path)[stat.ST_MODE]):
                raise ValueError, _("The specified path is not a block device.")

        self._readOnly = readOnly
        self._device = device
        self._driverName = driverName
        self._driverType = driverType
        self.target = None

    def get_type(self):
        return self._type
    type = property(get_type)

    def get_transient(self):
        return self._transient
    transient = property(get_transient)

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
                             text=_("Creating storage file..."))
            fd = None
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
                if fd is not None:
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
        if self.path is None:
            ret += "      <source %(typeattr)s=''/>\n" % { "typeattr": typeattr }
        else:
            ret += "      <source %(typeattr)s='%(disk)s'/>\n" % { "typeattr": typeattr, "disk": self.path }
        if self.target is not None:
            disknode = self.target
        ret += "      <target dev='%(disknode)s'/>\n" % { "disknode": disknode }
        if self.read_only:
            ret += "      <readonly/>\n"
        ret += "    </disk>\n"
        return ret

    def is_conflict_disk(self, conn):
        vms = []
        # get working domain's name
        ids = conn.listDomainsID();
        for id in ids:
            vm = conn.lookupByID(id)
            vms.append(vm)
        # get defined domain
        names = conn.listDefinedDomains()
        for name in names:
            vm = conn.lookupByName(name)
            vms.append(vm)

        count = 0
        for vm in vms:
            doc = None
            try:
                doc = libxml2.parseDoc(vm.XMLDesc(0))
            except:
                continue
            ctx = doc.xpathNewContext()
            try:
                try:
                    count += ctx.xpathEval("count(/domain/devices/disk/source[@dev='%s'])" % self.path)
                    count += ctx.xpathEval("count(/domain/devices/disk/source[@file='%s'])" % self.path)
                except:
                    continue
            finally:
                if ctx is not None:
                    ctx.xpathFreeContext()
                if doc is not None:
                    doc.freeDoc()
        if count > 0:
            return True
        else:
            return False

    def __repr__(self):
        return "%s:%s" %(self.type, self.path)

# Back compat class to avoid ABI break
class XenDisk(VirtualDisk):
    pass

class VirtualNetworkInterface:
    def __init__(self, macaddr = None, type="bridge", bridge = None, network=None):

        if macaddr is not None:
            form = re.match("^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$",macaddr)
            if form is None:
                raise ValueError(_("MAC address must be of the format AA:BB:CC:DD:EE:FF"))
        self.macaddr = macaddr
        self.type = type
        self.bridge = bridge
        self.network = network
        if self.type == "network":
            if network is None:
                raise ValueError, _("A network name was not provided")
            if bridge != None:
                raise ValueError, _("Bridge name is not required for %s") % ("type=network",)
        elif self.type == "bridge":
            if network != None:
                raise ValueError, _("Network name is not required for %s") % ("type=bridge",)
        elif self.type == "user":
            if network != None:
                raise ValueError, _("Network name is not required for %s") % ("type=bridge",)
            if bridge != None:
                raise ValueError, _("Bridge name is not required for %s") % ("type=network",)
        else:
            raise ValueError, _("Unknown network type %s") % (type,)

    def setup(self, conn):
        # get Running Domains
        ids = conn.listDomainsID();
        vms = []
        for id in ids:
            vm = conn.lookupByID(id)
            vms.append(vm)
        # get inactive Domains
        inactive_vm = []
        names = conn.listDefinedDomains()
        for name in names:
            vm = conn.lookupByName(name)
            inactive_vm.append(vm)

        # get the Host's NIC MACaddress
        hostdevs = util.get_host_network_devices()

        # check conflict MAC address
        if self.macaddr is None:
            while 1:
                self.macaddr = util.randomMAC()
                if self.countMACaddr(vms) > 0:
                    continue
                else:
                    break
        else:
            if self.countMACaddr(vms) > 0:
                raise RuntimeError, _("The MAC address you entered is already in use by another virtual machine!")
            for (dummy, dummy, dummy, dummy, host_macaddr) in hostdevs:
                if self.macaddr.upper() == host_macaddr.upper():
                    raise RuntimeError, _("The MAC address you entered conflicts with the physical NIC.")
            if self.countMACaddr(inactive_vm) > 0:
                msg = _("The MAC address you entered is already in use by another inactive virtual machine!")
                print >> sys.stderr, msg
                logging.warning(msg)

        if not self.bridge and self.type == "bridge":
            self.bridge = util.default_bridge()

    def get_xml_config(self):
        if self.type == "bridge":
            return ("    <interface type='bridge'>\n" + \
                    "      <source bridge='%(bridge)s'/>\n" + \
                    "      <mac address='%(mac)s'/>\n" + \
                    "    </interface>\n") % \
                    { "bridge": self.bridge, "mac": self.macaddr }
        elif self.type == "network":
            return ("    <interface type='network'>\n" + \
                    "      <source network='%(network)s'/>\n" + \
                    "      <mac address='%(mac)s'/>\n" + \
                    "    </interface>\n") % \
                    { "network": self.network, "mac": self.macaddr }
        elif self.type == "user":
            return ("    <interface type='user'>\n" + \
                    "      <mac address='%(mac)s'/>\n" + \
                    "    </interface>\n") % \
                    { "mac": self.macaddr }

    def countMACaddr(self, vms):
        count = 0
        for vm in vms:
            doc = None
            try:
                doc = libxml2.parseDoc(vm.XMLDesc(0))
            except:
                continue
            ctx = doc.xpathNewContext()
            try:
                try:
                    count += ctx.xpathEval("count(/domain/devices/interface/mac[@address='%s'])"
                                           % self.macaddr.upper())
                    count += ctx.xpathEval("count(/domain/devices/interface/mac[@address='%s'])"
                                           % self.macaddr.lower())
                except:
                    continue
            finally:
                if ctx is not None:
                    ctx.xpathFreeContext()
                if doc is not None:
                    doc.freeDoc()
        return count

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
        if len(args) >= 1 and not args[0] is None:
            if args[0] < 5900:
                raise ValueError, _("Invalid value for vnc port, port number must be greater than or equal to 5900")
            self.port = args[0]
        else:
            self.port = -1
        if len(args) >= 2 and args[1]:
            self.keymap = args[1]
        else:
            self.keymap = None

    def get_xml_config(self):
        if self.keymap == None:
            keymapstr = ""
        else:
            keymapstr = "keymap='"+self.keymap+"' "
        return "    <graphics type='vnc' port='%(port)d' %(keymapstr)s/>" % {"port":self.port, "keymapstr":keymapstr}

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

class Installer(object):
    def __init__(self, type = "xen", location = None, boot = None, extraargs = None):
        self._location = None
        self._extraargs = None
        self._boot = None
        self._cdrom = False

        if type is None:
            type = "xen"
        self.type = type

        if not location is None:
            self.location = location
        if not boot is None:
            self.boot = boot
        if not extraargs is None:
            self.extraargs = extraargs

        self._tmpfiles = []

    def cleanup(self):
        for f in self._tmpfiles:
            logging.debug("Removing " + f)
            os.unlink(f)
        self._tmpfiles = []

    def get_type(self):
        return self._type
    def set_type(self, val):
        self._type = val
    type = property(get_type, set_type)

    def get_scratchdir(self):
        if self.type == "xen":
            return "/var/lib/xen"
        return "/var/tmp"
    scratchdir = property(get_scratchdir)

    def get_cdrom(self):
        return self._cdrom
    def set_cdrom(self, enable):
        self._cdrom = enable
    cdrom = property(get_cdrom, set_cdrom)

    def get_location(self):
        return self._location
    def set_location(self, val):
        self._location = val
    location = property(get_location, set_location)

    # kernel + initrd pair to use for installing as opposed to using a location
    def get_boot(self):
        return self._boot
    def set_boot(self, val):
        self.cdrom = False
        if type(val) == tuple:
            if len(val) != 2:
                raise ValueError, _("Must pass both a kernel and initrd")
            (k, i) = val
            self._boot = {"kernel": k, "initrd": i}
        elif type(val) == dict:
            if not val.has_key("kernel") or not val.has_key("initrd"):
                raise ValueError, _("Must pass both a kernel and initrd")
            self._boot = val
        elif type(val) == list:
            if len(val) != 2:
                raise ValueError, _("Must pass both a kernel and initrd")
            self._boot = {"kernel": val[0], "initrd": val[1]}
    boot = property(get_boot, set_boot)

    # extra arguments to pass to the guest installer
    def get_extra_args(self):
        return self._extraargs
    def set_extra_args(self, val):
        self._extraargs = val
    extraargs = property(get_extra_args, set_extra_args)

class Guest(object):
    def __init__(self, type=None, connection=None, hypervisorURI=None, installer=None):
        self._installer = installer
        self.disks = []
        self.nics = []
        self._name = None
        self._uuid = None
        self._memory = None
        self._maxmemory = None
        self._vcpus = None
        self._graphics = { "enabled": False }
        self._keymap = None

        self.domain = None
        self.conn = connection
        if self.conn == None:
            self.conn = libvirt.open(hypervisorURI)
        if self.conn == None:
            raise RuntimeError, _("Unable to connect to hypervisor, aborting installation!")

        self.disknode = None # this needs to be set in the subclass

    def get_installer(self):
        return self._installer
    installer = property(get_installer)


    def get_type(self):
        return self._installer.type
    def set_type(self, val):
        self._installer.type = type
    type = property(get_type, set_type)


    # Domain name of the guest
    def get_name(self):
        return self._name
    def set_name(self, val):
        if len(val) > 50 or len(val) == 0:
            raise ValueError, _("System name must be greater than 0 and no more than 50 characters")
        if re.match("^[0-9]+$", val):
            raise ValueError, _("System name must not be only numeric characters")
        if re.match("^[a-zA-Z0-9._-]+$", val) == None:
            raise ValueError, _("System name can only contain alphanumeric, '_', '.', or '-' characters")
        if type(val) != type("string"):
            raise ValueError, _("System name must be a string")
        self._name = val
    name = property(get_name, set_name)


    # Memory allocated to the guest.  Should be given in MB
    def get_memory(self):
        return self._memory
    def set_memory(self, val):
        if (type(val) is not type(1) or val < 0):
            raise ValueError, _("Memory value must be an integer greater than 0")
        self._memory = val
        if self._maxmemory is None or self._maxmemory < val:
            self._maxmemory = val
    memory = property(get_memory, set_memory)

    # Memory allocated to the guest.  Should be given in MB
    def get_maxmemory(self):
        return self._maxmemory
    def set_maxmemory(self, val):
        if (type(val) is not type(1) or val < 0):
            raise ValueError, _("Max Memory value must be an integer greater than 0")
        self._maxmemory = val
    maxmemory = property(get_maxmemory, set_maxmemory)


    # UUID for the guest
    def get_uuid(self):
        return self._uuid
    def set_uuid(self, val):
        # need better validation
        form = re.match("[a-fA-F0-9]{8}[-]([a-fA-F0-9]{4}[-]){3}[a-fA-F0-9]{12}$", val)
        if form is None:
            form = re.match("[a-fA-F0-9]{32}$", val)
            if form is None:
                raise ValueError, _("UUID must be a 32-digit hexadecimal number. It may take the form XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX or may omit hyphens altogether.")

            else:   # UUID had no dashes, so add them in
                val=val[0:8] + "-" + val[8:12] + "-" + val[12:16] + \
                "-" + val[16:20] + "-" + val[20:32]
        self._uuid = val
    uuid = property(get_uuid, set_uuid)


    # number of vcpus for the guest
    def get_vcpus(self):
        return self._vcpus
    def set_vcpus(self, val):
        maxvcpus = util.get_max_vcpus(self.conn)
        if val < 1 or val > maxvcpus:
            raise ValueError, \
                  _("Number of vcpus must be in the range of 1-%d") % (maxvcpus,)
        self._vcpus = val
    vcpus = property(get_vcpus, set_vcpus)


    # graphics setup
    def get_graphics(self):
        return self._graphics
    def set_graphics(self, val):
        def validate_keymap(keymap):
            if not keymap:
                return keymap
            if type(keymap) != type("string"):
                raise ValueError, _("Keymap must be a string")
            if len(keymap) > 16:
                raise ValueError, _("Keymap must be less than 16 characters")
            if re.match("^[a-zA-Z0-9_-]*$", keymap) == None:
                raise ValueError, _("Keymap can only contain alphanumeric, '_', or '-' characters")
            return keymap

        opts = None
        t = None
        if type(val) == dict:
            if not val.has_key("enabled"):
                raise ValueError, _("Must specify whether graphics are enabled")
            self._graphics["enabled"] = val["enabled"]
            if val.has_key("type"):
                t = val["type"]
                if val.has_key("opts"):
                    opts = val["opts"]
        elif type(val) == tuple:
            if len(val) >= 1: self._graphics["enabled"] = val[0]
            if len(val) >= 2: t = val[1]
            if len(val) >= 3: opts = val[2]
            if len(val) >= 4: self._graphics["keymap"] = validate_keymap(val[3])
        else:
            if val in ("vnc", "sdl"):
                t = val
                self._graphics["enabled"] = True
            else:
                self._graphics["enabled"] = val

        if self._graphics["enabled"] not in (True, False):
            raise ValueError, _("Graphics enabled must be True or False")

        if self._graphics["enabled"] == True:
            if t == "vnc":
                if self.graphics.has_key("keymap"):
                    gt = VNCVirtualGraphics(opts, self._graphics["keymap"])
                else:
                    gt = VNCVirtualGraphics(opts)
            elif t == "sdl":
                gt = SDLVirtualGraphics(opts)
            else:
                raise ValueError, _("Unknown graphics type")
            self._graphics["type"] = gt

    graphics = property(get_graphics, set_graphics)


    # Legacy, deprecated properties
    def get_scratchdir(self):
        return self._installer.scratchdir
    scratchdir = property(get_scratchdir)

    def get_boot(self):
        return self._installer.boot
    def set_boot(self, val):
        self._installer.boot = val
    boot = property(get_boot, set_boot)

    def get_location(self):
        return self._installer.location
    def set_location(self, val):
        self._installer.location = val
    location = property(get_location, set_location)

    def get_extraargs(self):
        return self._installer.extraargs
    def set_extraargs(self, val):
        self._installer.extraargs = val
    extraargs = property(get_extraargs, set_extraargs)

    def get_cdrom(self):
        return self.location
    def set_cdrom(self, val):
        self.location = val
        self._installer.cdrom = True
    cdrom = property(get_cdrom, set_cdrom)


    def _create_devices(self,progresscb):
        """Ensure that devices are setup"""
        for disk in self.disks:
            disk.setup(progresscb)
        for nic in self.nics:
            nic.setup(self.conn)

    def _get_network_xml(self, install = True):
        """Get the network config in the libvirt XML format"""
        ret = ""
        for n in self.nics:
            ret += n.get_xml_config()
        return ret

    def _get_graphics_xml(self, install = True):
        """Get the graphics config in the libvirt XML format."""
        ret = ""
        if self.graphics["enabled"] == False:
            return ret
        gt = self.graphics["type"]
        return gt.get_xml_config()

    def _get_input_xml(self, install = True):
        """Get the input device config in libvirt XML format."""
        (type,bus) = self.get_input_device()
        return "    <input type='%s' bus='%s'/>" % (type, bus)

    def _get_device_xml(self, install = True):
        return """%(disks)s
%(networks)s
%(input)s
%(graphics)s""" % { "disks": self._get_disk_xml(install), \
        "networks": self._get_network_xml(install), \
        "input": self._get_input_xml(install), \
        "graphics": self._get_graphics_xml(install) }

    def get_config_xml(self, install = True, disk_boot = False):
        if install:
            action = "destroy"
        else:
            action = "restart"

        osblob_install = install
        if disk_boot:
            osblob_install = False

        osblob = self._get_osblob(osblob_install)
        if not osblob:
            return None

        return """<domain type='%(type)s'>
  <name>%(name)s</name>
  <currentMemory>%(ramkb)s</currentMemory>
  <memory>%(maxramkb)s</memory>
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
        "maxramkb": self.maxmemory * 1024, \
        "devices": self._get_device_xml(install), \
        "osblob": osblob, \
        "action": action }


    def start_install(self, consolecb = None, meter = None):
        """Do the startup of the guest installation."""
        self.validate_parms()

        if meter is None:
            # BaseMeter does nothing, but saves a lot of null checking
            meter = progress.BaseMeter()

        self._prepare_install(meter)
        try:
            return self._do_install(consolecb, meter)
        finally:
            self._installer.cleanup()

    def _do_install(self, consolecb, meter):
        try:
            if self.conn.lookupByName(self.name) is not None:
                raise RuntimeError, _("Domain named %s already exists!") %(self.name,)
        except libvirt.libvirtError:
            pass

        child = None
        self._create_devices(meter)
        install_xml = self.get_config_xml()
        if install_xml:
            logging.debug("Creating guest from '%s'" % ( install_xml ))
            meter.start(size=None, text=_("Creating domain..."))
            self.domain = self.conn.createLinux(install_xml, 0)
            if self.domain is None:
                raise RuntimeError, _("Unable to create domain for the guest, aborting installation!")
            meter.end(0)

            logging.debug("Created guest, looking to see if it is running")
            # sleep in .25 second increments until either a) we find
            # our domain or b) it's been 5 seconds.  this is so that
            # we can try to gracefully handle domain creation failures
            num = 0
            d = None
            while num < (5 / .25): # 5 seconds, .25 second sleeps
                try:
                    d = self.conn.lookupByName(self.name)
                    break
                except libvirt.libvirtError, e:
                    logging.debug("No guest running yet " + str(e))
                    pass
                num += 1
                time.sleep(0.25)

            if d is None:
                raise RuntimeError, _("It appears that your installation has crashed.  You should be able to find more information in the logs")

            if consolecb:
                logging.debug("Launching console callback")
                child = consolecb(self.domain)

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
            time.sleep(1)

        # This should always work, because it'll lookup a config file
        # for inactive guest, or get the still running install..
        return self.conn.lookupByName(self.name)

    def post_install_check(self):
        return self.installer.post_install_check(self)

    def connect_console(self, consolecb):
        logging.debug("Restarted guest, looking to see if it is running")
        # sleep in .25 second increments until either a) we get running
        # domain ID or b) it's been 5 seconds.  this is so that
        # we can try to gracefully handle domain restarting failures
        num = 0
        while num < (5 / .25): # 5 seconds, .25 second sleeps
            try:
                self.domain = self.conn.lookupByName(self.name)
                if self.domain and self.domain.ID() != -1:
                    break
            except libvirt.libvirtError, e:
                logging.debug("No guest existing " + str(e))
                self.domain = None
                pass
            num += 1
            time.sleep(0.25)

        if self.domain is None:
            raise RuntimeError, _("Domain has not existed.  You should be able to find more information in the logs")
        elif self.domain.ID() == -1:
            raise RuntimeError, _("Domain has not run yet.  You should be able to find more information in the logs")

        child = None
        if consolecb:
            logging.debug("Launching console callback")
            child = consolecb(self.domain)

        if child: # if we connected the console, wait for it to finish
            try:
                (pid, status) = os.waitpid(child, 0)
            except OSError, (errno, msg):
                raise RuntimeError, "waiting console pid error: %s" % msg

    def validate_parms(self):
        if self.domain is not None:
            raise RuntimeError, _("Domain has already been started!")
        self._set_defaults()

    def _set_defaults(self):
        if self.uuid is None:
            while 1:
                self.uuid = util.uuidToString(util.randomUUID())
                try:
                    if self.conn.lookupByUUIDString(self.uuid) is not None:
                        continue
                    else:
                        # libvirt probably shouldn't throw an error on a 
                        # non-matching UUID, so do the right thing on a 
                        # None return value with no error
                        break
                except libvirt.libvirtError:
                    break
        else:
            try:
                if self.conn.lookupByUUIDString(self.uuid) is not None:
                    raise RuntimeError, _("The UUID you entered is already in use by another guest!")
                else:
                    pass
            except libvirt.libvirtError:
                pass
        if self.vcpus is None:
            self.vcpus = 1
        if self.name is None or self.memory is None:
            raise RuntimeError, _("Name and memory must be specified for all guests!")

# Back compat class to avoid ABI break
class XenGuest(Guest):
	pass
