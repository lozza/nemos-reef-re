# Run Nemo's Reef without keeping your laptop on

For a copy-and-paste Compose file that builds directly from GitHub, start with
[OMV.md](OMV.md) and [compose.github.yaml](compose.github.yaml). The local-source
instructions below are an alternative for an extracted or cloned project.

This package is based on `lozza/nemos-reef-re`, branch `re-notes`, commit
`a09f0ad5cfe61090e880fcbf1e87516ce4561de7`. The server uses Python's standard
library and SQLite; no Java or Android emulator runs inside the container.

Docker still needs a computer that stays on: a NAS, Raspberry Pi with a 64-bit
Linux OS, or a cloud VM with Docker Engine and the Compose plugin. Your phone
connects directly to that computer. A container on your laptop stops when it sleeps.

## Start the server

1. Extract this package on the host. If using GitHub instead, select the branch
   containing these Docker files; upstream `main` only contains a placeholder README.
2. Put your **original** Nemo's Reef Android 1.8.1 APK beside `compose.yaml`, named
   `nemo.apk`. It must be a readable file. The APK is mounted read-only at runtime;
   it is excluded from the image and must not be uploaded to GitHub or a registry.
3. Create a `.env` file beside `compose.yaml` containing your host's **LAN or VPN**
   address (the example below must be replaced with your address):

   ```dotenv
   NEMO_BIND=192.168.1.20
   NEMO_PORT=8080
   ```

   Without `.env`, the port listens only on `127.0.0.1` for local testing.
   The game protocol uses HTTP, device IDs and player IDs with limited authentication.
   For a cloud host, connect the phone and host through a private VPN and bind to
   the host's VPN address. Keep port 8080 closed on the public internet.
4. Run from this directory:

   ```sh
   docker compose up -d --build
   docker compose ps
   docker compose logs --tail=50 nemo
   ```

   The service should become `healthy`. Check `http://YOUR_HOST:8080/healthz`
   from the phone's network; it returns `{"status":"ok"}`. Allow TCP 8080 only
   from your trusted LAN/VPN. Make sure Docker starts when the host reboots.

The image runs as UID/GID 10001. Saves and the request log live in the Compose
volume `nemos-reef_reef-data`, mounted at `/data`, separately from the image.
Only one server instance should use that volume. Console logs rotate; the
server's separate `/data/requests.log` does not, so monitor its size and archive
or truncate it while the service is stopped.

## Keep your existing reef

Do this **before playing on the new server**. Close the old laptop server and
back up its entire `server/data` directory. Copy that directory to the new host
beside `compose.yaml`, renamed `old-data`. Keep the original backup untouched.
On a Linux host, run:

```sh
docker compose build
docker compose stop nemo
docker compose run --rm --no-deps --user 0 --entrypoint sh \
  -v "$PWD/old-data:/old-data:ro" nemo -c \
  'test ! -e /data/nemo.db && cp /old-data/nemo.db /data/nemo.db && chown 10001:10001 /data/nemo.db'
docker compose up -d
```

This refuses to overwrite a database already on the new host. If it refuses,
stop and back up that database before choosing which save to keep. Always stop
the old server before copying a database so it is consistent.

Keep the phone's existing app data and device identity. The database contains
all players, reefs and friendships; `requests.log` is not needed to load saves.

## Point the game at the new host

The installed APK embeds the laptop's URL. Patch your original APK again with
the host's LAN/VPN address using the existing patcher and signing tool:

```sh
python patcher/patch_apk.py nemo.apk http://192.168.1.20:8080 --debug-log
```

Replace the address with your host's actual address. The patcher restricts the
base URL length (the upstream README documents a 29-character limit), so use a
short hostname or an IPv4 address. Keep the same port in the URL and `.env`.
Use the **same signing key** as the currently installed private APK, and install
as an update over it. **Do not uninstall the app or clear its data to migrate**;
that can lose the device identity used to find its saved reef. If Android reports
a signing-key mismatch, recover the original signing key before proceeding.
Java and the signer are needed only on the patching computer, which can then be off.

## Backups, upgrades and stopping

For a consistent backup, briefly stop the service and copy its database:

```sh
mkdir -p backups
docker compose stop nemo
docker compose cp nemo:/data/nemo.db ./backups/nemo.db
docker compose start nemo
```

Copy backups off the host and use dated filenames for later backups.
To upgrade the code, back up first, then run `docker compose up -d --build`.
`docker compose down` keeps the saved volume. **Do not use `down -v`** unless
you intend to delete all saved reefs and accounts.

## Build or transfer just the image

```sh
docker build -t nemos-reef:local .
docker save -o nemos-reef-image.tar nemos-reef:local
# On another host of the same CPU architecture:
docker load -i nemos-reef-image.tar
```

Also transfer `compose.yaml` and your private APK separately. On the receiving
host, run `docker compose up -d --no-build`. Build natively on your target CPU
architecture; the server is pure Python and does not execute the APK's ARM code.

## Verification

`python -m unittest discover -s tests -v` uses a tiny synthetic asset archive,
without copyrighted game files, to check real server startup with the story,
health checks without account/log side effects, account login, and SQLite
world persistence across process restarts. The GitHub workflow additionally builds
and smoke-tests the actual Docker image and Compose setup on Linux.
Full device play still requires your APK and phone.

Docker references: [Dockerfile](https://docs.docker.com/reference/dockerfile/),
[Compose services](https://docs.docker.com/reference/compose-file/services/).
