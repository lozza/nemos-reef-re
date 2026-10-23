# Docker and Portainer setup

Nemo's Reef Revival is distributed as a prebuilt container image:

`ghcr.io/lozza/nemos-reef-re:latest`

Use Linux containers on Docker Desktop, Docker Engine, Portainer or a compatible
NAS container manager. AMD64 and ARM64 builds are published. The container runs
the Python server; it does not run Android or the game.

## Portainer: paste and deploy

1. Copy your original Android 1.8.1 APK to a folder on the Docker host.
2. Open **Stacks > Add stack > Web editor**. Name the stack `nemos-reef`.
3. Choose your storage: the [default Compose example](README.md#portainer-or-docker-compose)
   keeps saves in a Docker volume. For saves in your own share, paste
   [compose.shares.yaml](compose.shares.yaml) instead.
4. Set the APK source path. With the shared-folder file, also set the data-folder
   source path and create that folder as described below. Keep the indentation.
5. Click **Deploy the stack**.

Portainer downloads the image and starts it. No build step or Git checkout is
needed. The APK stays on the host and is mounted read-only; saves live in a
Docker volume. The health check is built into the image.

For an existing reef, download the image and import its database before playing;
see [Keep your existing reef](#keep-your-existing-reef).

## Terminal: Docker Compose

Save [docker-compose.yml](https://raw.githubusercontent.com/lozza/nemos-reef-re/main/docker-compose.yml)
in a folder called `nemo`. Edit the APK `source` path, then run from that folder:

```sh
docker compose up -d
```

If the APK is beside the Compose file, `source: ./nemo.apk` works for terminal
use. For NAS or Portainer web editors, use an absolute Docker-host path.
Save only one Compose filename per folder to avoid ambiguity; `compose.yaml`
and the old compatibility filenames contain the same configuration.

On Windows, a path such as `C:/nemo/nemo.apk` can be used in Docker Desktop.
On a Linux NAS, use its real Linux path, not a Windows SMB path such as
`\\NAS\share\nemo.apk`. The file must exist and be readable by container UID
10001; a normal Linux file permission of 644 is sufficient.

## Use your own shared folder

If you want the APK and saved reefs in a folder you can see on your server,
use **[compose.shares.yaml](compose.shares.yaml)**.
[Open the raw file to copy](https://raw.githubusercontent.com/lozza/nemos-reef-re/main/compose.shares.yaml).

Create a `nemo` folder anywhere on your own share:

```text
YOUR-SHARE/nemo/
  nemo.apk       your original APK
  data/          saved reefs, accounts and logs
```

**Change both `source:` paths. Keep both `target:` paths unchanged.**
For example, if your folder is `/media/nemo`:

| What it stores | Your server path (`source`) | Container path (`target`) |
|---|---|---|
| Original APK file | `/media/nemo/nemo.apk` | `/game/nemo.apk` — read-only |
| Saved reefs and accounts | `/media/nemo/data` | `/data` — writable |

Someone using `/srv/storage/appdata/nemo` would instead use
`/srv/storage/appdata/nemo/nemo.apk` and `/srv/storage/appdata/nemo/data`.
Docker Desktop users can use paths such as `C:/nemo/nemo.apk` and `C:/nemo/data`.
These are examples: choose existing paths on **your Docker host**, not a
Windows network-share address or a path on the phone.

The volumes section for the `/media/nemo` example is:

```yaml
    volumes:
      - type: bind
        source: /media/nemo/nemo.apk
        target: /game/nemo.apk
        read_only: true
        bind:
          create_host_path: false
      - type: bind
        source: /media/nemo/data
        target: /data
        bind:
          create_host_path: false
```

Both the APK file and data folder must exist before deployment.
For a new Linux data folder, run on the Docker host:

```sh
sudo mkdir -p /media/nemo/data
sudo chown 10001:10001 /media/nemo/data
```

Replace `/media/nemo/data` in both commands with your chosen data path.
The container runs as user/group `10001:10001` and needs to write there.
`read_only: true` (or `:ro` in short volume syntax) protects the APK;
leave the save-data folder writable. No bottom-level named-volume declaration
is needed with the shared-folder file.

**Already playing?** Changing from `reef-data:/data` to a folder does not
move the database. [Copy your current save before switching](#move-an-existing-docker-save-to-a-share).
The original Compose file still uses `nemos-reef_reef-data` for existing installations.

## Move an existing Docker save to a share

Switching storage does not copy the database automatically. Keep the old volume
and an untouched backup until you have checked that the new setup loads your reef.

1. Create the new data folder and prepare permissions as above. Use an empty
   destination so you do not overwrite another reef.
2. Stop the existing server. From its **current** Compose folder, copy the save
   before changing the volumes configuration:

   ```sh
   docker compose stop nemo
   docker compose cp nemo:/data/nemo.db /media/nemo/data/nemo.db
   sudo chown 10001:10001 /media/nemo/data/nemo.db
   ```

   Replace the destination in both commands with your own chosen data folder.
   On Docker Desktop, use your Windows/macOS path; the Linux ownership command
   is for Linux/NAS hosts. In Portainer, stop the old container first; through
   SSH you can use `docker cp YOUR-EXISTING-CONTAINER:/data/nemo.db /your/data/nemo.db`
   with its actual container name and your actual empty destination.
3. Check that the copy succeeded. Deploy the shared-folder configuration using
   that same data directory. Keep the phone's app data and signing key.
4. Confirm the game loads the expected reef before considering any cleanup of
   the old Docker volume. The request log is not required to load your save.

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
3. Download the image with `docker compose pull`, then stop any running new server
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
| Download an update | `docker compose pull` |

With the default file, the named volume `nemos-reef_reef-data` survives image
rebuilds and ordinary `docker compose down`. With `compose.shares.yaml`, saves
are in the data folder you selected on your host. **Do not use `down -v` or delete the volume** unless
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

## Updating and selecting a version

In Portainer, choose **Update the stack**, enable **Re-pull image**, then deploy.
With Compose:

```sh
docker compose pull
docker compose up -d
```

`latest` follows tested publications from the server's `re-notes` branch.
Each publication also has a `sha-FULL_COMMIT_SHA` image tag for pinning a version.
Replace `:latest` with that tag, or pin an image digest from the package page.
Back up first; a successful container test is not a guarantee against gameplay bugs.

## Image access

A public GHCR image can be pulled without signing in. A `denied` error can mean
the new package has not yet been made public, or that a container manager is
sending stale registry credentials. Check the package's visibility before
asking users to generate registry tokens.

**One-time maintainer step:** after the first publication, open the
[package page](https://github.com/users/lozza/packages/container/package/nemos-reef-re),
choose **Package settings**, then **Change visibility > Public**.
GitHub creates new container packages as private even when the repository is
public. This setting is separate from repository visibility.
After it is public, verify an anonymous `docker pull ghcr.io/lozza/nemos-reef-re:latest`.

## Local development builds

The server source and Dockerfile are on the `re-notes` branch.
To build a checkout locally:

```sh
docker build -t nemos-reef:local .
```

In your development Compose copy, use `image: nemos-reef:local` and remove
`pull_policy: always` so it uses that local image.

## Verification

GitHub Actions tests server startup, account handling and saved reef persistence
with synthetic assets. It then tests the Compose setup, publishes multi-platform
images only after those checks pass, and starts the published image to verify
its health and persistent storage. No original APK is published.

References: [Portainer stacks](https://docs.portainer.io/user/docker/stacks/add),
[GitHub Container Registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).
