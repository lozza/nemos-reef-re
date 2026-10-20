#!/usr/bin/env python3
"""Points the Nemo's Reef 1.8.1 APK at a private server.

    python patch_apk.py nemos-reef-1-8-1-en-android.apk http://192.168.1.20:8080 [--debug-log]

Rewrites the two server URLs inside lib/armeabi/libsdr.so (the server URL can be at most 29
characters, since the account API URL <server>/nemo/api/ must fit the original's 39), optionally re-enables the engine's debug log (visible with `adb logcat`), then
re-signs the APK with uber-apk-signer (https://github.com/patrickfav/uber-apk-signer) if its jar is
next to this script or given with --signer, or with `apksigner` from the Android SDK.
"""
import argparse
import glob
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile

LIB = 'lib/armeabi/libsdr.so'
ACCOUNT_URL = b'http://nemo.apps.tapulous.com/nemo/api/'
GAME_URL = b'http://nemo.pragueweb.tapulous.com/nemo/'

# sdr::Debug::log overloads are compiled to `bx lr` in the release build; branch them to the
# still-working sdr::Debug::print overloads with the same leading arguments (file offset == vaddr).
DEBUG_PATCHES = [
    (0xa4fe3c, 0xa500fc),  # log(String const&)                  -> print(String const&)
    (0xa4fe40, 0xa50020),  # log(int, String const&, Severity)    -> print(int, String const&)
]


def thumb2_b_w(src, dst):
    """Encodes a Thumb-2 `b.w dst` placed at src (4 bytes, little-endian halfwords)."""
    off = dst - (src + 4)
    if not -(1 << 24) <= off < (1 << 24) or off & 1:
        raise ValueError('branch out of range')
    s = (off >> 24) & 1
    i1, i2 = (off >> 23) & 1, (off >> 22) & 1
    imm10, imm11 = (off >> 12) & 0x3ff, (off >> 1) & 0x7ff
    j1, j2 = (1 - (i1 ^ s)), (1 - (i2 ^ s))
    hw1 = 0xf000 | (s << 10) | imm10
    hw2 = 0x9000 | (j1 << 13) | (j2 << 11) | imm11
    return struct.pack('<HH', hw1, hw2)


def replace_cstring(lib, old, new):
    if len(new) > len(old):
        sys.exit('URL %r is longer than the original %r (%d > %d characters)'
                 % (new.decode(), old.decode(), len(new), len(old)))
    i = lib.find(old + b'\0')
    if i < 0:
        sys.exit('could not find %r in %s (already patched?)' % (old.decode(), LIB))
    lib[i:i + len(old)] = new.ljust(len(old), b'\0')


def patch_lib(lib, account_url, game_url, debug_log):
    lib = bytearray(lib)
    replace_cstring(lib, ACCOUNT_URL, account_url.encode())
    replace_cstring(lib, GAME_URL, game_url.encode())
    if debug_log:
        for src, dst in DEBUG_PATCHES:
            if lib[src:src + 2] != b'\x70\x47':  # bx lr
                sys.exit('unexpected bytes at %#x; is this the 1.8.1 APK?' % src)
            lib[src:src + 4] = thumb2_b_w(src, dst)
    return bytes(lib)


def rebuild(apk_in, apk_out, lib):
    with zipfile.ZipFile(apk_in) as zin, zipfile.ZipFile(apk_out, 'w') as zout:
        for info in zin.infolist():
            if info.filename.startswith('META-INF/') and info.filename.rsplit('.', 1)[-1] in ('SF', 'RSA', 'DSA', 'MF', 'EC'):
                continue  # old signature
            data = lib if info.filename == LIB else zin.read(info.filename)
            zout.writestr(info, data, compress_type=info.compress_type)


def sign(apk, signer_jar):
    if signer_jar:
        out = tempfile.mkdtemp()
        subprocess.check_call(['java', '-jar', signer_jar, '-a', apk, '-o', out, '--allowResign'])
        signed = glob.glob(os.path.join(out, '*.apk'))[0]
        shutil.move(signed, apk)
        shutil.rmtree(out, ignore_errors=True)
        return True
    if shutil.which('apksigner'):
        ks = os.path.join(os.path.dirname(os.path.abspath(apk)), 'nemo-debug.keystore')
        if not os.path.exists(ks):
            subprocess.check_call(['keytool', '-genkeypair', '-keystore', ks, '-storepass', 'android',
                                   '-alias', 'nemo', '-keyalg', 'RSA', '-keysize', '2048', '-validity', '10000',
                                   '-dname', 'CN=Nemo Private Server'])
        subprocess.check_call(['apksigner', 'sign', '--ks', ks, '--ks-pass', 'pass:android', apk])
        return True
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('apk', help='original nemos-reef 1.8.1 APK')
    ap.add_argument('server', help='server base URL, e.g. http://192.168.1.20:8080')
    ap.add_argument('-o', '--output', help='output APK (default: <apk>-private.apk)')
    ap.add_argument('--debug-log', action='store_true', help="send the game's internal log to logcat")
    ap.add_argument('--signer', help='path to uber-apk-signer.jar')
    args = ap.parse_args()

    base = args.server.rstrip('/')
    account_url, game_url = base + '/nemo/api/', base + '/nemo/'
    out = args.output or os.path.splitext(args.apk)[0] + '-private.apk'
    signer = args.signer or next(iter(sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uber-apk-signer*.jar')))), None)

    with zipfile.ZipFile(args.apk) as z:
        lib = patch_lib(z.read(LIB), account_url, game_url, args.debug_log)
    rebuild(args.apk, out, lib)
    print('account API -> %s\ngame API    -> %s' % (account_url, game_url))
    if sign(out, signer):
        print('wrote signed %s' % out)
    else:
        print('wrote UNSIGNED %s: put uber-apk-signer.jar next to this script (or pass --signer), '
              'or install the Android SDK build-tools (apksigner), then run again' % out)


if __name__ == '__main__':
    main()
