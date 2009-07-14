#
# List of OS Specific data
#
# Copyright 2006-2008  Red Hat, Inc.
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

import libvirt

import _util

"""
Default values for OS_TYPES keys. Can be overwritten at os_type or
variant level
"""
DEFAULTS = { \
    "acpi": True,
    "apic": True,
    "clock": "utc",
    "continue": False,
    "distro": None,
    "label": None,
    "pv_cdrom_install": False,
    "devices" : {
     #  "devname" : { "attribute" : [( ["applicable", "hv-type", list"],
     #                               "recommended value for hv-types" ),]},
        "input"   : { "type" : [ (["all"], "mouse") ],
                      "bus"  : [ (["all"], "ps2") ] },
        "disk"    : { "bus"  : [ (["all"], None) ] },
        "net"     : { "model": [ (["all"], None) ] },
    }
}

def sort_helper(tosort):
    """Helps properly sorting os dictionary entires"""
    key_mappings = {}
    keys = []
    retlist = []

    for key in tosort.keys():
        if tosort[key].get("skip"):
            continue

        sortby = tosort[key].get("sortby")
        if not sortby:
            sortby = key
        key_mappings[sortby] = key
        keys.append(sortby)

    keys.sort()
    for key in keys:
        retlist.append(key_mappings[key])

    return retlist

def parse_key_entry(conn, hv_type, key_entry):
    d = _util.get_uri_driver(conn.getURI())
    libver = libvirt.getVersion()
    try:
        drvver = libvirt.getVersion(d)[1]
    except:
        drvver = 0

    if type(key_entry) == list:
        # List of tuples with hv_type, version, etc. mappings
        for tup in key_entry:
            exp_hvs = tup[0]
            if type(exp_hvs) != list:
                exp_hvs = [exp_hvs]
            exp_hv_ver = 0
            exp_lib_ver = 0
            val = tup[-1]

            if len(tup) > 2:
                exp_hv_ver = tup[1]
            if len(tup) > 3:
                exp_lib_ver = tup[2]

            if hv_type not in exp_hvs and "all" not in exp_hvs:
                continue

            if exp_hv_ver and drvver > exp_hv_ver:
                continue

            if exp_lib_ver and libver > exp_lib_ver:
                continue

            return val
    else:
        return key_entry

def lookup_osdict_key(conn, hv_type, os_type, var, key):

    dictval = DEFAULTS[key]
    if os_type:
        if var and OS_TYPES[os_type]["variants"][var].has_key(key):
            dictval = OS_TYPES[os_type]["variants"][var][key]
        elif OS_TYPES[os_type].has_key(key):
            dictval = OS_TYPES[os_type][key]

    return parse_key_entry(conn, hv_type, dictval)


def lookup_device_param(conn, hv_type, os_type, var, device_key, param):

    os_devs = lookup_osdict_key(conn, hv_type, os_type, var, "devices")
    default_devs = DEFAULTS["devices"]

    for devs in [os_devs, default_devs]:
        if not devs.has_key(device_key):
            continue

        return parse_key_entry(conn, hv_type, devs[device_key][param])

    raise RuntimeError(_("Invalid dictionary entry for device '%s %s'" %
                       (device_key, param)))

