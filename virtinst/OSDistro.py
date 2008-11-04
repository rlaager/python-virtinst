#
# Represents OS distribution specific install data
#
# Copyright 2006-2007  Red Hat, Inc.
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

import logging
import os
import gzip
import re
import tempfile
import platform
import ConfigParser

from virtinst import _virtinst as _

# An image store is a base class for retrieving either a bootable
# ISO image, or a kernel+initrd  pair for a particular OS distribution
class Distro:

    def __init__(self, uri, vmtype=None, scratchdir=None, arch=None):
        self.uri = uri
        self.type = vmtype
        self.scratchdir = scratchdir
        if arch == None:
            arch = platform.machine()
        self.arch = arch
        self.treeinfo = None

    def acquireBootDisk(self, fetcher, progresscb):
        raise "Not implemented"

    def acquireKernel(self, fetcher, progresscb):
        raise "Not implemented"

    def isValidStore(self, fetcher, progresscb):
        """Determine if uri points to a tree of the store's distro"""
        raise "Not implemented"

    def _hasTreeinfo(self, fetcher, progresscb):
        # all Red Hat based distros should have .treeinfo, perhaps others
        # will in time
        if not (self.treeinfo is None):
            return True

        if not fetcher.hasFile(".treeinfo"):
            return False

        logging.debug("Detected .treeinfo file")

        tmptreeinfo = fetcher.acquireFile(".treeinfo", progresscb)
        try:
            self.treeinfo = ConfigParser.SafeConfigParser()
            self.treeinfo.read(tmptreeinfo)
        finally:
            os.unlink(tmptreeinfo)
        return True

    def _getTreeinfoMedia(self, fetcher, progresscb, mediaName):
        if self.type == "xen":
            t = "xen"
        else:
            t = self.treeinfo.get("general", "arch")

        return self.treeinfo.get("images-%s" % t, mediaName)


class GenericDistro(Distro):
    """Generic distro store. Check well known paths for kernel locations
       as a last resort if we can't recognize any actual distro"""
    _xen_paths = [ ("images/xen/vmlinuz",
                    "images/xen/initrd.img"),           # Fedora
                 ]
    _hvm_paths = [ ("images/pxeboot/vmlinuz",
                    "images/pxeboot/initrd.img"),       # Fedora
                 ]
    _iso_paths = [ "images/boot.iso",                   # RH/Fedora
                   "boot/boot.iso",                     # Suse
                   "current/images/netboot/mini.iso",   # Debian
                   "install/images/boot.iso",           # Mandriva
                 ]

    # Holds values to use when actually pulling down media
    _valid_kernel_path = None
    _valid_iso_path = None

    def isValidStore(self, fetcher, progresscb):
        if self._hasTreeinfo(fetcher, progresscb):
            # Use treeinfo to pull down media paths
            if self.type == "xen":
                typ = "xen"
            else:
                typ = self.treeinfo.get("general", "arch")
            kernelSection = "images-%s" % typ
            isoSection = "images-%s" % self.treeinfo.get("general", "arch")

            if self.treeinfo.has_section(kernelSection):
                self._valid_kernel_path = (self._getTreeinfoMedia(fetcher, progresscb, "kernel"), self._getTreeinfoMedia(fetcher, progresscb, "initrd"))
            if self.treeinfo.has_section(isoSection):
                self._valid_iso_path = self.treeinfo.get(isoSection, "boot.iso")

        if self.type == "xen":
            kern_list = self._xen_paths
        else:
            kern_list = self._hvm_paths

        # If validated media paths weren't found (no treeinfo), check against
        # list of media location paths.
        for kern, init in kern_list:
            if self._valid_kernel_path == None \
               and fetcher.hasFile(kern) and fetcher.hasFile(init):
                self._valid_kernel_path = (kern, init)
                break
        for iso in self._iso_paths:
            if self._valid_iso_path == None \
               and fetcher.hasFile(iso):
                self._valid_iso_path = iso
                break

        if self._valid_kernel_path or self._valid_iso_path:
            return True
        return False

    def acquireKernel(self, fetcher, progresscb):
        if self._valid_kernel_path == None:
            raise ValueError(_("Could not find a kernel path for virt type "
                               "'%s'" % self.type))

        kernel = fetcher.acquireFile(self._valid_kernel_path[0], progresscb)
        try:
            initrd = fetcher.acquireFile(self._valid_kernel_path[1], progresscb)
            if fetcher.location.startswith("/"):
                return (kernel, initrd, "")
            else:
                return (kernel, initrd, "method=" + fetcher.location)
        except:
            os.unlink(kernel)

    def acquireBootDisk(self, fetcher, progresscb):
        if self._valid_iso_path == None:
            raise ValueError(_("Could not find a boot iso path for this tree."))

        return fetcher.acquireFile(self._valid_iso_path, progresscb)


