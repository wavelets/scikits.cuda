#!/usr/bin/env python

"""
Utility functions.
"""

import sys
import ctypes
import os
import re
import subprocess
import struct

try:
    import elftools
except ImportError:
    import re

    
    def get_soname(filename):
        """
        Retrieve SONAME of shared library.

        Parameters
        ----------
        filename : str
            Full path to shared library.

        Returns
        -------
        soname : str
            SONAME of shared library.

        Notes
        -----
        This function uses the `objdump` system command on linux and
        'otool' on Mac OS X (darwin).
        
        """
        if sys.platform == 'darwin':
            cmds = ['otool', '-L', filename]
        else:
            # Fallback to linux... what about windows?
            cmds = ['objdump', '-p', filename]

        try:
            p = subprocess.Popen(cmds, stdout=subprocess.PIPE)
            out = p.communicate()[0]
        except:
            raise RuntimeError('error executing {0}'.format(cmds))

        if sys.platform == 'darwin':
            result = re.search('^\s@rpath/(lib.+.dylib)', out, re.MULTILINE)
        else:
            result = re.search('^\s+SONAME\s+(.+)$',out,re.MULTILINE)
        
        if result:
            return result.group(1)
        else:
            # No SONAME found:
            raise RuntimeError('no library name found for {0}'.format(
                (filename,)))

else:
    import ctypes
    import elftools.elf.elffile as elffile
    import elftools.construct.macros as macros
    import elftools.elf.structs as structs

    def get_soname(filename):
        """
        Retrieve SONAME of shared library.

        Parameters
        ----------
        filename : str
            Full path to shared library.

        Returns
        -------
        soname : str
            SONAME of shared library.

        Notes
        -----
        This function uses the pyelftools [ELF] package.

        References
        ----------
        .. [ELF] http://pypi.python.org/pypi/pyelftools
        
        """

        stream = open(filename, 'rb')
        f = elffile.ELFFile(stream)
        dynamic = f.get_section_by_name('.dynamic')
        dynstr = f.get_section_by_name('.dynstr')

        # Handle libraries built for different machine architectures:         
        if f.header['e_machine'] == 'EM_X86_64':
            st = structs.Struct('Elf64_Dyn',
                                macros.ULInt64('d_tag'),
                                macros.ULInt64('d_val'))
        elif f.header['e_machine'] == 'EM_386':
            st = structs.Struct('Elf32_Dyn',
                                macros.ULInt32('d_tag'),
                                macros.ULInt32('d_val'))
        else:
            raise RuntimeError('unsupported machine architecture')

        entsize = dynamic['sh_entsize']
        for k in xrange(dynamic['sh_size']/entsize):
            result = st.parse(dynamic.data()[k*entsize:(k+1)*entsize])

            # The following value for the SONAME tag is specified in elf.h:  
            if result.d_tag == 14:
                return dynstr.get_string(result.d_val)

        # No SONAME found:
        return ''

def find_lib_path(name):
    """
    Find full path of a shared library.

    Parameter
    ---------
    name : str
        Link name of library, e.g., cublas for libcublas.so.*.

    Returns
    -------
    path : str
        Full path to library.

    Notes
    -----
    Code adapted from ctyles.util module.

    """

    uname = os.uname()[4]
    if uname.startswith("arm"):
        uname = "arm"
    if struct.calcsize('l') == 4:
        machine = uname + '-32'
    else:
        machine = uname + '-64'
    mach_map = {
        'x86_64-64': 'libc6,x86-64',
        'ppc64-64': 'libc6,64bit',
        'sparc64-64': 'libc6,64bit',
        's390x-64': 'libc6,64bit',
        'ia64-64': 'libc6,IA-64',
        'arm-32': 'libc6(,hard-float)?',
        }
    abi_type = mach_map.get(machine, 'libc6')
    expr = r'\s+lib%s\.[^\s]+\s+\(%s.*\=\>\s(.+)' % (re.escape(name), abi_type)
    f = os.popen('/sbin/ldconfig -p 2>/dev/null')
    try:
        data = f.read()
    finally:
        f.close()
    res = re.search(expr, data)
    if not res:
        return None
    return res.group(1)
