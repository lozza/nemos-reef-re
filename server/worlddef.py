"""Builds a world definition ("worldDef") for the client from the prototypes bundled in the APK.

The original server sent the whole game economy (prices, timers, levels, quests, ...) in this
document. Only the prototype list (ids, types, graphics) can be recovered from the APK; every
number below is a placeholder chosen to make the game playable until better data turns up.

The client throws on missing keys (sdr::JSONObject::safeGet), so every prototype carries every
field any getter may read, with neutral defaults.
"""
import hashlib
import json
import zipfile

from ipro import read_attributes


# .ipro "type" -> worldDef list the client loads it from (proto::PrototypeAttrib::loadPrototypePrimaryData)
LIST_FOR_TYPE = {
    'ET_CORAL': 'coralPrototypeList',
    'ET_LIVING_PLANT': 'livingPlantPrototypeList',
    'ET_ORN_PLANT': 'ornamentalPlantPrototypeList',
    'ET_RARE_PLANT': 'rarePlantPrototypeList',
    'ET_NORMAL_DECORATION': 'decorationPrototypeList',
    'ET_SPEC_HOUSE': 'housePrototypeList',
    'ET_SEED': 'seedPrototypeList',
    'ET_PATCH': 'patchList',
}

# .ipro "type" -> shop tab (ShopScreen::initShopCategories: CORAL, LIVINGPLANT, ORNAMENTALPLANT, RAREPLANT,
# SPECIAL). Decorations have no tab of their own; they are put with the ornamental plants for now.
SHOP_CATEGORY = {
    'ET_CORAL': 'CORAL',
    'ET_LIVING_PLANT': 'LIVINGPLANT',
    'ET_ORN_PLANT': 'ORNAMENTALPLANT',
    'ET_NORMAL_DECORATION': 'ORNAMENTALPLANT',
    'ET_RARE_PLANT': 'RAREPLANT',
    'ET_SPEC_HOUSE': 'SPECIAL',
}

# Tutorial/server-only prototype ids referenced by the client code.
EXTRA_PATCHES = ['patch_tutorial_01', 'patch_tutorial_02']


def cost(coins=0, pearls=0, algae=0, low_tool=0, high_tool=0):
    # proto::Cost::Cost reads exactly these five keys
    return {'energy': algae, 'virtualMoney': coins, 'hardMoney': pearls,
            'lowTool': low_tool, 'highTool': high_tool}


def reward(xp=0, coins=0, pearls=0, algae=0, low_tool=0, high_tool=0):
    r = cost(coins, pearls, algae, low_tool, high_tool)
    r['xp'] = xp
    return r


def duration(seconds):
    # proto::ServerPrototype::getTime: {"duration": int64, "timeWarp": int}
    return {'duration': seconds * 1000, 'timeWarp': 0}


