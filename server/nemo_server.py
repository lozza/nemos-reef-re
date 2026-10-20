#!/usr/bin/env python3
"""Private server for Nemo's Reef (Android 1.8.1). Standard library only.

    python nemo_server.py --apk nemos-reef-1-8-1-en-android.apk [--port 8080]

Answers both the Tapulous account API and the game API (see PROTOCOL.md). Every request and
response is appended to <data>/requests.log as JSON lines so unknown calls can be studied.
"""
import argparse
import email.parser
import email.policy
import json
import os
import random
import sqlite3
import string
import threading
import time
import traceback
import urllib.parse
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import texts
import worlddef

# 128-byte table from cypher::XorCypher::xorFuncChar; getDaWorld bodies are XORed with key[i & 0x7f].
XOR_KEY = bytes.fromhex(
    '06429d212c941939646215fa85a0450e8c554d4de90c3bb1378c14553e516e6f'
    'd612949349ca962ed836db1dda33eb4b0062ff1509de594593f7ba70ab310b15'
    'f6d28021eada52bc4ee5b46cf7c8038ecefb16a6c7c8640290237b4744de384e'
    '283a884cb8844c54df27b9152fc5b7ef0642705954041d2b05161d804590134a')

ENTITY_LISTS = ('corals', 'houses', 'decorations', 'livingPlants', 'ornamentalPlants',
                'fishes', 'quests', 'rarePlants', 'patches')


def xor(data):
    return bytes(b ^ XOR_KEY[i & 0x7f] for i, b in enumerate(data))


def now_ms():
    return int(time.time() * 1000)


