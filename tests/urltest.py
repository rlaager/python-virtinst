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

import virtinst.OSDistro as OSDistro
from virtinst.OSDistro import FedoraDistro
from virtinst.OSDistro import SuseDistro
from virtinst.OSDistro import DebianDistro
from virtinst.OSDistro import CentOSDistro
from virtinst.OSDistro import SLDistro
from virtinst.OSDistro import UbuntuDistro
from virtinst.OSDistro import MandrivaDistro

import unittest
import time
import logging
import re
import urlgrabber.progress
import platform
import tests
import libvirt
import virtinst

# Filters for including/excluding certain distros.
MATCH_FILTER = ".*"

# Variable used to store a local iso or dir path to check for a distro
# Specified via 'python setup.py test_urls --path"
LOCAL_MEDIA = []

# GeoIP/managed URLs
FEDORA_BASEURL = "http://download.fedoraproject.org/pub/fedora/linux/releases/%s/Fedora/%s/os/"
FEDORA_RAWHIDE_BASEURL = "http://download.fedoraproject.org/pub/fedora/linux/development/%s/os"
OPENSUSE_BASEURL = "http://download.opensuse.org/distribution/%s/repo/oss/"
OLD_OPENSUSE_BASEURL = "http://ftp5.gwdg.de/pub/opensuse/discontinued/distribution/%s/repo/oss"

# ISO Code specific URLs
UBUNTU_BASEURL = "http://us.archive.ubuntu.com/ubuntu/dists/%s/main/installer-%s"
DEBIAN_BASEURL = "http://ftp.us.debian.org/debian/dists/%s/main/installer-%s/"

# Static URLs
CURCENTOS_BASEURL = "http://ftp.linux.ncsu.edu/pub/CentOS/%s/os/%s/"
OLDCENTOS_BASEURL = "http://vault.centos.org/%s/os/%s"
MANDRIVA_BASEURL = "ftp://ftp.uwsg.indiana.edu/linux/mandrake/official/%s/%s/"
SCIENTIFIC_BASEURL = "http://ftp.scientificlinux.org/linux/scientific/%s/%s/"

# Regex matching distro names that don't have xen kernels.
NOXEN_FILTER = ".*ubuntu.*|.*etch.*|.*mandriva.*|.*lenny-64.*|.*centos-4.0.*|.*scientific-4.0.*"

# Doesn't appear to be a simple boot iso in newer suse trees
NOBOOTISO_FILTER = ".*opensuse11.*|.*opensuse10.3.*|.*opensuse10.0.*"

# Opensuse < 10.3 (and some sles) require crazy rpm hacking to get a bootable
# kernel. We expect failure in this case since our test harness doesn't
# actually fetch anything
EXPECT_XEN_FAIL = ".*opensuse10.2.*|.*opensuse10.0.*"

# Return the expected Distro class for the passed distro label
def distroClass(distname):
    if re.match(r".*fedora.*", distname):
        return FedoraDistro
    elif re.match(r".*suse.*", distname):
        return SuseDistro
    elif re.match(r".*debian.*", distname):
        return DebianDistro
    elif re.match(r".*centos.*", distname):
        return CentOSDistro
    elif re.match(r".*ubuntu.*", distname):
        return UbuntuDistro
    elif re.match(r".*mandriva.*", distname):
        return MandrivaDistro
    elif re.match(r".*scientific.*", distname):
        return SLDistro
    raise RuntimeError("distroClass: no distro registered for '%s'" % distname)

