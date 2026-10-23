# Docker setup for everyone

This guide is for anyone running their own local copy of Nemo's Reef Revival.
The same Compose file works with Docker Compose on Windows, macOS, Linux and
NAS systems with build support. The APK is supplied locally by each user.

## Quick start: two files and one command

Install Docker Desktop on Windows/macOS, or Docker Engine and the Compose
plugin on Linux. Use Linux containers. The first build needs internet access
to GitHub and Docker Hub.

Create this folder:

```text
nemo/
  compose.yaml
  nemo.apk
```

- Download [compose.yaml](https://raw.githubusercontent.com/lozza/nemos-reef-re/main/compose.yaml).
- Supply your own original Nemo's Reef Android 1.8.1 APK, renamed `nemo.apk`.
- Open a terminal in this folder and run:

```sh
docker compose up -d --build
```

No Git clone, Python installation or `.env` file is needed to run the server.
Python and the server are built into the Docker image. The APK is mounted
read-only at runtime and is never baked into the image or uploaded to GitHub.

The image builds from the server code on the `re-notes` branch. There is no
prebuilt registry image to pull. A computer running the container must remain
powered on; this can be the same computer you play on or an always-on host.

## Connect the game

1. Find the server computer's **LAN IPv4 address**. On Windows, run `ipconfig`;
   on macOS, look in Network settings; on Linux, inspect the network settings.
   Reserve that address in your router if possible so it stays the same.
2. From a device on the same network, open
   `http://YOUR-SERVER-IP:8080/healthz`. It should return `{"status":"ok"}`.
3. Download the [project source](https://github.com/lozza/nemos-reef-re/archive/refs/heads/re-notes.zip)
   on the computer used for patching, and extract it. Follow the
   [patcher prerequisites](https://github.com/lozza/nemos-reef-re/blob/re-notes/README.md#setup-on-windows-one-time)
   for Python, Java and the signing tool. In the extracted project folder run:

   ```sh
   python patcher/patch_apk.py nemo.apk http://192.168.1.20:8080 --debug-log
   ```

   Replace the example IP with your own server's address, and supply the
   original APK in the patching folder too. Keep the server URL short; the
   upstream patcher documents a 29-character limit.
4. Install the resulting patched APK. If you already play, use the same signing
   key and install it as an update. **Do not uninstall the game or clear its
   data when moving an existing reef**: the saved device identity finds your account.

The patched game still requires a compatible 32-bit-capable Android device
or compatible emulator. Docker runs the Python server, not Android or the game.

## NAS and web-based stack editors

Use the **same** `compose.yaml`. Paste it into your stack editor, then change
just the `source` line to your APK's real path on the Docker host:

```yaml
        source: /path/on/your/nas/nemo.apk
```

Replace that entire example with an existing, readable file. A Windows network
share path such as `\\NAS\share\nemo.apk` is not a Linux host path.
The container runs as UID/GID 10001; a regular file permission of 644 is sufficient.

Build and start the stack. No environment variables or server IP entry are
required in Compose. Your server IP is only used when patching the game.
See [OMV.md](OMV.md) for an OpenMediaVault example.

Some stack managers only deploy existing images and cannot build from Git.
In that case, use the Docker host's terminal to run the quick-start command
first, then manage the existing stack there.

## Ports and private-network access

`"8080:8080"` publishes the game on port 8080 on the host's network interfaces.
Allow access only from your trusted home network or private VPN. Leave router
port forwarding off; this legacy server has limited authentication.

If the host port is busy, change only the **left** number, for example:

```yaml
    ports:
      - "8081:8080"
```

Then use 8081 in the health URL and APK patcher. The internal port remains 8080.
The phone uses the host computer/NAS's address, not a Docker container IP.
Allow the chosen TCP port through the host firewall for the private network.

## Keep your existing reef

Do this before playing on a new server.

1. Stop the old server and back up its entire `server/data` directory.
2. Copy that directory into your new `nemo` folder as `old-data`.
3. Build the image with `docker compose build`, then stop any running new server
   with `docker compose stop nemo`.
4. Run the command below from the `nemo` folder. It works in PowerShell on
   Windows and a terminal on macOS/Linux:

```sh
docker compose run --rm --no-deps --user 0 --entrypoint sh -v "./old-data:/old-data:ro" nemo -c 'test ! -e /data/nemo.db && cp /old-data/nemo.db /data/nemo.db && chown 10001:10001 /data/nemo.db'
```

This deliberately refuses to overwrite an existing `/data/nemo.db`. If it
fails, inspect the error and preserve the existing save before choosing which
database to use. Keep the original backup untouched.

Start the new server with `docker compose up -d`. Keep the phone's existing
app data and signing key. The database holds accounts, reefs and friendships;
the old `requests.log` is not needed to load a reef.

For a NAS stack, stop it in the GUI, then perform the import in a terminal
using the same Compose configuration and the real old-data path on that host.

## Everyday commands

Run these in the folder containing `compose.yaml`:

| Task | Command |
|---|---|
| Start | `docker compose up -d` |
| Check status | `docker compose ps` |
| View recent logs | `docker compose logs --tail=50 nemo` |
| Stop | `docker compose stop` |
| Update from GitHub | `docker compose up -d --build` |

The saved volume `nemos-reef_reef-data` survives image rebuilds and ordinary
`docker compose down`. **Do not use `down -v` or delete the volume** unless
you intend to remove every account and reef. Only one server instance should
write to this volume. Separate Docker hosts have separate saves.

## Back up saves

Create a `backups` folder next to `compose.yaml`. Stop the service briefly:

```sh
docker compose stop nemo
docker compose cp nemo:/data/nemo.db ./backups/nemo.db
docker compose start nemo
```

Check the copy succeeded. Keep dated backups off the server and back up before
updating. Monitor Docker logs and `/data/requests.log`; archive or truncate
large logs while stopped.

## Advanced: local source builds and version pinning

With a source checkout, change `build:` to `build: .` to build that checkout.
To pin a GitHub version, replace `#re-notes` in the build URL with a full
commit SHA. These are optional changes; beginners can use the file as supplied.

The old `compose.github.yaml` and `compose.omv.yaml` filenames remain as
copies of the shared configuration for existing links. New instructions use
`compose.yaml`. Old `NEMO_*` environment settings are no longer used by these
files: set the APK path or published port directly in the YAML if needed.

## Verification

GitHub Actions checks startup, accounts and reef persistence with synthetic
assets, then builds and starts both a local-source image and the GitHub-source
Compose setup. It checks that the saved volume survives container replacement.
A real APK and Android device are still needed to verify actual play.

References: [Compose services](https://docs.docker.com/reference/compose-file/services/),
[Git build contexts](https://docs.docker.com/reference/compose-file/build/#context).
