# Nemo's Reef 1.8.1 (libsdr.so) - game-action protocol spec for a replacement server

> **Correction (verified later):** the client never credits or debits currencies, XP or level itself.
> Every `/api` response must carry the full user `status` object (same format as in startgame) next to
> `reactions`; `netcl::ComManager::loadingFinished` (F:2e8720..2e8764) passes it to
> `TheUser::updateUserStatus`, which updates the HUD (and shows the level-up dialog when `level` rises).
> The server is therefore authoritative for the balance; section 4.4 below is wrong on this point.
> Pushed `messages` types: 1 fish added (`data` = a fishes[] entry), 2 open quest, 3 construction ended
> `{id}`, 4 feed ended `{id,state}`, 6 finish quest, 7 fish removed `{id}`, 8 fish state `{id,state}`,
> 9 sector added, 11 in-game message `{visualStyle,textId,params}`, 17 entity upgraded `{id,full,plantPrototypeId}`.

Scope: the batched game actions (`actions[]` / `reactions[]`) used for normal reef play, the
per-entity JSON in the startgame world lists, and the rules a server needs to keep a world consistent.

Address conventions used below:
- `F:xxxxxx` = file offset = vaddr in libsdr.so (what `re/disx.py` and `calls.txt` use).
- `G:xxxxxx` = Ghidra address = F + 0x10000 (the `@xxxxxxxx` in `re/decomp/*` file names).

Evidence: decompiles in `re/decomp/gar`, `re/decomp/n2r`, `re/decomp/r`, plus new decompiles in
`re/decomp/sa` and `re/decomp/sar` (EntityManager, Growable, Harvestable, Constructable, ProducableFish,
EntityToGaMapper and others). Disassembly came from `disx.py` and an extended copy that also resolves
`ldr rX,[pcrel_table,#n]` into static `sdr::String` table entries. In this binary most JSON keys are
static `sdr::String` objects laid out in 16-byte tables (`+0` vtable, `+4` UTF-16 data, `+8` length).
The texts come from `gstrings_emu.json`.

---------------------------------------------------------------------------------------------------

## 0. JSON-reading semantics you must respect (important for "what if a key is missing")

The client uses a cJSON wrapper (`sdr::JSONObject`). The relevant vtable slots are confirmed from the
`sdr::JSONDict` vtable at 0xc28e98 and the `JSONNumber` vtable at 0xc28d98:

| slot | method |
|---|---|
| +0x0c | toInt() |
| +0x10 | toLong() (64-bit) |
| +0x14 | toFloat() |
| +0x18 | toBool() |
| +0x1c | toString() |
| +0x20 | get(index) |
| +0x24 | count() |
| +0x28 | get(key) |
| +0x2c | hasKey(key) |

- `get(key)` (`JSONDict::get` F:a544cc) does `cJSON_GetObjectItem` then `jsonCast`, and `jsonCast(NULL)`
  returns NULL (F:a54446). The game almost never null-checks the result before calling a virtual on it,
  so **a missing key read with `get` crashes the native client (SIGSEGV)**. Every key described
  below as "required" is read this way.
- `JSONObject::safeGet(key)` (F:18df60) throws `JSONException("Key '<k>' not found in dictionary")`.
  The interval readers use it for `start` and `finish`. Treat it as fatal too.
- Keys that are "optional" are guarded with `hasKey` (+0x2c) first.
- Type coercion: `JSONNumber::toInt` returns the number, and `JSONDict::toInt` throws
  ("JSONDict cannot be used as int"). Always send numbers as JSON numbers, ids as integers, prototype
  ids as strings, and booleans as true/false.
- Timestamps are always read with `toLong()` (64-bit) and are **milliseconds** (see section 5).

---------------------------------------------------------------------------------------------------

## 1. Request side: action objects

Every action is written by `<GA>::addToJson(JSONSerializer&)`:

1. `BasicGA::addActionHeader` (F:2fa1bc / G:30a1bc) writes `"action":"<name>"` and `"aid":<int>`.
2. For almost all actions it then opens `"data":{ ... }` and writes the fields.

So the general shape is:

```json
{"action":"<name>","aid":17,"data":{ ...fields... }}
```

Actions whose `addToJson` only calls `addActionHeader` have **no `data` key**. These are
`collectAllFish` (F:3071c8) and `dailyTapReward` (F:93d6f8).

The internal "type" int stored at GA+0x1c (for example 0x12 for construct) is never serialized.

### 1.1 Placement actions (BasicEntityPlaceGA)

`BasicEntityPlaceGA::BasicEntityPlaceGA(protoId, x, z, Entity*, actionName)` is at F:780d34 / G:790d34.
It stores `+0x24` = Entity*, `+0x30` = prototypeId string, `+0x40` = x and `+0x44` = z.
`BasicEntityPlaceGA::addToJson` is at F:780d98 / G:790d98:

