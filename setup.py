from distutils.core import setup

pkgs = ['virtinst']
setup(name='virtinst',
      version='0.97.0',
      description='Virtual machine installation',
      author='Jeremy Katz',
      author_email='katzj@redhat.com',
      license='GPL',
      package_dir={'virtinst': 'virtinst'},
      scripts = ["virt-install"],
      packages=pkgs,
      )
               
