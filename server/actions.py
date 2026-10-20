"""Game actions (the batched "actions" of the game API) applied to a stored world.

Formats follow the client's netcl::ga::GA_* classes; see ACTIONS.md for the full protocol. The
client applies costs and rewards itself from the prototypes and only takes ids and timers from the
server, so the server repeats the same arithmetic to keep "status" right for the next startgame.

Entities are stored in the world lists as the client reads them in startgame (id, prototypeId,
position, state, intervals ...). States are recomputed from the timers whenever the world is sent.
"""
# server ids must stay below the client's temporary ids (EntityIdGenerator starts at 1,000,000)
MAX_ENTITY_ID = 999999

CURRENCIES = {'hardMoney': 'hardMoney', 'virtualMoney': 'virtualMoney', 'energy': 'energy',
              'lowTool': 'lowTool', 'highTool': 'highTool'}

# client state codes read by restoreStateFromServer
BUILT, CONSTRUCTING = 1, 0
GROWING, WAITING_FEED, PRODUCING, READY = 3, 5, 6, 7
GROWABLE = ('ET_CORAL', 'ET_LIVING_PLANT', 'ET_ORN_PLANT', 'ET_RARE_PLANT')
HARVESTABLE = ('ET_CORAL', 'ET_LIVING_PLANT', 'ET_RARE_PLANT')


def interval(start, length):
    return {'start': start, 'finish': start + length}


class Prototypes:
    """Lookup of worldDef prototypes by id, with the list each entity type is stored in."""

    def __init__(self, wd):
        self.by_id = {}
        world_list = {'coralPrototypeList': 'corals', 'livingPlantPrototypeList': 'livingPlants',
                      'ornamentalPlantPrototypeList': 'ornamentalPlants', 'rarePlantPrototypeList': 'rarePlants',
                      'decorationPrototypeList': 'decorations', 'housePrototypeList': 'houses',
                      'seedPrototypeList': None, 'patchList': 'patches',
                      'fishPrototypeList': 'fishes', 'ambientFishPrototypeList': 'fishes'}
        for key, lst in world_list.items():
            for p in wd.get(key, []):
                self.by_id[p['id']] = (lst, p)
        self.shop_cost = {s['prototypeId']: s['cost'] for s in wd.get('ingameShopItems', [])}
        self.levels = sorted(wd.get('levelList', []), key=lambda l: l['level'])

    def get(self, pid):
        return self.by_id.get(pid, (None, None))


