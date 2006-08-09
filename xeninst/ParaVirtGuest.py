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
import tempfile

import libvirt

import XenGuest

def _copy_temp(fileobj, prefix):
    (fd, fn) = tempfile.mkstemp(prefix=prefix, dir="/var/lib/xen")
    block_size = 16384
    while 1:
        buff = fileobj.read(block_size)
        if not buff:
            break
        os.write(fd, buff)
    os.close(fd)
    return fn

class ParaVirtGuest(XenGuest.XenGuest):
    def __init__(self):
        XenGuest.XenGuest.__init__(self)
        self._location = None
        self._boot = None
        self._extraargs = ""

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
    def set_boot(self, *args):
        if len(args) != 2:
            raise ValueError, "Must pass both a kernel and initrd"
        (k, i) = args
        self._boot = {"kernel": k, "initrd": i}
    boot = property(get_boot, set_boot)

    # extra arguments to pass to the guest installer
    def get_extra_args(self):
        return self._extraargs
    def set_extra_args(self, val):
        self._extraargs = val
    extraargs = property(get_extra_args, set_extra_args)

    def _get_paravirt_install_images(self):
        if self.boot is not None:
            return (self.boot["kernel"], self.boot["initrd"])
        if self.location.startswith("http://") or \
               self.location.startswith("ftp://"):
            try:
                kernel = grabber.urlopen("%s/images/xen/vmlinuz"
                                         %(self.location,))
                initrd = grabber.urlopen("%s/images/xen/initrd.img"
                                         %(self.location,))
            except IOError:
                raise RuntimeError, "Invalid URL location given!"
        elif self.location.startswith("nfs:"):
            nfsmntdir = tempfile.mkdtemp(prefix="xennfs.", dir="/var/lib/xen")
            cmd = ["mount", "-o", "ro", self.location[4:], nfsmntdir]
            ret = subprocess.call(cmd)
            if ret != 0:
                raise RuntimeError, "Unable to mount NFS location!"
            try:
                kernel = open("%s/images/xen/vmlinuz" %(nfsmntdir,), "r")
                initrd = open("%s/images/xen/initrd.img" %(nfsmntdir,), "r")
            except IOError:
                raise RuntimeError, "Invalid NFS location given!"

        kfn = _copy_temp(kernel, prefix="vmlinuz.")
        kernel.close()

        ifn = _copy_temp(initrd, prefix="initrd.img.")
        initrd.close()

        # and unmount
        if self.location.startswith("nfs"):
            cmd = ["umount", nfsmntdir]
            ret = subprocess.call(cmd)
            os.rmdir(nfsmntdir)

        return (kfn, ifn)

    def _get_disk_xml(self):
        ret = ""
        count = 0
        for d in self.disks:
            ret += "<disk type='%(disktype)s'><source file='%(disk)s'/><target dev='xvd%(dev)c'/></disk>" %{"disktype": d.type, "disk": d.path, "dev": ord('a') + count}
            count += 1
        return ret

    def _get_network_xml(self):
        ret = ""
        for n in self.nics:
            ret += "<interface type='bridge'><source bridge='%(bridge)s'/><mac address='%(mac)s'/><script path='/etc/xen/scripts/vif-bridge'/></interface>" % { "bridge": n.bridge, "mac": n.macaddr }
        return ret

    def _get_config_xml(self, kernel, initrd):
        if self.location:
            metharg="method=%s " %(self.location,)
        else:
            metharg = ""
            
        return """<domain type='xen'>
  <name>%(name)s</name>
  <os>
    <type>linux</type>
    <kernel>%(kernel)s</kernel>
    <initrd>%(initrd)s</initrd>
    <cmdline> %(metharg)s %(extra)s</cmdline>
  </os>
  <memory>%(ramkb)s</memory>
  <vcpu>%(vcpus)d</vcpu>
  <uuid>%(uuid)s</uuid>
  <on_reboot>destroy</on_reboot>
  <on_poweroff>destroy</on_poweroff>
  <on_crash>destroy</on_crash>
  <devices>
    '%(disks)s'
    '%(networks)s'
  </devices>
</domain>
""" % { "kernel": kernel, "initrd": initrd, "name": self.name, "metharg": metharg, "extra": self.extraargs, "vcpus": self.vcpus, "uuid": self.uuid, "ramkb": self.memory * 1024, "disks": self._get_disk_xml(), "networks": self._get_network_xml() }

    def _get_disk_xen(self):
        if len(self.disks) == 0: return ""
        ret = "disk = [ "
        count = 0
        for d in self.disks:
            ret += "'%(disktype)s:%(disk)s,xvd%(dev)c,w', " %{"disktype": d.type, "disk": d.path, "dev": ord('a') + count}
            count += 1
        ret += "]"
        return ret

    def _get_network_xen(self):
        if len(self.nics) == 0: return ""
        ret = "vif = [ "
        for n in self.nics:
            ret += "'mac=%(mac)s, bridge=%(bridge)s', " % { "bridge": n.bridge, "mac": n.macaddr }
        ret += "]"
        return ret

    def _get_config_xen(self):
        return """# Automatically generated xen config file
name = "%(name)s"
memory = "%(ram)s"
%(disks)s
%(networks)s
uuid = "%(uuid)s"
bootloader="/usr/bin/pygrub"

on_reboot   = 'restart'
on_crash    = 'restart'
""" % { "name": self.name, "ram": self.memory, "disks": self._get_disk_xen(), "networks": self._get_network_xen(), "uuid": self.uuid }

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

    def start_install(self, connectConsole = False):
        if not self.location and not self.boot:
            raise RuntimeError, "A location must be specified to install from"
        XenGuest.XenGuest.validateParms(self)
        
        conn = libvirt.openReadOnly(None)
        if conn == None:
            raise RuntimeError, "Unable to connect to hypervisor, aborting installation!"
        try:
            if conn.lookupByName(self.name) is not None:
                raise RuntimeError, "Domain named %s already exists!" %(self.name,)
        except libvirt.libvirtError:
            pass

        (kfn, ifn) = self._get_paravirt_install_images()
        self._createDevices()
        cxml = self._get_config_xml(kfn, ifn)
        
        self.domain = conn.createLinux(cxml, 0)
        if self.domain is None:
            raise RuntimeError, "Unable to create domain for guest, aborting installation!"
        if connectConsole:
            child = self._connectSerialConsole()

        time.sleep(5)
        os.unlink(kfn)
        os.unlink(ifn)

        # FIXME: if the domain doesn't exist now, it almost certainly crashed.
        # it'd be nice to know that for certain...
        try:
            d = conn.lookupByID(self.domain.ID())
        except libvirt.libvirtError:
            raise RuntimeError, "It appears that your installation has crashed.  You should be able to find more information in the xen logs"


        cf = "/etc/xen/%s" %(self.name,)
        f = open(cf, "w+")
        f.write(self._get_config_xen())
        f.close()

        if connectConsole: # if we connected the console, wait for it to finish
            try:
                (pid, status) = os.waitpid(child, 0)
            except OSError, (errno, msg):
                print __name__, "waitpid:", msg

            # ensure there's time for the domain to finish destroying if the
            # install has finished or the guest crashed
            time.sleep(1)
            try:
                d = conn.lookupByID(self.domain.ID())
            except libvirt.libvirtError:
                return "If your install completed successfully, you can restart your guest by running 'xm create -c %s'." %(self.name,)
            else:
                return "You can reconnect to the console of your guest by running 'xm console %s'" %(self.name,)

        return 
        