# Dictionary with all the test data
urls = {

    # Fedora Distros
    "fedora11" : {
        'i386'  : FEDORA_BASEURL % ("11", "i386"),
        'x86_64': FEDORA_BASEURL % ("11", "x86_64"),
        'distro': ("linux", "fedora11")
    },
    "fedora12" : {
        'i386'  : FEDORA_BASEURL % ("12", "i386"),
        'x86_64': FEDORA_BASEURL % ("12", "x86_64"),
        'distro': ("linux", "fedora12")
    },
    "fedora13" : {
        'i386'  : FEDORA_BASEURL % ("13", "i386"),
        'x86_64': FEDORA_BASEURL % ("13", "x86_64"),
        'distro': ("linux", "fedora13")
    },
    "fedora-rawhide" : {
        #'i386'  : FEDORA_RAWHIDE_BASEURL % ("i386"),
        #'x86_64': FEDORA_RAWHIDE_BASEURL % ("x86_64"),
        #'distro': ("linux", "fedora13")
    },

    # SUSE Distros
    "opensuse10.0" : {
        'i386'  : "http://ftp.hosteurope.de/mirror/ftp.opensuse.org/discontinued/10.0/",
        'x86_64': "http://ftp.hosteurope.de/mirror/ftp.opensuse.org/discontinued/10.0/",
    },
    "opensuse10.2" : {
        'i386'  : OLD_OPENSUSE_BASEURL % ("10.2"),
        'x86_64': OLD_OPENSUSE_BASEURL % ("10.2")
    },
    "opensuse10.3" : {
        'i386'  : OLD_OPENSUSE_BASEURL % ("10.3"),
        'x86_64': OLD_OPENSUSE_BASEURL % ("10.3")
    },
    "opensuse11" : {
        'i386'  : OPENSUSE_BASEURL % ("11.0"),
        'x86_64': OPENSUSE_BASEURL % ("11.0")
    },

    # Debian Distros
    "debian-etch" : {
        'i386' : DEBIAN_BASEURL % ("etch", "i386"),
        'x86_64': DEBIAN_BASEURL % ("etch", "amd64"),
        'distro': ("linux", None)
    },
    "debian-lenny-32" : {
        'i386' : DEBIAN_BASEURL % ("lenny", "i386"),
        'distro': ("linux", None)
    },
    "debian-lenny-64" : {
        'x86_64': DEBIAN_BASEURL % ("lenny", "amd64"),
        'distro': ("linux", None)
    },
    "debian-daily" : {
        'i386' : "http://people.debian.org/~joeyh/d-i/",
        'distro': ("linux", None)
    },

    # CentOS Distros
    "centos-5-latest" : {
        'i386' : CURCENTOS_BASEURL % ("5", "i386"),
        'x86_64' : CURCENTOS_BASEURL % ("5", "x86_64"),  # No .treeinfo
        'distro': ("linux", "rhel5.4")
    },
    "centos-4-latest" : {
        'i386' : CURCENTOS_BASEURL % ("4", "i386"),
        'x86_64' : CURCENTOS_BASEURL % ("4", "x86_64"),
        'distro': ("linux", None)
    },
    "centos-5.0" : {
        'i386' : OLDCENTOS_BASEURL % ("5.0", "i386"),
        'x86_64' : OLDCENTOS_BASEURL % ("5.0", "x86_64"),
        'distro': ("linux", None)
    },
    "centos-4.0" : {
        'i386' : OLDCENTOS_BASEURL % ("4.0", "i386"),
        'x86_64' : OLDCENTOS_BASEURL % ("4.0", "x86_64"),
        'distro': ("linux", None)
    },

    # Scientific Linux
    "scientific-5.4" : {
        'i386'  : SCIENTIFIC_BASEURL % ("54", "i386"),
        'x86_64': SCIENTIFIC_BASEURL % ("54", "x86_64"),
        'distro': ("linux", "rhel5.4")
    },
    "scientific-5.2" : {
        'i386'  : SCIENTIFIC_BASEURL % ("52", "i386"),
        'x86_64': SCIENTIFIC_BASEURL % ("52", "x86_64"),
        'distro': ("linux", "rhel5")
    },
    "scientific-5.0" : {
        'i386'  : SCIENTIFIC_BASEURL % ("50", "i386"),
        'x86_64': SCIENTIFIC_BASEURL % ("50", "x86_64"),
        'distro': ("linux", None)
    },
    "scientific-4.7" : {
        'i386'  : SCIENTIFIC_BASEURL % ("47", "i386"),
        'x86_64': SCIENTIFIC_BASEURL % ("47", "x86_64"),
        'distro': ("linux", None)
    },
    "scientific-4.0" : {
        'i386'  : SCIENTIFIC_BASEURL % ("40", "i386"),
        'x86_64': SCIENTIFIC_BASEURL % ("40", "x86_64"),
        'distro': ("linux", None)
    },

    # Ubuntu
    "ubuntu-gutsy" : {
        'i386': UBUNTU_BASEURL % ("gutsy", "i386"),
        'x86_64': UBUNTU_BASEURL % ("gutsy", "amd64"),
        'distro': ("linux", None)
    },
    "ubuntu-hardy" : {
        'i386': UBUNTU_BASEURL % ("hardy", "i386"),
        'x86_64': UBUNTU_BASEURL % ("hardy", "amd64"),
        'distro': ("linux", None)
    },
    "ubuntu-intrepid" : {
        'i386': UBUNTU_BASEURL % ("intrepid", "i386"),
        'x86_64': UBUNTU_BASEURL % ("intrepid", "amd64"),
        'distro': ("linux", None)
    },

    # Mandriva
    "mandriva-2007.1" : {
        'i386': MANDRIVA_BASEURL % ("2007.1", "i586"),
        'x86_64': MANDRIVA_BASEURL % ("2007.1", "x86_64"),
        'distro': ("linux", None)
    },
    "mandriva-2008.1" : {
        'i386': MANDRIVA_BASEURL % ("2008.1", "i586"),
        'x86_64': MANDRIVA_BASEURL % ("2008.1", "x86_64"),
        'distro': ("linux", None)
    },
    "mandriva-2009.0" : {
        'i386': MANDRIVA_BASEURL % ("2009.0", "i586"),
        'x86_64': MANDRIVA_BASEURL % ("2009.0", "x86_64"),
        'distro': ("linux", None)
    },

}


