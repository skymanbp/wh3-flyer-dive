#!/usr/bin/env python3
"""
PackFile — WH3 Pack File Swiss Army Knife
==========================================
A pure-Python tool for reading, extracting, creating, searching, and merging
Total War: Warhammer III .pack files. No RPFM needed.

Supports PFH5 (WH2-era) and PFH6 (WH3-native) formats.

Usage:
    python packfile.py info     <pack>                    Show pack metadata
    python packfile.py list     <pack> [--filter PATTERN]  List files in pack
    python packfile.py extract  <pack> <output> [--filter] Extract files
    python packfile.py search   <dir>  <pattern>           Search across packs
    python packfile.py create   <pack> <source_dir>        Create pack from dir
    python packfile.py merge    <out>  <pack1> <pack2>...  Merge multiple packs
    python packfile.py db-read  <pack> <table_path>        Read DB table as TSV
    python packfile.py assets   <pack> [--type TYPE]       List assets by type

Author: Lore Disasters Tool Suite
"""
import struct
import os
import errno
import ntpath
import sys
import re
import fnmatch
import argparse
import json
import secrets
import stat
import threading
from contextlib import contextmanager
from pathlib import Path
from collections import defaultdict

# =============================================================================
# CONSTANTS
# =============================================================================

# Pack types (bitmask)
PACK_TYPE_BOOT      = 0
PACK_TYPE_RELEASE   = 1
PACK_TYPE_PATCH     = 2
PACK_TYPE_MOD       = 3
PACK_TYPE_MOVIE     = 4
PACK_TYPE_NAMES = {0: "Boot", 1: "Release", 2: "Patch", 3: "Mod", 4: "Movie"}

# Header bitmask layout flags (above the pack-type nibble).
PFH_FLAG_INDEX_TIMESTAMPS = 0x40   # each index entry: size, u32 timestamp, ...
PFH_FLAG_ENCRYPTED_INDEX  = 0x80
PFH_FLAG_EXTENDED_HEADER  = 0x100

# Supported magic bytes
SUPPORTED_FORMATS = {b"PFH5": 5, b"PFH6": 6, b"PFH4": 4}

# Asset type detection
ASSET_TYPES = {
    "model":   [".rigid_model_v2", ".wsmodel", ".model"],
    "texture": [".dds", ".png", ".tga"],
    "sound":   [".bnk", ".wem", ".wav", ".ogg"],
    "anim":    [".anim", ".matched_combat", ".anim_fragment"],
    "ui":      [".twui", ".layout"],
    "script":  [".lua"],
    "db":      [],  # DB tables detected by path, not extension
    "loc":     [".loc"],
    "video":   [".ca_vp8", ".mp4", ".webm"],
    "vfx":     [".vfx", ".particle"],
    "text":    [".xml", ".json", ".tsv", ".csv", ".txt"],
}

# DB table path patterns
DB_PATH_PATTERN = re.compile(r'^db/([^/]+)/.*$')

# Python 3.13 added ntpath.isreserved(), but this standalone tool also runs on
# Python 3.12. Keep the equivalent component-level check local and deterministic.
_WINDOWS_RESERVED_CHARS = frozenset(
    {chr(i) for i in range(32)} | {'"', '*', ':', '<', '>', '?', '|', '/', '\\'}
)
_WINDOWS_RESERVED_NAMES = frozenset(
    {'CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$'}
    | {f'COM{suffix}' for suffix in '123456789¹²³'}
    | {f'LPT{suffix}' for suffix in '123456789¹²³'}
)
_POSIX_STAGE_DIRECTORY = '.pack_extract_transactions'


def _is_windows_reserved_component(name):
    """Match Windows reserved-component rules without a Python 3.13 dependency."""
    if name[-1:] in ('.', ' '):
        return name not in ('.', '..')
    if _WINDOWS_RESERVED_CHARS.intersection(name):
        return True
    return name.partition('.')[0].rstrip(' ').upper() in _WINDOWS_RESERVED_NAMES


def _file_identity(path):
    """Return a stable filesystem identity for containment revalidation."""
    info = Path(path).stat()
    return info.st_dev, info.st_ino


def _validated_extract_parts(entry_path):
    """Parse one archive path into safe host-independent components."""
    if not isinstance(entry_path, str) or not entry_path or '\x00' in entry_path:
        raise ValueError(f"unsafe pack entry path: {entry_path!r}")

    normalized = entry_path.replace('\\', '/')
    drive, _tail = ntpath.splitdrive(entry_path)
    parts = normalized.split('/')
    drive_prefix = re.match(r'^[A-Za-z]:', normalized)
    if drive or drive_prefix or normalized.startswith('/') or '..' in parts:
        raise ValueError(f"unsafe pack entry path: {entry_path!r}")

    useful_parts = tuple(part for part in parts if part not in ('', '.'))
    if (
        not useful_parts
        or _POSIX_STAGE_DIRECTORY in useful_parts
        or any(_is_windows_reserved_component(part) for part in useful_parts)
    ):
        raise ValueError(f"unsafe pack entry path: {entry_path!r}")
    return useful_parts


def _create_windows_directory_component(directory):
    """Create one Windows directory component without recursive path traversal."""
    import ctypes
    from ctypes import wintypes

    error_already_exists = 183
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    create_directory = kernel32.CreateDirectoryW
    create_directory.argtypes = (wintypes.LPCWSTR, wintypes.LPVOID)
    create_directory.restype = wintypes.BOOL
    if create_directory(str(directory), None):
        return
    error = ctypes.get_last_error()
    if error != error_already_exists:
        raise ctypes.WinError(error)


@contextmanager
def _locked_windows_directory_chain(root, parent):
    """Create and pin the selected root and archive parents without reparses.

    Every caller-supplied output component is created from the volume anchor one at a
    time, then opened with FILE_FLAG_OPEN_REPARSE_POINT and without delete sharing.
    The selected root is therefore authoritative before any path is resolved. Archive
    components are created only while all output-root handles remain pinned.
    """
    if os.name != 'nt':
        yield
        return

    import ctypes
    from ctypes import wintypes

    file_traverse = 0x0020
    file_read_attributes = 0x0080
    file_share_read = 0x00000001
    file_share_write = 0x00000002
    open_existing = 3
    file_attribute_directory = 0x00000010
    file_attribute_reparse_point = 0x00000400
    file_flag_backup_semantics = 0x02000000
    file_flag_open_reparse_point = 0x00200000
    invalid_handle_value = ctypes.c_void_p(-1).value

    class ByHandleFileInformation(ctypes.Structure):
        _fields_ = [
            ('file_attributes', wintypes.DWORD),
            ('creation_time', wintypes.FILETIME),
            ('last_access_time', wintypes.FILETIME),
            ('last_write_time', wintypes.FILETIME),
            ('volume_serial_number', wintypes.DWORD),
            ('file_size_high', wintypes.DWORD),
            ('file_size_low', wintypes.DWORD),
            ('number_of_links', wintypes.DWORD),
            ('file_index_high', wintypes.DWORD),
            ('file_index_low', wintypes.DWORD),
        ]

    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    create_file.restype = wintypes.HANDLE
    get_information = kernel32.GetFileInformationByHandle
    get_information.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(ByHandleFileInformation),
    )
    get_information.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL

    anchor = Path(root.anchor)
    if not root.anchor or not root.is_absolute():
        raise ValueError(f'unsafe extraction root: not absolute: {root}')
    output_parts = root.relative_to(anchor).parts
    archive_parts = parent.relative_to(root).parts
    root_index = len(output_parts)

    chain = [anchor]
    current = anchor
    for component in output_parts + archive_parts:
        current = current / component
        chain.append(current)

    handles = []
    root_identity = None
    try:
        for index, directory in enumerate(chain):
            if index > 0:
                _create_windows_directory_component(directory)

            handle = create_file(
                str(directory),
                file_traverse | file_read_attributes,
                file_share_read | file_share_write,
                None,
                open_existing,
                file_flag_backup_semantics | file_flag_open_reparse_point,
                None,
            )
            if handle == invalid_handle_value:
                raise ctypes.WinError(ctypes.get_last_error())

            handles.append(handle)
            information = ByHandleFileInformation()
            if not get_information(handle, ctypes.byref(information)):
                raise ctypes.WinError(ctypes.get_last_error())
            attributes = information.file_attributes
            scope = 'extraction root' if index <= root_index else 'pack entry path'
            if attributes & file_attribute_reparse_point:
                raise ValueError(f'unsafe {scope}: reparse directory {directory}')
            if not attributes & file_attribute_directory:
                raise ValueError(f'unsafe {scope}: non-directory {directory}')

            identity = _file_identity(_windows_handle_path(handle))
            if _file_identity(directory) != identity:
                raise ValueError(f'unsafe {scope} changed: {directory}')
            if index == root_index:
                root_identity = identity

        yield handles[root_index], handles[-1], root_identity
    finally:
        for handle in reversed(handles):
            close_handle(handle)


def _posix_directory_identity_at_path(path):
    """Return one no-follow directory identity, or None after namespace drift."""
    try:
        info = os.stat(path, follow_symlinks=False)
    except (FileNotFoundError, NotADirectoryError):
        return None
    if not stat.S_ISDIR(info.st_mode):
        return None
    return info.st_dev, info.st_ino


@contextmanager
def _locked_posix_directory_chain(root, parent_parts):
    """Create and pin the selected POSIX root plus archive-controlled parents.

    Traversal starts at the filesystem anchor and opens every caller-supplied output
    component with O_NOFOLLOW before archive data is read or published. The selected
    root is flocked for cooperating extractors. Lexical identity is rechecked after
    every open because POSIX descriptors pin inodes but do not pin directory names.

    Created parents are monotonic: failed extraction may leave them empty. POSIX has
    no atomic remove-if-inode primitive, so pathname cleanup could delete a foreign
    replacement installed after a separate identity check.
    """
    try:
        import fcntl
    except ImportError as exc:
        raise OSError(
            errno.ENOTSUP,
            'secure POSIX extraction requires advisory flock support',
        ) from exc

    open_flags = os.O_RDONLY
    if hasattr(os, 'O_DIRECTORY'):
        open_flags |= os.O_DIRECTORY
    if hasattr(os, 'O_NOFOLLOW'):
        open_flags |= os.O_NOFOLLOW

    anchor = Path(root.anchor)
    if not root.anchor or not root.is_absolute():
        raise ValueError(f'unsafe extraction root: not absolute: {root}')
    output_parts = root.relative_to(anchor).parts
    all_parts = output_parts + tuple(parent_parts)
    root_index = len(output_parts)

    handles = []
    root_fd = None
    root_identity = None
    current_path = anchor
    try:
        current_fd = os.open(anchor, open_flags)
        handles.append(current_fd)
        current_info = os.fstat(current_fd)
        current_identity = current_info.st_dev, current_info.st_ino
        if _posix_directory_identity_at_path(current_path) != current_identity:
            raise ValueError(f'unsafe extraction root changed: {current_path}')
        if root_index == 0:
            root_fd = current_fd
            root_identity = current_identity
            fcntl.flock(root_fd, fcntl.LOCK_EX)

        for index, component in enumerate(all_parts, start=1):
            scope_is_root = index <= root_index
            scope_label = 'extraction root' if scope_is_root else 'pack entry path'
            if _posix_directory_identity_at_path(current_path) != current_identity:
                raise ValueError(f'unsafe {scope_label} changed: {current_path}')

            try:
                os.mkdir(component, 0o777, dir_fd=current_fd)
            except FileExistsError:
                pass  # Existing entries are opened O_NOFOLLOW immediately below.
            try:
                child_fd = os.open(component, open_flags, dir_fd=current_fd)
            except OSError as exc:
                if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                    raise ValueError(
                        f'unsafe {scope_label}: component {component!r}'
                    ) from exc
                raise

            handles.append(child_fd)
            child_info = os.fstat(child_fd)
            child_identity = child_info.st_dev, child_info.st_ino
            child_path = current_path / component
            if _posix_directory_identity_at_path(child_path) != child_identity:
                raise ValueError(f'unsafe {scope_label} changed: {child_path}')

            current_fd = child_fd
            current_identity = child_identity
            current_path = child_path

            if index == root_index:
                root_fd = child_fd
                root_identity = child_identity
                fcntl.flock(root_fd, fcntl.LOCK_EX)
                if _posix_directory_identity_at_path(root) != root_identity:
                    raise ValueError(f'unsafe extraction root changed: {root}')

        if root_fd is None or root_identity is None:
            raise ValueError(f'unsafe extraction root could not be pinned: {root}')
        yield root_fd, current_fd, root_identity
    finally:
        for handle in reversed(handles):
            os.close(handle)


