#!/usr/bin/python -tt

# Some code for parsing libvirt's capabilities XML
#
# Copyright 2007  Red Hat, Inc.
# Mark McLoughlin <markmc@redhat.com>
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import libxml2

class CapabilitiesParserException(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg)

FEATURE_ACPI    = 0x01
FEATURE_APIC    = 0x02
FEATURE_PAE     = 0x04
FEATURE_NONPAE  = 0x08
FEATURE_VMX     = 0x10
FEATURE_SVM     = 0x20
FEATURE_IA64_BE = 0x40

features_map = {
    "acpi"    : FEATURE_ACPI,
    "apic"    : FEATURE_APIC,
    "pae"     : FEATURE_PAE,
    "nonpae"  : FEATURE_NONPAE,
    "vmx"     : FEATURE_VMX,
    "svm"     : FEATURE_SVM,
    "ia64_be" : FEATURE_IA64_BE
}

NUM_FEATURES = len(features_map)

def _parse_features(self, node):
    features = 0

    child = node.children
    while child:
        if child.name in features_map:
            features |= features_map[child.name]

        child = child.next

    return features

class Host(object):
    def __init__(self, node = None):
        # e.g. "i686" or "x86_64"
        self.arch = None

        # e.g. FEATURE_HVM|FEATURE_ACPI
        self.features = 0

        if not node is None:
            self.parseXML(node)

    def parseXML(self, node):
        child = node.children
        while child:
            if child.name != "cpu":
                child = child.next
                continue

            n = child.children
            while n:
                if n.name == "arch":
                    self.arch = n.content
                elif n.name == "features":
                    self.features |= _parse_features(self, n)
                n = n.next

            child = child.next

class Guest(object):
    def __init__(self, node = None):
        # e.g. "xen" or "hvm"
        self.os_type = None

        # e.g. "xen", "qemu", "kqemu" or "kvm"
        self.hypervisor_type = None

        # e.g. "i686" or "x86_64"
        self.arch = None

        # e.g. FEATURE_HVM|FEATURE_ACPI
        self.features = 0

        if not node is None:
            self.parseXML(node)

    def parseXML(self, node):
        child = node.children
        while child:
            if child.name == "os_type":
                self.os_type = child.content
            elif child.name == "features":
                self.features |= _parse_features(self, child)
            elif child.name == "arch":
                self.arch = child.prop("name")
                n = child.children
                while n:
                    # NB. for now, ignoring the rest of arch e.g. wordsize etc.
                    if n.name == "domain":
                        self.hypervisor_type = n.prop("type")
                    n = n.next

            child = child.next

class Capabilities(object):
    def __init__(self, node = None):
        self.host = None
        self.guests = []

        if not node is None:
            self.parseXML(node)

    def parseXML(self, node):
        child = node.children
        while child:
            if child.name == "host":
                self.host = Host(child)
            elif child.name == "guest":
                self.guests.append(Guest(child))
            child = child.next

def parse(xml):
    class ErrorHandler:
        def __init__(self):
            self.msg = ""
        def handler(self, ctx, str):
            self.msg += str
    error = ErrorHandler()
    libxml2.registerErrorHandler(error.handler, None)

    try:
        # try/except/finally is only available in python-2.5
        try:
            doc = libxml2.readMemory(xml, len(xml),
                                     None, None,
                                     libxml2.XML_PARSE_NOBLANKS)
        except (libxml2.parserError, libxml2.treeError), e:
            raise CapabilitiesParserException("%s\n%s" % (e, error.msg))
    finally:
        libxml2.registerErrorHandler(None, None)

    try:
        root = doc.getRootElement()
        if root.name != "capabilities":
            raise CapabilitiesParserException("Root element is not 'capabilties'")

        capabilities = Capabilities(root)
    finally:
        doc.freeDoc()

    return capabilities