def prototype(pid, graphical_id, name, etype, specific_type, order, level=1, price=None):
    price = price or cost(coins=100)
    return {
        'id': pid,
        'graphicalId': graphical_id,
        'name': name,
        'nameId': name,
        'descriptionId': '',
        'type': etype,
        'specificType': specific_type or '',
        'requiredLevel': level,
        'visibleAtLevel': level,
        'visibleMaxLevel': 999,
        'newUsersOnly': False,
        'guiOrder': order,
        'shopCategory': '',
        # ShopManager::isPrototypeVisibeInShop hides an item once you own maxInstancesCount of it
        'maxInstancesCount': 999,
        'maxPlants': 0,
        'cost': price,
        'constructionTime': duration(30),
        'speedupCost': cost(pearls=1),
        'growingTime': duration(60),
        'growingCycles': 3,
        'growingCycleCost': cost(coins=10),
        'producingTime': duration(300),
        'producingCost': cost(algae=1),
        'producingSpeedupCost': cost(pearls=1),
        'producedReward': reward(xp=5, coins=20),
        'rewardAfterBuilt': reward(xp=10),
        'refundReward': reward(coins=price.get('virtualMoney', 0) // 2),
        'friendReward': reward(xp=1, coins=5),
        'ownerReward': reward(coins=5),
        'vitality': 0,
        'supportedShops': ['GOOGLE', 'AMAZON', 'ITUNES'],
        'availableTimeInterval': {'start': 0, 'finish': 0},  # finish 0 = no time limit
    }


def shop_item(p):
    """ingameShopItems entry: ServerPrototype::getActiveShopData picks one by level (CriteriumLevel),
    then the shop reads price, time window and limits from it."""
    keys = ('cost', 'supportedShops', 'visibleAtLevel', 'visibleMaxLevel', 'availableTimeInterval',
            'newUsersOnly', 'maxInstancesCount', 'shopCategory', 'guiOrder', 'requiredLevel')
    item = {k: p[k] for k in keys}
    item['prototypeId'] = p['id']
    return item


def levels(count=60):
    out, xp = [], 0
    for lv in range(1, count + 1):
        out.append({
            'level': lv,
            'requiredXP': xp,
            'reward': reward(coins=100 * lv, pearls=1 if lv % 5 == 0 else 0, algae=5),
            'minChests': 1,
            'maxChests': 3,
            'squirtCost': cost(algae=5),
            'vitality': {'vitality': 100, 'categories': []},
        })
        xp += 50 * lv
    return out


def read_prototypes(apk_path):
    """Returns [(file stem, attributes)] for every assets/prototypes/*.ipro in the APK."""
    with zipfile.ZipFile(apk_path) as z:
        names = sorted(n for n in z.namelist() if n.startswith('assets/prototypes/') and n.endswith('.ipro'))
        return [(n.rsplit('/', 1)[1][:-5], read_attributes(z.read(n))) for n in names]


def build(apk_path, story=None):
    wd = {
        'version': '',  # filled in by finish()
        # Read with JSONObject::get (null when missing → crash) by World::getTextBundleId/getResourceBundleId.
        'localizedTextsBundleId': 1,
        'resourcesBundleId': 1,
        'globalSettings': {
            'minimalClientVersion': '1.0.0',
            'timeoutTap': 30,
            'timeoutGameAction': 30,
            'aliveMessageInterval': 60,
            'aliveMessageIntervalInactivity': 300,
            'inactivityTreshold': 300,
            'localTapAuthorizing': False,
            'DMOAnalyticLogLevel': 0,
            'GoogleAnalyticLogLevel': 0,
            'facebookAndroidURL': '', 'facebookAmazonURL': '', 'facebookWallPostURL': '',
            'gamePictureURL': '', 'URLiTunes': '', 'URLAndroid': '', 'URLAmazon': '',
            'burslyPregameInterstitalAndroid': False,
        },
        # World::loadWorldDefinition reads test/variant (strings), control (int), active (bool)
        'abTestSettings': {'test': '', 'variant': '', 'control': 0, 'active': False},
        'ambientFishPrototypeList': [],
        'fishPrototypeList': [],
        'ingameShopItems': [],
        'levelList': levels(),
        # Not reconstructed yet; empty lists keep the parsers happy.
        'sectorPrototypeList': [], 'dailyRewardPrototypeList': [], 'chestsList': [],
        'squirtMinigameList': [], 'newPrototypeList': [], 'discounts': [],
        'vitalityPatchList': [], 'conditionDefinitionList': [], 'questPrototypeList': [],
        'dialogPrototypeList': [], 'colorVariantList': [], 'patternList': [],
        'inAppPricePoints': [], 'hintPrototypeList': [], 'exchangePackagePrototypes': [],
        'cooperativeQuests': [], 'pushNotificationPrototypeList': [], 'whatsNewList': [],
    }
    for lst in LIST_FOR_TYPE.values():
        wd[lst] = []

    order = 0
    for stem, a in read_prototypes(apk_path):
        etype, st = a.get('type'), a.get('specificType', '')
        if etype == 'ET_CHARACTER':
            lst = 'ambientFishPrototypeList' if st == 'EST_FISH_AMBIENT' else 'fishPrototypeList'
        else:
            lst = LIST_FOR_TYPE.get(etype)
        if not lst:
            continue
        order += 1
        p = prototype(stem, stem, a.get('name') or stem, etype, st, order)
        p['shopCategory'] = SHOP_CATEGORY.get(etype, '')
        if etype == 'ET_PATCH':
            p['maxPlants'] = 3  # EntityPatch::getPlantMax: plants needed before the patch produces
        wd[lst].append(p)
        wd['ingameShopItems'].append(shop_item(p))

    patch = next((p for p in wd['patchList'] if p['graphicalId'] == 'spec_house_patch'), None)
    if patch:
        for pid in EXTRA_PATCHES:
            wd['patchList'].append(dict(patch, id=pid))
    if story:
        story.extend_worlddef(wd)
    return finish(wd)


def finish(wd):
    """Stamps a numeric version derived from the content, so clients refresh their cached copy
    whenever the definition changes. CU::canClientWorkWithWorldVersion parses major.minor.patch."""
    wd['version'] = ''
    digest = hashlib.sha1(json.dumps(wd, sort_keys=True).encode()).hexdigest()
    wd['version'] = '1.8.1.%d' % (int(digest[:7], 16))
    return wd


if __name__ == '__main__':
    import sys
    json.dump(build(sys.argv[1]), sys.stdout, indent=1)