```json
"data": {"prototypeId":"<string>", "x":<int>, "z":<int>, "transform":<int>, "early":<int>}
```

- `prototypeId`: the server prototype id string (the same id used in the world definition / shop).
- `x`, `z`: iso grid tile coordinates. The client keeps them as int16 (`IsoGridLocation{short x, short z}`).
- `transform`: `Entity::getTransformMask()` (F:24f120) returns the byte at Entity+0x44 (the mirror flag).
  The values are 0 or 1. `Entity::applyTransformMask(int)` (F:24f128) only uses bit 0, which sets the mirror.
- `early`: int at Entity+0xf4. It is set by `MapBuilder::init(proto, pos, int)` (F:1b82dc).
  It is 0 for a normal shop build (`ShopScreen::build(proto)` passes 0, F:5be456) and 1 when bought
  through `DialogGetItEarly::buyItem` (F:8faf4c), that is, an item bought before its unlock level,
  presumably paid with hard money. The meaning comes from the call sites; the pricing is a guess.
- **No entity id is sent.** The client gives the new entity a temporary id (section 4) and expects the
  server to return the real id.

The concrete action is chosen by `EntityToGaMapper::sendAction` (F:2ffb38), MappedAction 0, "place":

| GA class | action string | ctor | chosen when |
|---|---|---|---|
| GA_EntityConstruct | `entityConstruct` | F:31e328 | entity is Constructable (vfunc +0x64): decorations, special houses, patches |
| GA_EntitySeed | `entitySeed` | F:33fc18 | entity is Growable (vfunc +0x68): corals, living plants, ornamental plants |
| GA_PlaceItemForCleaning | `placeItemForCleaning` | F:35c3e8 | entity type `ET_BUBBLE` (cleaning/bubble items) |
| GA_SeedEntitySeed | `seedEntitySeed` | F:364d6c | entity type `ET_SEED` (see 1.3) |

All four send the `data` object above. GA_SeedEntitySeed has its own addToJson (F:364da0), which
writes only `prototypeId`, `x`, `z` and `transform` (no `early`).

### 1.2 Entity-id-only actions

Each of these sends `"data":{"id":<int entity id>}` (Entity::getId of GA+0x24). The addToJson addresses
are listed per row:

| GA class | action string | addToJson (F) | MappedAction / sender |
|---|---|---|---|
| GA_EntityGrow | `entityFeed` | 32c974 | 2, feed a plant/coral (`cmd_grow`) |
| GA_EntitySpeedupGrow | `entitySpeedupFeed` | 344c30 | 3, paid growth speed-up |
| GA_EntityFreeSpeedupGrow | `entityFreeSpeedupFeed` | 34974c | 4, free growth speed-up |
| GA_EntityConstructionSpeedup | `entityConstructionSpeedup` | 32333c | 5 |
| GA_EntityConstructionFreeSpeedup | `entityConstructionFreeSpeedup` | 327e58 | 6 |
| GA_EntitySpeedupProduction | `entitySpeedupProduction` | 34e268 | paid production speed-up |
| GA_EntityFreeSpeedupProduction | `entityFreeSpeedupProduction` | 352d84 | 8 |
| GA_EntityRefund | `entityRefund` | 33b1e0 | sell/remove an entity |
| GA_FishFeed | `fishFeed` | 3698ec | feed a (rare) fish |

### 1.3 Other entity actions

- **GA_EntityCollectReward**, `entityCollectReward`, ctor F:31914c, addToJson F:3191fc:
  ```json
  "data": {"id":<int>, "performed":<int64 ms>}
  ```
  `performed` is set in the ctor as `gettimeofday() -> sec*1000 + usec/1000` plus the global server-clock
  offset (int64 at the global the ctor reads; see section 5). It is the server-time millisecond at which
  the player tapped "collect". It is printed with `%lld` as a bare number. These GAs go through
  `EntityToGaMapper::BasicGAQueue::insert` (F:2ffe82), so they may be sent delayed and batched.
  In "friend visit" mode the separate `friendsEntityCollectReward` action is used instead (not covered).
- **GA_EntityMove**, `entityMove`, ctor F:331c90 (x, z, Entity*), addToJson F:331d00:
  ```json
  "data": {"id":<int>, "x":<int>, "z":<int>, "transform":<0|1>}
  ```
- **GA_EntityPlaceToPatch**, `placeEntityInPatch`, ctor F:336724 (x, z, Entity*, patchId), addToJson F:33679c:
  ```json
  "data": {"id":<int plant entity id>, "patchId":<int patch entity id>}
  ```
  It is sent from `MapBuilder::moveEntity` (F:1b6e58 / 1b6ff8) when an existing placed plant is dragged
  onto a patch (MappedAction 0xe). The plant already has a server id. On success the client deletes the
  plant entity and adds it to the patch (see 2.4).
