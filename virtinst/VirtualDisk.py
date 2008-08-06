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

import os, os.path
import statvfs
import stat, sys, time
import re
import libxml2
import urlgrabber.progress as progress
import util
import libvirt
import __builtin__
from virtinst import _virtinst as _

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

    def __init__(self, path = None, size = None, transient=False, type=None, device=DEVICE_DISK, driverName=None, driverType=None, readOnly=False, sparse=True):
        """@path is the path to the disk image.
           @size is the size of the disk image in gigabytes."""
        self.size = size
        self.sparse = sparse
        self.transient = transient
        self.path = path
        self._type = type
        self._readOnly = readOnly
        self._device = device
        self._driverName = driverName
        self._driverType = driverType
        self.target = None

        # Reset type variable as the builtin function
        type = __builtin__.type

        if self._device == self.DEVICE_CDROM:
            self._readOnly = True

        # Only floppy or cdrom can be created w/o media
        if self.path is None:
            if device != self.DEVICE_FLOPPY and device != self.DEVICE_CDROM:
                raise ValueError, _("Disk type '%s' requires a path") % device
            return

        # Basic path validation
        if type(self.path) is not str:
            raise ValueError, _("The %s path must be a string or None.") % \
                              self._device
        self.path = os.path.abspath(self.path)
        if os.path.isdir(self.path):
            raise ValueError, _("The %s path must be a file or a device, not a directory") % self._device

        # Main distinction: does path exist or not?
        if os.path.exists(self.path):
            logging.debug("VirtualDisk path exists.")

            # Determine disk type
            if stat.S_ISBLK(os.stat(self.path)[stat.ST_MODE]):
                logging.debug("Path is block file: Assuming Block disk type.")
                newtype = VirtualDisk.TYPE_BLOCK
            else:
                newtype = VirtualDisk.TYPE_FILE

            if self._type is not None and self._type != newtype:
                raise ValueError, _("Path is not specified type '%s'." % \
                                    self._type)
            self._type = newtype


        else:
            logging.debug("VirtualDisk path does not exist.")
            if self._device == self.DEVICE_FLOPPY or \
               self._device == self.DEVICE_CDROM:
                raise ValueError, _("The %s path must exist.") % self._device

            if self._type is self.TYPE_BLOCK:
                raise ValueError, _("Block device path must exist.")
            self._type = self.TYPE_FILE

            # Path doesn't exist: make sure we have write access to dir
            if not os.access(os.path.dirname(self.path), os.W_OK):
                raise ValueError, _("No write access to directory '%s'") % \
                                  os.path.dirname(self.path)

            # Ensure size was specified
            if size is None or type(size) not in [int, float] or size < 0:
                raise ValueError, \
                      _("A size must be provided for non-existent disks")

            ret = self.size_conflict()
            if ret[0]:
                raise ValueError, ret[1]
            elif ret[1]:
                logging.warn(ret[1])


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
        if self._type == VirtualDisk.TYPE_FILE and self.path is not None \
           and not os.path.exists(self.path):
            size_bytes = long(self.size * 1024L * 1024L * 1024L)
            progresscb.start(filename=self.path,size=long(size_bytes), \
                             text=_("Creating storage file..."))
            fd = None
            try: 
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
                except OSError, detail:
                    raise RuntimeError, "Error creating diskimage " + self.path + ": " + detail.strerror
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
        if self.path is not None:
            path = util.xml_escape(self.path)
            ret += "      <source %(typeattr)s='%(disk)s'/>\n" % { "typeattr": typeattr, "disk": path }
        if self.target is not None:
            disknode = self.target
        ret += "      <target dev='%(disknode)s'/>\n" % { "disknode": disknode }
        if self.read_only:
            ret += "      <readonly/>\n"
        ret += "    </disk>"
        return ret

    def size_conflict(self):
        """size_conflict: reports if disk size conflicts with available space

           returns a two element tuple:
               first element is True if fatal conflict occurs
               second element is a string description of the conflict or None
           Non fatal conflicts (sparse disk exceeds available space) will
           return (False, "description of collision")"""

        if not self.size or not self.path or os.path.exists(self.path) or \
           self.type != self.TYPE_FILE:
            return (False, None)

        ret = False
        msg = None
        vfs = os.statvfs(os.path.dirname(self.path))
        avail = vfs[statvfs.F_FRSIZE] * vfs[statvfs.F_BAVAIL]
        need = self.size * 1024 * 1024 * 1024
        if need > avail:
            if self.sparse:
                msg = _("The filesystem will not have enough free space"
                        " to fully allocate the sparse file when the guest"
                        " is running.")
            else:
                ret = True
                msg = _("There is not enough free space to create the disk.")
        return (ret, msg)

    def is_conflict_disk(self, conn):
        vms = []
        # get working domain's name
        ids = conn.listDomainsID();
        for id in ids:
            try:
                vm = conn.lookupByID(id)
                vms.append(vm)
            except libvirt.libvirtError:
                # guest probably in process of dieing
                logging.warn("Failed to lookup domain id %d" % id)
        # get defined domain
        names = conn.listDefinedDomains()
        for name in names:
            try:
                vm = conn.lookupByName(name)
                vms.append(vm)
            except libvirt.libvirtError:
                # guest probably in process of dieing
                logging.warn("Failed to lookup domain name %s" % name)

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
