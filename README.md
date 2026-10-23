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

In Portainer:

1. Copy your original APK onto the Docker host.
2. Open **Stacks > Add stack > Web editor** and name the stack `nemos-reef`.
3. Paste the Compose file above.
4. Replace `/path/to/nemo.apk` with the APK's actual full path **on the Docker host**.
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
