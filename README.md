# Nemo's Reef Revival

An unofficial fan project helping people play Nemo's Reef (Android 1.8.1)
using a server they run on their own computer or home network.

## Start your own server with Docker

Use the same setup on Windows, macOS, Linux, or a NAS that supports Docker
Compose builds. On Windows and macOS, install Docker Desktop; on Linux, use
Docker Engine with the Compose plugin. Run Linux containers.

1. Create a folder named `nemo`.
2. Download [compose.yaml](https://raw.githubusercontent.com/lozza/nemos-reef-re/main/compose.yaml)
   into it. Save it as `compose.yaml`, not `compose.yaml.txt`.
3. Put your own **original Android 1.8.1 APK** in the same folder and name it
   `nemo.apk`.
4. Open a terminal in that folder and run:

   ```sh
   docker compose up -d --build
   ```

That's the entire server setup: two files, one command, no environment file.
The image builds automatically from GitHub. Your APK stays on your machine.

Next, patch the game to connect to `http://YOUR-SERVER-IP:8080`, using the
computer or NAS's LAN address. For example, if that address is 192.168.1.20,
use `http://192.168.1.20:8080`. Use the same home network for phone and server.

**Full instructions:** [Docker setup, APK patching, moving a reef and backups](DOCKER.md).

**Using a NAS web interface?** Paste the same Compose file into its stack
editor. Change `source: ./nemo.apk` to the APK's full path **on the NAS**.
[OpenMediaVault walkthrough](OMV.md). Managers without build support require
building through the host's terminal first.

Saves live in the persistent `nemos-reef_reef-data` Docker volume. Stop the
server before migrating an existing database, and preserve the phone's app data
and signing key. Keep this legacy server on your home network or private VPN.

Game files are not provided. This project is independent of Disney and Pixar.

## Project files

The [`re-notes` branch](https://github.com/lozza/nemos-reef-re/tree/re-notes)
contains the server source, APK patcher, original Windows launchers and full
game documentation. This page provides the shared quick start for everyone.
