from distutils.core import setup, Command
from unittest import TextTestRunner, TestLoader
from glob import glob
from os.path import splitext, basename, join as pjoin, walk
import os
import tests.coverage as coverage


pkgs = ['virtinst']

class TestCommand(Command):
    user_options = [ ]

    def initialize_options(self):
        self._dir = os.getcwd()

    def finalize_options(self):
        pass

    def run(self):
        '''
        Finds all the tests modules in tests/, and runs them.
        '''
        testfiles = [ ]
        for t in glob(pjoin(self._dir, 'tests', '*.py')):
            if not t.endswith('__init__.py'):
                testfiles.append('.'.join(
                    ['tests', splitext(basename(t))[0]])
                )
        tests = TestLoader().loadTestsFromNames(testfiles)
        t = TextTestRunner(verbosity = 1)
        coverage.erase()
        coverage.start()
        t.run(tests)
        coverage.stop()

setup(name='virtinst',
      version='0.103.0',
      description='Virtual machine installation',
      author='Jeremy Katz',
      author_email='katzj@redhat.com',
      license='GPL',
      package_dir={'virtinst': 'virtinst'},
      scripts = ["virt-install"],
      packages=pkgs,
      data_files = [('share/man/man1', ['man/en/virt-install.1', 'man/en/virt-clone.1'])],
      cmdclass = { 'test': TestCommand }
      )

