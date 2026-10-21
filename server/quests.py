"""Quests: the story content (story.json) and the per-player quest state.

Quest progression is server-driven (see QUESTS.md): the client only runs quests the server gives it,
either in the startgame "quests" list (state 9 = running, 8 = offered) or pushed as a type-2 message.
The client detects task progress itself and reports each step with questTaskSetState; when every task
is finished the server credits the reward, records the quest as finished and pushes the next ones.

story.json holds the content: quests (with their tasks, rewards and the quests they unlock), dialogs,
hints, fish-attraction patterns and the English texts. Text ids are generated from the quest ids.
"""
import json
import os

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
