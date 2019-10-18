import os

from setuptools import setup
from distutils.command.sdist import sdist
from distutils.command.bdist import bdist

CWD = os.path.abspath(os.path.dirname(__file__))

README = open(os.path.join(CWD, 'README.md')).read()

INSTALL_REQUIREMENTS =  [
    'Flask==1.0',
    'Flask-SSLify==0.1.4',
    'Jinja2==2.7.3',
    'MarkupSafe==0.23',
    'Werkzeug==0.9.6',
    'boto==2.33.0',
    'itsdangerous==0.24',
    'wsgiref==0.1.2',
    'gunicorn==19.1.1',
    'gevent==1.0.1'

]


setup(name='pipsy',
      version='0.1.5',
      description='pypi ',
      long_description=README,
      author='Ernest W. Durbin III, Benjamin W. Smith',
      author_email='ewdurbin@gmail.com, benjaminwarfield@gmail.com',
      packages=['pipsy'],
      url='http://github.com/pipsy/pipsy.py',
      install_requires=INSTALL_REQUIREMENTS,
      platforms = 'Posix; MacOS X; Windows',
      entry_points={
          'console_scripts': 'pipsy=pipsy.app:main'
      }
) 

