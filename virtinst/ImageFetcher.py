#!/usr/bin/python -tt
#
# Convenience module for fetching files from a network source
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
import stat
import subprocess
import urlgrabber.grabber as grabber
import urlgrabber.progress as progress
import tempfile
from virtinst import _virtinst as _

# This is a generic base class for fetching/extracting files from
# a media source, such as CD ISO, NFS server, or HTTP/FTP server
class ImageFetcher:

    def __init__(self, location, scratchdir):
        self.location = location
        self.scratchdir = scratchdir

    def saveTemp(self, fileobj, prefix):
        (fd, fn) = tempfile.mkstemp(prefix="virtinst-" + prefix, dir=self.scratchdir)
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

    def prepareLocation(self, progresscb):
        return True

    def cleanupLocation(self):
        pass

    def acquireFile(self, src, progresscb):
        raise "Must be implemented in subclass"

    def hasFile(self, src, progresscb):
        raise "Must be implemented in subclass"

# This is a fetcher capable of downloading from FTP / HTTP
class URIImageFetcher(ImageFetcher):

    def prepareLocation(self, progresscb):
        try:
            grabber.urlopen(self.location,
                            progress_obj = progresscb,
                            text = _("Verifying install location..."))
            return True
        except IOError, e:
            logging.debug("Opening URL %s failed." % (self.location,) + " " + str(e))
            raise ValueError(_("Opening URL %s failed.") % (self.location,))
            return False

    def acquireFile(self, filename, progresscb):
        file = None
        try:
            base = os.path.basename(filename)
            logging.debug("Fetching URI " + self.location + "/" + filename)
            try:
                file = grabber.urlopen(self.location + "/" + filename,
                                       progress_obj = progresscb, \
                                       text = _("Retrieving file %s...") % base)
            except IOError, e:
                raise ValueError, _("Invalid URL location given: %s %s") %\
                                  ((self.location + "/" + filename), str(e))
            tmpname = self.saveTemp(file, prefix=base + ".")
            logging.debug("Saved file to " + tmpname)
            return tmpname
        finally:
            if file:
                file.close()

    def hasFile(self, filename, progresscb):
        try:
            tmpfile = self.acquireFile(filename, progresscb)
            os.unlink(tmpfile)
            return True
        except Exception, e:
            logging.debug("Cannot find file %s" % filename)
            return False


class LocalImageFetcher(ImageFetcher):

    def __init__(self, location, scratchdir, srcdir=None):
        ImageFetcher.__init__(self, location, scratchdir)

    def acquireFile(self, filename, progresscb):
        file = None
        try:
            logging.debug("Acquiring file from " + self.srcdir + "/" + filename)
            base = os.path.basename(filename)
            try:
                src = self.srcdir + "/" + filename
                if stat.S_ISDIR(os.stat(src)[stat.ST_MODE]):
                    logging.debug("Found a directory")
                    return None
                else:
                    file = open(src, "r")
            except IOError, e:
                raise ValueError, _("Invalid file location given: ") + str(e)
            except OSError, (errno, msg):
                raise ValueError, _("Invalid file location given: ") + msg
            tmpname = self.saveTemp(file, prefix=base + ".")
            logging.debug("Saved file to " + tmpname)
            return tmpname
        finally:
            if file:
                file.close()

    def hasFile(self, filename, progresscb):
        try:
            tmpfile = self.acquireFile(filename, progresscb)
            if tmpfile is not None:
                os.unlink(tmpfile)
            return True
        except Exception, e:
            logging.debug("Cannot find file %s" % filename)
            return False

# This is a fetcher capable of extracting files from a NFS server
# or loopback mounted file, or local CDROM device
class MountedImageFetcher(LocalImageFetcher):

    def prepareLocation(self, progresscb):
        cmd = None
        self.srcdir = tempfile.mkdtemp(prefix="virtinstmnt.", dir=self.scratchdir)
        logging.debug("Preparing mount at " + self.srcdir)
        if self.location.startswith("nfs://"):
            cmd = ["mount", "-o", "ro", self.location[4:], self.srcdir]
        elif self.location.startswith("nfs:"):
            cmd = ["mount", "-o", "ro", self.location[6:], self.srcdir]
        else:
            if stat.S_ISBLK(os.stat(self.location)[stat.ST_MODE]):
                cmd = ["mount", "-o", "ro", self.location, self.srcdir]
            else:
                cmd = ["mount", "-o", "ro,loop", self.location, self.srcdir]
        ret = subprocess.call(cmd)
        if ret != 0:
            self.cleanupLocation()
            logging.debug("Mounting location %s failed" % (self.location,))
            raise ValueError(_("Mounting location %s failed") % (self.location))
            return False
        return True

    def cleanupLocation(self):
        logging.debug("Cleaning up mount at " + self.srcdir)
        cmd = ["umount", self.srcdir]
        ret = subprocess.call(cmd)
        try:
            os.rmdir(self.srcdir)
        except:
            pass

class DirectImageFetcher(LocalImageFetcher):

    def prepareLocation(self, progresscb):
        self.srcdir = self.location

