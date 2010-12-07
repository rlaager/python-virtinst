#
# Paravirtualized guest support
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

import DistroInstaller
from Guest import Guest

class ParaVirtGuest(Guest):
    def __init__(self, type=None, connection=None, hypervisorURI=None,
                 installer=None):
        if not installer:
            installer = DistroInstaller.DistroInstaller(type=type,
                                                        os_type="xen",
                                                        conn=connection)
        Guest.__init__(self, type, connection, hypervisorURI, installer)

