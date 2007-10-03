import virtinst
import unittest
import traceback

# Template for adding arguments to test
#      { 'label'    : { 'VAR'       : { 'invalid' : [param],\
#                                       'valid'   : [param]},\
#                       '__init__'  : { 'invalid' : [{'initparam':val}],\
#                                       'valid'   : [{'initparam':val}]}\

args = { 'guest'    : { \
                        'name'      : { 'invalid' : ['123456789', 'im_invalid!', '', 0, 'verylongnameverylongnameverylongnameverylongnameveryvery'], \
                                        'valid'   : ['Valid_name.01'] }, \
                        'memory'    : { 'invalid' : [-1, 0, ''], \
                                        'valid'   : [200, 2000] }, \
                        'maxmemory' : { 'invalid' : [-1, 0, ''], \
                                        'valid'   : [200, 2000], }, \
                        'uuid'      : { 'invalid' : [ '', 0, '1234567812345678123456781234567x'], \
                                        'valid'   : ['12345678123456781234567812345678','12345678-1234-1234-ABCD-ABCDEF123456']}, \
                        'vcpus'     : { 'invalid' : [-1, 0, 1000, ''], \
                                        'valid'   : [ 1, 32 ] }, \
                        'graphics'  : { 'invalid' : ['', True, 'unknown', {},\
('', '', '', 0), ('','','', 'longerthan16chars'), ('','','','invalid!!ch@r'),\
                                                    {}], \
                                        'valid'   : [False, 'sdl', 'vnc', \
                                                    (True, 'sdl', '',\
                                                    'key_map-2'),\
                                                    {'enabled' : True, \
                                                     'type':'vnc', 'opts':'o'}\
                                                    ]},\
                        'type'      : { 'invalid' : [], \
                                        'valid'   : ['sometype'] }, \
                        'cdrom'     : { 'invalid' : ['', 0, '/somepath'],\
                                        'valid'   : ['/dev/root']}\
                      },\
         'fvguest'  : { \
                        'os_type'   : { 'invalid' : ['notpresent',0,''],\
                                        'valid'   : ['other', 'windows',\
                                                     'unix', 'linux']}, \
                        'os_variant': { 'invalid' : ['', 0, 'invalid'], \
                                        'valid'   : ['rhel5', \
                                                     'sles10']}, \
                      },\
         'disk'     : { \
                        '__init__'  : { 'invalid' : [{ 'path' : 0},\
                                                     { 'path' : '/root' },\
                                                     { 'path' : 'valid',
                                                       'size' : None },\
                                                     { 'path' : "valid", \
                                                       'size' : 'invalid'},\
                                                     { 'path' : 'valid', \
                                                       'size' : -1},\
                                                     { 'path' : 'notblock',\
                                                       'type' : virtinst.VirtualDisk.TYPE_BLOCK},\
                                                     { 'path' :'/dev/null',\
                                                       'type' : virtinst.VirtualDisk.TYPE_BLOCK},
                                                     { 'path' : None}],\
                                        'valid'   : [{ 'path' : '/dev/root'},\
                                                     { 'path' : 'nonexist', \
                                                       'size' : 10}, \
                                                     { 'path' :'/dev/null'},
                                                     { 'path' : None,
                                                       'device' : virtinst.VirtualDisk.DEVICE_CDROM},
                                                     { 'path' : None,
                                                       'device' : virtinst.VirtualDisk.DEVICE_FLOPPY}]}\
                      },\
         'installer' : { \
                        'boot'      : { 'invalid' : ['', 0, ('1element'),\
                                                     ['1el', '2el', '3el'],\
                                                     {'1element': '1val'},\
                                                     {'kernel' : 'a',\
                                                      'wronglabel' : 'b'}],\
                                        'valid'   : [('kern', 'init'),\
                                                     ['kern', 'init'],\
                                                     { 'kernel' : 'a',\
                                                       'initrd' : 'b'}]}, \
                        'extraargs' : { 'invalid' : [], \
                                        'valid'   : ['someargs']}, \
                             },\
         'distroinstaller' : { \
                        'location'  : { 'invalid' : ['nogood', \
                                                     'http:/nogood'],\
                                        'valid'   : ['/file',\
                                                     'http://web',\
                                                     'ftp://ftp',\
                                                     'nfs:nfsserv']}\
                             },\
         'network'   : { \
                        '__init__'  : { 'invalid' : [{'macaddr':0}, \
                                                     {'macaddr':''},\
                                                     {'macaddr':'$%XD'}, \
                                                     {'type':'network'}, \
                                                     {'type':'network', \
                                                      'bridge':'somebridge'},\
                                                     {'network':'somenet'}, \
                                                     {'type':'user',\
                                                      'network':'somenet'},\
                                                     {'type':'user',\
                                                      'bridge':'somebridge'},\
                                                     {'type':'unknowntype'}],\
                                        'valid'   : []}, \
                     },\
         'clonedesign' : {\
                        'original_guest' :{\
                                        'invalid' : ['', 0, 'invalid_name&',\
                                        '123456781234567812345678123456789'],\
                                        'valid'   : ['some.valid-name_9', \
                                        '12345678123456781234567812345678']},\
                        'clone_name': { 'invalid' : [0],
                                        'valid'   : ['some.valid-name_9']},
                        'clone_uuid': { 'invalid' : [0],
                                        'valid'   :
                                        ['12345678123456781234567812345678']},\
                        'clone_mac' : { 'invalid' : ['badformat'],
                                        'valid'   : ['AA:BB:CC:DD:EE:FF']},\
                        'clone_bs'  : { 'invalid' : [],
                                        'valid'   : ['valid']}}\
       }

