#
# Copyright 2010  Red Hat, Inc.
# Cole Robinson <crobinso@redhat.com>
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

class Clock(object):
    """
    Class for generating <clock> XML
    """

    def __init__(self, conn):
        self.conn = conn

        self._offset = None

    def get_offset(self):
        return self._offset
    def set_offset(self, val):
        self._offset = val
    offset = property(get_offset, set_offset)

    def get_xml_config(self):
        if not self.offset:
            return ""

        return """  <clock offset="%s"/>""" % self.offset
