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

import virtconv.formats as formats
import virtconv.vmcfg as vmcfg
import virtconv.diskcfg as diskcfg
import virtconv.netdevcfg as netdevcfg

import re
import os

def parse_netdev_entry(vm, fullkey, value):
    """
    Parse a particular key/value for a network.  Throws ValueError.
    """

    ignore, ignore, inst, key = re.split("^(ethernet)([0-9]+).", fullkey)

    lvalue = value.lower()

    if key == "present" and lvalue == "false":
        return

    if not vm.netdevs.get(inst):
        vm.netdevs[inst] = netdevcfg.netdev(type = netdevcfg.NETDEV_TYPE_UNKNOWN)

    # "vlance", "vmxnet", "e1000"
    if key == "virtualDev":
        vm.netdevs[inst].driver = lvalue
    if key == "addressType" and lvalue == "generated":
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
        inst = int(inst) + int(bus_nr) * 2

    devid = (bus, inst)
    if not vm.disks.get(devid):
        vm.disks[devid] = diskcfg.disk(bus = bus,
            type = diskcfg.DISK_TYPE_DISK)

    if key == "deviceType":
        if lvalue == "atapi-cdrom" or lvalue == "cdrom-raw":
            vm.disks[devid].type = diskcfg.DISK_TYPE_CDROM
        elif lvalue == "cdrom-image":
            vm.disks[devid].type = diskcfg.DISK_TYPE_ISO

    if key == "fileName":
        vm.disks[devid].path = value
        vm.disks[devid].format = diskcfg.DISK_FORMAT_RAW
        if lvalue.endswith(".vmdk"):
            vm.disks[devid].format = diskcfg.DISK_FORMAT_VMDK

import re

class vmx_parser(formats.parser):
    """
    Support for VMWare .vmx files.  Note that documentation is
    particularly sparse on this format, with pretty much the best
    resource being http://sanbarrow.com/vmx.html
    """

    name = "vmx"
    suffix = ".vmx"
    can_import = True
    can_export = False
    can_identify = True

    @staticmethod
    def identify_file(input_file):
        """
        Return True if the given file is of this format.
        """
        infile = open(input_file, "r")
        line = infile.readline()
        infile.close()

        # some .vmx files don't bother with the header
        if re.match(r'^config.version\s+=', line):
            return True
        return re.match(r'^#!\s*/usr/bin/vm(ware|player)', line) is not None

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
                key = before_eq.strip()
                value = after_eq.strip().strip('"')
                config[key] = value

                if key.startswith("scsi") or key.startswith("ide"):
                    parse_disk_entry(vm, key, value)
                if key.startswith("ethernet"):
                    parse_netdev_entry(vm, key, value)
            except:
                raise Exception("Syntax error at line %d: %s" %
                    (line_nr + 1, line.strip()))

        for devid, disk in vm.disks.iteritems():
            if disk.type == diskcfg.DISK_TYPE_DISK:
                continue
                
            # vmx files often have dross left in path for CD entries
            if (disk.path == "auto detect" or
                not os.path.exists(disk.path)):
                vm.disks[devid].path = None

        if not config.get("displayName"):
            raise ValueError("No displayName defined in \"%s\"" % input_file)
        vm.name = config.get("displayName")

        vm.memory = config.get("memsize")
        vm.description = config.get("annotation")
        vm.nr_vcpus = config.get("numvcpus")
     
        vm.validate()
        return vm

    @staticmethod
    def export_file(vm, output_file):
        """
        Export a configuration file.
        @vm vm configuration instance
        @file Output file

        Raises ValueError if configuration is not suitable, or another
        exception on failure to write the output file.
        """

        raise NotImplementedError

formats.register_parser(vmx_parser)