- **GA_SeedEntitySeed**, `seedEntitySeed`: `"data":{"prototypeId":"<seed proto>","x":..,"z":..,"transform":..}`.
  This is placing an `ET_SEED` item. The server answers with the concrete prototype that grows from it
  (see 2.3). Calling it a "random seed packet" is a guess from the response handling.
- **GA_EntityPlaceToInventory**, `placeEntitiesToInventory`, ctor F:7a01c8 (std::set<int>), addToJson F:79fec8:
  ```json
  "data": {"ids":[<int>, <int>, ...]}
  ```
  The ids are sorted ascending (std::set iteration). It is sent by `InventoryManager::saveEntitiesToInventory`
  (F:606a42).
- **GA_CollectAllFishes**, `collectAllFish`, ctor F:3071d0: no `data`.

### 1.4 Non-entity actions

- **GA_ExchangeMoney**, `exchangeMoney`, ctor(String) F:7a433c, addToJson F:7a43a0:
  `"data":{"exchangePackageId":"<string>"}`. The id of an exchange package from the exchange catalogue
  (`InAppShopManager::initExchangeContent`). It is sent from `DialogFlowExchange` / `DialogQuestionExchange`.
- **GA_SquirtCollect**, `collectSquirtTapReward`, ctor(int, proto::Reward) F:94e6b4, addToJson F:94e6f8:
  ```json
  "data": {"id":<int>, "reward":{"energy":<int>,"virtualMoney":<int>,"hardMoney":<int>,"lowTool":<int>,"highTool":<int>}}
  ```
  It is sent from `QuestGameSquirt::findKeys` (F:80e59e). `id` is the int passed by the minigame,
  probably the found key/treasure index (a guess). The reward amounts are **computed by the client**.
- **GA_DailyTapAction**, `dailyTapReward`, ctor F:93d7c0: no `data`. Sent from `DialogDailyReward::actionPerformed`.
- **GA_QuestStart**, `questStart`, ctor(int) F:7b673c, addToJson F:7b6768: `"data":{"id":<int>}`.
  `id` is `quest::Quest::getServerId()` (Quest+0x148, F:39f36c), the `id` from the startgame `quests` list.
- **GA_QuestTaskComplete**, `questTaskSetState`. The ctor is at F:7babb4, signature
  `(questId, tid, count, counter, TaskState, finished, QuestReward*, prototypeId, moves, difficulty, maxMoves, endTime)`.
  It is sent by `quest::Quest::saveTaskProgressToServer` (F:39fdc6). addToJson F:7bac58:
  ```json
  "data": {
    "id": <int quest server id>, "tid": <int task id>,
    "progress": {
      "counter": <int>, "state": <int TaskState>, "count": <int>,
      "prototypeId": "<string>"   // only if non-empty
      "moves": <int>              // only if != 0 (minigame)
      "difficulty": <int>         // only if != 0
      "maxMoves": <int>           // only if != 0
      "endTime": <int64 ms>       // only if != 0, printed with %lld
    },
    "reward": {"virtualMoney":..,"hardMoney":..,"xp":..,"energy":..,"lowTool":..,"highTool":..},  // only if a QuestReward* was given
    "finished": true|false
  }
  ```

---------------------------------------------------------------------------------------------------

## 2. Response side: what each reaction must contain

Envelope handling is in `netcl::ComManager::loadingFinished` (F:2e7d5c):
- It reads `reactions` and **`serverTime` with `get`, so `serverTime` is required** (F:2e7eb0).
- It computes the clock offset = serverTime - (sec*1000 + usec/1000), so serverTime is in ms (F:2e7ed2..2e7f30).
- `trySetServerId`.
- It matches reactions by `aid`.
- When a reaction's code is not 200 and it has `errorData`, it calls
  `EntityManager::processErrorOnEntity(errorData)` and `QuestManager::processErrorOnEntity` (see 2.8).

Then each action's `processResponse(reaction)` runs.

Two dispatch styles exist:

**(A) Entity actions.** The GA's processResponse just forwards the whole reaction to its listener
(GA+0x20), and for entity actions that listener is `netcl::ga::EntityToGaMapper::processResponse`
(F:2fe7f0 / G:30e7f0). That function:
1. Reads `resultCode` **with `get` (required, crash if missing)**.
2. Calls `EntityManager::confirmEntity(entity->id)`, which clears the "waiting to confirm" lock.
3. Branches on the action name. On success it usually takes `reaction.data` and calls the entity's
   virtual `processResponse(ga, data)` (vtable +0x34). For actions that reach it, **`data` is required**.
   For most failures it calls the entity's failure hook (vtable +0x38) or a rollback, often deletes or
   resets the entity, and shows `ComManager::showGameIssueDialog` with the action name and code.

