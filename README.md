# Nemo's Reef private server

A replacement server for Disney's *Nemo's Reef* (Android 1.8.1), whose official servers have shut down.
Protocol details are in [PROTOCOL.md](PROTOCOL.md).

**Status:** early and untested on a real device. Login, loading your reef and game actions are implemented;
prices, timers and levels are placeholder numbers, and quests/daily rewards are not done yet.

The game files are not included: you need your own copy of `nemos-reef-1-8-1-en-android.apk`.

---

## Setup on Windows (one time)

You need a Windows PC and an Android phone (or an emulator such as BlueStacks) on the **same Wi-Fi network**.
The PC runs the server; the phone runs the game.

### 1. Install Python

1. Download Python from https://www.python.org/downloads/ (the big yellow "Download Python" button).
2. Run the installer. On the first screen **tick "Add python.exe to PATH"**, then click "Install Now".

### 2. Install Java

Needed only to sign the patched game file.

1. Go to https://adoptium.net/temurin/releases/ , choose **Windows**, **x64**, package **JRE**, and download the `.msi`.
2. Run it and accept the defaults.

### 3. Download this project and the game

1. Download this project as a zip:
   https://github.com/lozza/nemos-reef-re/archive/refs/heads/re-notes.zip
2. Right-click the zip → **Extract All…** → extract to `C:\nemo`.
   You should now have a folder like `C:\nemo\nemos-reef-re-re-notes` containing `start-server.bat`, `patch-apk.bat`,
   `server`, `patcher`, … (this README calls it **the project folder**).
3. Copy your `nemos-reef-1-8-1-en-android.apk` into the project folder and **rename it to `nemo.apk`**.

### 4. Download the signing tool

1. Download `uber-apk-signer-1.3.0.jar` from
   https://github.com/patrickfav/uber-apk-signer/releases/download/v1.3.0/uber-apk-signer-1.3.0.jar
2. Put it in the project folder's **`patcher`** folder.

### 5. Find your PC's IP address

1. Press the Windows key, type `cmd`, press Enter. A black Command Prompt window opens.
2. Type `ipconfig` and press Enter.
3. Under your Wi-Fi (or Ethernet) adapter, find the line **IPv4 Address**, e.g. `192.168.1.20`. Write it down.

If your router gives the PC a different address later, repeat steps 5–7.

### 6. Make the patched game

Double-click **`patch-apk.bat`** in the project folder, type the IP address from step 5 and press Enter.
After a few seconds it should say `wrote signed nemo-private.apk`. The new file `nemo-private.apk` appears in the
project folder. This copy of the game talks to your PC instead of Disney's old servers.

### 7. Install it on the phone

1. Uninstall any old copy of Nemo's Reef from the phone.
2. Copy `nemo-private.apk` to the phone (USB cable, Google Drive, email to yourself, …).
3. On the phone, open it from the Files/Downloads app and tap **Install**. If Android asks, allow
   "Install unknown apps" for that app.

The game is 32-bit only, so it will not install on 64-bit-only phones (Pixel 7 and newer, some 2023+ phones).
In that case use BlueStacks on the PC (drag `nemo-private.apk` onto the BlueStacks window to install).

## Playing / testing

1. Double-click **`start-server.bat`**. A window opens saying `Nemo's Reef server on http://0.0.0.0:8080`.
   If Windows Firewall asks, tick **Private networks** and click **Allow access**.
   Keep this window open; each request from the game shows up in it.
2. Start the game on the phone.

When something goes wrong, send `server\data\requests.log` from the project folder.

### Optional: game logs (much more detail)

The patched game writes its own internal log, which tells us exactly where it gets stuck. Reading it needs
`adb` and a USB cable:

1. Download "SDK Platform-Tools for Windows" from https://developer.android.com/tools/releases/platform-tools
   and extract it to `C:\platform-tools`.
2. On the phone: **Settings → About phone**, tap **Build number** 7 times. Then **Settings → System →
   Developer options**, turn on **USB debugging**. Plug the phone into the PC and accept the prompt on the phone.
3. In a Command Prompt:
   ```
   cd C:\platform-tools
   adb logcat -c
   adb logcat -s SDR:* AndroidRuntime:E DEBUG:* > C:\nemo\nemo-log.txt
   ```
   Start the game, play until it gets stuck, then press Ctrl+C in the Command Prompt.
   Send `C:\nemo\nemo-log.txt` along with `requests.log`.

---

## For developers

- `server/nemo_server.py --apk <apk> [--port 8080] [--data dir] [--worlddef file.json]`: the server
  (Python standard library only). `worlddef.py` builds the world definition from the APK's prototypes.
- `patcher/patch_apk.py <apk> <server-url> [--debug-log] [--emulator] [--signer jar]`: rewrites the two server
  URLs in `lib/armeabi/libsdr.so` (server URL ≤ 29 characters), optionally re-enables the engine's debug log,
  re-signs. `--emulator` works around the Android Studio emulator's GL driver (see below).

### Testing in the Android Studio emulator

Use an **Android 11 (API 30) x86_64** image (it runs the game's 32-bit ARM code; Android 14+ refuses apps
this old). The emulator reaches the PC at `10.0.2.2`, so type that IP in `patch-apk.bat`; it then also adds
`--emulator`, which skips the emulator's broken `GL_MAX_PALETTE_MATRICES_OES` query (without it the game
aborts at start-up with `RendererResize failed with exception: vector::reserve`).
- `tools/`: reverse-engineering scripts used to derive the protocol (see PROTOCOL.md).
