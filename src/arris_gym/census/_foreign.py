"""Fixed CPython 3.12 Linux standard-library roots admitted by reach (ADR-0012).

Recorded from the worker interpreter's sys.stdlib_module_names whose root
has an import spec. Never discovers or imports a program's modules. The
list governs module roots, not the existence of an attribute or whether
sandbox restrictions let a call complete. Both architectures use this list.
"""

from typing import Final

# Membership only; no order from this set reaches a report.
STDLIB_ROOTS: Final = frozenset(
    """
__future__ _abc _aix_support _ast _asyncio _bisect _blake2 _bz2 _codecs _codecs_cn
_codecs_hk _codecs_iso2022 _codecs_jp _codecs_kr _codecs_tw _collections _collections_abc
_compat_pickle _compression _contextvars _crypt _csv _ctypes _curses _curses_panel _datetime
_dbm _decimal _elementtree _frozen_importlib _frozen_importlib_external _functools _gdbm
_hashlib _heapq _imp _io _json _locale _lsprof _lzma _markupbase _md5 _multibytecodec
_multiprocessing _opcode _operator _osx_support _pickle _posixshmem _posixsubprocess _py_abc
_pydatetime _pydecimal _pyio _pylong _queue _random _sha1 _sha2 _sha3 _signal _sitebuiltins
_socket _sqlite3 _sre _ssl _stat _statistics _string _strptime _struct _symtable _thread
_threading_local _tkinter _tokenize _tracemalloc _typing _warnings _weakref _weakrefset
_zoneinfo abc aifc antigravity argparse array ast asyncio atexit audioop base64 bdb binascii
bisect builtins bz2 cProfile calendar cgi cgitb chunk cmath cmd code codecs codeop
collections colorsys compileall concurrent configparser contextlib contextvars copy copyreg
crypt csv ctypes curses dataclasses datetime dbm decimal difflib dis doctest email encodings
enum errno faulthandler fcntl filecmp fileinput fnmatch fractions ftplib functools gc
genericpath getopt getpass gettext glob graphlib grp gzip hashlib heapq hmac html http
imaplib imghdr importlib inspect io ipaddress itertools json keyword linecache locale
logging lzma mailbox mailcap marshal math mimetypes mmap modulefinder multiprocessing netrc
nntplib ntpath nturl2path numbers opcode operator optparse os ossaudiodev pathlib pdb pickle
pickletools pipes pkgutil platform plistlib poplib posix posixpath pprint profile pstats pty
pwd py_compile pyclbr pydoc pydoc_data pyexpat queue quopri random re readline reprlib
resource rlcompleter runpy sched secrets select selectors shelve shlex shutil signal site
smtplib sndhdr socket socketserver spwd sqlite3 sre_compile sre_constants sre_parse ssl stat
statistics string stringprep struct subprocess sunau symtable sys sysconfig syslog tabnanny
tarfile telnetlib tempfile termios textwrap this threading time timeit tkinter token
tokenize tomllib trace traceback tracemalloc tty turtle types typing unicodedata unittest
urllib uu uuid venv warnings wave weakref webbrowser wsgiref xdrlib xml xmlrpc zipapp
zipfile zipimport zlib zoneinfo
""".split()  # noqa: SIM905
)
