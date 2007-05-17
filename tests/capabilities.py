import os.path
import unittest
import virtinst.CapabilitiesParser as capabilities

class TestCapabilities(unittest.TestCase):

    def _compareGuest(self, (arch, os_type, hypervisor_type, features), guest):
        self.assertEqual(arch,            guest.arch)
        self.assertEqual(os_type,         guest.os_type)
        self.assertEqual(hypervisor_type, guest.hypervisor_type)
        self.assertEqual(features,        guest.features)

    def _testCapabilities(self, path, (host_arch, host_features), guests):
        caps = capabilities.parse(file(os.path.join("tests", path)).read())

        self.assertEqual(host_arch,     caps.host.arch)
        self.assertEqual(host_features, caps.host.features)

        map(self._compareGuest, guests, caps.guests)

    def testCapabilities1(self):
        host = ( 'x86_64', capabilities.FEATURE_VMX )

        guests = [
            ( 'x86_64', 'xen', 'xen', 0 ),
            ( 'i686',   'xen', 'xen', capabilities.FEATURE_PAE ),
            ( 'i686',   'hvm', 'xen', capabilities.FEATURE_PAE|capabilities.FEATURE_NONPAE ),
            ( 'x86_64', 'hvm', 'xen', 0 )
        ]

        self._testCapabilities("capabilities-xen.xml", host, guests)

    def testCapabilities2(self):
        host = ( 'x86_64', 0 )

        guests = [
            ( 'x86_64', 'hvm', 'qemu', 0 ),
            ( 'i686',   'hvm', 'qemu', 0 ),
            ( 'mips',   'hvm', 'qemu', 0 ),
            ( 'mipsel', 'hvm', 'qemu', 0 ),
            ( 'sparc',  'hvm', 'qemu', 0 ),
            ( 'ppc',    'hvm', 'qemu', 0 ),
        ]

        self._testCapabilities("capabilities-qemu.xml", host, guests)

    def testCapabilities3(self):
        host = ( 'i686', capabilities.FEATURE_PAE|capabilities.FEATURE_NONPAE )

        guests = [
            ( 'i686', 'linux', 'test', capabilities.FEATURE_PAE|capabilities.FEATURE_NONPAE ),
        ]

        self._testCapabilities("capabilities-test.xml", host, guests)

if __name__ == "__main__":
    unittest.main()