**(B) Simple actions** (DailyTap F:93d700, SquirtCollect F:94e548, QuestStart, QuestTaskComplete, ExchangeMoney):
`processResult` reads `resultCode` if present. BasicGA::processResult (F:2fa020) returns true when the
key is absent. The QuestStart/QuestTaskComplete overrides (F:7b65c0 / F:7ba9c4) return **false** when it
is absent. When the result is 200 the whole reaction goes to the listener; otherwise there is a
"game issue" dialog.

Always send `resultCode: 200` for an accepted action.

### 2.1 entityConstruct / entitySeed / placeItemForCleaning - **server must return the new id**

EntityToGaMapper, F:2fea5a..2febf2. If the code is 200:
```
newId = reaction.data.id            // get + toInt  -> REQUIRED (missing => crash)
e = EntityManager::confirmEntityInserting(tempId, newId)    // F:27ca2c
```
`confirmEntityInserting` finds the entity under the client temporary id, removes it from the scene,
erases it from the id map, calls `Entity::setId(newId)`, re-inserts it as `map[newId]`, renames it
`myEntity<newId>` and re-adds it to the scene. If tempId is not found it returns NULL and nothing else
happens. Then `e->processResponse(ga, data)` runs.

Per entity class (section 3 has the restore formats):

- **EntityNormalDecoration** (F:6fc400), on `entityConstruct`: reads `data.id` again (required) and calls
  `Constructable::processResponseConstruct(data)`, so it needs
  `data.constructionInterval = {"start":ms,"finish":ms}`. It then enters client state 1. If start/finish
  are missing, `safeGet` throws.
- **EntitySpecHouse** (F:70ad2c), on `entityConstruct`: reads `data.id` and calls
  `processResponseConstruct(data)`, which needs `constructionInterval`. It then enters client state 0.
- **EntityPatch** (F:26371c), on `entityConstruct`: reads `data.id` and enters client state 1 (empty patch).
  It does not read an interval.
- **EntityCoral / EntityLivingPlant / EntityOrnPlant**, on `entitySeed` (F:6ef310, F:6f5f92, F:703904):
  read `data.id` (required) and `data.seeded` (**required**, int64 ms seed time), which is stored at
  Entity+0x158. No timers start; the plant waits for the first `entityFeed`.
- Cleaning/bubble items: `EntityCleanItem` / `EntityBubbleItem` use the base `Entity::processResponse`
  (no-op), so only `data.id` is needed.

Minimum valid reaction for a construct:
`{"aid":N,"resultCode":200,"data":{"id":123,"constructionInterval":{"start":T0,"finish":T1}}}`.
For a seed it is `{"aid":N,"resultCode":200,"data":{"id":124,"seeded":T0}}`.

If the code is not 200 (F:2fef74 path): for one entity type the client calls the entity's
vfunc +0x38(ga, code), then `EntityManager::deleteEntity(tempId)` (the placed object disappears) and
shows the game-issue dialog. Analytics `logBuyPlant` uses the client-side price, so the server
should deduct the same cost.

### 2.2 entityMove

At F:2ff030. On 200, `PatternSystem::entityMoved` runs and no `data` is read. On failure the entity is
put back at `MapBuilder::getEntityLastPosition` and the game-issue dialog is shown. The server should
store the new `x`, `z` and `transform`.

### 2.3 seedEntitySeed

At F:2febf4..2fed90. On 200:
```
d = reaction.data
newId   = d.id          (required, int)
d.seeded               (required, read with toLong, value unused)
newProto = d.prototypeId (required, string)
```
The client then deletes the seed entity, takes `PrototypeManager::getServerPrototype(newProto)` and calls
`insertEntityOnTile(newProto, sameTile, newId, false, true, seedPrototype)`. It copies the mirror flag
and logs analytics. The server decides which plant grows from the seed and must persist it as a new
entity with `seedPrototypeId` = the seed's prototype (see 3.1). On failure the seed entity is deleted and
the dialog is shown.

### 2.4 placeEntityInPatch

At F:2fee48..2fef64. On 200:
```
d = reaction.data
full       = d.full        (required, toBool)
plantCount = d.plantCount  (required, read as number)
patch = getEntityById(GA.patchId)
patch.setPlantCount(plantCount)
if !full: patch.insertPlantToPatch(plant.prototypeId)
else:     patch.processResponse(ga, d)          // EntityPatch: if d has "producingInterval" -> start production
          patch.insertUpgradedPlantToPatch(plant.prototypeId)
```
Then the plant entity is removed (`PatternSystem::entityRemoved`, `EntityManager::deleteEntity`).
Server rule: delete the plant entity, increment the patch's `plantCount`, and set its
`plantPrototypeId`. When `plantCount` reaches the patch maximum, return `full:true` and
`producingInterval:{start,finish}`. The patch then becomes a producing "upgraded" patch.
On failure the plant goes back to its last position and the dialog is shown.