class Store:
    """SQLite-backed users and worlds."""

    def __init__(self, path):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.Lock()
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                uid TEXT PRIMARY KEY, udid TEXT UNIQUE, name TEXT, secret TEXT, created INTEGER);
            CREATE TABLE IF NOT EXISTS worlds (uid TEXT PRIMARY KEY, world TEXT);
        ''')

    def user_by_udid(self, udid):
        with self.lock:
            r = self.db.execute('SELECT uid, name, secret FROM users WHERE udid=?', (udid,)).fetchone()
        return r and {'uid': r[0], 'name': r[1], 'secret': r[2]}

    def user(self, uid):
        with self.lock:
            r = self.db.execute('SELECT uid, name, secret FROM users WHERE uid=?', (uid,)).fetchone()
        return r and {'uid': r[0], 'name': r[1], 'secret': r[2]}

    def create_user(self, udid, name):
        uid = str(random.randint(10 ** 9, 10 ** 10 - 1))
        secret = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(16))
        with self.lock, self.db:
            self.db.execute('INSERT INTO users VALUES (?,?,?,?,?)', (uid, udid, name, secret, int(time.time())))
        return {'uid': uid, 'name': name, 'secret': secret}

    def rename(self, uid, name):
        with self.lock, self.db:
            self.db.execute('UPDATE users SET name=? WHERE uid=?', (name, uid))

    def world(self, uid):
        with self.lock:
            r = self.db.execute('SELECT world FROM worlds WHERE uid=?', (uid,)).fetchone()
        return json.loads(r[0]) if r else None

    def save_world(self, uid, world):
        with self.lock, self.db:
            self.db.execute('INSERT OR REPLACE INTO worlds VALUES (?,?)', (uid, json.dumps(world)))

    def delete_world(self, uid):
        with self.lock, self.db:
            self.db.execute('DELETE FROM worlds WHERE uid=?', (uid,))


def new_world(user):
    """A fresh reef. Keys follow World::processUserWorld / readEntities / data::UserStatus."""
    w = {name: [] for name in ENTITY_LISTS}
    w['user'] = {'uid': user['uid'], 'name': user['name']}
    w['finishedTutorialQuests'] = []
    w['status'] = {
        'hardMoney': 10, 'virtualMoney': 1000, 'energy': 20, 'level': 1, 'xp': 0,
        'xpForNextLevel': 50, 'lowTool': 0, 'highTool': 0, 'vitality': 100,
        'friendCollectCount': 0, 'friendCollectMaxCount': 10,
        'friendCollectInterval': {'start': 0, 'finish': 0},
        'lastSquirt': 0, 'squirtStarted': 0,
        'tapRewardsCount': 0, 'tapRewardsExtraTapAvail': False, 'tapRewardsGetAllAvail': False,
    }
    w['data'] = user_info()
    return w


def user_info():
    # data::UserStatus::loadUserInfo
    return {'resumeGame': False, 'moneySpent': 0, 'tapjoyMoneySpent': 0,
            'currentDailyRewardCountOffer': 0, 'lastDailyRewardCountClaimed': 0,
            'dailyTapRewardReady': False}


class Game:
    def __init__(self, args):
        os.makedirs(args.data, exist_ok=True)
        self.store = Store(os.path.join(args.data, 'nemo.db'))
        self.log_path = os.path.join(args.data, 'requests.log')
        self.log_lock = threading.Lock()
        if args.worlddef:
            with open(args.worlddef, 'rb') as f:
                self.worlddef = json.load(f)
            if not self.worlddef.get('version'):
                worlddef.finish(self.worlddef)
        else:
            self.worlddef = worlddef.build(args.apk)
        self.world_version = str(self.worlddef['version'])
        self.worlddef_blob = xor(json.dumps(self.worlddef, separators=(',', ':')).encode('utf-8'))
        with zipfile.ZipFile(args.apk) as z:
            self.bundles = json.loads(z.read('assets/bundle.json'))
        self.apk = args.apk
        self.texts = {}
        self.server_id = '1'

    def log(self, entry):
        with self.log_lock, open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    # ---------------------------------------------------------------- Tapulous account API
    def tap_user(self, p):
        udid = p.get('token_info') or p.get('udid') or 'unknown'
        return self.store.user_by_udid(udid) or self.store.create_user(udid, 'Diver' + udid[-4:])

    def tap(self, method, p):
        if method == 'recommend_name':
            return {'response': {'suggestedName': 'Diver%04d' % random.randint(0, 9999)}}
        user = self.tap_user(p)
        if method == 'register_user':
            name = p.get('proposed_name') or user['name']
            self.store.rename(user['uid'], name)
            return {'response': {'user': {'user_id': user['uid'], 'username': name}}}
        if method == 'change_username':
            name = p.get('new_username') or user['name']
            self.store.rename(user['uid'], name)
            return {'response': {'user_id': user['uid'], 'username': name}}
        if method == 'authenticate':
            return {'response': {'user_id': user['uid'], 'username': user['name']},
                    'attachedData': {'clientSignatureKey': user['secret']}}
        if method in ('login', 'logout'):
            return {'response': {'user_id': user['uid'], 'username': user['name']}}
        if method == 'get_friends':
            return {'response': {'friends': []}}
        if method == 'add_friend':
            return {'status': {'code': 404, 'reason': 'Friends are not supported yet'}}
        return None

    # ---------------------------------------------------------------- game API
    def envelope(self, body, req):
        body.setdefault('resultCode', 200)
        body.setdefault('serverTime', now_ms())
        body.setdefault('serverId', self.server_id)
        body.setdefault('stamp', req.get('stamp', 0))
        return body

    def user_world(self, uid):
        user = self.store.user(uid)
        if not user:
            return None
        w = self.store.world(uid)
        if w is None:
            w = new_world(user)
            self.store.save_world(uid, w)
        return w

    def game(self, endpoint, p):
        """Returns (bytes, content_type)."""
        req = {}
        if p.get('json'):
            try:
                req = json.loads(p['json'])
            except ValueError:
                pass
        uid = p.get('uid') or req.get('uid') or ''

        if endpoint == 'getdaworld':
            return self.worlddef_blob, 'application/octet-stream'
        if endpoint == 'getcurrentworldversion':
            body = {'worldVersion': self.world_version}
        elif endpoint in ('startgame', 'gettutorialworld'):
            body = dict(self.user_world(uid) or new_world({'uid': uid, 'name': 'Diver'}))
        elif endpoint == 'getfriendworld':
            body = dict(self.user_world(req.get('friendId') or req.get('requestedUid') or uid) or {})
        elif endpoint == 'reset':
            self.store.delete_world(uid)
            body = {}
        elif endpoint == 'resources':
            body = self.bundles
        elif endpoint in ('getfriendstatus', 'getfriendlasttime'):
            body = {'friends': []}
        elif endpoint == 'getlocalizedtextsbundle':
            # The whole response object is the {"STR_KEY": "text"} dictionary, so no envelope fields.
            lang = req.get('languageCode') or 'en'
            if lang not in self.texts:
                self.texts[lang] = texts.build(self.apk, lang)
            return json.dumps(self.texts[lang], ensure_ascii=False).encode('utf-8'), 'application/json'
        else:  # '/api': queued game actions
            body = {'reactions': [self.reaction(uid, a) for a in req.get('actions', [])]}
        return json.dumps(self.envelope(body, req)).encode('utf-8'), 'application/json'

    def reaction(self, uid, action):
        r = {'aid': action.get('aid'), 'resultCode': 200}
        if action.get('action') == 'resumeGame':
            r['data'] = user_info()
        return r


class Handler(BaseHTTPRequestHandler):
    game = None
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *args):
        pass

    def params(self, body):
        url = urllib.parse.urlsplit(self.path)
        p = {k: v[-1] for k, v in urllib.parse.parse_qs(url.query, keep_blank_values=True).items()}
        ctype = self.headers.get('Content-Type', '')
        if ctype.startswith('multipart/'):
            msg = email.parser.BytesParser(policy=email.policy.HTTP).parsebytes(
                b'Content-Type: ' + ctype.encode() + b'\r\n\r\n' + body)
            for part in msg.iter_parts():
                name = part.get_param('name', header='content-disposition')
                if name:
                    p[name] = part.get_payload(decode=True).decode('utf-8', 'replace')
        elif body:
            text = body.decode('utf-8', 'replace')
            if text.lstrip().startswith('{'):
                p.setdefault('json', text)
            else:
                p.update({k: v[-1] for k, v in urllib.parse.parse_qs(text, keep_blank_values=True).items()})
        return url.path, p

    def handle_any(self):
        n = int(self.headers.get('Content-Length') or 0)
        body = self.rfile.read(n) if n else b''
        path, p = self.params(body)
        segs = [s for s in path.split('/') if s]
        endpoint = (segs[-1] if segs else '').lower()
        if 'resources' in [s.lower() for s in segs]:
            endpoint = 'resources'
        try:
            tap = self.game.tap(endpoint, p)
            if tap is not None:
                out, ctype = json.dumps(tap).encode('utf-8'), 'application/json'
            else:
                out, ctype = self.game.game(endpoint, p)
            status = 200
        except Exception:
            traceback.print_exc()
            out, ctype, status = b'{"resultCode":500}', 'application/json', 500
        self.send_response(status)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(out)))
        self.end_headers()
        self.wfile.write(out)
        shown = '<%d bytes xor>' % len(out) if endpoint == 'getdaworld' else out.decode('utf-8', 'replace')[:4000]
        self.game.log({'t': time.strftime('%H:%M:%S'), 'method': self.command, 'path': self.path,
                       'params': p, 'status': status, 'response': shown})
        print('%s %s %s -> %d (%d bytes)' % (time.strftime('%H:%M:%S'), self.command, path, status, len(out)))

    do_GET = do_POST = handle_any


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--apk', required=True, help='original nemos-reef 1.8.1 APK (prototypes, bundle.json)')
    ap.add_argument('--host', default='0.0.0.0')
    ap.add_argument('--port', type=int, default=8080)
    ap.add_argument('--data', default='data', help='directory for the database and request log')
    ap.add_argument('--worlddef', help='use this worldDef JSON instead of generating one')
    args = ap.parse_args()
    Handler.game = Game(args)
    print('Nemo\'s Reef server on http://%s:%d  (world version %s, log: %s)'
          % (args.host, args.port, Handler.game.world_version, Handler.game.log_path))
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
