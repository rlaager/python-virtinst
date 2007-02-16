#!/usr/bin/python -tt
#
# Paravirtualized guest support
#
# Copyright 2006-2007  Red Hat, Inc.
# Jeremy Katz <katzj@redhat.com>
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import os
import libvirt
import Guest
import DistroManager

class ParaVirtGuest(Guest.XenGuest):
    def __init__(self, type=None, connection=None, hypervisorURI=None):
        Guest.Guest.__init__(self, type=type, connection=connection, hypervisorURI=hypervisorURI)
        self.disknode = "xvd"

    def _get_install_xml(self):
        return """<os>
    <type>linux</type>
    <kernel>%(kernel)s</kernel>
    <initrd>%(initrd)s</initrd>
    <cmdline>%(extra)s</cmdline>
  </os>""" % \
    { "kernel": self.kernel, \
      "initrd": self.initrd, \
      "extra": self.extraargs }


    def _get_runtime_xml(self):
        return """<bootloader>/usr/bin/pygrub</bootloader>"""

    def _connectSerialConsole(self):
        # *sigh*  would be nice to have a python version of xmconsole
        # and probably not much work at all to throw together, but this will
        # do for now
        cmd = ["/usr/sbin/xm", "console", "%s" %(self.domain.ID(),)]
        child = os.fork()
        if (not child):
            os.execvp(cmd[0], cmd)
            os._exit(1)
        return child

    def validate_parms(self):
        if not self.location and not self.boot:
            raise RuntimeError, "A location must be specified to install from"
        Guest.Guest.validate_parms(self)

    def _prepare_install_location(self, meter):
        tmpfiles = []
        if self.boot is not None:
            # Got a local kernel/initrd already
            self.kernel = self.boot["kernel"]
            self.initrd = self.boot["initrd"]
        else:
            # Need to fetch the kernel & initrd from a remote site, or
            # out of a loopback mounted disk image/device
            (kernelfn,initrdfn,args) = DistroManager.acquireKernel(self.location, meter, scratchdir=self.scratchdir, type=self.type)
            self.kernel = kernelfn
            self.initrd = initrdfn
            if self.extraargs is not None:
                self.extraargs = self.extraargs + " " + args
            else:
                self.extraargs = args
            tmpfiles.append(kernelfn)
            tmpfiles.append(initrdfn)

        # If they're installing off a local file/device, we map it
        # through to a virtual harddisk
        if self.location is not None and self.location.startswith("/"):
            self.disks.append(Guest.VirtualDisk(self.location, readOnly=True, transient=True))

        return tmpfiles