def _windows_handle_path(handle):
    """Resolve an open Windows handle to the directory entry it actually names."""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    get_final_path = kernel32.GetFinalPathNameByHandleW
    get_final_path.argtypes = (
        wintypes.HANDLE,
        wintypes.LPWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
    )
    get_final_path.restype = wintypes.DWORD
    needed = get_final_path(handle, None, 0, 0)
    if not needed:
        raise ctypes.WinError(ctypes.get_last_error())
    buffer = ctypes.create_unicode_buffer(needed + 1)
    written = get_final_path(handle, buffer, len(buffer), 0)
    if not written or written >= len(buffer):
        raise ctypes.WinError(ctypes.get_last_error())
    path = buffer.value
    if path.startswith('\\\\?\\UNC\\'):
        path = '\\\\' + path[8:]
    elif path.startswith('\\\\?\\'):
        path = path[4:]
    return Path(path)


def _delete_windows_handle_on_close(handle):
    """Mark exactly one open Windows file handle for deletion on close."""
    import ctypes
    from ctypes import wintypes

    class FileDispositionInfo(ctypes.Structure):
        _fields_ = [('delete_file', wintypes.BOOL)]

    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    set_information = kernel32.SetFileInformationByHandle
    set_information.argtypes = (
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    )
    set_information.restype = wintypes.BOOL
    information = FileDispositionInfo(True)
    if set_information(
        handle, 4, ctypes.byref(information), ctypes.sizeof(information)
    ):
        return

    error = ctypes.get_last_error()
    if error != 5:  # ERROR_ACCESS_DENIED
        raise ctypes.WinError(error)

    # A copied READONLY attribute blocks FileDispositionInfo. Clear only the
    # operation-owned temp's user-visible attributes, then retry exact-handle
    # deletion; no archive-controlled pathname is followed during cleanup.
    _set_windows_handle_attributes(handle, None)
    if not set_information(
        handle, 4, ctypes.byref(information), ctypes.sizeof(information)
    ):
        raise ctypes.WinError(ctypes.get_last_error())


def _close_windows_handle(handle):
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL
    if not close_handle(handle):
        raise ctypes.WinError(ctypes.get_last_error())


def _truncate_windows_handle(handle):
    """Erase one operation-owned inode before removing its directory entry."""
    import ctypes
    from ctypes import wintypes

    file_begin = 0
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    set_pointer = kernel32.SetFilePointerEx
    set_pointer.argtypes = (
        wintypes.HANDLE,
        ctypes.c_longlong,
        ctypes.POINTER(ctypes.c_longlong),
        wintypes.DWORD,
    )
    set_pointer.restype = wintypes.BOOL
    set_end = kernel32.SetEndOfFile
    set_end.argtypes = (wintypes.HANDLE,)
    set_end.restype = wintypes.BOOL

    if not set_pointer(handle, 0, None, file_begin):
        raise ctypes.WinError(ctypes.get_last_error())
    if not set_end(handle):
        raise ctypes.WinError(ctypes.get_last_error())


def _dispose_windows_handle(handle, *, delete_on_close, primary_error=None):
    """Release one owned handle without replacing an in-flight primary error."""
    cleanup_errors = []
    if delete_on_close:
        # Windows share modes do not prevent hardlink creation. Truncate through
        # the authoritative handle first so failed archive bytes cannot survive
        # under another name, then remove this operation's directory entry.
        try:
            _truncate_windows_handle(handle)
        except BaseException as exc:
            cleanup_errors.append(exc)
        try:
            _delete_windows_handle_on_close(handle)
        except BaseException as exc:
            cleanup_errors.append(exc)
    try:
        _close_windows_handle(handle)
    except BaseException as exc:
        cleanup_errors.append(exc)

    if not cleanup_errors:
        return
    detail = '; '.join(str(error) for error in cleanup_errors)
    if primary_error is not None:
        if hasattr(primary_error, 'add_note'):
            primary_error.add_note(f'Windows extraction cleanup also failed: {detail}')
        return
    raise cleanup_errors[0]


def _windows_path_attributes(path):
    """Return current Windows attributes, or None when the path is absent."""
    import ctypes
    from ctypes import wintypes

    invalid_file_attributes = 0xFFFFFFFF
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    get_attributes = kernel32.GetFileAttributesW
    get_attributes.argtypes = (wintypes.LPCWSTR,)
    get_attributes.restype = wintypes.DWORD
    attributes = get_attributes(str(path))
    if attributes == invalid_file_attributes:
        error = ctypes.get_last_error()
        if error in (2, 3):  # ERROR_FILE_NOT_FOUND / ERROR_PATH_NOT_FOUND
            return None
        raise ctypes.WinError(error)
    return attributes


def _set_windows_handle_attributes(handle, existing_attributes):
    """Apply stable user-visible attributes to the replacement before commit."""
    import ctypes
    from ctypes import wintypes

    class FileBasicInfo(ctypes.Structure):
        _fields_ = [
            ('creation_time', ctypes.c_longlong),
            ('last_access_time', ctypes.c_longlong),
            ('last_write_time', ctypes.c_longlong),
            ('change_time', ctypes.c_longlong),
            ('file_attributes', wintypes.DWORD),
        ]

    file_attribute_normal = 0x00000080
    # Preserve metadata that is meaningful on an ordinary replacement file.
    # Reparse, directory, sparse, compressed, encrypted and temporary flags are
    # object/layout properties and must not be copied to a newly written payload.
    preservable = 0x00000001 | 0x00000002 | 0x00000004 | 0x00000020 | 0x00002000
    desired = (existing_attributes or 0) & preservable
    if desired == 0:
        desired = file_attribute_normal

    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    get_information = kernel32.GetFileInformationByHandleEx
    get_information.argtypes = (
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    )
    get_information.restype = wintypes.BOOL
    set_information = kernel32.SetFileInformationByHandle
    set_information.argtypes = (
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    )
    set_information.restype = wintypes.BOOL

    information = FileBasicInfo()
    if not get_information(
        handle, 0, ctypes.byref(information), ctypes.sizeof(information)
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    information.file_attributes = desired
    if not set_information(
        handle, 0, ctypes.byref(information), ctypes.sizeof(information)
    ):
        raise ctypes.WinError(ctypes.get_last_error())


def _create_windows_temp_handle(parent, expected_parent_identity):
    """Create and exclusively pin a temp before archive bytes are written."""
    import ctypes
    from ctypes import wintypes

    generic_write = 0x40000000
    delete_access = 0x00010000
    file_read_attributes = 0x0080
    create_new = 1
    file_attribute_normal = 0x00000080
    error_file_exists = 80
    error_already_exists = 183
    invalid_handle_value = ctypes.c_void_p(-1).value

    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    create_file.restype = wintypes.HANDLE

    for _attempt in range(128):
        name = '.pack_extract_' + secrets.token_hex(8)
        handle = create_file(
            str(parent / name),
            generic_write | delete_access | file_read_attributes,
            # No share access prevents unrelated read/write opens and relocation.
            # Hardlink creation is still possible on Windows, so failed cleanup
            # truncates this inode through the authoritative handle before delete.
            0,
            None,
            create_new,
            file_attribute_normal,
            None,
        )
        if handle == invalid_handle_value:
            error = ctypes.get_last_error()
            if error in (error_file_exists, error_already_exists):
                continue
            raise ctypes.WinError(error)

        try:
            actual_path = _windows_handle_path(handle)
            if _file_identity(actual_path.parent) != expected_parent_identity:
                raise ValueError(f'unsafe extraction temp path changed: {actual_path}')
        except BaseException as exc:
            _dispose_windows_handle(
                handle, delete_on_close=True, primary_error=exc
            )
            raise
        return handle, name
    raise FileExistsError('could not allocate a unique extraction temporary file')


def _windows_handle_is_destination(handle, parent_identity, final_name):
    """Detect a completed rename even if Python is interrupted before bookkeeping."""
    try:
        actual_path = _windows_handle_path(handle)
        actual_parent_identity = _file_identity(actual_path.parent)
    except (OSError, ValueError):
        return False
    return (
        actual_parent_identity == parent_identity
        and actual_path.name.casefold() == final_name.casefold()
    )


def _write_windows_handle(handle, data):
    """Write bytes through a duplicate while retaining the authoritative handle."""
    import ctypes
    import msvcrt
    from ctypes import wintypes

    duplicate_same_access = 0x00000002
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    current_process = kernel32.GetCurrentProcess
    current_process.restype = wintypes.HANDLE
    duplicate_handle = kernel32.DuplicateHandle
    duplicate_handle.argtypes = (
        wintypes.HANDLE,
        wintypes.HANDLE,
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.HANDLE),
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD,
    )
    duplicate_handle.restype = wintypes.BOOL
    flush_file = kernel32.FlushFileBuffers
    flush_file.argtypes = (wintypes.HANDLE,)
    flush_file.restype = wintypes.BOOL

    process = current_process()
    duplicate = wintypes.HANDLE()
    if not duplicate_handle(
        process,
        handle,
        process,
        ctypes.byref(duplicate),
        0,
        False,
        duplicate_same_access,
    ):
        raise ctypes.WinError(ctypes.get_last_error())

    flags = os.O_WRONLY | getattr(os, 'O_BINARY', 0)
    try:
        fd = msvcrt.open_osfhandle(duplicate.value, flags)
    except BaseException as exc:
        _dispose_windows_handle(
            duplicate.value, delete_on_close=False, primary_error=exc
        )
        raise
    try:
        with os.fdopen(fd, 'wb') as stream:
            fd = None
            stream.write(data)
    finally:
        if fd is not None:
            os.close(fd)
    if not flush_file(handle):
        raise ctypes.WinError(ctypes.get_last_error())


