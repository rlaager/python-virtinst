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

import commands
import os
import sys

import utils

os.environ["VIRTCONV_TEST_NO_DISK_CONVERSION"] = "1"
os.environ["LANG"] = "en_US.UTF-8"

testuri = "test:///`pwd`/tests/testdriver.xml"

# There is a hack in virtinst/cli.py to find this magic string and
# convince virtinst we are using a remote connection.
fakeuri     = "__virtinst_test__" + testuri + ",predictable"
remoteuri   = fakeuri + ",remote"
kvmuri      = fakeuri + ",caps=`pwd`/tests/capabilities-xml/libvirt-0.7.6-qemu-caps.xml,qemu"
xenuri      = fakeuri + ",caps=`pwd`/tests/capabilities-xml/rhel5.4-xen-caps-virt-enabled.xml,xen"
xenia64uri  = fakeuri + ",caps=`pwd`/tests/capabilities-xml/xen-ia64-hvm.xml,xen"

# Location
image_prefix = "/tmp/__virtinst_cli_"
xmldir = "tests/cli-test-xml"
treedir = "%s/faketree" % xmldir
vcdir = "%s/virtconv" % xmldir
ro_dir = image_prefix + "clitest_rodir"
ro_img = "%s/cli_exist3ro.img" % ro_dir
ro_noexist_img = "%s/idontexist.img" % ro_dir
compare_xmldir = "%s/compare" % xmldir
virtconv_out = "/tmp/__virtinst_tests__virtconv-outdir"

# Images that will be created by virt-install/virt-clone, and removed before
# each run
new_images = [
    image_prefix + "new1.img",
    image_prefix + "new2.img",
    image_prefix + "new3.img",
    image_prefix + "exist1-clone.img",
    image_prefix + "exist2-clone.img",
]

# Images that are expected to exist before a command is run
exist_images = [
    image_prefix + "exist1.img",
    image_prefix + "exist2.img",
    ro_img,
]

# Images that need to exist ahead of time for virt-image
virtimage_exist = ["/tmp/__virtinst__cli_root.raw"]

# Images created by virt-image
virtimage_new = ["/tmp/__virtinst__cli_scratch.raw"]

# virt-convert output dirs
virtconv_dirs = [virtconv_out]

exist_files = exist_images + virtimage_exist
new_files   = new_images + virtimage_new + virtconv_dirs
clean_files = (new_images + exist_images +
               virtimage_exist + virtimage_new + virtconv_dirs + [ro_dir])

test_files = {
    'TESTURI'           : testuri,
    'REMOTEURI'         : remoteuri,
    'KVMURI'            : kvmuri,
    'XENURI'            : xenuri,
    'XENIA64URI'        : xenia64uri,
    'CLONE_DISK_XML'    : "%s/clone-disk.xml" % xmldir,
    'CLONE_STORAGE_XML' : "%s/clone-disk-managed.xml" % xmldir,
    'CLONE_NOEXIST_XML' : "%s/clone-disk-noexist.xml" % xmldir,
    'IMAGE_XML'         : "%s/image.xml" % xmldir,
    'NEWIMG1'           : new_images[0],
    'NEWIMG2'           : new_images[1],
    'NEWIMG3'           : new_images[2],
    'EXISTIMG1'         : exist_images[0],
    'EXISTIMG2'         : exist_images[1],
    'ROIMG'             : ro_img,
    'ROIMGNOEXIST'      : ro_noexist_img,
    'POOL'              : "default-pool",
    'VOL'               : "testvol1.img",
    'DIR'               : os.getcwd(),
    'TREEDIR'           : treedir,
    'MANAGEDEXIST1'     : "/default-pool/testvol1.img",
    'MANAGEDEXIST2'     : "/default-pool/testvol2.img",
    'MANAGEDNEW1'       : "/default-pool/clonevol",
    'MANAGEDNEW2'       : "/default-pool/clonevol",
    'MANAGEDDISKNEW1'   : "/disk-pool/newvol1.img",
    'COLLIDE'           : "/default-pool/collidevol1.img",
    'SHARE'             : "/default-pool/sharevol.img",

    'VIRTCONV_OUT'      : "%s/test.out" % virtconv_out,
    'VC_IMG1'           : "%s/virtimage/test1.virt-image" % vcdir,
    'VC_IMG2'           : "tests/image-xml/image-format.xml",
    'VMX_IMG1'          : "%s/vmx/test1.vmx" % vcdir,
}

debug = False
testprompt = False

