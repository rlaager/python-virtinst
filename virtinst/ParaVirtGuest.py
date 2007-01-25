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

import os, sys, time
import subprocess
import urlgrabber.grabber as grabber
import urlgrabber.progress as progress
import tempfile

import libvirt

import logging

import Guest

def _copy_temp(fileobj, prefix, scratchdir):
    (fd, fn) = tempfile.mkstemp(prefix="virtinst-" + prefix, dir=scratchdir)
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

class ParaVirtGuest(Guest.Guest):
    def __init__(self, type=None, hypervisorURI=None):
        Guest.Guest.__init__(self, type=type, hypervisorURI=hypervisorURI)
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

        scratchdir = "/var/tmp"
        if self.type == "xen":
            # Xen needs kernel/initrd here to comply with
            # selinux policy
            scratchdir = "/var/lib/xen/"

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
                    kernel = grabber.urlopen(self.location + "/images/" + self.type + "/vmlinuz",
                                             progress_obj = progresscb, \
                                             text = "Retrieving vmlinuz...")
                except IOError, e:
                    raise RuntimeError, "Invalid URL location given: " + str(e)
                kfn = _copy_temp(kernel, prefix="vmlinuz.", scratchdir=scratchdir)
                logging.debug("Copied kernel to " + kfn)
            finally:
                if kernel:
                    kernel.close()
            try:
                try:
                    initrd = grabber.urlopen(self.location + "/images/" + self.type + "/initrd.img",
                                             progress_obj=progresscb, \
                                             text = "Retrieving initrd.img...")
                except IOError, e:
                    raise RuntimeError, "Invalid URL location given: " + str(e)
                ifn = _copy_temp(initrd, prefix="initrd.img.", scratchdir=scratchdir)
                logging.debug("Copied initrd to " + kfn)
            finally:
                if initrd:
                    initrd.close()

        elif self.location.startswith("nfs:"):
            nfsmntdir = tempfile.mkdtemp(prefix="nfs.", dir=scratchdir)
            cmd = ["mount", "-o", "ro", self.location[4:], nfsmntdir]
            ret = subprocess.call(cmd)
            if ret != 0:
                cleanup_nfs(nfsmntdir)
                raise RuntimeError, "Unable to mount NFS location!"
            kernel = None
            initrd = None
            try:
                try:
                    kernel = open(nfsmntdir + "/images/" + self.type + "/vmlinuz", "r")
                except IOError, e:
                    raise RuntimeError, "Invalid NFS location given: " + str(e)
                kfn = _copy_temp(kernel, prefix="vmlinuz.", scratchdir=scratchdir)
                try:
                    initrd = open(nfsmntdir + "/images/" + self.type + "/initrd.img", "r")
                except IOError, e:
                    raise RuntimeError, "Invalid NFS location given: " + str(e)
                ifn = _copy_temp(initrd, prefix="initrd.img.", scratchdir=scratchdir)
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

    def start_install(self, consolecb = None, meter = None):
        self.validate_parms()
        if meter:
            progresscb = meter
        else:
            progresscb = progress.BaseMeter()

        (self.kernel, self.initrd) = self._get_paravirt_install_images(progresscb)

        try:
            return Guest.Guest.start_install(self, consolecb, progresscb)
        finally:
            os.unlink(self.kernel)
            os.unlink(self.initrd)
