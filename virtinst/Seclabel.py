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
    SECLABEL_TYPE_DEFAULT = "default"
    SECLABEL_TYPES = [SECLABEL_TYPE_DYNAMIC, SECLABEL_TYPE_STATIC]

    MODEL_DEFAULT = "default"

    _dumpxml_xpath = "/domain/seclabel"
    def __init__(self, conn, parsexml=None, parsexmlnode=None, caps=None):
        XMLBuilderDomain.XMLBuilderDomain.__init__(self, conn, parsexml,
                                                   parsexmlnode, caps)

        self._type = None
        self._model = None
        self._label = None
        self._imagelabel = None
        self._relabel = None

        if self._is_parse():
            return

        self.model = self.MODEL_DEFAULT
        self.type = self.SECLABEL_TYPE_DEFAULT

    def _get_default_model(self):
        return self._get_caps().host.secmodel.model

    def get_type(self):
        return self._type
    def set_type(self, val):
        if (val not in self.SECLABEL_TYPES and
            val != self.SECLABEL_TYPE_DEFAULT):
            raise ValueError("Unknown security type '%s'" % val)
        self._type = val
    type = _xml_property(get_type, set_type,
                         xpath="./seclabel/@type")

    def get_model(self):
        return self._model
    def set_model(self, val):
        self._model = val
    model = _xml_property(get_model, set_model,
                          xpath="./seclabel/@model",
                          default_converter=_get_default_model)

    def get_label(self):
        return self._label
    def set_label(self, val):
        self._label = val
    label = _xml_property(get_label, set_label,
                          xpath="./seclabel/label")

    def _get_relabel(self):
        return self._relabel
    def _set_relabel(self, val):
        self._relabel = val
    relabel = _xml_property(_get_relabel, _set_relabel,
                            xpath="./seclabel/@relabel")

    def get_imagelabel(self):
        return self._imagelabel
    def set_imagelabel(self, val):
        self._imagelabel = val
    imagelabel = _xml_property(get_imagelabel, set_imagelabel,
                               xpath="./seclabel/imagelabel")

    def _get_xml_config(self):
        if (self.model == self.MODEL_DEFAULT and
            self.type == self.SECLABEL_TYPE_DEFAULT):
            return ""

        model = self.model
        typ = self.type
        relabel = self.relabel

        if model == self.MODEL_DEFAULT:
            model = self._get_default_model()
        if typ == self.SECLABEL_TYPE_DEFAULT:
            typ = self.SECLABEL_TYPE_DYNAMIC

        if not typ:
            raise RuntimeError("Security type and model must be specified")

        if typ == self.SECLABEL_TYPE_STATIC:
            if not self.label:
                raise RuntimeError("A label must be specified for static "
                                   "security type.")


        label_xml = ""
        xml = "  <seclabel type='%s' model='%s'" % (typ, model)
        if relabel is not None:
            xml += " relabel='%s'" % (relabel and "yes" or "no")

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
