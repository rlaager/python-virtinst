from distutils.core import setup, Command
from distutils.command.sdist import sdist as _sdist
from distutils.command.build import build as _build
from distutils.command.install_data import install_data as _install_data
from distutils.command.install_lib import install_lib as _install_lib
from distutils.command.install import install as _install
from unittest import TextTestRunner, TestLoader
from glob import glob
from os.path import splitext, basename, join as pjoin
import os, sys

pkgs = ['virtinst', 'virtconv', 'virtconv.parsers' ]

datafiles = [('share/man/man1', ['man/en/virt-install.1',
                                 'man/en/virt-clone.1',
                                 'man/en/virt-image.1',
                                 'man/en/virt-convert.1']),
             ('share/man/man5', ['man/en/virt-image.5'])]
locale = None
builddir = None

VERSION = file("virtinst/version.py").read().split(" ")[2].strip(" \n\"")

class TestBaseCommand(Command):

    user_options = [('debug', 'd', 'Show debug output')]
    boolean_options = ['debug']

    def initialize_options(self):
        self.debug = 0
        self._testfiles = []
        self._dir = os.getcwd()

    def finalize_options(self):
        if self.debug and not os.environ.has_key("DEBUG_TESTS"):
            os.environ["DEBUG_TESTS"] = "1"

    def run(self):
        try:
            import coverage
            use_coverage = True
        except:
            # Use system 'coverage' if available
            use_coverage = False

        tests = TestLoader().loadTestsFromNames(self._testfiles)
        t = TextTestRunner(verbosity = 1)

        if use_coverage:
            coverage.erase()
            coverage.start()

        result = t.run(tests)

        if use_coverage:
            coverage.stop()

        if len(result.failures) > 0 or len(result.errors) > 0:
            sys.exit(1)
        else:
            sys.exit(0)

class TestCommand(TestBaseCommand):

    description = "Runs a quick unit test suite"
    user_options = TestBaseCommand.user_options + \
                   [("testfile=", None, "Specific test file to run (e.g "
                                        "validation, storage, ...)"),]

    def initialize_options(self):
        TestBaseCommand.initialize_options(self)
        self.testfile = None

    def finalize_options(self):
        TestBaseCommand.finalize_options(self)

    def run(self):
        '''
        Finds all the tests modules in tests/, and runs them.
        '''
        testfiles = []
        for t in glob(pjoin(self._dir, 'tests', '*.py')):
            if (not t.endswith('__init__.py') and
                not t.endswith("urltest.py") and
                not t.endswith("clitest.py")):

                if self.testfile:
                    base = os.path.basename(t)
                    check = os.path.basename(self.testfile)
                    if base != check and base != (check + ".py"):
                        continue

                testfiles.append('.'.join(['tests',
                                           splitext(basename(t))[0]]))
        self._testfiles = testfiles
        TestBaseCommand.run(self)

class TestCLI(TestBaseCommand):

    description = "Test various CLI invocations"

    user_options = (TestBaseCommand.user_options +
                    [("prompt", None, "Run interactive CLI invocations.")])

    def initialize_options(self):
        TestBaseCommand.initialize_options(self)
        self.prompt = 0

    def run(self):
        cmd = "python tests/clitest.py"
        if self.debug:
            cmd += " debug"
        if self.prompt:
            cmd += " prompt"
        os.system(cmd)

class TestURLFetch(TestBaseCommand):

    description = "Test fetching kernels and isos from various distro trees"

    user_options = TestBaseCommand.user_options + \
                   [("match=", None, "Regular expression of dist names to "
                                     "match [default: '.*']"),
                    ("path=", None, "Paths to local iso or directory or check"
                                    " for installable distro. Comma separated")]

    def initialize_options(self):
        TestBaseCommand.initialize_options(self)
        self.match = None
        self.path = ""

    def finalize_options(self):
        TestBaseCommand.finalize_options(self)
        if self.match is None:
            self.match = ".*"

        origpath = str(self.path)
        if not origpath:
            self.path = []
        else:
            self.path = origpath.split(",")

    def run(self):
        import tests
        self._testfiles = [ "tests.urltest" ]
        tests.urltest.MATCH_FILTER = self.match
        if self.path:
            for p in self.path:
                tests.urltest.LOCAL_MEDIA.append(p)
        TestBaseCommand.run(self)

class CheckPylint(Command):
    user_options = []
    description = "Run static analysis script against codebase."

    def initialize_options(self):
        pass
    def finalize_options(self):
        pass

    def run(self):
        os.system("tests/pylint-virtinst.sh")

class custom_rpm(Command):

    user_options = []

    description = "Build a non-binary rpm."

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        """
        Run sdist, then 'rpmbuild' the tar.gz
        """
        self.run_command('sdist')
        os.system('rpmbuild -ta dist/virtinst-%s.tar.gz' % VERSION)