class Reef:
    def __init__(self, protos):
        self.protos = protos

    # ------------------------------------------------------------ helpers
    @staticmethod
    def find(w, eid):
        for lst in ('corals', 'houses', 'decorations', 'livingPlants', 'ornamentalPlants',
                    'fishes', 'rarePlants', 'patches'):
            for e in w.get(lst, []):
                if e.get('id') == eid:
                    return lst, e
        return None, None

    @staticmethod
    def new_id(w):
        used = {e.get('id') for lst in ('corals', 'houses', 'decorations', 'livingPlants', 'ornamentalPlants',
                                        'fishes', 'rarePlants', 'patches') for e in w.get(lst, [])}
        n = w.get('nextEntityId', 1)
        while n in used:
            n += 1
        if n > MAX_ENTITY_ID:
            n = next(i for i in range(1, MAX_ENTITY_ID + 1) if i not in used)
        w['nextEntityId'] = n + 1
        return n

    def pay(self, w, cost, sign=-1):
        st = w['status']
        for k in CURRENCIES:
            st[k] = max(0, st.get(k, 0) + sign * int((cost or {}).get(k, 0)))

    def earn(self, w, reward):
        self.pay(w, reward, +1)
        xp = int((reward or {}).get('xp', 0))
        if xp:
            st = w['status']
            st['xp'] = st.get('xp', 0) + xp
            self.update_level(w)

    def update_level(self, w):
        st = w['status']
        levels = self.protos.levels
        lvl = st.get('level', 1)
        while True:
            nxt = next((l for l in levels if l['level'] == lvl + 1), None)
            if not nxt or st['xp'] < nxt['requiredXP']:
                break
            lvl += 1
            self.pay(w, nxt.get('reward'), +1)
        st['level'] = lvl
        nxt = next((l for l in levels if l['level'] == lvl + 1), None)
        st['xpForNextLevel'] = nxt['requiredXP'] if nxt else st['xp']

    @staticmethod
    def ms(p, key):
        return int((p.get(key) or {}).get('duration', 0))

    # ------------------------------------------------------------ state shown to the client
    def refresh(self, w, now):
        """Advances every entity whose timer ran out (called before the world is sent)."""
        for lst in ('corals', 'houses', 'decorations', 'livingPlants', 'ornamentalPlants', 'rarePlants',
                    'patches', 'fishes'):
            for e in w.get(lst, []):
                self.advance(e, now)

    def advance(self, e, now):
        _, p = self.protos.get(e.get('prototypeId'))
        etype = (p or {}).get('type')
        st = e.get('state')
        if st == CONSTRUCTING and e.get('constructionInterval', {}).get('finish', 0) <= now:
            e['state'] = BUILT
            e.pop('constructionInterval', None)
        elif st == GROWING and e.get('growingInterval', {}).get('finish', 0) <= now:
            if e.get('growingCycle', 0) < int((p or {}).get('growingCycles', 1)):
                e['state'] = WAITING_FEED
            elif etype in HARVESTABLE:
                fin = e['growingInterval']['finish']
                e['state'] = PRODUCING
                e['producingInterval'] = interval(fin, self.ms(p, 'producingTime'))
            else:
                e['state'] = BUILT
            if e['state'] != GROWING:
                e.pop('growingInterval', None)
        if e.get('state') == PRODUCING and e.get('producingInterval', {}).get('finish', 0) <= now:
            e['state'] = READY

    # ------------------------------------------------------------ actions
    def apply(self, w, action, now):
        """Returns the reaction for one action (always with resultCode)."""
        name = action.get('action')
        d = action.get('data') or {}
        r = {'aid': action.get('aid'), 'resultCode': 200}
        handler = getattr(self, 'a_' + str(name), None)
        if handler:
            data = handler(w, d, now)
            if data is not None:
                r['data'] = data
        return r

    def place(self, w, d, now):
        pid = d.get('prototypeId')
        lst, p = self.protos.get(pid)
        if not lst:
            return None, None, None
        e = {'id': self.new_id(w), 'prototypeId': pid,
             'position': {'x': int(d.get('x', 0)), 'z': int(d.get('z', 0)), 'transform': int(d.get('transform', 0)) & 1}}
        self.pay(w, self.protos.shop_cost.get(pid) or p.get('cost'))
        w.setdefault(lst, []).append(e)
        return lst, p, e

    def a_entityConstruct(self, w, d, now):
        lst, p, e = self.place(w, d, now)
        if not e:
            return {'id': self.new_id(w), 'constructionInterval': interval(now, 0)}
        if p['type'] == 'ET_PATCH':
            e.update(state=BUILT, plantCount=0)
            return {'id': e['id']}
        e['state'] = CONSTRUCTING
        e['constructionInterval'] = interval(now, self.ms(p, 'constructionTime'))
        self.earn(w, p.get('rewardAfterBuilt'))
        return {'id': e['id'], 'constructionInterval': e['constructionInterval']}

    def a_entitySeed(self, w, d, now):
        lst, p, e = self.place(w, d, now)
        if not e:
            return {'id': self.new_id(w), 'seeded': now}
        e.update(state=WAITING_FEED, seeded=now, growingCycle=0)
        return {'id': e['id'], 'seeded': now}

    def a_placeItemForCleaning(self, w, d, now):
        lst, p, e = self.place(w, d, now)
        return {'id': e['id'] if e else self.new_id(w)}

    def a_seedEntitySeed(self, w, d, now):
        # the seed turns into a plant; pick the first plant prototype as the result for now
        _, seed = self.protos.get(d.get('prototypeId'))
        self.pay(w, self.protos.shop_cost.get(d.get('prototypeId')) or (seed or {}).get('cost'))
        plant = next((pid for pid, (lst, p) in self.protos.by_id.items() if lst == 'livingPlants'), None)
        lst, p = self.protos.get(plant)
        e = {'id': self.new_id(w), 'prototypeId': plant, 'seedPrototypeId': d.get('prototypeId'),
             'position': {'x': int(d.get('x', 0)), 'z': int(d.get('z', 0)), 'transform': int(d.get('transform', 0)) & 1},
             'state': WAITING_FEED, 'seeded': now, 'growingCycle': 0}
        w.setdefault(lst or 'livingPlants', []).append(e)
        return {'id': e['id'], 'seeded': now, 'prototypeId': plant}

    def a_entityMove(self, w, d, now):
        _, e = self.find(w, d.get('id'))
        if e:
            e['position'] = {'x': int(d.get('x', 0)), 'z': int(d.get('z', 0)), 'transform': int(d.get('transform', 0)) & 1}
            e.pop('inventory', None)
        return None

    def a_entityRefund(self, w, d, now):
        lst, e = self.find(w, d.get('id'))
        if e:
            _, p = self.protos.get(e['prototypeId'])
            self.earn(w, (p or {}).get('refundReward'))
            w[lst].remove(e)
        return None

    def grow(self, w, e, now, pay=True):
        _, p = self.protos.get(e['prototypeId'])
        p = p or {}
        if pay:
            self.pay(w, p.get('growingCycleCost'))
        e['growingCycle'] = min(e.get('growingCycle', 0) + 1, int(p.get('growingCycles', 1)))
        e['growingInterval'] = interval(now, self.ms(p, 'growingTime'))
        e['state'] = GROWING
        return {'growingCycle': e['growingCycle'], 'growingInterval': e['growingInterval']}

    def a_entityFeed(self, w, d, now):
        _, e = self.find(w, d.get('id'))
        if not e:
            return {'growingCycle': 1, 'growingInterval': interval(now, 0)}
        self.advance(e, now)
        return self.grow(w, e, now)

    def speedup_grow(self, w, d, now, paid):
        _, e = self.find(w, d.get('id'))
        if not e:
            return {'growingCycle': 1, 'growingInterval': interval(now, 0)}
        _, p = self.protos.get(e['prototypeId'])
        if paid:
            self.pay(w, (p or {}).get('speedupCost'))
        gi = e.get('growingInterval') or interval(now, 0)
        e['growingInterval'] = {'start': gi['start'], 'finish': now}
        out = {'growingCycle': e.get('growingCycle', 1), 'growingInterval': e['growingInterval']}
        self.advance(e, now)
        if e.get('state') == PRODUCING:
            out['producingInterval'] = e['producingInterval']
        return out

    def a_entitySpeedupFeed(self, w, d, now):
        return self.speedup_grow(w, d, now, True)

    def a_entityFreeSpeedupFeed(self, w, d, now):
        return self.speedup_grow(w, d, now, False)

    def a_entityCollectReward(self, w, d, now):
        _, e = self.find(w, d.get('id'))
        if not e:
            return {'producingInterval': interval(now, 0)}
        _, p = self.protos.get(e['prototypeId'])
        p = p or {}
        self.earn(w, p.get('producedReward'))
        if p.get('type') in HARVESTABLE or p.get('type') == 'ET_PATCH':
            start = int(d.get('performed') or now)
            e['state'] = PRODUCING
            e['producingInterval'] = interval(start, self.ms(p, 'producingTime'))
            return {'producingInterval': e['producingInterval']}
        e['state'] = 1  # fish: idle again
        e.pop('producingInterval', None)
        return {}

    def speedup_production(self, w, d, now, paid):
        _, e = self.find(w, d.get('id'))
        if not e:
            return {'producingInterval': interval(now, 0)}
        _, p = self.protos.get(e['prototypeId'])
        if paid:
            self.pay(w, (p or {}).get('producingSpeedupCost'))
        pi = e.get('producingInterval') or interval(now, 0)
        e['producingInterval'] = {'start': pi['start'], 'finish': now}
        e['state'] = READY
        return {'producingInterval': e['producingInterval']}

    def a_entitySpeedupProduction(self, w, d, now):
        return self.speedup_production(w, d, now, True)

    def a_entityFreeSpeedupProduction(self, w, d, now):
        return self.speedup_production(w, d, now, False)

    def speedup_construction(self, w, d, now, paid):
        _, e = self.find(w, d.get('id'))
        if not e:
            return {'constructionInterval': interval(now, 0)}
        _, p = self.protos.get(e['prototypeId'])
        if paid:
            self.pay(w, (p or {}).get('speedupCost'))
        ci = e.get('constructionInterval') or interval(now, 0)
        out = {'constructionInterval': {'start': ci['start'], 'finish': now}}
        e['state'] = BUILT
        e.pop('constructionInterval', None)
        return out

    def a_entityConstructionSpeedup(self, w, d, now):
        return self.speedup_construction(w, d, now, True)

    def a_entityConstructionFreeSpeedup(self, w, d, now):
        return self.speedup_construction(w, d, now, False)

    def a_placeEntityInPatch(self, w, d, now):
        plst, plant = self.find(w, d.get('id'))
        _, patch = self.find(w, d.get('patchId'))
        if not patch:
            return {'full': False, 'plantCount': 0}
        _, pp = self.protos.get(patch['prototypeId'])
        cap = max(1, int((pp or {}).get('maxPlants') or 3))
        patch['plantCount'] = min(cap, patch.get('plantCount', 0) + 1)
        if plant:
            patch['plantPrototypeId'] = plant['prototypeId']
            w[plst].remove(plant)
        out = {'full': patch['plantCount'] >= cap, 'plantCount': patch['plantCount']}
        if out['full']:
            patch['state'] = PRODUCING
            patch['producingInterval'] = interval(now, self.ms(pp or {}, 'producingTime'))
            out['producingInterval'] = patch['producingInterval']
        return out

    def a_placeEntitiesToInventory(self, w, d, now):
        for eid in d.get('ids') or []:
            _, e = self.find(w, eid)
            if e:
                e['inventory'] = True
        return {}

    def a_fishFeed(self, w, d, now):
        _, e = self.find(w, d.get('id'))
        _, p = self.protos.get((e or {}).get('prototypeId'))
        p = p or {}
        self.pay(w, p.get('producingCost'))
        pi = interval(now, self.ms(p, 'producingTime'))
        if e:
            e['state'] = PRODUCING
            e['producingInterval'] = pi
        return {'producingInterval': pi}

    def a_collectAllFish(self, w, d, now):
        ids = []
        for e in w.get('fishes', []):
            self.advance(e, now)
            if e.get('state') == READY:
                _, p = self.protos.get(e['prototypeId'])
                self.earn(w, (p or {}).get('producedReward'))
                e['state'] = 1
                e.pop('producingInterval', None)
                ids.append(e['id'])
        return {'fishes': ids, 'reward': {'hardMoney': 0}}

    def a_collectSquirtTapReward(self, w, d, now):
        self.earn(w, d.get('reward'))
        return None

    def a_questTaskSetState(self, w, d, now):
        if d.get('reward'):
            self.earn(w, d['reward'])
        return {'questFinished': bool(d.get('finished'))}
