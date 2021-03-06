import os, json
import requests
import config, globals

#needed to remove the accent in 'Pokemon'
import unicodedata

from lxml import html
from globals import Card, specmana, mtgreprints

def download_scan(name, expansion):
    expansion = expansion.lower()
    if expansion == 'mps':
        # This is the only place I know where mtgjson and magiccards.info differ on set codes. 
        expansion = 'mpskld'

    name2 = ''.join(e for e in name if e.isalnum())
    localname = name2+'_'+expansion+'.jpg'
    lookupScan = os.path.join(globals.SCAN_PATH, localname)
    if os.path.exists(lookupScan):
        return lookupScan

    scanweb = 'http://www.magiccards.info/{set}/en.html'.format(set=expansion)
    scanpage = requests.get(scanweb)
    scantree = html.fromstring(scanpage.content)

    if name.find('/') != -1:
        name = name.split('/')[0]+' ('+name+')'

    scannumber = scantree.xpath('//a[text()="{name}"]/@href'.format(name=name))
    print(scannumber)
    cardloc = None
    for item in scannumber:
        if item.find("/en/"):
#            cardloc = scannumber[0][:-4].split("/")
            cardloc = item[:-4].split("/")
    if cardloc is None:
        print('WARNING - Could not find {0} ({1})'.format(name, expansion))
        return None
    else:
        # print(cardloc)
        pass

    expansion = cardloc[1]
    number = cardloc[3].strip('.')
    url = 'http://magiccards.info/scans/en/'+expansion+'/'+number+'.jpg'
    store(url, number+'.jpg')
    os.rename(number + '.jpg', lookupScan)

    return lookupScan

def download_scanPKMN(name, expansion, expID):
    name = unaccent(name[:-1].decode('latin-1'))
    displayname = name
    name = name.replace(' ', '-').replace("'", '')

    localname = 'PKMN-{name}-{expansion}-{expID}.jpg'.format(name=name, expansion=expansion, expID=expID)

    lookupScan = os.path.join(globals.SCAN_PATH, localname)

    if os.path.exists(lookupScan):
        return lookupScan, displayname

    pokeurl = 'https://s3.amazonaws.com/pokegoldfish/images/gf/{name}-{expansion}-{expID}.jpg'.format(name=name, expansion=expansion, expID=expID)
    print(pokeurl)
    store(pokeurl, localname)
    os.rename(localname, lookupScan)

    return lookupScan, displayname

def download_scanHexCM(mainguy, mainguyscan, typeCM):
    mainguy2 = ''.join(e for e in mainguy if e.isalnum())
    localname = 'HexTCG-'+mainguy2+'_'+typeCM+'.jpg'
    lookupScan = os.path.join(globals.SCAN_PATH, localname)

    if os.path.exists(lookupScan):
        return lookupScan

    if mainguyscan == 'cardback-big':
        url = 'https://hex.tcgbrowser.com/images/cards/'+mainguyscan+'.jpg'
    else:
        url = 'https://storage.hex.tcgbrowser.com/big/'+mainguyscan+'.jpg'
        #card scans are labeled via set number -> need to rename the file temporarily to avoid potential overwriting until decklist is finalized
    store(url, localname)
    os.rename(localname, lookupScan)

    return lookupScan

def download_scanHex(name, namescan):
    name2 = ''.join(e for e in name if e.isalnum())
    localname = 'HexTCG-'+name2+'.jpg'
    lookupScan = os.path.join(globals.SCAN_PATH, localname)

    if os.path.exists(lookupScan):
        return lookupScan

    url = 'https://storage.hex.tcgbrowser.com/big/'+namescan+'.jpg'
    #card scans are labeled via set number -> need to rename the file temporarily to avoid potential overwriting until decklist is finalized
    store(url, localname)
    os.rename(localname, lookupScan)

    return lookupScan

def get_card_info(line, quantity=None):
    # Tappedout puts tabs instead of spaces.
    # Easiest solution is to just sub them for spaces.
    line = line.replace('\t', ' ')

    ncount_card = 0
    isitland = False
    scan_part1 = None
    #flag for split cards
    splitcost = False
    n_cost = 0
    altcmc_list = []

    if quantity is None:
        data = line.split(" ", 1)
        quantity = int(data[0])
        line = data[1]

    if line.find(' / ') != -1:
        data = line.split(" / ")
        #for non-XML files, we need to check if this is a split card
        if len(data) > 2:
            name = data[0] + ' // ' + data[1]
            expansion = data[2].split("\n")[0].lower()
        else:
            #split the info at the first blank space
            name = data[0]
            expansion = data[1].split("\n")[0].lower()
    else:
        #split the info at the first blank space
        name = line.strip()
        expansion = config.Get('cards', name.lower())

    print('Looking up {0} ({1})'.format(name, expansion))
    if quantity == 0:
        return None

    if name.lower() in ["plains", "island", "swamp", "mountain", "forest"]:
        isitland = True

    if not isitland:

        expansion, manacost, typeline, number = get_json(name, expansion)

        if typeline.find("Land") != -1:
            manacost = '*'
        elif manacost is None:
            # Lotus Bloom, Evermind, and other costless cards.
            manacost = '**'
        else:
            costs = manacost.split(' // ')
            manacost = ''
            for cost in costs:
                cost = cost[1:-1]
                cost = cost.split("}{")
                cost = [specmana[x] for x in cost]
                cost = ''.join(cost)
                if manacost == '':
                    manacost = cost
                else:
                    manacost = manacost + '/' + cost

        print((name, expansion, manacost))

    else:

        #all basic lands will be using Unhinged card art
        if expansion is None:
            expansion = "uh"
        number = None
        manacost = "*"
    return Card(name, expansion, manacost, quantity, collector_num=number)

def get_json(cardname, expansion):
    fullname = cardname
    if ' // ' in cardname:
        splitcard = True
        cardname, altname = cardname.split(' // ')
        fullname = '{0}/{1}'.format(cardname, altname)
    else:
        splitcard = False

    js = requests.get('http://api.magicthegathering.io/v1/cards?name="{cardname}"'.format(cardname=cardname))
    blob = json.loads(js.text)
    card = blob['cards'][0]
    mana_cost = card.get('manaCost', None)
    typeline = card['type']
    printings = card['printings']
    number = card.get('number', None)
    if not str(expansion).upper() in printings:
        #grabbing the last item relies on MCI having those scans already
        for printing in printings:
            if download_scan(fullname, printing) is not None:
                expansion = printing
                break

    if splitcard:
        js = requests.get('http://api.magicthegathering.io/v1/cards?name="{cardname}"'.format(cardname=altname))
        blob = json.loads(js.text)
        card = blob['cards'][0]
        mana_cost = mana_cost + ' // ' + card.get('manaCost', None)
    # print((cardname, expansion, mana_cost, typeline))
    return expansion, mana_cost, typeline, number

def unaccent(text):
    text =  ''.join((c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn'))
    text = text.encode('ASCII', 'ignore').replace('PokAmon','Pokemon')
    return text

def store(url, filename):
    r = requests.get(url, stream=True)
    with open(filename, 'wb') as f:
        for chunk in r.iter_content(1024):
            f.write(chunk)
