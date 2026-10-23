# OpenMediaVault setup

[All guides](README.md)

Use this if OMV already has the Compose plugin installed. If you manage Docker
through Portainer instead, follow [Docker setup](DOCKER.md).

## 1. Choose your storage

Copy your original Android 1.8.1 APK to an OMV share. Under
**Storage → Shared Folders**, find the share's absolute Linux path.

Choose one Compose file:

| Where to save reefs | File and instructions |
|---|---|
| Let Docker manage saves; easiest setup | [Docker setup, steps 1–2](DOCKER.md#1-put-the-original-apk-on-your-server) |
| In a folder on your own share | [Shared folders](SHARES.md) |

## 2. Deploy

1. Open **Services → Compose → Files** and create `nemos-reef`.
2. Paste your chosen Compose file into **File**.
3. Edit its `source:` paths to match your OMV paths. Leave **Environment** empty.
4. Save, then choose **Up**. There is no Build step.

If the chosen port is busy, [find an available port](TROUBLESHOOTING.md#port-is-already-allocated).

## 3. Check and connect

Open `http://YOUR-OMV-IP:8080/healthz` in a browser. Replace the IP and,
if you changed it, the port. You should see `{"status":"ok"}`.

**Next: [Patch and install the APK](PATCHING.md)** using that same OMV IP and port.

[Folder permissions](SHARES.md#2-allow-the-server-to-save) ·
[Backups and updates](SAVES.md)