# Base image store for any Red Hat related distros which have
# a common layout
class RedHatDistro(Distro):

    def acquireKernel(self, fetcher, progresscb):
        if self._hasTreeinfo(fetcher, progresscb):
            kernelpath = self._getTreeinfoMedia(fetcher, progresscb, "kernel")
            initrdpath = self._getTreeinfoMedia(fetcher, progresscb, "initrd")
        else:
            # fall back to old code
            if self.type is None or self.type == "hvm":
                kernelpath = "images/pxeboot/vmlinuz"
                initrdpath = "images/pxeboot/initrd.img"
            else:
                kernelpath = "images/%s/vmlinuz" % (self.type)
                initrdpath = "images/%s/initrd.img" % (self.type)

        kernel = fetcher.acquireFile(kernelpath, progresscb)
        try:
            initrd = fetcher.acquireFile(initrdpath, progresscb)
            if fetcher.location.startswith("/"):
                # Local host path, so can't pass a location to guest for install method
                return (kernel, initrd, "")
            else:
                return (kernel, initrd, "method=" + fetcher.location)
        except:
            os.unlink(kernel)

    def acquireBootDisk(self, fetcher, progresscb):
        if self._hasTreeinfo(fetcher, progresscb):
            return fetcher.acquireFile(self._getTreeinfoMedia(fetcher,
                                                              progresscb,
                                                              "boot.iso"))
        else:
            return fetcher.acquireFile("images/boot.iso", progresscb)

# Fedora distro check
class FedoraDistro(RedHatDistro):
    def isValidStore(self, fetcher, progresscb):
        if self._hasTreeinfo(fetcher, progresscb):
            m = re.match(".*Fedora.*", self.treeinfo.get("general", "family"))
            return (m != None)
        else:
            if fetcher.hasFile("Fedora"):
                logging.debug("Detected a Fedora distro")
                return True
            return False

# Red Hat Enterprise Linux distro check
class RHELDistro(RedHatDistro):
    def isValidStore(self, fetcher, progresscb):
        if self._hasTreeinfo(fetcher, progresscb):
            m = re.match(".*Red Hat Enterprise Linux.*", self.treeinfo.get("general", "family"))
            return (m != None)
        else:
            # fall back to old code
            if fetcher.hasFile("Server"):
                logging.debug("Detected a RHEL 5 Server distro")
                return True
            if fetcher.hasFile("Client"):
                logging.debug("Detected a RHEL 5 Client distro")
                return True
            if fetcher.hasFile("RedHat"):
                logging.debug("Detected a RHEL 4 distro")
                return True
            return False

# CentOS distro check
class CentOSDistro(RedHatDistro):
    def isValidStore(self, fetcher, progresscb):
        if self._hasTreeinfo(fetcher, progresscb):
            m = re.match(".*CentOS.*", self.treeinfo.get("general", "family"))
            return (m != None)
        else:
            # fall back to old code
            if fetcher.hasFile("CentOS"):
                logging.debug("Detected a CentOS distro")
                return True
            return False

# Scientific Linux distro check
class SLDistro(RedHatDistro):
    def isValidStore(self, fetcher, progresscb):
        if fetcher.hasFile("SL"):
            logging.debug("Detected a Scientific Linux distro")
            return True
        return False



