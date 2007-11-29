#!/usr/bin/python -tt
#
# Convenience module for fetching/creating kernel/initrd files
# or bootable CD images.
#
# Copyright 2006-2007  Red Hat, Inc.
# Daniel P. Berrange <berrange@redhat.com>
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

import logging
import os
import gzip
import re
import struct
import tempfile
import Guest
from virtinst import _virtinst as _

from ImageFetcher import MountedImageFetcher
from ImageFetcher import URIImageFetcher

from OSDistro import FedoraImageStore
from OSDistro import RHELImageStore
from OSDistro import CentOSImageStore
from OSDistro import SuseImageStore
from OSDistro import DebianImageStore
from OSDistro import UbuntuImageStore
from OSDistro import GentooImageStore
from OSDistro import MandrivaImageStore

def _fetcherForURI(uri, scratchdir=None):
    if uri.startswith("http://") or uri.startswith("ftp://"):
        return URIImageFetcher(uri, scratchdir)
    else:
        return MountedImageFetcher(uri, scratchdir)

def _storeForDistro(fetcher, baseuri, type, progresscb, distro=None, scratchdir=None):
    stores = []
    if distro == "fedora" or distro is None:
        stores.append(FedoraImageStore(baseuri, type, scratchdir))
    if distro == "rhel" or distro is None:
        stores.append(RHELImageStore(baseuri, type, scratchdir))
    if distro == "centos" or distro is None:
        stores.append(CentOSImageStore(baseuri, type, scratchdir))
    if distro == "suse" or distro is None:
        stores.append(SuseImageStore(baseuri, type, scratchdir))
    if distro == "debian" or distro is None:
        stores.append(DebianImageStore(baseuri, type, scratchdir))
    if distro == "ubuntu" or distro is None:
        stores.append(UbuntuImageStore(baseuri, type, scratchdir))
    if distro == "gentoo" or distro is None:
        stores.append(GentooImageStore(baseuri, type, scratchdir))
    if distro == "mandriva" or distro is None:
        stores.append(MandrivaImageStore(baseuri, type, scratchdir))

    for store in stores:
        if store.isValidStore(fetcher, progresscb):
            return store

    raise ValueError, _("Could not find an installable distribution the install location")


# Method to fetch a krenel & initrd pair for a particular distro / HV type
def acquireKernel(baseuri, progresscb, scratchdir="/var/tmp", type=None, distro=None):
    fetcher = _fetcherForURI(baseuri, scratchdir)
    
    try:
        fetcher.prepareLocation(progresscb)
    except ValueError, e:
        raise ValueError, _("Invalid install location: ") + str(e)

    try:
        store = _storeForDistro(fetcher=fetcher, baseuri=baseuri, type=type, \
                                progresscb=progresscb, distro=distro, scratchdir=scratchdir)
        return store.acquireKernel(fetcher, progresscb)
    finally:
        fetcher.cleanupLocation()

# Method to fetch a bootable ISO image for a particular distro / HV type
def acquireBootDisk(baseuri, progresscb, scratchdir="/var/tmp", type=None, distro=None):
    fetcher = _fetcherForURI(baseuri, scratchdir)

    try:
        fetcher.prepareLocation(progresscb)
    except ValueError, e:
        raise ValueError, _("Invalid install location: ") + str(e)

    try:
        store = _storeForDistro(fetcher=fetcher, baseuri=baseuri, type=type, \
                                progresscb=progresscb, distro=distro, scratchdir=scratchdir)
        return store.acquireBootDisk(fetcher, progresscb)
    finally:
        fetcher.cleanupLocation()

