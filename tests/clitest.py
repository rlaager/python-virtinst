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
import os, sys

# Set DISPLAY if it isn't already set
os.environ["DISPLAY"] = "testdisplay"

testuri = "test:///`pwd`/tests/testdriver.xml"

# There is a hack in virtinst/cli.py to find this magic string and
# convince virtinst we are using a remote connection.
remoteuri = "__virtinst_test_remote__test:///`pwd`/tests/testdriver.xml"

# Location
xmldir = "tests/cli-test-xml"
treedir = "tests/cli-test-xml/faketree"
ro_img = "cli_exist3ro.img"

# Images that will be created by virt-install/virt-clone, and removed before
# each run
new_images =    [ "cli_new1.img", "cli_new2.img", "cli_new3.img",
                  "cli_exist1-clone.img", "cli_exist2-clone.img"]

# Images that are expected to exist before a command is run
exist_images =  [ "cli_exist1.img", "cli_exist2.img", ro_img]

# Images that need to exist ahead of time for virt-image
virtimage_exist = [os.path.join(xmldir, "cli_root.raw")]

# Images created by virt-image
virtimage_new = [os.path.join(xmldir, "cli_scratch.raw")]

exist_files = exist_images + virtimage_exist
new_files   = new_images + virtimage_new
clean_files = new_images + exist_images + virtimage_exist + virtimage_new

test_files = {
    'TESTURI'           : testuri,
    'REMOTEURI'         : remoteuri,
    'CLONE_DISK_XML'    : "%s/clone-disk.xml" % xmldir,
    'CLONE_STORAGE_XML' : "%s/clone-disk-managed.xml" % xmldir,
    'IMAGE_XML'         : "%s/image.xml" % xmldir,
    'NEWIMG1'           : new_images[0],
    'NEWIMG2'           : new_images[1],
    'NEWIMG3'           : new_images[2],
    'EXISTIMG1'         : exist_images[0],
    'EXISTIMG2'         : exist_images[1],
    'ROIMG'             : ro_img,
    'POOL'              : "default-pool",
    'VOL'               : "testvol1.img",
    'MANAGEDEXIST1'     : "/default-pool/testvol1.img",
    'MANAGEDEXIST2'     : "/default-pool/testvol2.img",
    'MANAGEDNEW1'       : "/default-pool/clonevol",
    'MANAGEDNEW2'       : "/default-pool/clonevol",
    'MANAGEDDISKNEW1'   : "/disk-pool/newvol1.img",
}

debug = False
testprompt = False

