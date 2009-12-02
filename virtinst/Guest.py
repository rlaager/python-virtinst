#
# Common code for all guests
#
# Copyright 2006-2009  Red Hat, Inc.
# Jeremy Katz <katzj@redhat.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free  Software Foundation; either version 2 of the License, or
# (at your option)  any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA 02110-1301 USA.

import os, os.path
import time
import re
import urlgrabber.progress as progress
import _util
import libvirt
import CapabilitiesParser
import VirtualGraphics
from VirtualDevice import VirtualDevice
from VirtualDisk import VirtualDisk

import osdict
from virtinst import _virtinst as _
import logging
import signal

def _validate_cpuset(conn, val):
    if val is None or val == "":
        return

    if type(val) is not type("string") or len(val) == 0:
        raise ValueError, _("cpuset must be string")
    if re.match("^[0-9,-]*$", val) is None:
        raise ValueError, _("cpuset can only contain numeric, ',', or "
                            "'-' characters")

    pcpus = _util.get_phy_cpus(conn)
    for c in val.split(','):
        if c.find('-') != -1:
            (x, y) = c.split('-')
            if int(x) > int(y):
                raise ValueError, _("cpuset contains invalid format.")
            if int(x) >= pcpus or int(y) >= pcpus:
                raise ValueError, _("cpuset's pCPU numbers must be less "
                                    "than pCPUs.")
        else:
            if len(c) == 0:
                continue

            if int(c) >= pcpus:
                raise ValueError, _("cpuset's pCPU numbers must be less "
                                    "than pCPUs.")
    return

