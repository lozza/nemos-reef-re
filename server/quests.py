"""Quests: the story content (story.json) and the per-player quest state.

Quest progression is server-driven (see QUESTS.md): the client only runs quests the server gives it,
either in the startgame "quests" list (state 9 = running, 8 = offered) or pushed as a type-2 message.
The client detects task progress itself and reports each step with questTaskSetState; when every task
is finished the server credits the reward, records the quest as finished and pushes the next ones.

story.json holds the content: quests (with their tasks, rewards and the quests they unlock), dialogs,
hints, fish-attraction patterns and the English texts. Text ids are generated from the quest ids.
"""
import copy
import glob
import hashlib
import json
import os

import worlddef

STORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'story.json')
RUNNING, OFFERED = 9, 8
QUEST_OPEN, QUEST_FINISH = 2, 6  # message types


def reward(r):
    r = r or {}
    return {k: int(r.get(k, 0)) for k in ('xp', 'virtualMoney', 'energy', 'hardMoney', 'lowTool', 'highTool')}


def cost(c):
    c = c or {}
    return {k: int(c.get(k, 0)) for k in ('energy', 'virtualMoney', 'hardMoney', 'lowTool', 'highTool')}


class Story:
    def __init__(self, path=STORY):
        with open(path, encoding='utf-8') as f:
            self.data = json.load(f)
        self.quests = {q['id']: q for q in self.data['quests']}
        self.first = self.data['first']

    # ------------------------------------------------------------ worldDef / texts
    def texts(self):
        t = dict(self.data.get('texts', {}))
        for q in self.data['quests']:
            key = q['id'].upper()
            t['STR_%s_TITLE' % key] = q.get('title', '')
            t['STR_%s_DESC' % key] = q.get('description', '')
            if q.get('completed'):
                t['STR_%s_DONE' % key] = q['completed']
            for i, task in enumerate(q.get('tasks', []), 1):
                t['STR_%s_TASK%d' % (key, i)] = task['text']
        for d in self.data.get('dialogs', []):
            for i, line in enumerate(d['lines'], 1):
                t['STR_DLG_%s_%d' % (d['id'].upper(), i)] = line[2]
        for h in self.data.get('hints', []):
            t['STR_HINT_%s' % h['id'].upper()] = h['text']
        return t

    def extend_worlddef(self, wd):
        self.add_items(wd)
        # The client keeps a downloaded texts bundle per (id, language) and never asks again for an id it
        # already has (Action_GetTextBundle::canSkipNetAction), so the id must change whenever the texts do.
        h = hashlib.sha1(json.dumps(self.texts(), sort_keys=True).encode('utf-8'))
        for f in sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'texts_*.json'))):
            with open(f, 'rb') as fh:
                h.update(fh.read())
        wd['localizedTextsBundleId'] = 2 + int(h.hexdigest()[:7], 16)
        wd['questPrototypeList'] = [self.quest_prototype(q) for q in self.data['quests']]
        wd['dialogPrototypeList'] = [
            {'id': d['id'], 'conditionList': [
                {'position': side, 'actorId': actor, 'toActorId': listener,
                 'textId': 'STR_DLG_%s_%d' % (d['id'].upper(), i)}
                for i, (side, actor, _text, listener) in enumerate(
                    [(l[0], l[1], l[2], l[3] if len(l) > 3 else '') for l in d['lines']], 1)]}
            for d in self.data.get('dialogs', [])]
        wd['hintPrototypeList'] = [{'id': h['id'], 'cost': cost(h.get('cost')), 'index': h.get('index', 0),
                                    'textId': 'STR_HINT_%s' % h['id'].upper()} for h in self.data.get('hints', [])]
        wd['patternList'] = [dict(p, centralHintCost=cost(p.get('centralHintCost')),
                                  sorroundingHintCost=cost(p.get('sorroundingHintCost')))
                             for p in self.data.get('patterns', [])]
        wd['conditionDefinitionList'] = []
        self.check(wd)

    def add_items(self, wd):
        """Colour variants and the real shop values from story.json "items"."""
        wd['colorVariantList'] = [{'id': c, 'color': {'alpha': 255, 'red': v[0], 'green': v[1], 'blue': v[2]}}
                                  for c, v in self.data.get('colors', {}).items()]
        lists = [k for k in wd if k.endswith('PrototypeList') or k == 'patchList']
        by_id = {p['id']: (k, p) for k in lists if isinstance(wd[k], list) for p in wd[k] if isinstance(p, dict)}
        shop = {s['prototypeId']: s for s in wd['ingameShopItems']}
        has_variants = set()
        for pid, it in self.data.get('items', {}).items():
            base = it.get('base')
            if base:
                if base not in by_id:
                    raise ValueError('item %s: unknown base prototype %s' % (pid, base))
                lst, bp = by_id[base]
                p = copy.deepcopy(bp)
                p['id'] = pid
                p['graphicalId'] = base
                wd[lst].append(p)
                by_id[pid] = (lst, p)
                has_variants.add(base)
            elif pid in by_id:
                p = by_id[pid][1]
            else:
                raise ValueError('item %s: unknown prototype' % pid)
            if it.get('color'):
                p['colorVariantId'] = it['color']
            if it.get('name'):
                p['name'] = p['nameId'] = it['name']
            if it.get('price'):
                pc = it['price']
                p['cost'] = worlddef.cost(coins=pc.get('virtualMoney', 0), pearls=pc.get('hardMoney', 0))
                p['refundReward'] = worlddef.reward(coins=p['cost']['virtualMoney'] // 2)
            if 'feed' in it:
                p['growingCycleCost'] = worlddef.cost(algae=it['feed'])
            if 'step' in it:
                p['growingTime'] = worlddef.duration(it['step'])
            if 'produce' in it:
                pr = it['produce']
                p['producedReward'] = worlddef.reward(xp=pr.get('xp', 0), coins=pr.get('virtualMoney', 0),
                                                      algae=pr.get('energy', 0))
            if 'every' in it:
                p['producingTime'] = worlddef.duration(it['every'])
            if 'hearts' in it:
                p['vitality'] = it['hearts']
            if 'build' in it:
                p['constructionTime'] = worlddef.duration(it['build'])
            shop[pid] = worlddef.shop_item(p)
        # bases sold only as colour variants would show grey in the shop
        wd['ingameShopItems'] = [s for pid, s in shop.items() if pid not in has_variants]

    def check(self, wd):
        """Every prototype the story refers to must exist, or the client crashes."""
        ids = {p['id'] for k, v in wd.items() if isinstance(v, list) for p in v if isinstance(p, dict) and 'id' in p}
        missing = set()
        for q in self.data['quests']:
            for t in q.get('tasks', []):
                params = t.get('params', [])
                if len(params) > 1 and t['cid'] not in ('CID_PATTERN', 'CID_DIALOG_FINISHED') and params[1] not in ids:
                    missing.add(params[1])
            for f in [q.get('giver', 'fish_special_nemo')] + q.get('grantFish', []):
                if f not in ids:
                    missing.add(f)
        for d in self.data.get('dialogs', []):
            missing.update(a for l in d['lines'] for a in l[1:2] + l[3:4] if a and a not in ids)
        for pt in self.data.get('patterns', []):
            missing.update(x for x in [pt['centralPrototype'], pt['producedFishId']] + pt['nearPrototypes'] if x not in ids)
        if missing:
            raise ValueError('story.json refers to unknown prototypes: %s' % ', '.join(sorted(missing)))

    def quest_prototype(self, q):
        key = q['id'].upper()
        p = {
            'id': q['id'],
            'type': q.get('type', 'STORY'),
            'autoStart': q.get('autoStart', True),
            'questGiverId': q.get('giver', 'fish_special_nemo'),
            'nameStringId': 'STR_%s_TITLE' % key,
            'descriptionStringId': 'STR_%s_DESC' % key,
            'reward': reward(q.get('reward')),
            'endConditionList': [
                {'tid': i, 'textId': 'STR_%s_TASK%d' % (key, i), 'conditionDefinitionId': t['cid'],
                 'parameterValueList': [{'index': n, 'value': str(v)} for n, v in enumerate(t.get('params', []), 1)]}
                for i, t in enumerate(q.get('tasks', []), 1)],
        }
        for k in ('startDialogId', 'endDialogId', 'hintIdList', 'rewardPrototypeIdList'):
            if q.get(k):
                p[k] = q[k]
        return p

    # ------------------------------------------------------------ player state
    def new_player(self, w):
        w['quests'] = []
        w['finishedTutorialQuests'] = []
        w['messages'] = []
        w['nextQuestId'] = 1
        for qid in self.first:
            self.open(w, qid, push=False)

    def migrate(self, w):
        if 'nextQuestId' not in w:
            done = set(w.get('finishedTutorialQuests') or [])
            w['finishedTutorialQuests'] = [q for q in done if q in self.quests]
            w['messages'] = []
            w['nextQuestId'] = 1
            w['quests'] = [q for q in w.get('quests', []) if q.get('prototypeId') in self.quests]
            if not w['quests'] and not w['finishedTutorialQuests']:
                for qid in self.first:
                    self.open(w, qid, push=False)

    def open(self, w, qid, push=True):
        q = self.quests.get(qid)
        if not q or qid in w['finishedTutorialQuests'] or any(e['prototypeId'] == qid for e in w['quests']):
            return
        sid = w['nextQuestId']
        w['nextQuestId'] += 1
        entry = {'prototypeId': qid, 'id': sid, 'state': RUNNING if q.get('autoStart', True) else OFFERED,
                 'tasks': [{'tid': i, 'progress': {}} for i in range(1, len(q.get('tasks', [])) + 1)]}
        w['quests'].append(entry)
        if push:
            w['messages'].append({'id': self.message_id(w), 'type': QUEST_OPEN,
                                  'data': {'prototypeId': qid, 'id': sid, 'tasks': []}})

    @staticmethod
    def message_id(w):
        n = w.get('nextMessageId', 1)
        w['nextMessageId'] = n + 1
        return n

    def find(self, w, sid):
        return next((e for e in w['quests'] if e['id'] == sid), None)

    def start(self, w, d):
        e = self.find(w, d.get('id'))
        if e:
            e['state'] = RUNNING

    def task_state(self, w, d, finish):
        """questTaskSetState: returns {"questFinished": bool}."""
        e = self.find(w, d.get('id'))
        if not e:
            return {'questFinished': False}
        tid = d.get('tid')
        task = next((t for t in e['tasks'] if t['tid'] == tid), None)
        if task is None:
            task = {'tid': tid, 'progress': {}}
            e['tasks'].append(task)
        prog = {k: v for k, v in (d.get('progress') or {}).items() if v not in (None, '')}
        if prog.get('state') == 2:
            prog['state'] = 1  # finished tasks are marked with "finished" instead
        task['progress'].update(prog)
        if d.get('finished'):
            task['finished'] = True
            task['progress']['counter'] = 0
        q = self.quests.get(e['prototypeId'], {})
        done = len(e['tasks']) >= len(q.get('tasks', [])) and all(t.get('finished') for t in e['tasks'])
        if done:
            finish(q, d.get('reward') or q.get('reward'))
            w['quests'].remove(e)
            if e['prototypeId'] not in w['finishedTutorialQuests']:
                w['finishedTutorialQuests'].append(e['prototypeId'])
            for nxt in q.get('next', []):
                self.open(w, nxt)
        return {'questFinished': done}

    def buy_hint(self, w, d, pay):
        e = self.find(w, d.get('id'))
        if not e:
            return
        q = self.quests.get(e['prototypeId'], {})
        idx = int(d.get('hintIndex', 0))
        hint = next((h for h in self.data.get('hints', [])
                     if h['id'] in q.get('hintIdList', []) and h.get('index', 0) == idx), None)
        if hint:
            pay(hint.get('cost'))
        e['hintPurchasedIndex'] = max(idx, e.get('hintPurchasedIndex', -1))

    def confirm(self, w, d):
        ids = set(d.get('ids') or [])
        w['messages'] = [m for m in w.get('messages', []) if m['id'] not in ids]


class NoStory(Story):
    """No quests: the client gets empty quest data, as before the story existed."""

    def __init__(self):
        self.data = {'quests': [], 'dialogs': [], 'hints': [], 'patterns': []}
        self.quests = {}
        self.first = []