"""
CLI test matrix

Format:

"appname" {
  "global_args" : Arguments to be passed to every app invocation

  "categoryfoo" : { Some descriptive test catagory name (e.g. storage)

    "categoryfoo_args" : Args to be applied to all invocations in category

    "valid" : { # Argument strings that should succeed
      "--option --string --number1" # Some option string to test. The
          resulting cmdstr would be:
          $ appname global_args categoryfoo_args --option --string --number1
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
    "global_args" : " --connect %(TESTURI)s -d --name foobar --ram 64",

    "storage" : {
      "storage_args": "--pxe --nographics --noautoconsole --hvm",

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
        "--disk path=%(EXISTIMG1)s,perms=ro,size=.0001,cache=writethrough",
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
        # Two IDE cds
        "--disk path=%(EXISTIMG1)s,device=cdrom --disk path=%(EXISTIMG1)s,device=cdrom",
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
      ]
     }, # category "storage"

     "install" : {
      "install_args": "--nographics --noautoconsole --nodisks",

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
        #"--arch i486 --pxe",
        # Directory tree URL install
        "--hvm --location %s" % treedir,
        # Directory tree URL install with extra-args
        "--hvm --location %s --extra-args console=ttyS0" % treedir,
        # Directory tree CDROM install
        "--hvm --cdrom %s" % treedir,
        # Paravirt location
        "--paravirt --location %s" % treedir,
        # Using ro path as a cd media
        "--hvm --cdrom %(ROIMG)s",
        # Paravirt location with --os-variant none
        "--paravirt --location %s --os-variant none" % treedir,
        # URL install with manual os-variant
        "--hvm --location %s --os-variant fedora12" % treedir,
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
      ],
     }, # category "install"

     "graphics": {
      "graphics_args": "--noautoconsole --nodisks --pxe",

      "valid": [
        # SDL
        "--sdl",
        # VNC w/ lots of options
        "--vnc --keymap ja --vncport 5950 --vnclisten 1.2.3.4",
        # --video option
        "--vnc --video vga",
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
        # Invalid --video
        "--vnc --video foobar",
      ],

     }, # category "graphics"

    "char" : {
     "char_args": "--hvm --nographics --noautoconsole --nodisks --pxe",

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
     ],

     }, # category 'char'

     "cpuram" : {
      "cpuram_args" : "--hvm --nographics --noautoconsole --nodisks --pxe",

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
      ],

      "invalid" : [
        # Bogus cpuset
        "--vcpus 32 --cpuset=969-1000",
        # Bogus cpuset
        "--vcpus 32 --cpuset=autofoo",
        # Over max vcpus
        "--vcpus 10000",
      ],

    }, # category 'cpuram'

     "misc": {
      "misc_args": "--nographics --noautoconsole",

      "valid": [
        # Specifying cdrom media via --disk
        "--hvm --disk path=virt-install,device=cdrom",
        # FV Import install
        "--hvm --import --disk path=virt-install",
        # PV Import install
        "--paravirt --import --disk path=virt-install",
      ],

      "invalid": [
        # pxe and nonetworks
        "--nodisks --pxe --nonetworks",
      ],
     }, # category "misc"

     "network": {
      "network_args": "--pxe --nographics --noautoconsole --nodisks",

      "valid": [
        # Just a macaddr
        "--mac 11:22:33:44:55:66",
        # user networking
        "--network=user",
        # Old bridge option
        "--bridge mybr0",
        # Old bridge w/ mac
        "--bridge mybr0 --mac 11:22:33:44:55:66",
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
        "--network=network:default,model=e1000 --network=user,model=virtio,mac=11:22:33:44:55:66",
      ],
      "invalid": [
        # Nonexistent network
        "--network=FOO",
        # Invalid mac
        "--network=network:default --mac 1234",
        # More mac addrs than nics
        "--network user --mac 00:11:22:33:44:55 --mac 00:11:22:33:44:66",
        # Mixing bridge and network
        "--network user --bridge foo0",
      ],

     }, # category "network"

     "remote" : {
      "remote_args": "--connect %(REMOTEURI)s --nographics --noautoconsole",

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

    "prompt" : [ " --connect %(TESTURI)s --debug --prompt" ]
  },




  "virt-clone": {
    "global_args" : " --connect %(TESTURI)s -d",

    "general" : {
      "general_args": "-n clonetest",

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
        #"--original-xml %(CLONE_STORAGE_XML)s --file /cross-pool/clonevol",
      ],

      "invalid": [
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
      ]
     }, # category "general"

    "misc" : {
      "misc_args": "",

      "valid" : [
        # Auto flag, no storage
        "-o test --auto-clone",
        # Auto flag w/ storage,
        "--original-xml %(CLONE_DISK_XML)s --auto-clone",
        # Auto flag w/ managed storage,
        "--original-xml %(CLONE_STORAGE_XML)s --auto-clone",
      ],

      "invalid" : [
        # Just the auto flag
        "--auto-clone"
      ]
    }, # category "misc"

     "remote" : {
      "remote_args": "--connect %(REMOTEURI)s",

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

    "prompt" : [ " --connect %(TESTURI) --debug --prompt",
                 " --connect %(TESTURI) --debug --original-xml %(CLONE_DISK_XML)s --prompt" ]
  }, # app 'virt-clone'




  'virt-image': {
    "global_args" : " --connect %(TESTURI)s -d %(IMAGE_XML)s",

    "general" : {
      "general_args" : "--name test-image",

      "valid": [
        # All default values
        "",
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
      "graphics_args" : "--name test-image --boot 0",

      "valid": [
        # SDL
        "--sdl",
        # VNC w/ lots of options
        "--vnc --keymap ja --vncport 5950 --vnclisten 1.2.3.4",
      ],

      "invalid": [],
    },

    "misc": {
     "misc_args" : "",

      "valid" : [],
      "invalid" : [
        # No name specified, and no prompt flag
        "",
      ],

     }, # category 'misc'

     "network": {
      "network_args": "--name test-image --boot 0 --nographics",

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
    "prompt" : [ " --connect %(TESTURI) %(IMAGE_XML)s --debug --prompt" ],

  } # app 'virt-image'
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

def assertPass(comm):
    ret = runcomm(comm)
    if ret[0] is not 0:
        raise AssertionError("Expected command to pass, but failed.\n" + \
                             "Command was: %s\n" % (comm) + \
                             "Error code : %d\n" % ret[0] + \
                             "Output was:\n%s" % ret[1])

def assertFail(comm):
    ret = runcomm(comm)
    if ret[0] is 0:
        raise AssertionError("Expected command to fail, but passed.\n" + \
                             "Command was: %s\n" % (comm) + \
                             "Error code : %d\n" % ret[0] + \
                             "Output was:\n%s" % ret[1])

# Setup: build cliarg dict, which uses
def run_tests():
    for app in args_dict:
        unique = {}
        prompts = []
        global_args = ""

        # Build default command line dict
        for option in args_dict.get(app):
            if option == "global_args":
                global_args = args_dict[app][option]
                continue
            elif option == "prompt":
                prompts = args_dict[app][option]
                continue

            # Default is a unique cmd string
            unique[option]= args_dict[app][option]

        # Build up prompt cases
        if testprompt:
            for optstr in prompts:
                cmd = "./" + app + " " + optstr
                run_prompt_comm(cmd)
            continue

        # Build up unique command line cases
        for category in unique.keys():
            catdict = unique[category]
            category_args = catdict["%s_args" % category]

            for optstr in catdict["valid"]:
                cmdstr = "./%s %s %s %s" % (app, global_args,
                                            category_args, optstr)
                assertPass(cmdstr)

            for optstr in catdict["invalid"]:
                cmdstr = "./%s %s %s %s" % (app, global_args,
                                            category_args, optstr)
                assertFail(cmdstr)

def main():
    # CLI Args
    global debug
    global testprompt

    if len(sys.argv) > 1:
        for i in range(1, len(sys.argv)):
            if sys.argv[i].count("debug"):
                debug = True
            elif sys.argv[i].count("prompt"):
                testprompt = True

    # Setup needed files
    for i in exist_files:
        if os.path.exists(i):
            raise ValueError("'%s' will be used by testsuite, can not already"
                             " exist." % i)
    for i in exist_files:
        os.system("touch %s" % i)

    # Set ro_img to readonly
    os.system("chmod 444 %s" % ro_img)

    try:
        run_tests()
    finally:
        # Cleanup files
        for i in clean_files:
            os.system("rm -f %s > /dev/null 2>&1" % i)

if __name__ == "__main__":
    main()
