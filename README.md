# Nemo's Reef Revival

> **Early development:** the game is playable, but features are still being
> reconstructed. Back up your reef before updating and report reproducible problems.

An unofficial fan project helping people play Nemo's Reef (Android 1.8.1)
through a server they run on their own computer or home network.
There is no central Revival account or public game server.

## Supported installation

Use the prebuilt container image:

`ghcr.io/lozza/nemos-reef-re:latest`

The image contains only the server. Supply your own original Android 1.8.1 APK;
game files are not included or uploaded. Linux AMD64 and ARM64 images are
published for desktop Docker hosts, compatible NAS systems and 64-bit Raspberry Pis.

### Portainer or Docker Compose

```yaml
name: nemos-reef

services:
  nemo:
    image: ghcr.io/lozza/nemos-reef-re:latest
    pull_policy: always
    ports:
      - "8080:8080"
    volumes:
      - type: bind
        # Change this to your original APK's full path on the Docker host.
        source: /path/to/nemo.apk
        target: /game/nemo.apk
        read_only: true
        bind:
          create_host_path: false
      - reef-data:/data
    restart: unless-stopped

volumes:
  reef-data:
    name: nemos-reef_reef-data
```

For saves in your own share, choose [Use your own shared folder](#use-your-own-shared-folder)
and use that complete Compose file instead of the default example above.

In Portainer:

1. Copy your original APK onto the Docker host.
2. Open **Stacks > Add stack > Web editor** and name the stack `nemos-reef`.
3. Paste the default Compose file above, or the shared-folder file linked below.
4. Set the APK path; with the shared-folder file, set the data-folder path too.
5. Click **Deploy the stack**.
6. Check `http://YOUR-SERVER-IP:8080/healthz`; it should return `{"status":"ok"}`.

No source checkout, local image build, environment file or registry login is
needed for a public image. The health check is built into the image.
If the image reports `denied`, see the [image-access troubleshooting note](DOCKER.md#image-access).

Next, patch the game to use `http://YOUR-SERVER-IP:8080`.
[Full setup, patching, migration and backup instructions](DOCKER.md).
[OpenMediaVault instructions](OMV.md).

The root [docker-compose.yml](docker-compose.yml) and [compose.yaml](compose.yaml)
use the same image, port and save volume as the example above.
For terminal installation, save **one** of those files, set the APK path, then run:

```sh
docker compose up -d
```

### Use your own shared folder

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
move the database. [Copy your current save before switching](DOCKER.md#move-an-existing-docker-save-to-a-share).
The original Compose file still uses `nemos-reef_reef-data` for existing installations.

### Updating

In Portainer, open the stack, choose **Update the stack**, enable **Re-pull image**,
and deploy again. With Docker Compose, run:

```sh
docker compose pull
docker compose up -d
```

Back up first. The `nemos-reef_reef-data` volume keeps accounts and reefs
separately from the image. Existing project installations use the same volume.
Preserve the phone's app data and signing key when moving a reef.
Only one running server should write to that volume.

### Hosting and game files

Use the server on your home network or a private VPN. The legacy game protocol
uses HTTP and has limited authentication; leave router port forwarding off.
If the host port is busy, change `"8080:8080"` to `"8081:8080"` and use port
8081 in the game's patched URL.

Game files are not provided. This project is independent of Disney and Pixar.

## Project links

- [Server source and APK patcher](https://github.com/lozza/nemos-reef-re/tree/re-notes)
- [Issues](https://github.com/lozza/nemos-reef-re/issues)
- [Container image](https://github.com/users/lozza/packages/container/package/nemos-reef-re)
- [Docker build and publication checks](https://github.com/lozza/nemos-reef-re/actions)

The repository/image name remains `nemos-reef-re`; the project is called
**Nemo's Reef Revival**.
