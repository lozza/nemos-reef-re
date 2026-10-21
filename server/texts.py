"""Builds the localized text bundle (getLocalizedTextsBundle) for the client.

The bundle is a flat JSON object {"STR_KEY": "text"}, sent as the response's "texts" member
(netcl::ActionGetLocalizedTextsBundle::loadingFinished → text::GameTextManager::load). The original
wording lived on the server and is lost, so every STR_ key referenced by the game code or UI files
gets a readable placeholder derived from its name. Real wording can be supplied in a JSON file of
the same shape (texts_<lang>.json next to this script), which takes precedence.
"""
import json
import os
import re
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


def build(apk_path, lang='en'):
    bundle = {k: humanize(k) for k in sorted(collect_keys(apk_path))}
    override = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'texts_%s.json' % lang)
    if os.path.exists(override):
        with open(override, encoding='utf-8') as f:
            bundle.update(json.load(f))
    return bundle
