__author__ = 'eponsko'
from setuptools import setup, find_packages
setup(name='doubledecker',
      version='0.4',
      description='DoubleDecker client module and examples',
      url='http://acreo.github.io/DoubleDecker/',
      author='ponsko',
      author_email='ponsko@acreo.se',
      license='LGPLv2.1',
      scripts=['bin/ddclient.py', 'bin/ddkeys.py', ],
      packages=find_packages(),
      install_requires=['pyzmq', 'pynacl', 'future'])
