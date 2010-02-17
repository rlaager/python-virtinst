#
# Fullly virtualized guest support
#
# Copyright 2006-2007  Red Hat, Inc.
# Jeremy Katz <katzj@redhat.com>
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
import DistroInstaller

from Guest import Guest
from VirtualDevice import VirtualDevice
from VirtualDisk import VirtualDisk
from VirtualInputDevice import VirtualInputDevice
from VirtualCharDevice import VirtualCharDevice

class FullVirtGuest(Guest):

    def __init__(self, type=None, arch=None, connection=None,
                 hypervisorURI=None, emulator=None, installer=None):
        if not installer:
            installer = DistroInstaller.DistroInstaller(type = type,
                                                        os_type = "hvm",
                                                        conn=connection)
        Guest.__init__(self, type, connection, hypervisorURI, installer)

        self.disknode = "hd"
        self._diskbus = "ide"

        self.features = { "acpi": None, "pae":
            _util.is_pae_capable(self.conn), "apic": None }

        self.emulator = emulator
        if arch:
            self.arch = arch

        self.loader = None
        guest = self._caps.guestForOSType(type=self.installer.os_type,
                                          arch=self.arch)
        if (not self.emulator) and guest:
            for dom in guest.domains:
                if dom.hypervisor_type == self.installer.type:
                    self.emulator = dom.emulator
                    self.loader = dom.loader

        # Fall back to default hardcoding
        if self.emulator is None:
            if self.type == "xen":
                if self._caps.host.arch in ("x86_64"):
                    self.emulator = "/usr/lib64/xen/bin/qemu-dm"
                else:
                    self.emulator = "/usr/lib/xen/bin/qemu-dm"

        if (not self.loader) and self.type == "xen":
            self.loader = "/usr/lib/xen/boot/hvmloader"

        # Add a default console device
        dev = VirtualCharDevice.get_dev_instance(self.conn,
                                                 VirtualCharDevice.DEV_CONSOLE,
                                                 VirtualCharDevice.CHAR_PTY)
        self.add_device(dev)
        self._default_console_assigned = True

        self._set_default_input_dev()


    def _get_input_device(self):
        inputtype = VirtualDevice.VIRTUAL_DEV_INPUT

        typ = self._lookup_device_param(inputtype, "type")
        bus = self._lookup_device_param(inputtype, "bus")
        dev = VirtualInputDevice(self.conn)
        dev.type = typ
        dev.bus = bus
        return dev

    def _get_device_xml(self, install=True):
        emu_xml = ""
        if self.emulator is not None:
            emu_xml = "    <emulator>%s</emulator>\n" % self.emulator

        return (emu_xml + Guest._get_device_xml(self, install))

    def _set_defaults(self, devlist_func):
        disktype = VirtualDevice.VIRTUAL_DEV_DISK
        nettype = VirtualDevice.VIRTUAL_DEV_NET
        disk_bus  = self._lookup_device_param(disktype, "bus")
        net_model = self._lookup_device_param(nettype, "model")

        # Only overwrite params if they weren't already specified
        for net in devlist_func(nettype):
            if net_model and not net.model:
                net.model = net_model

        for disk in devlist_func(disktype):
            if (disk_bus and not disk.bus and
                disk.device == VirtualDisk.DEVICE_DISK):
                disk.bus = disk_bus

        if self.clock.offset == None:
            self.clock.offset = self._lookup_osdict_key("clock")

        # Run this last, so we get first crack at disk attributes
        Guest._set_defaults(self, devlist_func)