"""
CLI test matrix

Format:

"appname" {
  "globalargs" : Arguments to be passed to every app invocation

  "categoryfoo" : { Some descriptive test catagory name (e.g. storage)

    "args" : Args to be applied to all invocations in category

    "valid" : { # Argument strings that should succeed
      "--option --string --number1" # Some option string to test. The
          resulting cmdstr would be:
          $ appname globalargs categoryfoo_args --option --string --number1
    }

    "invalid" : { # Argument strings that should fail
      "--opt1 --opt2",
    }
  } # End categoryfoo

  "prompt" : { # Special category that will launch an interactive command.
               # which is only run if special args are passed to the test
    "--some --prompt --command --string"
  }
}
  "
"""
args_dict = {


  "virt-install" : {
    "globalargs" : " --connect %(TESTURI)s -d --name foobar --ram 64",

    "storage" : {
      "args": "--pxe --nographics --noautoconsole --hvm",

      "valid"  : [
        # Existing file, other opts
        "--file %(EXISTIMG1)s --nonsparse --file-size 4",
        # Existing file, no opts
        "--file %(EXISTIMG1)s",
        # Multiple existing files
        "--file %(EXISTIMG1)s --file virt-image --file virt-clone",
        # Nonexistent file
        "--file %(NEWIMG1)s --file-size .00001 --nonsparse",

        # Existing disk, lots of opts
        "--disk path=%(EXISTIMG1)s,perms=ro,size=.0001,cache=writethrough,io=threads",
        # Existing disk, rw perms
        "--disk path=%(EXISTIMG1)s,perms=rw",
        # Existing floppy
        "--disk path=%(EXISTIMG1)s,device=floppy",
        # Existing disk, no extra options
        "--disk path=%(EXISTIMG1)s",
        # Create volume in a pool
        "--disk pool=%(POOL)s,size=.0001",
        # Existing volume
        "--disk vol=%(POOL)s/%(VOL)s",
        # 3 IDE and CD
        "--disk path=%(EXISTIMG1)s --disk path=%(EXISTIMG1)s --disk path=%(EXISTIMG1)s --disk path=%(EXISTIMG1)s,device=cdrom",
        # > 16 scsi disks
        " --disk path=%(EXISTIMG1)s,bus=scsi --disk path=%(EXISTIMG1)s,bus=scsi --disk path=%(EXISTIMG1)s,bus=scsi --disk path=%(EXISTIMG1)s,bus=scsi --disk path=%(EXISTIMG1)s,bus=scsi --disk path=%(EXISTIMG1)s,bus=scsi --disk path=%(EXISTIMG1)s,bus=scsi --disk path=%(EXISTIMG1)s,bus=scsi --disk path=%(EXISTIMG1)s,bus=scsi --disk path=%(EXISTIMG1)s,bus=scsi --disk path=%(EXISTIMG1)s,bus=scsi --disk path=%(EXISTIMG1)s,bus=scsi --disk path=%(EXISTIMG1)s,bus=scsi --disk path=%(EXISTIMG1)s,bus=scsi --disk path=%(EXISTIMG1)s,bus=scsi --disk path=%(EXISTIMG1)s,bus=scsi --disk path=%(EXISTIMG1)s,bus=scsi",
        # Unmanaged file using format 'raw'
        "--disk path=%(NEWIMG1)s,format=raw,size=.0000001",
        # Managed file using format raw
        "--disk path=%(MANAGEDNEW1)s,format=raw,size=.0000001",
        # Managed file using format qcow2
        "--disk path=%(MANAGEDNEW1)s,format=qcow2,size=.0000001",
        # Using ro path as a disk with readonly flag
        "--disk path=%(ROIMG)s,perms=ro",
        # Using RO path with cdrom dev
        "--disk path=%(ROIMG)s,device=cdrom",
        # Not specifying path=
        "--disk %(EXISTIMG1)s",
        # Not specifying path= but creating storage
        "--disk %(NEWIMG1)s,format=raw,size=.0000001",
        # Colliding storage with --force
        "--disk %(COLLIDE)s --force",
        # Colliding shareable storage
        "--disk %(SHARE)s,perms=sh",
        # Two IDE cds
        "--disk path=%(EXISTIMG1)s,device=cdrom --disk path=%(EXISTIMG1)s,device=cdrom",
        # Dir with a floppy dev
        "--disk %(DIR)s,device=floppy",
        # Driver name and type options
        "--disk %(EXISTIMG1)s,driver_name=qemu,driver_type=qcow2",
        # Unknown driver name and type options
        "--disk %(EXISTIMG1)s,driver_name=foobar,driver_type=foobaz",
        # Using a storage pool source as a disk
        "--disk /dev/hda",
      ],

      "invalid": [
        # Nonexisting file, size too big
        "--file %(NEWIMG1)s --file-size 100000 --nonsparse",
        # Huge file, sparse, but no prompting
        "--file %(NEWIMG1)s --file-size 100000",
        # Nonexisting file, no size
        "--file %(NEWIMG1)s",
        # Too many IDE
        "--file %(EXISTIMG1)s --file %(EXISTIMG1)s --file %(EXISTIMG1)s --file %(EXISTIMG1)s --file %(EXISTIMG1)s",
        # Size, no file
        "--file-size .0001",
        # Specify a nonexistent pool
        "--disk pool=foopool,size=.0001",
        # Specify a nonexistent volume
        "--disk vol=%(POOL)s/foovol",
        # Specify a pool with no size
        "--disk pool=%(POOL)s",
        # Unknown cache type
        "--disk path=%(EXISTIMG1)s,perms=ro,size=.0001,cache=FOOBAR",
        # Unmanaged file using non-raw format
        "--disk path=%(NEWIMG1)s,format=qcow2,size=.0000001",
        # Managed file using unknown format
        "--disk path=%(MANAGEDNEW1)s,format=frob,size=.0000001",
        # Managed disk using any format
        "--disk path=%(MANAGEDDISKNEW1)s,format=raw,size=.0000001",
        # Not specifying path= and non existent storage w/ no size
        "--disk %(NEWIMG1)s",
        # Colliding storage without --force
        "--disk %(COLLIDE)s",
        # Dir without floppy
        "--disk %(DIR)s,device=cdrom",
      ]
     }, # category "storage"

     "install" : {
      "args": "--nographics --noautoconsole --nodisks",

      "valid" : [
        # Simple cdrom install
        "--hvm --cdrom %(EXISTIMG1)s",
        # Cdrom install with managed storage
        "--hvm --cdrom %(MANAGEDEXIST1)s",
        # Windows (2 stage) install
        "--hvm --wait 0 --os-variant winxp --cdrom %(EXISTIMG1)s",
        # Explicit virt-type
        "--hvm --pxe --virt-type test",
        # Explicity fullvirt + arch
        "--arch i686 --pxe",
        # Convert i*86 -> i686
        "--arch i486 --pxe",
        # Directory tree URL install
        "--hvm --location %(TREEDIR)s",
        # Directory tree URL install with extra-args
        "--hvm --location %(TREEDIR)s --extra-args console=ttyS0",
        # Directory tree CDROM install
        "--hvm --cdrom %(TREEDIR)s",
        # Paravirt location
        "--paravirt --location %(TREEDIR)s",
        # Using ro path as a cd media
        "--hvm --cdrom %(ROIMG)s",
        # Paravirt location with --os-variant none
        "--paravirt --location %(TREEDIR)s --os-variant none",
        # URL install with manual os-variant
        "--hvm --location %(TREEDIR)s --os-variant fedora12",
        # Boot menu
        "--hvm --pxe --boot menu=on",
        # Kernel params
        """--hvm --pxe --boot kernel=/tmp/foo1.img,initrd=/tmp/foo2.img,kernel_args="ro quiet console=/dev/ttyS0" """,
        # Boot order
        "--hvm --pxe --boot cdrom,fd,hd,network,menu=off",
        # Boot w/o other install option
        "--hvm --boot network,hd,menu=on",
      ],

      "invalid": [
        # Bogus virt-type
        "--hvm --pxe --virt-type bogus",
        # Bogus arch
        "--hvm --pxe --arch bogus",
        # PXE w/ paravirt
        "--paravirt --pxe",
        # Import with no disks
        "--import",
        # LiveCD with no media
        "--livecd",
        # Bogus --os-variant
        "--hvm --pxe --os-variant farrrrrrrge"
        # Boot menu w/ bogus value
        "--hvm --pxe --boot menu=foobar",
        # cdrom fail w/ extra-args
        "--hvm --cdrom %(EXISTIMG1)s --extra-args console=ttyS0",
      ],
     }, # category "install"

     "graphics": {
      "args": "--noautoconsole --nodisks --pxe",

      "valid": [
        # SDL
        "--sdl",
        # --graphics SDL
        "--graphics sdl",
        # --graphics none,
        "--graphics none",
        # VNC w/ lots of options
        "--vnc --keymap ja --vncport 5950 --vnclisten 1.2.3.4",
        # VNC w/ lots of options, new way
        "--graphics vnc,port=5950,listen=1.2.3.4,keymap=ja,password=foo",
        # SPICE w/ lots of options
        "--graphics spice,port=5950,tlsport=5950,listen=1.2.3.4,keymap=ja",
        # --video option
        "--vnc --video vga",
        # --video option
        "--graphics spice --video qxl",
        # --keymap local,
        "--vnc --keymap local",
        # --keymap none
        "--vnc --keymap none",
      ],

      "invalid": [
        # Invalid keymap
        "--vnc --keymap ZZZ",
        # Invalid port
        "--vnc --vncport -50",
        # Invalid port
        "--graphics spice,tlsport=-50",
        # Invalid --video
        "--vnc --video foobar",
        # --graphics bogus
        "--graphics vnc,foobar=baz",
        # mixing old and new
        "--graphics vnc --vnclisten 1.2.3.4",
      ],

     }, # category "graphics"

    "char" : {
     "args": "--hvm --nographics --noautoconsole --nodisks --pxe",

     "valid": [
        # Simple devs
        "--serial pty --parallel null",
        # Some with options
        "--serial file,path=/tmp/foo --parallel unix,path=/tmp/foo --parallel null",
        # UDP
        "--parallel udp,host=0.0.0.0:1234,bind_host=127.0.0.1:1234",
        # TCP
        "--serial tcp,mode=bind,host=0.0.0.0:1234",
        # Unix
        "--parallel unix,path=/tmp/foo-socket",
        # TCP w/ telnet
        "--serial tcp,host=:1234,protocol=telnet",
        # --channel guestfwd
        "--channel pty,target_type=guestfwd,target_address=127.0.0.1:10000",
        # --channel virtio
        "--channel pty,target_type=virtio,name=org.linux-kvm.port1",
        # --channel virtio without name=
        "--channel pty,target_type=virtio",
        # --console virtio
        "--console pty,target_type=virtio",
        # --console xen
        "--console pty,target_type=xen",
     ],
     "invalid" : [
        # Bogus device type
        "--parallel foobah",
        # Unix with no path
        "--serial unix",
        # Path where it doesn't belong
        "--serial null,path=/tmp/foo",
        # Nonexistent argument
        "--serial udp,host=:1234,frob=baz",
        # --channel guestfwd without target_address
        "--channel pty,target_type=guestfwd",
        # --console unknown type
        "--console pty,target_type=abcd",
     ],

     }, # category 'char'

     "cpuram" : {
      "args" : "--hvm --nographics --noautoconsole --nodisks --pxe",

      "valid" : [
        # Max VCPUS
        "--vcpus 32",
        # Cpuset
        "--vcpus 4 --cpuset=1,3-5",
        # Cpuset with trailing comma
        "--vcpus 4 --cpuset=1,3-5,",
        # Cpuset with trailing comma
        "--vcpus 4 --cpuset=auto",
        # Ram overcommit
        "--ram 100000000000",
        # maxvcpus, --check-cpu shouldn't error
        "--vcpus 5,maxvcpus=10 --check-cpu",
        # Topology
        "--vcpus 4,cores=2,threads=2,sockets=2",
        # Topology auto-fill
        "--vcpus 4,cores=1",
        # Topology only
        "--vcpus sockets=2,threads=2",
        # Simple --cpu
        "--cpu somemodel",
        # Crazy --cpu
        "--cpu foobar,+x2apic,+x2apicagain,-distest,forbid=foo,forbid=bar,disable=distest2,optional=opttest,require=reqtest,match=strict,vendor=meee",
      ],

      "invalid" : [
        # Bogus cpuset
        "--vcpus 32 --cpuset=969-1000",
        # Bogus cpuset
        "--vcpus 32 --cpuset=autofoo",
        # Over max vcpus
        "--vcpus 10000",
        # Over host vcpus w/ --check-cpu
        "--vcpus 20 --check-cpu",
        # maxvcpus less than cpus
        "--vcpus 5,maxvcpus=1",
        # vcpus unknown option
        "--vcpus foo=bar",
        # --cpu host, but no host CPU in caps
        "--cpu host",
      ],

    }, # category 'cpuram'

     "misc": {
      "args": "--nographics --noautoconsole",

      "valid": [
        # Specifying cdrom media via --disk
        "--hvm --disk path=virt-install,device=cdrom",
        # FV Import install
        "--hvm --import --disk path=virt-install",
        # PV Import install
        "--paravirt --import --disk path=virt-install",
        # PV Import install, print single XML
        "--paravirt --import --disk path=virt-install --print-xml",
        # Import a floppy disk
        "--hvm --import --disk path=virt-install,device=floppy",
        # --autostart flag
        "--hvm --nodisks --pxe --autostart",
        # --description
        "--hvm --nodisks --pxe --description \"foobar & baz\"",
        # HVM windows install with disk
        "--hvm --cdrom %(EXISTIMG2)s --file %(EXISTIMG1)s --os-variant win2k3 --wait 0",
        # HVM windows install, print 3rd stage XML
        "--hvm --cdrom %(EXISTIMG2)s --file %(EXISTIMG1)s --os-variant win2k3 --wait 0 --print-step 3",
        # --watchdog dev default
        "--hvm --nodisks --pxe --watchdog default",
        # --watchdog opts
        "--hvm --nodisks --pxe --watchdog ib700,action=pause",
        # --sound option
        "--hvm --nodisks --pxe --sound",
        # --soundhw option
        "--hvm --nodisks --pxe --soundhw default --soundhw ac97",
        # --security dynamic
        "--hvm --nodisks --pxe --security type=dynamic",
        # --security implicit static
        "--hvm --nodisks --pxe --security label=foobar.label",
        # --security static with commas 1
        "--hvm --nodisks --pxe --security label=foobar.label,a1,z2,b3,type=static",
        # --security static with commas 2
        "--hvm --nodisks --pxe --security label=foobar.label,a1,z2,b3",
      ],

      "invalid": [
        # Positional arguments error
        "--hvm --nodisks --pxe foobar",
        # pxe and nonetworks
        "--nodisks --pxe --nonetworks",
        # Colliding name
        "--nodisks --pxe --name test",
        # Busted --watchdog
        "--hvm --nodisks --pxe --watchdog default,action=foobar",
        # Busted --soundhw
        "--hvm --nodisks --pxe --soundhw default --soundhw foobar",
        # Busted --security
        "--hvm --nodisks --pxe --security type=foobar",
        # PV Import install, no second XML step
        "--paravirt --import --disk path=virt-install --print-step 2",
        # 2 stage install with --print-xml
        "--hvm --nodisks --pxe --print-xml",
      ],

      "compare": [
        # No arguments
        ("", "noargs-fail"),
        # Diskless PXE install
        ("--hvm --nodisks --pxe --print-step all", "simple-pxe"),
        # HVM windows install with disk
        ("--hvm --cdrom %(EXISTIMG2)s --file %(EXISTIMG1)s --os-variant win2k3 --wait 0 --vcpus cores=4", "w2k3-cdrom"),
        # Lot's of devices
        ("--hvm --pxe "
         "--disk %(EXISTIMG1)s,cache=writeback,io=threads,perms=sh "
         "--disk %(NEWIMG1)s,sparse=false,size=.001,perms=ro "
         "--serial tcp,host=:2222,mode=bind,protocol=telnet ",
         "many-devices"),
      ],

     }, # category "misc"

     "network": {
      "args": "--pxe --nographics --noautoconsole --nodisks",

      "valid": [
        # Just a macaddr
        "--mac 11:22:33:44:55:AF",
        # user networking
        "--network=user",
        # Old bridge option
        "--bridge mybr0",
        # Old bridge w/ mac
        "--bridge mybr0 --mac 11:22:33:44:55:AF",
        # --network bridge:
        "--network bridge:mybr0,model=e1000",
        # VirtualNetwork with a random macaddr
        "--network network:default --mac RANDOM",
        # VirtualNetwork with a random macaddr
        "--network network:default --mac 00:11:22:33:44:55",
        # Using '=' as the net type delimiter
        "--network network=default,mac=11:00:11:00:11:00",
        # with NIC model
        "--network=user,model=e1000",
        # several networks
        "--network=network:default,model=e1000 --network=user,model=virtio,mac=11:22:33:44:55:AF",
      ],
      "invalid": [
        # Nonexistent network
        "--network=FOO",
        # Invalid mac
        "--network=network:default --mac 1234",
        # More mac addrs than nics
        "--network user --mac 00:11:22:33:44:EF --mac 00:11:22:33:44:AB",
        # Mixing bridge and network
        "--network user --bridge foo0",
        # Colliding macaddr
        "--mac 11:22:33:12:34:AB",
      ],

     }, # category "network"

     "hostdev" : {
      "args": "--noautoconsole --nographics --nodisks --pxe",

      "valid" : [
        # Host dev by libvirt name
        "--host-device usb_device_781_5151_2004453082054CA1BEEE",
        # Many hostdev parsing types
        "--host-device 001.003 --host-device 15:0.1 --host-device 2:15:0.2 --host-device 0:15:0.3 --host-device 0x0781:0x5151 --host-device 1d6b:2",
      ],

      "invalid" : [
        # Unsupported hostdev type
        "--host-device pci_8086_2850_scsi_host_scsi_host",
        # Unknown hostdev
        "--host-device foobarhostdev",
        # Parseable hostdev, but unknown digits
        "--host-device 300:400",
      ],
     }, # category "hostdev"

     "remote" : {
      "args": "--connect %(REMOTEURI)s --nographics --noautoconsole",

      "valid" : [
        # Simple pxe nodisks
        "--nodisks --pxe",
        # Managed CDROM install
        "--nodisks --cdrom %(MANAGEDEXIST1)s",
        # Using existing managed storage
        "--pxe --file %(MANAGEDEXIST1)s",
        # Using existing managed storage 2
        "--pxe --disk vol=%(POOL)s/%(VOL)s",
        # Creating storage on managed pool
        "--pxe --disk pool=%(POOL)s,size=.04",
      ],
      "invalid": [
        # Use of --location
        "--nodisks --location /tmp",
        # Trying to use unmanaged storage
        "--file %(EXISTIMG1)s --pxe",
      ],

     }, # category "remote"


"kvm" : {
  "args": "--connect %(KVMURI)s --noautoconsole",

  "valid" : [
    # HVM windows install with disk
    "--cdrom %(EXISTIMG2)s --file %(EXISTIMG1)s --os-variant win2k3 --wait 0 --sound",
    # F14 Directory tree URL install with extra-args
    "--os-variant fedora14 --file %(EXISTIMG1)s --location %(TREEDIR)s --extra-args console=ttyS0 --sound"
  ],

  "invalid" : [
    # Unknown machine type
    "--nodisks --boot network --machine foobar",
    # Invalid domain type for arch
    "--nodisks --boot network --arch mips --virt-type kvm",
    # Invalid arch/virt combo
    "--nodisks --boot network --paravirt --arch mips",
  ],

  "compare" : [
    # F14 Directory tree URL install with extra-args
    ("--os-variant fedora14 --file %(EXISTIMG1)s --location %(TREEDIR)s --extra-args console=ttyS0 --cpu host", "kvm-f14-url"),
    # Quiet URL install should make no noise
    ("--os-variant fedora14 --disk %(NEWIMG1)s,size=.01 --location %(TREEDIR)s --extra-args console=ttyS0 --quiet", "quiet-url"),
    # HVM windows install with disk
    ("--cdrom %(EXISTIMG2)s --file %(EXISTIMG1)s --os-variant win2k3 --wait 0 --sound", "kvm-win2k3-cdrom"),

    # xenner
    ("--os-variant fedora14 --nodisks --boot hd --paravirt", "kvm-xenner"),
    # plain qemu
    ("--os-variant fedora14 --nodisks --boot cdrom --virt-type qemu",
     "qemu-plain"),
    # 32 on 64
    ("--os-variant fedora14 --nodisks --boot network --nographics --arch i686",
     "qemu-32-on-64"),
    # kvm machine type 'pc'
    ("--os-variant fedora14 --nodisks --boot fd --graphics spice --machine pc", "kvm-machine"),
    # exotic arch + machine type
    ("--os-variant fedora14 --nodisks --boot fd --graphics sdl --arch sparc --machine SS-20",
     "qemu-sparc"),
  ],

}, # category "kvm"

"xen" : {
  "args": "--connect %(XENURI)s --noautoconsole",

  "valid"   : [
    # HVM
    "--nodisks --cdrom %(EXISTIMG1)s --livecd --hvm",
    # PV
    "--nodisks --boot hd --paravirt",
    # 32 on 64 xen
    "--nodisks --boot hd --paravirt --arch i686",
  ],

  "invalid" : [
  ],

  "compare" : [
    # Xen default
    ("--disk %(EXISTIMG1)s --import", "xen-default"),
    # Xen PV
    ("--disk %(EXISTIMG1)s --location %(TREEDIR)s --paravirt", "xen-pv"),
    # Xen HVM
    ("--disk %(EXISTIMG1)s --cdrom %(EXISTIMG1)s --livecd --hvm", "xen-hvm"),
    # ia64 default
    ("--connect %(XENIA64URI)s --disk %(EXISTIMG1)s --import",
     "xen-ia64-default"),
    # ia64 pv
    ("--connect %(XENIA64URI)s --disk %(EXISTIMG1)s --location %(TREEDIR)s --paravirt", "xen-ia64-pv"),
    # ia64 hvm
    ("--connect %(XENIA64URI)s --disk %(EXISTIMG1)s --location %(TREEDIR)s --hvm", "xen-ia64-hvm"),
  ],

},
    "prompt" : [ " --connect %(TESTURI)s --debug --prompt" ]
  },




  "virt-clone": {
    "globalargs" : " --connect %(TESTURI)s -d",

    "general" : {
      "args": "-n clonetest",

      "valid"  : [
        # Nodisk guest
        "-o test",
        # Nodisk, but with spurious files passed
        "-o test --file %(NEWIMG1)s --file %(NEWIMG2)s",

        # XML File with 2 disks
        "--original-xml %(CLONE_DISK_XML)s --file %(NEWIMG1)s --file %(NEWIMG2)s",
        # XML w/ disks, overwriting existing files with --preserve
        "--original-xml %(CLONE_DISK_XML)s --file virt-install --file %(EXISTIMG1)s --preserve",
        # XML w/ disks, force copy a readonly target
        "--original-xml %(CLONE_DISK_XML)s --file %(NEWIMG1)s --file %(NEWIMG2)s --file %(NEWIMG3)s --force-copy=hdc",
        # XML w/ disks, force copy a target with no media
        "--original-xml %(CLONE_DISK_XML)s --file %(NEWIMG1)s --file %(NEWIMG2)s --force-copy=fda",
        # XML w/ managed storage, specify managed path
        "--original-xml %(CLONE_STORAGE_XML)s --file %(MANAGEDNEW1)s",
        # XML w/ managed storage, specify managed path across pools
        # XXX: Libvirt test driver doesn't support cloning across pools
        #"--original-xml %(CLONE_STORAGE_XML)s --file /cross-pool/clonevol",
        # XML w/ non-existent storage, with --preserve
        "--original-xml %(CLONE_NOEXIST_XML)s --file %(EXISTIMG1)s --preserve",
      ],

      "invalid": [
        # Positional arguments error
        "-o test foobar",
        # Non-existent vm name
        "-o idontexist",
        # Non-existent vm name with auto flag,
        "-o idontexist --auto-clone",
        # Colliding new name
        "-o test -n test",
        # XML file with several disks, but non specified
        "--original-xml %(CLONE_DISK_XML)s",
        # XML w/ disks, overwriting existing files with no --preserve
        "--original-xml %(CLONE_DISK_XML)s --file virt-install --file %(EXISTIMG1)s",
        # XML w/ disks, force copy but not enough disks passed
        "--original-xml %(CLONE_DISK_XML)s --file %(NEWIMG1)s --file %(NEWIMG2)s --force-copy=hdc",
        # XML w/ managed storage, specify unmanaged path (should fail)
        "--original-xml %(CLONE_STORAGE_XML)s --file /tmp/clonevol",
        # XML w/ non-existent storage, WITHOUT --preserve
        "--original-xml %(CLONE_NOEXIST_XML)s --file %(EXISTIMG1)s",
        # XML w/ managed storage, specify RO image without preserve
        "--original-xml %(CLONE_DISK_XML)s --file %(ROIMG)s --file %(ROIMG)s --force",
        # XML w/ managed storage, specify RO non existent
        "--original-xml %(CLONE_DISK_XML)s --file %(ROIMG)s --file %(ROIMGNOEXIST)s --force",
      ]
     }, # category "general"

    "misc" : {
      "args": "",

      "valid" : [
        # Auto flag, no storage
        "-o test --auto-clone",
        # Auto flag w/ storage,
        "--original-xml %(CLONE_DISK_XML)s --auto-clone",
        # Auto flag w/ managed storage,
        "--original-xml %(CLONE_STORAGE_XML)s --auto-clone",
        # Auto flag, actual VM, skip state check
        "-o test-for-clone --auto-clone --clone-running",
      ],

      "invalid" : [
        # Just the auto flag
        "--auto-clone"
        # Auto flag, actual VM, without state skip
        "-o test-for-clone --auto-clone",
      ],

      "compare" : [
        ("-o test-for-clone --auto-clone --clone-running", "clone-auto1"),
        ("-o test-clone-simple --name newvm --auto-clone --clone-running",
         "clone-auto2"),
      ],
    }, # category "misc"

     "remote" : {
      "args": "--connect %(REMOTEURI)s",

      "valid"  : [
        # Auto flag, no storage
        "-o test --auto-clone",
        # Auto flag w/ managed storage,
        "--original-xml %(CLONE_STORAGE_XML)s --auto-clone",
      ],
      "invalid": [
        # Auto flag w/ storage,
        "--original-xml %(CLONE_DISK_XML)s --auto-clone",
      ],
    }, # categort "remote"

    "prompt" : [
        " --connect %(TESTURI) --debug --prompt",
        " --connect %(TESTURI) --debug --original-xml %(CLONE_DISK_XML)s --prompt" ]
  }, # app 'virt-clone'




  'virt-image': {
    "globalargs" : " --connect %(TESTURI)s -d %(IMAGE_XML)s",

    "general" : {
      "args" : "--name test-image",

      "valid": [
        # All default values
        "",
        # Print default
        "--print",
        # Manual boot idx 0
        "--boot 0",
        # Manual boot idx 1
        "--boot 1",
        # Lots of options
        "--name foobar --ram 64 --os-variant winxp",
        # OS variant 'none'
        "--name foobar --ram 64 --os-variant none",
      ],

      "invalid": [
        # Out of bounds index
        "--boot 10",
      ],
     }, # category 'general'

    "graphics" : {
      "args" : "--name test-image --boot 0",

      "valid": [
        # SDL
        "--sdl",
        # VNC w/ lots of options
        "--vnc --keymap ja --vncport 5950 --vnclisten 1.2.3.4",
      ],

      "invalid": [],
    },

    "misc": {
     "args" : "",

      "valid" : [
        # Colliding VM name w/ --replace
        "--name test --replace",
      ],
      "invalid" : [
        # No name specified, and no prompt flag
        "",
        # Colliding VM name without --replace
        "--name test",
      ],

      "compare" : [
        ("--name foobar --ram 64 --os-variant winxp --boot 0", "image-boot0"),
        ("--name foobar --ram 64 --network user,model=e1000 --boot 1",
         "image-boot1"),
      ]

     }, # category 'misc'

     "network": {
      "args": "--name test-image --boot 0 --nographics",

      "valid": [
        # user networking
        "--network=user",
        # VirtualNetwork with a random macaddr
        "--network network:default --mac RANDOM",
        # VirtualNetwork with a random macaddr
        "--network network:default --mac 00:11:22:33:44:55",
        # with NIC model
        "--network=user,model=e1000",
        # several networks
        "--network=network:default,model=e1000 --network=user,model=virtio",
        # no networks
        #"--nonetworks",
      ],
      "invalid": [
        # Nonexistent network
        "--network=FOO",
        # Invalid mac
        "--network=network:default --mac 1234",
      ],

     }, # category "network"
    "prompt" : [ " --connect %(TESTURI)s %(IMAGE_XML)s --debug --prompt" ],

  }, # app 'virt-image'


  "virt-convert" : {
    "globalargs" : "--debug",

    "misc" : {
     "args": "",

     "valid": [
        # virt-image to default (virt-image) w/ no convert
        "%(VC_IMG1)s -D none %(VIRTCONV_OUT)s",
        # virt-image to virt-image w/ no convert
        "%(VC_IMG1)s -o virt-image -D none %(VIRTCONV_OUT)s",
        # virt-image to vmx w/ no convert
        "%(VC_IMG1)s -o vmx -D none %(VIRTCONV_OUT)s",
        # virt-image to vmx w/ raw
        "%(VC_IMG1)s -o vmx -D raw %(VIRTCONV_OUT)s",
        # virt-image to vmx w/ vmdk
        "%(VC_IMG1)s -o vmx -D vmdk %(VIRTCONV_OUT)s",
        # virt-image to vmx w/ qcow2
        "%(VC_IMG1)s -o vmx -D qcow2 %(VIRTCONV_OUT)s",
        # vmx to vmx no convert
        "%(VMX_IMG1)s -o vmx -D none %(VIRTCONV_OUT)s",
        # virt-image with exotic formats specified
        "%(VC_IMG2)s -o vmx -D vmdk %(VIRTCONV_OUT)s"
     ],

     "invalid": [
        # virt-image to virt-image with invalid format
        "%(VC_IMG1)s -o virt-image -D foobarfmt %(VIRTCONV_OUT)s",
        # virt-image to ovf (has no output formatter)
        "%(VC_IMG1)s -o ovf %(VIRTCONV_OUT)s",
     ],

     "compare": [
        # virt-image to default (virt-image) w/ no convert
        ("%(VC_IMG1)s %(VIRTCONV_OUT)s", "convert-default"),
     ],
    }, # category 'misc'

  }, # app 'virt-conver'
}

