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


class ParaVirtGuest(Guest.XenGuest):
    def __init__(self, type=None, hypervisorURI=None):
        Guest.Guest.__init__(self, type=type, hypervisorURI=hypervisorURI)
        self._boot = None
        self._extraargs = ""
        self.disknode = "xvd"

    # kernel + initrd pair to use for installing as opposed to using a location
    def get_boot(self):
        return self._boot
    def set_boot(self, val):
        if type(val) == tuple:
            if len(val) != 2:
                raise ValueError, "Must pass both a kernel and initrd"
            (k, i) = val
            self._boot = {"kernel": k, "initrd": i}
        elif type(val) == dict:
            if not val.has_key("kernel") or not val.has_key("initrd"):
                raise ValueError, "Must pass both a kernel and initrd"
            self._boot = val
        elif type(val) == list:
            if len(val) != 2:
                raise ValueError, "Must pass both a kernel and initrd"
            self._boot = {"kernel": val[0], "initrd": val[1]}
    boot = property(get_boot, set_boot)

    # extra arguments to pass to the guest installer
    def get_extra_args(self):
        return self._extraargs
    def set_extra_args(self, val):
        self._extraargs = val
    extraargs = property(get_extra_args, set_extra_args)

    def _get_install_xml(self):
        if self.location:
            if self.location.startswith("/"):
                metharg="method=hd://"
            else:
                metharg="method=%s " %(self.location,)
        else:
            metharg = ""

        return """<os>
    <type>linux</type>
    <kernel>%(kernel)s</kernel>
    <initrd>%(initrd)s</initrd>
    <cmdline> %(metharg)s %(extra)s</cmdline>
  </os>""" % \
    { "kernel": self.kernel, \
      "initrd": self.initrd, \
      "metharg": metharg, \
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
            filenames = self._get_install_files(["images/" + self.type + "/vmlinuz", "images/" + self.type + "/initrd.img"], meter)
            self.kernel = filenames[0]
            self.initrd = filenames[1]
            tmpfiles.append(self.kernel)
            tmpfiles.append(self.initrd)

        # If they're installing off a local file/device, we map it
        # through to a virtual harddisk
        if self.location is not None and self.location.startswith("/"):
            self.disks.append(Guest.VirtualDisk(self.location, readOnly=True))

        return tmpfiles
