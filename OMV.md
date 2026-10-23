# Run Nemo's Reef on OpenMediaVault directly from GitHub

The mini PC builds the Docker image from GitHub and runs it independently of
your laptop. You only need to put your original APK on OMV; downloading the
server source is optional. Use Docker Compose v2 with build support.

## 1. Put the APK on OMV

Create a folder in an OMV shared folder, such as `appdata/nemo`, and copy your
**original Nemo's Reef Android 1.8.1 APK** into it as `nemo.apk`.

Find its Linux absolute path under **Storage > Shared Folders**. For example:

```text
/srv/dev-disk-by-uuid-YOUR-DISK/appdata/nemo/nemo.apk
```

Use your actual path. A Windows SMB path such as `\\OMV\appdata\nemo\nemo.apk`
will not work inside Docker. The APK must be readable by container UID 10001;
a normal file permission of 644 is sufficient. It is mounted read-only and is
never included in the image or uploaded to GitHub.

## 2. Add the Compose file

Open **Services > Compose > Files**, create an entry named **nemos-reef**,
and paste the contents of [compose.github.yaml](compose.github.yaml)
([open the raw YAML](https://raw.githubusercontent.com/lozza/nemos-reef-re/re-notes/compose.github.yaml))
into the **File** box.

In the **Environment** box, enter:

```dotenv
NEMO_APK_PATH=/srv/dev-disk-by-uuid-YOUR-DISK/appdata/nemo/nemo.apk
NEMO_BIND=192.168.1.20
NEMO_PORT=8080
```

Replace the path and IP with your own. `NEMO_BIND` is the **mini PC's LAN IP**.
Reserve that IP in your router so it stays stable. If another service uses
8080, choose a free port and also use it in the APK's server URL.

The Compose build context is:

```yaml
build:
  context: "https://github.com/lozza/nemos-reef-re.git#${NEMO_BUILD_REF:-re-notes}"
```

It reads the Dockerfile and server code from the `re-notes` branch. This is a
source build; no prebuilt registry image is required. The mini PC needs internet
access to GitHub and Docker Hub during the build. Do not replace the branch
with `main`, which is only the project's landing page.

## 3. Build and start

Save the entry and choose **Build** (under Tools on some OMV versions).
If you are moving an existing reef, import its database using the next section
**before playing**. Then choose **Up**.

Check the logs and visit `http://MINI-PC-IP:8080/healthz` from your phone's
network. It should return `{"status":"ok"}`. Make sure Docker starts after the
mini PC reboots. The container restarts automatically unless you stop it.

Keep the service on your LAN or a private VPN, with router port forwarding off.
The legacy game protocol uses HTTP and has limited authentication.

## 4. Keep an existing reef

Skip this section only if you want to start fresh.

1. Stop the laptop server. Back up its entire `server/data` folder.
2. Copy that folder to OMV, for example as `appdata/nemo/old-data`. Keep the
   original backup untouched. Copy only after the old server has stopped.
3. Stop the OMV entry if it is running. Ensure no other container uses the save
   volume. The image must already have been built in step 3.
4. Connect to OMV through SSH and run the following, replacing the example
   `/srv/.../old-data` path with your real absolute path:

```sh
docker run --rm --user 0 --entrypoint sh \
  --mount type=volume,source=nemos-reef_reef-data,target=/data \
  --mount type=bind,source=/srv/YOUR-DISK/appdata/nemo/old-data,target=/old-data,readonly \
  nemos-reef:local -c \
  'test ! -e /data/nemo.db && cp /old-data/nemo.db /data/nemo.db && chown 10001:10001 /data/nemo.db'
```

This refuses to overwrite an existing database on OMV. If it exits with an
error, inspect the message and back up any existing save before choosing which
database to keep. Do not delete a database just to get past that check.

Choose **Up** in OMV. The database contains all accounts, reefs and friendships.
The old `requests.log` is not needed for play.

## 5. Update the game to connect to the mini PC

On the laptop, use the project's existing APK patcher and signing tool:

```sh
python patcher/patch_apk.py nemo.apk http://192.168.1.20:8080 --debug-log
```

Use your actual mini PC IP and port. Keep the base URL short (the upstream
patcher documents a 29-character limit). Install the patched APK **as an update
with the same signing key**. Preserve the phone's app data: do not uninstall the
game or clear its data, because its device identity is used to find the reef.
If Android reports a signing-key mismatch, recover the original key first.

Once the game loads your reef through OMV, the laptop can be switched off.

## Updates and backups

To update, stop the OMV entry, back up the database, choose **Build**, then **Up**.
The GitHub build follows `re-notes`. To hold a specific version, set
`NEMO_BUILD_REF` to a full commit SHA in the Environment box before building.

All Compose variants explicitly use the saved volume `nemos-reef_reef-data`.
Rebuilding the image keeps it. Avoid deleting that volume or using `down -v`.

For a database backup, stop the entry, open an SSH session on OMV, change to
your chosen backup directory, and run:

```sh
docker run --rm --entrypoint cat \
  --mount type=volume,source=nemos-reef_reef-data,target=/data,readonly \
  nemos-reef:local /data/nemo.db > nemo-backup.db
```

Check the command succeeded and keep dated backups off the mini PC. Start the
entry again. For a restore, stop it and preserve the existing database first;
the import command above deliberately refuses to overwrite it.

Console logs rotate automatically. The server's separate `/data/requests.log`
does not, so monitor its size and archive or truncate it while stopped.

## Other ways to run

For a local source checkout use [compose.yaml](compose.yaml), or
[compose.omv.yaml](compose.omv.yaml) when the OMV GUI manages a source directory.
See [DOCKER.md](DOCKER.md) for local builds and image transfers.

The GitHub workflow checks Python startup and saved data using synthetic assets,
builds the container, and exercises both local and GitHub Compose builds.
Full device play still requires your original APK and phone.

References: [OMV 7 Compose](https://wiki.omv-extras.org/doku.php?id=omv7:omv7_plugins:docker_compose),
[OMV 8 Compose](https://wiki.omv-extras.org/doku.php?id=omv8:omv8_plugins:docker_compose),
[Docker Git build contexts](https://docs.docker.com/build/concepts/context/#git-repositories).
