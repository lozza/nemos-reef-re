"""Seed provenance, native condition format, and save recovery regressions."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
import actions
import quests


class SeedQuestTest(unittest.TestCase):
    def setUp(self):
        self.story = quests.Story()
        self.story.catch_up = lambda *a, **k: None
        self.paid = []
        self.protos = actions.Prototypes({
            'seedPrototypeList': [{'id': 'seed_coin', 'growingCycles': 3}],
            'ornamentalPlantPrototypeList': [{'id': 'orn_plant_cirripathes_lilac',
                                             'shopCategory': 'ORNAMENTALPLANT'}],
            'rarePlantPrototypeList': [{'id': 'rare_plant_cabbage', 'shopCategory': 'RAREPLANT'}]})
        self.world = {'quests': [], 'finishedTutorialQuests': [], 'nextQuestId': 26,
                      'status': {'level': 10}, 'messages': [], 'ornamentalPlants': [], 'rarePlants': []}

    def recover(self):
        self.story.recover_seed_tasks(self.world, self.protos, lambda q, r: self.paid.append(q['id']))

    def plant(self, ident=88, seed=True, rare=False, state=actions.BUILT):
        e = {'id': ident, 'prototypeId': 'rare_plant_cabbage' if rare else 'orn_plant_cirripathes_lilac',
             'state': state, 'growingCycle': 3, 'seeded': 100}
        if seed:
            e['seedPrototypeId'] = 'seed_coin'
        self.world['rarePlants' if rare else 'ornamentalPlants'].append(e)
        return e

    def test_saved_lilac_completes_mystery_seed_quest_once_without_touching_plant(self):
        self.story.open(self.world, 'story_quest_08', push=False)
        plant = self.plant()
        original = copy.deepcopy(plant)
        self.recover()
        self.assertEqual(self.paid, ['story_quest_08'])
        self.assertIn('story_quest_08', self.world['finishedTutorialQuests'])
        self.assertEqual(plant, original)
        self.recover()
        self.assertEqual(self.paid, ['story_quest_08'])

    def test_nursery_lilac_has_no_seed_evidence(self):
        self.story.open(self.world, 'story_quest_08', push=False)
        self.plant(seed=False)
        before = copy.deepcopy(self.world)
        self.recover()
        self.assertEqual(self.world, before)
        self.assertEqual(self.paid, [])

    def test_unfinished_seed_marks_planting_only(self):
        self.story.open(self.world, 'story_quest_08', push=False)
        self.plant(state=actions.GROWING)
        self.recover()
        ts = self.world['quests'][0]['tasks']
        self.assertTrue(ts[0]['finished'])
        self.assertFalse(ts[1].get('finished', False))
        self.assertEqual(self.paid, [])

    def test_lilac_cannot_satisfy_a_rare_plant_seed_task(self):
        self.story.open(self.world, 'side_quest_us_03', push=False)
        self.plant()
        self.recover()
        self.assertFalse(self.world['quests'][0]['tasks'][0].get('finished', False))
        self.assertEqual(self.paid, [])

    def test_repeated_logins_do_not_count_one_seed_twice(self):
        self.story.open(self.world, 'side_quest_05', push=False)
        self.plant()
        self.recover()
        task = self.world['quests'][0]['tasks'][0]
        self.assertEqual(task['progress']['counter'], 1)
        self.recover()
        self.assertEqual(task['progress']['counter'], 1)
        self.plant(ident=89)
        self.recover()
        self.assertEqual(self.paid, ['side_quest_05'])

    def test_all_seed_growth_definitions_use_native_source_filter(self):
        checked = 0
        for q in self.story.data['quests']:
            for t in q['tasks']:
                ps = t.get('params', [])
                self.assertFalse(t['cid'] == 'CID_GROWN' and len(ps) > 1 and str(ps[1]).startswith('seed_'), q['id'])
                if t['cid'] == 'CID_GROW_ANY' and len(ps) > 2 and str(ps[2]).startswith('seed_'):
                    self.assertGreater(int(ps[1]), 0)
                    checked += 1
        self.assertEqual(checked, 15)
        p = self.story.quest_prototype(self.story.quests['story_quest_08'])
        c = p['endConditionList'][1]
        self.assertEqual(c['conditionDefinitionId'], 'CID_GROW_ANY')
        self.assertEqual(c['parameterValueList'][2], {'index': 3, 'value': 'seed_coin'})


if __name__ == '__main__':
    unittest.main()
