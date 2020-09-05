#!/usr/bin/env python3
import os
from distutils.core import setup
from Cython.Build import cythonize
from distutils.extension import Extension

root = os.path.dirname(os.path.realpath(__file__))

heclib_obj = os.path.join(root,'heclib/linux/heclib.a')

extension = [
	Extension("pyheclib",
	sources=["src/pyheclib.pyx"], 
	libraries=['gcc','m','dl','gfortran'],
	define_macros=[
		("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION"),
	],
	include_dirs=[os.path.join(root,'heclib/headers')],
	library_dirs=[],
	extra_compile_args=[
			'-lgcc','-lm', '-ldl', '-lgfortran','-O0',
			# disable warnings 
			# '-Wno-unused-but-set-variable',
			# '-Wno-unused-parameter', 
			# '-Wno-unused-variable',
			# '-Wno-uninitialized'
			],
	extra_objects=[heclib_obj],
	),
]

setup(
	name='build-pyheclib',
	ext_modules= cythonize(extension[0],language_level='3'),
)