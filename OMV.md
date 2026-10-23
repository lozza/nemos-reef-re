# OpenMediaVault setup

Use the same prebuilt image and copy-and-paste Compose file as Portainer.

1. Copy your original Nemo's Reef Android 1.8.1 APK into an OMV shared folder.
2. Find its Linux absolute path under **Storage > Shared Folders**.
3. Open **Services > Compose > Files** and create an entry called `nemos-reef`.
4. Choose a Compose file and paste it into the **File** box:
   - [Shared-folder file](https://raw.githubusercontent.com/lozza/nemos-reef-re/main/compose.shares.yaml)
     if you want the database in your own OMV share.
   - [Default file](https://raw.githubusercontent.com/lozza/nemos-reef-re/main/docker-compose.yml)
     if you want Docker to manage the saved-data volume.
5. With the shared-folder file, edit **both** `source:` lines: the APK file
   and the writable data folder. Keep `/game/nemo.apk` and `/data` as the targets.
   Create the data folder before deployment and give UID/GID `10001:10001`
   write access. Leave the Environment box empty.
6. Save and choose **Up**. The image downloads automatically; no Build step is needed.
7. Check `http://YOUR-OMV-IP:8080/healthz`, then follow the
   [shared patching instructions](DOCKER.md#connect-the-game).

## Example: a folder called /media/nemo

Your folder should contain:

```text
/media/nemo/
  nemo.apk
  data/
```

In the shared-folder file, set the APK `source` to `/media/nemo/nemo.apk`
and the save-folder `source` to `/media/nemo/data`.

```sh
sudo mkdir -p /media/nemo/data
sudo chown 10001:10001 /media/nemo/data
```

Use your own share's actual path in both the YAML and commands.
For example, a folder at `/srv/dev-disk-by-uuid-.../appdata/nemo` has
`nemo.apk` and `data` inside that folder. There is no requirement to use
`/media/nemo`. Find the real path under **Storage > Shared Folders**;
a Windows path such as `\\OMV\share\nemo` is not the Linux host path.

The APK is read-only (`read_only: true`, equivalent to `:ro`).
The data folder is writable so the game can save.
[Full explanation and more path examples](DOCKER.md#use-your-own-shared-folder).

If port 8080 is already used, change `"8080:8080"` to `"8081:8080"` and use
8081 in the health URL and game patcher. The phone uses OMV's LAN IP address.

**Existing saves:** the default file still uses `nemos-reef_reef-data`.
If moving from that volume to a share, [copy the saved database before changing
storage](DOCKER.md#move-an-existing-docker-save-to-a-share). Stop the old
server and back up `server/data` before migrating. Preserve the phone's app
data and signing key. Follow [the migration instructions](DOCKER.md#keep-your-existing-reef)
using the same stack configuration and the old-data directory's actual host path.

For a shared-folder deployment, stop the entry and back up `nemo.db` from your
chosen data folder, then start the entry again. Keep dated copies off the NAS.

For the default Docker-volume deployment, stop the entry and run this through
SSH on OMV from your backup directory:

```sh
docker run --rm --entrypoint cat --mount type=volume,source=nemos-reef_reef-data,target=/data,readonly ghcr.io/lozza/nemos-reef-re:latest /data/nemo.db > nemo-backup.db
```

Check the command succeeded, keep dated copies off the NAS, and start the entry.
To update, stop and back up, use OMV's image Pull action, then Up again.
Keep the service on your LAN or private VPN, with router port forwarding off.

If downloading the image reports `denied`, see [Image access](DOCKER.md#image-access).
The public image should not require users to sign in or create registry tokens.

[OMV 7 Compose](https://wiki.omv-extras.org/doku.php?id=omv7:omv7_plugins:docker_compose) ·
[OMV 8 Compose](https://wiki.omv-extras.org/doku.php?id=omv8:omv8_plugins:docker_compose)
