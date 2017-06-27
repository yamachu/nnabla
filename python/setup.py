# Copyright (c) 2017 Sony Corporation. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

'''
Python API setup script.

This hasn't been designed well yet. Polishing it is future developement.
The current improvement plan is as following:

* Cythonize before publishing. Users do not use Cython, instead just use
generated C++ files to build extensions.

* Remove hard-coded relative paths for library link. Maybe the solution will be
  install NNabla C++ library in order to put them into folders path of which
  are set.
'''
from setuptools import setup
from distutils.extension import Extension
import os
import shutil
import sys
from collections import namedtuple
import copy

setup_requires = [
    'numpy>=1.12.0',
    'Cython>=0.24',  # Requires python-dev.
]

install_requires = setup_requires + [
    'contextlib2',
    'enum',
    'futures',
    'h5py',
    'protobuf',
    'scikit-image',
    'scipy',
    'tqdm',
]

LibInfo = namedtuple('LibInfo', ['file_name', 'path', 'name', 'export_lib'])
ExtConfig = namedtuple('ExtConfig',
                       ['package_dir', 'packages', 'package_data',
                        'ext_modules', 'ext_opts'])


def get_libinfo():
    from ConfigParser import ConfigParser

    # Parse setup.cfg
    path_cfg = os.path.join(os.path.dirname(__file__), "setup.cfg")
    if not os.path.isfile(path_cfg):
        raise ValueError(
            "`setup.cfg` does not exist. Read installation document and install using CMake.")
    cfgp = ConfigParser()
    cfgp.read(path_cfg)

    # Read NNabla lib info
    if sys.platform == 'win32':
        binary_dir = cfgp.get("cmake", "binary_dir")
        for root, dirs, files in os.walk(os.path.join(binary_dir, 'bin')):
            for file in files:
                if os.path.splitext(file)[1] == '.lib':
                    export_lib = os.path.join(root, file)

        lib = LibInfo(cfgp.get("cmake", "target_file_name"),
                      cfgp.get("cmake", "target_file"),
                      cfgp.get("cmake", "target_name"),
                      export_lib)
    else:
        lib = LibInfo(cfgp.get("cmake", "target_file_name"),
                      cfgp.get("cmake", "target_file"),
                      cfgp.get("cmake", "target_name"),
                      '')
    print "Library name:", lib.name
    print "Library file name:", lib.file_name
    print "Library file:", lib.path
    print "Export Library", lib.export_lib

    return lib


def get_cpu_extopts(lib):
    import numpy as np
    include_dir = os.path.realpath(os.path.join(
        os.path.dirname(__file__), '../include'))
    ext_opts = dict(
        include_dirs=[include_dir, np.get_include()],
        libraries=[lib.name],
        library_dirs=[os.path.dirname(lib.path)],
        language="c++",
        # The below definition breaks build. Use -Wcpp instead.
        # define_macros=[('NPY_NO_DEPRECATED_API', 'NPY_1_7_API_VERSION')],
    )
    if sys.platform != 'win32':
        extra_compile_args = [
                '-std=c++11', '-Wno-sign-compare', '-Wno-unused-function', '-Wno-cpp']
        if sys.platform == 'darwin':
            extra_compile_args.append('-stdlib=libc++')
        ext_opts.update(dict(
            extra_compile_args=extra_compile_args,
            runtime_library_dirs=['$ORIGIN/'],
        ))
    else:
        ext_opts.update(dict(extra_compile_args=['/W0']))
    return ext_opts