### 2.5 Growth: entityFeed / entitySpeedupFeed / entityFreeSpeedupFeed

On 200 the mapper calls `entity->processResponse(ga, data)` (F:2ff222, 2ff1b6, 2ff3c4).
Coral, LivingPlant and OrnPlant then call `Growable::processResponseGrow(data)` (F:713384) and enter
client state 2. It reads:
```
growingCycle    : int    (required)  current growth cycle number, 1-based (showDrawableSeedPhase(cycle-1))
growingInterval : {"start":ms,"finish":ms}  (required, safeGet)
producingInterval : {"start":ms,"finish":ms} (optional, hasKey) -> Harvestable::processResponseProduction
```
`Growable::grow(cycle, start, finish)` starts the client timer. For a speed-up the server should return an
interval that has already ended (finish <= now), or the next cycle. This is inferred from the shared code
path, not from separate logic. `producingInterval` is expected when growth completes and production starts.
That is a guess based on the optional key.

### 2.6 Production: entityCollectReward / entitySpeedupProduction / entityFreeSpeedupProduction

The mapper takes `data` and calls `entity->processResponse` (F:2ff510, 2ff3fa, 2ff5b4).
- Coral and LivingPlant (F:6ef1fc, F:6f5e74) on collect call `Harvestable::processResponseCollect(data)`
  (F:27316c). On a speed-up they call `processResponseProduction(data)` (F:273204). Both read
  **`producingInterval` = {"start":ms,"finish":ms}, which is required**, and set client state 3
  (producing). For a collect this is the *next* production cycle. For a speed-up it should have
  already ended.
- EntityPatch (F:26371c): collect calls `processResponseCollect` and enters state 2. Speed-ups call
  `processResponseProduction` and enter state 3.
- EntityFish (F:2a175c): for `entityCollectReward` / `collectAllFish` it sets producable state 0
  (idle/hungry) and reads nothing.

Rewards (sand dollars, xp and so on) are computed and credited **client-side** from the prototype.
No reaction key for new balances is read in these paths. The server must apply the same arithmetic to
stay consistent (see section 4).

### 2.7 Other actions

- **entityConstructionSpeedup / entityConstructionFreeSpeedup**: `entity->processResponse(data)`.
  EntitySpecHouse calls `processResponseConstruct(data)`, which needs `constructionInterval{start,finish}`.
  Return finish <= now so construction completes, then enters state 0.
  EntityNormalDecoration ignores these, but `data` is still fetched (send `{}`).
- **entityRefund** (F:2ff5ea): on 200 the client deletes the entity (`PatternSystem::entityRemoved`,
  `deleteEntity`). For patches it uses `EntityPatch::getRefundReward()` (client-side). No `data` keys.
- **fishFeed** (F:2ff79a): `EntityFish::processResponse` calls `ProducableFish::processResponseFeed(data)`
  (F:71aa70), which needs **`producingInterval{start,finish}`** and sets producable state 1.
- **collectAllFish** (inline, F:2fe960..2fea5a): on 200
  ```
  d = reaction.data (required)
  d.fishes : array of int fish entity ids (null-checked)
  d.reward : object (required, read via JSONObject::getInt) with "hardMoney" (getInt, default 0; analytics only)
  ```
  For each fish id, `EntityFish::processResponse(ga, d)` sets the fish to state 0.
- **placeEntitiesToInventory** (`InventoryManager::processResponse` F:606aa8): **`data` is required**.
  `data.failedEntities` is an optional int array; if present and non-empty, those ids are not moved and
  an error dialog is shown. Server: mark the listed ids as `inventory:true` and keep them (see 3.1).
- **exchangeMoney** (`DialogFlowExchange::processResponse` F:46955c): it only checks `resultCode == 200`
  and closes the dialog. The currency change is applied client-side.
- **dailyTapReward** (`DialogDailyReward::processResponse` F:8b2518): no reaction keys read.
- **collectSquirtTapReward**: listener only on 200. No keys.
- **questStart** (`quest::Quest::processResponse` F:39f3d4): checks `resultCode == 200` and calls `QuestManager::runQuest`.
- **questTaskSetState** (same function, F:39f640): on 200 it reads `reaction.data.questFinished`,
  **which is required (safeGet, bool)**. If true, it calls `QuestManager::finishQuest`.

### 2.8 Error resync (optional)

