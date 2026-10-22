"""Prints what the server has saved for each player: level, the fish combinations the game reported
(savePattern), the fish living in the reef and the plants the combinations are built around.
Run it from the repository folder: python tools\\reef_report.py  (or reef-report.bat)."""
import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'server', 'data')
sys.path.insert(0, os.path.join(HERE, '..', 'server'))


def main():
    db = os.path.join(DATA, 'nemo.db')
    if not os.path.exists(db):
        print('No database at %s - has the server been started from this folder?' % db)
        return
    with open(os.path.join(HERE, '..', 'server', 'story.json'), encoding='utf-8') as f:
        patterns = {p['id']: p for p in json.load(f).get('patterns', [])}
    con = sqlite3.connect(db)
    names = dict(con.execute('SELECT uid, name FROM users'))
    for uid, world in con.execute('SELECT uid, world FROM worlds'):
        w = json.loads(world)
        print('=' * 70)
        print('Player %s (%s)  level %s  kids=%s' % (names.get(uid, '?'), uid, w.get('status', {}).get('level'),
                                                    w.get('kids')))
        print('Combinations reported by the game:', w.get('patterns', []))
        for pid in w.get('patterns', []):
            p = patterns.get(pid, {})
            print('   %s: %s + %s -> %s' % (pid, p.get('centralPrototype'), p.get('nearPrototypes'),
                                           p.get('producedFishId')))
        print('Fish in the reef:')
        for e in w.get('fishes', []):
            print('   %-40s id %-6s at %s' % (e.get('prototypeId'), e.get('id'), e.get('position')))
        centrals = {patterns[pid]['centralPrototype'] for pid in w.get('patterns', []) if pid in patterns}
        print('Centre plants of those combinations in the reef:')
        for lst in ('livingPlants', 'ornamentalPlants', 'corals', 'decorations'):
            for e in w.get(lst, []):
                if e.get('prototypeId') in centrals:
                    print('   %-40s state %s inventory %s at %s' % (e['prototypeId'], e.get('state'),
                                                                    bool(e.get('inventory')), e.get('position')))
    log = os.path.join(DATA, 'requests.log')
    if os.path.exists(log):
        print('=' * 70)
        print('savePattern lines in requests.log:')
        with open(log, encoding='utf-8', errors='replace') as f:
            for line in f:
                if 'savePattern' in line:
                    print('   ' + line.strip()[:300])


if __name__ == '__main__':
    main()