class refresh_translations(Command):

    user_options = []

    description = "Regenerate POT file and merge with current translations."

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):

        # Generate POT file
        files = [ "virtinst/*.py", "virtconv/*.py", "virtconv/parsers/*.py",
                  "virt-*" ]
        pot_cmd = "xgettext --language=Python -o po/virtinst.pot"
        for f in files:
            pot_cmd += " %s " % f
        os.system(pot_cmd)

        # Merge new template with existing translations.
        for po in glob(pjoin(os.getcwd(), 'po', '*.po')):
            os.system("msgmerge -U po/%s po/virtinst.pot" %
                      os.path.basename(po))

class sdist(_sdist):
    """ custom sdist command, to prep virtinst.spec file for inclusion """

    def run(self):
        cmd = (""" sed -e "s/::VERSION::/%s/g" < python-virtinst.spec.in """ %
               VERSION) + " > python-virtinst.spec"
        os.system(cmd)

        # Update and generate man pages
        self._update_manpages()

        _sdist.run(self)

    def _update_manpages(self):
        # Update virt-install.1 with latest os type/variant values
        import virtinst.osdict as osdict

        output = ""
        output += "=over 4\n\n"
        for t in osdict.sort_helper(osdict.OS_TYPES):
            output += "=item %s\n\n" % t

            output += "=over 4\n\n"
            for v in osdict.sort_helper(osdict.OS_TYPES[t]["variants"]):
                output += "=item %s\n\n" % v
                output += osdict.OS_TYPES[t]["variants"][v]["label"] + "\n\n"

            output += "=back\n\n"
        output += "=back\n\n"

        infile = "man/en/virt-install.pod.in"
        outfile = "man/en/virt-install.pod"

        infd  = open(infile, "r")
        outfd = open(outfile, "w")

        inp = infd.read()
        infd.close()

        outp = inp.replace("::VARIANT VALUES::", output)
        outfd.write(outp)
        outfd.close()

        # Generate new manpages
        if os.system("make -C man/en"):
            raise RuntimeError("Couldn't generate man pages.")

class build(_build):
    """ custom build command to compile i18n files"""

    def run(self):
        global builddir

        if not os.path.exists("build/po"):
            os.makedirs("build/po")

        for filename in glob(pjoin(os.getcwd(), 'po', '*.po')):
            filename = os.path.basename(filename)
            lang = os.path.basename(filename)[0:len(filename)-3]
            if not os.path.exists("build/po/%s" % lang):
                os.makedirs("build/po/%s" % lang)
            newname = "build/po/%s/virtinst.mo" % lang

            print "Building %s from %s" % (newname, filename)
            os.system("msgfmt po/%s -o %s" % (filename, newname))

        _build.run(self)
        builddir = self.build_lib


class install(_install):
    """custom install command to extract install base for locale install"""

    def finalize_options(self):
        global locale
        _install.finalize_options(self)
        locale = self.install_base + "/share/locale"


class install_lib(_install_lib):
    """ custom install_lib command to place locale location into library"""

    def run(self):
        for initfile in [ "virtinst/__init__.py", "virtconv/__init__.py" ]:
            cmd =  "cat %s | " % initfile
            cmd += """sed -e "s,::LOCALEDIR::,%s," > """ % locale
            cmd += "%s/%s" % (builddir, initfile)
            os.system(cmd)

        _install_lib.run(self)


class install_data(_install_data):
    """ custom install_data command to prepare i18n files for install"""

    def run(self):
        dirlist = os.listdir("build/po")
        for lang in dirlist:
            if lang != "." and lang != "..":
                install_path = "share/locale/%s/LC_MESSAGES/" % lang

                src_path = "build/po/%s/virtinst.mo" % lang

                print "Installing %s to %s" % (src_path, install_path)
                toadd = (install_path, [src_path])

                # Add these to the datafiles list
                datafiles.append(toadd)
        _install_data.run(self)

setup(name='virtinst',
      version=VERSION,
      description='Virtual machine installation',
      author='Jeremy Katz, Daniel Berrange, Cole Robinson',
      author_email='crobinso@redhat.com',
      license='GPL',
      url='http://virt-manager.et.redhat.com',
      package_dir={'virtinst': 'virtinst'},
      scripts = ["virt-install","virt-clone", "virt-image", "virt-convert"],
      packages=pkgs,
      data_files = datafiles,
      cmdclass = { 'test': TestCommand, 'test_urls' : TestURLFetch,
                   'test_cli' : TestCLI,
                    'check': CheckPylint,
                    'rpm' : custom_rpm,
                    'sdist': sdist, 'build': build,
                    'install_data' : install_data,
                    'install_lib' : install_lib,
                    'install' : install,
                    'refresh_translations' : refresh_translations}
      )
