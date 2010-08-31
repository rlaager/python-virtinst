#
# Copyright 2009  Red Hat, Inc.
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

import VirtualDevice
from virtinst import _virtinst as _

class VirtualInputDevice(VirtualDevice.VirtualDevice):

    _virtual_device_type = VirtualDevice.VirtualDevice.VIRTUAL_DEV_INPUT

    INPUT_TYPE_MOUSE = "mouse"
    INPUT_TYPE_TABLET = "tablet"
    INPUT_TYPE_DEFAULT = "default"
    input_types = [INPUT_TYPE_MOUSE, INPUT_TYPE_TABLET, INPUT_TYPE_DEFAULT]

    INPUT_BUS_PS2 = "ps2"
    INPUT_BUS_USB = "usb"
    INPUT_BUS_XEN = "xen"
    INPUT_BUS_DEFAULT = "default"
    input_buses = [INPUT_BUS_PS2, INPUT_BUS_USB, INPUT_BUS_XEN,
                   INPUT_BUS_DEFAULT]

    def __init__(self, conn, parsexml=None, parsexmlnode=None):
        VirtualDevice.VirtualDevice.__init__(self, conn, parsexml,
                                             parsexmlnode)

        self._type = self.INPUT_TYPE_DEFAULT
        self._bus = self.INPUT_TYPE_DEFAULT

    def get_type(self):
        return self._type
    def set_type(self, val):
        if val not in self.input_types:
            raise ValueError(_("Unknown input type '%s'.") % val)
        self._type = val
    type = property(get_type, set_type)

    def get_bus(self):
        return self._bus
    def set_bus(self, val):
        if val not in self.input_buses:
            raise ValueError(_("Unknown input bus '%s'.") % val)
        self._bus = val
    bus = property(get_bus, set_bus)

    def _get_xml_config(self):
        typ = self.type
        bus = self.bus
        if typ == self.INPUT_TYPE_DEFAULT:
            typ = self.INPUT_TYPE_MOUSE
        if bus == self.INPUT_BUS_DEFAULT:
            bus = self.INPUT_BUS_XEN

        return "    <input type='%s' bus='%s'/>" % (typ, bus)
