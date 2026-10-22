#!/usr/bin/env python3
"""Builds server/story.json from the quest catalogue and the fan wiki's numbers.

    python3 tools/build_story.py --catalog <dir> --wiki <wiki_gamedata.json> --apk nemo.apk [--out server/story.json]

The catalogue (quests.json, dialogs.json, items.json) is made from the game's own text table
(assets/new__text__en.bin): every quest, task, dialog line and item name there has a text key, and
story.json refers to those keys only. The server reads the texts from the APK at run time, in every
language the game ships, so no game text is copied into story.json.

What the generator decides (the catalogue only has the texts):
* which quests are offered: story, side, Tank Gang, narrative scenes, the vitality and rare-fish
  tutorials, Crush & Squirt and the guest missions. Quests that need features the server does not
  have yet (co-op, homework, patches) are left out.
* when: the Let's Play order (parts 1-2) for the early game; after that a level per quest (the
  catalogue's level band, anchored on the Tank Gang arrival levels) and chains (story quests in
  number order, A/B/C parts, guest missions one at a time).
* rewards: the ones seen in the video, otherwise a scale by level.
* the items the quests ask for: colour variants of the game's base graphics, with prices and
  timers from the wiki where it has them.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, '..', 'server')
sys.path.insert(0, SERVER)

# Quests in the order the Let's Play (parts 1-2) offered them; each waits for the one before.
VIDEO_ORDER = [
    'narrative_quest_01', 'story_quest_01', 'story_quest_02', 'story_quest_03', 'story_quest_04',
    'story_quest_05', 'story_quest_07', 'story_quest_12', 'story_quest_06', 'narrative_quest_02',
    'vitality_quest_01', 'story_quest_10', 'story_quest_11', 'mission_02', 'story_quest_13',
    'story_quest_15', 'story_quest_16', 'side_quest_02', 'side_quest_us_07', 'story_quest_08',
    'story_quest_14', 'story_quest_09', 'pearls_tutorial_01', 'side_quest_us_06', 'squirt_quest_01',
    'squirt_quest_02',
]
# Ids used by earlier versions of story.json -> the original ids (existing reefs are migrated).
RENAMED = {
    'rock_on': 'story_quest_07', 'sunset_cup': 'story_quest_12', 'story_quest_11': 'story_quest_10',
    'pearls_tutorial_01': 'story_quest_11', 'seadragon': 'mission_02', 'seabush': 'story_quest_13',
    'more_color': 'story_quest_15', 'wormy_mess': 'story_quest_16', 'playground': 'side_quest_02',
    'whats_a_coral': 'side_quest_us_07', 'what_could_it_be': 'story_quest_08',
    'all_about_coral': 'story_quest_14', 'extraordinary': 'story_quest_09',
    'fish_starve': 'pearls_tutorial_01', 'spare_no_effort': 'side_quest_us_06',
    'unexpected_party': 'squirt_quest_01', 'planting_101': 'squirt_quest_02',
}
FAMILIES = ('story_quest_', 'side_quest_', 'tankgang_', 'narrative_quest_', 'vitality_quest_',
            'pearls_tutorial_', 'squirt_quest_', 'mission_', 'chest_tutorial_02', 'minigame_squirt',
            'kids_story_quest_', 'patch_tutorial_', 'homework_', 'time_event_', 'google_quest_',
            'xpbar_tutorial_')
# Kids edition quests (players who entered an age under the game's limit), placed by what they ask for.
KIDS_AFTER = {'kids_story_quest_01': 'story_quest_13', 'kids_story_quest_02': 'kids_story_quest_01',
              'kids_story_quest_03': 'kids_story_quest_02', 'kids_story_quest_04': 'pearls_tutorial_01'}
UNSUPPORTED = {'CID_COOP_QUEST_CHECK'}
# The generic weekend events and the kind of weekend-challenge fish they give (see "challengeFish")
CHALLENGE_EVENTS = {'time_event_03': 'RP', 'time_event_05': 'RP', 'time_event_old_fish_rp': 'RP',
                    'time_event_tier_555c': 'RP', 'time_event_chest_01': 'OC', 'time_event_google_01_af': 'OC',
                    'time_event_old_fish_tc': 'OC', 'time_event_minigame_01': 'any'}
# Seasonal events come on their real dates each year; the others take turns on weekends.
SEASONS = {'christmas': 'christmas', 'halloween': 'halloween', '_val_': 'valentine', 'easter': 'easter'}
# Mr. Ray's daily homework (homework_0 = Sunday ... homework_6): three tasks from the game's generic task texts.
# The server picks each player's targets every day (quest task progress "prototypeId" and "count").
HOMEWORK_TASKS = [{'textKey': 'STR_GROW_A', 'cid': 'CID_GROWN', 'params': [2, 'coral_fan']},
                  {'textKey': 'STR_COLLECT_C', 'cid': 'CID_HARVESTED', 'params': [3, 'plant_table_yellow']},
                  {'textKey': 'STR_HARVEST_C', 'cid': 'CID_HARVESTED', 'params': [3, 'coral_fan']}]
# The early game ends with A Wormy Mess (level 5); later quests wait for it.
EARLY_END = 'story_quest_16'
MAX_LEVEL = 55
SQUIRT_GAME = 'questGame_Squirt'
AREA_SIZE = 9  # fish combinations: tiles across the area checked around the central item
BRUCE_GAME, BRUCE_FISH = 'questGame_Bruce', 8
AMBIENT = ['fish_ambient_0', 'fish_ambient_1', 'fish_ambient_coralfish', 'fish_ambient_firefish']
# Tint for colour variants the catalogue has no measured colour for (name colour word -> RGB).
# The ambient fish in the wiki's combination pictures: base prototype and the name for its colour variants
AMBIENT_KINDS = {'beaked': ('fish_ambient_coralfish', 'Beaked Fish'), 'firefish': ('fish_ambient_firefish', 'Firefish'),
                 'ordinary': ('fish_ambient_0', 'Ordinary Fish'), 'ambient': ('fish_ambient_1', 'Reef Fish')}
COLOUR_WORDS = {
    'yellow': (246, 222, 60), 'gold': (230, 180, 40), 'orange': (245, 140, 40), 'red': (215, 50, 50),
    'pink': (240, 120, 170), 'rose': (227, 78, 106), 'maroon': (130, 30, 50), 'purple': (140, 70, 170),
    'violet': (150, 90, 200), 'lilac': (190, 150, 220), 'indigo': (80, 70, 170), 'blue': (60, 110, 220),
    'lightblue': (120, 190, 240), 'turquoise': (60, 200, 190), 'green': (80, 180, 60),
    'lightgreen': (160, 220, 110), 'lime': (180, 230, 60), 'darkyellow': (200, 170, 40),
    'brown': (140, 95, 55), 'white': (240, 240, 235), 'silver': (190, 195, 205), 'grey': (150, 150, 150),
    'black': (50, 50, 55), 'amber': (230, 150, 40), 'bright green': (120, 230, 80),
}
# Guest missions have no task text of their own; the game's Collection screen line fits.
MISSION_TASK_KEY = 'STR_COLLECTION_COMBINATION_ATTRACT'
# Prices the wiki does not list: the Tank Gang houses (sand dollars, build seconds), growing with the level
# each arrives at, and the Enigmatic Seed (wiki: 10000 sand dollars, 60 % rare).
HOUSES = {'spec_house_bloat': (600, 4), 'spec_house_bubble': (900, 5), 'spec_house_peach': (1500, 6),
          'spec_house_jacque': (2000, 6), 'spec_house_gurgle': (3000, 8), 'spec_house_deb': (3500, 8),
          'spec_house_gill': (5000, 10)}
# Defaults by item kind when the wiki has no numbers (price in sand dollars; times in seconds).
KIND_DEFAULTS = {
    'coral': dict(price=40, feed=4, step=60, produce=6, every=300),
    'living_plant': dict(price=40, feed=4, step=60, produce=8, every=300),
    'ornamental': dict(price=30, feed=3, step=60),
    'decoration': dict(price=60),
}


def level_of(q):
    v = (q.get('video') or {}).get('level_offered')
    if v:
        return int(v)
    m = re.match(r'L(\d+)', q.get('level_estimate') or '')
    return int(m.group(1)) if m else None


def quest_reward(level):
    """Rewards for quests the video did not show. XP is about a sixth of the XP between two levels (story.json
    "levels"), so with three or four quests per level most XP still comes from the reef itself; sand dollars
    and algae grow with the prices."""
    return {'xp': 10 * round((15 * level + 20) / 10), 'virtualMoney': 10 * round((20 * level + 40) / 10),
            'energy': 10 * level}


def wiki_index(wiki):
    out = {}
    for sec in ('coral_and_living_plants', 'ornamental_plants', 'decorations', 'rare_plants'):
        for row in wiki.get(sec, []):
            keys = row.get('text_key')
            for k in keys if isinstance(keys, list) else [keys]:
                if k:
                    out.setdefault(k, dict(row, section=sec))
    return out


def num(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def item_numbers(cat, wrow, kind):
    """story.json item fields (price, feed, step, produce, every, level) from a wiki row."""
    d = dict(KIND_DEFAULTS.get(kind, {}))
    it = {}
    if wrow:
        price, cur = num(wrow.get('buy_price')), wrow.get('buy_currency')
        if price:
            d['price'] = price
            d['pearls'] = cur == 'hardMoney'
        if wrow.get('section') == 'coral_and_living_plants':
            for src, dst in (('algae_per_feed', 'feed'), ('grow_seconds_per_feed', 'step'),
                             ('produce_amount', 'produce'), ('produce_seconds', 'every')):
                if num(wrow.get(src)):
                    d[dst] = num(wrow[src])
            d['produces'] = wrow.get('produce_resource') or ''
        elif wrow.get('section') == 'ornamental_plants':
            total = num(wrow.get('total_algae_to_grow'))
            if total:
                d['feed'] = max(1, total // 3)
            if num(wrow.get('vitality')):
                it['hearts'] = num(wrow['vitality'])
        if num(wrow.get('unlock_level')):
            it['level'] = num(wrow['unlock_level'])
    if d.get('price'):
        it['price'] = {'hardMoney' if d.get('pearls') else 'virtualMoney': d['price']}
    for k in ('feed', 'step', 'every'):
        if k in d:
            it[k] = d[k]
    if 'produce' in d:
        amount = d['produce']
        it['produce'] = ({'energy': amount, 'xp': max(1, amount // 2)} if 'algae' in d.get('produces', 'algae')
                         else {'virtualMoney': amount, 'xp': max(1, amount // 2)})
    return it


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--catalog', required=True)
    ap.add_argument('--wiki', required=True)
    ap.add_argument('--apk', required=True)
    ap.add_argument('--rare-fish', help='worldDef rareFishList saved from the 2014 game (wiki revision)')
    ap.add_argument('--vitality-patches', help='worldDef vitalityPatchList saved from the 2014 game (wiki revision)')
    ap.add_argument('--old', default=os.path.join(SERVER, 'story.json'))
    ap.add_argument('--out', default=os.path.join(SERVER, 'story.json'))
    a = ap.parse_args()

    import quests
    import worlddef
    load = lambda name: json.load(open(os.path.join(a.catalog, name), encoding='utf-8'))
    cq, cd, ci = load('quests.json'), load('dialogs.json'), load('items.json')
    wiki = wiki_index(json.load(open(a.wiki, encoding='utf-8')))
    old = json.load(open(a.old, encoding='utf-8'))
    old_quests = {RENAMED.get(q['id'], q['id']): q for q in old['quests']}
    wd = worlddef.build(a.apk, quests.NoStory())
    base = {p['id'] for k, v in wd.items() if isinstance(v, list) for p in v if isinstance(p, dict) and 'id' in p}
    cat_items = {x['id']: x for x in ci['items'] + ci['fish'] if x.get('id')}
    patterns = {p['id']: p for p in old['patterns']}
    proposed = {p['id']: p for p in cq['patterns_proposed']}

    def available(pid):
        if pid in base or pid in old['items']:
            return True
        x = cat_items.get(pid)
        if x and x.get('kind') == 'patch_upgrade':  # a patch's upgraded plant: made from its plant
            return available(x.get('upgrade_of', ''))
        return bool(x and x.get('base_exists') and x.get('base_ipro') in base)

    def needs(q):
        out = set()
        for t in q['tasks']:
            p = t.get('params') or {}
            if t['cid'] in quests.PROTOTYPE_TASKS and p.get('2'):  # "" = any fish
                out.add(str(p['2']))
            if t['cid'] == 'CID_PATTERN' and '2' in p:
                pat = patterns.get(p['2']) or proposed.get(p['2'])
                if not pat:
                    out.add('?pattern ' + p['2'])
                else:
                    out.update([pat['centralPrototype']] + pat['nearPrototypes'])
                    if pat.get('producedFishId'):
                        out.add(pat['producedFishId'])
        return out

    # ---- choose quests
    chosen, skipped = {}, []
    for q in cq['quests']:
        if not q['id'].startswith(FAMILIES) or q['type'] not in ('STORY', 'MISSION', 'SQUIRT_MINIGAME', 'HOMEWORK',
                                                                  'TIME_EVENT'):
            continue
        if q['type'] == 'HOMEWORK':
            q = dict(q, tasks=[{'textId': t['textKey'], 'cid': t['cid'],
                                'params': {str(i): v for i, v in enumerate(t['params'], 1)}} for t in HOMEWORK_TASKS])
        why = [t['cid'] for t in q['tasks'] if t['cid'] in UNSUPPORTED]
        why += [p for p in needs(q) if not available(p)]
        if why:
            skipped.append((q['id'], sorted(set(why))))
            continue
        chosen[q['id']] = q

    # ---- order, levels, chains
    video = [qid for qid in VIDEO_ORDER if qid in chosen]
    out_quests = {}
    for qid, q in chosen.items():
        out_quests[qid] = {'id': qid, 'level': level_of(q), 'after': []}
    for i, qid in enumerate(video):
        e = out_quests[qid]
        e['order'] = i
        if i:
            e['after'] = [video[i - 1]]
    rest = sorted((qid for qid in chosen if qid not in video), key=lambda qid: chosen[qid]['table_index'])
    prev_story = 'story_quest_16'
    missions = [qid for qid in rest if qid.startswith('mission_')]
    for qid in rest:
        e = out_quests[qid]
        e['order'] = 100 + int(chosen[qid]['table_index'])
        m = re.match(r'(story_quest_\d+)([abc]?)$', qid)
        if qid.startswith('story_quest_'):
            e['after'] = [prev_story]
            prev_story = qid
        elif qid.startswith('mission_'):
            i = missions.index(qid)
            e['after'] = [missions[i - 1]] if i else [EARLY_END]
            e['level'] = e['level'] or min(MAX_LEVEL, 6 + 2 * i)
        elif qid == 'pearls_tutorial_02':
            e['after'] = ['pearls_tutorial_01']
        elif qid.startswith('squirt_quest_'):
            n = int(qid[-2:])
            e['after'] = ['squirt_quest_%02d' % (n - 1)]
        elif qid == 'minigame_squirt_tutorial':  # the first game, with "Let's Play!"
            e['after'] = ['squirt_quest_02']
        elif chosen[qid]['type'] == 'TIME_EVENT':  # scheduled by the server (quests.Story.event_windows)
            e['level'] = 6
            m = re.match(r'(.*\d)([abc])$', qid)
            season = next((v for k, v in SEASONS.items() if k in qid), 'weekend')
            e['event'] = {'season': season}
            if m and m.group(2) != 'a':
                prev = m.group(1) + chr(ord(m.group(2)) - 1)
                e['event']['after'] = prev
                e['after'] = [prev]
        elif qid.startswith('homework_') and chosen[qid]['type'] == 'HOMEWORK':
            e['homework'] = True  # opened by the server each day, not by the story
            e['after'] = [EARLY_END]  # with the tutorial, which asks to tap the homework button
            e['level'] = 9
        elif qid == 'homework_tutorial_01':  # "School is cool": tap the homework button
            e['after'] = [EARLY_END]
            e['level'] = 9
            e['order'] = 75
        elif qid == 'patch_tutorial_01':  # patches need 3500 Vitality (vitalityPatchList), about level 10
            e['after'] = [EARLY_END]
            e['level'] = 10
            e['order'] = 70
        elif qid == 'patch_tutorial_02':
            e['after'] = ['patch_tutorial_01']
            e['order'] = 71
        elif qid in KIDS_AFTER:
            e['after'] = [KIDS_AFTER[qid]]
            e['kidsOnly'] = True
        elif qid == 'minigame_squirt':  # then Hide and Seek whenever Squirt is ready
            e['after'] = ['minigame_squirt_tutorial']
            e['repeat'] = True
        else:
            e['after'] = [EARLY_END]
        if e['level'] is None:
            e['level'] = 6
        if qid == 'chest_tutorial_02':  # no chest appears until this one is done (canGenerateTreasureChest)
            e['order'] = 50
        if qid in ('squirt_quest_03', 'minigame_squirt_tutorial'):  # right after Planting 101
            e['order'] = 60
    # levels never go down along a chain (a quest waiting for a later-level one)
    for _ in range(3):
        for e in out_quests.values():
            for p in e['after']:
                if p in out_quests and out_quests[p]['level'] > e['level'] and not e['id'] in video:
                    e['level'] = out_quests[p]['level']

    # ---- quest bodies
    dialogs_needed, pattern_ids, fish_rewards, kids_patterns = set(), set(), set(), set()
    for qid, e in out_quests.items():
        q = chosen[qid]
        oldq = old_quests.get(qid, {})
        # A mission's giver is its guest fish: QuestMission::finish looks the giver up among the reef's fish
        # (the one the combination attracted) for the "Congratulations" popup.
        giver = q.get('questGiverId') or 'fish_special_nemo'
        if not available(giver):
            giver = 'fish_special_nemo'
        e['type'] = q['type']
        e['giver'] = giver
        name_key = q.get('nameStringId')
        if isinstance(name_key, list):
            name_key = name_key[-1]
        e['nameKey'] = name_key or 'STR_QUEST'
        e['descKey'] = q.get('descriptionStringId') or 'STR_QUEST'
        if q.get('rewardStringId'):
            e['rewardKey'] = q['rewardStringId']
        for role in ('startDialogId', 'endDialogId'):
            if q.get(role):
                e[role] = q[role]
                dialogs_needed.add(q[role])
        if q.get('narrative') or q.get('autoStart') is not None:
            e['autoStart'] = bool(q.get('autoStart', True))
        if q['type'] == 'SQUIRT_MINIGAME':  # starts when the player taps Squirt's button (questStart)
            e['autoStart'] = False
        e['tasks'] = []
        for t in q['tasks']:
            p = t.get('params') or {}
            params = [p[k] for k in sorted(p, key=int)]
            if t['cid'].startswith('CID_MINIGAME') and params and params[0] == 'squirt':
                params[0] = SQUIRT_GAME  # the only id the Hide and Seek screen runs
            if t['cid'] == 'CID_PATTERN':
                pattern_ids.add(str(params[1]))
            e['tasks'].append({'textKey': t.get('textId') or MISSION_TASK_KEY, 'cid': t['cid'], 'params': params})
        if q['type'] == 'HOMEWORK':
            e['descKey'] = q['descriptionStringId']
        rw = oldq.get('reward') or q.get('reward_story_json')
        e['reward'] = rw if rw else quest_reward(e['level'])
        if qid.startswith('narrative_quest_'):  # a conversation only: no popup, no reward
            e['reward'] = {}
        hints = q.get('hints') or []
        if hints:
            e['hintIdList'] = [h['id'] for h in hints]
        kv = q.get('kids_variant')
        if kv:  # the Kids edition of a guest mission: its own texts, hints and an easier combination
            kids = {'nameKey': kv['nameStringId'], 'descKey': kv['descriptionStringId'],
                    'rewardKey': kv['rewardStringId']}
            if kv.get('hints'):
                kids['hintIdList'] = ['%s_kids_%d' % (qid, i) for i in range(len(kv['hints']))]
            pat = kv.get('pattern')
            if pat and pat in proposed and all(available(x) for x in [proposed[pat]['centralPrototype']]
                                                + proposed[pat]['nearPrototypes']):
                kids['pattern'] = pat
                kids_patterns.add(pat)
            e['kids'] = kids
        ko = q.get('kids_overrides') or {}
        if set(ko) == {'reward'}:  # only wording; other Kids edition changes swap the tutorial's items
            e['kids'] = {'rewardKey': ko['reward']['textId']}
        if q['type'] == 'TIME_EVENT' and not rw:
            e['reward'] = quest_reward(12)
        fish = [f for f in (q.get('rewardPrototypeIdList_proposed') or []) if f.startswith('fish_') and available(f)]
        if oldq.get('grantFish'):
            fish = oldq['grantFish']
        if fish:
            e['rewardPrototypeIdList'] = fish
            e['grantFish'] = fish
            fish_rewards.update(fish)
        for k in ('unlockSectors',):
            if oldq.get(k):
                e[k] = oldq[k]

    # Bruce's visit (a weekend event): quest::QuestMinigame (type SQUIRT_MINIGAME) starts QuestGameBruce by itself
    # once the quest runs; the player taps the BRUCE_FISH fish hiding from him before the weekend is over.
    if 'time_event_bruce' in out_quests:
        e = out_quests['time_event_bruce']
        e.update(type='SQUIRT_MINIGAME', autoStart=True)
        e['tasks'] = [dict(e['tasks'][0], cid='CID_MINIGAME', params=[BRUCE_GAME, BRUCE_FISH])]

    # ---- dialogs (text keys only)
    conv = {c['id']: c for c in cd['conversations']}
    dialogs = []
    for did in sorted(dialogs_needed):
        c = conv.get(did)
        if not c or not c['lines']:
            for e in out_quests.values():  # no lines known: drop the reference (an empty dialog crashes)
                for role in ('startDialogId', 'endDialogId'):
                    if e.get(role) == did:
                        del e[role]
            continue
        dialogs.append({'id': did, 'lines': [
            {'side': l['position'], 'actor': l['actorId'], 'key': l['textId'], 'listener': l.get('toActorId') or ''}
            for l in c['lines']]})

    # ---- hints
    hints = []
    for q in chosen.values():
        for h in q.get('hints') or []:
            hints.append({'id': h['id'], 'index': h.get('index', 0), 'key': h['textId'],
                          'cost': h.get('cost_proposed') or {'virtualMoney': 200}})
        for i, h in enumerate((q.get('kids_variant') or {}).get('hints') or []):
            hints.append({'id': '%s_kids_%d' % (q['id'], i), 'index': i, 'key': h['textId'],
                          'cost': {'virtualMoney': 200} if i == 0 else {'hardMoney': 1}})

    # ---- patterns
    colors = dict(old['colors'])
    out_patterns = []
    for i, pid in enumerate(sorted(pattern_ids | kids_patterns)):
        p = dict(patterns.get(pid) or proposed[pid])
        for k in ('confidence', 'notes', 'source'):
            p.pop(k, None)
        if not p.get('producedFishId'):
            p['producedFishId'] = AMBIENT[i % len(AMBIENT)]
        if pid in kids_patterns and pid not in pattern_ids:
            p['kidsOnly'] = True
        p.setdefault('centralHintCost', {'virtualMoney': 100})
        p.setdefault('sorroundingHintCost', {'virtualMoney': 100})
        # PatternArea centres the area on the central plant with (areaSize - plant size) / 2, rounded down, so
        # one side is shorter. The wiki says "within a 6x6 tile area", but with 6 a large item placed on the short
        # side (a Yellow Plateau Plant left of a Heap of Stones) fell outside; 9 takes every side.
        p['areaSize'] = AREA_SIZE
        out_patterns.append(p)

    # The living plant is a combination's central item (wiki: "Primary living plant + 1-2 items"). It matters:
    # PatternSystem looks for combinations only around a central item that is placed or moved, and on loading
    # only around living plants, so a Yellow Plateau Plant moved next to a central Heap of Stones never counted.
    living = {p['id'] for p in wd.get('livingPlantPrototypeList', [])}
    for p in out_patterns:
        if p['centralPrototype'] not in living:
            plant = next((n for n in p['nearPrototypes'] if n in living or cat_items.get(n, {}).get('kind') == 'living_plant'), None)
            if plant:
                p['nearPrototypes'] = [p['centralPrototype']] + [n for n in p['nearPrototypes'] if n != plant]
                p['centralPrototype'] = plant

    # ---- the wiki's ambient fish combinations (a living plant and 1-2 items near it): colour variants of the
    # four ambient fish ("Fish beaked orange.png" -> fish_ambient_coralfish tinted orange)
    id_by_key = {x['key']: x['id'] for x in ci['items'] if x.get('key') and x.get('id')}
    have = {tuple(sorted([p['centralPrototype']] + p['nearPrototypes'])) for p in out_patterns}
    ambient_items, ambient_wanted = {}, set()
    for c in json.load(open(a.wiki, encoding='utf-8')).get('ambient_fish_combinations', []):
        ids = [next((id_by_key[x] for x in (k if isinstance(k, list) else [k]) if x in id_by_key), '?%s' % k)
               for k in c['item_text_keys']]
        words = c['fish_image'].rsplit('.', 1)[0].split()  # Fish <kind> <colour>
        if len(words) != 3 or words[1].lower() not in AMBIENT_KINDS or tuple(sorted(ids)) in have:
            continue
        if not all(i in base or (cat_items.get(i, {}).get('base_ipro') in base) for i in ids):
            continue
        kind, colour = words[1].lower(), words[2].lower()
        fish_base, fish_name = AMBIENT_KINDS[kind]
        fid = '%s_%s' % (fish_base, colour)
        colors.setdefault('ambient_%s_%s' % (kind, colour), list(COLOUR_WORDS[colour]))
        ambient_items[fid] = {'base': fish_base, 'color': 'ambient_%s_%s' % (kind, colour),
                              'name': '%s %s' % (colour.capitalize(), fish_name)}
        out_patterns.append({'id': 'pattern_ambient_%s_%s' % (kind, colour), 'centralPrototype': ids[0],
                             'nearPrototypes': ids[1:], 'producedFishId': fid, 'areaSize': AREA_SIZE,
                             'centralHintCost': {'virtualMoney': 100}, 'sorroundingHintCost': {'virtualMoney': 100}})
        ambient_wanted.update(ids)

    # ---- items: everything the quests and patterns ask for that the game has only as a base graphic
    wanted = set(fish_rewards) | ambient_wanted
    for qid in out_quests:
        wanted |= {p for p in needs(chosen[qid]) if not p.startswith('?')}
    for e in out_quests.values():
        wanted.add(e['giver'])
    for pid in kids_patterns:
        pat = proposed[pid]
        wanted |= {pat['centralPrototype'], *pat['nearPrototypes']} | ({pat['producedFishId']} if pat.get('producedFishId') else set())
    items = dict(old['items'])
    items.update(ambient_items)
    for pid, it in items.items():  # names from the game's text table
        x = cat_items.get(pid)
        if x and x.get('key'):
            it['name'] = x['key']
    for pid in sorted(wanted):
        if pid in base and pid not in cat_items:
            continue
        x = cat_items.get(pid)
        if not x:
            continue
        it = items.get(pid)
        if it is None and pid in base:
            it = {}
        if it is None:
            it = {'base': x['base_ipro']}
            cid = x.get('colour_id')
            if cid:
                rgb = x.get('rgb') or COLOUR_WORDS.get((x.get('colour') or '').lower().replace(' ', ''))
                rgb = rgb or COLOUR_WORDS.get((x.get('colour') or '').split()[-1].lower()) if x.get('colour') else rgb
                if rgb:
                    colors.setdefault(cid, list(rgb))
                    it['color'] = cid
        it['name'] = x['key']
        kind = x.get('kind')
        if kind in ('coral', 'living_plant', 'ornamental', 'decoration') and 'price' not in it:
            for k, v in item_numbers(x, wiki.get(x['key']), kind).items():
                it.setdefault(k, v)
        if it or pid not in base:
            items[pid] = it

    # QuestGameBruce tops the hiding fish up with "fish_ordinary_orange" (ServerPrototype must exist)
    colors.setdefault('ambient_ordinary_orange', list(COLOUR_WORDS['orange']))
    items.setdefault('fish_ordinary_orange', {'base': 'fish_ambient_0', 'color': 'ambient_ordinary_orange',
                                              'name': 'Orange Ordinary Fish'})
    for pid, (price, hours) in HOUSES.items():
        if pid in wanted:
            items.setdefault(pid, {}).update(price={'virtualMoney': price}, build=hours * 3600)
            if cat_items.get(pid, {}).get('key'):
                items[pid]['name'] = cat_items[pid]['key']
    if 'seed_coin_expensive' in wanted:
        rare = sorted(p['id'] for p in wd.get('rarePlantPrototypeList', []))
        common = list(items.get('seed_coin', {}).get('results', []))
        items.setdefault('seed_coin_expensive', {}).update(
            name=cat_items['seed_coin_expensive']['key'], price={'virtualMoney': 10000}, feed=600, step=21600,
            results=rare * 3 + common * 2)

    # Unlock levels (GET IT EARLY before them): seen in the Let's Play, else the wiki's; never later than the
    # first quest that asks for the item, so the story never needs pearls.
    first_need = {}
    for qid, e in out_quests.items():
        for p in needs(chosen[qid]):
            first_need[p] = min(first_need.get(p, 99), e['level'])
    wiki_level = {k: num(r.get('unlock_level')) for k, r in wiki.items() if num(r.get('unlock_level'))}
    for pid, it in items.items():
        if not it.get('price'):
            continue
        x = cat_items.get(pid, {})
        lv = x.get('unlock_level_seen') or wiki_level.get(x.get('key')) or first_need.get(pid) or 1
        it['level'] = max(1, min(int(lv), first_need.get(pid, 99)))

    # ---- rare fish: the 2014 worldDef's own numbers; each comes to the reef when its rare plant has grown
    rare_fish, rare_pairs, vitality_patches = {}, {}, []
    challenge_fish = {'RP': [], 'OC': []}
    if a.rare_fish:
        import texts
        table = texts.apk_texts(a.apk, 'en')
        key_by_name = {}
        for k, v in table.items():
            if k.startswith('STR_NAME_'):
                key_by_name.setdefault(v.strip().lower(), k)
        fish_by_key = {x['key']: x for x in ci['fish']}
        plant_by_key = {x['key']: x for x in ci['items'] if x['kind'] == 'rare_plant'}
        for f in json.load(open(a.rare_fish, encoding='utf-8')):
            fid = f['id']
            x = cat_items.get(fid, {})
            fish_base = x.get('base_ipro') or next(
                (b for b in sorted(base, key=len, reverse=True) if b.startswith('fish_rare_') and fid.startswith(b + '_')), None)
            if not fish_base and fid not in base:
                continue
            it = items.get(fid, {})
            if fid not in base:
                it['base'] = fish_base
                colour = (x.get('colour') or fid.rsplit('_', 1)[-1]).lower()
                rgb = x.get('rgb') or COLOUR_WORDS.get(colour)
                if rgb:
                    cid = x.get('colour_id') or fid[len('fish_rare_'):]
                    colors.setdefault(cid, list(rgb))
                    it['color'] = cid
            it['name'] = x.get('key') or key_by_name.get(f['name'].strip().lower()) or f['name']
            it['fishFeed'] = f['producingCost'].get('energy', 0)
            it['every'] = f['producingTime']['duration'] // 1000
            it['produce'] = {k: v for k, v in f['producedReward'].items() if v}
            it['hearts'] = f['vitality']
            items[fid] = it
            rare_fish[fid] = f.get('guiOrder', 0)
        # The Orange Vampire Crab (a 2014 weekend-challenge fish) is missing from the October list: as the Red one,
        # in orange
        if 'fish_rare_vampire_red' in items and 'fish_rare_vampire_orange' not in items:
            colors.setdefault('vampire_orange', list(COLOUR_WORDS['orange']))
            items['fish_rare_vampire_orange'] = dict(items['fish_rare_vampire_red'], color='vampire_orange',
                                                     name='STR_NAME_CRAB_ORANGE')
            rare_fish['fish_rare_vampire_orange'] = rare_fish.get('fish_rare_vampire_red', 0)
        for r in json.load(open(a.wiki, encoding='utf-8')).get('rare_fish_wiki', []):
            fx, px = fish_by_key.get(r['text_key']), plant_by_key.get(r.get('rare_plant_text_key'))
            if fx and px and fx['id'] in rare_fish and (px['id'] in base or px.get('base_ipro') in base):
                rare_pairs[px['id']] = fx['id']
                if px['id'] not in base and px['id'] not in items:
                    pit = {'base': px['base_ipro'], 'name': px['key']}
                    if px.get('rgb') or COLOUR_WORDS.get((px.get('colour') or '').lower()):
                        colors.setdefault(px['colour_id'], list(px.get('rgb') or COLOUR_WORDS[px['colour'].lower()]))
                        pit['color'] = px['colour_id']
                    items[px['id']] = pit
        # Weekend challenges (wiki "special events", 2014): the rare fish each one gave, by its task (RP = grow
        # rare plants, OC = open chests). The generic weekend events give the next of these the player lacks.
        granted = {f for q in out_quests.values() for f in q.get('grantFish', [])}
        id_by_key = {it.get('name'): fid for fid, it in items.items() if fid in rare_fish}
        for e in json.load(open(a.wiki, encoding='utf-8')).get('special_events', []):
            fid = id_by_key.get(key_by_name.get((e.get('Reward Fish') or '').strip().lower()))
            kind = 'RP' if (e.get('Task:Open Chests(OC) or Rare Plants(RP)?') or '').strip().upper() == 'RP' else 'OC'
            given = {items[f].get('name') for f in granted | set(challenge_fish['RP'] + challenge_fish['OC']) if f in items}
            if fid and items[fid].get('name') not in given:
                challenge_fish[kind].append(fid)
        for qid, kind in CHALLENGE_EVENTS.items():
            if qid in out_quests:
                out_quests[qid]['challengeFish'] = kind
        # the Enigmatic and Extraordinary seeds grow every rare plant, the paired ones included
        rare_plants = sorted({p['id'] for p in wd.get('rarePlantPrototypeList', [])} | set(rare_pairs))
        for sid in ('seed_coin_expensive', 'seed_pearl'):
            if sid in items:
                common = [r for r in items[sid].get('results', []) if not r.startswith('rare_plant_')]
                items[sid]['results'] = rare_plants * 3 + common * (2 if sid == 'seed_coin_expensive' else 0)
    if a.vitality_patches:
        vitality_patches = json.load(open(a.vitality_patches, encoding='utf-8'))

    # Patches: four grown plants of a kind on a Patch become its upgraded "_upr" plant (upgradePrototypeId),
    # which produces as much as the four. The Patch itself costs what vitalityPatchList says for the next one.
    upgrades = {x['upgrade_of']: x for x in ci['items'] if x['kind'] == 'patch_upgrade' and x.get('upgrade_of')}
    for pid, it in list(items.items()):
        x = cat_items.get(pid, {})
        if it.get('price') and x.get('kind') in ('coral', 'living_plant') and pid in upgrades:
            it['upgrade'] = {'id': upgrades[pid]['id'], 'name': upgrades[pid]['key']}
    for pid, x in upgrades.items():  # plants a quest needs as a patch, even if not sold
        if upgrades[pid]['id'] in wanted and pid in items:
            items[pid].setdefault('upgrade', {'id': x['id'], 'name': x['key']})
    items['spec_house_patch'] = {'name': 'STR_PATCH', 'price': {'virtualMoney': 80}, 'level': 10}

    # Vitality caps per level (the wiki's table, levels 1-55) and rare plants' hearts.
    wiki_raw = json.load(open(a.wiki, encoding='utf-8'))
    vitality_caps = [[r['cap_ornamental'], r['cap_rare_plants'], r['cap_rare_fish'], r['cap_guests'], r['total']]
                     for r in sorted(wiki_raw.get('vitality_caps_per_level', []), key=lambda r: r['level'])]
    rare_by_key = {}
    for r in wiki_raw.get('rare_plants', []):
        keys = r.get('text_key')
        for k in keys if isinstance(keys, list) else [keys]:
            if k and num(r.get('vitality')):
                rare_by_key[k] = num(r['vitality'])
    for x in ci['items']:
        if x['kind'] == 'rare_plant' and x.get('id') and rare_by_key.get(x['key']) and (x['id'] in base or x['id'] in items):
            items.setdefault(x['id'], {}).setdefault('hearts', rare_by_key[x['key']])
            items[x['id']].setdefault('name', x['key'])

    story = {
        'about': 'Generated by tools/build_story.py from the quest catalogue (text keys from the game\'s own '
                 'text table) and the fan wiki. Texts are looked up in the APK at run time.',
        'renamed': RENAMED,
        'quests': sorted(out_quests.values(), key=lambda e: e['order']),
        'dialogs': dialogs,
        'hints': hints,
        'patterns': out_patterns,
        'texts': old.get('texts', {}),
        'colors': colors,
        'items': items,
        'levels': dict(old['levels'], vitality=vitality_caps),
        'rareFish': {'pairs': rare_pairs, 'all': sorted(rare_fish, key=lambda f: rare_fish[f])},
        'challengeFish': challenge_fish,
        'vitalityPatchList': vitality_patches,
    }
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(story, f, indent=1, ensure_ascii=False)
        f.write('\n')
    print('%d quests, %d dialogs, %d hints, %d patterns, %d items -> %s'
          % (len(out_quests), len(dialogs), len(hints), len(out_patterns), len(items), a.out))
    for qid, why in skipped:
        print('  left out %s: %s' % (qid, ', '.join(why)))


if __name__ == '__main__':
    main()