class TestValidation(unittest.TestCase):


    guest = virtinst.Guest(hypervisorURI="test:///default", type="xen")

    def _testArgs(self, object, testclass, name):
        """@object Object to test parameters against
           @testclass Full class to test initialization against
           @name String name indexing args"""
        for paramname in args[name]:
            for val in args[name][paramname]['invalid']:

                try:
                    if paramname is '__init__':
                        testclass(*(), **val)                    
                    else:
                        setattr(object, paramname, val)
                    msg = "Expected TypeError or ValueError: None raised.\n"
                    msg += "For '%s' object, paramname '%s', val '%s':" % \
                        (name, paramname, val)
                    raise AssertionError, msg
                except AssertionError, e:
                    raise e
                except ValueError:
                    pass
                except Exception, e:
                    msg = "Unexpected exception raised: %s\n" % e
                    msg += "Original traceback was: \n%s\n" % \
                           traceback.format_exc()
                    msg += "For '%s' object, paramname '%s', val '%s':" % \
                        (name, paramname, val)
                    raise AssertionError, msg
                
            for val in args[name][paramname]['valid']:
                try:
                    if paramname is '__init__':
                        testclass(*(), **val)                    
                    else:
                        setattr(object, paramname, val)
                except Exception, e:
                    msg = "Validation case failed, expected success.\n"
                    msg +="Exception received was: %s\n" % e
                    msg += "Original traceback was: \n%s\n" % \
                           traceback.format_exc()
                    msg += "For '%s' object, paramname '%s', val '%s':" % \
                        (name, paramname, val)
                    raise AssertionError, msg

    # Actual Tests

    def testGuestValidation(self):
        PVGuest = virtinst.ParaVirtGuest(hypervisorURI="test:///default",\
                                         type="xen")
        self._testArgs(PVGuest, virtinst.Guest, 'guest')

    def testDiskValidation(self):
        disk = virtinst.VirtualDisk("/dev/root")
        self._testArgs(disk, virtinst.VirtualDisk, 'disk')

    def testFVGuestValidation(self):
        FVGuest = virtinst.FullVirtGuest(hypervisorURI="test:///default",\
                                         type="xen")
        self._testArgs(FVGuest, virtinst.FullVirtGuest, 'fvguest')

    def testNetworkValidation(self):
        network = virtinst.VirtualNetworkInterface()
        self._testArgs(network, virtinst.VirtualNetworkInterface, 'network')

        # Test MAC Address collision
        hostmac = virtinst.util.get_host_network_devices()
        if len(hostmac) is not 0:
            hostmac = hostmac[0][4]

        for params in ({'macaddr' : hostmac},):
            network = virtinst.VirtualNetworkInterface(*(), **params)
            self.assertRaises(RuntimeError, network.setup, \
                              self.guest.conn)
        
        # Test dynamic MAC/Bridge success
        try:
            network = virtinst.VirtualNetworkInterface()
            network.setup(self.guest.conn)
        except Exception, e:
            raise AssertionError, \
                "Network setup with no params failed, expected success."

    def testDistroInstaller(self):
       dinstall = virtinst.DistroInstaller()
       self._testArgs(dinstall, virtinst.DistroInstaller, 'installer')
       self._testArgs(dinstall, virtinst.DistroInstaller, 'distroinstaller')

    def testCloneManager(self):
        cman = virtinst.CloneManager.CloneDesign(self.guest.conn)
        self._testArgs(cman, virtinst.CloneManager.CloneDesign, 'clonedesign')
    

if __name__ == "__main__":
    unittest.main()