def _rename_windows_handle(handle, parent_handle, final_name):
    """Rename one open temp handle relative to an authoritative parent handle."""
    import ctypes
    from ctypes import wintypes

    if (
        not isinstance(final_name, str)
        or not final_name
        or final_name in ('.', '..')
        or '/' in final_name
        or '\\' in final_name
    ):
        raise ValueError(f'invalid final Windows extraction name: {final_name!r}')

    class IoStatusBlock(ctypes.Structure):
        _fields_ = [
            ('status', ctypes.c_void_p),
            ('information', ctypes.c_size_t),
        ]

    class FileRenameInformation(ctypes.Structure):
        _fields_ = [
            ('replace_if_exists', ctypes.c_ubyte),
            ('root_directory', wintypes.HANDLE),
            ('file_name_length', wintypes.ULONG),
            ('file_name', wintypes.WCHAR * 1),
        ]

    encoded_name = final_name.encode('utf-16-le')
    name_offset = FileRenameInformation.file_name.offset
    buffer = ctypes.create_string_buffer(
        ctypes.sizeof(FileRenameInformation) + len(encoded_name)
    )
    information = FileRenameInformation.from_buffer(buffer)
    # Strict extraction is no-clobber. The kernel resolves the final name relative
    # to the pinned parent and reports a collision atomically if it already exists.
    information.replace_if_exists = False
    information.root_directory = parent_handle
    information.file_name_length = len(encoded_name)
    ctypes.memmove(
        ctypes.addressof(buffer) + name_offset, encoded_name, len(encoded_name)
    )

    # The Win32 wrapper rejected a non-null RootDirectory with ERROR_INVALID_PARAMETER
    # on the supported host. NtSetInformationFile is the verified handle-relative
    # interface for FILE_RENAME_INFORMATION and keeps pathname resolution pinned.
    ntdll = ctypes.WinDLL('ntdll')
    set_information = ntdll.NtSetInformationFile
    set_information.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(IoStatusBlock),
        wintypes.LPVOID,
        wintypes.ULONG,
        ctypes.c_int,
    )
    set_information.restype = ctypes.c_long
    to_dos_error = ntdll.RtlNtStatusToDosError
    to_dos_error.argtypes = (ctypes.c_long,)
    to_dos_error.restype = wintypes.ULONG

    io_status = IoStatusBlock()
    nt_status = set_information(
        handle, ctypes.byref(io_status), buffer, len(buffer), 10
    )
    if nt_status < 0:
        raise ctypes.WinError(to_dos_error(nt_status))


def _open_posix_named_stage(parent_fd):
    """Create an exclusive fallback stage in a reserved same-filesystem directory.

    Some WSL/DrvFS mounts reject O_TMPFILE. The random name is never trusted as the
    commit source: publication still links from the authoritative descriptor. Since
    POSIX cannot safely unlink a mutable name only if it still owns the inode, stage
    residues are retained and failed payloads are truncated through the descriptor.
    """
    directory_flags = os.O_RDONLY
    if hasattr(os, 'O_DIRECTORY'):
        directory_flags |= os.O_DIRECTORY
    if hasattr(os, 'O_NOFOLLOW'):
        directory_flags |= os.O_NOFOLLOW
    if hasattr(os, 'O_CLOEXEC'):
        directory_flags |= os.O_CLOEXEC

    try:
        os.mkdir(_POSIX_STAGE_DIRECTORY, 0o700, dir_fd=parent_fd)
    except FileExistsError:
        # A prior transaction may have created the reserved directory; opening it
        # O_NOFOLLOW below verifies that the existing entry is a real directory.
        pass
    try:
        stage_directory_fd = os.open(
            _POSIX_STAGE_DIRECTORY,
            directory_flags,
            dir_fd=parent_fd,
        )
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.ENOTDIR):
            raise ValueError('unsafe POSIX extraction transaction directory') from exc
        raise

    stage_flags = os.O_RDWR | os.O_CREAT | os.O_EXCL
    if hasattr(os, 'O_NOFOLLOW'):
        stage_flags |= os.O_NOFOLLOW
    if hasattr(os, 'O_CLOEXEC'):
        stage_flags |= os.O_CLOEXEC
    try:
        for _attempt in range(128):
            stage_name = 'stage_' + secrets.token_hex(16)
            try:
                return os.open(
                    stage_name,
                    stage_flags,
                    0o666,
                    dir_fd=stage_directory_fd,
                )
            except FileExistsError:
                continue
    finally:
        os.close(stage_directory_fd)
    raise FileExistsError('could not allocate a unique POSIX extraction stage')


def _open_posix_temp(parent_fd):
    """Create an authoritative same-filesystem payload descriptor.

    Prefer an unnamed Linux inode. Filesystems without O_TMPFILE, notably common
    WSL-mounted Windows drives, use an exclusive named stage whose descriptor—not
    its mutable pathname—is later linked to the final no-clobber destination.
    """
    unsupported = {
        errno.EINVAL,
        errno.EISDIR,
        errno.ENOSYS,
        errno.ENOTSUP,
        errno.EOPNOTSUPP,
    }
    if hasattr(os, 'O_TMPFILE'):
        flags = os.O_RDWR | os.O_TMPFILE
        if hasattr(os, 'O_CLOEXEC'):
            flags |= os.O_CLOEXEC
        try:
            return os.open('.', flags, 0o666, dir_fd=parent_fd)
        except OSError as exc:
            if exc.errno not in unsupported:
                raise
    return _open_posix_named_stage(parent_fd)


def _posix_linkat(old_dir_fd, old_path, new_dir_fd, new_path, flags):
    """Call linkat with explicit errno handling for secure temp publication."""
    import ctypes

    libc = ctypes.CDLL(None, use_errno=True)
    link_at = libc.linkat
    link_at.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
    )
    link_at.restype = ctypes.c_int
    encoded_old = os.fsencode(old_path)
    encoded_new = os.fsencode(new_path)
    if link_at(old_dir_fd, encoded_old, new_dir_fd, encoded_new, flags) == 0:
        return
    error = ctypes.get_errno()
    raise OSError(error, os.strerror(error), os.fsdecode(encoded_new))


def _link_posix_temp(temp_fd, parent_fd, name=None):
    """Give an unnamed Linux temp one verified name under a pinned parent."""
    at_empty_path = 0x1000
    at_symlink_follow = 0x400
    at_fdcwd = getattr(os, 'AT_FDCWD', -100)
    fallback_errors = {
        errno.EACCES,
        errno.EINVAL,
        errno.ENOENT,
        errno.ENOSYS,
        errno.EPERM,
    }

    candidates = [name] if name is not None else [
        '.pack_extract_' + secrets.token_hex(8) for _attempt in range(128)
    ]
    for candidate in candidates:
        try:
            _posix_linkat(
                temp_fd,
                b'',
                parent_fd,
                candidate,
                at_empty_path,
            )
            return candidate
        except OSError as direct_error:
            if direct_error.errno == errno.EEXIST:
                if name is None:
                    continue
                raise
            if direct_error.errno not in fallback_errors:
                raise

        # linkat(AT_EMPTY_PATH) requires CAP_DAC_READ_SEARCH on Linux. Ordinary
        # users publish the same authoritative O_TMPFILE inode through procfs;
        # AT_SYMLINK_FOLLOW follows only the kernel-owned /proc/self/fd handle.
        proc_path = f'/proc/self/fd/{temp_fd}'
        try:
            _posix_linkat(
                at_fdcwd,
                proc_path,
                parent_fd,
                candidate,
                at_symlink_follow,
            )
            return candidate
        except OSError as fallback_error:
            if fallback_error.errno == errno.EEXIST and name is None:
                continue
            if fallback_error.errno in fallback_errors or fallback_error.errno == errno.ENOTDIR:
                raise OSError(
                    errno.ENOTSUP,
                    'secure Linux extraction requires /proc/self/fd link support',
                    candidate,
                ) from fallback_error
            raise
    raise FileExistsError('could not allocate a unique extraction temporary file')


def _posix_entry_identity(parent_fd, name):
    """Return one no-follow directory-entry identity, or None when absent."""
    try:
        info = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    return info.st_dev, info.st_ino


def _posix_directory_is_within_root(parent_fd, root_identity):
    """Check whether a pinned parent currently descends from the root inode."""
    flags = os.O_RDONLY
    if hasattr(os, 'O_DIRECTORY'):
        flags |= os.O_DIRECTORY
    if hasattr(os, 'O_NOFOLLOW'):
        flags |= os.O_NOFOLLOW

    current_fd = os.dup(parent_fd)
    try:
        while True:
            current = os.fstat(current_fd)
            current_identity = current.st_dev, current.st_ino
            if current_identity == root_identity:
                return True

            ancestor_fd = os.open('..', flags, dir_fd=current_fd)
            ancestor = os.fstat(ancestor_fd)
            ancestor_identity = ancestor.st_dev, ancestor.st_ino
            if ancestor_identity == current_identity:
                os.close(ancestor_fd)
                return False
            os.close(current_fd)
            current_fd = ancestor_fd
    finally:
        os.close(current_fd)


def _write_posix_fd(temp_fd, data):
    """Write through an adopted duplicate without leaking on fdopen failure."""
    duplicate_fd = os.dup(temp_fd)
    try:
        stream = os.fdopen(duplicate_fd, 'wb')
    except BaseException:
        os.close(duplicate_fd)
        raise
    with stream:
        stream.write(data)


def _report_cleanup_errors(label, cleanup_errors, primary_error):
    """Attach cleanup diagnostics without replacing an in-flight exception."""
    if not cleanup_errors:
        return
    detail = '; '.join(str(error) for error in cleanup_errors)
    if primary_error is not None:
        if hasattr(primary_error, 'add_note'):
            primary_error.add_note(f'{label}: {detail}')
        return
    raise cleanup_errors[0]


def _cleanup_posix_failed_publication(
    parent_fd,
    temp_fd,
    new_identity,
    final_name,
    temp_name,
    preserve_committed,
    primary_error,
):
    """Erase failed payload bytes without racing on mutable pathnames.

    POSIX has no atomic "unlink this name only if it still identifies this inode"
    primitive. A stat-then-unlink cleanup can therefore delete a foreign replacement.
    The authoritative descriptor is the only safe ownership proof: truncate through
    it and leave any operation-owned zero-length name for explicit later cleanup.
    """
    del parent_fd, new_identity, final_name, temp_name
    if preserve_committed:
        return

    cleanup_errors = []
    try:
        os.ftruncate(temp_fd, 0)
    except OSError as exc:
        cleanup_errors.append(exc)

    _report_cleanup_errors(
        'POSIX extraction cleanup also failed',
        cleanup_errors,
        primary_error,
    )


