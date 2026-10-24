"""Regression for the two-row timed-event dialog in Android 1.8.1."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
import quests


class EventDialogTest(unittest.TestCase):
    def test_large_events_keep_objectives_but_use_regular_quest_card(self):
        story = quests.Story()
        story.windows = story.event_windows(1792857600000)
        for qid in ('google_quest_01', 'time_event_google_01'):
            with self.subTest(quest=qid):
                q = story.quests[qid]
                original = copy.deepcopy(q)
                prototype = story.quest_prototype(q)
                self.assertEqual(prototype['type'], 'STORY')
                self.assertEqual(len(prototype['endConditionList']), 3)
                self.assertEqual([c['tid'] for c in prototype['endConditionList']], [1, 2, 3])
                for field in ('startDialogId', 'rewardPrototypeIdList'):
                    if field in q:
                        self.assertEqual(prototype[field], q[field])
                self.assertEqual(prototype['startConditionList'][0]['conditionDefinitionId'],
                                 'CID_TIME_INTERVAL')
                self.assertEqual(q, original)
                self.assertEqual(q['type'], 'TIME_EVENT')

    def test_two_objective_events_retain_timed_dialog(self):
        story = quests.Story()
        checked = 0
        for q in story.data['quests']:
            if q.get('type') == 'TIME_EVENT' and len(q.get('tasks', [])) <= 2:
                self.assertEqual(story.quest_prototype(q)['type'], 'TIME_EVENT', q['id'])
                checked += 1
        self.assertGreater(checked, 0)

    def test_existing_beach_progress_is_retained_and_completes_as_event(self):
        story = quests.Story()
        qid = 'time_event_google_01'
        now = int(quests.time.time() * 1000)
        story.windows = {q['id']: (now - 1000, now + 60000)
                         for q in story.data['quests'] if q.get('event')}
        w = {'quests': [], 'finishedTutorialQuests': [], 'nextQuestId': 41,
             'messages': [], 'status': {'level': 9}}
        story.open(w, qid, push=False)
        entry = w['quests'][0]
        entry['tasks'][0].update(finished=True, progress={'counter': 0})
        before = copy.deepcopy(w)
        story.quest_prototype(story.quests[qid])
        self.assertEqual(w, before)
        paid = []
        # Disable unrelated new event offers to isolate completion bookkeeping.
        story.run_events = lambda *args, **kwargs: None
        for tid in (2, 3):
            result = story.task_state(w, {'id': 41, 'tid': tid, 'finished': True},
                                      lambda q, r: paid.append((q['id'], r)))
            self.assertEqual(result['questFinished'], tid == 3)
        self.assertEqual([p[0] for p in paid], [qid])
        self.assertEqual(w['eventsDone'][qid], story.windows[qid][0])
        self.assertNotIn(qid, w['finishedTutorialQuests'])
        self.assertFalse(any(e['prototypeId'] == qid for e in w['quests']))


if __name__ == '__main__':
    unittest.main()