# Suse  image store is harder - we fetch the kernel RPM and a helper
# RPM and then munge bits together to generate a initrd
class SuseDistro(Distro):
    def __init__(self, uri, vmtype=None, scratchdir=None, arch=None):
        Distro.__init__(self, uri, vmtype, scratchdir, arch)
        if len(self.arch) == 4 and self.arch[0] == 'i' \
           and self.arch[2:] == "86":
            self.arch = "i386"

    def acquireBootDisk(self, fetcher, progresscb):
        return fetcher.acquireFile("boot/boot.iso", progresscb)

    def acquireKernel(self, fetcher, progresscb):
        kernel_args = ""
        if not fetcher.location.startswith("/"):
            kernel_args = "method=" + fetcher.location

        # If installing a fullvirt guest
        if self.type is None or self.type == "hvm":
            # Tested with Opensuse 10, 11, and sles 10
            kernel = fetcher.acquireFile("boot/%s/loader/linux" % self.arch,
                                         progresscb)
            initrd = fetcher.acquireFile("boot/%s/loader/initrd" % self.arch,
                                         progresscb)
            return (kernel, initrd, kernel_args)

        # Else we are looking for a paravirt kernel
        if fetcher.hasFile("boot/%s/vmlinuz-xen" % self.arch):
            # Should match opensuse > 10.2 and sles 10
            kernel = fetcher.acquireFile("boot/%s/vmlinuz-xen" % self.arch,
                                         progresscb)
            initrd = fetcher.acquireFile("boot/%s/initrd-xen" % self.arch,
                                         progresscb)
            return (kernel, initrd, kernel_args)

        # For Opensuse <= 10.2, we need to perform some heinous stuff
        logging.debug("Trying Opensuse 10 PV rpm hacking")
        return self._findXenRPMS(fetcher, progresscb)


    def _findXenRPMS(self, fetcher, progresscb):
        kernelrpm = None
        installinitrdrpm = None
        filelist = None
        try:
            # There is no predictable filename for kernel/install-initrd RPMs
            # so we have to grok the filelist and find them
            filelist = fetcher.acquireFile("ls-lR.gz", progresscb)
            (kernelrpmname, initrdrpmname) = self._extractRPMNames(filelist)

            # Now fetch the two RPMs we want
            kernelrpm = fetcher.acquireFile(kernelrpmname, progresscb)
            installinitrdrpm = fetcher.acquireFile(initrdrpmname, progresscb)

            # Process the RPMs to extract the kernel & generate an initrd
            return self._buildKernelInitrd(fetcher, kernelrpm, installinitrdrpm, progresscb)
        finally:
            if filelist is not None:
                os.unlink(filelist)
            if kernelrpm is not None:
                os.unlink(kernelrpm)
            if installinitrdrpm is not None:
                os.unlink(installinitrdrpm)

    # We need to parse the ls-lR.gz file, looking for the kernel &
    # install-initrd RPM entries - capturing the directory they are
    # in and the version'd filename.
    def _extractRPMNames(self, filelist):
        filelistData = gzip.GzipFile(filelist, mode = "r")
        try:
            arches = [self.arch]
            # On i686 arch, we also look under i585 and i386 dirs
            # in case the RPM is built for a lesser arch. We also
            # need the PAE variant (for Fedora dom0 at least)
            #
            # XXX shouldn't hard code that dom0 is PAE
            if self.arch == "i386":
                arches.append("i586")
                arches.append("i686")
                kernelname = "kernel-xenpae"
            else:
                kernelname = "kernel-xen"

            installinitrdrpm = None
            kernelrpm = None
            dirname = None
            while 1:
                data = filelistData.readline()
                if not data:
                    break
                if dirname is None:
                    for arch in arches:
                        wantdir = "/suse/" + arch
                        if data == "." + wantdir + ":\n":
                            dirname = wantdir
                            break
                else:
                    if data == "\n":
                        dirname = None
                    else:
                        if data[:5] != "total":
                            filename = re.split("\s+", data)[8]

                            if filename[:14] == "install-initrd":
                                installinitrdrpm = dirname + "/" + filename
                            elif filename[:len(kernelname)] == kernelname:
                                kernelrpm = dirname + "/" + filename

            if kernelrpm is None:
                raise Exception(_("Unable to determine kernel RPM path"))
            if installinitrdrpm is None:
                raise Exception(_("Unable to determine install-initrd RPM path"))
            return (kernelrpm, installinitrdrpm)
        finally:
            filelistData.close()

    # We have a kernel RPM and a install-initrd RPM with a generic initrd in it
    # Now we have to merge the two together to build an initrd capable of
    # booting the installer.
    #
    # Yes, this is crazy ass stuff :-)
    def _buildKernelInitrd(self, fetcher, kernelrpm, installinitrdrpm, progresscb):
        progresscb.start(text=_("Building initrd"), size=11)
        progresscb.update(1)
        cpiodir = tempfile.mkdtemp(prefix="virtinstcpio.", dir=self.scratchdir)
        try:
            # Extract the kernel RPM contents
            os.mkdir(cpiodir + "/kernel")
            cmd = "cd " + cpiodir + "/kernel && (rpm2cpio " + kernelrpm + " | cpio --quiet -idm)"
            logging.debug("Running " + cmd)
            os.system(cmd)
            progresscb.update(2)

            # Determine the raw kernel version
            kernelinfo = None
            for f in os.listdir(cpiodir + "/kernel/boot"):
                if f.startswith("System.map-"):
                    kernelinfo = re.split("-", f)
            kernel_override = kernelinfo[1] + "-override-" + kernelinfo[3]
            kernel_version = kernelinfo[1] + "-" + kernelinfo[2] + "-" + kernelinfo[3]
            logging.debug("Got kernel version " + str(kernelinfo))

            # Build a list of all .ko files
            modpaths = {}
            for root, dummy, files in os.walk(cpiodir + "/kernel/lib/modules", topdown=False):
                for name in files:
                    if name.endswith(".ko"):
                        modpaths[name] = os.path.join(root, name)
            progresscb.update(3)

            # Extract the install-initrd RPM contents
            os.mkdir(cpiodir + "/installinitrd")
            cmd = "cd " + cpiodir + "/installinitrd && (rpm2cpio " + installinitrdrpm + " | cpio --quiet -idm)"
            logging.debug("Running " + cmd)
            os.system(cmd)
            progresscb.update(4)

            # Read in list of mods required for initrd
            modnames = []
            fn = open(cpiodir + "/installinitrd/usr/lib/install-initrd/" + kernelinfo[3] + "/module.list", "r")
            try:
                while 1:
                    line = fn.readline()
                    if not line:
                        break
                    line = line[:len(line)-1]
                    modnames.append(line)
            finally:
                fn.close()
            progresscb.update(5)

            # Uncompress the basic initrd
            cmd = "gunzip -c " + cpiodir + "/installinitrd/usr/lib/install-initrd/initrd-base.gz > " + cpiodir + "/initrd.img"
            logging.debug("Running " + cmd)
            os.system(cmd)
            progresscb.update(6)

            # Create temp tree to hold stuff we're adding to initrd
            moddir = cpiodir + "/initrd/lib/modules/" + kernel_override + "/initrd/"
            moddepdir = cpiodir + "/initrd/lib/modules/" + kernel_version
            os.makedirs(moddir)
            os.makedirs(moddepdir)
            os.symlink("../" + kernel_override, moddepdir + "/updates")
            os.symlink("lib/modules/" + kernel_override + "/initrd", cpiodir + "/initrd/modules")
            cmd = "cp " + cpiodir + "/installinitrd/usr/lib/install-initrd/" + kernelinfo[3] + "/module.config" + " " + moddir
            logging.debug("Running " + cmd)
            os.system(cmd)
            progresscb.update(7)

            # Copy modules we need into initrd staging dir
            for modname in modnames:
                if modpaths.has_key(modname):
                    src = modpaths[modname]
                    dst = moddir + "/" + modname
                    os.system("cp " + src + " " + dst)
            progresscb.update(8)

            # Run depmod across the staging area
            cmd = "depmod -a -b " + cpiodir + "/initrd -F " + cpiodir + "/kernel/boot/System.map-" + kernel_version + " " + kernel_version
            logging.debug("Running " + cmd)
            os.system(cmd)
            progresscb.update(9)

            # Add the extra modules to the basic initrd
            cmd = "cd " + cpiodir + "/initrd && ( find . | cpio --quiet -o -H newc -A -F " + cpiodir + "/initrd.img)"
            logging.debug("Running " + cmd)
            os.system(cmd)
            progresscb.update(10)

            # Compress the final initrd
            cmd = "gzip -f9N " + cpiodir + "/initrd.img"
            logging.debug("Running " + cmd)
            os.system(cmd)
            progresscb.end(11)

            # Save initrd & kernel to temp files for booting...
            initrdname = fetcher.saveTemp(open(cpiodir + "/initrd.img.gz", "r"), "initrd.img")
            logging.debug("Saved " + initrdname)
            try:
                kernelname = fetcher.saveTemp(open(cpiodir + "/kernel/boot/vmlinuz-" + kernel_version, "r"), "vmlinuz")
                logging.debug("Saved " + kernelname)
                return (kernelname, initrdname, "install=" + fetcher.location)
            except:
                os.unlink(initrdname)
        finally:
            #pass
            os.system("rm -rf " + cpiodir)


    def isValidStore(self, fetcher, progresscb):
        # Suse distros always have a 'directory.yast' file in the top
        # level of install tree, which we use as the magic check
        if fetcher.hasFile("directory.yast"):
            logging.debug("Detected a Suse distro.")
            return True
        return False


