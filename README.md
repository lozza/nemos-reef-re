# Nemo's Reef private server

A replacement server for the Android 1.8.1 version of Nemo's Reef.

The server source, APK patcher and full documentation are on the
[`re-notes` branch](https://github.com/lozza/nemos-reef-re/tree/re-notes).

## Run on OpenMediaVault with Docker

Host the server on an always-on mini PC so your laptop can be switched off.
The Compose file builds the Docker image directly from this GitHub repository.

1. Copy your **original Nemo's Reef 1.8.1 APK** to a shared folder on OMV as
   `nemo.apk`. Note its Linux absolute path.
2. In **Services > Compose > Files**, create an entry called **nemos-reef**.
   Copy [this Compose file](https://github.com/lozza/nemos-reef-re/blob/re-notes/compose.github.yaml)
   ([raw YAML](https://raw.githubusercontent.com/lozza/nemos-reef-re/re-notes/compose.github.yaml))
   into the **File** box.
3. In **Environment**, enter these values, replacing the example path and IP
   with your APK path and the mini PC's LAN address:

   ```dotenv
   NEMO_APK_PATH=/srv/YOUR-DISK/appdata/nemo/nemo.apk
   NEMO_BIND=192.168.1.20
   NEMO_PORT=8080
   ```

4. Save, choose **Build** (under Tools on some versions), then **Up**.
   Check `http://MINI-PC-IP:8080/healthz`.

**Keeping an existing reef:** migrate the laptop's database before playing,
then patch the APK to use the mini PC's address. Preserve the phone's app data
and use the same signing key when installing the updated APK.

Follow the [complete OMV setup, migration and backup instructions](https://github.com/lozza/nemos-reef-re/blob/re-notes/OMV.md).
Saves remain in the persistent `nemos-reef_reef-data` volume when the image is
rebuilt. Keep the service on your LAN or a private VPN.

Game files are not included in this repository or the Docker image.
