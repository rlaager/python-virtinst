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

import difflib
import os
import logging

import libvirt
import virtinst.cli

# Used to ensure consistent SDL xml output
os.environ["HOME"] = "/tmp"
os.environ["DISPLAY"] = ":3.4"

_cwd        = os.getcwd()
_testuri    = "test:///%s/tests/testdriver.xml" % _cwd
_fakeuri    = "__virtinst_test__" + _testuri + ",predictable"
_kvmcaps    = "%s/tests/capabilities-xml/libvirt-0.7.6-qemu-caps.xml" % _cwd
_kvmuri     = "%s,caps=%s,qemu" % (_fakeuri, _kvmcaps)

def get_debug():
    return ("DEBUG_TESTS" in os.environ and
            os.environ["DEBUG_TESTS"] == "1")

def open_testdriver():
    return virtinst.cli.getConnection(_testuri)

def open_testkvmdriver():
    return virtinst.cli.getConnection(_kvmuri)

# Register libvirt handler
def libvirt_callback(ignore, err):
    logging.warn("libvirt errmsg: %s" % err[2])
libvirt.registerErrorHandler(f=libvirt_callback, ctx=None)

def sanitize_xml_for_define(xml):
    # Libvirt throws errors since we are defining domain
    # type='xen', when test driver can only handle type='test'
    # Sanitize the XML so we can define
    if not xml:
        return xml

    xml = xml.replace("<domain type='xen'>",
                      "<domain type='test'>")
    xml = xml.replace(">linux<", ">xen<")

    return xml

def test_create(testconn, xml):
    xml = sanitize_xml_for_define(xml)

    try:
        dom = testconn.defineXML(xml)
    except Exception, e:
        raise RuntimeError(str(e) + "\n" + xml)

    try:
        dom.create()
        dom.destroy()
        dom.undefine()
    except:
        try:
            dom.destroy()
        except:
            pass
        try:
            dom.undefine()
        except:
            pass

def read_file(filename):
    """Helper function to read a files contents and return them"""
    f = open(filename, "r")
    out = f.read()
    f.close()

    return out

def diff_compare(actual_out, filename=None, expect_out=None):
    """Compare passed string output to contents of filename"""
    if not expect_out:
        expect_out = read_file(filename)

    diff = "".join(difflib.unified_diff(expect_out.splitlines(1),
                                        actual_out.splitlines(1),
                                        fromfile=filename,
                                        tofile="Generated Output"))
    if diff:
        raise AssertionError("Conversion outputs did not match.\n%s" % diff)