def runcomm(comm):
    try:
        for i in new_files:
            os.system("rm %s > /dev/null 2>&1" % i)

        if debug:
            print comm % test_files

        ret = commands.getstatusoutput(comm % test_files)
        if debug:
            print ret[1]
            print "\n"

        return ret
    except Exception, e:
        return (-1, str(e))

def run_prompt_comm(comm):
    print comm
    os.system(comm % test_files)

def write_pass():
    if not debug:
        sys.stdout.write(".")
        sys.stdout.flush()

def write_fail():
    if not debug:
        sys.stdout.write("F")
        sys.stdout.flush()

def assertPass(comm):
    ret = runcomm(comm)
    if ret[0] is not 0:
        raise AssertionError("Expected command to pass, but failed.\n" + \
                             "Command was: %s\n" % (comm) + \
                             "Error code : %d\n" % ret[0] + \
                             "Output was:\n%s" % ret[1])
    return ret

def assertFail(comm):
    ret = runcomm(comm)
    if ret[0] is 0:
        raise AssertionError("Expected command to fail, but passed.\n" + \
                             "Command was: %s\n" % (comm) + \
                             "Error code : %d\n" % ret[0] + \
                             "Output was:\n%s" % ret[1])
    return ret


class Command(object):
    def __init__(self, cmdstr):
        self.cmdstr = cmdstr
        self.check_success = True
        self.compare_file = None

    def run(self):
        filename = self.compare_file
        err = None

        try:
            if self.check_success:
                ignore, output = assertPass(self.cmdstr)
            else:
                ignore, output = assertFail(self.cmdstr)

            if filename:
                # Uncomment to generate new test files
                if not os.path.exists(filename):
                    file(filename, "w").write(output)

                utils.diff_compare(output, filename)

            write_pass()
        except AssertionError, e:
            write_fail()
            err = self.cmdstr + "\n" + str(e)

        return err

