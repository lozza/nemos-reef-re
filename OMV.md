# OpenMediaVault setup

Use the same prebuilt image and copy-and-paste Compose file as Portainer.

1. Copy your original Nemo's Reef Android 1.8.1 APK into an OMV shared folder.
2. Find its Linux absolute path under **Storage > Shared Folders**.
3. Open **Services > Compose > Files** and create an entry called `nemos-reef`.
4. Paste [docker-compose.yml](https://raw.githubusercontent.com/lozza/nemos-reef-re/main/docker-compose.yml)
   into the **File** box.
5. Change `source: /path/to/nemo.apk` to the APK's actual full path on OMV.
   Leave the Environment box empty.
6. Save and choose **Up**. The image downloads automatically; no Build step is needed.
7. Check `http://YOUR-OMV-IP:8080/healthz`, then follow the
   [shared patching instructions](DOCKER.md#connect-the-game).

If port 8080 is already used, change `"8080:8080"` to `"8081:8080"` and use
8081 in the health URL and game patcher. The phone uses OMV's LAN IP address.

**Existing saves:** the volume remains `nemos-reef_reef-data`. Stop the old
server and back up `server/data` before migrating. Preserve the phone's app
data and signing key. Follow [the migration instructions](DOCKER.md#keep-your-existing-reef)
using the same stack configuration and the old-data directory's actual host path.

For GUI-managed stack backups, stop the entry and run this through SSH on OMV
from your backup directory:

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
