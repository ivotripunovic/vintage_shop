import random
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from django.utils import timezone
from datetime import timedelta

from users.models import User
from sellers.models import Seller, SellerSubscription
from products.models import Product, ProductCategory, ProductCondition


CONDITIONS = [
    {"name": "Novo",         "description": "Nekorišćeno, originalno pakovanje",                   "order": 1},
    {"name": "Kao novo",     "description": "Korišćeno jednom ili dvaput, bez vidljivih oštećenja", "order": 2},
    {"name": "Dobro",        "description": "Vidljivi tragovi korišćenja, u potpunosti funkcionalno", "order": 3},
    {"name": "Prihvatljivo", "description": "Značajni tragovi korišćenja, funkcionalno",            "order": 4},
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

# Keys must match subcategory names from seed_categories
PRODUCTS = {
    # Nameštaj
    "Sedenje": [
        {"title": "Fotelja od pliša iz 70-ih",    "price": 18000, "description": "Bordo plišana fotelja sa drvenim naslonima, odlično sačuvana."},
        {"title": "Trpezarijska stolica, hrast",   "price": 4500,  "description": "Masivna hrastova stolica sa tkaninom, komplet 4 komada."},
        {"title": "Sofa dvosed, vintage stil",     "price": 35000, "description": "Dvosed iz 1980-ih, krem boja, minimalni tragovi korišćenja."},
        {"title": "Ljuljaška stolica, teak drvo",  "price": 22000, "description": "Klasična ljuljaška od teak drveta, stabilna i udobna."},
    ],
    "Odlaganje": [
        {"title": "Komoda sa 4 fioke, orah",       "price": 28000, "description": "Orahova komoda, originalne kvake, izvrsno stanje."},
        {"title": "Vitrina sa staklenim vratima",  "price": 32000, "description": "Visoka vitrina sa staklenim vratima, prikladna za porcelan."},
        {"title": "Polica za knjige, bor",         "price": 12000, "description": "Borova polica, 5 nivoa, lagano požutela boja."},
        {"title": "Ormar dvokrilni, antik",        "price": 45000, "description": "Dvokrilni ormar sa rezbarenim detaljima, početak 20. veka."},
    ],
    "Stolovi": [
        {"title": "Okrugli trpezarijski sto, hrast", "price": 38000, "description": "Proširivi hrastov sto, prečnik 120 cm, odlično stanje."},
        {"title": "Kafe sto sa staklenom pločom",  "price": 14000, "description": "Staklena ploča na kovanom postolju, retro dizajn."},
        {"title": "Pisaći sto, masiv",             "price": 21000, "description": "Masivni pisaći sto sa pregradom i fiokama."},
        {"title": "Pomoćni sto sa intarzijom",     "price": 9500,  "description": "Mali sto sa intarzijskim motivima, Vojvodina, 1950-ih."},
    ],
    "Osvetljenje": [
        {"title": "Luster sa kristalima",          "price": 27000, "description": "Luster sa 12 kristalnih privezaka, funkcionalan."},
        {"title": "Stona lampa, mesingana noga",   "price": 8500,  "description": "Mesingana noga, originalni abažur od pergamenta."},
        {"title": "Podni svećnjak, kovano gvožđe", "price": 11000, "description": "Ručno kovani podni svećnjak, visina 160 cm."},
        {"title": "Zidna aplika, par",             "price": 6500,  "description": "Par aplika od frosted stakla, za E27 sijalicu."},
    ],
    "Ukrasi za dom": [
        {"title": "Ogledalo sa zlatnim okvirom",   "price": 15000, "description": "Ručno rezbareni zlatni okvir, 80×60 cm, bez ogrebotina."},
        {"title": "Zidni sat, mehanički",          "price": 12000, "description": "Mehanički zidni sat, funkcionalan, original ključ u kompletu."},
        {"title": "Ćilim, 200×140 cm",            "price": 19000, "description": "Ručno tkani vuneni ćilim, geometrijski motivi, bez oštećenja."},
        {"title": "Dekorativni jastuci, komplet",  "price": 4000,  "description": "Tapacirski jastuci sa vintage uzorkom, čisti i uredni."},
    ],
    "Dekorativni predmeti": [
        {"title": "Vaza, plave kobalt boje",       "price": 5500,  "description": "Kobalt plava keramička vaza, visina 35 cm, bez pukotina."},
        {"title": "Skulptura, bronza",             "price": 42000, "description": "Bronzana figura žene, visina 28 cm, original."},
        {"title": "Porcelanske šolje, servis za 6","price": 7500,  "description": "Servis za 6 osoba, cvjetni motiv, prodajemo komplet."},
        {"title": "Kutija za nakit, drvo i bakar", "price": 3800,  "description": "Ručno ukrašena kutija, interno tapacirana somotom."},
    ],
    # Umetnost
    "Slike": [
        {"title": "Uljana slika, pejzaž",          "price": 55000, "description": "Ulje na platnu, potpisana, 60×80 cm."},
        {"title": "Akvarel, portret žene",         "price": 18000, "description": "Akvarel na papiru, uokviren, 40×50 cm, odlično stanje."},
        {"title": "Pastelni crtež, tihomorje",     "price": 12000, "description": "Pastel na kartonu, motiv voća, neuramljeno."},
    ],
    "Fotografija": [
        {"title": "Fotografija Beograda, 1960-ih", "price": 4500,  "description": "Originalna crno-bela fotografija, uramljena, 30×40 cm."},
        {"title": "Portretna fotografija, sepia",  "price": 3200,  "description": "Sepia fotografija, fin okvir od drveta, 20×25 cm."},
    ],
    "Skulpture": [
        {"title": "Gipsana figura, art deco",      "price": 22000, "description": "Art deco gipsana figura, visina 45 cm, original."},
        {"title": "Drvena skulptura, ptica",       "price": 9000,  "description": "Ručno rezbarena drvena skulptura ptice, visina 25 cm."},
    ],
    "Grafike": [
        {"title": "Bakrorez, veduta Novog Sada",   "price": 8000,  "description": "Originalni bakrorez, 35×25 cm, uokviren, potpisano."},
        {"title": "Litografija, apstraktni motiv", "price": 6500,  "description": "Litografija iz 1970-ih, 50×40 cm, bez okvira."},
    ],
    "Crteži": [
        {"title": "Crtež tušem, arhitektura",      "price": 5000,  "description": "Crtež tušem, detalji fasade, uokviren, 30×40 cm."},
        {"title": "Olovkom, akt studija",          "price": 4200,  "description": "Akademska studija akta, olovkom, 35×50 cm."},
    ],
    # Nakit
    "Prstenje": [
        {"title": "Zlatni prsten, 14k",            "price": 28000, "description": "Zlatni prsten 14k sa sitnim dijamantom, nošen."},
        {"title": "Srebrni prsten sa ametistom",   "price": 5500,  "description": "Ručno rađen srebrni prsten, lila ametist."},
        {"title": "Koktel prsten, pozlata",        "price": 3200,  "description": "Pozlaćeni koktel prsten sa zelenim staklenim kamenom."},
    ],
    "Ogrlice": [
        {"title": "Biserna ogrlica, klasična",     "price": 12000, "description": "Biserna ogrlica sa zlatnom kopčom, dužina 45 cm."},
        {"title": "Zlatni lančić, 18k",            "price": 35000, "description": "Tanki zlatni lančić 18k, dužina 50 cm, bez oštećenja."},
        {"title": "Koraljna ogrlica",              "price": 8000,  "description": "Ogrlica od crvenog koralja, zlatna kopča, stara 50 godina."},
    ],
    "Minđuše": [
        {"title": "Klipse, pozlaćene",             "price": 2500,  "description": "Vintage klipse, cvetni motiv, dobro sačuvane."},
        {"title": "Srebrne minđuše, filigranski rad", "price": 6000, "description": "Filigransko srebro, dugačke, lagane, ručni rad."},
    ],
    "Narukvice": [
        {"title": "Zlatna narukvica sa charm privescima", "price": 22000, "description": "Zlatna narukvica sa 5 charm privezaka, 14k."},
        {"title": "Srebrna narukvica, pletena",    "price": 7500,  "description": "Srebrna pletena narukvica, punca 925."},
    ],
    "Broševi": [
        {"title": "Broš, kameja",                  "price": 9000,  "description": "Kameja na morskoj školjci, pozlaćeni okvir, original."},
        {"title": "Broš, cvjetni motiv, emajl",    "price": 4500,  "description": "Emajliran broš, dvobojni, odlično stanje."},
    ],
    "Satovi": [
        {"title": "Ručni sat, mehanički, muški",   "price": 45000, "description": "Vintage mehanički sat, čelična kućica, original kaiš."},
        {"title": "Ručni sat, automatski, ženski", "price": 38000, "description": "Automatski sat, zlatna kućica, biserasta platna."},
        {"title": "Džepni sat, srebro",            "price": 55000, "description": "Srebrni džepni sat sa lancima, gravura na kućici."},
    ],
    # Moda
    "Odeća": [
        {"title": "Kožna jakna, smeđa, L",         "price": 16000, "description": "Prava koža, 1980-ih, bez oštećenja, veličina L."},
        {"title": "Teksas jakna, Levi's vintage",  "price": 7500,  "description": "Originalna teksas jakna, vel. M, blago izbledela."},
        {"title": "Vuneni kaput, sivi, vel. 40",   "price": 14000, "description": "100% vuna, dvostruko kopčanje, odlično stanje."},
        {"title": "Svečana haljina, 1960-ih",      "price": 9000,  "description": "Tafta tkanina, cvetni dezeni, vel. 38, originalna."},
    ],
    "Tašne": [
        {"title": "Kožna torba, konjak boja",      "price": 12000, "description": "Prava koža, zlatne kopče, malo nošena."},
        {"title": "Clutch torbica, zlatna",        "price": 5500,  "description": "Svečana clutch, zlatni sjaj, zatvarač funkcionalan."},
        {"title": "Platnena torba, 70-ih",         "price": 3500,  "description": "Pamučna torba sa vezenim motivima, unikat."},
    ],
    "Obuća": [
        {"title": "Kožne cipele, muške, br. 43",   "price": 8500,  "description": "Engleska izrada, ručno šivene, malo nošene."},
        {"title": "Štikle, crvene, br. 38",        "price": 5000,  "description": "Klasične crvene štikle, visina 7 cm, blaga nošenost."},
        {"title": "Čizme do kolena, kožne, br. 39","price": 11000, "description": "Kozija koža, tamno smeđe, odlično stanje."},
    ],
    "Dodaci": [
        {"title": "Svileni šal, 90×90 cm",         "price": 7000,  "description": "Svileni šal, živopisne boje, bez oštećenja."},
        {"title": "Kožni kaiš, muški",             "price": 3200,  "description": "Kožni kaiš sa kovanom kopčom, tamno smeđ."},
        {"title": "Kožne rukavice, crne",          "price": 4500,  "description": "Kožne obloge sa svilenom podstavom, vel. M."},
    ],
    # Kolekcionarstvo
    "Keramika i porcelan": [
        {"title": "Meisenski porcelan, šoljice",   "price": 18000, "description": "Par šoljica sa tanjirićima, plavi motiv, bez pukotina."},
        {"title": "Keramička tegla, folk motivi",  "price": 4500,  "description": "Glazirana keramika, folk motivi, Zlakusa, 1970-ih."},
        {"title": "Porcelanski servis za čaj",     "price": 32000, "description": "Komplet servis, 12 komada, zlatni ivičnjaci, besprekoran."},
    ],
    "Srebrnina i metal": [
        {"title": "Srebrni escajg, 12 komada",     "price": 25000, "description": "Masivno srebro, punca 84, originalna kutija."},
        {"title": "Mesingani svećnjak, par",       "price": 8500,  "description": "Par mesinganh svećnjaka, visina 25 cm, lepo patinirali."},
        {"title": "Srebrni okvir za sliku",        "price": 6000,  "description": "Srebrni okvir, ornamentika, 15×10 cm, punca."},
    ],
    "Staklo": [
        {"title": "Bohemski kristalni servis",     "price": 28000, "description": "Kristalni servis za vino, 6+6 čaša, original kutija."},
        {"title": "Art Deco vaza, zeleno staklo",  "price": 12000, "description": "Zeleno puvano staklo, Art Deco motivi, visina 30 cm."},
    ],
    "Tekstil": [
        {"title": "Vezeni stolnjak, ručni rad",    "price": 6500,  "description": "Ručno vezen stolnjak, beli linen, 150×250 cm."},
        {"title": "Svilena posteljina, set",       "price": 15000, "description": "Svilena posteljina, 2 jastuka + čaršav, blaga patina."},
        {"title": "Vuneni ćilim, kilim stil",      "price": 22000, "description": "Ručno tkani kilim, crveno-plavi motiv, 180×120 cm."},
    ],
}


class Command(BaseCommand):
    help = "Seed conditions, sellers and products. Run seed_categories first."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all products, conditions and seed sellers before seeding",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            Product.objects.all().delete()
            ProductCondition.objects.all().delete()
            seed_shop_names = [s["shop_name"] for s in SELLERS]
            Seller.objects.filter(shop_name__in=seed_shop_names).delete()
            User.objects.filter(email__endswith="@seed.vs").delete()
            User.objects.filter(email__regex=r"^seller\d+@example\.com$").delete()
            self.stdout.write(self.style.WARNING("Cleared products, conditions and seed sellers."))

        if not ProductCategory.objects.filter(parent__isnull=False).exists():
            self.stdout.write(self.style.ERROR(
                "No subcategories found. Run `python manage.py seed_categories` first."
            ))
            return

        conditions = self._seed_conditions()
        sellers = self._seed_sellers()
        self._seed_products(sellers, conditions)

    def _seed_conditions(self):
        created = 0
        conditions = {}
        for data in CONDITIONS:
            obj, is_new = ProductCondition.objects.get_or_create(
                name=data["name"],
                defaults={"description": data["description"], "order": data["order"]},
            )
            conditions[data["name"]] = obj
            if is_new:
                created += 1
        self.stdout.write(f"Stanja: {created} kreirana, {len(CONDITIONS) - created} već postoje.")
        return conditions

    def _seed_sellers(self):
        created = 0
        sellers = []
        for i, data in enumerate(SELLERS):
            email = f"seller{i + 1}@seed.vs"
            user, user_created = User.objects.get_or_create(
                email=email,
                defaults={
                    "username": email,
                    "first_name": data["shop_name"].split()[0],
                    "last_name": "Seed",
                    "is_seller": True,
                    "email_verified": True,
                },
            )
            if user_created:
                user.set_unusable_password()
                user.save()

            # The post-save signal auto-creates a Seller when is_seller=True.
            # Update it with proper shop data instead of creating a second one.
            seller = Seller.objects.get(user=user)
            seller_created = not bool(seller.shop_name)
            Seller.objects.filter(pk=seller.pk).update(
                shop_name=data["shop_name"],
                shop_slug=slugify(data["shop_name"]),
                shop_description="Pažljivo odabrani vintage predmeti sa garancijom autentičnosti.",
                location=data["location"],
                status="active",
                bank_account_holder=data["shop_name"],
                bank_name="Banka",
                bank_account_number=f"RS35000000000000000{i:02d}",
            )
            seller.refresh_from_db()
            SellerSubscription.objects.get_or_create(
                seller=seller,
                defaults={
                    "plan_type": "monthly",
                    "start_date": timezone.now().date(),
                    "status": "active",
                    "amount": Decimal("999"),
                    "renewal_date": (timezone.now() + timedelta(days=30)).date(),
                },
            )
            sellers.append(seller)
            if seller_created:
                created += 1

        self.stdout.write(f"Prodavci: {created} kreirani, {len(SELLERS) - created} već postoje.")
        return sellers

    def _seed_products(self, sellers, conditions):
        created = 0
        skipped_missing = 0
        condition_list = list(conditions.values())
        seller_count = len(sellers)

        for subcategory_name, templates in PRODUCTS.items():
            try:
                category = ProductCategory.objects.get(name=subcategory_name)
            except ProductCategory.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f"  Podkategorija '{subcategory_name}' nije pronađena, preskačem."
                ))
                skipped_missing += len(templates)
                continue

            for i, tpl in enumerate(templates):
                _, is_new = Product.objects.get_or_create(
                    title=tpl["title"],
                    defaults={
                        "seller": sellers[i % seller_count],
                        "description": tpl["description"],
                        "price": Decimal(str(tpl["price"])),
                        "category": category,
                        "condition": random.choice(condition_list),
                        "stock": random.randint(1, 3),
                        "status": "published",
                    },
                )
                if is_new:
                    created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Proizvodi: {created} kreirani."
            + (f" {skipped_missing} preskočeni (nedostaje podkategorija)." if skipped_missing else "")
        ))
