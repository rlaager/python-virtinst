from distutils.core import setup

pkgs = ['xeninst']
setup(name='xeninst',
      version='0.92.0',
      description='Xen guest installation',
      author='Jeremy Katz',
      author_email='katzj@redhat.com',
      license='GPL',
      package_dir={'xeninst': 'xeninst'},
      scripts = ["xenguest-install"],
      packages=pkgs,
      )
               