When a reaction's code is not 200, it may carry `errorData`. `EntityManager::processErrorOnEntity`
(F:27d3a0) reads `errorData.corals`, `houses`, `decorations`, `livingPlants`, `ornamentalPlants`,
`fishes` and `rarePlants`. All 7 are read with `get` + `count`, so send all of them (empty arrays are
fine). For each entry, `syncEntityFromErrorData` (F:27b54c) reads `id` and an optional
`position{x,z,transform}` and moves the entity back. Simplest server policy: never send `errorData`.

---------------------------------------------------------------------------------------------------

## 3. Startgame world: per-entity JSON

`World::readEntities` (F:18f4e0 / G:19f4e0) reads these keys from the world object:
`corals`, `houses`, `decorations`, `livingPlants`, `ornamentalPlants`, `fishes`, `quests`, `rarePlants`,
`patches`, and optional `sectors`. A missing list counts as empty (null-checked).
Processing order: corals, livingPlants, ornamentalPlants, houses, decorations, rarePlants, fishes,
quests (`QuestManager::loadQuests`), then patches. `sectors` goes to `MapUnlockerBase::load`.

**The list name does not decide the class.** Every entity entry goes through
`EntityManager::insertEntityOnTileFromServer` (F:27c5cc / G:28c5cc), and the class comes from the
prototype's type through `EntityFactory`. Put each entity in the list matching its prototype category
anyway: the error-resync code and possibly the server expect it.

| list | prototype type | client class |
|---|---|---|
| corals | ET_CORAL | EntityCoral |
| livingPlants | ET_LIVING_PLANT | EntityLivingPlant |
| ornamentalPlants | ET_ORN_PLANT | EntityOrnPlant |
| houses | ET_SPEC_HOUSE | EntitySpecHouse |
| decorations | ET_NORMAL_DECORATION | EntityNormalDecoration |
| rarePlants | ET_RARE_PLANT | (guess: coral-like) |
| fishes | ET_CHARACTER (fish) | EntityFish |
| patches | ET_PATCH | EntityPatch |

### 3.1 Common keys (insertEntityOnTileFromServer)

| key | type | req? | meaning |
|---|---|---|---|
| `id` | int | **required** | entity id, used as-is (no generator) |
| `prototypeId` | string | **required** | server prototype id |
| `seedPrototypeId` | string | optional | prototype of the seed it grew from. Passed as the last arg of insertEntityOnTile |
| `patchPrototypeId` | string | optional | if present the entity is created **with the patch prototype**, and Entity+0xdc = patch proto, Entity+0xd4 = main proto (plant-in-patch variant) |
| `position` | object | optional | `{"x":int,"z":int,"transform":int}`. x, z = tile, truncated to int16. transform bit0 = mirror. If absent the entity goes to tile (0,0) with no transform |
| `inventory` | bool | optional | if true, sets Entity+0xf1 and calls `InventoryManager::addEntityToInvetory(e,true)` (entity is in inventory, not on the map) |

After creation it calls `entity->restoreStateFromServer(entry)` (vtable +0x30) with the same object.

### 3.2 Per-class `restoreStateFromServer`

`state` is an int server-state code. The values below are the only ones each class reacts to; any other
value leaves the fresh default (initial) state. Names in quotes are inferred from behaviour.

**EntityCoral** (F:6eeab8) and **EntityLivingPlant** (F:6f586c):
- `state` (int, **required**) and `seeded` (int64 ms, **required**), stored at Entity+0x158.
- `3` = "growing" (timer running): `Growable::processResponseGrow(entry)` needs
  `growingCycle`, `growingInterval{start,finish}` and optionally `producingInterval`. Client state 2.
- `5` = "waiting for feed": `restoreForGrowingStateFromServer` (F:7134f4) reads optional `growingCycle`
  (int, default 0) and shows that growth phase with no timer.
- `6` = "producing": set as grown, then `Harvestable::processResponseCollect(entry)` needs
  `producingInterval{start,finish}`, then `startProduction`. Client state 3.
- `7` = "production ready": set as grown, client state 4. LivingPlant also shows the collect icon.

**EntityOrnPlant** (F:7033e0):
- `state` and `seeded` (both required).
- `3` growing (as above), `5` waiting for feed (as above), `1` = fully grown (client state 3).
- Ornamental plants do not produce.

**EntityNormalDecoration** (F:6fc6cc) and **EntitySpecHouse** (F:70ae3c):
- `state` (int, required).
- `0` = under construction: `Constructable::processResponseConstruct(entry)` (F:6e2038) needs
  `constructionInterval{start,finish}`.
- `1` = built.
- Any other value hits an assertion ("Assertion failed" log, nothing else).

