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

_parsers = [ ]

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