def _decompress_pack_entry(raw):
    """Decompress a compressed pack entry (Zstd, LZ4 or LZMA1, dispatched by magic).

    Modern WH3 packs store compressed entries as a little-endian uint32
    decompressed size followed by a raw compression frame. The codec varies
    by pack: db.pack ships zstd frames (magic 28 B5 2F FD) while e.g.
    variants.pack ships LZ4 frames (magic 04 22 4D 18) — proven 2026-07-18
    on ogr_irongut_great_weapon.variantmeshdefinition, whose zstd-only
    decode failed with 'error determining content size from frame header'.
    Our own packs store only the vendored map files compressed (MAPS-W1,
    ``StoredCompressed``); every other entry is written plain.
    """
    if len(raw) < 8:
        raise ValueError("compressed pack entry too short for a size prefix")
    declared = struct.unpack('<I', raw[:4])[0]
    magic = raw[4:8]
    if magic == b"\x28\xb5\x2f\xfd":
        try:
            import zstandard
        except ImportError as exc:  # pragma: no cover - depends on host env
            raise RuntimeError(
                "pack entry is Zstd-compressed but the 'zstandard' module is not "
                "installed; run 'pip install zstandard' to read compressed game packs"
            ) from exc
        data = zstandard.ZstdDecompressor().decompress(raw[4:], max_output_size=declared)
    elif magic == b"\x04\x22\x4d\x18":
        try:
            import lz4.frame
        except ImportError as exc:  # pragma: no cover - depends on host env
            raise RuntimeError(
                "pack entry is LZ4-compressed but the 'lz4' module is not "
                "installed; run 'pip install lz4' to read compressed game packs"
            ) from exc
        data = lz4.frame.decompress(raw[4:])
    elif raw[4] < 225 and len(raw) >= 9:
        # [GLF-W1 2026-10-16] LZMA1: 5 property bytes (lc/lp/pb packed in one
        # byte + u32 dictionary size), then a raw stream with no size field.
        # Seen in 2789845079 @z_double_skill_points.pack (12 of 15 entries,
        # props 5d = lc3 lp0 pb2); stdlib FORMAT_ALONE rejects it because the
        # 8-byte size that format expects is absent. / RPFM 的 Lzma1 布局。
        import lzma
        props = raw[4]
        filters = [{
            "id": lzma.FILTER_LZMA1,
            "lc": props % 9, "lp": (props // 9) % 5, "pb": props // 45,
            "dict_size": struct.unpack('<I', raw[5:9])[0],
        }]
        try:
            decoder = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=filters)
            data = decoder.decompress(raw[9:], max_length=declared)
        except (lzma.LZMAError, ValueError) as exc:
            # any byte below 225 parses as props, so junk lands here too
            raise ValueError(
                f"unknown compression magic {magic.hex()} in pack entry "
                f"(not zstd or lz4, and not a readable lzma1 stream: {exc})"
            ) from exc
    else:
        raise ValueError(
            f"unknown compression magic {magic.hex()} in pack entry "
            f"(expected zstd 28b52ffd, lz4 04224d18 or an lzma1 props byte)"
        )
    if len(data) != declared:
        raise ValueError(
            f"decompressed size mismatch: got {len(data)} bytes, "
            f"header declared {declared}"
        )
    return data

# =============================================================================
# PACK FILE READER
# =============================================================================

class PackEntry:
    """A single file entry inside a pack."""
    __slots__ = ('path', 'size', 'is_compressed', 'data_offset')

    def __init__(self, path, size, is_compressed=False, data_offset=0):
        self.path = path
        self.size = size
        self.is_compressed = is_compressed
        self.data_offset = data_offset

    def __repr__(self):
        c = " [compressed]" if self.is_compressed else ""
        return f"PackEntry({self.path}, {self.size:,}B{c})"

    @property
    def extension(self):
        _, ext = os.path.splitext(self.path)
        return ext.lower()

    @property
    def asset_type(self):
        # Check DB tables by path
        if DB_PATH_PATTERN.match(self.path):
            return "db"
        for atype, exts in ASSET_TYPES.items():
            if self.extension in exts:
                return atype
        return "other"


