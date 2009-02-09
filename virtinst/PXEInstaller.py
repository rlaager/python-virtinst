#
# Copyright 2006-2009  Red Hat, Inc.
# Daniel P. Berrange <berrange@redhat.com>
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

class PXEInstaller(Installer.Installer):

    def prepare(self, guest, meter, distro = None):
        pass

    def _get_osblob(self, install, hvm, arch = None, loader = None,
                    conn = None):
        if install:
            bootdev="network"
        else:
            bootdev = "hd"

        return self._get_osblob_helper(isinstall=install, ishvm=hvm,
                                       arch=arch, loader=loader, conn=conn,
                                       kernel=None, bootdev=bootdev)