class Guest(object):

    # OS Dictionary static variables and methods
    _DEFAULTS = osdict.DEFAULTS
    _OS_TYPES = osdict.OS_TYPES

    def list_os_types():
        return osdict.sort_helper(Guest._OS_TYPES)
    list_os_types = staticmethod(list_os_types)

    def list_os_variants(type):
        return osdict.sort_helper(Guest._OS_TYPES[type]["variants"])
    list_os_variants = staticmethod(list_os_variants)

    def get_os_type_label(type):
        return Guest._OS_TYPES[type]["label"]
    get_os_type_label = staticmethod(get_os_type_label)

    def get_os_variant_label(type, variant):
        return Guest._OS_TYPES[type]["variants"][variant]["label"]
    get_os_variant_label = staticmethod(get_os_variant_label)

    def cpuset_str_to_tuple(conn, cpuset):
        _validate_cpuset(conn, cpuset)
        pinlist = [False] * _util.get_phy_cpus(conn)

        entries = cpuset.split(",")
        for e in entries:
            series = e.split("-", 1)

            if len(series) == 1:
                pinlist[int(series[0])] = True
                continue

            start = int(series[0])
            end = int(series[1])

            for i in range(start, end):
                pinlist[i] = True

        return tuple(pinlist)
    cpuset_str_to_tuple = staticmethod(cpuset_str_to_tuple)

    def __init__(self, type=None, connection=None, hypervisorURI=None,
                 installer=None):
        # We specifically ignore the 'type' parameter here, since
        # it has been replaced by installer.type, and child classes can
        # use it when creating a default installer.
        self._installer = installer
        self._name = None
        self._uuid = None
        self._memory = None
        self._maxmemory = None
        self._vcpus = 1
        self._cpuset = None
        self._graphics_dev = None
        self._consolechild = None
        self._os_autodetect = False

        self._os_type = None
        self._os_variant = None

        # DEPRECATED: Public device lists unaltered by install process
        self.disks = []
        self.nics = []
        self.sound_devs = []
        self.hostdevs = []

        # General device list. Only access through API calls (even internally)
        self._devices = []

        # Device list to use/alter during install process. Don't access
        # directly, use internal APIs
        self._install_devices = []

        # The libvirt virDomain object we 'Create'
        self.domain = None

        # Default disk target prefix ('hd' or 'xvd'). Set in subclass
        self.disknode = None

        # Default bus for disks (set in subclass)
        self._diskbus = None

        self.conn = connection
        if self.conn == None:
            logging.debug("No conn passed to Guest, opening URI '%s'" % \
                          hypervisorURI)
            self.conn = libvirt.open(hypervisorURI)
        if self.conn == None:
            raise RuntimeError, _("Unable to connect to hypervisor, aborting "
                                  "installation!")

        self._caps = CapabilitiesParser.parse(self.conn.getCapabilities())


    def get_installer(self):
        return self._installer
    def set_installer(self, val):
        # FIXME: Make sure this is valid: it's pretty fundamental to
        # working operation. Should we even allow it to be changed?
        self._installer = val
    installer = property(get_installer, set_installer)

    # Domain name of the guest
    def get_name(self):
        return self._name
    def set_name(self, val):
        _util.validate_name(_("Guest"), val)
        try:
            self.conn.lookupByName(val)
        except:
            # Name not found
            self._name = val
            return
        raise ValueError(_("Guest name '%s' is already in use.") % val)
    name = property(get_name, set_name)

    # Memory allocated to the guest.  Should be given in MB
    def get_memory(self):
        return self._memory
    def set_memory(self, val):
        if (type(val) is not type(1) or val <= 0):
            raise ValueError, _("Memory value must be an integer greater "
                                "than 0")
        self._memory = val
        if self._maxmemory is None or self._maxmemory < val:
            self._maxmemory = val
    memory = property(get_memory, set_memory)

    # Memory allocated to the guest.  Should be given in MB
    def get_maxmemory(self):
        return self._maxmemory
    def set_maxmemory(self, val):
        if (type(val) is not type(1) or val <= 0):
            raise ValueError, _("Max Memory value must be an integer greater "
                                "than 0")
        self._maxmemory = val
    maxmemory = property(get_maxmemory, set_maxmemory)

    # UUID for the guest
    def get_uuid(self):
        return self._uuid
    def set_uuid(self, val):
        val = _util.validate_uuid(val)
        self._uuid = val
    uuid = property(get_uuid, set_uuid)

    # number of vcpus for the guest
    def get_vcpus(self):
        return self._vcpus
    def set_vcpus(self, val):
        maxvcpus = _util.get_max_vcpus(self.conn, self.type)
        if type(val) is not int or val < 1:
            raise ValueError, _("Number of vcpus must be a postive integer.")
        if val > maxvcpus:
            raise ValueError, _("Number of vcpus must be no greater than %d "
                                "for this vm type.") % maxvcpus
        self._vcpus = val
    vcpus = property(get_vcpus, set_vcpus)

    # set phy-cpus for the guest
    def get_cpuset(self):
        return self._cpuset
    def set_cpuset(self, val):
        if val is None or val == "":
            self._cpuset = None
            return

        _validate_cpuset(self.conn, val)
        self._cpuset = val
    cpuset = property(get_cpuset, set_cpuset)

    def get_graphics_dev(self):
        return self._graphics_dev
    def set_graphics_dev(self, val):
        self._graphics_dev = val
    graphics_dev = property(get_graphics_dev, set_graphics_dev)

    # GAH! - installer.os_type = "hvm" or "xen" (aka xen paravirt)
    #        guest.os_type     = "Solaris", "Windows", "Linux"
    # FIXME: We should really rename this property to something else,
    #        change it throughout the codebase for readability sake, but
    #        maintain back compat.
    def get_os_type(self):
        return self._os_type
    def set_os_type(self, val):
        if type(val) is not str:
            raise ValueError(_("OS type must be a string."))
        val = val.lower()

        if self._OS_TYPES.has_key(val):
            if self._os_type == val:
                # No change, don't invalidate variant
                return

            # Invalidate variant, since it may not apply to the new os type
            self._os_type = val
            self._os_variant = None
        else:
            raise ValueError, _("OS type '%s' does not exist in our "
                                "dictionary") % val
    os_type = property(get_os_type, set_os_type)

    def get_os_variant(self):
        return self._os_variant
    def set_os_variant(self, val):
        if type(val) is not str:
            raise ValueError(_("OS variant must be a string."))
        val = val.lower()
        if self.os_type:
            if self._OS_TYPES[self.os_type]["variants"].has_key(val):
                self._os_variant = val
            else:
                raise ValueError, _("OS variant '%(var)s' does not exist in "
                                    "our dictionary for OS type '%(ty)s'" ) % \
                                    {'var' : val, 'ty' : self._os_type}
        else:
            for ostype in self.list_os_types():
                if self._OS_TYPES[ostype]["variants"].has_key(val) and \
                   not self._OS_TYPES[ostype]["variants"][val].get("skip"):
                    logging.debug("Setting os type to '%s' for variant '%s'" %\
                                  (ostype, val))
                    self.os_type = ostype
                    self._os_variant = val
                    return
            raise ValueError, _("Unknown OS variant '%s'" % val)
    os_variant = property(get_os_variant, set_os_variant)

    def set_os_autodetect(self, val):
        self._os_autodetect = bool(val)
    def get_os_autodetect(self):
        return self._os_autodetect
    os_autodetect = property(get_os_autodetect, set_os_autodetect)

    # Get the current variants 'distro' tag: 'rhel', 'fedora', etc.
    def get_os_distro(self):
        return self._lookup_osdict_key("distro")
    os_distro = property(get_os_distro)


    # DEPRECATED PROPERTIES

    # Deprecated: Should set graphics_dev.keymap directly
    def get_keymap(self):
        if self._graphics_dev is None:
            return None
        return self._graphics_dev.keymap
    def set_keymap(self, val):
        if self._graphics_dev is not None:
            self._graphics_dev.keymap = val
    keymap = property(get_keymap, set_keymap)

    # Deprecated: Should set guest.graphics_dev = VirtualGraphics(...)
    def get_graphics(self):
        if self._graphics_dev is None:
            return { "enabled" : False }
        return { "enabled" : True, "type" : self._graphics_dev, \
                 "keymap"  : self._graphics_dev.keymap}
    def set_graphics(self, val):

        # val can be:
        #   a dictionary with keys:  enabled, type, port, keymap
        #   a tuple of the form   : (enabled, type, port, keymap)
        #                            last 2 optional
        #                         : "vnc", "sdl", or false
        port = None
        gtype = None
        enabled = False
        keymap = None
        gdev = None
        if type(val) == dict:
            if not val.has_key("enabled"):
                raise ValueError, _("Must specify whether graphics are enabled")
            enabled = val["enabled"]
            if val.has_key("type"):
                gtype = val["type"]
                if val.has_key("opts"):
                    port = val["opts"]
        elif type(val) == tuple:
            if len(val) >= 1:
                enabled = val[0]
            if len(val) >= 2:
                gtype = val[1]
            if len(val) >= 3:
                port = val[2]
            if len(val) >= 4:
                keymap = val[3]
        else:
            if val in ("vnc", "sdl"):
                gtype = val
                enabled = True
            else:
                enabled = val

        if enabled not in (True, False):
            raise ValueError, _("Graphics enabled must be True or False")

        if enabled:
            gdev = VirtualGraphics.VirtualGraphics(type=gtype)
            if port:
                gdev.port = port
            if keymap:
                gdev.keymap = keymap
        self._graphics_dev = gdev

    graphics = property(get_graphics, set_graphics)


    # Properties that are mapped through to the Installer

    # Hypervisor name (qemu, xen, kvm, etc.)
    def get_type(self):
        return self._installer.type
    def set_type(self, val):
        self._installer.type = val
    type = property(get_type, set_type)

    def get_arch(self):
        return self.installer.arch
    def set_arch(self, val):
        self.installer.arch = val
    arch = property(get_arch, set_arch)

    # Deprecated: Should be called from the installer directly
    def get_location(self):
        return self._installer.location
    def set_location(self, val):
        self._installer.location = val
    location = property(get_location, set_location)

    # Deprecated: Should be called from the installer directly
    def get_scratchdir(self):
        return self._installer.scratchdir
    scratchdir = property(get_scratchdir)

    # Deprecated: Should be called from the installer directly
    def get_boot(self):
        return self._installer.boot
    def set_boot(self, val):
        self._installer.boot = val
    boot = property(get_boot, set_boot)

    # Deprecated: Should be called from the installer directly
    def get_extraargs(self):
        return self._installer.extraargs
    def set_extraargs(self, val):
        self._installer.extraargs = val
    extraargs = property(get_extraargs, set_extraargs)

    # Deprecated: Should set the installer values directly
    def get_cdrom(self):
        return self._installer.location
    def set_cdrom(self, val):
        if val is None or type(val) is not type("string") or len(val) == 0:
            raise ValueError, _("You must specify a valid ISO or CD-ROM location for the installation")
        if val.startswith("/"):
            if not os.path.exists(val):
                raise ValueError, _("The specified media path does not exist.")
            self._installer.location = os.path.abspath(val)
        else:
            # Assume its a http/nfs/ftp style path
            self._installer.location = val
        self._installer.cdrom = True
    cdrom = property(get_cdrom, set_cdrom)
    # END DEPRECATED PROPERTIES


    # Device Add/Remove Public API methods

    def _dev_build_list(self, devtype, devlist=None):
        if not devlist:
            devlist = self._devices

        newlist = []
        for i in devlist:
            if i.virtual_device_type == devtype:
                newlist.append(i)
        return newlist

    def add_device(self, dev):
        """
        Add the passed device to the guest's device list.

        @param dev: VirtualDevice instance to attach to guest
        """
        if not isinstance(dev, VirtualDevice):
            raise ValueError(_("Must pass a VirtualDevice instance."))
        devtype = dev.virtual_device_type

        if   devtype == VirtualDevice.VIRTUAL_DEV_DISK:
            self.disks.append(dev)
        elif devtype == VirtualDevice.VIRTUAL_DEV_NET:
            self.nics.append(dev)
        elif devtype == VirtualDevice.VIRTUAL_DEV_AUDIO:
            self.sound_devs.append(dev)
        elif devtype == VirtualDevice.VIRTUAL_DEV_GRAPHICS:
            self._graphics_dev = dev
        elif devtype == VirtualDevice.VIRTUAL_DEV_HOSTDEV:
            self.hostdevs.append(dev)
        else:
            self._devices.append(dev)

    def get_devices(self, devtype):
        """
        Return a list of devices of type 'devtype' that will installed on
        the guest.

        @param devtype: Device type to search for (one of
                        VirtualDevice.virtual_device_types)
        """
        if   devtype == VirtualDevice.VIRTUAL_DEV_DISK:
            return self.disks[:]
        elif devtype == VirtualDevice.VIRTUAL_DEV_NET:
            return self.nics[:]
        elif devtype == VirtualDevice.VIRTUAL_DEV_AUDIO:
            return self.sound_devs[:]
        elif devtype == VirtualDevice.VIRTUAL_DEV_GRAPHICS:
            return self._graphics_dev and [self._graphics_dev] or []
        elif devtype == VirtualDevice.VIRTUAL_DEV_HOSTDEV:
            return self.hostdevs[:]
        else:
            return self._dev_build_list(devtype)

    def get_all_devices(self):
        """
        Return a list of all devices being installed with the guest
        """
        retlist = []
        for devtype in VirtualDevice.virtual_device_types:
            retlist.extend(self.get_devices(devtype))
        return retlist

    def remove_device(self, dev):
        """
        Remove the passed device from the guest's device list

        @param dev: VirtualDevice instance
        """
        if dev == self._graphics_dev:
            self._graphics_dev = None

        for devlist in [self.disks, self.nics, self.sound_devs, self.hostdevs,
                        self._devices]:
            if dev in devlist:
                devlist.remove(dev)

    # Device fetching functions used internally during the install process.
    # These allow us to change dev defaults, add install media, etc. during
    # the install, but revert to a clean state if the install fails
    def _init_install_devs(self):
        self._install_devices = self.get_all_devices()[:]

    def _get_install_devs(self, devtype):
        return self._dev_build_list(devtype, self._install_devices)

    def _add_install_dev(self, dev):
        self._install_devices.append(dev)

    def _get_all_install_devs(self):
        retlist = []
        for devtype in VirtualDevice.virtual_device_types:
            retlist.extend(self._get_install_devs(devtype))
        return retlist

    # Private xml building methods

    def _get_input_device(self):
        """ Return a tuple of the form (devtype, bus) for the desired
            input device. (Must be implemented in subclass) """
        raise NotImplementedError

    def _get_device_xml(self, install=True):
        change_disks = []
        for d in self._get_install_devs(VirtualDevice.VIRTUAL_DEV_DISK):
            if (d.device == VirtualDisk.DEVICE_CDROM
                and d.transient
                and not install):
                # Keep cdrom around, but with no media attached,
                # But only if we are a distro that doesn't have a multi
                # stage install (aka not Windows)
                if not self.get_continue_inst():
                    change_disks.append((d, d.path))
                    d.path = None

        xml = ""
        try:
            for dev in self._get_all_install_devs():
                xml = _util.xml_append(xml, dev.get_xml_config())
        finally:
            try:
                for disk, path in change_disks:
                    disk.path = path
            except:
                pass

        return xml

    def _get_features_xml(self):
        """
        Return features (pae, acpi, apic) xml (currently only releavnt for FV)
        """
        return ""

    def _get_clock_xml(self):
        """
        Return <clock/> xml (currently only relevant for FV guests)
        """
        return ""

    def _get_osblob(self, install):
        """Return os, features, and clock xml (Implemented in subclass)"""
        xml = ""

        osxml = self.installer.get_install_xml(self, install)
        if not osxml:
            return None

        xml = _util.xml_append(xml,
                               self.installer.get_install_xml(self, install))
        xml = _util.xml_append(xml, self._get_features_xml())
        xml = _util.xml_append(xml, self._get_clock_xml())
        return xml



    def get_config_xml(self, install = True, disk_boot = False):
        """
        Return the full Guest xml configuration.

        @param install: Whether we want the 'OS install' configuration or
                        the 'post-install' configuration. (Some Installers,
                        like the LiveCDInstaller may not have an 'install'
                        config.)
        @type install: C{bool}
        @param disk_boot: Whether we should boot off the harddisk, regardless
                          of our position in the install process (this is
                          used for 2 stage installs, where the second stage
                          boots off the disk. You probably don't need to touch
                          this.)
        @type disk_boot: C{bool}
        """

        if install:
            action = "destroy"
        else:
            action = "restart"

        osblob_install = install
        if disk_boot:
            osblob_install = False

        osblob = self._get_osblob(osblob_install)
        if not osblob:
            # This means there is no 'install' phase, so just return
            return None

        if self.cpuset is not None:
            cpuset = " cpuset='" + self.cpuset + "'"
        else:
            cpuset = ""

        xml = ""
        add = lambda x: _util.xml_append(xml, x)

        xml = add("<domain type='%s'>" % self.type)
        xml = add("  <name>%s</name>" % self.name)
        xml = add("  <currentMemory>%s</currentMemory>" % (self.memory * 1024))
        xml = add("  <memory>%s</memory>" % (self.maxmemory * 1024))
        xml = add("  <uuid>%s</uuid>" % self.uuid)
        xml = add("  %s" % osblob)
        xml = add("  <on_poweroff>destroy</on_poweroff>")
        xml = add("  <on_reboot>%s</on_reboot>" % action)
        xml = add("  <on_crash>%s</on_crash>" % action)
        xml = add("  <vcpu%s>%d</vcpu>" % (cpuset, self.vcpus))
        xml = add("  <devices>")
        xml = add("%s" % self._get_device_xml(install))
        xml = add("  </devices>")
        xml = add("</domain>\n")

        return xml

    def start_install(self, consolecb=None, meter=None, removeOld=False,
                      wait=True):
        """Do the startup of the guest installation."""
        self.validate_parms()
        self._consolechild = None

        if meter is None:
            # BaseMeter does nothing, but saves a lot of null checking
            meter = progress.BaseMeter()

        self._prepare_install(meter)
        try:
            return self._do_install(consolecb, meter, removeOld, wait)
        finally:
            self._installer.cleanup()

    def get_continue_inst(self):
        val = self._lookup_osdict_key("continue")
        if not val:
            val = False

        if val == True:
            # If we are doing an 'import' or 'liveCD' install, there is
            # no true install process, so continue install has no meaning
            if not self.get_config_xml(install=True):
                val = False
        return val

    def continue_install(self, consolecb, meter, wait=True):
        cont_xml = self.get_config_xml(disk_boot = True)
        logging.debug("Continuing guest with:\n%s" % cont_xml)
        meter.start(size=None, text="Starting domain...")

        # As of libvirt 0.5.1 we can't 'create' over an defined VM.
        # So, redefine the existing domain (which should be shutoff at
        # this point), and start it.
        finalxml = self.domain.XMLDesc(0)

        self.domain = self.conn.defineXML(cont_xml)
        self.domain.create()
        self.conn.defineXML(finalxml)

        #self.domain = self.conn.createLinux(install_xml, 0)
        if self.domain is None:
            raise RuntimeError, _("Unable to start domain for guest, aborting installation!")
        meter.end(0)

        self.connect_console(consolecb, wait)

        # ensure there's time for the domain to finish destroying if the
        # install has finished or the guest crashed
        if consolecb:
            time.sleep(1)

        # This should always work, because it'll lookup a config file
        # for inactive guest, or get the still running install..
        return self.conn.lookupByName(self.name)


    def _prepare_install(self, meter):
        self._init_install_devs()

        self._installer.prepare(guest = self,
                                meter = meter)
        if self._installer.install_disk is not None:
            self._add_install_dev(self._installer.install_disk)

        # Run 'set_defaults' after install prep, since some installers
        # (ImageInstaller) alter the device list.
        self._set_defaults()

        # Only set up an input device if there isn't already preset
        if not self._get_install_devs(VirtualDevice.VIRTUAL_DEV_INPUT):
            self._add_install_dev(self._get_input_device())

    def _create_devices(self, progresscb):
        """Ensure that devices are setup"""
        for disk in self._get_install_devs(VirtualDevice.VIRTUAL_DEV_DISK):
            disk.setup(progresscb)
        for nic in self._get_install_devs(VirtualDevice.VIRTUAL_DEV_NET):
            nic.setup(self.conn)
        for hostdev in self._get_install_devs(VirtualDevice.VIRTUAL_DEV_HOSTDEV):
            hostdev.setup()

    def _do_install(self, consolecb, meter, removeOld=False, wait=True):
        vm = None
        try:
            vm = self.conn.lookupByName(self.name)
        except libvirt.libvirtError:
            pass

        if vm is not None:
            if removeOld :
                try:
                    if vm.ID() != -1:
                        logging.info("Destroying image %s" %(self.name))
                        vm.destroy()
                    logging.info("Removing old definition for image %s" %(self.name))
                    vm.undefine()
                except libvirt.libvirtError, e:
                    raise RuntimeError, _("Could not remove old vm '%s': %s") %(self.name, str(e))
            else:
                raise RuntimeError, _("Domain named %s already exists!") %(self.name,)

        child = None
        self._create_devices(meter)
        install_xml = self.get_config_xml()
        if install_xml:
            logging.debug("Creating guest from:\n%s" % install_xml)
            meter.start(size=None, text=_("Creating domain..."))
            self.domain = self.conn.createLinux(install_xml, 0)
            if self.domain is None:
                raise RuntimeError, _("Unable to create domain for the guest, aborting installation!")
            meter.end(0)

            logging.debug("Created guest, looking to see if it is running")

            d = _wait_for_domain(self.conn, self.name)

            if d is None:
                raise RuntimeError, _("It appears that your installation has crashed.  You should be able to find more information in the logs")

            if consolecb:
                logging.debug("Launching console callback")
                child = consolecb(self.domain)
                self._consolechild = child

        boot_xml = self.get_config_xml(install = False)
        logging.debug("Saving XML boot config:\n%s" % boot_xml)
        self.conn.defineXML(boot_xml)

        if child and wait: # if we connected the console, wait for it to finish
            try:
                os.waitpid(child, 0)
            except OSError, (err_no, msg):
                print __name__, "waitpid: %s: %s" % (err_no, msg)

            # ensure there's time for the domain to finish destroying if the
            # install has finished or the guest crashed
            time.sleep(1)

        # This should always work, because it'll lookup a config file
        # for inactive guest, or get the still running install..
        return self.conn.lookupByName(self.name)

    def post_install_check(self):
        return self.installer.post_install_check(self)

    def connect_console(self, consolecb, wait=True):
        logging.debug("Restarted guest, looking to see if it is running")

        self.domain = _wait_for_domain(self.conn, self.name)

        if self.domain is None:
            raise RuntimeError, _("Domain has not existed.  You should be able to find more information in the logs")
        elif self.domain.ID() == -1:
            raise RuntimeError, _("Domain has not run yet.  You should be able to find more information in the logs")

        child = None
        if consolecb:
            logging.debug("Launching console callback")
            child = consolecb(self.domain)
            self._consolechild = child

        if child and wait: # if we connected the console, wait for it to finish
            try:
                os.waitpid(child, 0)
            except OSError, (err_no, msg):
                raise RuntimeError, \
                      "waiting console pid error: %s: %s" % (err_no, msg)

    def validate_parms(self):
        if self.domain is not None:
            raise RuntimeError, _("Domain has already been started!")

    def _set_defaults(self):
        used_targets = []
        for disk in self._get_install_devs(VirtualDevice.VIRTUAL_DEV_DISK):
            if not disk.bus:
                if disk.device == disk.DEVICE_FLOPPY:
                    disk.bus = "fdc"
                else:
                    disk.bus = self._diskbus
            used_targets.append(disk.generate_target(used_targets))

        if self.uuid is None:
            while 1:
                self.uuid = _util.uuidToString(_util.randomUUID())
                if _util.vm_uuid_collision(self.conn, self.uuid):
                    continue
                break
        else:
            if _util.vm_uuid_collision(self.conn, self.uuid):
                raise RuntimeError, _("The UUID you entered is already in "
                                      "use by another guest!")
        if self.name is None or self.memory is None:
            raise RuntimeError, _("Name and memory must be specified for all guests!")

    # Guest Dictionary Helper methods

    def _lookup_osdict_key(self, key):
        """
        Using self.os_type and self.os_variant to find key in OSTYPES
        @returns: dict value, or None if os_type/variant wasn't set
        """
        return osdict.lookup_osdict_key(self.conn, self.type, self.os_type,
                                        self.os_variant, key)

    def _lookup_device_param(self, device_key, param):
        """
        Check the OS dictionary for the prefered device setting for passed
        device type and param (bus, model, etc.)
        """
        return osdict.lookup_device_param(self.conn, self.type, self.os_type,
                                          self.os_variant, device_key, param)

    def terminate_console(self):
        if self._consolechild:
            try:
                os.kill(self._consolechild, signal.SIGKILL)
            except:
                pass

def _wait_for_domain(conn, name):
    # sleep in .25 second increments until either a) we get running
    # domain ID or b) it's been 5 seconds.  this is so that
    # we can try to gracefully handle domain restarting failures
    dom = None
    for ignore in range(1, int(5 / .25)): # 5 seconds, .25 second sleeps
        try:
            dom = conn.lookupByName(name)
            if dom and dom.ID() != -1:
                break
        except libvirt.libvirtError, e:
            logging.debug("No guest running yet: " + str(e))
            dom = None
        time.sleep(0.25)

    return dom

# Back compat class to avoid ABI break
XenGuest = Guest
