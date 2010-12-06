#
# Base class for all VM devices
#
# Copyright 2008  Red Hat, Inc.
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

import XMLBuilderDomain
from virtinst import _virtinst as _

class VirtualDevice(XMLBuilderDomain.XMLBuilderDomain):
    """
    Base class for all domain xml device objects.
    """

    VIRTUAL_DEV_DISK            = "disk"
    VIRTUAL_DEV_NET             = "interface"
    VIRTUAL_DEV_INPUT           = "input"
    VIRTUAL_DEV_GRAPHICS        = "graphics"
    VIRTUAL_DEV_AUDIO           = "sound"
    VIRTUAL_DEV_HOSTDEV         = "hostdev"
    VIRTUAL_DEV_SERIAL          = "serial"
    VIRTUAL_DEV_PARALLEL        = "parallel"
    VIRTUAL_DEV_CHANNEL         = "channel"
    VIRTUAL_DEV_CONSOLE         = "console"
    VIRTUAL_DEV_VIDEO           = "video"
    VIRTUAL_DEV_CONTROLLER      = "controller"
    VIRTUAL_DEV_WATCHDOG        = "watchdog"

    # Ordering in this list is important: it will be the order the
    # Guest class outputs XML. So changing this may upset the test suite
    virtual_device_types = [VIRTUAL_DEV_DISK,
                            VIRTUAL_DEV_CONTROLLER,
                            VIRTUAL_DEV_NET,
                            VIRTUAL_DEV_INPUT,
                            VIRTUAL_DEV_GRAPHICS,
                            VIRTUAL_DEV_SERIAL,
                            VIRTUAL_DEV_PARALLEL,
                            VIRTUAL_DEV_CONSOLE,
                            VIRTUAL_DEV_CHANNEL,
                            VIRTUAL_DEV_AUDIO,
                            VIRTUAL_DEV_VIDEO,
                            VIRTUAL_DEV_HOSTDEV,
                            VIRTUAL_DEV_WATCHDOG ]

    # General device type (disk, interface, etc.)
    _virtual_device_type = None

    def __init__(self, conn=None, parsexml=None, parsexmlnode=None):
        """
        Initialize device state

        @param conn: libvirt connection to validate device against
        @type conn: virConnect
        """
        XMLBuilderDomain.XMLBuilderDomain.__init__(self, conn, parsexml,
                                                   parsexmlnode)

        if not self._virtual_device_type:
            raise ValueError(_("Virtual device type must be set in subclass."))

        if self._virtual_device_type not in self.virtual_device_types:
            raise ValueError(_("Unknown virtual device type '%s'.") %
                             self._virtual_device_type)


    def get_virtual_device_type(self):
        return self._virtual_device_type
    virtual_device_type = property(get_virtual_device_type)

    def _get_xml_config(self):
        # See XMLBuilderDomain for docs
        raise NotImplementedError()

    def setup_dev(self, conn=None, meter=None):
        """
        Perform potentially hazardous device initialization, like
        storage creation or host device reset

        @param conn: Optional connection to use if neccessary. If not
                     specified, device's 'conn' will be used
        @param meter: Optional progress meter to use
        """
        # Will be overwritten by subclasses if necessary.
        ignore = conn
        ignore = meter
        return
