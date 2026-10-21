"""Builds the localized text bundle (getLocalizedTextsBundle) for the client.

The bundle is a flat JSON object {"STR_KEY": "text"}, sent as the response's "texts" member
(netcl::ActionGetLocalizedTextsBundle::loadingFinished → text::GameTextManager::load).

The APK ships the game's full text table per language as assets/new__text__<lang>.bin
(sdrx::TextManager::loadTexts): big-endian u16 count, then (u16 length + UTF-8 key, u16 length +
UTF-8 value) pairs. In the texts, "|" is a line break, "{" the tick icon and ${...} a variable.
Keys missing from it get a placeholder derived from their name. A JSON file of the same shape
(texts_<lang>.json next to this script) takes precedence.
"""
import json
import os
import re
import struct
import zipfile

_KEY = re.compile(rb'STR_[A-Z0-9_]{2,80}')
_SUFFIXES = ('_ALLCAPS', '_UP_CASE', '_CAPITAL', '_CAPS', '_SMALL', '_SHORT')


def humanize(key):
    words = key[len('STR_'):]
    upper = False
    for suffix in _SUFFIXES:
        if words.endswith(suffix):
            upper = suffix in ('_ALLCAPS', '_CAPS', '_UP_CASE')
            words = words[:-len(suffix)]
            break
    text = words.replace('_', ' ').strip().lower()
    text = text[:1].upper() + text[1:]
    return text.upper() if upper else text


def collect_keys(apk_path):
    keys = set()
    with zipfile.ZipFile(apk_path) as z:
        for name in z.namelist():
            if name == 'lib/armeabi/libsdr.so' or (name.startswith('assets/') and name.endswith('.bin')):
                keys.update(m.decode() for m in _KEY.findall(z.read(name)))
    return keys


def read_text_table(data):
    """Parses a new__text__<lang>.bin text table into {key: text}."""
    count, = struct.unpack_from('>H', data, 0)
    pos, out = 2, {}

    def field():
        nonlocal pos
        n, = struct.unpack_from('>H', data, pos)
        raw = data[pos + 2:pos + 2 + n]
        pos += 2 + n
        try:
            return raw.decode('utf-8')
        except UnicodeDecodeError:
            return raw.decode('latin-1')
    for _ in range(count):
        key = field().strip()
        out[key] = field()
    return out


def apk_texts(apk_path, lang):
    with zipfile.ZipFile(apk_path) as z:
        names = set(z.namelist())
        for code in (lang, lang.split('-')[0].split('_')[0], 'en'):
            name = 'assets/new__text__%s.bin' % code.lower()
            if name in names:
                return read_text_table(z.read(name))
    return {}


def build(apk_path, lang='en'):
    bundle = {k: humanize(k) for k in sorted(collect_keys(apk_path))}
    bundle.update(apk_texts(apk_path, lang))
    override = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'texts_%s.json' % lang)
    if os.path.exists(override):
        with open(override, encoding='utf-8') as f:
            bundle.update(json.load(f))
    return bundle
