# Troubleshooting

[All guides](README.md)

## Port is already allocated

Another container or program is using the **host port**.

In Portainer, open **Containers** and look at **Published Ports** to find what
uses it. If it is an older Nemo stack, stop that old stack before deploying
the replacement. Leave unrelated services running.

Otherwise choose an available host port. For example, **if 8081 is free**:

```yaml
ports:
  - "8081:8080"
```

Change only the number on the **left**. Keep the container port on the right
as 8080. Use the chosen port in both the health-check URL and the
[APK patcher](PATCHING.md#3-make-the-patched-copy).

## APK file not found or invalid mount

The APK must exist on the **Docker host** at the exact `source:` path.
Check it is a file, not a folder, and that the filename is not accidentally
`nemo.apk.apk`.

Keep `target: /game/nemo.apk` unchanged. Use the original Android 1.8.1 APK.
[Path examples](SHARES.md#1-choose-a-folder-on-your-docker-host).

## Permission denied or unable to open database

With shared-folder storage, the container's user/group 10001:10001 must be able
to write the data folder and any existing `nemo.db`.
[Set folder permissions](SHARES.md#2-allow-the-server-to-save).

If SSH says **“appuser is not in the sudoers file”**, repeating `sudo` will
not fix it. Use the temporary folder-setup stack in that guide if you manage
Docker through Portainer or OMV.

## The game cannot connect

1. Keep the server running and the phone on the same home network.
2. Open the server's `/healthz` address in the **phone's browser**.
3. If it fails, check the server IP, host port, firewall and whether guest Wi-Fi
   prevents devices from reaching each other. On Windows, allow Python on
   **Private networks**.
4. If the health page works but the game does not, check that the installed APK
   was patched for that same IP and port. Patch again after an address change.

Use the server computer's LAN IP, not `localhost`, `0.0.0.0`, the container
IP or the patching laptop's IP when Docker runs elsewhere.

## Android will not install the APK

Check the patcher finished with **wrote signed nemo-private.apk**, and that
the device supports 32-bit apps.

If Android reports a conflicting package or signature, the installed copy may
have a different signing key. For an existing player, preserve app data and
reuse the original signing setup. Uninstalling or clearing app data can lose
the device's player identity.

For a first installation with no progress to keep, an incompatible old copy
may need removing before the newly signed copy can install.

## Python or Java is not recognised

Close and reopen Command Prompt after installing. Check
`python --version` and `java -version`. If either command fails, fix that
program's installation/PATH before running the patcher again.

## Image download says denied

The image is intended to be public:
[container package](https://github.com/users/lozza/packages/container/package/nemos-reef-revival).

Check the image name is `ghcr.io/lozza/nemos-reef-revival:latest`.
Remove stale registry credentials in your container manager and retry.
Users should not need a GitHub token to pull this public image.

## My reef looks new after moving or updating

Stop and preserve both old and new databases. Check the
[save locations](SAVES.md#where-is-my-save) and confirm the phone still has
its original app data. Changing a volume path does not copy an existing save.

## Reporting a game problem

Include what you did, what you expected, what happened, and your server version.
Server logs are in `requests.log` next to `nemo.db`.
Container logs are also available in Portainer/OMV, or with
`docker compose logs --tail=50 nemo`.

Logs can include player names and identifiers; review them before sharing.
[Detailed Android logging](DEVELOPMENT.md#android-game-logs).