class PackFile:
    """
    Reader/writer for Total War pack files (PFH4/PFH5/PFH6).

    Usage:
        pack = PackFile.open("data.pack")
        for entry in pack.entries:
            print(entry.path, entry.size)
        data = pack.read_file(entry)
    """

    _read_lock_init_guard = threading.Lock()

    def __init__(self):
        self.format_version = 5
        self.pack_type = PACK_TYPE_MOD
        self.entries = []
        self.file_path = None
        self._file_handle = None
        # One PackFile owns one seekable stream. Keep each seek/read transaction
        # atomic so concurrent callers cannot move the shared cursor mid-read.
        self._read_lock = threading.Lock()
        self._data_start = 0
        self.timestamp = 0
        # PFH6 extras
        self.ref_file_count = 0
        self.pack_file_index_size = 0
        self.pack_file_count = 0

    def _get_read_lock(self):
        """Return the per-instance stream lock, including legacy raw instances.

        A few lightweight callers construct PackFile through __new__ and populate
        only file_path plus _file_handle. Serialize lazy lock installation so two
        first readers of such an instance cannot receive independent locks.
        """
        lock = getattr(self, '_read_lock', None)
        if lock is not None:
            return lock
        with self._read_lock_init_guard:
            lock = getattr(self, '_read_lock', None)
            if lock is None:
                lock = threading.Lock()
                self._read_lock = lock
            return lock

    @classmethod
    def open(cls, filepath):
        """Open and parse a .pack file without leaking handles on parse errors."""
        pack = cls()
        pack.file_path = os.path.abspath(filepath)
        try:
            pack._parse()
        except BaseException:
            pack.close()
            raise
        return pack

    def _parse(self):
        """Parse pack file header and index."""
        f = open(self.file_path, 'rb')
        self._file_handle = f

        # Read magic
        magic = f.read(4)
        if magic not in SUPPORTED_FORMATS:
            raise ValueError(f"Unknown pack format: {magic!r} (expected PFH4/PFH5/PFH6)")
        self.format_version = SUPPORTED_FORMATS[magic]

        # Read header fields (all uint32 LE). The first is a bitmask: the low
        # nibble is the pack type, the high bits are layout flags.
        # [DLC-W1 2026-10-12] The 2026-10-11 game patch set 0x40 on boot.pack
        # and the old reader, which kept only the low nibble, misparsed it
        # ("decoded 30 entries using 937 of 1973 bytes"). Measured on the
        # patched pack: with 0x40 every index entry carries a u32 timestamp
        # right after its size (the sizes then sum exactly to the data region,
        # 40,858 bytes; the other order sums to 46.6 GB). Flags that change
        # the layout in ways this reader cannot decode are refused, never
        # guessed: a misread index yields wrong paths that look valid.
        raw_type = struct.unpack('<I', f.read(4))[0]
        self.pack_type = raw_type & 0xF  # Lower 4 bits
        self.index_has_timestamps = bool(raw_type & PFH_FLAG_INDEX_TIMESTAMPS)
        unsupported = raw_type & (PFH_FLAG_ENCRYPTED_INDEX
                                  | PFH_FLAG_EXTENDED_HEADER)
        if unsupported:
            raise ValueError(
                f"Unsupported pack header flags 0x{unsupported:x} "
                f"(encrypted index / extended header) in {self.file_path}")
        self.ref_file_count = struct.unpack('<I', f.read(4))[0]
        self.pack_file_index_size = struct.unpack('<I', f.read(4))[0]
        self.pack_file_count = struct.unpack('<I', f.read(4))[0]
        packed_file_index_size = struct.unpack('<I', f.read(4))[0]

        # PFH5+ has timestamp
        if self.format_version >= 5:
            self.timestamp = struct.unpack('<I', f.read(4))[0]
        else:
            self.timestamp = 0

        # Skip the dependency-pack index (if any). ref_file_count (offset 8)
        # is the number of dependency pack NAMES and pack_file_index_size
        # (offset 12) is that index's byte size — they describe the SAME
        # region. The old code skipped it twice (once NUL-scanning per count,
        # once by size), which misaligned every pack that declares
        # dependencies (WH3's *_bl blood packs, anim_3, ui_3: E6b 2026-07-16).
        # The byte-size field is authoritative; skip exactly once.
        if self.pack_file_index_size > 0:
            f.read(self.pack_file_index_size)

        # Read packed file index
        index_start = f.tell()
        index_data = f.read(packed_file_index_size)
        self._data_start = f.tell()

        # [C12.63] Parse exactly the count declared by the header. Every
        # boundary failure is reported as pack-index corruption instead of
        # leaking struct/index implementation errors; a count/size mismatch
        # (which the engine may reject) is no longer silently accepted.
        pos = 0
        data_offset = self._data_start
        for entry_number in range(self.pack_file_count):
            context = (
                f"packed file index entry {entry_number + 1}/"
                f"{self.pack_file_count} at byte {pos}"
            )
            if pos + 4 > len(index_data):
                raise ValueError(f"Truncated {context}: missing file size")
            file_size = struct.unpack_from('<I', index_data, pos)[0]
            pos += 4
            if self.index_has_timestamps:
                if pos + 4 > len(index_data):
                    raise ValueError(f"Truncated {context}: missing timestamp")
                pos += 4

            is_compressed = False
            if self.format_version >= 5:
                if pos >= len(index_data):
                    raise ValueError(
                        f"Truncated {context}: missing compression flag"
                    )
                is_compressed = bool(index_data[pos])
                pos += 1

            null_pos = index_data.find(b'\x00', pos)
            if null_pos < 0:
                raise ValueError(
                    f"Truncated {context}: unterminated file path"
                )
            file_path = index_data[pos:null_pos].decode(
                'utf-8', errors='replace'
            )
            pos = null_pos + 1

            entry = PackEntry(file_path, file_size, is_compressed, data_offset)
            self.entries.append(entry)
            data_offset += file_size

        if pos != packed_file_index_size:
            raise ValueError(
                "Packed file index size/count mismatch: "
                f"decoded {self.pack_file_count} entries using {pos} of "
                f"{packed_file_index_size} bytes"
            )

    def read_file(self, entry, decompress=True):
        """Read a file entry's bytes.

        Entries flagged is_compressed (PFH5+) are stored as
        [uint32 LE decompressed_size][zstd frame]; decompress them by default so
        callers always receive the real payload. Pass decompress=False to obtain
        the stored bytes verbatim (e.g. to re-pack them unchanged).
        """
        with self._get_read_lock():
            if self._file_handle is None:
                self._file_handle = open(self.file_path, 'rb')
            self._file_handle.seek(entry.data_offset)
            raw = self._file_handle.read(entry.size)
        if decompress and entry.is_compressed:
            return _decompress_pack_entry(raw)
        return raw

    def find(self, pattern, case_insensitive=True):
        """Find entries matching a glob pattern."""
        if case_insensitive:
            pattern = pattern.lower()
            return [e for e in self.entries if fnmatch.fnmatch(e.path.lower(), pattern)]
        return [e for e in self.entries if fnmatch.fnmatch(e.path, pattern)]

    def find_regex(self, regex_pattern):
        """Find entries matching a regex pattern."""
        pat = re.compile(regex_pattern, re.IGNORECASE)
        return [e for e in self.entries if pat.search(e.path)]

    @staticmethod
    def _safe_extract_path(entry_path, output_dir, resolved_root=None):
        """Resolve an archive path inside one pinned root or reject it as unsafe."""
        useful_parts = _validated_extract_parts(entry_path)
        root = Path(resolved_root) if resolved_root is not None else Path(output_dir).resolve()
        parent = root.joinpath(*useful_parts[:-1]).resolve()
        try:
            parent.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"unsafe pack entry path: {entry_path!r}") from exc
        return parent / useful_parts[-1]

    def extract(self, entry, output_dir):
        """Publish one complete entry atomically without clobbering any destination.

        Existing final names are conflicts on every platform. Windows pins parents
        without delete sharing. POSIX pins descriptors and uses no-follow traversal,
        but an uncooperative same-UID writer that can rename open ancestors remains
        outside the generic POSIX containment guarantee; flock coordinates only
        cooperating extractors.
        """
        useful_parts = _validated_extract_parts(entry.path)
        # abspath is lexical: unlike resolve(), it never follows a caller-selected
        # symlink before the root has been opened no-follow and pinned.
        root = Path(os.path.abspath(os.fspath(output_dir)))
        out_path = root.joinpath(*useful_parts)
        data = self.read_file(entry)

        if os.name == 'nt':
            # Output-root and archive components are created one at a time while all
            # ancestor handles remain open without delete sharing.
            with _locked_windows_directory_chain(
                root, out_path.parent
            ) as (_root_handle, parent_handle, root_identity):
                parent_identity = _file_identity(out_path.parent)
                confirmed_path = self._safe_extract_path(entry.path, output_dir, root)
                if (
                    confirmed_path != out_path
                    or _file_identity(root) != root_identity
                    or _file_identity(confirmed_path.parent) != parent_identity
                ):
                    raise ValueError(f"unsafe pack entry path changed: {entry.path!r}")

                existing_attributes = _windows_path_attributes(out_path)
                if existing_attributes is not None:
                    is_directory = bool(existing_attributes & 0x00000010)
                    is_reparse = bool(existing_attributes & 0x00000400)
                    if is_directory and not is_reparse:
                        raise IsADirectoryError(out_path)
                    raise FileExistsError(
                        errno.EEXIST,
                        'extraction destination already exists',
                        str(out_path),
                    )

                temp_handle = None
                committed = False
                try:
                    temp_handle, _temp_name = _create_windows_temp_handle(
                        out_path.parent, parent_identity
                    )
                    _write_windows_handle(temp_handle, data)
                    _set_windows_handle_attributes(temp_handle, None)

                    confirmed_path = self._safe_extract_path(entry.path, output_dir, root)
                    if (
                        confirmed_path != out_path
                        or _file_identity(root) != root_identity
                        or _file_identity(confirmed_path.parent) != parent_identity
                    ):
                        raise ValueError(
                            f"unsafe pack entry path changed: {entry.path!r}"
                        )

                    # The kernel performs the no-clobber name check atomically.
                    _rename_windows_handle(temp_handle, parent_handle, out_path.name)
                    committed = True
                finally:
                    if temp_handle is not None:
                        if not committed and _windows_handle_is_destination(
                            temp_handle, parent_identity, out_path.name
                        ):
                            committed = True
                        _dispose_windows_handle(
                            temp_handle,
                            delete_on_close=not committed,
                            primary_error=sys.exc_info()[1],
                        )
            return str(out_path)

        # POSIX publishes only by hard-linking the authoritative payload descriptor
        # to an absent final name. Failed transactions truncate their owned inode but
        # never unlink a mutable pathname or remove an archive-created parent.
        parent_fd = None
        temp_fd = None
        new_identity = None
        commit_attempted = False
        completed = False
        with _locked_posix_directory_chain(
            root, useful_parts[:-1]
        ) as (_root_fd, parent_fd, root_identity):
            parent_info = os.fstat(parent_fd)
            parent_identity = parent_info.st_dev, parent_info.st_ino
            try:
                try:
                    existing = os.stat(
                        out_path.name, dir_fd=parent_fd, follow_symlinks=False
                    )
                except FileNotFoundError:
                    existing = None
                if existing is not None:
                    if stat.S_ISDIR(existing.st_mode):
                        raise IsADirectoryError(out_path)
                    raise FileExistsError(
                        errno.EEXIST,
                        'extraction destination already exists',
                        str(out_path),
                    )

                temp_fd = _open_posix_temp(parent_fd)
                new_file = os.fstat(temp_fd)
                new_identity = new_file.st_dev, new_file.st_ino
                _write_posix_fd(temp_fd, data)

                try:
                    confirmed_path = self._safe_extract_path(
                        entry.path, output_dir, root
                    )
                except (FileNotFoundError, NotADirectoryError) as exc:
                    raise ValueError(
                        f"unsafe pack entry parent changed: {entry.path!r}"
                    ) from exc
                if (
                    confirmed_path != out_path
                    or _file_identity(root) != root_identity
                    or _posix_directory_identity_at_path(confirmed_path.parent)
                    != parent_identity
                    or not _posix_directory_is_within_root(parent_fd, root_identity)
                ):
                    raise ValueError(f"unsafe pack entry path changed: {entry.path!r}")

                commit_attempted = True
                _link_posix_temp(temp_fd, parent_fd, out_path.name)

                if _posix_entry_identity(parent_fd, out_path.name) != new_identity:
                    raise ValueError(
                        f"unsafe extraction committed payload changed: {entry.path!r}"
                    )
                if (
                    _posix_directory_identity_at_path(out_path.parent)
                    != parent_identity
                    or not _posix_directory_is_within_root(parent_fd, root_identity)
                ):
                    raise ValueError(
                        f"unsafe pack entry parent left extraction root: {entry.path!r}"
                    )

                completed = True
            finally:
                primary_error = sys.exc_info()[1]
                if temp_fd is not None:
                    try:
                        final_is_new = (
                            _posix_entry_identity(parent_fd, out_path.name)
                            == new_identity
                        )
                        parent_is_still_exact = (
                            _posix_directory_identity_at_path(out_path.parent)
                            == parent_identity
                            and _posix_directory_is_within_root(
                                parent_fd, root_identity
                            )
                        )
                        preserve_committed = (
                            final_is_new
                            and parent_is_still_exact
                            and (completed or commit_attempted)
                        )
                        _cleanup_posix_failed_publication(
                            parent_fd,
                            temp_fd,
                            new_identity,
                            out_path.name,
                            None,
                            preserve_committed,
                            primary_error,
                        )
                    finally:
                        os.close(temp_fd)

        return str(out_path)

    def extract_all(self, output_dir, filter_pattern=None, progress_callback=None):
        """Extract all (or filtered) entries."""
        entries = self.find(filter_pattern) if filter_pattern else self.entries
        extracted = []
        for i, entry in enumerate(entries):
            if progress_callback:
                progress_callback(i, len(entries), entry.path)
            path = self.extract(entry, output_dir)
            extracted.append(path)
        return extracted

    def get_stats(self):
        """Return summary statistics about pack contents."""
        stats = defaultdict(lambda: {"count": 0, "size": 0})
        for entry in self.entries:
            atype = entry.asset_type
            stats[atype]["count"] += 1
            stats[atype]["size"] += entry.size
        return dict(stats)

    def close(self):
        """Close the shared stream after any in-flight read transaction finishes.

        The same lock used by read_file prevents close() from invalidating the
        seekable handle between a caller's seek and read operations. Reopening
        after close remains supported by the existing lazy-open behavior, including
        raw test/tool instances that intentionally bypass normal construction.
        """
        with self._get_read_lock():
            if self._file_handle:
                self._file_handle.close()
                self._file_handle = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __len__(self):
        return len(self.entries)

    def __repr__(self):
        return (f"PackFile(v{self.format_version}, "
                f"type={PACK_TYPE_NAMES.get(self.pack_type, '?')}, "
                f"files={len(self.entries)})")


# =============================================================================
# PACK FILE WRITER
# =============================================================================

class StoredCompressed(bytes):
    """Payload bytes that are already in CA's compressed-entry form.

    [MAPS-W1 2026-10-14] User ruling "compress only the maps": vendored map
    files are staged exactly as their source mod stored them -- a u32 LE
    decompressed size followed by a zstd frame, the same wrapper
    ``_decompress_pack_entry`` reads -- and ``write_pack_file`` writes such a
    payload with the compressed flag set. Everything else stays plain. The
    wrapper is checked on construction by decompressing it, so a payload that
    is not a valid compressed entry can never reach a pack index flagged 1.
    / 已是 CA 压缩条目格式的载荷；构造时解压一次以确认格式，写包时置压缩标志。
    """

    def __new__(cls, data):
        if len(data) < 8 or bytes(data[4:8]) != b"\x28\xb5\x2f\xfd":
            raise ValueError("StoredCompressed needs a [u32 size][zstd frame] payload")
        _decompress_pack_entry(bytes(data))
        return super().__new__(cls, data)


def write_pack_file(output_path, entries, pack_type, timestamp=0,
                    format_version=5):
    """Write ``entries`` as a PFH pack; return the bytes written.

    Every payload is written verbatim. A ``StoredCompressed`` payload (PFH5+
    only) gets the index compressed flag 1; every other payload gets 0.

    The one PFH byte layout behind PackWriter.write, build_pack.build_pack,
    dbw_clone.ModPackBuilder and the N3-A spike builder. Header: magic
    ``PFH<format_version>``, u32 pack-type bitmask, ref_file_count 0,
    pack_file_index_size 0, u32 pack_file_count, u32 packed_file_index_size,
    then (PFH5+) u32 ``int(timestamp)``. Index: per entry u32 stored size, (PFH5+)
    u8 compressed flag, NUL-terminated UTF-8 path; data follows in index order.
    Header and index are built before ``output_path`` is opened, so a path that
    cannot be encoded or a timestamp out of u32 range never truncates it.
    / 唯一的 PFH 字节布局：头与索引先在内存建好再打开输出文件。
    """
    # Build index
    index = bytearray()
    for pack_path, data in entries:
        index += struct.pack('<I', len(data))       # file size
        if format_version >= 5:
            index += struct.pack('B', 1 if isinstance(data, StoredCompressed) else 0)
        elif isinstance(data, StoredCompressed):
            raise ValueError(f"PFH{format_version} has no compressed flag: {pack_path}")
        index += pack_path.encode('utf-8') + b'\x00' # null-terminated path

    # Build header
    magic = f"PFH{format_version}".encode('ascii')
    header = bytearray()
    header += magic
    header += struct.pack('<I', pack_type)       # bitmask
    header += struct.pack('<I', 0)               # ref_file_count
    header += struct.pack('<I', 0)               # pack_file_index_size
    header += struct.pack('<I', len(entries))    # pack_file_count
    header += struct.pack('<I', len(index))      # packed_file_index_size
    if format_version >= 5:
        header += struct.pack('<I', int(timestamp))  # timestamp

    # Write
    with open(output_path, 'wb') as f:
        f.write(header)
        f.write(index)
        for _, data in entries:
            f.write(data)

    return len(header) + len(index) + sum(len(d) for _, d in entries)


