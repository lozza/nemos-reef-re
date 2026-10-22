# Nemo's Reef private server

A replacement server for Disney's *Nemo's Reef* (Android 1.8.1), whose official servers have shut down.
Protocol details are in [PROTOCOL.md](PROTOCOL.md); game actions in [ACTIONS.md](ACTIONS.md).

**Status:** early. Runs on a real device (Fire 7). Login, saving what you buy, place, feed, move and collect, the
original starter reef, friends (add by name, visit and help each other's reefs) and the story work. The story has 210 of the original quests plus 36 time events
quests (story, side quests, Tank Gang, guest missions, tutorials) under their original ids and texts, offered in the
order of a Let's Play of the original game and then by level. The shop locks items until their level (GET IT EARLY
costs double and gives free algae) and the daily reward (tap the hidden plants) opens once a day. Treasure chests
appear on the reef after the chest tutorial, and Squirt plays Hide and Seek every few hours after "Let's Play!".
Vitality is worked out from your plants and fish (capped per level, as in the original), and from about
level 10 Patches let four plants of a kind grow into one upgraded plant. From about level 9 Mr. Ray sets daily homework. The
original time events come back too: Christmas, Halloween, Valentine's and Easter ones on their dates every year,
the others one each weekend (Friday to Monday), from level 6. Co-op quests (with other players) are not done yet.
The Android Studio emulator draws some sand paths white; real devices are fine.

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
It converts the game's textures (about a minute), then should say `wrote signed nemo-private.apk`. The new file `nemo-private.apk` appears in the
project folder. This copy of the game talks to your PC instead of Disney's old servers.

**Music (optional):** this copy of the game has no music files. The iOS version of the game has the original
four tracks as `music0.mp3` … `music3.mp3`. Put them (or your own `.ogg`/`.mp3` files with those names) in a
`music` folder next to `patch-apk.bat` before running it, then install the new `nemo-private.apk` (step 7).

### 7. Install it on the phone

1. Uninstall any old copy of Nemo's Reef from the phone.
2. Copy `nemo-private.apk` to the phone (USB cable, Google Drive, email to yourself, …).
3. On the phone, open it from the Files/Downloads app and tap **Install**. If Android asks, allow
   "Install unknown apps" for that app.

The game is 32-bit only, so it will not install on 64-bit-only phones (Pixel 7 and newer, some 2023+ phones).
In that case use BlueStacks on the PC (drag `nemo-private.apk` onto the BlueStacks window to install).

## Players

Each device is its own player. The first time the game starts on a device it asks for a profile name (names are
unique; a taken one gets a number added). Players who enter an age under the game's age limit get the Kids edition:
easier fish combinations and hints for the guest missions, and three Kids-only quests. It takes effect from the
second time the game is started (the game only tells the server the age group after loading the world).

**Friends:** in the game's Friends screen, tap **Invite** and type the other player's profile name. You both then
see each other in your friend lists and can visit each other's reefs, help out there (5 actions a day), and look at
each other's sticker album and Vitality.

## Playing / testing

1. Double-click **`start-server.bat`**. A window opens saying `Nemo's Reef server on http://0.0.0.0:8080`.
   If Windows Firewall asks, tick **Private networks** and click **Allow access**.
   Keep this window open; each request from the game shows up in it.
2. Start the game on the phone.

When something goes wrong, send `server\data\requests.log` from the project folder.

To start completely fresh as a new player (the game asks for a name and age again), close the server window,
clear the game's data on the phone (Settings → Apps → Nemo's Reef → Storage → **Clear data**), then double-click
**`new-start.bat`**. It deletes every account and reef and runs the server.

To start over with a fresh starter reef (for example after updating the server), close the server window and
double-click **`reset-reef.bat`**. It asks for confirmation, deletes the saved reefs (your account stays), and then
runs the server.

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
- `tools/build_story.py`: generates `server/story.json` (quests, dialogs, hints, patterns, items) from the quest
  catalogue made from the game's text table and the fan wiki's prices and timers. story.json holds text keys only;
  the server reads the texts from the APK. `--rare-fish` / `--vitality-patches` take the 2014 worldDef lists
  (rareFishList, vitalityPatchList) saved on the fan wiki.
