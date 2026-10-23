# OpenMediaVault setup

Nemo's Reef Revival uses the same [compose.yaml](compose.yaml) on every host.
This page only explains where to paste it in OMV.

1. Copy your original Android 1.8.1 APK to an OMV shared folder as `nemo.apk`.
   Find its Linux absolute path under **Storage > Shared Folders**.
2. Open **Services > Compose > Files** and create an entry called `nemos-reef`.
3. Paste [compose.yaml](https://raw.githubusercontent.com/lozza/nemos-reef-re/main/compose.yaml)
   into the **File** box.
4. Change just `source: ./nemo.apk` to the APK's absolute path on OMV. For example:

   ```yaml
           source: /srv/dev-disk-by-uuid-YOUR-DISK/appdata/nemo/nemo.apk
   ```

   Replace the entire example with your real file path. Keep the same indentation.
   The file must be readable by UID 10001; normal file permissions of 644 work.
5. Leave the **Environment** box empty. Save, select **Build** (under Tools on
   some versions), then **Up**.
6. Visit `http://YOUR-OMV-IP:8080/healthz` from the phone's network. It should
   return `{"status":"ok"}`.
7. Patch the game to use `http://YOUR-OMV-IP:8080`, then install it. Follow the
   [shared Docker guide](DOCKER.md) for patching prerequisites and keeping saves.

If port 8080 is already used, change `"8080:8080"` to `"8081:8080"` and use
8081 in the health URL and APK patcher. No IP address is entered in Compose.

Your own server and save database stay on your own Docker host. Saves live in
`nemos-reef_reef-data`, the same volume name used by previous project examples.
The updated Compose file ignores old `NEMO_*` environment variables; carry
over any custom APK path or port directly into the YAML.

**Moving an existing reef:** stop the old server and back up `server/data`.
Build the new image, stop the new stack, then import the database before
playing. See [the migration instructions](DOCKER.md#keep-your-existing-reef).
Keep the phone's app data and use the original signing key when updating the APK.

For GUI-managed stack backups, stop the entry, then run the following through
SSH on OMV from a backup directory:

```sh
docker run --rm --entrypoint cat --mount type=volume,source=nemos-reef_reef-data,target=/data,readonly nemos-reef:local /data/nemo.db > nemo-backup.db
```

Check the command succeeded, keep dated backups off the NAS, and start the
entry again. Leave router port forwarding off for this local game server.

[OMV 7 Compose documentation](https://wiki.omv-extras.org/doku.php?id=omv7:omv7_plugins:docker_compose) ·
[OMV 8 Compose documentation](https://wiki.omv-extras.org/doku.php?id=omv8:omv8_plugins:docker_compose)