class PackWriter:
    """
    Create a new .pack file from scratch or from existing files.

    Direct file/directory imports keep the historical forward-slash normalization
    used for scripts and ordinary mod assets. Pack-to-pack imports preserve the
    source index path exactly because verified WH3 VFS namespaces such as terrain
    and Wwise audio intentionally use backslashes.

    Usage:
        writer = PackWriter()
        writer.add_file("script/campaign/mod/my_mod.lua", lua_bytes)
        writer.add_directory("/path/to/mod/folder", base_path="/path/to/mod")
        writer.write("my_mod.pack")
    """

    def __init__(self, format_version=5, pack_type=PACK_TYPE_MOD, strict=True):
        self.format_version = format_version
        self.pack_type = pack_type
        # [C12.63] strict (default): reject duplicate canonical VFS identities
        # and zero-length payloads at add time — the engine resolves db/x and
        # db\x case-insensitively to ONE identity, so duplicates silently mask
        # an asset depending on index order. No repo flow legitimately adds
        # duplicates (merge included); strict stays on everywhere.
        self.strict = strict
        self.files = []  # list of (pack_path, data_bytes)
        self._canonical_paths = set()

    @staticmethod
    def _canonical_vfs_path(pack_path):
        # Mirrors build_pack.validate_pack_entries: WH3 VFS identity is
        # separator- and case-insensitive.
        return pack_path.replace('\\', '/').lower()

    def _append_exact_path(self, pack_path, data):
        """Append one already-authoritative pack index path without rewriting it."""
        if not isinstance(pack_path, str) or not pack_path or '\x00' in pack_path:
            raise ValueError(f"invalid pack path: {pack_path!r}")
        canonical = self._canonical_vfs_path(pack_path)
        if self.strict:
            if not data:
                raise ValueError(f"Zero-length pack entry: {canonical}")
            if canonical in self._canonical_paths:
                raise ValueError(f"Duplicate pack path: {pack_path}")
        self._canonical_paths.add(canonical)
        self.files.append((pack_path, data))

    def add_file(self, pack_path, data):
        """Add bytes, normalizing a direct caller's OS separators to slash."""
        if isinstance(pack_path, str):
            pack_path = pack_path.replace('\\', '/')
        self._append_exact_path(pack_path, data)

    def add_from_disk(self, disk_path, pack_path):
        """Add a file from disk using the direct-import path convention."""
        with open(disk_path, 'rb') as f:
            data = f.read()
        self.add_file(pack_path, data)

    def add_directory(self, dir_path, base_path=None, extensions=None):
        """
        Recursively add all files from a directory.
        base_path: strip this prefix from paths (default: dir_path itself).
        extensions: only include files with these extensions (e.g., ['.lua', '.xml']).
        """
        if base_path is None:
            base_path = dir_path
        for root, dirs, files in os.walk(dir_path):
            for fname in sorted(files):
                if extensions and not any(fname.endswith(e) for e in extensions):
                    continue
                fpath = os.path.join(root, fname)
                rel = os.path.relpath(fpath, base_path).replace('\\', '/')
                self.add_from_disk(fpath, rel)

    def add_from_pack(self, source_pack, filter_pattern=None):
        """Import files while preserving each source pack's exact VFS path."""
        entries = source_pack.find(filter_pattern) if filter_pattern else source_pack.entries
        for entry in entries:
            data = source_pack.read_file(entry)
            self._append_exact_path(entry.path, data)

    def write(self, output_path):
        """Write the pack file to disk. Returns (file_count, total_bytes)."""
        total_size = write_pack_file(output_path, self.files, self.pack_type,
                                     0, self.format_version)
        return len(self.files), total_size


# =============================================================================
# DB TABLE READER
# =============================================================================

class DBTableReader:
    """
    Read binary DB tables from WH3 pack files.

    DB tables in TW:WH3 use a custom binary format:
    - Optional GUID header (marker 0xFD)
    - Version marker (0xFC)
    - Entry count (uint32)
    - Row data (variable, depends on schema)

    Without a schema file, we can only do limited parsing.
    For TSV-format tables (already text), we read directly.
    """

    @staticmethod
    def read_tsv(data):
        """Parse a TSV-format table. Returns (headers, rows)."""
        text = data.decode('utf-8', errors='replace')
        lines = text.strip().split('\n')
        if not lines:
            return [], []
        headers = lines[0].split('\t')
        rows = [line.split('\t') for line in lines[1:] if line.strip()]
        return headers, rows

    @staticmethod
    def detect_format(data):
        """Detect if data is binary DB or text TSV."""
        if len(data) < 4:
            return "unknown"
        # Check for GUID marker (0xFD) or version marker (0xFC)
        if data[0] in (0xFD, 0xFC, 0x01):
            return "binary"
        # Check if it looks like text
        try:
            text = data[:200].decode('utf-8')
            if '\t' in text and '\n' in text:
                return "tsv"
        except UnicodeDecodeError:
            pass
        return "binary"

    # Real marker bytes. Both are FOUR bytes, not one.
    GUID_MARKER = b'\xfd\xfe\xfc\xff'
    VERSION_MARKER = b'\xfc\xfd\xfe\xff'

    @staticmethod
    def parse_binary_header(data):
        """Parse the header of a binary DB table. Returns metadata dict.

        Header layout, read off vanilla db.pack rather than assumed:
            [FD FE FC FF][u16 char count][GUID as UTF-16LE]   (optional)
            [FC FD FE FF][i32 version]                        (optional)
            [u8 unknown][u32 entry count]

        The previous implementation treated the markers as SINGLE bytes and the
        GUID as a fixed 36-byte ASCII run. Both are wrong: the markers are four
        bytes and the GUID is a UTF-16LE string with a u16 length prefix. The
        consequence was that `packfile.py db-read` -- a documented entry point in
        CLAUDE.md -- reported `Version: 0` and `Entries: 1711301376` for
        main_units_tables, and began its string scan mid-header, printing
        mojibake. Verified against six vanilla tables: main_units v7/2609 rows,
        agent_subtypes v3/613, land_units v54/2486, battle_entities v39/1256,
        unit_variants v5/2507, faction_agent_permitted_subtypes v1/9187 -- the
        six versions match db_writer.SCHEMAS exactly.
        """
        pos = 0
        # `version_marker` records whether the FC FD FE FF block was present:
        # a markerless fragment carries no version at all, so its `version` 0
        # is "absent", not "zero" (TEST-REPAIR-1113). / 无标记片段不带版本号。
        result = {"guid": None, "version": 0, "entry_count": 0, "data_start": 0,
                  "version_marker": False}

        if len(data) < 4:
            return result

        if data[0:4] == DBTableReader.GUID_MARKER:
            pos = 4
            if pos + 2 > len(data):
                return result
            char_count = struct.unpack_from('<H', data, pos)[0]
            pos += 2
            end = pos + char_count * 2
            if end > len(data):
                return result
            result["guid"] = data[pos:end].decode('utf-16-le', errors='replace')
            pos = end

        if data[pos:pos + 4] == DBTableReader.VERSION_MARKER:
            pos += 4
            result["version_marker"] = True
            if pos + 4 > len(data):
                return result
            # Signed: RPFM stores the table version as i32.
            result["version"] = struct.unpack_from('<i', data, pos)[0]
            pos += 4

        # One byte whose meaning RPFM does not name, then the row count.
        pos += 1
        if pos + 4 <= len(data):
            result["entry_count"] = struct.unpack_from('<I', data, pos)[0]
            pos += 4

        result["data_start"] = pos
        return result

    @staticmethod
    def try_extract_strings(data, min_length=4, max_strings=200, start=0):
        """
        Extract readable strings from binary data.
        Useful for finding unit keys, faction names, etc. in DB tables.
        """
        strings = []
        # Look for UTF-16LE strings (WH3 DB format uses 2-byte length + UTF-16LE)
        # [C12.102] `start` lets a caller skip the header. It defaults to 0 so
        # every existing caller is unaffected. C12.101's claim that the scan
        # "began mid-header" was wrong -- it always began at byte 0 and never
        # consulted data_start -- so the GUID and version bytes were scanned as
        # if they were row data.
        pos = max(0, int(start))
        while pos < len(data) - 4 and len(strings) < max_strings:
            # Try reading as length-prefixed UTF-16LE string
            str_len = struct.unpack('<H', data[pos:pos+2])[0]
            if 2 <= str_len <= 500:
                str_start = pos + 2
                str_end = str_start + str_len * 2
                if str_end <= len(data):
                    try:
                        s = data[str_start:str_end].decode('utf-16-le')
                        if s.isprintable() and len(s) >= min_length:
                            strings.append((pos, s))
                            pos = str_end
                            continue
                    except (UnicodeDecodeError, struct.error):
                        pass
            pos += 1

        # Also try ASCII strings
        ascii_pattern = re.compile(rb'[a-z0-9_]{6,}')
        for match in ascii_pattern.finditer(data):
            s = match.group().decode('ascii')
            if len(s) >= min_length:
                strings.append((match.start(), s))

        # Deduplicate and sort by position
        seen = set()
        unique = []
        for pos, s in sorted(strings, key=lambda x: x[0]):
            if s not in seen:
                seen.add(s)
                unique.append((pos, s))
        return unique


# =============================================================================
# LOC FILE READER
# =============================================================================

class LocReader:
    """
    Read .loc localization files from WH3.

    Format:
    - 2 bytes: FF FE (BOM) or other marker
    - Then: entries with key + value as length-prefixed strings
    """

    @staticmethod
    def read(data):
        """Parse a WH3 LOC v1 file. Returns list of (key, value) tuples.

        `data` must be the DECOMPRESSED payload — PackFile.read_file() already
        inflates the CA [u32 size][zstd frame] wrapper, so pass its output here.
        The verified header is FF FE 'L' 'O' 'C' 00, then int32 version (==1), then
        uint32 row_count (matches decode_loc_rows below). The old parser
        skipped a 2-byte BOM and read bytes[2:4] ('L','O' = 0x4F4C) as a uint16
        marker; since that never equals 0xFFFE/0x0001 it returned empty on every
        real loc — so LocReader resolved nothing even when read_file decompressed
        correctly. / 真实头是 FF FE 'L''O''C' 00 + int32 版本 + uint32 行数；旧代码把
        第 2..4 字节 'LO'(0x4F4C) 当 uint16 marker，永不匹配 0xFFFE/0x0001，于是即便
        read_file 已正确解压，LocReader 仍解出空。传入必须是解压后的 payload。
        """
        entries = []
        # Real WH3 LOC v1 layout. Each row: uint16 key_len (UTF-16 code units) +
        # key + uint16 val_len + value + 1 tooltip flag byte.
        if len(data) < 14 or data[:6] != b'\xff\xfeLOC\x00':
            return entries
        version = struct.unpack('<i', data[6:10])[0]
        if version != 1:
            return entries
        count = struct.unpack('<I', data[10:14])[0]
        pos = 14

        for _ in range(min(count, 500000)):
            if pos + 2 > len(data):
                break
            # Key
            key_len = struct.unpack('<H', data[pos:pos+2])[0]
            pos += 2
            if pos + key_len * 2 > len(data):
                break
            key = data[pos:pos+key_len*2].decode('utf-16-le', errors='replace')
            pos += key_len * 2
            # Value
            if pos + 2 > len(data):
                break
            val_len = struct.unpack('<H', data[pos:pos+2])[0]
            pos += 2
            if pos + val_len * 2 > len(data):
                break
            val = data[pos:pos+val_len*2].decode('utf-16-le', errors='replace')
            pos += val_len * 2
            # Tooltip flag byte / 提示标志字节
            if pos < len(data):
                pos += 1

            entries.append((key, val))

        return entries


