# Changes from the original game

[All guides](README.md) · [Game status](STATUS.md)

Nemo's Reef Revival uses the Android 1.8.1 game with a replacement server.
These are the changes we've made to how it plays and runs.

## Fish stay visible when you zoom out

Small ambient fish no longer fade away when you zoom out. You can see them
swimming around while viewing the whole reef.

This is part of the APK patcher. It changes the small fish's visibility, not
the number of fish in your reef.

## Pearls you can earn every day

Real-money pearl purchases are unavailable. To give players a reliable way
to earn pearls, the **third and final daily reward tap always gives pearls**.

The guaranteed amount is **2 pearls, plus 1 for every 10 player levels**:

| Player level | Pearls on the final daily tap |
|---|---|
| 1–9 | 2 |
| 10–19 | 3 |
| 20–29 | 4 |
| 30–39 | 5 |

The first two taps can also give pearls, alongside sand dollars, algae or XP.
Complete all three taps to receive the guaranteed pearl reward.

The ad-funded extra tap and the pearl-spending “get everything” option are
hidden. The three normal daily taps remain available. In-game pearl prices
and spending still apply.

## Events come back

Seasonal events return each year around Christmas, Halloween, Valentine's
Day and Easter. Other time events rotate on weekends, from Friday to Monday,
for players at level 6 or above. Event timing is handled by the replacement
server rather than the old live-service calendar.

## Your server, your reef

You can run the server on Windows, Docker or a NAS, and keep your save files
yourself. Friends are added by their player name and must be using the same
server. There is no shared official player network.

## Fixes for the patched game

- **Settings:** fixed a crash when opening Settings while connected to a server
  by IP address.
- **Saving on newer Android versions:** the patched game uses its internal app
  storage for login details and caches, avoiding the old external-storage path.
- **Texture compatibility:** the patcher adds PNG copies of textures for
  devices that cannot use the original PowerVR format.
- **Large event task windows:** events with more than two objectives use the
  regular quest card. This fixes the crash after the opening conversation in
  “Let's go to the beach!” and keeps all objectives and rewards.

You can also add your own music files when patching; see
[patcher options](DEVELOPMENT.md#patcher-options).

## What to update

Fish visibility and Android compatibility fixes are included when you
[patch the APK](PATCHING.md). An older patched APK needs to be patched again
to pick up those changes; keep your app data when installing the update.

Daily rewards, event schedules and the large-event task-window fix come from
the server. They work with both Windows and Docker. Updating the server does
not require repatching the APK.

## About the reconstruction

The original server is gone, so parts of its economy and progression have been
rebuilt from the information available. Some prices, timers and rewards may
differ from the original. That reconstruction is separate from the deliberate
changes listed above.

For features that are still missing or imperfect, see [Game status](STATUS.md).
