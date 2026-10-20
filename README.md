# Nemo's Reef private server

A replacement server for Disney's *Nemo's Reef* (Android 1.8.1), whose official servers have shut down.
Protocol details are in [PROTOCOL.md](PROTOCOL.md).

**Status:** early. Login, world loading and game-action acknowledgement are implemented from static
analysis but have not been tested against a real device yet. The game economy (prices, timers, levels,
quests) is placeholder data generated from the APK's bundled prototypes.

You need your own copy of the original APK (`nemos-reef-1-8-1-en-android.apk`); it is not included here.

## 1. Run the server (any PC with Python 3.8+)

```
cd server
python nemo_server.py --apk path\to\nemos-reef-1-8-1-en-android.apk --port 8080
```

Every request is printed and logged to `server/data/requests.log`; the database is `server/data/nemo.db`.
Allow Python through the firewall so your phone can reach port 8080.

## 2. Patch the APK to use your server

Find your PC's LAN IP (`ipconfig` on Windows), then:

```
cd patcher
python patch_apk.py path\to\nemos-reef-1-8-1-en-android.apk http://192.168.1.20:8080 --debug-log
```

Signing needs Java plus [uber-apk-signer](https://github.com/patrickfav/uber-apk-signer/releases)
(put `uber-apk-signer-1.3.0.jar` in `patcher/`), or `apksigner` from the Android SDK. The server URL must be
at most 29 characters (`http://192.168.1.20:8080` is 24).

## 3. Install and test

Uninstall any old copy, then `adb install nemos-reef-1-8-1-en-android-private.apk`. The game is 32-bit ARM
only; it will not run on 64-bit-only phones (e.g. Pixel 7 and newer). Android Studio's emulator or
BlueStacks work too.

With `--debug-log`, the game's own trace is visible with:

```
adb logcat -s SDR:* AndroidRuntime:E DEBUG:* > nemo-log.txt
```

Send `server/data/requests.log` and the logcat output when something goes wrong.

## Layout

- `server/` — the server (`nemo_server.py`), world-definition generator (`worlddef.py`), `.ipro` reader
- `patcher/` — APK patcher
- `tools/` — reverse-engineering scripts used to derive the protocol
