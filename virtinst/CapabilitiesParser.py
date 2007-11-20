#!/usr/bin/python -tt

# Some code for parsing libvirt's capabilities XML
#
# Copyright 2007  Red Hat, Inc.
# Mark McLoughlin <markmc@redhat.com>
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

import libxml2
from virtinst import _virtinst as _

class CapabilitiesParserException(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg)

# Whether a guest can be created with a certain feature on resp. off
FEATURE_ON      = 0x01
FEATURE_OFF     = 0x02

class Features(object):
    """Represent a set of features. For each feature, store a bit mask of
       FEATURE_ON and FEATURE_OFF to indicate whether the feature can
       be turned on or off. For features for which toggling doesn't make sense
       (e.g., 'vmx') store FEATURE_ON when the feature is present."""

    def __init__(self, node = None):
        self.features = {}
        if node is not None:
            self.parseXML(node)

    def __getitem__(self, feature):
        if self.features.has_key(feature):
            return self.features[feature]
        return 0

    def names(self):
        return self.features.keys()

    def parseXML(self, node):
        d = self.features
        for n in node.xpathEval("*"):
            feature = n.name
            if not d.has_key(feature):
                d[feature] = 0

            self._extractFeature(feature, d, n)

    def _extractFeature(self, feature, dict, node):
        """Extract the value of FEATURE from NODE and set DICT[FEATURE] to
        its value. Abstract method, must be overridden"""
        raise NotImplementedError("Abstract base class")

class CapabilityFeatures(Features):
    def __init__(self, node = None):
        Features.__init__(self, node)

    def _extractFeature(self, feature, d, n):
        default = xpathString(n, "@default")
        toggle = xpathString(n, "@toggle")

        if default is not None:
            if default == "on":
                d[feature] = FEATURE_ON
            elif default == "off":
                d[feature] = FEATURE_OFF
            else:
                raise CapabilitiesParserException("Feature %s: value of default must be 'on' or 'off', but is '%s'" % (feature, default))
            if toggle == "yes":
                d[feature] |= d[feature] ^ (FEATURE_ON|FEATURE_OFF)
        else:
            if feature == "nonpae":
                d["pae"] |= FEATURE_OFF
            else:
                d[feature] |= FEATURE_ON

class Host(object):
    def __init__(self, node = None):
        # e.g. "i686" or "x86_64"
        self.arch = None

        self.features = CapabilityFeatures()

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
                    self.features = CapabilityFeatures(n)
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

        self.features = CapabilityFeatures()

        if not node is None:
            self.parseXML(node)

    def parseXML(self, node):
        child = node.children
        while child:
            if child.name == "os_type":
                self.os_type = child.content
            elif child.name == "features":
                self.features = CapabilityFeatures(child)
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
            raise CapabilitiesParserException("Root element is not 'capabilities'")

        capabilities = Capabilities(root)
    finally:
        doc.freeDoc()

    return capabilities

def xpathString(node, path, default = None):
    result = node.xpathEval("string(%s)" % path)
    if len(result) == 0:
        result = default
    return result
