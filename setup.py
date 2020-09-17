#!/usr/bin/env python3
import os,sys,numpy
# from distutils.core import setup
from setuptools import setup
from Cython.Build import cythonize
from distutils.extension import Extension

root = os.path.dirname(os.path.realpath(__file__))

# platform dependent
extra_objects_list = []
library_dirs_list = []
compiler_arg_list = []
libraries_list = []

# platform independent
macros_list = [("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION"),]
include_dirs_list = [os.path.join(root,'heclib/headers'),numpy.get_include()]
sources_list = ["src/pyheclib.pyx"]

if sys.platform.lower()=='linux':
	print("*** Platform *** LINUX ***")
	
	extra_objects_list = [os.path.join(root,'heclib/linux/heclib.a')]

	compiler_arg_list = [
		# '-lgcc','-lm', '-ldl', '-lgfortran',
		'-O0',
		# disable warnings 
		'-Wno-unused-but-set-variable',
		'-Wno-unused-parameter', 
		'-Wno-unused-variable',
		'-Wno-uninitialized',
		'-Wno-unused-function'
	]

	libraries_list = ['gcc','m','dl','gfortran']

elif sys.platform.lower().startswith('win'):

	# requires:
	# * Intel fortran compiler
	# * Microsoft visual c++ 14 build tools

	print("*** Platform *** WINDOWS ***")


	extra_objects_list = [
		os.path.join(root,'heclib\windows\Release64\heclib_c_v6v7.lib'),
		os.path.join(root,'heclib\windows\Release64\heclib_f_v6v7.lib')
	]

	library_dirs_list =[
		# intel fortran compiler library location
		'C:\\Program Files (x86)\\IntelSWTools\\compilers_and_libraries_2020\\windows\\compiler\\lib\\intel64_win'
	]



extension = [
	Extension("pyheclib",
		sources = sources_list, 
		libraries = libraries_list,
		define_macros = macros_list,
		include_dirs = include_dirs_list,
		library_dirs = library_dirs_list,
		extra_compile_args = compiler_arg_list,
		extra_objects = extra_objects_list,
	),
]

setup(
    python_requires='>=3.6',
	version='0.1.0',
	name='build-pyheclib',
	ext_modules= cythonize(extension,language_level='3'),
)