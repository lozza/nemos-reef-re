#!/usr/bin/env python3
"""Private server for Nemo's Reef (Android 1.8.1). Standard library only.

    python nemo_server.py --apk nemos-reef-1-8-1-en-android.apk [--port 8080]

Answers both the Tapulous account API and the game API (see PROTOCOL.md and ACTIONS.md). Every request and
response is appended to <data>/requests.log as JSON lines so unknown calls can be studied.
"""
import argparse
import email.parser
import email.policy
import hashlib
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

import actions
import iscn
import quests
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
    # mapunlock::MapUnlockerBase::load runs only if "sectors" exists: it unlocks "base" plus every
    # area named in the list (scene areas: tiles, tiles_2 ... tiles_8). Without it the map stays locked.
    # It recomputes the unlocked tiles only when the list is non-empty, so "base" is always listed.
    w['sectors'] = ['base']
    w['status'] = {
        'hardMoney': 10, 'virtualMoney': 100, 'energy': 100, 'level': 1, 'xp': 0,
        'xpForNextLevel': 50, 'lowTool': 0, 'highTool': 0,
        # data::Vitality::load: {vitality, level (optional), categories[{categoryId, ...}]}
        'vitality': {'vitality': 100, 'level': 1, 'categories': []},
        'friendCollectCount': 0, 'friendCollectMaxCount': FRIEND_ACTIONS,
        'friendCollectInterval': {'start': 0, 'finish': 0},
        'lastSquirt': 0, 'squirtStarted': 0,
        'tapRewardsCount': 0, 'tapRewardsExtraTapAvail': False, 'tapRewardsGetAllAvail': False,
    }
    w['data'] = user_info()
    return w


SECTOR_ADDED = 9  # message type
# reef areas (level.iscn tile groups) in order outward from "base", and the level each opens at
EXPANSIONS = [(4, 'tiles'), (8, 'tiles_2'), (12, 'tiles_3'), (16, 'tiles_4'), (21, 'tiles_5'), (27, 'tiles_6'),
              (33, 'tiles_7'), (40, 'tiles_8')]
FRIEND_UID = 'friend_nemo'
FRIEND_ACTIONS = 5  # "Daily Actions: 5/5" on a friend's reef


def user_info(w=None):
    # data::UserStatus::loadUserInfo(obj): if obj has "resumeGame", reads these fields inside it.
    # dailyTapRewardReady opens the daily reward (DailyRewardManager::checkDailyRewards).
    ready = bool(w) and actions.Reef.daily_taps_left(w) > 0
    return {'resumeGame': {'moneySpent': False, 'tapjoyMoneySpent': False,
                           'currentDailyRewardCountOffer': 0, 'lastDailyRewardCountClaimed': 0,
                           'dailyTapRewardReady': ready}}