**EntityPatch** (F:264874):
- `state` (int, required), `plantCount` (int, optional, default 0), `plantPrototypeId` (string, optional).
- If `0 < plantCount < plantMax` it calls `insertPlantToPatch(plantPrototypeId)`. If
  `plantCount == plantMax` it calls `insertUpgradedPlantToPatch`. plantMax comes from `EntityPatch::getPlantMax`.
- `1` = idle (client state 1), `6` = producing (needs `producingInterval`, client state 2),
  `7` = ready to collect (client state 3).

**EntityFish** (F:2a1c00):
- `state` (int, optional) is stored at Entity+0x280.
- Only for rare fish (`EntityFish::isRare`) in own-reef mode (`CU::getGameMode()==0`):
  - `1` = idle/hungry (producable state 0).
  - `6` = producing: `ProducableFish::processResponseFeed(entry)` needs `producingInterval`.
  - `7` = ready (producable state 2).
- Other fish (special/ambient) need only `id`, `prototypeId` and `position`.

**EntityCleanItem / EntityBubbleItem** (F:2cafac / F:2c5bf0): no keys. They only increment the
cleaning-item counters. EntityCharacter, EntityCollectible, EntityColor, EntitySector and the base Entity: no keys.

Interval object everywhere: `{"start": <int64 ms>, "finish": <int64 ms>}`, read with `safeGet` + `toLong`
(helper F:272778).

### 3.3 Example entries

```json
{"id":5,"prototypeId":"<coral proto>","position":{"x":12,"z":7,"transform":0},
 "state":6,"seeded":1700000000000,"growingCycle":3,
 "producingInterval":{"start":1700000300000,"finish":1700003900000}}
{"id":9,"prototypeId":"<house proto>","position":{"x":3,"z":4,"transform":1},
 "state":0,"constructionInterval":{"start":1700000000000,"finish":1700000600000}}
{"id":11,"prototypeId":"<patch proto>","position":{"x":20,"z":5,"transform":0},
 "state":1,"plantCount":2,"plantPrototypeId":"<plant proto>"}
{"id":30,"prototypeId":"<rare fish proto>","position":{"x":8,"z":8,"transform":0},
 "state":6,"producingInterval":{"start":1700000000000,"finish":1700001800000}}
```

### 3.4 Quests list entry (QuestManager::loadQuests F:3ab344)

- `prototypeId` (string, safeGet, required). It must match a quest prototype from the world definition.
- `id` (int, safeGet, required). This is the quest server id that questStart/questTaskSetState send back.
- `tasks` (array, passed to `QuestManager::loadTasks` F:3a8e54). Each task: `tid`, `count`, `counter`,
  `prototypeId`, `finished` (safeGet), `state`, optional `difficulty`, `maxMoves`, `endTime`.
- `state` (int quest state; 8 and 9 are special-cased).
- optional `hintPurchased` (bool) and `hintPurchasedIndex` (int).

The task-level details were only skimmed; check them before relying on them.

### 3.5 Status object

`data::UserStatus::loadUserStatus` (G:243f9c) reads `hardMoney`, `virtualMoney`, `energy`, `level`, `xp`,
`xpForNextLevel`, `lowTool`, `highTool`, `vitality`, `moneySpent`, `tapjoyMoneySpent`,
`friendCollectCount`, `friendCollectMaxCount`, `friendCollectInterval{start,finish}`,
`tapRewardsCount`, `tapRewardsExtraTapAvail`, `tapRewardsGetAllAvail`, `dailyTapRewardReady`,
`currentDailyRewardCountOffer`, `lastDailyRewardCountClaimed`, `lastSquirt`, `squirtStarted`,
`activeDiscount` and `resumeGame`. Keys come from calls.txt; whether each is required was not checked.

---------------------------------------------------------------------------------------------------

## 4. Rules for a consistent server

1. **The server allocates entity ids.** Placement actions do not send an id. The reaction must
   contain `data.id`, and the client re-keys the entity from its temporary id
   (`confirmEntityInserting` F:27ca2c).
   - Client temporary ids come from `EntityIdGenerator` (F:7269e4): a free-list first, otherwise a
     counter that **starts at 1,000,000** (0xf4240, ctor F:7269cc).
   - Build-preview ids come from `EntityManager::getTemporaryId` (F:27b3e8), a counter starting at
     0x3b9acbf4 (≈1.0e9).
   - `confirmEntityInserting` does a plain `map[newId] = e`, so a server id that collides with a live
     temp id overwrites it. **Allocate server ids in 1..999,999**, unique per user and never reused.
   - Ids from the world (`id` in startgame) are used verbatim.
