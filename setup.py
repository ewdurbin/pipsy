import os
from setuptools import setup
from distutils.command.sdist import sdist
from distutils.command.bdist import bdist

from pip.req import parse_requirements

cwd = os.path.abspath(os.path.dirname(__file__))

requirements_txt = parse_requirements(os.path.join(cwd, 'requirements.txt'))
requirements = [str(r.req) for r in requirements_txt]
readme = open(os.path.join(cwd, 'README.md')).read()

setup(name='pipsy',
      version='0.1.3',
      description='pypi ',
      long_description=readme,
      author='Ernest W. Durbin III, Benjamin W. Smith',
      author_email='ewdurbin@gmail.com, benjaminwarfield@gmail.com',
      packages=['pipsy'],
      url='http://github.com/pipsy/pipsy.py',
      install_requires=requirements,
      platforms = 'Posix; MacOS X; Windows',
      entry_points={
          'console_scripts': 'pipsy=pipsy.app:main'
      }
) 

