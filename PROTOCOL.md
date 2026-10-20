# Nemo's Reef (Android 1.8.1, `com.disney.nemo`) — server protocol notes

Reverse-engineered from `lib/armeabi/libsdr.so` (Living Mobile "sdr" C++ engine, symbols intact).
All networking is native (bundled libcurl); the Java layer only hosts ads/billing/push.

## Servers (both plain HTTP, no TLS, no cert pinning)

| Purpose | Base URL (string in libsdr.so) |
|---|---|
| Tapulous account API (`netcl::ta::Tap*`) | `http://nemo.apps.tapulous.com/nemo/api/` |
| Game API (`netcl::Action*`, game actions) | `http://nemo.pragueweb.tapulous.com/nemo/` |
| Push notifications | `http://apps.tapulous.com/misc/notifications/` |

Redirect options: patch these strings in `libsdr.so` (same length or shorter, NUL-padded) and re-sign
the APK, or point the hostnames at our server via DNS.

## Tapulous account API (`netcl::ta::TapAction`)

POST form fields on every call:

- `format=json`
- `api_key=OI6TWPNH-IEJT-06C2-VG65-HP6HDJH8QHGZ` (`TapConfig::getAPIKey`, candidate)
- `timestamp=<unix seconds>`
- `token_info=<UDID>` (`TapConfig::getUDID`)
- method-specific fields (below)
- `api-sig` = base64(HMAC-SHA1(key = API secret + "&", msg = "POST&" + urlencode(url) + "&" + urlencode(sorted k=v pairs joined by "&")))
  — OAuth-1-style; API secret candidate `1VDE5CLX-U1RR-WHLQ-I2IF-HQRHTD609J14`. Server may ignore it.

| Action class | method / path | request fields | response fields |
|---|---|---|---|
| TapRegisterUser | `register_user` | `proposed_name` | `user{user_id, username}` |
| TapDeviceLogin | `login` | `username`, `email` | |
| TapDeviceLogout | `logout` | | |
| TapRecommendName | `recommend_name` | | `suggestedName` |
| TapChangeName | `change_username` | `new_username` | |
| TapGetFriends | `get_friends` | | `friends[{user_id, username, has_app}]` |
| TapAddFriend | `add_friend` | `friend_name` | `friend{user_id, username}` |
| TapAuthorizeUser | **game server** `/api/authenticate` | `lang_code` | `user_id`, `username`; `attachedData.clientSignatureKey` |

Response envelope (`TapAction::loadingFinished`): `{ "status": ..., "code": ..., "reason": ..., "response": {...}, "attachedData": {...} }`.

## Game API (`netcl::ComManager`)

`POST <game base>/api...` (form-encoded) with fields:

- `json` = request body (JSON)
- `uid` = user id
- `signature` = `sha1_hex(utf8(secret + json + uid))`
  - values concatenated in key order (`json` < `uid`); `secret` = `clientSignatureKey`
    from `/api/authenticate`, or the literal `bsF3Ey6XNn` when no secret is set yet.

Request JSON header fields (`ComManager::addRequestHeader`):
`stamp` (incrementing int64), `uid`, `worldVersion`, optional `serverId`, optional `lastStamp`.

Response: JSON; game-action results under `reactions`, status in `resultCode`; client picks up
`serverId` from responses (`trySetServerId`) and errors per entity (`EntityManager::processErrorOnEntity`).
**Responses are not signed/verified by the client.**

Endpoints referenced: `/api/authenticate`, `/api/startgame`, `/api/getDaWorld`, `/api/getTutorialWorld`,
`/api/getCurrentWorldVersion`, `/api/getFriendWorld`, `/api/getFriendStatus`, `/api/getFriendLastTime`,
`/api/getLocalizedTextsBundle`, `/api/getCoopQuestParticipants`, `/api/startCoopQuest`, `/api/reset`,
`/api/resources/` (asset bundle download, see `assets/bundle.json`).

Game-action names (sent inside the request JSON; ~49 `netcl::ga::GA_*` classes), e.g.
`emptyAction, resumeGame, entityConstruct, entityMove, entityRefund, entitySeed, entityFeed,
entityCollectReward, friendsEntityCollectReward, entitySpeedupFeed, entityFreeSpeedupFeed,
entityConstructionSpeedup, entityConstructionFreeSpeedup, entitySpeedupProduction,
entityFreeSpeedupProduction, seedEntitySeed, getFriendFish, getFriendVitality, dailyRewardCollect,
dailyTapReward, dailyTapRewardExtraTap, dailyTapRewardGetEverything, placeEntityInPatch,
placeEntitiesToInventory, getUserWorld, confirmMessages, placeItemForCleaning, cleanItemForCleaning,
sectorBuy, getCurrentWorld, ...`

## Big open item

Game economy/definitions (`worldDef`: prices, grow/produce times, levels, quests, daily rewards) are
**sent by the server**, not bundled in the APK. These must be reconstructed from the client's parsers
(`loadDefinition`, `restoreStateFromServer`, `processResponse*`) and sensible values.

## Tooling (in this workspace)

- `tools/pic.py` + `tools/strmap.py` → `tools/calls.txt`: every call site with resolved string args.
- `tools/emu_init.py`: Unicorn-emulates all static initialisers to name global `sdr::String` keys.
- `tools/fstr.sh <regex>`: string args used per function.
- Ghidra project (`analyzeHeadless` + `tools/DumpDecomp.java`) (base 0x10000 vs file addresses).