# Setup: build cliarg dict, which uses
def run_tests(do_app, do_category, error_ret):
    if do_app and do_app not in args_dict.keys():
        raise ValueError("Unknown app '%s'" % do_app)

    for app in args_dict:
        if do_app and app != do_app:
            continue

        unique = {}
        prompts = []
        globalargs = ""

        # Build default command line dict
        for option in args_dict.get(app):
            if option == "globalargs":
                globalargs = args_dict[app][option]
                continue
            elif option == "prompt":
                prompts = args_dict[app][option]
                continue

            # Default is a unique cmd string
            unique[option] = args_dict[app][option]

        # Build up prompt cases
        if testprompt:
            for optstr in prompts:
                cmd = "./" + app + " " + optstr
                run_prompt_comm(cmd)
            continue

        if do_category and do_category not in unique.keys():
            raise ValueError("Unknown category %s" % do_category)

        # Build up unique command line cases
        for category in unique.keys():
            if do_category and category != do_category:
                continue
            catdict = unique[category]
            category_args = catdict["args"]

            cmdlist = []

            for optstr in catdict["valid"]:
                cmdstr = "./%s %s %s %s" % (app, globalargs,
                                            category_args, optstr)
                cmd = Command(cmdstr)
                cmd.check_success = True
                cmdlist.append(cmd)

            for optstr in catdict["invalid"]:
                cmdstr = "./%s %s %s %s" % (app, globalargs,
                                            category_args, optstr)
                cmd = Command(cmdstr)
                cmd.check_success = False
                cmdlist.append(cmd)

            for optstr, filename in catdict.get("compare") or []:
                filename = "%s/%s.xml" % (compare_xmldir, filename)
                cmdstr = "./%s %s %s %s" % (app, globalargs,
                                            category_args, optstr)
                cmdstr = cmdstr % test_files

                # Strip --debug to get reasonable output
                cmdstr = cmdstr.replace("--debug ", "").replace("-d ", "")
                if app == "virt-install":
                    if (not cmdstr.count("--print-xml") and
                        not cmdstr.count("--print-step") and
                        not cmdstr.count("--quiet")):
                        cmdstr += " --print-step all"

                elif app == "virt-image":
                    if not cmdstr.count("--print"):
                        cmdstr += " --print"

                elif app == "virt-clone":
                    if not cmdstr.count("--print-xml"):
                        cmdstr += " --print-xml"

                if app != "virt-convert" and not cmdstr.count(fakeuri):
                    cmdstr += " --connect %s" % fakeuri

                cmd = Command(cmdstr)
                cmd.check_success = not filename.endswith("fail.xml")
                cmd.compare_file = filename
                cmdlist.append(cmd)

            # Run commands
            for cmd in cmdlist:
                err = cmd.run()
                if err:
                    error_ret.append(err)

