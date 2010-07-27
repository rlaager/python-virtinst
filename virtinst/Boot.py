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

import _util

class Boot(object):
    """
    Class for generating boot device related XML
    """

    BOOT_DEVICE_HARDDISK = "hd"
    BOOT_DEVICE_CDROM = "cdrom"
    BOOT_DEVICE_FLOPPY = "fd"
    BOOT_DEVICE_NETWORK = "network"

    def __init__(self, conn):
        self.conn = conn

        self._bootorder = []
        self._enable_bootmenu = None
        self._kernel = None
        self._initrd = None
        self._kernel_args = None

    def _get_enable_bootmenu(self):
        return self._enable_bootmenu
    def _set_enable_bootmenu(self, val):
        self._enable_bootmenu = val
    enable_bootmenu = property(_get_enable_bootmenu, _set_enable_bootmenu)

    def _get_bootorder(self):
        return self._bootorder
    def _set_bootorder(self, val):
        self._bootorder = val
    bootorder = property(_get_bootorder, _set_bootorder)

    def _get_kernel(self):
        return self._kernel
    def _set_kernel(self, val):
        self._kernel = val
    kernel = property(_get_kernel, _set_kernel)

    def _get_initrd(self):
        return self._initrd
    def _set_initrd(self, val):
        self._initrd = val
    initrd = property(_get_initrd, _set_initrd)

    def _get_kernel_args(self):
        return self._kernel_args
    def _set_kernel_args(self, val):
        self._kernel_args = val
    kernel_args = property(_get_kernel_args, _set_kernel_args)

    def get_xml_config(self):
        xml = ""

        if self.kernel:
            xml = _util.xml_append(xml, "    <kernel>%s</kernel>" %
                                   _util.xml_escape(self.kernel))
            if self.initrd:
                xml = _util.xml_append(xml, "    <initrd>%s</initrd>" %
                                       _util.xml_escape(self.initrd))
            if self.kernel_args:
                xml = _util.xml_append(xml, "    <cmdline>%s</cmdline>" %
                                       _util.xml_escape(self.kernel_args))

        else:
            for dev in self.bootorder:
                xml = _util.xml_append(xml, "    <boot dev='%s'/>" % dev)

            if self.enable_bootmenu in [True, False]:
                val = self.enable_bootmenu and "yes" or "no"
                xml = _util.xml_append(xml,
                                       "    <bootmenu enable='%s'/>" % val)

        return xml