# [DLC-W1 2026-10-12] Since the 2026-10 patch CA writes loc values as
# `{{tr:<target>}}` references (measured in local_en.pack: 23,219 values,
# 17,494 of them nothing but the reference, 5,725 with it embedded in longer
# text, 662 pointing at another reference). <target> is either a full loc key
# or the tail of a `ui_text_replacements_localised_text_` key; 111 of CA's own
# references resolve to nothing. A reader that returns the raw value hands
# every consumer the literal "{{tr:...}}", which is how 417 names in
# VANILLA_REFERENCE.md and 1,133 in the dedup index came out unreadable.
LOC_REFERENCE = re.compile(r"\{\{tr:([^}]+)\}\}")
LOC_REFERENCE_UI_PREFIX = "ui_text_replacements_localised_text_"


def resolve_loc_references(table, max_depth=8, fallback=None):
    """Return ``(resolved, unresolved)`` for one language's whole loc table.

    ``table`` maps loc key -> raw value and must hold the WHOLE language (a
    reference may point into any other .loc file of the pack). Each
    `{{tr:X}}` is replaced by table[X], else by
    table["ui_text_replacements_localised_text_" + X], recursively up to
    ``max_depth``. ``fallback`` (an already-resolved table, e.g. vanilla's
    for a Workshop pack) is consulted when ``table`` has no target. A
    reference with no target is left verbatim and its target counted in
    ``unresolved`` -- never guessed, never silently dropped.
    / 整张语言表一起解析 {{tr:}} 引用；找不到目标的原样保留并计数。
    """
    unresolved = {}
    fallback = fallback or {}

    def lookup(target, depth):
        for source in (table, fallback):
            for key in (target, LOC_REFERENCE_UI_PREFIX + target):
                if key in source:
                    return expand(source[key], depth + 1)
        unresolved[target] = unresolved.get(target, 0) + 1
        return None

    def expand(value, depth):
        if "{{tr:" not in value or depth > max_depth:
            return value

        def sub(match):
            found = lookup(match.group(1), depth)
            return match.group(0) if found is None else found

        return LOC_REFERENCE.sub(sub, value)

    resolved = {key: expand(value, 0) for key, value in table.items()}
    return resolved, unresolved


def read_language_table(pack_path):
    """Every .loc row of ``pack_path`` as one dict, references resolved.

    The one place a whole vanilla/Workshop language pack is read for display
    text; returns ``(table, unresolved)`` as resolve_loc_references does.
    """
    raw = {}
    with PackFile.open(pack_path) as pack:
        for entry in pack.entries:
            if entry.path.lower().endswith(".loc"):
                raw.update(LocReader.read(pack.read_file(entry)))
    return resolve_loc_references(raw)


def decode_loc_rows(data, pack_path):
    """Decode the verified WH3 LOC v1 format into ordered key/value rows.

    The strict counterpart of LocReader.read: every truncation, bad UTF-16
    unit, tooltip marker outside 0/1 and trailing byte raises ValueError
    naming ``pack_path``. The one decoder behind validate_mod's gates and
    build_pack's LOC key-collision check. / 严格版 LOC v1 解码：任何截断、
    非法 UTF-16、提示标志非 0/1、尾随字节都抛错；校验门与构建撞键检查共用。
    """
    if len(data) < 14 or data[:6] != b"\xff\xfeLOC\x00":
        raise ValueError(f"Invalid LOC header: {pack_path}")
    version = struct.unpack("<i", data[6:10])[0]
    if version != 1:
        raise ValueError(f"Unsupported LOC version {version}: {pack_path}")

    row_count = struct.unpack("<I", data[10:14])[0]
    pos = 14
    rows = []

    def take(size, context):
        nonlocal pos
        end = pos + size
        if size < 0 or end > len(data):
            available = max(0, len(data) - pos)
            raise ValueError(
                f"Truncated {context} at offset {pos}: need {size} bytes, "
                f"have {available}"
            )
        value = data[pos:end]
        pos = end
        return value

    for row_index in range(row_count):
        key_units = struct.unpack(
            "<H", take(2, f"LOC key length row {row_index}")
        )[0]
        try:
            key = take(
                key_units * 2, f"LOC key row {row_index}"
            ).decode("utf-16-le")
        except UnicodeDecodeError as exc:
            raise ValueError(
                f"Invalid UTF-16 key in {pack_path} row {row_index}: {exc}"
            ) from exc

        value_units = struct.unpack(
            "<H", take(2, f"LOC value length row {row_index}")
        )[0]
        try:
            value = take(
                value_units * 2, f"LOC value row {row_index}"
            ).decode("utf-16-le")
        except UnicodeDecodeError as exc:
            raise ValueError(
                f"Invalid UTF-16 value in {pack_path} row {row_index}: {exc}"
            ) from exc

        tooltip = take(1, f"LOC tooltip row {row_index}")[0]
        if tooltip not in (0, 1):
            raise ValueError(
                f"Invalid LOC tooltip marker 0x{tooltip:02X} in "
                f"{pack_path} row {row_index}"
            )
        rows.append((key, value))

    if pos != len(data):
        raise ValueError(
            f"Trailing LOC data in {pack_path}: decoded {pos} of {len(data)} bytes"
        )
    return rows


# =============================================================================
# MULTI-PACK SEARCH ENGINE
# =============================================================================

class PackSearchEngine:
    """
    Search across multiple .pack files in a directory.

    Usage:
        engine = PackSearchEngine("/path/to/WH3/data/")
        results = engine.search("*chaos_warriors*")
        results = engine.search_content("wh_main_chs_inf_chosen")
    """

    def __init__(self, pack_dir=None):
        self.pack_dir = pack_dir
        self.packs = {}  # filename -> PackFile

    def load_packs(self, pack_dir=None, filter_pattern="*.pack"):
        """Load all packs from a directory."""
        pack_dir = pack_dir or self.pack_dir
        if not pack_dir:
            raise ValueError("No pack directory specified")
        self.pack_dir = pack_dir

        for fname in sorted(os.listdir(pack_dir)):
            if fnmatch.fnmatch(fname.lower(), filter_pattern):
                fpath = os.path.join(pack_dir, fname)
                try:
                    pack = PackFile.open(fpath)
                    self.packs[fname] = pack
                except Exception as e:
                    print(f"  Warning: Could not read {fname}: {e}", file=sys.stderr)

        return len(self.packs)

    def search(self, pattern):
        """Search for files matching a glob pattern across all packs."""
        results = []
        for pack_name, pack in self.packs.items():
            matches = pack.find(pattern)
            for entry in matches:
                results.append((pack_name, entry))
        return results

    def search_regex(self, regex_pattern):
        """Search for files matching a regex across all packs."""
        results = []
        for pack_name, pack in self.packs.items():
            matches = pack.find_regex(regex_pattern)
            for entry in matches:
                results.append((pack_name, entry))
        return results

    def search_content(self, text_pattern, file_pattern="*.lua"):
        """Search file contents for a text pattern (like grep)."""
        results = []
        pat = re.compile(text_pattern.encode('utf-8', errors='replace'), re.IGNORECASE)
        for pack_name, pack in self.packs.items():
            entries = pack.find(file_pattern)
            for entry in entries:
                data = pack.read_file(entry)
                matches = list(pat.finditer(data))
                if matches:
                    results.append((pack_name, entry, len(matches)))
        return results

    def list_all_units(self, pack_name=None):
        """Find all unit keys from main_units_tables across packs."""
        units = []
        packs = {pack_name: self.packs[pack_name]} if pack_name else self.packs
        for pname, pack in packs.items():
            for entry in pack.find("db/main_units_tables/*"):
                data = pack.read_file(entry)
                fmt = DBTableReader.detect_format(data)
                if fmt == "tsv":
                    headers, rows = DBTableReader.read_tsv(data)
                    if rows:
                        units.extend(row[0] for row in rows if row)
                elif fmt == "binary":
                    strings = DBTableReader.try_extract_strings(data)
                    units.extend(s for _, s in strings if s.startswith("wh"))
        return sorted(set(units))

    def find_asset(self, unit_key, asset_types=None):
        """
        Find all assets related to a unit key.
        Searches models, textures, sounds, etc.
        """
        if asset_types is None:
            asset_types = ["model", "texture", "anim"]

        results = []
        # Unit keys often map to file paths with the same name
        key_parts = unit_key.split('_')
        # Try various search patterns
        patterns = [
            f"*{unit_key}*",
            f"*{'_'.join(key_parts[-3:])}*",
            f"*{'_'.join(key_parts[-2:])}*",
        ]

        for pat in patterns:
            for pack_name, pack in self.packs.items():
                matches = pack.find(pat)
                for entry in matches:
                    if asset_types and entry.asset_type not in asset_types:
                        continue
                    results.append((pack_name, entry))

        # Deduplicate
        seen = set()
        unique = []
        for pname, entry in results:
            key = (pname, entry.path)
            if key not in seen:
                seen.add(key)
                unique.append((pname, entry))
        return unique

    def global_stats(self):
        """Get aggregate stats across all loaded packs."""
        total_files = 0
        total_size = 0
        type_counts = defaultdict(int)
        for pack in self.packs.values():
            for entry in pack.entries:
                total_files += 1
                total_size += entry.size
                type_counts[entry.asset_type] += 1
        return {
            "pack_count": len(self.packs),
            "total_files": total_files,
            "total_size": total_size,
            "by_type": dict(type_counts),
        }

    def close_all(self):
        for pack in self.packs.values():
            pack.close()
        self.packs.clear()


# =============================================================================
# CLI INTERFACE
# =============================================================================

