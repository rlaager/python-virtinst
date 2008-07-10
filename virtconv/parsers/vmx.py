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
        disks = []

        # split out all remaining entries of key = value form
        for (line_nr, line) in enumerate(lines):
            try:
                before_eq, after_eq = line.split("=", 1)
                key = before_eq.replace(" ","")
                value = after_eq.replace('"',"")
                value = value.strip()
                config[key] = value
                # FIXME: this should probably be a lot smarter.
                if value.endswith(".vmdk"):
                    disks += [ value ]
            except:
                raise Exception("Syntax error at line %d: %s" %
                    (line_nr + 1, line.strip()))

        if not config.get("displayName"):
            raise ValueError("No displayName defined in \"%s\"" % input_file)
        vm.name = config.get("displayName")

        vm.memory = config.get("memsize")
        vm.description = config.get("annotation")
        vm.nr_vcpus = config.get("numvcpus")

        for (number, path) in enumerate(disks):
            vm.disks += [ diskcfg.disk(path, number, diskcfg.DISK_FORMAT_VMDK) ]

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
