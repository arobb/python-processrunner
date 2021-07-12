# -*- coding: utf-8 -*-
# https://gehrcke.de/2014/02/distributing-a-python-command-line-application/
# ^ Structure help for overall project

from setuptools import setup
# To use a consistent encoding
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Version information
try:
    with open(path.join(here, 'VERSION'), encoding='utf-8') as vf:
        version = vf.readline()
except IOError:
    # During development the VERSION file won't exist
    from gitversion import get_git_version
    version = get_git_version()

# Get the long description from the README file
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
      name='processrunner'

      # Version
    , version=version

    # Descriptions
    , description='Easily trigger and manage output from external processes.'
    , long_description=long_description

    # Project URL
    , url='https://github.com/arobb/python-processrunner'

    # Author
    , author='Andy Robb'
    , author_email='andy@andyrobb.com'

    # License
    , license='MIT'

    # Classifiers
    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    , classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 4 - Beta',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Topic :: Utilities',

        # Pick your license as you wish (should match "license" above)
        'License :: OSI Approved :: MIT License',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',

        # Other stuff
        'Environment :: Console',
        'Operating System :: POSIX'
    ]

    # What does your project relate to?
    , keywords='external process execution'

    # You can just specify the packages manually here if your project is
    # simple. Or you can use find_packages().
    # , packages=find_packages("processrunner")
    , packages=["processrunner"]

    # Alternatively, if you want to distribute just a my_module.py, uncomment
    # this:
    # , py_modules=["processrunner"]

    # List run-time dependencies here.  These will be installed by pip when
    # your project is installed. For an analysis of "install_requires" vs pip's
    # requirements files see:
    # https://packaging.python.org/en/latest/requirements.html
    , install_requires=['future', 'kitchen', 'deprecated', 'funcsigs']

    # List additional groups of dependencies here (e.g. development
    # dependencies). You can install these using the following syntax,
    # for example:
    # $ pip install -e .[dev,test]
    , extras_require={
        'dev': ['pylama', 'check-manifest'],
        'test': ['mock', 'pygments', 'pytest', 'parameterized'],
    }

    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # pip to create the appropriate form of executable for the target platform.
    # , entry_points={
    #     'console_scripts': [
    #         'cmd = Package.Class:method'
    #     ],
    # }
)