testconn = libvirt.open("test:///default")
testguest = virtinst.FullVirtGuest(connection=testconn, installer=virtinst.DistroInstaller())

class TestURLFetch(unittest.TestCase):


    def setUp(self):
        self.meter = urlgrabber.progress.BaseMeter()
        if tests.debug:
            self.meter = urlgrabber.progress.TextMeter()

    def _fetchLocalMedia(self, mediapath):
        arch = platform.machine()

        fetcher = OSDistro._fetcherForURI(mediapath, "/tmp")

        try:
            fetcher.prepareLocation()

            # Make sure we detect _a_ distro
            hvmstore = self._getStore(fetcher, mediapath, "hvm", arch)
            logging.debug("Local distro detected as: %s" % hvmstore)
        finally:
            fetcher.cleanupLocation()


    def _fetchFromURLDict(self, distname, url, arch, distro_info):
        logging.debug("\nDistro='%s' arch='%s' url=%s" % \
                      (distname, arch, url))

        fetcher = OSDistro._fetcherForURI(url, "/tmp")

        try:
            fetcher.prepareLocation()
        except Exception, e:
            # Don't raise an error here: the site might be down atm
            logging.error("%s-%s: Couldn't access url %s: %s. Skipping." % \
                          (distname, arch, fetcher.location, str(e)))
            fetcher.cleanupLocation()
            return

        try:
            self._grabURLMedia(fetcher, distname, url, arch, distro_info)
        finally:
            fetcher.cleanupLocation()

    def _checkDistroReporting(self, stores, distro_info):
        if distro_info is None:
            return

        dtype, dvariant = distro_info

        for store in stores:
            if not store:
                continue

            t, v = store.os_type, store.os_variant

            if dtype != t or dvariant != v:
                raise RuntimeError("Store distro/variant did not match "
                                   "expected values: %s (%s, %s) != (%s, %s)"
                                   % (store, t, v, dtype, dvariant))

            # Verify the values are valid
            if t:
                testguest.os_type = t
            if v:
                testguest.os_variant = v

    def _grabURLMedia(self, fetcher, distname, url, arch, distro_info=None):

        check_xen = True
        if re.match(r"%s" % NOXEN_FILTER, distname):
            check_xen = False

        hvmstore = self._getStore(fetcher, url, "hvm", arch)

        if check_xen:
            xenstore = self._getStore(fetcher, url, "xen", arch)
        else:
            xenstore = None

        exp_store = distroClass(distname)
        for s in [hvmstore, xenstore]:
            if s and not isinstance(s, exp_store):
                logging.error("(%s): expected store %s, was %s" % \
                              (distname, exp_store, s))
                self.fail()

        # Make sure the stores are reporting correct distro name/variant
        try:
            self._checkDistroReporting([hvmstore, xenstore], distro_info)
        except:
            logging.exception("Distro detection failed.")
            self.fail()

        def fakeAcquireFile(filename, meter):
            if not isinstance(meter, urlgrabber.progress.BaseMeter):
                raise ValueError("passed meter is '%s' not an"
                                 " actual meter." % meter)
            logging.debug("Fake acquiring %s" % filename)
            return fetcher.hasFile(filename)

        # Replace acquireFile with hasFile, so we don't actually have to fetch
        # 1000 kernels
        fetcher.acquireFile = fakeAcquireFile

        # Fetch boot iso
        try:
            if re.match(r"%s" % NOBOOTISO_FILTER, distname):
                logging.debug("Known lack of boot.iso in %s tree. Skipping." \
                              % distname)
            else:
                boot = hvmstore.acquireBootDisk(testguest, fetcher, self.meter)
                logging.debug("acquireBootDisk: %s" % str(boot))

                if boot != True:
                    raise RuntimeError("Didn't fetch any boot iso.")
        except Exception, e:
            logging.exception("%s-%s: bootdisk fetching: %s" %
                              (distname, arch, str(e)))
            self.fail()

        # Fetch regular kernel
        try:
            kern = hvmstore.acquireKernel(testguest, fetcher, self.meter)
            logging.debug("acquireKernel (hvm): %s" % str(kern))

            if kern[0] is not True or kern[1] is not True:
                raise RuntimeError("Didn't fetch any hvm kernel.")
        except Exception, e:
            logging.exception("%s-%s: hvm kernel fetching: %s" %
                              (distname, arch, str(e)))
            self.fail()

        # Fetch xen kernel
        try:
            if xenstore and check_xen:
                kern = xenstore.acquireKernel(testguest, fetcher, self.meter)
                logging.debug("acquireKernel (xen): %s" % str(kern))

                if kern[0] is not True or kern[1] is not True:
                    raise RuntimeError("Didn't fetch any xen kernel.")
            else:
                logging.debug("acquireKernel (xen): Hardcoded skipping.")
        except Exception, e:
            if re.match(r"%s" % EXPECT_XEN_FAIL, distname):
                logging.debug("%s: anticipated xen failure." % distname)
            else:
                logging.exception("%s-%s: xen kernel fetching: %s" %
                                  (distname, arch, str(e)))
                self.fail()

    def _getStore(self, fetcher, url, _type, arch):
        for ignore in range(0, 10):
            try:
                return OSDistro._storeForDistro(fetcher=fetcher, baseuri=url,
                                                progresscb=self.meter,
                                                arch=arch, typ=_type)
            except Exception, e:
                if str(e).count("502"):
                    logging.debug("Caught proxy error: %s" % str(e))
                    time.sleep(.5)
                    continue
                raise
        raise

    def testURLFetch(self):

        if LOCAL_MEDIA:
            logging.debug("Skipping URL tests since local path is specified.")
            return

        keys = urls.keys()
        keys.sort()
        assertions = 0
        for label in keys:
            distro_info = None
            if MATCH_FILTER and not re.match(r"%s" % MATCH_FILTER, label):
                logging.debug("Excluding '%s' from exclude filter." % label)
                continue

            if urls[label].has_key("distro"):
                distro_info = urls[label]["distro"]

            for arch, url in urls[label].items():
                if arch == "distro":
                    continue

                try:
                    print "Testing %s-%s : %s" % (label, arch, url)
                    self._fetchFromURLDict(label, url, arch, distro_info)
                except AssertionError:
                    print "%s-%s FAILED." % (label, arch)
                    assertions += 1

        if assertions != 0:
            raise AssertionError("Found %d errors in URL suite." % assertions)

    def testLocalMedia(self):
        assertions = 0
        if LOCAL_MEDIA:
            for p in LOCAL_MEDIA:
                print "Checking local path: %s" % p
                try:
                    self._fetchLocalMedia(p)
                except Exception, e:
                    logging.exception("Local path '%s' failed: %s" % (p, e))
                    print "Local path FAILED."
                    assertions += 1

        if assertions != 0:
            raise AssertionError("Found %d errors in local fetch tests." %
                                 assertions)
