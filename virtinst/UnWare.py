#
# Processing of VMWare(tm) .vmx files
#
# Copyright 2007  Red Hat, Inc.
# David Lutterkort <dlutter@redhat.com>
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

import time
import sys
import os
import logging
import ImageParser
import util

class Disk:
    """A disk for a VMWare(tm) virtual machine"""

    MONOLITHIC_FLAT   = "monolithicFlat"
    TWO_GB_MAX_EXTENT_SPARSE = "twoGbMaxExtentSparse"
    # This seems only to be usable if the vmdk header is embedded in the
    # data file, not when the descriptor is in a separate text file. Use
    # TWO_GB_MAX_EXTENT_SPARSE instead.
    # VMWare's(tm) documentation of VMDK seriously sucks. A lot.
    MONOLITHIC_SPARSE = "monolithicSparse"

    IDE_HEADS = 16
    IDE_SECTORS = 63
    
    def __init__(self, descriptor, extent, size, dev, format):
        """Create a new disk. DESCRIPTOR is the name of the VMDK descriptor
        file. EXTENT is the name of the file holding the actual data. SIZE
        is the filesize in bytes. DEV identifies the device, for IDE (the
        only one supported right now) it should be $bus:$master. FORMAT is
        the format of the underlying extent, one of the formats defined in
        virtinst.ImageParser.Disk"""
        self.cid = 0xffffffff
        self.createType = Disk.MONOLITHIC_FLAT
        self.descriptor = descriptor
        self.extent = extent
        self.size = size
        self.dev = dev
        self.format = format

    def make_extent(self, base):
        """Write the descriptor file, and create the extent as a monolithic 
        sparse extent if it does not exist yet"""
        f = os.path.join(base, self.extent)
        logging.debug("Checking %s" % f)
        if not os.path.exists(f):
            util.system("qemu-img create -f vmdk %s %d" % (f, self.size/1024))
            self.createType = Disk.TWO_GB_MAX_EXTENT_SPARSE
        else:
            qemu = os.popen("qemu-img info %s" % f, "r")
            for l in qemu:
                (tag, val) = l.split(":")
                if tag == "file format" and val.strip() == "vmdk":
                    self.createType = Disk.TWO_GB_MAX_EXTENT_SPARSE
            qemu.close()
        return self.extent
        
    def _VMDK_TEMPLATE(self):

        blocks = self.size/512
        if self.createType == Disk.MONOLITHIC_FLAT:
            vmdk_extent_info= "RW %d FLAT \"%s\" 0\n" % (blocks, os.path.basename(self.extent))
        else: # Disk.MONOLITHIC_SPARSE
            vmdk_extent_info= "RW %d SPARSE \"%s\"\n" % (blocks, os.path.basename(self.extent))

        vmdk_dict = {
            "SELF_CID" : self.cid,
            "CREATE_TYPE" : self.createType,
            "IDE_SECTORS" : Disk.IDE_SECTORS,
            "IDE_HEADS" : Disk.IDE_HEADS,
            "IDE_BLOCKS" : blocks,
            "IDE_CYLINDERS" : blocks/(Disk.IDE_SECTORS*Disk.IDE_HEADS),
            "VMDK_EXTENT_INFO" : vmdk_extent_info,
        }    
        
        vmdk = """# Disk DescriptorFile
# Generated from virtinst
version=1

CID=%(SELF_CID)s
parentCID=ffffffff
createType="%(CREATE_TYPE)s"

# Extent description
%(VMDK_EXTENT_INFO)s

# Disk Data Base
ddb.virtualHWVersion = "4"
ddb.adapterType = "ide"
ddb.geometry.sectors = "%(IDE_SECTORS)s"
ddb.geometry.heads = "%(IDE_HEADS)s"
ddb.geometry.cylinders = "%(IDE_CYLINDERS)s"
"""     
        vmdk = vmdk % vmdk_dict
        return vmdk


    def to_vmx(self):
        """Return the fragment for the VMX file for this disk"""

        vmx = ""
        vmx_dict = {
            "dev"      : self.dev,
            "disk_filename" : self.descriptor
        }
        if self.format == ImageParser.Disk.FORMAT_ISO:
            vmx = _VMX_ISO_TEMPLATE % vmx_dict
        else:   # FORMAT_RAW
            vmx = _VMX_IDE_TEMPLATE % vmx_dict
        return vmx
        
