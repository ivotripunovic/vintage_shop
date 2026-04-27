"""
Shared seed data for seed_products and download_seed_images commands.
PRODUCTS and SUBCATEGORY_SEARCH are keyed by category SLUG (always unique).
"""

CONDITIONS = [
    {"name": "Novo",         "description": "Nekorišćeno, originalno pakovanje",                    "order": 1},
    {"name": "Kao novo",     "description": "Korišćeno jednom ili dvaput, bez vidljivih oštećenja",  "order": 2},
    {"name": "Dobro",        "description": "Vidljivi tragovi korišćenja, u potpunosti funkcionalno","order": 3},
    {"name": "Prihvatljivo", "description": "Značajni tragovi korišćenja, funkcionalno",             "order": 4},
]

SELLERS = [
    {"shop_name": "Staro i Zlato",   "location": "Beograd"},
    {"shop_name": "Kod Bake",        "location": "Novi Sad"},
    {"shop_name": "Retro Kabinet",   "location": "Niš"},
    {"shop_name": "Tavan Nalaz",     "location": "Subotica"},
    {"shop_name": "Vremenski Trag",  "location": "Kragujevac"},
    {"shop_name": "Stari Sat",       "location": "Beograd"},
    {"shop_name": "Nostalgia Bazar", "location": "Novi Sad"},
    {"shop_name": "Podrumska Blaga", "location": "Zemun"},
]

# Pexels search query per category slug
SUBCATEGORY_SEARCH = {
    # Moda
    "moda-garderoba-zenska":      "vintage women clothing dress",
    "moda-garderoba-muska":       "vintage men suit jacket",
    "moda-obuca":                 "vintage leather shoes boots",
    "moda-aksesoari-i-nakit":     "vintage jewelry accessories scarf",
    "moda-dizajnerski-komadi":    "designer vintage fashion luxury",
    # Kuća – Kuhinja & trpezarija
    "kuca-kuhinja-trpezarija-porcelan-i-keramika": "antique porcelain china dinnerware",
    "kuca-kuhinja-trpezarija-case-i-servisi":      "vintage crystal glasses tea set",
    "kuca-kuhinja-trpezarija-escajg":              "antique silver cutlery flatware",
    "kuca-kuhinja-trpezarija-kristal":             "crystal decanter glassware",
    # Kuća – Rasveta
    "kuca-rasveta-stone-lampe":         "vintage desk lamp brass",
    "kuca-rasveta-lusteri":             "antique chandelier crystal",
    "kuca-rasveta-industrijska-rasveta":"industrial vintage lamp",
    "kuca-rasveta-retro-lampe":         "retro floor lamp vintage",
    # Kuća – Nameštaj
    "kuca-namestaj-stolice-fotelje":           "vintage armchair upholstered",
    "kuca-namestaj-stolovi-i-komode":          "antique wooden dresser table",
    "kuca-namestaj-ormari-i-vitrine":          "antique wardrobe cabinet",
    "kuca-namestaj-retro-mid-century-komadi":  "mid century modern furniture",
    # Antikviteti
    "antikviteti-namestaj":    "antique furniture ornate wood",
    "antikviteti-dekoracija":  "antique decorative objects ornaments",
    # Umetnost
    "umetnost-slike-i-crtezi":    "oil painting vintage artwork",
    "umetnost-skulpture":         "antique bronze sculpture",
    "umetnost-fotografija":       "vintage black white photograph framed",
    "umetnost-rucni-radovi":      "handmade embroidery textile art",
    "umetnost-printovi-i-plakati":"vintage poster print art",
    # Tehnika i elektronika
    "tehnika-i-elektronika-mobilni-telefoni":   "retro mobile phone vintage nokia",
    "tehnika-i-elektronika-racunari-i-oprema":  "vintage computer retro technology",
    "tehnika-i-elektronika-tv-i-audio":         "vintage record player turntable",
    "tehnika-i-elektronika-foto-i-video-oprema":"vintage film camera",
    "tehnika-i-elektronika-kucni-aparati":      "vintage kitchen appliance retro",
    "tehnika-i-elektronika-gaming":             "retro gaming console vintage",
    # Kolekcionarski predmeti
    "kolekcionarski-predmeti-stari-novac":  "old coins numismatics collection",
    "kolekcionarski-predmeti-znacke":       "vintage badges pins collection",
    "kolekcionarski-predmeti-razglednice":  "vintage postcards collection",
    "kolekcionarski-predmeti-stare-knjige": "old books antique library",
    "kolekcionarski-predmeti-satovi":       "vintage mechanical watch",
    # Sport i slobodno vreme
    "sport-i-slobodno-vreme-bicikli":      "vintage bicycle retro",
    "sport-i-slobodno-vreme-fitnes-oprema":"vintage fitness equipment gym",
    "sport-i-slobodno-vreme-kamp-oprema":  "vintage camping equipment outdoor",
    "sport-i-slobodno-vreme-instrumenti":  "vintage musical instrument guitar",
    "sport-i-slobodno-vreme-hobiji":       "vintage hobby craft collection",
}

