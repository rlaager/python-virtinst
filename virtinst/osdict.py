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

import support
from VirtualDevice import VirtualDevice
from virtinst import _virtinst as _

HV_ALL = "all"

"""
Default values for OS_TYPES keys. Can be overwritten at os_type or
variant level
"""

NET   = VirtualDevice.VIRTUAL_DEV_NET
DISK  = VirtualDevice.VIRTUAL_DEV_DISK
INPUT = VirtualDevice.VIRTUAL_DEV_INPUT
SOUND = VirtualDevice.VIRTUAL_DEV_AUDIO

DEFAULTS = {
    "acpi":             True,
    "apic":             True,
    "clock":            "utc",
    "continue":         False,
    "distro":           None,
    "label":            None,
    "pv_cdrom_install": False,

    "devices" : {
        #  "devname" : { "attribute" : [( ["applicable", "hv-type", list"],
        #                               "recommended value for hv-types" ),]},
        INPUT   : {
            "type" : [
                (HV_ALL, "mouse")
            ],
            "bus"  : [
                (HV_ALL, "ps2")
            ],
        },

        DISK    : {
            "bus"  : [
                (HV_ALL, None)
            ],
        },

        NET     : {
            "model": [
                (HV_ALL, None)
            ],
        },

        SOUND : {
            "model": [
                (HV_ALL, "es1370"),
            ]
        }
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

def parse_key_entry(conn, hv_type, key_entry, defaults):
    ret = None
    found = False
    if type(key_entry) == list:

        # List of tuples with (support -> value) mappings
        for tup in key_entry:

            support_key = tup[0]
            value = tup[1]

            # HV_ALL means don't check for support, just return the value
            if support_key != HV_ALL:
                support_ret = support.check_conn_hv_support(conn,
                                                            support_key,
                                                            hv_type)

                if support_ret != True:
                    continue

            found = True
            ret = value
            break
    else:
        found = True
        ret = key_entry

    if not found and defaults:
        ret = parse_key_entry(conn, hv_type, defaults, None)

    return ret

def lookup_osdict_key(conn, hv_type, os_type, var, key):

    defaults = DEFAULTS[key]
    dictval = defaults
    if os_type:
        if var and OS_TYPES[os_type]["variants"][var].has_key(key):
            dictval = OS_TYPES[os_type]["variants"][var][key]
        elif OS_TYPES[os_type].has_key(key):
            dictval = OS_TYPES[os_type][key]

    return parse_key_entry(conn, hv_type, dictval, defaults)


def lookup_device_param(conn, hv_type, os_type, var, device_key, param):

    os_devs = lookup_osdict_key(conn, hv_type, os_type, var, "devices")
    defaults = DEFAULTS["devices"]

    for devs in [os_devs, defaults]:
        if not devs.has_key(device_key):
            continue

        return parse_key_entry(conn, hv_type, devs[device_key][param],
                               defaults.get(param))

    raise RuntimeError(_("Invalid dictionary entry for device '%s %s'" %
                       (device_key, param)))

VIRTIO_DISK = {
    "bus" : [
        (support.SUPPORT_CONN_HV_VIRTIO, "virtio"),
    ]
}

VIRTIO_NET = {
    "model" : [
        (support.SUPPORT_CONN_HV_VIRTIO, "virtio"),
    ]
}

USB_TABLET = {
    "type" : [
        (HV_ALL, "tablet"),
    ],
    "bus"  : [
        (HV_ALL, "usb"),
    ]
}

# NOTE: keep variant keys using only lowercase so we can do case
#       insensitive checks on user passed input
OS_TYPES = {
"linux": {
    "label": "Linux",
    "variants": {
        "rhel2.1": { "label": "Red Hat Enterprise Linux 2.1",
                     "distro": "rhel" },
        "rhel3": { "label": "Red Hat Enterprise Linux 3",
                   "distro": "rhel" },
        "rhel4": { "label": "Red Hat Enterprise Linux 4",
                   "distro": "rhel" },
        "rhel5": { "label": "Red Hat Enterprise Linux 5",
                   "distro": "rhel" },
        "rhel5.4": { "label": "Red Hat Enterprise Linux 5.4 or later",
                     "distro": "rhel",
                      "devices" : {
                        DISK : VIRTIO_DISK,
                        NET  : VIRTIO_NET,
                      },},
        "rhel6": { "label": "Red Hat Enterprise Linux 6", "distro": "rhel",
                   "devices" : {
                        DISK : VIRTIO_DISK,
                        NET  : VIRTIO_NET,
                        INPUT: USB_TABLET,
                   }},
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
                        #DISK : VIRTIO_DISK,
                        NET  : VIRTIO_NET,
                      }},
        "fedora10": { "label": "Fedora 10", "distro": "fedora",
                      "devices" : {
                        DISK : VIRTIO_DISK,
                        NET  : VIRTIO_NET,
                      }},
        "fedora11": { "label": "Fedora 11", "distro": "fedora",
                      "devices" : {
                        DISK : VIRTIO_DISK,
                        NET  : VIRTIO_NET,
                        INPUT: USB_TABLET,
                     }},
        "fedora12": { "label": "Fedora 12", "distro": "fedora",
                      "devices" : {
                        DISK : VIRTIO_DISK,
                        NET  : VIRTIO_NET,
                        INPUT: USB_TABLET,
                     }},
        "fedora13": { "label": "Fedora 13", "distro": "fedora",
                      "devices" : {
                        DISK : VIRTIO_DISK,
                        NET  : VIRTIO_NET,
                        INPUT: USB_TABLET,
                     }},
        "sles10": { "label": "Suse Linux Enterprise Server",
                    "distro": "suse" },
        "sles11": { "label": "Suse Linux Enterprise Server 11",
                    "distro": "suse",
                      "devices" : {
                        DISK : VIRTIO_DISK,
                        NET  : VIRTIO_NET,
                      },
                  },
        "debianetch": { "label": "Debian Etch", "distro": "debian" },
        "debianlenny": { "label": "Debian Lenny", "distro": "debian",
                      "devices" : {
                        DISK : VIRTIO_DISK,
                        NET  : VIRTIO_NET,
                      }},
        "debiansqueeze": { "label": "Debian Squeeze", "distro": "debian",
                      "devices" : {
                        DISK : VIRTIO_DISK,
                        NET  : VIRTIO_NET,
                        INPUT: USB_TABLET,
                     }},
        "ubuntuhardy": { "label": "Ubuntu 8.04 LTS (Hardy Heron)",
                         "distro": "ubuntu",
                         "devices" : {
                            NET  : VIRTIO_NET,
                         }},
        "ubuntuintrepid": { "label": "Ubuntu 8.10 (Intrepid Ibex)",
                            "distro": "ubuntu",
                            "devices" : {
                              NET  : VIRTIO_NET,
                           }},
        "ubuntujaunty": { "label": "Ubuntu 9.04 (Jaunty Jackalope)",
                          "distro": "ubuntu",
                          "devices" : {
                            DISK : VIRTIO_DISK,
                            NET  : VIRTIO_NET,
                        }},
        "ubuntukarmic": { "label": "Ubuntu 9.10 (Karmic Koala)",
                          "distro": "ubuntu",
                          "devices" : {
                            DISK : VIRTIO_DISK,
                            NET  : VIRTIO_NET,
                        }},
        "generic24": { "label": "Generic 2.4.x kernel" },
        "generic26": { "label": "Generic 2.6.x kernel" },
        "virtio26": { "sortby": "genericvirtio26",
                      "label": "Generic 2.6.25 or later kernel with virtio",
                      "devices" : {
                            DISK : VIRTIO_DISK,
                            NET  : VIRTIO_NET,
                    }},

    },
},

"windows": {
    "label": "Windows",
    "clock": "localtime",
    "continue": True,
    "devices" : {
        INPUT : USB_TABLET,
    },
    "variants": {
        "winxp":{ "label": "Microsoft Windows XP (x86)",
                  "acpi": [
                    (support.SUPPORT_CONN_HV_SKIP_DEFAULT_ACPI, False),
                  ],
                  "apic": [
                    (support.SUPPORT_CONN_HV_SKIP_DEFAULT_ACPI, False),
                  ],
        },
        "winxp64":{ "label": "Microsoft Windows XP (x86_64)" },
        "win2k": { "label": "Microsoft Windows 2000",
                  "acpi": [
                    (support.SUPPORT_CONN_HV_SKIP_DEFAULT_ACPI, False),
                  ],
                  "apic": [
                    (support.SUPPORT_CONN_HV_SKIP_DEFAULT_ACPI, False),
                  ],
        },
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
                       "devices" : {
                            INPUT : USB_TABLET,
                         },
                       },
        "opensolaris": { "label": "Sun OpenSolaris",
                       "devices" : {
                            INPUT : USB_TABLET,
                         },
                       },
    },
},

"unix": {
    "label": "UNIX",
    "variants": {
        "freebsd6": { "label": "Free BSD 6.x" ,
                      # http://www.nabble.com/Re%3A-Qemu%3A-bridging-on-FreeBSD-7.0-STABLE-p15919603.html
                      "devices" : {
                        NET : { "model" : [ (HV_ALL, "ne2k_pci") ] }
                      }},
        "freebsd7": { "label": "Free BSD 7.x" ,
                      "devices" : {
                        NET : { "model" : [ (HV_ALL, "ne2k_pci") ] }
                      }},
        "openbsd4": { "label": "Open BSD 4.x" ,
                      # http://calamari.reverse-dns.net:980/cgi-bin/moin.cgi/OpenbsdOnQemu
                      # https://www.redhat.com/archives/et-mgmt-tools/2008-June/msg00018.html
                      "devices" : {
                        NET  : { "model" : [ (HV_ALL, "pcnet") ] }
                    }},
    },
},

"other": {
    "label": "Other",
    "variants": {
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