2. Entity "lock": after sending certain actions the client calls `setEntityAsWaitingToConfirm(id)`
   (F:27cc38). That sets deadline = now + WorldSettings[+0x2a0]*1000 ms, and further actions on that
   entity are blocked until a reaction arrives (`confirmEntity`) or the deadline passes. Always answer
   every `aid`.
3. **Times are milliseconds** since the Unix epoch, as int64. The client keeps
   `offset = serverTime - localNowMs` (F:2e7f26) and uses `localNowMs + offset` for all progress bars
   (`Constructable/Growable/Harvestable::getProgress` call gettimeofday then `/1000`) and for
   `entityCollectReward.performed`. `serverTime` must be present in every batch response.
4. The client is authoritative for economy amounts in this protocol. Costs (build, feed, speed-up,
   exchange) and rewards (collect, refund, squirt, quest task) are applied locally from prototype data.
   Reactions carry only timers and ids. To keep `status` correct at the next startgame, the server must
   apply the same prototype-based arithmetic per action. The alternative is to accept client values
   where they are sent (`reward` blocks in squirt and quest actions). Exceptions where the server
   decides something: the new entity id, the seed result prototype (`seedEntitySeed`),
   the patch `full`/`plantCount`, and all intervals.
5. Server-side state machine to persist per entity (codes as read by the client):
   - Constructables: `state 0` with constructionInterval. Once `finish <= now` the server may report
     `state 1` (built). A construction speed-up sets finish = now.
   - Growables (coral, living plant, ornamental plant):
     - After `entitySeed`: `seeded = now` and initial state. The client does nothing special; send
       `state 5`, `growingCycle 0` (a guess, since no explicit "just seeded" code exists).
     - Each `entityFeed`: `growingCycle += 1`, `growingInterval = [now, now + growingTime]`, `state 3`.
       When the interval ends with cycles remaining, report `state 5` (waiting for feed).
     - After the last cycle (prototype `getGrowingCycles`): ornamental becomes `state 1`. Coral and
       living plant become `state 6` with `producingInterval = [growFinish, growFinish + productionTime]`,
       then `state 7` when it ends.
     - `entityCollectReward`: new `producingInterval` starting at `performed` (or now), `state 6`.
     - Speed-ups end the current interval at now.
   - Patches: `state 1` while filling. `placeEntityInPatch` increments plantCount. At max:
     `state 6` + producingInterval, then `7`, then collect returns to `6`.
   - Rare fish: `fishFeed` gives `state 6` + producingInterval, then `7` when it ends.
     Collect (single or `collectAllFish`) gives `state 1`.
   - `entityMove` updates `position`. `entityRefund` deletes the entity. `placeEntitiesToInventory`
     sets `inventory:true` (keep the entity; its position is irrelevant). Placing from inventory goes
     through the normal place path again and gets a fresh id. That last point is a guess: it was not
     traced.
6. Every reaction for an EntityToGaMapper action must include `resultCode` (crash otherwise).
   For actions listed in section 2 as reading `data`, include `data` with the required keys.
   `data:{}` is safe for the others.

---------------------------------------------------------------------------------------------------

## 5. Quick reference: action -> required reaction `data`

| action | request `data` | reaction `data` (200) |
|---|---|---|
| entityConstruct | prototypeId,x,z,transform,early | **id**. Decoration/house: **constructionInterval**. Patch: none extra |
| entitySeed | prototypeId,x,z,transform,early | **id**, **seeded** |
| placeItemForCleaning | prototypeId,x,z,transform,early | **id** |
| seedEntitySeed | prototypeId,x,z,transform | **id**, **seeded**, **prototypeId** (resulting plant) |
| entityMove | id,x,z,transform | none |
| placeEntityInPatch | id,patchId | **full**, **plantCount**; if full: producingInterval |
| entityCollectReward | id,performed | **producingInterval** (coral/living/patch). Fish: none (`data` still fetched) |
| entityFeed / entitySpeedupFeed / entityFreeSpeedupFeed | id | **growingCycle**, **growingInterval**, opt producingInterval |
| entitySpeedupProduction / entityFreeSpeedupProduction | id | **producingInterval** |
| entityConstructionSpeedup / entityConstructionFreeSpeedup | id | house: **constructionInterval**. Decoration: `{}` |
| entityRefund | id | none |
| fishFeed | id | **producingInterval** |
| collectAllFish | (no data) | **fishes** [ids], **reward** {hardMoney} |
| placeEntitiesToInventory | ids[] | `{}` or {failedEntities:[...]} (`data` required) |
| exchangeMoney | exchangePackageId | none |
| collectSquirtTapReward | id, reward{...} | none |
| dailyTapReward | (no data) | none |
| questStart | id | none |
| questTaskSetState | id,tid,progress{...},reward?,finished | **questFinished** (bool) |

Bold = read without a presence check, so a missing key crashes or throws.
