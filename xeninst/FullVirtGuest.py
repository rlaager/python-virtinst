#!/usr/bin/python -tt
#
# Fullly virtualized guest support
#
# Copyright 2006  Red Hat, Inc.
# Jeremy Katz <katzj@redhat.com>
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import os

import XenGuest

class FullVirtGuest(XenGuest.XenGuest):
    def __init__(self):
        XenGuest.XenGuest.__init__(self)

    def get_cdrom(self):
        return self._cdrom
    def set_cdrom(self, val):
        val = os.path.abspath(val)
        if not os.path.exists(val):
            raise ValueError, "CD device must exist!"
        self._cdrom = val
    cdrom = property(get_cdrom, set_cdrom)

    
    # install location for the PV guest
    # this is a string pointing to an NFS, HTTP or FTP install source 
    def get_install_location(self):
        return self._location
    def set_install_location(self, val):
        if not (val.startswith("http://") or val.startswith("ftp://") or
                val.startswith("nfs:")):
            raise ValueError, "Install location must be an NFS, HTTP or FTP install source"
        self._location = val
    location = property(get_install_location, set_install_location)


    # extra arguments to pass to the guest installer
    def get_extra_args(self):
        return self._extraargs
    def set_extra_args(self, val):
        self._extraargs = val
    extraargs = property(get_extra_args, set_extra_args)


    def start_install(self):
        pass
