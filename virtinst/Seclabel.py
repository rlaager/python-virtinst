#
# Copyright 2010  Red Hat, Inc.
# Cole Robinson <crobinso@redhat.com>
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

import XMLBuilderDomain
from XMLBuilderDomain import _xml_property

class Seclabel(XMLBuilderDomain.XMLBuilderDomain):
    """
    Class for generating <seclabel> XML
    """

    SECLABEL_TYPE_DYNAMIC = "dynamic"
    SECLABEL_TYPE_STATIC = "static"
    SECLABEL_TYPES = [SECLABEL_TYPE_DYNAMIC, SECLABEL_TYPE_STATIC]

    def __init__(self, conn, parsexml=None, parsexmlnode=None):
        XMLBuilderDomain.XMLBuilderDomain.__init__(self, conn, parsexml,
                                                   parsexmlnode)

        self._type = None
        self._model = None
        self._label = None
        self._imagelabel = None

        if self._is_parse():
            return

        model = self._get_caps().host.secmodel.model
        if not model:
            raise ValueError("Hypervisor does not have any security driver"
                             "enabled")
        self.model = model
        self.type = self.SECLABEL_TYPE_DYNAMIC

    def get_type(self):
        return self._type
    def set_type(self, val):
        if val not in self.SECLABEL_TYPES:
            raise ValueError("Unknown security type '%s'" % val)
        self._type = val
    type = _xml_property(get_type, set_type,
                         xpath="./@type")

    def get_model(self):
        return self._model
    def set_model(self, val):
        self._model = val
    model = _xml_property(get_model, set_model,
                          xpath="./@model")

    def get_label(self):
        return self._label
    def set_label(self, val):
        self._label = val
    label = _xml_property(get_label, set_label,
                          xpath="./label")

    def get_imagelabel(self):
        return self._imagelabel
    def set_imagelabel(self, val):
        self._imagelabel = val
    imagelabel = _xml_property(get_imagelabel, set_imagelabel,
                               xpath="./imagelabel")

    def _get_xml_config(self):
        if not self.type or not self.model:
            raise RuntimeError("Security type and model must be specified")

        if (self.type == self.SECLABEL_TYPE_STATIC and not self.label):
            raise RuntimeError("A label must be specified for static "
                               "security type.")

        label_xml = ""
        xml = "  <seclabel type='%s' model='%s'" % (self.type, self.model)

        if self.label:
            label_xml += "    <label>%s</label>\n" % self.label
        if self.imagelabel:
            label_xml += "    <imagelabel>%s</imagelabel>\n" % self.imagelabel

        if label_xml:
            xml += ">\n"
            xml += label_xml
            xml += "  </seclabel>"
        else:
            xml += "/>"


        return xml