class Game:
    def __init__(self, args):
        os.makedirs(args.data, exist_ok=True)
        self.store = Store(os.path.join(args.data, 'nemo.db'))
        self.log_path = os.path.join(args.data, 'requests.log')
        self.log_lock = threading.Lock()
        self.world_lock = threading.Lock()
        self.story = quests.NoStory() if args.no_story else quests.Story()
        if args.worlddef:
            with open(args.worlddef, 'rb') as f:
                self.worlddef = json.load(f)
            if not self.worlddef.get('version'):
                worlddef.finish(self.worlddef)
        else:
            self.worlddef = worlddef.build(args.apk, self.story)
        self.reef = actions.Reef(actions.Prototypes(self.worlddef))
        self.dummy_friend = None
        # The client keeps one downloaded text bundle and only asks again when this id changes
        # (GameTextManager::existTextBundle), so the id covers every text the server sends.
        h = hashlib.sha1(str(self.worlddef.get('localizedTextsBundleId')).encode())
        h.update(json.dumps(texts.build(args.apk, 'en'), sort_keys=True).encode('utf-8'))
        self.worlddef['localizedTextsBundleId'] = 2 + int(h.hexdigest()[:7], 16)
        worlddef.finish(self.worlddef)  # new version stamp, so clients fetch the definition with the new id
        self.world_version = str(self.worlddef['version'])
        self.worlddef_blob = xor(json.dumps(self.worlddef, separators=(',', ':')).encode('utf-8'))
        with zipfile.ZipFile(args.apk) as z:
            self.bundles = json.loads(z.read('assets/bundle.json'))
            # The designed starting layout; nemo_2/_3 are later upgrade stages of the same anemone and
            # Peach's house belongs to a later area.
            self.starter = [e for e in iscn.entities(z.read('assets/level.iscn'))
                            if e['ipro'][:-5] not in ('spec_house_nemo_2', 'spec_house_nemo_3', 'spec_house_peach')]
        if args.reset_worlds:
            with self.store.lock, self.store.db:
                self.store.db.execute('DELETE FROM worlds')
            print('all reefs reset: every player starts again with the starter reef')
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
            self.starter_reef(w)
            self.story.new_player(w)
            self.store.save_world(uid, w)
        elif (not isinstance(w.get('status', {}).get('vitality'), dict)
              or not isinstance(w.get('data', {}).get('resumeGame'), dict)
              or not w.get('sectors')):  # worlds saved by older versions
            w['status']['vitality'] = new_world(user)['status']['vitality']
            w['data'] = user_info()
            w['sectors'] = w.get('sectors') or ['base']
            self.store.save_world(uid, w)
        if self.story.migrate(w):
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
        elif endpoint in ('gettutorialworld', 'getfriendworld'):
            body = self.friend_world(uid)
        elif endpoint == 'startgame':
            w = self.user_world(uid)
            if w:
                with self.world_lock:
                    self.reef.events = []
                    self.reef.refresh(w, now_ms())
                    self.finish_visit(w)
                    self.reef.new_day(w)
                    self.expand(w, push=False)
                    self.story.catch_up(w, push=False)  # in the startgame quests list
                    # quest messages are covered by the quests list; entity events still have to be pushed
                    w['messages'] = [m for m in w.get('messages', []) if m['type'] != quests.QUEST_OPEN]
                    self.push_events(w)
                    self.unstick_quests(w)
                    self.store.save_world(uid, w)
            body = dict(w or new_world({'uid': uid, 'name': 'Diver'}))
            for k in ('nextEntityId', 'nextQuestId', 'nextMessageId', 'messages', 'patterns'):
                body.pop(k, None)
            # World::processUserWorld passes the root to data::TheUser::updateUserInfo
            body['resumeGame'] = user_info(w)['resumeGame']
            for k in ('moneySpent', 'tapjoyMoneySpent', 'currentDailyRewardCountOffer',
                      'lastDailyRewardCountClaimed', 'dailyTapRewardReady'):
                body.pop(k, None)  # flat copies sent by older versions
        elif endpoint == 'reset':
            self.store.delete_world(uid)
            body = {}
        elif endpoint == 'resources':
            body = self.bundles
        elif endpoint in ('getfriendstatus', 'getfriendlasttime'):
            body = {'participants': []}  # data::FriendList::update reads "participants" (a missing key crashes)
        elif endpoint == 'getlocalizedtextsbundle':
            # ActionGetLocalizedTextsBundle::loadingFinished hands response["texts"] to GameTextManager::load.
            lang = p.get('languageCode') or req.get('languageCode') or 'en'
            if lang not in self.texts:
                self.texts[lang] = texts.build(self.apk, lang)
                self.texts[lang].update(self.story.texts())
            body = {'texts': self.texts[lang]}
        else:  # '/api': queued game actions
            with self.world_lock:
                w = self.user_world(uid)
                self.reef.events = []
                body = {'reactions': [self.reaction(w, a) for a in req.get('actions', [])]}
                if w:
                    self.reef.refresh(w, now_ms())
                    self.push_events(w)
                    self.story.catch_up(w)  # quests that open with a level-up
                    self.expand(w)
                    # The client never changes currencies itself: the HUD only updates from a "status"
                    # object next to the reactions (ComManager::loadingFinished → updateUserStatus).
                    body['status'] = w['status']
                    if w.get('messages'):
                        body['messages'] = list(w['messages'])
                    self.store.save_world(uid, w)
        return json.dumps(self.envelope(body, req)).encode('utf-8'), 'application/json'

    def reaction(self, w, action):
        if action.get('action') == 'resumeGame':
            return {'aid': action.get('aid'), 'resultCode': 200, 'data': user_info(w)}
        if w is None:
            return {'aid': action.get('aid'), 'resultCode': 200}
        try:
            name, d = action.get('action'), action.get('data') or {}
            ok = {'aid': action.get('aid'), 'resultCode': 200}
            if name == 'questTaskSetState':
                return dict(ok, data=self.story.task_state(w, d, lambda q, r: self.quest_done(w, q, r)))
            if name == 'questStart':
                self.story.start(w, d)
                return ok
            if name == 'questBuyHint':
                self.story.buy_hint(w, d, self.reef.pay)
                return ok
            if name == 'confirmMessages':
                self.story.confirm(w, d)
                return ok
            if name == 'savePattern':
                if d.get('patternId') and d['patternId'] not in w.setdefault('patterns', []):
                    w['patterns'].append(d['patternId'])
                return ok
            if name == 'buyPatternHint':
                return ok
            if name == 'friendsEntityCollectReward':
                return dict(ok, data=self.friend_collect(w, d))
            return self.reef.apply(w, action, now_ms())
        except Exception:
            traceback.print_exc()
            return {'aid': action.get('aid'), 'resultCode': 200, 'data': {}}


    def push_events(self, w):
        events, self.reef.events = self.reef.events, []
        for kind, data in events:
            w.setdefault('messages', []).append({'id': self.story.message_id(w), 'type': kind, 'data': data})
            if kind == actions.END_FEED:
                self.attract_rare_fish(w, data['id'])

    def attract_rare_fish(self, w, plant_id):
        """A rare plant has grown: the rare fish that loves it comes to the reef (or, for plants without a
        partner, a rare fish the reef does not have yet). A reef welcomes one fish of each kind."""
        e = next((x for x in w.get('rarePlants', []) if x['id'] == plant_id), None)
        rare = self.story.data.get('rareFish') or {}
        if not e or e.get('attracted') or not rare.get('all'):
            return
        e['attracted'] = True
        owned = {f.get('prototypeId') for f in w.get('fishes', [])}
        fish = rare.get('pairs', {}).get(e['prototypeId'])
        if not fish or fish in owned:
            fish = next((f for f in rare['all'] if f not in owned), None)
        if not fish:
            return
        pos = e.get('position', {})
        f = self.reef.add_entity(w, fish, pos.get('x', 80), pos.get('z', 80))
        if f:  # message type 1: EntityManager::processFishAddedMessage swims the fish in
            w.setdefault('messages', []).append({'id': self.story.message_id(w), 'type': 1, 'data': dict(f)})

    def unstick_quests(self, w):
        """A running grow/build task whose item is already grown/built (finished while the game was closed,
        or before the server sent completion messages) never ticks, so resend the completion message."""
        queued = {(m['type'], m['data'].get('id')) for m in w.get('messages', []) if isinstance(m.get('data'), dict)}
        for q in w.get('quests', []):
            proto = self.story.quests.get(q['prototypeId'], {})
            for i, task in enumerate(proto.get('tasks', [])):
                st = next((t for t in q['tasks'] if t['tid'] == i + 1), {})
                if st.get('finished') or task['cid'] not in ('CID_GROWN', 'CID_BUILT') or len(task.get('params', [])) < 2:
                    continue
                for lst in ('corals', 'livingPlants', 'ornamentalPlants', 'rarePlants', 'houses', 'decorations', 'patches'):
                    for e in w.get(lst, []):
                        if e.get('prototypeId') != task['params'][1]:
                            continue
                        if task['cid'] == 'CID_GROWN' and e.get('state') in (actions.BUILT, actions.PRODUCING, actions.READY):
                            msg = (actions.END_FEED, {'id': e['id'], 'state': e['state']})
                        elif task['cid'] == 'CID_BUILT' and e.get('state') == actions.BUILT:
                            msg = (actions.END_CONSTRUCT, {'id': e['id']})
                        else:
                            continue
                        if (msg[0], e['id']) not in queued:
                            queued.add((msg[0], e['id']))
                            w.setdefault('messages', []).append({'id': self.story.message_id(w), 'type': msg[0], 'data': msg[1]})

    def friend_world(self, uid):
        """The reef shown when visiting a friend. "Random friend" (CU::visitRandomPlayer) asks for the tutorial
        world; there are no other players, so every visit shows Nemo's starter reef. World::processUserWorld
        reads "friendStatus" (data::FriendStatus::load: hardMoney, virtualMoney, level, xp, energy,
        xpForNextLevel) and "user" {name, uid} for the visited friend; "status" is still the visitor's own."""
        if self.dummy_friend is None:
            f = new_world({'uid': FRIEND_UID, 'name': 'Tad'})
            self.starter_reef(f)
            # A lived-in reef like the one visited in the Let's Play: corals and plants ready to help with,
            # Dory, a lionfish and a seahorse.
            for pid, x, z in (('coral_sunset_cup', 88, 80), ('coral_fruit_loop', 80, 73), ('plant_table_yellow', 72, 81),
                              ('plant_table_yellow', 84, 76), ('plant_barrel_sponge', 82, 83), ('deco_rock', 70, 83),
                              ('fish_special_dory', 81, 79), ('fish_rare_lion', 83, 81), ('fish_guest_seahorse', 78, 84)):
                self.reef.add_entity(f, pid, x, z)
            f['quests'] = []
            for k in ('nextEntityId', 'nextQuestId', 'nextMessageId', 'messages', 'patterns'):
                f.pop(k, None)
            self.dummy_friend = f
        body = json.loads(json.dumps(self.dummy_friend))
        body['friendStatus'] = {k: body['status'][k] for k in
                                ('hardMoney', 'virtualMoney', 'level', 'xp', 'energy', 'xpForNextLevel')}
        body['friendStatus'].update(level=7, xp=1300, xpForNextLevel=1300)
        body['resumeGame'] = user_info()['resumeGame']
        with self.world_lock:
            w = self.user_world(uid)
            if w:
                today = time.strftime('%Y-%m-%d')
                if w.get('friendActionsDay') != today:
                    w['friendActionsDay'] = today
                    w['status']['friendCollectCount'] = 0
                w['status']['friendCollectMaxCount'] = FRIEND_ACTIONS
                body['status'] = w['status']
                w['visitedFriend'] = True
                self.store.save_world(uid, w)
        return body

    def friend_collect(self, w, d):
        """friendsEntityCollectReward {id, friendUid}: a tap on a friend's ready item. The visitor gets the item's
        friendReward; the item's Harvestable::processResponseCollect reads its next "producingInterval"."""
        now = now_ms()
        lst, e = self.reef.find(self.dummy_friend or {}, d.get('id'))
        _, p = self.reef.protos.get(e['prototypeId']) if e else (None, None)
        p = p or {}
        st = w['status']
        if st.get('friendCollectCount', 0) < st.get('friendCollectMaxCount', FRIEND_ACTIONS):
            st['friendCollectCount'] = st.get('friendCollectCount', 0) + 1
            self.reef.earn(w, p.get('friendReward'))
        return {'producingInterval': actions.interval(now, self.reef.ms(p, 'producingTime'))}

    def finish_visit(self, w):
        """Back home after a visit: finishes a "Visit a Friend's Reef" task the client did not report itself."""
        if not w.pop('visitedFriend', False):
            return
        for q in list(w.get('quests', [])):
            proto = self.story.quests.get(q['prototypeId'], {})
            for i, task in enumerate(proto.get('tasks', []), 1):
                if task['cid'] == 'CID_FRIEND_VISIT':
                    self.story.task_state(w, {'id': q['id'], 'tid': i, 'finished': True},
                                          lambda qq, r: self.quest_done(w, qq, r))

    def starter_reef(self, w):
        now = now_ms()
        for e in self.starter:
            self.reef.add_entity(w, e['ipro'][:-5], e['x'], e['z'], e['mirror'], now)
        for fish, x, z in (('fish_special_nemo', 77, 79), ('fish_special_marlin', 79, 78)):
            self.reef.add_entity(w, fish, x, z)

    def quest_done(self, w, q, reward):
        """A quest's last task finished: reward, fish that move in, newly opened areas."""
        self.reef.earn(w, reward)
        for fish in q.get('grantFish', []):
            if not any(e.get('prototypeId') == fish for e in w.get('fishes', [])):
                e = self.reef.add_entity(w, fish, 82, 84)
                if e:  # message type 1: EntityManager::processFishAddedMessage swims the fish in now
                    w.setdefault('messages', []).append({'id': self.story.message_id(w), 'type': 1, 'data': dict(e)})
        for sector in q.get('unlockSectors', []):
            self.unlock_sector(w, sector)

    def unlock_sector(self, w, sector, push=True):
        """Opens a reef area. Message type 9 {"sector": name} makes IsoMap::processSectorAdded unlock it with the
        "Your reef has expanded!" scene (ScriptMapUnlocked); at startgame the "sectors" list is enough."""
        if sector in w['sectors']:
            return
        w['sectors'].append(sector)
        if push:
            w.setdefault('messages', []).append({'id': self.story.message_id(w), 'type': SECTOR_ADDED,
                                                 'data': {'sector': sector}})

    def expand(self, w, push=True):
        """Reef expansions. The original opened them as friends joined; with no other players they come with
        levels instead, the first at level 4 as in the Let's Play."""
        level = int(w['status'].get('level', 1))
        for need, sector in EXPANSIONS:
            if level >= need:
                self.unlock_sector(w, sector, push)


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
    ap.add_argument('--reset-worlds', action='store_true',
                    help='delete every saved reef (accounts are kept); players get the starter reef again')
    ap.add_argument('--no-story', action='store_true', help='turn off the story quests (story.json)')
    args = ap.parse_args()
    Handler.game = Game(args)
    print('Nemo\'s Reef server on http://%s:%d  (world version %s, log: %s)'
          % (args.host, args.port, Handler.game.world_version, Handler.game.log_path))
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
