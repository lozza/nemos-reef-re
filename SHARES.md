# Docker saves in your own shared folder

[All guides](README.md) · [Docker setup](DOCKER.md)

Optional: use this if you want saved reefs in a folder you can browse on your
server. The default Docker setup already saves progress in a Docker-managed volume.

**Already playing with the default setup?**
[Move your existing save first](SAVES.md#move-from-a-docker-volume-to-a-shared-folder).
Changing the Compose paths alone will not move it.

## 1. Choose a folder on your Docker host

Create a folder on your NAS or server. For example:

```text
/media/nemo/
  nemo.apk       original Android 1.8.1 APK
  data/          folder for accounts, reefs and logs
```

Your own share may use a completely different path. On OMV, find it under
**Storage → Shared Folders**. Use the absolute path on the Docker host,
not a Windows network address such as `\\NAS\share`.

Use **[compose.shares.yaml](compose.shares.yaml)**
([raw copy](https://raw.githubusercontent.com/lozza/nemos-reef-revival/main/compose.shares.yaml)).
Change **both `source:` paths**:

| What | Example source on your server | Target inside the container |
|---|---|---|
| Original APK file | `/media/nemo/nemo.apk` | `/game/nemo.apk` |
| Save folder | `/media/nemo/data` | `/data` |

Keep both targets unchanged. If your folder is
`/srv/storage/appdata/nemo`, the sources become
`/srv/storage/appdata/nemo/nemo.apk` and `/srv/storage/appdata/nemo/data`.

The APK's `read_only: true` means “read but do not change”; `:ro` means the
same thing in Docker's shorter syntax. The save folder must stay writable.

## 2. Allow the server to save

The container runs as user/group **10001:10001**. On Linux, its data folder
must be writable by that user.

**With sudo access**, run these on the Docker host, using your own data path:

```sh
sudo mkdir -p /media/nemo/data
sudo chown 10001:10001 /media/nemo/data
```

**Without sudo access**, you can prepare a new folder through Portainer or
OMV Compose. Deploy this as a separate, temporary stack named
`nemo-folder-setup`. Change the path on the left of `:/data` to your data folder:

```yaml
name: nemo-folder-setup

services:
  prepare-nemo:
    image: ghcr.io/lozza/nemos-reef-revival:latest
    user: "0:0"
    entrypoint: ["/bin/sh", "-c"]
    command:
      - "chown 10001:10001 /data && echo 'Nemo data folder ready'"
    volumes:
      - /media/nemo/data:/data
    restart: "no"
```

The helper uses root briefly to set ownership of that folder. It has no
published ports. **“Nemo data folder ready” and Exited (0) mean success.**
You can then remove the temporary stack.

This prepares the folder itself. If it already contains save files, those
files must also be writable by 10001:10001; follow [save migration](SAVES.md)
when copying an existing database.

## 3. Deploy the game server

Go back to [Docker setup, step 3](DOCKER.md#3-start-it) or
[OMV setup, step 2](OMV.md#2-deploy) and deploy the edited
`compose.shares.yaml` as your game stack.

The shared-folder file replaces the default Compose file. It does not need
a bottom-level `volumes: reef-data:` declaration.

[Next: patch the APK](PATCHING.md) · [Back up this folder](SAVES.md)
