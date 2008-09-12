#
# Fullly virtualized guest support
#
# Copyright 2006-2007  Red Hat, Inc.
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

import os
import libvirt
import Guest
import util
import DistroManager
import logging
import time
import platform

from VirtualDisk import VirtualDisk
from DistroManager import PXEInstaller
from virtinst import _virtinst as _


class FullVirtGuest(Guest.XenGuest):

    """
    Default values for OS_TYPES keys. Can be overwritten at os_type or
    variant level
    """
    _DEFAULTS = { \
        "acpi": True,
        "apic": True,
        "clock": "utc",
        "continue": False,
        "distro": None,
        "label": None,
        "devices" : {
         #  "devname" : { "attribute" : [( ["applicable", "hv-type", list"],
         #                               "recommended value for hv-types" ),]},
            "input"   : { "type" : [ (["all"], "mouse") ],
                          "bus"  : [ (["all"], "ps2") ] },
            "disk"    : { "bus"  : [ (["all"], None) ] },
            "net"     : { "model": [ (["all"], None) ] },
        }
    }


    # NOTE: keep variant keys using only lowercase so we can do case
    #       insensitive checks on user passed input
    _OS_TYPES = {\
    "linux": { \
        "label": "Linux",
        "variants": { \
            "rhel2.1": { "label": "Red Hat Enterprise Linux 2.1",
                         "distro": "rhel" },
            "rhel3": { "label": "Red Hat Enterprise Linux 3",
                       "distro": "rhel" },
            "rhel4": { "label": "Red Hat Enterprise Linux 4",
                       "distro": "rhel" },
            "rhel5": { "label": "Red Hat Enterprise Linux 5",
                       "distro": "rhel" },
            "fedora5": { "label": "Fedora Core 5", "distro": "fedora" },
            "fedora6": { "label": "Fedora Core 6", "distro": "fedora" },
            "fedora7": { "label": "Fedora 7", "distro": "fedora" },
            "fedora8": { "label": "Fedora 8", "distro": "fedora" },
            "fedora9": { "label": "Fedora 9", "distro": "fedora" },
            "fedora10": { "label": "Fedora 10", "distro": "fedora",
                          "devices" : {
                            "disk" : { "bus"   : [ (["kvm"], "virtio") ] },
                            "net"  : { "model" : [ (["kvm"], "virtio") ] }
                          }},
            "sles10": { "label": "Suse Linux Enterprise Server",
                        "distro": "suse" },
            "debianetch": { "label": "Debian Etch", "distro": "debian" },
            "debianlenny": { "label": "Debian Lenny", "distro": "debian" },
            "ubuntuhardy": { "label": "Ubuntu Hardy", "distro": "ubuntu",
                             "devices" : {
                                "net"  : { "model" : [ (["kvm"], "virtio") ] }
                             }},
            "generic24": { "label": "Generic 2.4.x kernel" },
            "generic26": { "label": "Generic 2.6.x kernel" },
        },
    },

    "windows": { \
        "label": "Windows",
        "clock": "localtime",
        "continue": True,
        "devices" : {
            "input" : { "type" : [ (["all"], "tablet") ],
                        "bus"  : [ (["all"], "usb"), ] },
        },
        "variants": { \
            "winxp":{ "label": "Microsoft Windows XP",
                      "acpi": False, "apic": False },
            "win2k": { "label": "Microsoft Windows 2000",
                       "acpi": False, "apic": False },
            "win2k3": { "label": "Microsoft Windows 2003" },
            "win2k8": { "label": "Microsoft Windows 2008" },
            "vista": { "label": "Microsoft Windows Vista" },
        },
    },

    "unix": {
        "label": "UNIX",
        "variants": { \
            "solaris9": { "label": "Sun Solaris 9" },
            "solaris10": { "label": "Sun Solaris 10" },
            "freebsd6": { "label": "Free BSD 6.x" ,
                          # http://www.nabble.com/Re%3A-Qemu%3A-bridging-on-FreeBSD-7.0-STABLE-p15919603.html
                          "devices" : {
                            "net" : { "model" : [ (["all"], "ne2k_pci") ] }
                          }},
            "freebsd7": { "label": "Free BSD 7.x" ,
                          "devices" : {
                            "net" : { "model" : [ (["all"], "ne2k_pci") ] }
                          }},
            "openbsd4": { "label": "Open BSD 4.x" ,
                          # http://calamari.reverse-dns.net:980/cgi-bin/moin.cgi/OpenbsdOnQemu
                          # https://www.redhat.com/archives/et-mgmt-tools/2008-June/msg00018.html
                          "devices" : {
                            "net"  : { "model" : [ (["all"], "pcnet") ] }
                        }},
        },
    },

    "other": { \
        "label": "Other",
        "variants": { \
            "msdos": { "label": "MS-DOS", "acpi": False, "apic": False },
            "netware4": { "label": "Novell Netware 4" },
            "netware5": { "label": "Novell Netware 5" },
            "netware6": { "label": "Novell Netware 6" },
            "generic": { "label": "Generic" },
        },
    },}

    def list_os_types():
        return FullVirtGuest._OS_TYPES.keys()
    list_os_types = staticmethod(list_os_types)

    def list_os_variants(type):
        return FullVirtGuest._OS_TYPES[type]["variants"].keys()
    list_os_variants = staticmethod(list_os_variants)

    def get_os_type_label(type):
        return FullVirtGuest._OS_TYPES[type]["label"]
    get_os_type_label = staticmethod(get_os_type_label)

    def get_os_variant_label(type, variant):
        return FullVirtGuest._OS_TYPES[type]["variants"][variant]["label"]
    get_os_variant_label = staticmethod(get_os_variant_label)


    def __init__(self, type=None, arch=None, connection=None, hypervisorURI=None, emulator=None, installer=None):
        if not installer:
            installer = DistroManager.DistroInstaller(type = type, os_type = "hvm")
        Guest.Guest.__init__(self, type, connection, hypervisorURI, installer)
        self.disknode = "hd"
        self.features = { "acpi": None, "pae": util.is_pae_capable(), "apic": None }
        if arch is None:
            arch = platform.machine()
        self.arch = arch

        self.emulator = emulator
        self.loader = None
        guest = self._caps.guestForOSType(type=self.installer.os_type,
                                          arch=self.arch)
        if (not self.emulator) and guest:
            for dom in guest.domains:
                if dom.hypervisor_type == self.installer.type:
                    self.emulator = dom.emulator
                    self.loader = dom.loader

        # Fall back to default hardcoding
        if self.emulator is None:
            if self.type == "xen":
                if os.uname()[4] in ("x86_64"):
                    self.emulator = "/usr/lib64/xen/bin/qemu-dm"
                else:
                    self.emulator = "/usr/lib/xen/bin/qemu-dm"

        if (not self.loader) and self.type == "xen":
            self.loader = "/usr/lib/xen/boot/hvmloader"

        self._os_type = None
        self._os_variant = None


    def get_os_type(self):
        return self._os_type
    def set_os_type(self, val):
        if type(val) is not str:
            raise ValueError(_("OS type must be a string."))
        val = val.lower()
        if FullVirtGuest._OS_TYPES.has_key(val):
            self._os_type = val
            # Invalidate variant, since it may not apply to the new os type
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
        if self._os_type:
            if self._OS_TYPES[self._os_type]["variants"].has_key(val):
                self._os_variant = val
            else:
                raise ValueError, _("OS variant '%(var)s; does not exist in "
                                    "our dictionary for OS type '%(ty)s'" ) % \
                                    {'var' : val, 'ty' : self._os_type}
        else:
            for ostype in self.list_os_types():
                if self._OS_TYPES[ostype]["variants"].has_key(val):
                    logging.debug("Setting os type to '%s' for variant '%s'" %\
                                  (ostype, val))
                    self.os_type = ostype
                    self._os_variant = val
                    return
            raise ValueError, _("Unknown OS variant '%s'" % val)
    os_variant = property(get_os_variant, set_os_variant)

    def os_features(self):
        """Determine the guest features, based on explicit settings in FEATURES
        and the OS_TYPE and OS_VARIANT. FEATURES takes precedence over the OS
        preferences"""
        if self.features is None:
            return None

        # explicitly disabling apic and acpi will override OS_TYPES values
        features = dict(self.features)
        for f in ["acpi", "apic"]:
            val = self._lookup_osdict_key(f)
            features[f] = val
        return features

    def get_os_distro(self):
        return self._lookup_osdict_key("distro")
    os_distro = property(get_os_distro)

    def get_input_device(self):
        typ = self._lookup_device_param("input", "type")
        bus = self._lookup_device_param("input", "bus")
        return (typ, bus)

    def _get_features_xml(self):
        ret = "<features>\n"
        features = self.os_features()
        if features:
            ret += "    "
            for k in sorted(features.keys()):
                v = features[k]
                if v:
                    ret += "<%s/>" %(k,)
            ret += "\n"
        return ret + "  </features>"

    def _get_osblob(self, install):
        osblob = self.installer._get_osblob(install, hvm = True,
            arch = self.arch, loader = self.loader, conn = self.conn)
        if osblob is None:
            return None

        clockxml = self._get_clock_xml()
        if clockxml is not None:
            return "%s\n  %s\n  %s" % (osblob, self._get_features_xml(), \
                                       clockxml)
        else:
            return "%s\n  %s" % (osblob, self._get_features_xml())

    def _get_clock_xml(self):
        val = self._lookup_osdict_key("clock")
        return """<clock offset="%s"/>""" % val

    def _get_device_xml(self, install = True):
        if self.emulator is None:
            return """    <console type='pty'/>
""" + Guest.Guest._get_device_xml(self, install)
        else:
            return ("""    <emulator>%(emulator)s</emulator>
    <console type='pty'/>
""" % { "emulator": self.emulator }) + \
        Guest.Guest._get_device_xml(self, install)

    def validate_parms(self):
        Guest.Guest.validate_parms(self)

    def _prepare_install(self, meter):
        Guest.Guest._prepare_install(self, meter)
        self._installer.prepare(guest = self,
                                meter = meter,
                                distro = self.os_distro)
        if self._installer.install_disk is not None:
            self._install_disks.append(self._installer.install_disk)

    def get_continue_inst(self):
        return self._lookup_osdict_key("continue")

    def continue_install(self, consolecb, meter, wait=True):
        install_xml = self.get_config_xml(disk_boot = True)
        logging.debug("Starting guest from '%s'" % ( install_xml ))
        meter.start(size=None, text="Starting domain...")
        self.domain = self.conn.createLinux(install_xml, 0)
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

    def _lookup_osdict_key(self, key):
        """
        Using self.os_type and self.os_variant to find key in OSTYPES
        @returns: dict value, or None if os_type/variant wasn't set
        """
        typ = self.os_type
        var = self.os_variant
        if typ:
            if var and self._OS_TYPES[typ]["variants"][var].has_key(key):
                return self._OS_TYPES[typ]["variants"][var][key]
            elif self._OS_TYPES[typ].has_key(key):
                return self._OS_TYPES[typ][key]
        return self._DEFAULTS[key]

    def _lookup_device_param(self, device_key, param):
        os_devs = self._lookup_osdict_key("devices")
        default_devs = self._DEFAULTS["devices"]
        for devs in [os_devs, default_devs]:
            if not devs.has_key(device_key):
                continue
            for ent in devs[device_key][param]:
                hv_types = ent[0]
                param_value = ent[1]
                if self.type in hv_types:
                    return param_value
                elif "all" in hv_types:
                    return param_value
        raise RuntimeError(_("Invalid dictionary entry for device '%s %s'" % \
                             (device_key, param)))

    def _get_disk_xml(self, install = True):
        """Get the disk config in the libvirt XML format"""
        ret = ""
        used_targets = []
        for disk in self._install_disks:
            if not disk.bus:
                disk.bus = "ide"
            used_targets.append(disk.generate_target(used_targets))

        for d in self._install_disks:
            saved_path = None
            if d.device == VirtualDisk.DEVICE_CDROM \
               and d.transient and not install:
                # Keep cdrom around, but with no media attached
                # But only if we are a distro that doesn't have a multi
                # stage install (aka not Windows)
                saved_path = d.path
                if not self.get_continue_inst():
                    d.path = None

            if ret:
                ret += "\n"
            ret += d.get_xml_config(d.target)
            if saved_path != None:
                d.path = saved_path

        return ret

    def _set_defaults(self):
        Guest.Guest._set_defaults(self)

        disk_bus  = self._lookup_device_param("disk", "bus")
        net_model = self._lookup_device_param("net", "model")
        pxe_skipped = False

        # Only overwrite params if they weren't already specified
        for net in self._install_nics:
            if net_model and not net.model:
                if net_model == "virtio":
                    # virtio net doesn't seem to support pxe, skip first interface
                    if not pxe_skipped and isinstance(self.installer, PXEInstaller):
                        pxe_skipped = True
                        continue
                net.model = net_model
        for disk in self._install_disks:
            if disk_bus and not disk.bus:
                disk.bus = disk_bus