class DebianDistro(Distro):
    # location e.g. http://ftp.egr.msu.edu/debian/dists/sarge/main/installer-i386/

    def __init__(self, uri, vmtype=None, scratchdir=None, arch=None):
        Distro.__init__(self, uri, vmtype, scratchdir, arch)
        if re.match(r'i[4-9]86', arch):
            self.arch = 'i386'
        self._prefix = 'current/images'

    def isValidStore(self, fetcher, progresscb):
        f = None
        try:
            try:
                f = None
                if fetcher.hasFile("%s/MANIFEST" % self._prefix):
                    f = fetcher.acquireFile("%s/MANIFEST" % self._prefix,
                                                   progresscb)
                elif fetcher.hasFile("images/daily/MANIFEST"):
                    self._prefix = "images/daily"
                    f = fetcher.acquireFile("%s/MANIFEST" % self._prefix,
                                                   progresscb)
                else:
                    logging.debug("Doesn't look like a Debian distro.")
                    return False
                    
            except ValueError, e:
                logging.debug("Doesn't look like a Debian distro " + str(e))
                return False
            fobj = open(f, "r")
            try:
                while 1:
                    buf = fobj.readline()
                    if not buf:
                        break
                    if re.match(".*debian.*", buf):
                        logging.debug("Detected a Debian distro")
                        return True
            finally:
                fobj.close()
        finally:
            if f is not None:
                os.unlink(f)
        return False

    def acquireBootDisk(self, fetcher, progresscb):
        return fetcher.acquireFile("%s/netboot/mini.iso" % self._prefix, progresscb)

    def acquireKernel(self, fetcher, progresscb):
        if self.type is None or self.type == "hvm":
            kernelpath = "%s/netboot/debian-installer/%s/linux" % (self._prefix, self.arch)
            initrdpath = "%s/netboot/debian-installer/%s/initrd.gz" % (self._prefix, self.arch)
        else:
            kernelpath = "%s/netboot/xen/vmlinuz" % self._prefix
            initrdpath = "%s/netboot/xen/initrd.gz" % self._prefix

        kernel = fetcher.acquireFile(kernelpath, progresscb)
        try:
            initrd = fetcher.acquireFile(initrdpath, progresscb)
            if fetcher.location.startswith("/"):
                # Local host path, so can't pass a location to guest for install method
                return (kernel, initrd, "")
            else:
                return (kernel, initrd, "method=" + fetcher.location)
        except:
            os.unlink(kernel)


class UbuntuDistro(Distro):
    def isValidStore(self, fetcher, progresscb):
        # Don't support any paravirt installs
        if self.type is not None and self.type != "hvm":
            return False
        return False

class GentooDistro(Distro):
    def isValidStore(self, fetcher, progresscb):
        # Don't support any paravirt installs
        if self.type is not None and self.type != "hvm":
            return False
        return False

class MandrivaDistro(Distro):
    def isValidStore(self, fetcher, progresscb):
        # Don't support any paravirt installs
        if self.type is not None and self.type != "hvm":
            return False

        # Mandriva websites / media appear to have a VERSION
        # file in top level which we can use as our 'magic'
        # check for validity
        version = None
        try:
            try:
                version = fetcher.acquireFile("VERSION")
            except:
                return False
            f = open(version, "r")
            try:
                info = f.readline()
                if info.startswith("Mandriva"):
                    logging.debug("Detected a Mandriva distro")
                    return True
            finally:
                f.close()
        finally:
            if version is not None:
                os.unlink(version)

        return False

    def acquireBootDisk(self, fetcher, progresscb):
        #
        return fetcher.acquireFile("install/images/boot.iso", progresscb)
