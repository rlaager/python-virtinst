#!/usr/bin/python -tt
#
# Paravirtualized guest support
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

import os, sys, time
import subprocess
import urlgrabber.grabber as grabber
import urlgrabber.progress as progress
import tempfile

import libvirt

import XenGuest

def _copy_temp(fileobj, prefix):
    (fd, fn) = tempfile.mkstemp(prefix=prefix, dir="/var/lib/xen")
    block_size = 16384
    try:
        while 1:
            buff = fileobj.read(block_size)
            if not buff:
                break
            os.write(fd, buff)
    finally:
        os.close(fd)
    return fn

class ParaVirtGuest(XenGuest.XenGuest):
    def __init__(self, hypervisorURI=None):
        XenGuest.XenGuest.__init__(self, hypervisorURI=hypervisorURI)
        self._location = None
        self._boot = None
        self._extraargs = ""
        self.disknode = "xvd"

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

    # kernel + initrd pair to use for installing as opposed to using a location
    def get_boot(self):
        return self._boot
    def set_boot(self, val):
        if type(val) == tuple:
            if len(val) != 2:
                raise ValueError, "Must pass both a kernel and initrd"
            (k, i) = val
        elif type(val) == dict:
            if not val.has_key("kernel") or not val.has_key("initrd"):
                raise ValueError, "Must pass both a kernel and initrd"
            k, i = val["kernel"], val["initrd"]
        self._boot = {"kernel": k, "initrd": i}
    boot = property(get_boot, set_boot)

    # extra arguments to pass to the guest installer
    def get_extra_args(self):
        return self._extraargs
    def set_extra_args(self, val):
        self._extraargs = val
    extraargs = property(get_extra_args, set_extra_args)

    def _get_paravirt_install_images(self, progresscb):
        def cleanup_nfs(nfsmntdir):
            cmd = ["umount", nfsmntdir]
            ret = subprocess.call(cmd)
            try:
                os.rmdir(nfsmntdir)
            except:
                pass
            
        if self.boot is not None:
            return (self.boot["kernel"], self.boot["initrd"])
        kfn = None
        ifn = None
        if self.location.startswith("http://") or \
               self.location.startswith("ftp://"):
            kernel = None
            initrd = None
            try:
                try:
                    kernel = grabber.urlopen("%s/images/xen/vmlinuz" %(self.location,), \
                                             progress_obj = progresscb, \
                                             text = "Retrieving vmlinuz...")
                except IOError, e:
                    raise RuntimeError, "Invalid URL location given: " + str(e)
                kfn = _copy_temp(kernel, prefix="vmlinuz.")
            finally:
                if kernel:
                    kernel.close()
            try:
                try:
                    initrd = grabber.urlopen("%s/images/xen/initrd.img" %(self.location,), \
                                             progress_obj=progresscb, \
                                             text = "Retrieving initrd.img...")
                except IOError, e:
                    raise RuntimeError, "Invalid URL location given: " + str(e)
                ifn = _copy_temp(initrd, prefix="initrd.img.")
            finally:
                if initrd:
                    initrd.close()

        elif self.location.startswith("nfs:"):
            nfsmntdir = tempfile.mkdtemp(prefix="xennfs.", dir="/var/lib/xen")
            cmd = ["mount", "-o", "ro", self.location[4:], nfsmntdir]
            ret = subprocess.call(cmd)
            if ret != 0:
                cleanup_nfs(nfsmntdir)
                raise RuntimeError, "Unable to mount NFS location!"
            kernel = None
            initrd = None
            try:
                try:
                    kernel = open("%s/images/xen/vmlinuz" %(nfsmntdir,), "r")
                except IOError, e:
                    raise RuntimeError, "Invalid NFS location given: " + str(e)
                kfn = _copy_temp(kernel, prefix="vmlinuz.")
                try:
                    initrd = open("%s/images/xen/initrd.img" %(nfsmntdir,), "r")
                except IOError, e:
                    raise RuntimeError, "Invalid NFS location given: " + str(e)
                ifn = _copy_temp(initrd, prefix="initrd.img.")
            finally:
                if kernel:
                    kernel.close()
                if initrd:
                    initrd.close()
                cleanup_nfs(nfsmntdir)            

        return (kfn, ifn)

    def _get_install_xml(self):
        if self.location:
            metharg="method=%s " %(self.location,)
        else:
            metharg = ""
            
        return """
  <os>
    <type>linux</type>
    <kernel>%(kernel)s</kernel>
    <initrd>%(initrd)s</initrd>
    <cmdline> %(metharg)s %(extra)s</cmdline>
  </os>
"""  % { "kernel": self.kernel, "initrd": self.initrd, "metharg": metharg, "extra": self.extraargs }

    def _get_runtime_xml(self):
        return """
  <bootloader>/usr/bin/pygrub</bootloader>
"""

    def _get_graphics_xen(self):
        """Get the graphics config in the xend python format"""
        if self.graphics["enabled"] == False:
            return ""
        ret = "vfb = [\""
        gt = self.graphics["type"]
        if gt.name == "vnc":
            ret += "type=vnc"
            if gt.port and gt.port >= 5900:
                ret += ",vncdisplay=%d" %(gt.port - 5900,)
                ret += ",vncunused=0"
            elif gt.port and gt.port == -1:
                ret += ",vncunused=1"
        elif gt.name == "sdl":
            ret += "type=sdl"
        ret += "\"]"
        return ret

    def _get_config_xml(self, install = True):
        if install:
            osblob = self._get_install_xml()
            action = "destroy"
        else:
            osblob = self._get_runtime_xml()
            action = "restart"

        return """<domain type='xen'>
  <name>%(name)s</name>
  <memory>%(ramkb)s</memory>
  <uuid>%(uuid)s</uuid>
  %(osblob)s
  <on_poweroff>destroy</on_poweroff>
  <on_reboot>%(action)s</on_reboot>
  <on_crash>%(action)s</on_crash>
  <vcpu>%(vcpus)d</vcpu>
  <devices>
%(disks)s
    %(networks)s
    %(graphics)s
  </devices>
</domain>
""" % { "name": self.name, "vcpus": self.vcpus, "uuid": self.uuid, "ramkb": self.memory * 1024, "disks": self._get_disk_xml(), "networks": self._get_network_xml(), "graphics": self._get_graphics_xml(), "osblob": osblob, "action": action }

    def _get_config_xen(self):
        return """# Automatically generated xen config file
name = "%(name)s"
memory = "%(ram)s"
%(disks)s
%(networks)s
%(graphics)s
uuid = "%(uuid)s"
bootloader="/usr/bin/pygrub"
vcpus=%(vcpus)s
on_reboot   = 'restart'
on_crash    = 'restart'
""" % { "name": self.name, "ram": self.memory, "disks": self._get_disk_xen(), "networks": self._get_network_xen(), "uuid": self.uuid, "graphics": self._get_graphics_xen(), "vcpus" : self.vcpus }

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
        XenGuest.XenGuest.validate_parms(self)

    def start_install(self, consolecb = None, meter = None):
        self.validate_parms()
        if meter:
            progresscb = meter
        else:
            progresscb = progress.BaseMeter()
        
        (self.kernel, self.initrd) = self._get_paravirt_install_images(progresscb)

        try:
            return XenGuest.XenGuest.start_install(self, consolecb, progresscb)
        finally:
            os.unlink(self.kernel)
            os.unlink(self.initrd)
