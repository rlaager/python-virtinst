#
# Copyright 2009 Red Hat, Inc.
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

import Installer
from VirtualDisk import VirtualDisk

class ImportInstaller(Installer.Installer):
    """
    Create a Guest around an existing disk device, and perform no 'install'
    stage.

    ImportInstaller sets the Guest's boot device to that of the first disk
    attached to the Guest (so, one of 'hd', 'cdrom', or 'floppy'). All the
    user has to do is fill in the Guest object with the desired parameters.
    """

    # General Installer methods

    def prepare(self, guest, meter):
        if len(guest.disks) == 0:
            raise ValueError(_("A disk device must be specified."))

    def get_install_xml(self, guest, isinstall):
        if isinstall:
            # Signifies to the 'Guest' that there is no 'install' phase
            return None
        else:
            bootdev = self._disk_to_bootdev(guest.disks[0])

        return self._get_osblob_helper(isinstall=isinstall, guest=guest,
                                       kernel=None, bootdev=bootdev)

    def post_install_check(self, guest):
        return True


    # Private methods

    def _disk_to_bootdev(self, disk):
        if disk.device == VirtualDisk.DEVICE_DISK:
            return "hd"
        elif disk.device == VirtualDisk.DEVICE_CDROM:
            return "cdrom"
        elif disk.device == VirtualDisk.DEVICE_FLOPPY:
            return "floppy"
        else:
            return "hd"
