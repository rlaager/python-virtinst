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
import ConfigParser

from virtinst import _virtinst as _

# An image store is a base class for retrieving either a bootable
# ISO image, or a kernel+initrd  pair for a particular OS distribution
class Distro:

    def __init__(self, uri, type=None, scratchdir=None):
        self.uri = uri
        self.type = type
        self.scratchdir = scratchdir

    def acquireBootDisk(self, fetcher, progresscb):
        raise "Not implemented"

    def acquireKernel(self, fetcher, progresscb):
        raise "Not implemented"

    def isValidStore(self, fetcher, progresscb):
        raise "Not implemented"


# Base image store for any Red Hat related distros which have
# a common layout
class RedHatDistro(Distro):
    def __init__(self, uri, type=None, scratchdir=None):
        Distro.__init__(self, uri, type, scratchdir)
        self.treeinfo = None

    def hasTreeinfo(self, fetcher, progresscb):
        # all Red Hat based distros should have .treeinfo / execute only once
        if (self.treeinfo is None):
            if fetcher.hasFile(".treeinfo"):
                logging.debug("Detected .treeinfo file")
                tmptreeinfo = fetcher.acquireFile(".treeinfo", progresscb)
                self.treeinfo = ConfigParser.SafeConfigParser()
                self.treeinfo.read(tmptreeinfo)
                return True
            else:
                return False
        else:
            return True

    def acquireKernel(self, fetcher, progresscb):
        if self.hasTreeinfo(fetcher, progresscb):
            if self.type == "xen":
                type = "xen"
            else:
                type = self.treeinfo.get("general", "arch")

            kernelpath = self.treeinfo.get("images-%s" % type, "kernel")
            initrdpath = self.treeinfo.get("images-%s" % type, "initrd")
        else:
            # fall back to old code
            if self.type is None:
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
        if self.hasTreeinfo(fetcher, progresscb):
            if self.type == "xen":
                type = "xen"
            else:
                type = self.treeinfo.get("general", "arch")
            return fetcher.acquireFile(self.treeinfo.get("images-%s" % type, "boot.iso"), progresscb)
        else:
            return fetcher.acquireFile("images/boot.iso", progresscb)

# Fedora distro check
class FedoraDistro(RedHatDistro):
    def isValidStore(self, fetcher, progresscb):
        if self.hasTreeinfo(fetcher, progresscb):
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
        if self.hasTreeinfo(fetcher, progresscb):
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
        if self.hasTreeinfo(fetcher, progresscb):
            m = re.match(".*CentOS.*", self.treeinfo.get("general", "family"))
            return (m != None)
        else:
            # fall back to old code
            if fetcher.hasFile("CentOS"):
                logging.debug("Detected a CentOS distro")
                return True
            return False



# Suse  image store is harder - we fetch the kernel RPM and a helper
# RPM and then munge bits together to generate a initrd
class SuseDistro(Distro):
    def acquireBootDisk(self, fetcher, progresscb):
        return fetcher.acquireFile("boot/boot.iso", progresscb)

    def acquireKernel(self, fetcher, progresscb):
        kernelrpm = None
        installinitrdrpm = None
        filelist = None
        try:
            # There is no predictable filename for kernel/install-initrd RPMs
            # so we have to grok the filelist and find them
            filelist = fetcher.acquireFile("ls-lR.gz", progresscb)
            (kernelrpmname, installinitrdrpmname) = self.extractRPMNames(filelist)

            # Now fetch the two RPMs we want
            kernelrpm = fetcher.acquireFile(kernelrpmname, progresscb)
            installinitrdrpm = fetcher.acquireFile(installinitrdrpmname, progresscb)

            # Process the RPMs to extract the kernel & generate an initrd
            return self.buildKernelInitrd(fetcher, kernelrpm, installinitrdrpm, progresscb)
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
    def extractRPMNames(self, filelist):
        filelistData = gzip.GzipFile(filelist, mode = "r")
        try:
            arch = os.uname()[4]
            arches = [arch]
            # On i686 arch, we also look under i585 and i386 dirs
            # in case the RPM is built for a lesser arch. We also
            # need the PAE variant (for Fedora dom0 at least)
            #
            # XXX shouldn't hard code that dom0 is PAE
            if arch == "i686":
                arches.append("i586")
                arches.append("i386")
                kernelname = "kernel-xenpae"

            installinitrdrpm = None
            kernelrpm = None
            dir = None
            while 1:
                data = filelistData.readline()
                if not data:
                    break
                if dir is None:
                    for arch in arches:
                        wantdir = "/suse/" + arch
                        if data == "." + wantdir + ":\n":
                            dir = wantdir
                            break
                else:
                    if data == "\n":
                        dir = None
                    else:
                        if data[:5] != "total":
                            filename = re.split("\s+", data)[8]

                            if filename[:14] == "install-initrd":
                                installinitrdrpm = dir + "/" + filename
                            elif filename[:len(kernelname)] == kernelname:
                                kernelrpm = dir + "/" + filename

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
    def buildKernelInitrd(self, fetcher, kernelrpm, installinitrdrpm, progresscb):
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
            for root, dirs, files in os.walk(cpiodir + "/kernel/lib/modules", topdown=False):
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
    def isValidStore(self, fetcher, progresscb):
        # Don't support any paravirt installs
        if self.type is not None:
            return False

        file = None
        try:
            try:
                file = None
                if fetcher.hasFile("current/images/MANIFEST"):
                    file = fetcher.acquireFile("current/images/MANIFEST", 
                                               progresscb)
                else:
                    logging.debug("Doesn't look like a Debian distro.")
                    return False
                    
            except ValueError, e:
                logging.debug("Doesn't look like a Debian distro " + str(e))
                return False
            f = open(file, "r")
            try:
                while 1:
                    buf = f.readline()
                    if not buf:
                        break
                    if re.match(".*debian.*", buf):
                        logging.debug("Detected a Debian distro")
                        return True
            finally:
                f.close()
        finally:
            if file is not None:
                os.unlink(file)
        return False

    def acquireBootDisk(self, fetcher, progresscb):
        # eg from http://ftp.egr.msu.edu/debian/dists/sarge/main/installer-i386/
        return fetcher.acquireFile("current/images/netboot/mini.iso", progresscb)


class UbuntuDistro(Distro):
    def isValidStore(self, fetcher, progresscb):
        # Don't support any paravirt installs
        if self.type is not None:
            return False
        return False

class GentooDistro(Distro):
    def isValidStore(self, fetcher, progresscb):
        # Don't support any paravirt installs
        if self.type is not None:
            return False
        return False

class MandrivaDistro(Distro):
    def isValidStore(self, fetcher, progresscb):
        # Don't support any paravirt installs
        if self.type is not None:
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