def cpu_config(root_dir, lib):
    src_dir = os.path.join(root_dir, 'src')
    ext_opts = get_cpu_extopts(lib)
    path_pkg = os.path.join(src_dir, 'nnabla')
    package_dir = {'': src_dir,
                   'nnabla.extensions.cpu': os.path.join(src_dir, 'extensions/cpu')}
    packages = ['nnabla',
                'nnabla.contrib',
                'nnabla.utils',
                'nnabla.utils.cli',
                'nnabla.extensions',
                'nnabla.extensions.cpu']

    # Move shared libs to module
    # http://stackoverflow.com/questions/6191942/distributing-pre-built-libraries-with-python-modules
    # Packaging shared lib
    # http://stackoverflow.com/questions/6191942/distributing-pre-built-libraries-with-python-modules
    shutil.copyfile(lib.path, os.path.join(path_pkg, lib.file_name))
    package_data = {"nnabla": [lib.file_name, 'nnabla.conf']}
    if os.path.exists(lib.export_lib):
        shutil.copyfile(lib.export_lib, os.path.join(
            path_pkg, os.path.basename(lib.export_lib)))
        package_data["nnabla"].append(os.path.basename(lib.export_lib))

    for d in ['include', 'doc', 'build-tools']:
        path_d = os.path.join(path_pkg, 'dev', d)
        shutil.rmtree(path_d, ignore_errors=True)
        shutil.copytree(os.path.join(root_dir, '..', d), path_d)
        for dirname, dirnames, filenames in os.walk(path_d):
            for filename in filenames:
                package_data["nnabla"].append(os.path.join(
                    'dev', d, dirname[len(path_d) + 1:], filename))

    ext_modules = [
        Extension("nnabla._variable",
                  [os.path.join(path_pkg, '_variable.pyx')],
                  **ext_opts),
        Extension("nnabla.function",
                  [os.path.join(path_pkg, 'function.pyx')],
                  **ext_opts),
        Extension("nnabla.solver",
                  [os.path.join(path_pkg, 'solver.pyx')],
                  **ext_opts),
        Extension("nnabla._init",
                  [os.path.join(path_pkg, '_init.pyx')],
                  **ext_opts),
        Extension("nnabla._nd_array",
                  [os.path.join(path_pkg, '_nd_array.pyx')],
                  **ext_opts),
    ]

    return ExtConfig(package_dir, packages, package_data,
                     ext_modules, ext_opts)


def get_setup_config(root_dir, lib):
    cpu_ext = cpu_config(root_dir, lib)
    packages = cpu_ext.packages
    package_dir = copy.deepcopy(cpu_ext.package_dir)
    package_data = copy.deepcopy(cpu_ext.package_data)
    ext_modules = cpu_ext.ext_modules

    exec(open(os.path.join(root_dir, 'src', 'nnabla', '_version.py')).read())

    pkg_info = dict(
        name="nnabla",
        description='Neural Network Libraries',
        version=__version__,
        author_email=__email__,
        url="https://github.com/sony/nnabla",
        license='Apache Licence 2.0',
        classifiers=[
                'Development Status :: 4 - Beta',
                'Intended Audience :: Developers',
                'Intended Audience :: Education',
                'Intended Audience :: Science/Research',
                'Topic :: Scientific/Engineering',
                'Topic :: Scientific/Engineering :: Artificial Intelligence',
                'License :: OSI Approved :: Apache Software License',
                'Programming Language :: Python :: 2.7',
                'Operating System :: Microsoft :: Windows',
                'Operating System :: POSIX :: Linux',
            ],
        keywords="deep learning artificial intelligence machine learning neural network",
        python_requires='>=2.7, <3',
    )
    return pkg_info, ExtConfig(package_dir, packages, package_data, ext_modules, {})


if __name__ == '__main__':
    from Cython.Build import cythonize
    lib = get_libinfo()

    root_dir = os.path.realpath(os.path.dirname(__file__))
    pkg_info, cfg = get_setup_config(root_dir, lib)

    # Cythonize
    ext_modules = cythonize(cfg.ext_modules, compiler_directives={
                            "embedsignature": True})

    # Setup
    setup(
        entry_points={"console_scripts":
                      ["nnabla_cli=nnabla.utils.cli.cli:main"]},
        setup_requires=setup_requires,
        install_requires=install_requires,
        ext_modules=ext_modules,
        package_dir=cfg.package_dir,
        packages=cfg.packages,
        package_data=cfg.package_data,
        **pkg_info)

    os.unlink(os.path.join(root_dir, 'src', 'nnabla', lib.file_name))
    shutil.rmtree(os.path.join(root_dir, 'src',
                               'nnabla', 'dev'), ignore_errors=True)
