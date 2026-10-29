#!/usr/bin/env python3
import os, sys, shutil, numpy
from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext
from Cython.Build import cythonize

root = os.path.dirname(os.path.realpath(__file__))
heclib = os.path.join(root, 'heclib')

# platform dependent
library_dirs_list = []
libraries_list = ['hecdss']
compiler_arg_list = []
linker_arg_list = []
shared_lib = None

# platform independent
macros_list = [("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION"),]
include_dirs_list = [os.path.join(heclib, 'include'), numpy.get_include()]
sources_list = ["src/_core.pyx"]

if sys.platform.startswith('linux'):
	print("*** Platform *** LINUX ***")

	library_dirs_list = [os.path.join(heclib, 'linux')]
	linker_arg_list = ['-Wl,-rpath,$ORIGIN']
	shared_lib = os.path.join(heclib, 'linux', 'libhecdss.so')

elif sys.platform == 'darwin':
	print("*** Platform *** MACOS ***")

	library_dirs_list = [os.path.join(heclib, 'macos')]
	# libhecdss.dylib links @rpath/libz.1.dylib, resolved from system /usr/lib
	linker_arg_list = ['-Wl,-rpath,@loader_path', '-Wl,-rpath,/usr/lib']
	shared_lib = os.path.join(heclib, 'macos', 'libhecdss.dylib')

elif sys.platform.startswith('win'):
	print("*** Platform *** WINDOWS ***")

	# hecdss.lib (import library) is generated from hecdss.def at build time
	library_dirs_list = [os.path.join(heclib, 'windows')]
	shared_lib = os.path.join(heclib, 'windows', 'hecdss.dll')

else:
	raise RuntimeError(f"Unsupported platform {sys.platform}")


class build_ext_hecdss(build_ext):
	''' bundles the hecdss shared library next to the extension module '''

	def build_extensions(self):
		if sys.platform.startswith('win'):
			self.compiler.initialize()
			win_dir = os.path.join(heclib, 'windows')
			self.compiler.spawn([self.compiler.lib, '/nologo', '/machine:x64',
				'/def:' + os.path.join(win_dir, 'hecdss.def'),
				'/out:' + os.path.join(win_dir, 'hecdss.lib')])
		super().build_extensions()

	def run(self):
		super().run()
		for ext in self.extensions:
			ext_dir = os.path.dirname(self.get_ext_fullpath(ext.name))
			os.makedirs(ext_dir, exist_ok=True)
			shutil.copy2(shared_lib, ext_dir)


extension = [
	Extension("pyheclib._core",
		sources = sources_list,
		libraries = libraries_list,
		define_macros = macros_list,
		include_dirs = include_dirs_list,
		library_dirs = library_dirs_list,
		extra_compile_args = compiler_arg_list,
		extra_link_args = linker_arg_list,
	),
]

setup(
	python_requires='>=3.9',
	version='0.4.1',
	name='pyheclib',
	description='Read and write HEC-DSS version 7 files from Python',
	long_description=open(os.path.join(root, 'readme.md'), encoding='utf-8').read(),
	long_description_content_type='text/markdown',
	url='https://github.com/nzahasan/pyheclib',
	project_urls={'Documentation': 'https://nzahasan.github.io/pyheclib'},
	license='MIT',
	packages=['pyheclib'],
	package_data={'pyheclib': ['*.so', '*.dylib', '*.dll']},
	install_requires=['numpy', 'pandas'],
	cmdclass={'build_ext': build_ext_hecdss},
	ext_modules=cythonize(extension, language_level='3', include_path=['src']),
)