# NOTE: keep variant keys using only lowercase so we can do case
#       insensitive checks on user passed input
OS_TYPES = {\
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
        "fedora5": { "sortby": "fedora05",
                     "label": "Fedora Core 5", "distro": "fedora" },
        "fedora6": { "sortby": "fedora06",
                     "label": "Fedora Core 6", "distro": "fedora" },
        "fedora7": { "sortby": "fedora07",
                     "label": "Fedora 7", "distro": "fedora" },
        "fedora8": { "sortby": "fedora08",
                     "label": "Fedora 8", "distro": "fedora" },
        "fedora9": { "sortby":  "fedora09",
                     "label": "Fedora 9", "distro": "fedora",
                      "devices" : {
                        # Apparently F9 has selinux errors when installing
                        # with virtio:
                        # https://bugzilla.redhat.com/show_bug.cgi?id=470386
                        #"disk" : { "bus"   : [ (["kvm"], "virtio") ] },
                        "net"  : { "model" : [ (["kvm"], "virtio") ] }
                      }},
        "fedora10": { "label": "Fedora 10", "distro": "fedora",
                      "devices" : {
                        "disk" : { "bus"   : [ (["kvm"], "virtio") ] },
                        "net"  : { "model" : [ (["kvm"], "virtio") ] }
                      }},
        "fedora11": { "label": "Fedora 11", "distro": "fedora",
                      "devices" : {
                        "disk" : { "bus"   : [ (["kvm"], "virtio") ] },
                        "net"  : { "model" : [ (["kvm"], "virtio") ] },
                        "input" : { "type" : [ (["all"], "tablet") ],
                                    "bus"  : [ (["all"], "usb"), ] },
                     }},
        "sles10": { "label": "Suse Linux Enterprise Server",
                    "distro": "suse" },
        "debianetch": { "label": "Debian Etch", "distro": "debian" },
        "debianlenny": { "label": "Debian Lenny", "distro": "debian",
                      "devices" : {
                        "disk" : { "bus"   : [ (["kvm"], "virtio") ] },
                        "net"  : { "model" : [ (["kvm"], "virtio") ] }
                      }},
        "debiansqueeze": { "label": "Debian Squeeze", "distro": "debian",
                      "devices" : {
                        "disk" : { "bus"   : [ (["kvm"], "virtio") ] },
                        "net"  : { "model" : [ (["kvm"], "virtio") ] },
                        "input" : { "type" : [ (["all"], "tablet") ],
                                    "bus"  : [ (["all"], "usb"), ] },
                     }},
        "ubuntuhardy": { "label": "Ubuntu 8.04 LTS (Hardy Heron)",
                         "distro": "ubuntu",
                         "devices" : {
                            "net"  : { "model" : [ (["kvm"], "virtio") ] }
                         }},
        "ubuntuintrepid": { "label": "Ubuntu 8.10 (Intrepid Ibex)",
                            "distro": "ubuntu",
                            "devices" : {
                                "net"  : { "model" : [ (["kvm"], "virtio") ] }
                           }},
        "ubuntujaunty": { "label": "Ubuntu 9.04 (Jaunty Jackalope)",
                          "distro": "ubuntu",
                          "devices" : {
                            "net"  : { "model" : [ (["kvm"], "virtio") ] },
                            "disk" : { "bus"   : [ (["kvm"], "virtio") ] }
                        }},
        "generic24": { "label": "Generic 2.4.x kernel" },
        "generic26": { "label": "Generic 2.6.x kernel" },
        "virtio26": { "sortby": "genericvirtio26",
                      "label": "Generic 2.6.25 or later kernel with virtio",
                      "devices" : {
                        "disk" : { "bus"   : [ (["kvm"], "virtio") ] },
                        "net"  : { "model" : [ (["kvm"], "virtio") ] }
                    }},

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
        "winxp":{ "label": "Microsoft Windows XP (x86)",
                  "acpi": False, "apic": False },
        "winxp64":{ "label": "Microsoft Windows XP (x86_64)" },
        "win2k": { "label": "Microsoft Windows 2000",
                   "acpi": False, "apic": False },
        "win2k3": { "label": "Microsoft Windows 2003" },
        "win2k8": { "label": "Microsoft Windows 2008" },
        "vista": { "label": "Microsoft Windows Vista" },
        "win7": { "label": "Microsoft Windows 7" }
    },
},

"solaris": {
    "label": "Solaris",
    "clock": "localtime",
    "pv_cdrom_install": True,
    "variants": {
        "solaris9": { "label": "Sun Solaris 9", },
        "solaris10": { "label": "Sun Solaris 10",
                       "devices" : { "input" : {
                         "type" : [ (["all"], "tablet") ],
                         "bus"  : [ (["all"], "usb"), ]
                         } },
                       },
        "opensolaris": { "label": "Sun OpenSolaris",
                       "devices" : { "input" : {
                           "type" : [ (["all"], "tablet") ],
                           "bus"  : [ (["all"], "usb"), ]
                         } },
                       },
    },
},

"unix": {
    "label": "UNIX",
    "variants": { \
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
        "netware6": { "label": "Novell Netware 6", "pv_cdrom_install": True, },
        "generic": { "label": "Generic" },
    },
},}

# Back compatibility entries
solaris_compat = OS_TYPES["unix"]["variants"]

solaris_compat["solaris9"] = OS_TYPES["solaris"]["variants"]["solaris9"].copy()
solaris_compat["solaris9"]["skip"] = True

solaris_compat["solaris10"] = OS_TYPES["solaris"]["variants"]["solaris10"].copy()
solaris_compat["solaris10"]["skip"] = True
