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

import VirtualDevice
#from virtinst import _virtinst as _
from XMLBuilderDomain import _xml_property

class VirtualController(VirtualDevice.VirtualDevice):

    _virtual_device_type = VirtualDevice.VirtualDevice.VIRTUAL_DEV_CONTROLLER

    CONTROLLER_TYPE_IDE             = "ide"
    CONTROLLER_TYPE_FDC             = "fdc"
    CONTROLLER_TYPE_SCSI            = "scsi"
    CONTROLLER_TYPE_SATA            = "sata"
    CONTROLLER_TYPE_VIRTIOSERIAL    = "virtio-serial"
    CONTROLLER_TYPES = [CONTROLLER_TYPE_IDE, CONTROLLER_TYPE_FDC,
                        CONTROLLER_TYPE_SCSI, CONTROLLER_TYPE_SATA,
                        CONTROLLER_TYPE_VIRTIOSERIAL ]

    @staticmethod
    def get_class_for_type(ctype):
        if ctype not in VirtualController.CONTROLLER_TYPES:
            raise ValueError("Unknown controller type '%s'" % ctype)

        if ctype == VirtualController.CONTROLLER_TYPE_IDE:
            return VirtualControllerIDE
        elif ctype == VirtualController.CONTROLLER_TYPE_FDC:
            return VirtualControllerFDC
        elif ctype == VirtualController.CONTROLLER_TYPE_SCSI:
            return VirtualControllerSCSI
        elif ctype == VirtualController.CONTROLLER_TYPE_SATA:
            return VirtualControllerSATA
        elif ctype == VirtualController.CONTROLLER_TYPE_VIRTIOSERIAL:
            return VirtualControllerVirtioSerial

    _controller_type = None

    def __init__(self, conn, parsexml=None, parsexmlnode=None):
        VirtualDevice.VirtualDevice.__init__(self, conn,
                                             parsexml, parsexmlnode)

        self._index = 0
        self._ports = None
        self._vectors = None

    def get_type(self):
        return self._controller_type
    type = _xml_property(get_type,
                         xpath="./@type")

    def get_index(self):
        return self._index
    def set_index(self, val):
        self._index = int(val)
    index = _xml_property(get_index, set_index,
                          xpath="./@index")

    def get_vectors(self):
        return self._vectors
    def set_vectors(self, val):
        self._vectors = val
    vectors = _xml_property(get_vectors, set_vectors,
                            xpath="./@vectors")

    def get_ports(self):
        return self._ports
    def set_ports(self, val):
        self._ports = val
    ports = _xml_property(get_ports, set_ports,
                          xpath="./@ports")

    def _extra_config(self):
        return ""

    def _get_xml_config(self):
        extra = self._extra_config()

        xml = "    <controller type='%s' index='%s'" % (self.type, self.index)
        xml += extra
        xml += "/>"

        return xml


class VirtualControllerIDE(VirtualController):
    _controller_type = VirtualController.CONTROLLER_TYPE_IDE

class VirtualControllerFDC(VirtualController):
    _controller_type = VirtualController.CONTROLLER_TYPE_FDC

class VirtualControllerSCSI(VirtualController):
    _controller_type = VirtualController.CONTROLLER_TYPE_SCSI

class VirtualControllerSATA(VirtualController):
    _controller_type = VirtualController.CONTROLLER_TYPE_SATA

class VirtualControllerVirtioSerial(VirtualController):
    _controller_type = VirtualController.CONTROLLER_TYPE_VIRTIOSERIAL

    def _extra_config(self):
        xml = ""
        if self.ports != None:
            xml += " ports='%s'" % self.ports
        if self.vectors != None:
            xml += " vectors='%s'" % self.vectors

        return xml