def main():
    # CLI Args
    global debug
    global testprompt

    do_app = None
    do_category = None

    if len(sys.argv) > 1:
        for i in range(1, len(sys.argv)):
            if sys.argv[i].count("debug"):
                debug = True
            elif sys.argv[i].count("prompt"):
                testprompt = True
            elif sys.argv[i].count("--app"):
                do_app = sys.argv[i + 1]
            elif sys.argv[i].count("--category"):
                do_category = sys.argv[i + 1]

    # Setup needed files
    for i in exist_files:
        if os.path.exists(i):
            raise ValueError("'%s' will be used by testsuite, can not already"
                             " exist." % i)

    os.system("mkdir %s" % ro_dir)

    for i in exist_files:
        os.system("touch %s" % i)

    # Set ro_img to readonly
    os.system("chmod 444 %s" % ro_img)
    os.system("chmod 555 %s" % ro_dir)

    error_ret = []
    try:
        run_tests(do_app, do_category, error_ret)
    finally:
        cleanup()
        for err in error_ret:
            print err + "\n\n"

    if not error_ret:
        print "\nAll tests completed successfully."

def cleanup():
    # Cleanup files
    for i in clean_files:
        os.system("chmod 777 %s > /dev/null 2>&1" % i)
        os.system("rm -rf %s > /dev/null 2>&1" % i)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print "Tests interrupted"
