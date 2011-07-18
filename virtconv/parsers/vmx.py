#
# Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
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

from virtconv import _gettext as _
import virtconv.formats as formats
import virtconv.vmcfg as vmcfg
import virtconv.diskcfg as diskcfg
import virtconv.netdevcfg as netdevcfg
import sys
import re
import os
import logging

_VMX_MAIN_TEMPLATE = """
#!/usr/bin/vmplayer

# Generated by %(progname)s
# http://virt-manager.org/

# This is a Workstation 5 or 5.5 config file and can be used with Player
config.version = "8"
virtualHW.version = "4"
guestOS = "other"
displayName = "%(vm_name)s"
annotation = "%(vm_description)s"
guestinfo.vmware.product.long = "%(vm_name)s"
guestinfo.vmware.product.url = "http://virt-manager.org/"
guestinfo.vmware.product.class = "virtual machine"
numvcpus = "%(vm_nr_vcpus)s"
memsize = "%(vm_memory)d"
MemAllowAutoScaleDown = "FALSE"
MemTrimRate = "-1"
uuid.action = "create"
tools.remindInstall = "TRUE"
hints.hideAll = "TRUE"
tools.syncTime = "TRUE"
serial0.present = "FALSE"
serial1.present = "FALSE"
parallel0.present = "FALSE"
logging = "TRUE"
log.fileName = "%(vm_name)s.log"
log.append = "TRUE"
log.keepOld = "3"
isolation.tools.hgfs.disable = "FALSE"
isolation.tools.dnd.disable = "FALSE"
isolation.tools.copy.enable = "TRUE"
isolation.tools.paste.enabled = "TRUE"
floppy0.present = "FALSE"
"""
_VMX_ETHERNET_TEMPLATE = """
ethernet%(dev)s.present = "TRUE"
ethernet%(dev)s.connectionType = "nat"
ethernet%(dev)s.addressType = "generated"
ethernet%(dev)s.generatedAddressOffset = "0"
ethernet%(dev)s.autoDetect = "TRUE"
"""
_VMX_IDE_TEMPLATE = """
# IDE disk
ide%(dev)s.present = "TRUE"
ide%(dev)s.fileName = "%(disk_filename)s"
ide%(dev)s.mode = "persistent"
ide%(dev)s.startConnected = "TRUE"
ide%(dev)s.writeThrough = "TRUE"
"""

def parse_netdev_entry(vm, fullkey, value):
    """
    Parse a particular key/value for a network.  Throws ValueError.
    """

    ignore, ignore, inst, key = re.split("^(ethernet)([0-9]+).", fullkey)

    lvalue = value.lower()

    if key == "present" and lvalue == "false":
        return

    if not vm.netdevs.get(inst):
        vm.netdevs[inst] = netdevcfg.netdev(type=netdevcfg.NETDEV_TYPE_UNKNOWN)

    # "vlance", "vmxnet", "e1000"
    if key == "virtualdev":
        vm.netdevs[inst].driver = lvalue
    if key == "addresstype" and lvalue == "generated":
        vm.netdevs[inst].mac = "auto"
    # we ignore .generatedAddress for auto mode
    if key == "address":
        vm.netdevs[inst].mac = lvalue

def parse_disk_entry(vm, fullkey, value):
    """
    Parse a particular key/value for a disk.  FIXME: this should be a
    lot smarter.
    """

    # skip bus values, e.g. 'scsi0.present = "TRUE"'
    if re.match(r"^(scsi|ide)[0-9]+[^:]", fullkey):
        return

    ignore, bus, bus_nr, inst, key = re.split(r"^(scsi|ide)([0-9]+):([0-9]+)\.",
        fullkey)

    lvalue = value.lower()

    if key == "present" and lvalue == "false":
        return

    # Does anyone else think it's scary that we're still doing things
    # like this?
    if bus == "ide":
        inst = int(bus_nr) * 2 + (int(inst) % 2)
    elif bus == "scsi":
        inst = int(bus_nr) * 16 + (int(inst) % 16)


    devid = (bus, inst)
    if not vm.disks.get(devid):
        vm.disks[devid] = diskcfg.disk(bus=bus,
            type=diskcfg.DISK_TYPE_DISK)

    if key == "devicetype":
        if lvalue == "atapi-cdrom" or lvalue == "cdrom-raw":
            vm.disks[devid].type = diskcfg.DISK_TYPE_CDROM
        elif lvalue == "cdrom-image":
            vm.disks[devid].type = diskcfg.DISK_TYPE_ISO

    if key == "filename":
        vm.disks[devid].path = value
        vm.disks[devid].format = diskcfg.DISK_FORMAT_RAW
        if lvalue.endswith(".vmdk"):
            vm.disks[devid].format = diskcfg.DISK_FORMAT_VMDK

