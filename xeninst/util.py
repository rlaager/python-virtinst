#!/usr/bin/python -tt
#
# Utility functions used for guest installation
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

import random


def get_cpu_flags():
    f = open("/proc/cpuinfo")
    lines = f.readlines()
    f.close()
    for line in lines:
        if not line.startswith("flags"):
            continue
        # get the actual flags
        flags = line[:-1].split(":", 1)[1]
        # and split them
        flst = flags.split(" ")
        return flst
    return []

def is_pae_capable():
    """Determine if a machine is PAE capable or not."""
    flags = get_cpu_flags()
    if "pae" in flags:
        return True
    return False

def is_hvm_capable():
    # FIXME: should this check msrs or use something exported by Xen
    # to see if we actually have FV support
    """Determine if a machine is HVM capable or not."""

    flags = get_cpu_flags()
    if "vmx" in flags:
        return True
    if "svm" in flags:
        return True
    return False


# this function is directly from xend/server/netif.py and is thus
# available under the LGPL,
# Copyright 2004, 2005 Mike Wray <mike.wray@hp.com>
# Copyright 2005 XenSource Ltd
def randomMAC():
    """Generate a random MAC address.

    Uses OUI (Organizationally Unique Identifier) 00-16-3E, allocated to
    Xensource, Inc. The OUI list is available at
    http://standards.ieee.org/regauth/oui/oui.txt.

    The remaining 3 fields are random, with the first bit of the first
    random field set 0.

    @return: MAC address string
    """
    mac = [ 0x00, 0x16, 0x3e,
            random.randint(0x00, 0x7f),
            random.randint(0x00, 0xff),
            random.randint(0x00, 0xff) ]
    return ':'.join(map(lambda x: "%02x" % x, mac))

# the following three functions are from xend/uuid.py and are thus
# available under the LGPL,
# Copyright 2005 Mike Wray <mike.wray@hp.com>
# Copyright 2005 XenSource Ltd
def randomUUID():
    """Generate a random UUID."""

    return [ random.randint(0, 255) for _ in range(0, 16) ]

def uuidToString(u):
    return "-".join(["%02x" * 4, "%02x" * 2, "%02x" * 2, "%02x" * 2,
                     "%02x" * 6]) % tuple(u)

def uuidFromString(s):
    s = s.replace('-', '')
    return [ int(s[i : i + 2], 16) for i in range(0, 32, 2) ]