def format_size(size):
    """Format a byte count with the prefix the arithmetic actually uses.

    [debt Q6, closed 2026-08-20] This divided by 1024 and then wrote "KB" /
    "MB" / "GB" — binary arithmetic with decimal labels. It is where three
    documents' pack-size figures appeared to contradict each other while all
    three were right: README and CLAUDE.md copied the tool's "2.65 GB",
    MASTER_PLAN converted the same bytes to decimal and got "2.848 GB", and
    nothing said which unit either number was in.

    The bytes are the anchor; this line is only how a human reads them, so
    the fix is to label them honestly rather than to change the arithmetic.
    / 用二进制算、贴十进制标签，正是三份文档口径「互相矛盾其实都对」的根因。
      字节数才是锚点，这里只管人怎么读，故改标签不改算法。
    """
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KiB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024*1024):.1f} MiB"
    else:
        return f"{size / (1024*1024*1024):.2f} GiB"


def run_command(cmd_map, args):
    """Run ``cmd_map[args.command](args)`` under the shared CLI error policy.

    A falsy handler result exits 0; any exception prints ``Error: <exc>`` to
    stderr (plus the traceback when ``--debug`` is on the command line) and
    exits 1. Shared with wh3_data, whose CLI wraps this module.
    """
    try:
        return cmd_map[args.command](args) or 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if '--debug' in sys.argv:
            import traceback
            traceback.print_exc()
        return 1


def cmd_info(args):
    """Show pack file metadata."""
    pack = PackFile.open(args.pack)
    stats = pack.get_stats()

    print(f"Pack File: {os.path.basename(args.pack)}")
    print(f"Format:    PFH{pack.format_version}")
    print(f"Type:      {PACK_TYPE_NAMES.get(pack.pack_type, 'Unknown')} ({pack.pack_type})")
    print(f"Files:     {len(pack.entries):,}")
    total = sum(e.size for e in pack.entries)
    print(f"Data Size: {format_size(total)}")
    print(f"Pack Size: {format_size(os.path.getsize(args.pack))}")
    if pack.timestamp:
        print(f"Timestamp: {pack.timestamp}")
    print()
    print("Contents by type:")
    for atype in sorted(stats.keys()):
        s = stats[atype]
        print(f"  {atype:12s}  {s['count']:6,} files  {format_size(s['size']):>10s}")
    pack.close()


def cmd_list(args):
    """List files in pack."""
    pack = PackFile.open(args.pack)
    entries = pack.find(args.filter) if args.filter else pack.entries

    if args.type:
        entries = [e for e in entries if e.asset_type == args.type]

    for entry in entries:
        if args.long:
            print(f"{entry.size:>12,}  {entry.asset_type:8s}  {entry.path}")
        else:
            print(entry.path)

    if not args.quiet:
        print(f"\n{len(entries)} files", file=sys.stderr)
    pack.close()


def cmd_extract(args):
    """Extract files from pack."""
    pack = PackFile.open(args.pack)
    output = args.output

    def progress(i, total, path):
        if not args.quiet:
            print(f"  [{i+1}/{total}] {path}")

    entries = pack.find(args.filter) if args.filter else pack.entries
    if args.type:
        entries = [e for e in entries if e.asset_type == args.type]

    if not entries:
        print("No matching files found.")
        return

    print(f"Extracting {len(entries)} files to {output}/")
    for i, entry in enumerate(entries):
        progress(i, len(entries), entry.path)
        pack.extract(entry, output)

    print(f"Done. {len(entries)} files extracted.")
    pack.close()


def cmd_search(args):
    """Search across multiple packs."""
    engine = PackSearchEngine(args.dir)
    print(f"Loading packs from {args.dir}...")
    count = engine.load_packs()
    print(f"Loaded {count} pack files.\n")

    if args.content:
        print(f"Searching file contents for '{args.pattern}'...")
        results = engine.search_content(args.pattern, args.file_filter or "*")
        for pack_name, entry, match_count in results:
            print(f"  {pack_name}: {entry.path} ({match_count} matches)")
    else:
        results = engine.search(args.pattern)
        for pack_name, entry in results:
            print(f"  {pack_name}: {entry.path} ({format_size(entry.size)})")

    print(f"\n{len(results)} results found.")
    engine.close_all()


def cmd_create(args):
    """Create pack from directory."""
    writer = PackWriter()

    if os.path.isdir(args.source):
        exts = args.extensions.split(',') if args.extensions else None
        writer.add_directory(args.source, base_path=args.source, extensions=exts)
    else:
        print(f"Error: {args.source} is not a directory.")
        return 1

    if not writer.files:
        print("No files to pack.")
        return 1

    print(f"Creating {args.pack} with {len(writer.files)} files...")
    count, size = writer.write(args.pack)
    print(f"Done. {count} files, {format_size(size)}.")
    return 0


def cmd_merge(args):
    """Merge multiple packs into one."""
    writer = PackWriter()

    for pack_path in args.packs:
        print(f"Reading {os.path.basename(pack_path)}...")
        pack = PackFile.open(pack_path)
        writer.add_from_pack(pack)
        pack.close()

    print(f"\nWriting merged pack: {args.output}")
    count, size = writer.write(args.output)
    print(f"Done. {count} files, {format_size(size)}.")


def cmd_db_read(args):
    """Read a DB table from a pack."""
    pack = PackFile.open(args.pack)

    # Find the table
    matches = pack.find(f"*{args.table}*")
    if not matches:
        print(f"Table '{args.table}' not found.")
        pack.close()
        return

    entry = matches[0]
    print(f"Reading: {entry.path} ({format_size(entry.size)})")

    data = pack.read_file(entry)
    fmt = DBTableReader.detect_format(data)

    if fmt == "tsv":
        headers, rows = DBTableReader.read_tsv(data)
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write('\t'.join(headers) + '\n')
                for row in rows:
                    f.write('\t'.join(row) + '\n')
            print(f"Written {len(rows)} rows to {args.output}")
        else:
            print(f"Headers: {', '.join(headers[:10])}{'...' if len(headers) > 10 else ''}")
            print(f"Rows: {len(rows)}")
            for row in rows[:5]:
                print(f"  {row[0] if row else '?'}")
            if len(rows) > 5:
                print(f"  ... and {len(rows)-5} more")
    elif fmt == "binary":
        info = DBTableReader.parse_binary_header(data)
        print(f"Format: Binary DB")
        print(f"GUID: {info.get('guid', 'N/A')}")
        print(f"Version: {info.get('version', 'N/A')}")
        print(f"Entries: {info.get('entry_count', 'N/A')}")

        # Extract strings from the ROW DATA, skipping the header we just parsed.
        # [C12.102] Previously this scanned from byte 0, so the UTF-16 GUID was
        # reported as the first "string" and the header bytes were interpreted
        # as length prefixes.
        strings = DBTableReader.try_extract_strings(
            data, start=info.get("data_start", 0))
        if strings:
            print(f"\nExtracted {len(strings)} strings:")
            for pos, s in strings[:20]:
                print(f"  @{pos:06x}: {s}")
            if len(strings) > 20:
                print(f"  ... and {len(strings)-20} more")

        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                for _, s in strings:
                    f.write(s + '\n')
            print(f"\nStrings written to {args.output}")
    else:
        print("Could not detect table format.")

    pack.close()


def cmd_assets(args):
    """List assets by type."""
    pack = PackFile.open(args.pack)

    if args.type:
        entries = [e for e in pack.entries if e.asset_type == args.type]
    else:
        entries = pack.entries

    if args.unit:
        entries = [e for e in entries if args.unit.lower() in e.path.lower()]

    stats = defaultdict(list)
    for e in entries:
        stats[e.asset_type].append(e)

    for atype in sorted(stats.keys()):
        items = stats[atype]
        print(f"\n{'='*60}")
        print(f" {atype.upper()} ({len(items)} files, {format_size(sum(e.size for e in items))})")
        print(f"{'='*60}")
        for e in items[:args.limit]:
            print(f"  {e.path} ({format_size(e.size)})")
        if len(items) > args.limit:
            print(f"  ... and {len(items)-args.limit} more")

    pack.close()


def main():
    parser = argparse.ArgumentParser(
        prog='packfile',
        description='WH3 Pack File Swiss Army Knife — read, extract, create, search .pack files'
    )
    sub = parser.add_subparsers(dest='command', help='Available commands')

    # info
    p_info = sub.add_parser('info', help='Show pack file metadata')
    p_info.add_argument('pack', help='Path to .pack file')

    # list
    p_list = sub.add_parser('list', help='List files in pack')
    p_list.add_argument('pack', help='Path to .pack file')
    p_list.add_argument('--filter', '-f', help='Glob pattern filter (e.g., "*.lua")')
    p_list.add_argument('--type', '-t', help='Asset type filter (model/texture/sound/script/db/loc)')
    p_list.add_argument('--long', '-l', action='store_true', help='Show sizes and types')
    p_list.add_argument('--quiet', '-q', action='store_true', help='No summary line')

    # extract
    p_ext = sub.add_parser('extract', help='Extract files from pack')
    p_ext.add_argument('pack', help='Path to .pack file')
    p_ext.add_argument('output', help='Output directory')
    p_ext.add_argument('--filter', '-f', help='Glob pattern filter')
    p_ext.add_argument('--type', '-t', help='Asset type filter')
    p_ext.add_argument('--quiet', '-q', action='store_true')

    # search
    p_search = sub.add_parser('search', help='Search across multiple packs')
    p_search.add_argument('dir', help='Directory containing .pack files')
    p_search.add_argument('pattern', help='Search pattern (glob or text)')
    p_search.add_argument('--content', '-c', action='store_true', help='Search file contents (like grep)')
    p_search.add_argument('--file-filter', help='File pattern for content search')

    # create
    p_create = sub.add_parser('create', help='Create pack from directory')
    p_create.add_argument('pack', help='Output .pack file path')
    p_create.add_argument('source', help='Source directory')
    p_create.add_argument('--extensions', '-e', help='Comma-separated extensions (e.g., .lua,.xml)')

    # merge
    p_merge = sub.add_parser('merge', help='Merge multiple packs')
    p_merge.add_argument('output', help='Output .pack file')
    p_merge.add_argument('packs', nargs='+', help='Pack files to merge')

    # db-read
    p_db = sub.add_parser('db-read', help='Read DB table from pack')
    p_db.add_argument('pack', help='Path to .pack file')
    p_db.add_argument('table', help='Table name or path pattern')
    p_db.add_argument('--output', '-o', help='Output file (TSV)')

    # assets
    p_assets = sub.add_parser('assets', help='List assets by type')
    p_assets.add_argument('pack', help='Path to .pack file')
    p_assets.add_argument('--type', '-t', help='Asset type (model/texture/sound/anim/script)')
    p_assets.add_argument('--unit', '-u', help='Filter by unit key substring')
    p_assets.add_argument('--limit', '-l', type=int, default=50, help='Max items per type')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    cmd_map = {
        'info': cmd_info,
        'list': cmd_list,
        'extract': cmd_extract,
        'search': cmd_search,
        'create': cmd_create,
        'merge': cmd_merge,
        'db-read': cmd_db_read,
        'assets': cmd_assets,
    }

    return run_command(cmd_map, args)


if __name__ == '__main__':
    sys.exit(main())