class DistroInstaller(Guest.Installer):
    def __init__(self, type = "xen", location = None, boot = None, extraargs = None):
        Guest.Installer.__init__(self, type, location, boot, extraargs)

    def get_location(self):
        return self._location
    def set_location(self, val):
        if not (val.startswith("http://") or val.startswith("ftp://") or
                val.startswith("nfs:") or val.startswith("/")):
            raise ValueError(_("Install location must be an NFS, HTTP or FTP network install source, or local file/device"))
        if os.geteuid() != 0 and val.startswith("nfs:"):
            raise ValueError(_("NFS installations are only supported as root"))
        self._location = val
    location = property(get_location, set_location)

    def _prepare_cdrom(self, guest, distro, meter):
        if self.location.startswith("/") and os.path.exists(self.location):
            # Huzzah, a local file/device
            cdrom = self.location
        else:
            # Xen needs a boot.iso if its a http://, ftp://, or nfs:/ url
            cdrom = acquireBootDisk(self.location,
                                    meter,
                                    scratchdir = self.scratchdir,
                                    distro = distro)
            self._tmpfiles.append(cdrom)

        self._install_disk = Guest.VirtualDisk(cdrom,
                                               device=Guest.VirtualDisk.DEVICE_CDROM,
                                               readOnly=True,
                                               transient=True)

    def _prepare_kernel_and_initrd(self, guest, distro, meter):
        if self.boot is not None:
            # Got a local kernel/initrd already
            self.install["kernel"] = self.boot["kernel"]
            self.install["initrd"] = self.boot["initrd"]
            if not self.extraargs is None:
                self.install["extraargs"] = self.extraargs
        else:
            ostype = None
            if self.type == "xen":
                ostype = "xen"
            # Need to fetch the kernel & initrd from a remote site, or
            # out of a loopback mounted disk image/device
            (kernelfn, initrdfn, args) = acquireKernel(self.location,
                                                       meter,
                                                       scratchdir = self.scratchdir,
                                                       type = ostype,
                                                       distro = distro)
            self.install["kernel"] = kernelfn
            self.install["initrd"] = initrdfn
            if not self.extraargs is None:
                self.install["extraargs"] = self.extraargs + " " + args
            else:
                self.install["extraargs"] = args

            self._tmpfiles.append(kernelfn)
            self._tmpfiles.append(initrdfn)

        # If they're installing off a local file/device, we map it
        # through to a virtual harddisk
        if self.location is not None and self.location.startswith("/"):
            self._install_disk = Guest.VirtualDisk(self.location,
                                                   readOnly=True,
                                                   transient=True)

    def prepare(self, guest, meter, distro = None):
        self.cleanup()

        self.install = {
            "kernel" : "",
            "initrd" : "",
            "extraargs" : "",
        }

        if self.cdrom:
            self._prepare_cdrom(guest, distro, meter)
        else:
            self._prepare_kernel_and_initrd(guest, distro, meter)

    def _get_osblob(self, install, hvm, arch = None, loader = None):
        osblob = ""
        if install or hvm:
            osblob = "<os>\n"

            if hvm:
                type = "hvm"
            else:
                type = "linux"

            if arch:
                osblob += "    <type arch='%s'>%s</type>\n" % (arch, type)
            else:
                osblob += "    <type>%s</type>\n" % type

            if install and self.install["kernel"]:
                osblob += "    <kernel>%s</kernel>\n"   % self.install["kernel"]
                osblob += "    <initrd>%s</initrd>\n"   % self.install["initrd"]
                osblob += "    <cmdline>%s</cmdline>\n" % self.install["extraargs"]
            else:
                if loader:
                    osblob += "    <loader>%s</loader>\n" % loader

                if install:
                    osblob += "    <boot dev='cdrom'/>\n"
                else:
                    osblob += "    <boot dev='hd'/>\n"

            osblob += "  </os>"
        else:
            osblob += "<bootloader>/usr/bin/pygrub</bootloader>"

        return osblob

    def post_install_check(self, guest):
        # Check for the 0xaa55 signature at the end of the MBR
        fd = os.open(guest._install_disks[0].path, os.O_RDONLY)
        buf = os.read(fd, 512)
        os.close(fd)
        return len(buf) == 512 and struct.unpack("H", buf[0x1fe: 0x200]) == (0xaa55,)



class PXEInstaller(Guest.Installer):
    def __init__(self, type = "xen", location = None, boot = None, extraargs = None):
        Guest.Installer.__init__(self, type, location, boot, extraargs)

    def prepare(self, guest, meter, distro = None):
        pass

    def _get_osblob(self, install, hvm, arch = None, loader = None):
        osblob = ""
        if install or hvm:
            osblob = "<os>\n"

            if hvm:
                type = "hvm"
            else:
                type = "linux"

            if arch:
                osblob += "    <type arch='%s'>%s</type>\n" % (arch, type)
            else:
                osblob += "    <type>%s</type>\n" % type

            if loader:
                osblob += "    <loader>%s</loader>\n" % loader

            if install:
                osblob += "    <boot dev='network'/>\n"
            else:
                osblob += "    <boot dev='hd'/>\n"

            osblob += "  </os>"
        else:
            osblob += "<bootloader>/usr/bin/pygrub</bootloader>"

        return osblob

    def post_install_check(self, guest):
        # Check for the 0xaa55 signature at the end of the MBR
        fd = os.open(guest._install_disks[0].path, os.O_RDONLY)
        buf = os.read(fd, 512)
        os.close(fd)
        return len(buf) == 512 and struct.unpack("H", buf[0x1fe: 0x200]) == (0xaa55,)