class vmx_parser(formats.parser):
    """
    Support for VMWare .vmx files.  Note that documentation is
    particularly sparse on this format, with pretty much the best
    resource being http://sanbarrow.com/vmx.html
    """

    name = "vmx"
    suffix = ".vmx"
    can_import = True
    can_export = True
    can_identify = True

    @staticmethod
    def identify_file(input_file):
        """
        Return True if the given file is of this format.
        """
        infile = open(input_file, "r")
        content = infile.readlines()
        infile.close()

        for line in content:
            # some .vmx files don't bother with the header
            if re.match(r'^config.version\s+=', line) or \
               re.match(r'^#!\s*/usr/bin/vm(ware|player)', line):
                return True
        return False

    @staticmethod
    def import_file(input_file):
        """
        Import a configuration file.  Raises if the file couldn't be
        opened, or parsing otherwise failed.
        """

        vm = vmcfg.vm()

        infile = open(input_file, "r")
        contents = infile.readlines()
        infile.close()

        lines = []

        # strip out comment and blank lines for easy splitting of values
        for line in contents:
            if not line.strip() or line.startswith("#"):
                continue
            else:
                lines.append(line)

        config = {}

        # split out all remaining entries of key = value form
        for (line_nr, line) in enumerate(lines):
            try:
                before_eq, after_eq = line.split("=", 1)
                key = before_eq.strip().lower()
                value = after_eq.strip().strip('"')
                config[key] = value

                if key.startswith("scsi") or key.startswith("ide"):
                    parse_disk_entry(vm, key, value)
                if key.startswith("ethernet"):
                    parse_netdev_entry(vm, key, value)
            except:
                raise Exception(_("Syntax error at line %d: %s") %
                    (line_nr + 1, line.strip()))

        for devid, disk in vm.disks.iteritems():
            if disk.type == diskcfg.DISK_TYPE_DISK:
                continue

            # vmx files often have dross left in path for CD entries
            if (disk.path is None
                or disk.path.lower() == "auto detect" or
                not os.path.exists(disk.path)):
                vm.disks[devid].path = None

        if not config.get("displayname"):
            raise ValueError(_("No displayName defined in \"%s\"") %
                             input_file)
        vm.name = config.get("displayname")

        vm.memory = config.get("memsize")
        vm.description = config.get("annotation")
        vm.nr_vcpus = config.get("numvcpus")

        vm.validate()
        return vm

    @staticmethod
    def export(vm):
        """
        Export a configuration file as a string.
        @vm vm configuration instance

        Raises ValueError if configuration is not suitable.
        """

        vm.description = vm.description.strip()
        vm.description = vm.description.replace("\n", "|")
        vmx_out_template = []
        vmx_dict = {
            #"now": time.strftime("%Y-%m-%dT%H:%M:%S %Z", time.localtime()),
            "progname": os.path.basename(sys.argv[0]),
            "vm_name": vm.name,
            "vm_description": vm.description or "None",
            "vm_nr_vcpus" : vm.nr_vcpus,
            "vm_memory": long(vm.memory)
        }
        vmx_out = _VMX_MAIN_TEMPLATE % vmx_dict
        vmx_out_template.append(vmx_out)

        disk_out_template = []
        for devid, disk in sorted(vm.disks.items()):
            bus, dev_nr = devid
            if bus.lower() != "ide":
                logging.debug("Disk bus '%s' not yet supported. Skipping." % \
                               bus.lower())
                continue

            dev = "%d:%d" % (dev_nr / 2, dev_nr % 2)
            disk_dict = {
                "dev": dev,
                "disk_filename" : disk.path
            }
            disk_out = _VMX_IDE_TEMPLATE % disk_dict
            disk_out_template.append(disk_out)

        eth_out_template = []
        if len(vm.netdevs):
            for devnum in vm.netdevs:
                eth_dict = {
                   "dev" : devnum
                }
                eth_out = _VMX_ETHERNET_TEMPLATE % eth_dict
                eth_out_template.append(eth_out)

        return "".join(vmx_out_template + disk_out_template + eth_out_template)

formats.register_parser(vmx_parser)
