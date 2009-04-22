#
# Copyright 2006  Red Hat, Inc.
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
#

#
# Internal utility functions. These do NOT form part of the API and must
# not be used by clients.
#

import stat
import os
import re
import commands
import logging

import libvirt

import virtinst
from virtinst import util
from virtinst import _virtinst as _

try:
    import selinux
except ImportError:
    selinux = None

def is_vdisk(path):
    if not os.path.exists("/usr/sbin/vdiskadm"):
        return False
    if not os.path.exists(path):
        return True
    if os.path.isdir(path) and \
       os.path.exists(path + "/vdisk.xml"):
        return True
    return False

def stat_disk(path):
    """Returns the tuple (isreg, size)."""
    if not os.path.exists(path):
        return True, 0

    if is_vdisk(path):
        size = int(commands.getoutput(
            "vdiskadm prop-get -p max-size " + path))
        return True, size

    mode = os.stat(path)[stat.ST_MODE]

    # os.path.getsize('/dev/..') can be zero on some platforms
    if stat.S_ISBLK(mode):
        try:
            fd = os.open(path, os.O_RDONLY)
            # os.SEEK_END is not present on all systems
            size = os.lseek(fd, 0, 2)
            os.close(fd)
        except:
            size = 0
        return False, size
    elif stat.S_ISREG(mode):
        return True, os.path.getsize(path)

    return True, 0

def blkdev_size(path):
    """Return the size of the block device.  We can't use os.stat() as
    that returns zero on many platforms."""
    fd = os.open(path, os.O_RDONLY)
    # os.SEEK_END is not present on all systems
    size = os.lseek(fd, 0, 2)
    os.close(fd)
    return size

def sanitize_arch(arch):
    """Ensure passed architecture string is the format we expect it.
       Returns the sanitized result"""
    if not arch:
        return arch
    tmparch = arch.lower().strip()
    if re.match(r'i[3-9]86', tmparch):
        return "i686"
    elif tmparch == "amd64":
        return "x86_64"
    return arch

def vm_uuid_collision(conn, uuid):
    """
    Check if passed UUID string is in use by another guest of the connection
    Returns true/false
    """
    check = False
    if uuid is not None:
        try:
            if conn.lookupByUUIDString(uuid) is not None:
                check = True
        except libvirt.libvirtError:
            pass
    return check

def validate_uuid(val):
    if type(val) is not str:
        raise ValueError, _("UUID must be a string.")

    form = re.match("[a-fA-F0-9]{8}[-]([a-fA-F0-9]{4}[-]){3}[a-fA-F0-9]{12}$",
                    val)
    if form is None:
        form = re.match("[a-fA-F0-9]{32}$", val)
        if form is None:
            raise ValueError, \
                  _("UUID must be a 32-digit hexadecimal number. It may take "
                    "the form XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX or may omit "
                    "hyphens altogether.")

        else:   # UUID had no dashes, so add them in
            val = (val[0:8] + "-" + val[8:12] + "-" + val[12:16] +
                   "-" + val[16:20] + "-" + val[20:32])
    return val

def validate_name(name_type, val):
    if type(val) is not type("string") or len(val) > 50 or len(val) == 0:
        raise ValueError, _("%s name must be a string between 0 and 50 "
                            "characters") % name_type
    if re.match("^[0-9]+$", val):
        raise ValueError, _("%s name can not be only numeric characters") % \
                          name_type
    if re.match("^[a-zA-Z0-9._-]+$", val) == None:
        raise ValueError, _("%s name can only contain alphanumeric, '_', '.', "
                            "or '-' characters") % name_type

def xml_append(orig, new):
    """
    Little function that helps generate consistent xml
    """
    if not new:
        return orig
    if orig:
        orig += "\n"
    return orig + new

def fetch_all_guests(conn):
    """
    Return 2 lists: ([all_running_vms], [all_nonrunning_vms])
    """
    active = []
    inactive = []

    # Get all active VMs
    ids = conn.listDomainsID()
    for i in ids:
        try:
            vm = conn.lookupByID(i)
            active.append(vm)
        except libvirt.libvirtError:
            # guest probably in process of dieing
            logging.warn("Failed to lookup active domain id %d" % i)

    # Get all inactive VMs
    names = conn.listDefinedDomains()
    for name in names:
        try:
            vm = conn.lookupByName(name)
            inactive.append(vm)
        except:
            # guest probably in process of dieing
            logging.warn("Failed to lookup inactive domain %d" % name)

    return (active, inactive)

def disk_exists(conn, path):
    """Use VirtualDisk errors to determine if a storage path exists."""
    try:
        virtinst.VirtualDisk(conn=conn, path=path, size=.000001)
    except:
        # This shouldn't fail, so just raise the error
        raise

    try:
        virtinst.VirtualDisk(conn=conn, path=path)
    except:
        # If this fails, but the previous attempt didn't, assume that
        # 'size' is failing factor, and the path doesn't exist
        return False

    return True

# Selinux helpers

def have_selinux():
    return bool(selinux) and bool(selinux.is_selinux_enabled())

def selinux_restorecon(path):
    if have_selinux() and hasattr(selinux, "restorecon"):
        try:
            selinux.restorecon(path)
        except Exception, e:
            logging.debug("Restoring context for '%s' failed: %s" % (path,
                                                                     str(e)))
def selinux_getfilecon(path):
    if have_selinux():
        return selinux.getfilecon(path)[1]
    return None

def selinux_setfilecon(storage, label):
    """
    Wrapper for selinux.setfilecon. Libvirt may be able to relabel existing
    storage someday, we can fold that into this.
    """
    if have_selinux():
        selinux.setfilecon(storage, label)

def selinux_is_label_valid(label):
    """
    Check if the passed label is an actually valid selinux context label
    Returns False if selinux support is not present
    """
    return bool(have_selinux() and (not hasattr(selinux, "context_new") or
                                    selinux.context_new(label)))

def selinux_rw_label():
    """
    Expected SELinux label for read/write disks
    """
    con = "system_u:object_r:virt_image_t:s0"

    if not selinux_is_label_valid(con):
        con = ""
    return con

def selinux_readonly_label():
    """
    Expected SELinux label for things like readonly installation media
    """
    con = "system_u:object_r:virt_content_t:s0"

    if not selinux_is_label_valid(con):
        # The RW label is newer than the RO one, so see if that exists
        con = selinux_rw_label()
    return con

#
# These functions accidentally ended up in the API under virtinst.util
#
default_route = util.default_route
default_bridge = util.default_bridge
default_network = util.default_network
default_connection = util.default_connection
get_cpu_flags = util.get_cpu_flags
is_pae_capable = util.is_pae_capable
is_blktap_capable = util.is_blktap_capable
get_default_arch = util.get_default_arch
randomMAC = util.randomMAC
randomUUID = util.randomUUID
uuidToString = util.uuidToString
uuidFromString = util.uuidFromString
get_host_network_devices = util.get_host_network_devices
get_max_vcpus = util.get_max_vcpus
get_phy_cpus = util.get_phy_cpus
xml_escape = util.xml_escape
compareMAC = util.compareMAC
default_keymap = util.default_keymap
pygrub_path = util.pygrub_path
uri_split = util.uri_split
is_uri_remote = util.is_uri_remote
get_uri_hostname = util.get_uri_hostname
get_uri_transport = util.get_uri_transport
get_uri_driver = util.get_uri_driver
is_storage_capable = util.is_storage_capable
get_xml_path = util.get_xml_path
lookup_pool_by_path = util.lookup_pool_by_path
check_keytable = util.check_keytable
