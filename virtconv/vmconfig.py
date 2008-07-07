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

import os

_parsers = [ ]

VM_TYPE_PV = 0
VM_TYPE_HVM = 1

DISK_TYPE_RAW = 0
DISK_TYPE_VMDK = 1

disk_suffixes = {
    DISK_TYPE_RAW: ".img",
    DISK_TYPE_VMDK: ".vmdk",
}

qemu_formats = {
    DISK_TYPE_RAW: "raw",
    DISK_TYPE_VMDK: "vmdk",
}

class disk(object):
    """Definition of an individual disk instance."""

    def __init__(self, path = None, number = None, type = None):
        self.path = path
        self.number = number
        self.type = type

    def convert(self, input_dir, output_dir, output_type):
        """
        Convert a disk into the requested format if possible, in the
        given output directory.  Raises NotImplementedError or other
        failures.
        """

        if self.type == output_type:
            return

        if output_type != DISK_TYPE_RAW:
            raise NotImplementedError("Cannot convert to disk type %d" %
                output_type)

        infile = self.path

        if not os.path.isabs(infile):
            infile = os.path.join(input_dir, infile)

        outfile = self.path

        if os.path.isabs(outfile):
            outfile = os.path.basename(outfile)

        outfile = outfile.replace(disk_suffixes[self.type],
            disk_suffixes[output_type]).strip()

        convert_cmd = ("qemu-img convert \"%s\" -O %s \"%s\"" %
            (infile, qemu_formats[output_type],
            os.path.join(output_dir, outfile)))

        os.system(convert_cmd)

        # Note: this is the *relative* path still
        self.path = outfile
        self.type = output_type


class vm(object):
    """
    Generic configuration for a particular VM instance.

    At export, a plugin is guaranteed to have the at least the following
    values set (any others needed should be checked for, raising
    ValueError on failure):

    vm.name
    vm.description (defaults to empty string)
    vm.nr_vcpus (defaults to 1)
    vm.type
    vm.arch

    If vm.memory is set, it is in Mb units.
    """

    name = None
    suffix = None

    def __init__(self):
        self.name = None
        self.description = None
        self.memory = None
        self.nr_vcpus = None
        self.disks = [ ]
        self.type = VM_TYPE_HVM
        self.arch = "i686" # FIXME?

    def validate(self):
        """
        Validate all parameters, and fix up any unset values to meet the
        guarantees we make above.
        """

        if not self.name:
            raise ValueError("VM name is not set")
        if not self.description:
            self.description = ""
        if not self.nr_vcpus:
            self.nr_vcpus = 1
        if not self.type:
            raise ValueError("VM type is not set")
        if not self.arch:
            raise ValueError("VM arch is not set")

        
class parser(object):
    """
    Base class for particular config file format definitions of
    a VM instance.

    Warning: this interface is not (yet) considered stable and may
    change at will.
    """

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
        @output_file Output file

        Raises ValueError if configuration is not suitable, or another
        exception on failure to write the output file.
        """
        raise NotImplementedError
            

def register_parser(parser):
    """
    Register a particular config format parser.  This should be called by each
    config plugin on import.
    """

    global _parsers
    _parsers += [ parser ]

def find_parser_by_name(name):
    """
    Return the parser of the given name
    """
    return [p for p in _parsers if p.name == name][0] or None

def find_parser_by_file(input_file):
    """
    Return the parser that is capable of comprehending the given file.
    """
    for p in _parsers:
        if p.identify_file(input_file):
            return p
    return None