class Image:
    """Represent an image for generation of a VMWare(tm) description"""

    def __init__(self, image = None):
        if image is not None:
            self._init_from_image(image)

    def _init_from_image(self, image):
        domain = image.domain
        boot = domain.boots[0]

        self.base = image.base
        self.name = image.name
        self.descr = image.descr
        self.label = image.label
        self.vcpu = domain.vcpu
        self.memory = domain.memory
        # Make this a boolean based on the existence of one or more
        # interfaces in the domain
        self.interface = domain.interface > 0

        self.disks = []
        for d in boot.drives:
            disk = d.disk
            descriptor = sub_ext(disk.file, ".vmdk")
            if disk.size is None:
                f = os.path.join(image.base, disk.file)
                size = os.stat(f).st_size
            else:
                size = long(disk.size) * 1024L * 1024L
            ide_count = len(self.disks)
            dev = "%d:%d" % (ide_count / 2, ide_count % 2)
            self.disks.append(Disk(descriptor, disk.file, size, dev, 
                                   disk.format))

    def make(self, base):
        """Write the descriptor file and all the disk descriptors"""
        files = []
        out = open(os.path.join(self.base, self.name + ".vmx"), "w")
        out.write(self.to_vmx())
        out.close()
        files.append(self.name + ".vmx")

        for d in self.disks:
            f = d.make_extent(self.base)
            files.append(f)
            out = open(os.path.join(base, d.descriptor), "w")
            out.write(d._VMDK_TEMPLATE())
            out.close()
            files.append(d.descriptor)
        return files

    def to_vmx(self):
        """Return the VMX description of this image"""
        # Strip blank spaces and EOL to prevent syntax errors in vmx file
        self.descr = self.descr.strip()
        self.descr = self.descr.replace("\n","|")

        dict = {
            "now": time.strftime("%Y-%m-%dT%H:%M:%S %Z", time.localtime()),
            "progname": os.path.basename(sys.argv[0]),
            "/image/name": self.name,
            "/image/description": self.descr or "None",
            "/image/label": self.label or self.name,
            "/image/devices/vcpu" : self.vcpu,
            "/image/devices/memory": long(self.memory)/1024
        }

        vmx = _VMX_MAIN_TEMPLATE % dict
        if self.interface:
            vmx += _VMX_ETHER_TEMPLATE

        for d in self.disks:
            vmx += d.to_vmx()

        return vmx
            
def sub_ext(filename, ext):
    return os.path.splitext(filename)[0] + ext

_VMX_MAIN_TEMPLATE = """
#!/usr/bin/vmplayer

# Generated %(now)s by %(progname)s
# http://virt-manager.et.redhat.com/

# This is a Workstation 5 or 5.5 config file
# It can be used with Player
config.version = "8"
virtualHW.version = "4"

# Selected operating system for your virtual machine
guestOS = "other"

# displayName is your own name for the virtual machine
displayName = "%(/image/name)s"

# These fields are free text description fields
annotation = "%(/image/description)s"
guestinfo.vmware.product.long = "%(/image/label)s"
guestinfo.vmware.product.url = "http://virt-manager.et.redhat.com/"
guestinfo.vmware.product.class = "virtual machine"

# Number of virtual CPUs. Your virtual machine will not
# work if this number is higher than the number of your physical CPUs
numvcpus = "%(/image/devices/vcpu)s"

# Memory size and other memory settings
memsize = "%(/image/devices/memory)d"
MemAllowAutoScaleDown = "FALSE"
MemTrimRate = "-1"

# Unique ID for the virtual machine will be created
uuid.action = "create"

## For appliances where tools are installed already, this should really
## be false, but we don't have that ionfo in the metadata
# Remind to install VMware Tools
# This setting has no effect in VMware Player
tools.remindInstall = "TRUE"

# Startup hints interfers with automatic startup of a virtual machine
# This setting has no effect in VMware Player
hints.hideAll = "TRUE"

# Enable time synchronization between computer
# and virtual machine
tools.syncTime = "TRUE"

# First serial port, physical COM1 is not available
serial0.present = "FALSE"

# Optional second serial port, physical COM2 is not available
serial1.present = "FALSE"

# First parallell port, physical LPT1 is not available
parallel0.present = "FALSE"

# Logging
# This config activates logging, and keeps last log
logging = "TRUE"
log.fileName = "%(/image/name)s.log"
log.append = "TRUE"
log.keepOld = "3"

# These settings decides interaction between your
# computer and the virtual machine
isolation.tools.hgfs.disable = "FALSE"
isolation.tools.dnd.disable = "FALSE"
isolation.tools.copy.enable = "TRUE"
isolation.tools.paste.enabled = "TRUE"

# Settings for physical floppy drive
floppy0.present = "FALSE"
"""

_VMX_ETHER_TEMPLATE = """
## if /image/devices/interface is present:
# First network interface card
ethernet0.present = "TRUE"
ethernet0.connectionType = "nat"
ethernet0.addressType = "generated"
ethernet0.generatedAddressOffset = "0"
ethernet0.autoDetect = "TRUE"
"""

_VMX_ISO_TEMPLATE = """
# CDROM drive
ide%(dev)s.present = "TRUE"
ide%(dev)s.deviceType = "cdrom-raw"
ide%(dev)s.startConnected = "TRUE"
ide%(dev)s.fileName = "%(disk_filename)s"
ide%(dev)s.autodetect = "TRUE"
"""

_VMX_IDE_TEMPLATE = """
# IDE disk
ide%(dev)s.present = "TRUE"
ide%(dev)s.fileName = "%(disk_filename)s"
ide%(dev)s.mode = "persistent"
ide%(dev)s.startConnected = "TRUE"
ide%(dev)s.writeThrough = "TRUE"
"""
