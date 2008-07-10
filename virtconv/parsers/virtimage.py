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

from xml.sax.saxutils import escape
from string import ascii_letters
import virtconv.formats as formats
import virtconv.vmcfg as vmcfg
import virtconv.diskcfg as diskcfg

import re

pv_boot_template = """
  <boot type="xen">
   <guest>
    <arch>%(arch)s</arch>
    <features>
     <pae/>
    </features>
   </guest>
   <os>
    <loader>pygrub</loader>
   </os>
   %(pv_disks)s
  </boot>
"""

hvm_boot_template = """
  <boot type="hvm">
   <guest>
    <arch>%(arch)s</arch>
   </guest>
   <os>
    <loader dev="hd"/>
   </os>
   %(hvm_disks)s
  </boot>
"""

image_template = """
<image>
 <name>%(name)s</name>
 <label>%(name)s</label>
 <description>
  %(description)s
 </description>
 <domain>
  %(boot_template)s
  <devices>
   <vcpu>%(nr_vcpus)s</vcpu>
   <memory>%(memory)s</memory>
   <interface/>
   <graphics/>
  </devices>
 </domain>
 <storage>
  %(storage)s
 </storage>
</image>
"""

class virtimage_parser(formats.parser):
    """
    Support for virt-install's image format (see virt-image man page).
    """
    name = "virt-image"
    suffix = ".virt-image.xml"

    @staticmethod
    def identify_file(input_file):
        """
        Return True if the given file is of this format.
        """
        raise NotImplementedError

    @staticmethod
    def import_file(input_file):
        """
        Import a configuration file.  Raises if the file couldn't be
        opened, or parsing otherwise failed.
        """
        raise NotImplementedError

    @staticmethod
    def export_file(vm, output_file):
        """
        Export a configuration file.
        @vm vm configuration instance
        @file Output file

        Raises ValueError if configuration is not suitable, or another
        exception on failure to write the output file.
        """

        if not vm.memory:
            raise ValueError("VM must have a memory setting")

        # xend wants the name to match r'^[A-Za-z0-9_\-\.\:\/\+]+$'
        vmname = re.sub(r'[^A-Za-z0-9_.:/+-]+',  '_', vm.name)

        pv_disks = []
        hvm_disks = []
        storage_disks = []

        # create disk filename lists for xml template
        for disk in vm.disks:
            number = disk.number
            path = disk.path

            # FIXME: needs updating for later Xen enhancements; need to
            # implement capabilities checking for max disks etc.
            pv_disks.append("""<drive disk="%s" target="xvd%s" />\n""" %
                (path, ascii_letters[number % 26]))
            hvm_disks.append("""<drive disk="%s" target="hd%s" />\n""" %
                (path, ascii_letters[number % 26]))
            storage_disks.append(
                """<disk file="%s" use="system" format="%s"/>\n"""
                    % (path, diskcfg.qemu_formats[disk.format]))

        if vm.type == vmcfg.VM_TYPE_PV:
            boot_template = pv_boot_template
        else:
            boot_template = hvm_boot_template

        boot_xml = boot_template % {
            "pv_disks" : "".join(pv_disks),
            "hvm_disks" : "".join(hvm_disks),
            "arch" : vm.arch,
        }

        out = image_template % {
            "boot_template": boot_xml,
            "name" : vmname,
            "description" : escape(vm.description),
            "nr_vcpus" : vm.nr_vcpus,
            # Mb to Kb
            "memory" : int(vm.memory) * 1024,
            "storage" : "".join(storage_disks),
        }

        outfile = open(output_file, "w")
        outfile.writelines(out)
        outfile.close()

formats.register_parser(virtimage_parser)
