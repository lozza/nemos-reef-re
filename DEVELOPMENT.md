# Development and advanced tools

[All guides](README.md)

Source code and launchers live on the
[re-notes branch](https://github.com/lozza/nemos-reef-revival/tree/re-notes).
The default branch provides the public setup guides and Compose files.

## Source and tests

The Python server uses the standard library. From a source checkout:

```sh
python -m unittest discover -s tests -v
```

Tests use synthetic assets; original game files are not included.

Key files:

- [server/nemo_server.py](https://github.com/lozza/nemos-reef-revival/blob/re-notes/server/nemo_server.py):
  HTTP server; accepts `--apk`, `--port`, `--data` and `--worlddef`.
- [server/worlddef.py](https://github.com/lozza/nemos-reef-revival/blob/re-notes/server/worlddef.py):
  reads game definitions from the original APK.
- [patcher/patch_apk.py](https://github.com/lozza/nemos-reef-revival/blob/re-notes/patcher/patch_apk.py):
  patches client URLs, textures and signing.
- [tools/build_story.py](https://github.com/lozza/nemos-reef-revival/blob/re-notes/tools/build_story.py):
  generates story data. Text keys remain in the story JSON; text is read from the APK.
- [Protocol notes](https://github.com/lozza/nemos-reef-revival/blob/re-notes/PROTOCOL.md)
  and [game-action notes](https://github.com/lozza/nemos-reef-revival/blob/re-notes/ACTIONS.md):
  reverse-engineering references.

## Local Docker builds

From the source checkout:

```sh
docker build -t nemos-reef:local .
```

In a development copy of Compose, set `image: nemos-reef:local` and remove
`pull_policy: always`. Keep your APK and data mounts.

The publication workflow tests the server and Docker persistence, builds
AMD64/ARM64 images and checks the published image. Publications have
`latest` and `sha-FULL_COMMIT_SHA` tags for version pinning.

## Patcher options

The patcher writes both legacy API URLs into the native client. Keep the
server base URL short (at most 29 characters); the patcher checks whether it fits.

**Android Studio emulator:** the existing tested setup uses an Android 11
(API 30) x86_64 image with ARM translation. From that emulator, the PC is
`10.0.2.2`. Use:

```sh
python patcher/patch_apk.py nemo.apk http://10.0.2.2:8080 --debug-log --emulator
```

The emulator flag works around a GL-driver query that can otherwise crash
startup. It is not needed for normal Android devices.

**Optional music:** supply your own tracks named `music0` through `music3`
with `.mp3` or `.ogg` extensions in a `music` folder. Add `--music music`
to the patch command. The Windows batch patcher picks that folder up
automatically. Music files are not provided.

## Android game logs

For an APK patched with `--debug-log`, install
[Android SDK Platform-Tools](https://developer.android.com/tools/releases/platform-tools),
enable USB debugging on the phone, connect it and accept its authorisation prompt.

From a terminal where `adb` is available:

```sh
adb logcat -c
adb logcat -s SDR:* AndroidRuntime:E DEBUG:* > nemo-log.txt
```

Reproduce the issue, then press Ctrl+C. Review the log before sharing it.

## Reset tools

These are destructive developer tools. Stop the server and
[back up first](SAVES.md).

- `reset-reef.bat` asks for confirmation and deletes **all saved reefs**,
  keeping accounts.
- `new-start.bat` asks for confirmation and deletes **all accounts and reefs**.
- `reef-report.bat` writes a report of saved fish/plant combinations.

Use these only for the Windows data directory they operate on. They are not
Docker migration or update steps.
