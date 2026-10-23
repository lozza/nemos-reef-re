"""Runtime smoke test using synthetic assets; no original APK is needed."""
import json
from contextlib import closing
from pathlib import Path
import socket
import sqlite3
import struct
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def make_apk(path):
    with zipfile.ZipFile(path, 'w') as apk:
        apk.writestr('assets/bundle.json', '{}')
        # The real story requires its base item IDs. Supply schematic prototypes,
        # not any original asset bytes or artwork.
        story = json.loads((ROOT / 'server/story.json').read_text(encoding='utf-8'))
        ids = set(story['items']) | {it['base'] for it in story['items'].values() if it.get('base')}
        ids.update(('fish_special_nemo', 'fish_special_marlin', 'fish_special_bruce', 'fish_special_tad'))
        for pid in sorted(ids):
            kind = ('ET_CHARACTER' if pid.startswith('fish_') else
                    'ET_CORAL' if pid.startswith('coral_') else
                    'ET_SEED' if pid.startswith('seed_') else
                    'ET_NORMAL_DECORATION' if pid.startswith('deco_') else
                    'ET_SPEC_HOUSE' if pid.startswith('spec_house_') else
                    'ET_LIVING_PLANT')
            value = kind.encode()
            attribute = b'\0\x04type\0\x01\x03' + struct.pack('>H', len(value)) + value
            apk.writestr(f'assets/prototypes/{pid}.ipro', attribute)
        # Empty, valid scene: no tiles, tile lists, or starting entities.
        apk.writestr('assets/level.iscn', b'\0\0Iscn 0.2\0\0' +
                     struct.pack('>HiiHHH', 0, 0, 0, 0, 0, 0))


class RuntimeTest(unittest.TestCase):
    def test_health_and_saved_reef_survive_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            apk = folder / 'fixture.apk'
            data = folder / 'data'
            make_apk(apk)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            base = f'http://127.0.0.1:{port}'

            def request(path, **params):
                url = base + path
                if params:
                    url += '?' + urllib.parse.urlencode(params)
                with urllib.request.urlopen(url, timeout=3) as response:
                    return json.load(response)

            def start():
                log = open(folder / 'process.log', 'ab')
                process = subprocess.Popen(
                    [sys.executable, '-u', str(ROOT / 'server/nemo_server.py'),
                     '--apk', str(apk), '--data', str(data),
                     '--host', '127.0.0.1', '--port', str(port)],
                    cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
                log.close()
                self.addCleanup(stop, process)
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    try:
                        self.assertEqual(request('/healthz'), {'status': 'ok'})
                        return process
                    except OSError:
                        if process.poll() is not None:
                            break
                        time.sleep(0.1)
                stop(process)
                self.fail((folder / 'process.log').read_text())

            def stop(process):
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)

            process = start()
            try:
                for _ in range(3):
                    self.assertEqual(request('/healthz'), {'status': 'ok'})
                with closing(sqlite3.connect(data / 'nemo.db')) as db:
                    self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0], 0)
                self.assertFalse((data / 'requests.log').exists())
                user = request('/nemo/api/register_user', token_info='test-device',
                               proposed_name='DockerDiver')['response']['user']
                uid = user['user_id']
                world = request('/nemo/startgame', uid=uid)
                self.assertEqual(world['resultCode'], 200)
                self.assertEqual(world['user']['uid'], uid)
            finally:
                stop(process)
            # A distinct saved value must be retained, rather than a fresh reef created.
            with closing(sqlite3.connect(data / 'nemo.db')) as db:
                saved = json.loads(db.execute('SELECT world FROM worlds WHERE uid=?', (uid,)).fetchone()[0])
                saved['status']['virtualMoney'] = 4321
                db.execute('UPDATE worlds SET world=? WHERE uid=?', (json.dumps(saved), uid))
                db.commit()
            process = start()
            try:
                logged_in = request('/nemo/api/authenticate', token_info='test-device')
                self.assertEqual(logged_in['response']['user_id'], uid)
                self.assertEqual(request('/nemo/startgame', uid=uid)['status']['virtualMoney'], 4321)
            finally:
                stop(process)


if __name__ == '__main__':
    unittest.main()