# Products keyed by category SLUG for unambiguous lookup
PRODUCTS = {
    # ── Moda ─────────────────────────────────────────────────────────────────
    "moda-garderoba-zenska": [
        {"title": "Vintage haljina, floral print, vel. 38", "price": 8500,  "description": "Pamučna haljina sa cvetnim motivom, 1960-ih, odlično stanje."},
        {"title": "Kožna jakna ženska, smeđa, vel. M",      "price": 16000, "description": "Prava koža, 1980-ih, bez oštećenja."},
        {"title": "Vuneni kaput, krem boja, vel. 40",        "price": 13500, "description": "100% vuna, klasičan kroj, minimalni tragovi nošenja."},
    ],
    "moda-garderoba-muska": [
        {"title": "Odelo, sivo karirano, vel. 50",           "price": 22000, "description": "Vuneno odelo, karirani uzorak, 1970-ih, komplet sako + pantalone."},
        {"title": "Kožna jakna muška, crna, vel. L",         "price": 18000, "description": "Prava koža, biker stil, 1990-ih, solidno stanje."},
        {"title": "Flanelska košulja, vel. XL",              "price": 4500,  "description": "Pamučna flanela, lumberjack uzorak, kao nova."},
    ],
    "moda-obuca": [
        {"title": "Kožne cipele muške, br. 43",              "price": 8500,  "description": "Engleska izrada, ručno šivene, malo nošene."},
        {"title": "Vintage štikle, crvene, br. 38",          "price": 5500,  "description": "Klasične crvene štikle, visina 7 cm."},
        {"title": "Čizme do kolena, kožne, br. 39",          "price": 11000, "description": "Kozija koža, tamno smeđe, odlično stanje."},
    ],
    "moda-aksesoari-i-nakit": [
        {"title": "Svileni šal, 90×90 cm",                   "price": 7000,  "description": "Svileni šal, živopisne boje, bez oštećenja."},
        {"title": "Biserna ogrlica, klasična",               "price": 12000, "description": "Biserna ogrlica sa zlatnom kopčom, dužina 45 cm."},
        {"title": "Zlatni prsten, 14k",                      "price": 28000, "description": "Zlatni prsten 14k sa sitnim dijamantom, nošen."},
    ],
    "moda-dizajnerski-komadi": [
        {"title": "Dizajnerska tašna, konjak koža",          "price": 35000, "description": "Prava koža, zlatne kopče, malo nošena, luksuzni komad."},
        {"title": "Vintage smoking, vel. 52",                "price": 28000, "description": "Klasični crni smoking, 1980-ih, odlično sačuvan."},
    ],
    # ── Kuća / Kuhinja & trpezarija ──────────────────────────────────────────
    "kuca-kuhinja-trpezarija-porcelan-i-keramika": [
        {"title": "Meisenski porcelan, servis za 6",         "price": 32000, "description": "Komplet servis, 12 komada, zlatni ivičnjaci, besprekoran."},
        {"title": "Keramička tegla, folk motivi, Zlakusa",   "price": 4500,  "description": "Glazirana keramika, folk motivi, 1970-ih."},
        {"title": "Porcelanski šoljice za kafu, par",        "price": 5500,  "description": "Par šoljica sa tanjirićima, plavi motiv, bez pukotina."},
    ],
    "kuca-kuhinja-trpezarija-case-i-servisi": [
        {"title": "Kristalni servis za vino, 6+6 čaša",      "price": 28000, "description": "Bohemski kristal, original kutija, komplet."},
        {"title": "Porcelanski servis za čaj, 12 delova",    "price": 18000, "description": "Engleski porcelan, ručno slikano, komplet."},
    ],
    "kuca-kuhinja-trpezarija-escajg": [
        {"title": "Srebrni escajg, 12 komada",               "price": 25000, "description": "Masivno srebro, punca 84, originalna kutija."},
        {"title": "Posrebreni escajg, 24 komada",            "price": 12000, "description": "Posrebreni escajg, kompletan set, kutija originalna."},
    ],
    "kuca-kuhinja-trpezarija-kristal": [
        {"title": "Art Deco vaza, zeleno staklo",             "price": 12000, "description": "Zeleno puvano staklo, Art Deco motivi, visina 30 cm."},
        {"title": "Kristalni dekantar sa 4 čaše",            "price": 15000, "description": "Bohemski kristal, gravirani motivi, odlično stanje."},
    ],
    # ── Kuća / Rasveta ───────────────────────────────────────────────────────
    "kuca-rasveta-stone-lampe": [
        {"title": "Stona lampa, mesingana noga",              "price": 8500,  "description": "Mesingana noga, originalni abažur od pergamenta."},
        {"title": "Art Deco stona lampa, staklo",             "price": 14000, "description": "Originalni Art Deco dizajn, 1930-ih, funkcionalna."},
    ],
    "kuca-rasveta-lusteri": [
        {"title": "Luster sa kristalima, 12 krakova",         "price": 45000, "description": "Luster sa 12 kristalnih privezaka, funkcionalan."},
        {"title": "MesIngani luster, 6 krakova",             "price": 28000, "description": "Mesing, ručno rađen, Art Nouveau stil."},
    ],
    "kuca-rasveta-industrijska-rasveta": [
        {"title": "Industrijska viseća lampa, gvožđe",        "price": 9500,  "description": "Autentična industrijska lampa, patinirana, vizualno impresivna."},
        {"title": "Vintage fabrička lampa, podesiva",         "price": 12000, "description": "Podesiva ruka, originalna oprema, očuvan izgled."},
    ],
    "kuca-rasveta-retro-lampe": [
        {"title": "Podni svećnjak, kovano gvožđe",            "price": 11000, "description": "Ručno kovani podni svećnjak, visina 160 cm."},
        {"title": "Retro podna lampa, 1960-ih",               "price": 16000, "description": "Tronožna podna lampa, originalni abažur, odlično stanje."},
    ],
    # ── Kuća / Nameštaj ──────────────────────────────────────────────────────
    "kuca-namestaj-stolice-fotelje": [
        {"title": "Fotelja od pliša iz 70-ih",                "price": 18000, "description": "Bordo plišana fotelja sa drvenim naslonima, odlično sačuvana."},
        {"title": "Trpezarijska stolica, hrast, komplet 4",   "price": 18000, "description": "Masivne hrastove stolice sa tkaninom, komplet."},
        {"title": "Ljuljaška stolica, teak drvo",             "price": 22000, "description": "Klasična ljuljaška od teak drveta, stabilna i udobna."},
    ],
    "kuca-namestaj-stolovi-i-komode": [
        {"title": "Okrugli trpezarijski sto, hrast",          "price": 38000, "description": "Proširivi hrastov sto, prečnik 120 cm, odlično stanje."},
        {"title": "Komoda sa 4 fioke, orah",                  "price": 28000, "description": "Orahova komoda, originalne kvake, izvrsno stanje."},
        {"title": "Kafe sto sa staklenom pločom",             "price": 14000, "description": "Staklena ploča na kovanom postolju, retro dizajn."},
    ],
    "kuca-namestaj-ormari-i-vitrine": [
        {"title": "Ormar dvokrilni, antik",                   "price": 45000, "description": "Dvokrilni ormar sa rezbarenim detaljima, početak 20. veka."},
        {"title": "Vitrina sa staklenim vratima",             "price": 32000, "description": "Visoka vitrina sa staklenim vratima, za porcelan."},
    ],
    "kuca-namestaj-retro-mid-century-komadi": [
        {"title": "Mid-century moderna sofa, krem",           "price": 55000, "description": "Danska izrada, 1960-ih, originalna tkanina, odlično stanje."},
        {"title": "Skandinavska polica, teak",                "price": 22000, "description": "Teak drvo, modularna, 1970-ih, bez oštećenja."},
        {"title": "Eames stil stolica, replica",              "price": 18000, "description": "Klasičan mid-century dizajn, fiberglas sedište."},
    ],
    # ── Antikviteti ──────────────────────────────────────────────────────────
    "antikviteti-namestaj": [
        {"title": "Eklektična fotelja, rezbareno drvo",       "price": 65000, "description": "Ručno rezbarena fotelja, kraj 19. veka, original tkanina."},
        {"title": "Secesijski ormar, orah",                   "price": 85000, "description": "Secesijski stil, 1900-ih, orah sa intarzijama, izuzetan komad."},
        {"title": "Bidermajer komod, trešnja",                "price": 72000, "description": "Austrijski bidermajer, 1830-ih, trešnja, originalne kvake."},
    ],
    "antikviteti-dekoracija": [
        {"title": "Bronzani sat sa figurom",                  "price": 38000, "description": "Francuski bronzani sat, 1880-ih, funkcionalan, original ključ."},
        {"title": "Porcelanska figura, Meisen",               "price": 45000, "description": "Originalna Meisen figura, 18. vek, bez oštećenja."},
        {"title": "Barokno ogledalo, pozlata",                "price": 55000, "description": "Pozlaćeni okvir, barokni motivi, 80×120 cm."},
    ],
    # ── Umetnost ─────────────────────────────────────────────────────────────
    "umetnost-slike-i-crtezi": [
        {"title": "Uljana slika, pejzaž, 60×80 cm",          "price": 55000, "description": "Ulje na platnu, potpisana, nepoznati autor, 60×80 cm."},
        {"title": "Akvarel, portret žene",                    "price": 18000, "description": "Akvarel na papiru, uokviren, 40×50 cm, odlično stanje."},
        {"title": "Crtež tušem, arhitektura",                 "price": 8000,  "description": "Crtež tušem, detalji fasade, uokviren, 30×40 cm."},
    ],
    "umetnost-skulpture": [
        {"title": "Bronzana figura žene",                     "price": 42000, "description": "Bronzana figura, visina 28 cm, original, potpis autora."},
        {"title": "Drvena skulptura, ptica",                  "price": 9000,  "description": "Ručno rezbarena drvena skulptura ptice, visina 25 cm."},
    ],
    "umetnost-fotografija": [
        {"title": "Fotografija Beograda, 1960-ih",            "price": 4500,  "description": "Originalna crno-bela fotografija, uramljena, 30×40 cm."},
        {"title": "Portretna fotografija, sepia, 1920-ih",    "price": 6500,  "description": "Sepia fotografija, fin okvir od drveta, 20×25 cm."},
    ],
    "umetnost-rucni-radovi": [
        {"title": "Vezeni stolnjak, ručni rad",               "price": 6500,  "description": "Ručno vezen stolnjak, beli linen, 150×250 cm."},
        {"title": "Tapiserija, cvjetni motiv",                "price": 14000, "description": "Ručno tkana tapiserija, vuna, 60×80 cm, unikat."},
    ],
    "umetnost-printovi-i-plakati": [
        {"title": "Bakrorez, veduta Novog Sada",              "price": 8000,  "description": "Originalni bakrorez, 35×25 cm, uokviren, potpisano."},
        {"title": "Art Nouveau poster, original",             "price": 12000, "description": "Originalni Art Nouveau plakat, 1900-ih, uokviren."},
    ],
    # ── Tehnika i elektronika ─────────────────────────────────────────────────
    "tehnika-i-elektronika-mobilni-telefoni": [
        {"title": "Nokia 3310, original",                     "price": 3500,  "description": "Legendarni Nokia 3310, funkcionalan, originalna baterija."},
        {"title": "Motorola DynaTAC, replika",                "price": 8000,  "description": "Ikonični dizajn, kolekcionar komad."},
    ],
    "tehnika-i-elektronika-racunari-i-oprema": [
        {"title": "Commodore 64, kompletan set",              "price": 18000, "description": "Commodore 64 sa tastaturom i kablovima, funkcionalan."},
        {"title": "Apple Macintosh 128K",                     "price": 45000, "description": "Original Mac iz 1984, muzejski eksponat, radi."},
    ],
    "tehnika-i-elektronika-tv-i-audio": [
        {"title": "Gramofon, automatski, 1970-ih",            "price": 14000, "description": "Automatski gramofon, odlično zvuči, novi iglaš."},
        {"title": "Reel-to-reel magnetofon, Revox",          "price": 28000, "description": "Revox B77, profesionalni, servisiran, odlično stanje."},
    ],
    "tehnika-i-elektronika-foto-i-video-oprema": [
        {"title": "Leica M3, analogni fotoaparat",            "price": 85000, "description": "Legendarni Leica M3, 1954, funkcionalan, originalni objektiv."},
        {"title": "Polaroid SX-70, original",                 "price": 12000, "description": "Original Polaroid SX-70, servisiran, radi savršeno."},
        {"title": "Rolleiflex, TLR kamera",                   "price": 35000, "description": "Rolleiflex 2.8F, srednji format, odlično stanje."},
    ],
    "tehnika-i-elektronika-kucni-aparati": [
        {"title": "KitchenAid mešalica, vintage crvena",      "price": 22000, "description": "Vintage KitchenAid, funkcionalna, ikonični dizajn."},
        {"title": "Smeg frižider, retro plavi",               "price": 65000, "description": "Smeg retro frižider, plava boja, odlično stanje."},
    ],
    "tehnika-i-elektronika-gaming": [
        {"title": "Nintendo Game Boy, original 1989",         "price": 8500,  "description": "Original Game Boy, sa Tetris-om, funkcionalan."},
        {"title": "Atari 2600, komplet sa igricama",          "price": 15000, "description": "Atari 2600, 10 kaseta, svi kablovi, funkcionalan."},
    ],
    # ── Kolekcionarski predmeti ────────────────────────────────────────────────
    "kolekcionarski-predmeti-stari-novac": [
        {"title": "Rimski denar, 2. vek",                     "price": 12000, "description": "Originalni rimski srebrni denar, 2. vek n.e., sa sertifikatom."},
        {"title": "Osmanli novac, komplet 5 komada",          "price": 8500,  "description": "Pet osmanskih akči, 17-18. vek, dobro sačuvani."},
    ],
    "kolekcionarski-predmeti-znacke": [
        {"title": "Kolekcija pionirskih značaka, 20 kom",     "price": 5500,  "description": "Komplet pionirskih značaka SFRJ, originalne, u kutiji."},
        {"title": "Olimpijska značka, Moskva 1980",           "price": 3500,  "description": "Originalna značka sa Olimpijade u Moskvi, 1980."},
    ],
    "kolekcionarski-predmeti-razglednice": [
        {"title": "Razglednice Beograda, 1920-ih, 10 kom",    "price": 6500,  "description": "Deset razglednica predratnog Beograda, izuzetno stanje."},
        {"title": "Austro-ugarske razglednice, 15 kom",       "price": 9000,  "description": "Razglednice iz perioda Austro-Ugarske, crno-bele."},
    ],
    "kolekcionarski-predmeti-stare-knjige": [
        {"title": "Enciklopedija, 1935, komplet",             "price": 15000, "description": "Kompletna enciklopedija iz 1935, 12 tomova, solidno stanje."},
        {"title": "Stara biblija, 1887",                      "price": 22000, "description": "Bibija štampana 1887, kožni povez, zlatni ukrasi."},
    ],
    "kolekcionarski-predmeti-satovi": [
        {"title": "Džepni sat, srebro, gravura",              "price": 55000, "description": "Srebrni džepni sat sa lancima, gravura na kućici, funkcionalan."},
        {"title": "Ručni sat, mehanički, Omega",              "price": 85000, "description": "Omega Seamaster, 1960-ih, servisiran, original kaiš."},
        {"title": "Zidni sat, mehanički, škrinja",            "price": 28000, "description": "Mehanički zidni sat, funkcionalan, original ključ u kompletu."},
    ],
    # ── Sport i slobodno vreme ─────────────────────────────────────────────────
    "sport-i-slobodno-vreme-bicikli": [
        {"title": "Peugeot bicikl, 1975, 10 brzina",          "price": 22000, "description": "Francuski Peugeot, 1975, servisiran, originalne komponente."},
        {"title": "Gradski bicikl, holandski, 3 brzine",      "price": 18000, "description": "Klasični holandski gradski bicikl, odlično stanje."},
    ],
    "sport-i-slobodno-vreme-fitnes-oprema": [
        {"title": "Metalne bučice, set 2×10 kg",              "price": 8500,  "description": "Klasične livene metalne bučice, originalnu stanje."},
        {"title": "Vintage veslačka mašina, drvo",            "price": 35000, "description": "Drvena veslačka mašina, 1980-ih, servisirana, funkcionalna."},
    ],
    "sport-i-slobodno-vreme-kamp-oprema": [
        {"title": "Coleman šator, vintage, 4 osobe",          "price": 12000, "description": "Klasični Coleman šator, 1980-ih, komplet sa kočićima."},
        {"title": "Primus šporet, kamping, funkcionalan",     "price": 6500,  "description": "Primus kamping šporet, servisiran, odlično radi."},
    ],
    "sport-i-slobodno-vreme-instrumenti": [
        {"title": "Akustična gitara, Yamaha FG-180",          "price": 18000, "description": "Yamaha FG-180 iz 1970-ih, odlično sačuvana, lepo svira."},
        {"title": "Harmonika, Hohner, 120 basova",            "price": 25000, "description": "Hohner harmonika, 120 basova, servisirana, odlično stanje."},
        {"title": "Truba, Bb, mesing, vintage",               "price": 22000, "description": "Mesingana truba Bb, 1960-ih, servisirana, sa futrolom."},
    ],
    "sport-i-slobodno-vreme-hobiji": [
        {"title": "Kolekcija maraka, SFRJ, album",            "price": 9500,  "description": "Kompletni album SFRJ maraka, sve numerisane, odlično stanje."},
        {"title": "Model broda u boci, ručni rad",            "price": 7500,  "description": "Ručno rađen model broda u boci, 1970-ih, unikat."},
    ],
}
