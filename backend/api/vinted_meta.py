"""
Proxy endpoints for Vinted brand and category metadata.
Used by the frontend to populate brand/category selectors in the filter form.
"""
from fastapi import APIRouter, Request, Query
from vinted.exceptions import VintedAuthError, VintedNetworkError

router = APIRouter(prefix="/api/vinted", tags=["vinted-meta"])

# Popular brands fallback (used when Vinted API is unavailable)
FALLBACK_BRANDS = [
    {"id": 53, "title": "Nike"}, {"id": 14, "title": "Adidas"},
    {"id": 3, "title": "Zara"}, {"id": 26, "title": "H&M"},
    {"id": 65, "title": "Mango"}, {"id": 304, "title": "Levi's"},
    {"id": 1341, "title": "Tommy Hilfiger"}, {"id": 109, "title": "Ralph Lauren"},
    {"id": 308, "title": "Calvin Klein"}, {"id": 302, "title": "Lacoste"},
    {"id": 88, "title": "Gucci"}, {"id": 99, "title": "Louis Vuitton"},
    {"id": 475, "title": "Balenciaga"}, {"id": 1, "title": "Prada"},
    {"id": 2, "title": "Chanel"}, {"id": 4, "title": "Dior"},
    {"id": 5, "title": "Versace"}, {"id": 6, "title": "Givenchy"},
    {"id": 7, "title": "Burberry"}, {"id": 8, "title": "Hermès"},
    {"id": 9, "title": "Saint Laurent"}, {"id": 10, "title": "Valentino"},
    {"id": 11, "title": "Bottega Veneta"}, {"id": 12, "title": "Celine"},
    {"id": 13, "title": "Fendi"}, {"id": 15, "title": "Off-White"},
    {"id": 16, "title": "Supreme"}, {"id": 17, "title": "Stone Island"},
    {"id": 18, "title": "The North Face"}, {"id": 19, "title": "Carhartt"},
    {"id": 20, "title": "Lululemon"}, {"id": 21, "title": "Patagonia"},
    {"id": 22, "title": "Champion"}, {"id": 23, "title": "Converse"},
    {"id": 24, "title": "Vans"}, {"id": 25, "title": "New Balance"},
    {"id": 27, "title": "Puma"}, {"id": 28, "title": "Reebok"},
    {"id": 29, "title": "Under Armour"}, {"id": 30, "title": "Columbia"},
    {"id": 31, "title": "Patagonia"}, {"id": 32, "title": "Timberland"},
    {"id": 33, "title": "Dr. Martens"}, {"id": 34, "title": "UGG"},
    {"id": 35, "title": "Birkenstock"}, {"id": 36, "title": "BOSS"},
    {"id": 37, "title": "Paul Smith"}, {"id": 38, "title": "Ted Baker"},
    {"id": 39, "title": "ASOS"}, {"id": 40, "title": "Topshop"},
    {"id": 41, "title": "Pull&Bear"}, {"id": 42, "title": "Stradivarius"},
    {"id": 43, "title": "Bershka"}, {"id": 44, "title": "Reserved"},
    {"id": 45, "title": "Only"}, {"id": 46, "title": "Vero Moda"},
    {"id": 47, "title": "Jack & Jones"}, {"id": 48, "title": "Esprit"},
    {"id": 49, "title": "Massimo Dutti"}, {"id": 50, "title": "COS"},
    {"id": 51, "title": "& Other Stories"}, {"id": 52, "title": "Arket"},
    {"id": 54, "title": "Uniqlo"}, {"id": 55, "title": "Primark"},
    {"id": 56, "title": "Next"}, {"id": 57, "title": "M&S"},
    {"id": 58, "title": "Gap"}, {"id": 59, "title": "Banana Republic"},
    {"id": 60, "title": "J.Crew"}, {"id": 61, "title": "American Eagle"},
    {"id": 62, "title": "Abercrombie & Fitch"}, {"id": 63, "title": "Hollister"},
    {"id": 64, "title": "Urban Outfitters"}, {"id": 66, "title": "Free People"},
    {"id": 67, "title": "Anthropologie"}, {"id": 68, "title": "Reformation"},
    {"id": 69, "title": "Reiss"}, {"id": 70, "title": "AllSaints"},
    {"id": 71, "title": "Barbour"}, {"id": 72, "title": "Mulberry"},
    {"id": 73, "title": "Longchamp"}, {"id": 74, "title": "Coach"},
    {"id": 75, "title": "Michael Kors"}, {"id": 76, "title": "Kate Spade"},
    {"id": 77, "title": "Tory Burch"}, {"id": 78, "title": "Marc Jacobs"},
    {"id": 79, "title": "Versace Jeans"}, {"id": 80, "title": "Diesel"},
    {"id": 81, "title": "G-Star RAW"}, {"id": 82, "title": "Pepe Jeans"},
    {"id": 83, "title": "Wrangler"}, {"id": 84, "title": "Lee"},
    {"id": 85, "title": "Replay"}, {"id": 86, "title": "Liu Jo"},
    {"id": 87, "title": "Pinko"}, {"id": 89, "title": "Miu Miu"},
    {"id": 90, "title": "Alexander McQueen"}, {"id": 91, "title": "Moschino"},
    {"id": 92, "title": "Kenzo"}, {"id": 93, "title": "Acne Studios"},
    {"id": 94, "title": "Maison Margiela"}, {"id": 95, "title": "Rick Owens"},
    {"id": 96, "title": "Comme des Garçons"}, {"id": 97, "title": "A.P.C."},
    {"id": 98, "title": "Isabel Marant"}, {"id": 100, "title": "Sandro"},
    {"id": 101, "title": "Maje"}, {"id": 102, "title": "Ba&sh"},
    {"id": 103, "title": "The Kooples"}, {"id": 104, "title": "IRO"},
    {"id": 105, "title": "Claudie Pierlot"}, {"id": 106, "title": "Zadig & Voltaire"},
    {"id": 107, "title": "Aigle"}, {"id": 108, "title": "Petit Bateau"},
    {"id": 110, "title": "Armor Lux"}, {"id": 111, "title": "Galeries Lafayette"},
    {"id": 112, "title": "IKKS"}, {"id": 113, "title": "Comptoir des Cotonniers"},
    {"id": 114, "title": "agnès b."}, {"id": 115, "title": "Jacquemus"},
    {"id": 116, "title": "Y-3"}, {"id": 117, "title": "Fear of God"},
    {"id": 118, "title": "Stüssy"}, {"id": 119, "title": "Palace"},
    {"id": 120, "title": "Kith"}, {"id": 121, "title": "Rhude"},
    {"id": 122, "title": "Amiri"}, {"id": 123, "title": "Represent"},
    {"id": 124, "title": "CP Company"}, {"id": 125, "title": "Moncler"},
    {"id": 126, "title": "Canada Goose"}, {"id": 127, "title": "Mackage"},
    {"id": 128, "title": "Arc'teryx"}, {"id": 129, "title": "Salomon"},
    {"id": 130, "title": "Merrell"}, {"id": 131, "title": "ASICS"},
    {"id": 132, "title": "Brooks"}, {"id": 133, "title": "Hoka"},
    {"id": 134, "title": "On Running"}, {"id": 135, "title": "Skechers"},
]


async def _ensure_session(client) -> None:
    """Ensure the Vinted client has a valid session (anonymous if needed)."""
    if not client._csrf_token and not client._cookies:
        await client.fetch_csrf_token()


@router.get("/brands")
async def search_brands(request: Request, q: str = Query(default="", min_length=0)):
    """Search Vinted brands by name. Returns list of {id, title}."""
    client = request.app.state.vinted_client
    q = q.strip()
    if not q:
        return {"brands": []}

    await _ensure_session(client)

    try:
        data = await client.get("/brands", params={"name": q, "per_page": 30})
        brands = data.get("brands") or []
        if brands:
            return {"brands": [{"id": b["id"], "title": b["title"]} for b in brands if b.get("id") and b.get("title")]}
    except (VintedAuthError, VintedNetworkError):
        pass
    except Exception:
        pass

    # Fallback: filter static brand list
    q_lower = q.lower()
    matched = [b for b in FALLBACK_BRANDS if q_lower in b["title"].lower()]
    matched.sort(key=lambda b: (0 if b["title"].lower().startswith(q_lower) else 1, b["title"]))
    return {"brands": matched[:20]}


def _flatten(cats: list, parent: str = "") -> list:
    result = []
    for c in (cats or []):
        if not isinstance(c, dict):
            continue
        cid = c.get("id")
        title = c.get("title") or c.get("name") or ""
        if not (cid and title):
            continue
        full = f"{parent} > {title}" if parent else title
        result.append({"id": cid, "title": title, "full_title": full})
        children = c.get("children") or c.get("subcategories") or []
        result.extend(_flatten(children, full))
    return result


# Static Vinted France categories (IDs réels Vinted.fr)
STATIC_CATEGORIES = [
    # ── FEMMES ──────────────────────────────────────────────────────────────────
    # Hauts
    {"id": 1904, "title": "T-shirts",           "full_title": "Femmes > Hauts > T-shirts"},
    {"id": 2050, "title": "Chemises",            "full_title": "Femmes > Hauts > Chemises"},
    {"id": 4,    "title": "Pulls & sweats",      "full_title": "Femmes > Hauts > Pulls & sweats"},
    {"id": 3,    "title": "Hoodies",             "full_title": "Femmes > Hauts > Hoodies"},
    {"id": 1906, "title": "Débardeurs & tops",   "full_title": "Femmes > Hauts > Débardeurs & tops"},
    {"id": 1912, "title": "Blouses",             "full_title": "Femmes > Hauts > Blouses"},
    {"id": 1913, "title": "Cardigans",           "full_title": "Femmes > Hauts > Cardigans"},
    {"id": 1914, "title": "Crop tops",           "full_title": "Femmes > Hauts > Crop tops"},
    # Robes
    {"id": 1607, "title": "Robes",               "full_title": "Femmes > Robes"},
    {"id": 1916, "title": "Robes courtes",       "full_title": "Femmes > Robes > Courtes"},
    {"id": 1917, "title": "Robes longues",       "full_title": "Femmes > Robes > Longues"},
    {"id": 1918, "title": "Robes mi-longues",    "full_title": "Femmes > Robes > Mi-longues"},
    # Bas
    {"id": 1609, "title": "Jeans",               "full_title": "Femmes > Bas > Jeans"},
    {"id": 1608, "title": "Pantalons",           "full_title": "Femmes > Bas > Pantalons"},
    {"id": 1610, "title": "Jupes",               "full_title": "Femmes > Bas > Jupes"},
    {"id": 1617, "title": "Shorts",              "full_title": "Femmes > Bas > Shorts"},
    {"id": 1920, "title": "Leggings",            "full_title": "Femmes > Bas > Leggings"},
    {"id": 1921, "title": "Joggings",            "full_title": "Femmes > Bas > Joggings"},
    # Manteaux & vestes
    {"id": 6,    "title": "Vestes",              "full_title": "Femmes > Manteaux & vestes > Vestes"},
    {"id": 7,    "title": "Manteaux",            "full_title": "Femmes > Manteaux & vestes > Manteaux"},
    {"id": 1925, "title": "Doudounes",           "full_title": "Femmes > Manteaux & vestes > Doudounes"},
    {"id": 1926, "title": "Trench-coats",        "full_title": "Femmes > Manteaux & vestes > Trench-coats"},
    {"id": 1927, "title": "Blazers",             "full_title": "Femmes > Manteaux & vestes > Blazers"},
    {"id": 1928, "title": "Parkas",              "full_title": "Femmes > Manteaux & vestes > Parkas"},
    # Combinaisons
    {"id": 1619, "title": "Combinaisons",        "full_title": "Femmes > Combinaisons"},
    {"id": 1621, "title": "Maillots de bain",    "full_title": "Femmes > Maillots de bain"},
    {"id": 1622, "title": "Lingerie",            "full_title": "Femmes > Lingerie"},
    # Chaussures femmes
    {"id": 16,   "title": "Baskets",             "full_title": "Femmes > Chaussures > Baskets"},
    {"id": 1634, "title": "Escarpins",           "full_title": "Femmes > Chaussures > Escarpins"},
    {"id": 1635, "title": "Bottes & bottines",   "full_title": "Femmes > Chaussures > Bottes & bottines"},
    {"id": 1636, "title": "Sandales",            "full_title": "Femmes > Chaussures > Sandales"},
    {"id": 1637, "title": "Ballerines",          "full_title": "Femmes > Chaussures > Ballerines"},
    {"id": 1638, "title": "Mocassins",           "full_title": "Femmes > Chaussures > Mocassins"},
    {"id": 1940, "title": "Mules & sabots",      "full_title": "Femmes > Chaussures > Mules & sabots"},
    {"id": 1941, "title": "Chaussures de sport", "full_title": "Femmes > Chaussures > Sport"},
    # Sacs femmes
    {"id": 1624, "title": "Sacs à main",         "full_title": "Femmes > Sacs > Sacs à main"},
    {"id": 1625, "title": "Sacs à dos",          "full_title": "Femmes > Sacs > Sacs à dos"},
    {"id": 1626, "title": "Sacs bandoulière",    "full_title": "Femmes > Sacs > Bandoulière"},
    {"id": 1945, "title": "Pochettes",           "full_title": "Femmes > Sacs > Pochettes"},
    {"id": 1946, "title": "Tote bags",           "full_title": "Femmes > Sacs > Tote bags"},
    # Accessoires femmes
    {"id": 1628, "title": "Lunettes",            "full_title": "Femmes > Accessoires > Lunettes"},
    {"id": 1629, "title": "Ceintures",           "full_title": "Femmes > Accessoires > Ceintures"},
    {"id": 1630, "title": "Bijoux",              "full_title": "Femmes > Accessoires > Bijoux"},
    {"id": 1631, "title": "Chapeaux & casquettes","full_title":"Femmes > Accessoires > Chapeaux"},
    {"id": 1633, "title": "Écharpes & foulards", "full_title": "Femmes > Accessoires > Écharpes"},
    {"id": 1950, "title": "Montres",             "full_title": "Femmes > Accessoires > Montres"},
    {"id": 1951, "title": "Gants",               "full_title": "Femmes > Accessoires > Gants"},

    # ── HOMMES ──────────────────────────────────────────────────────────────────
    # Hauts
    {"id": 1206, "title": "T-shirts",            "full_title": "Hommes > Hauts > T-shirts"},
    {"id": 2,    "title": "Chemises",            "full_title": "Hommes > Hauts > Chemises"},
    {"id": 1207, "title": "Pulls & sweats",      "full_title": "Hommes > Hauts > Pulls & sweats"},
    {"id": 1208, "title": "Hoodies",             "full_title": "Hommes > Hauts > Hoodies"},
    {"id": 2060, "title": "Débardeurs",          "full_title": "Hommes > Hauts > Débardeurs"},
    {"id": 2061, "title": "Polos",               "full_title": "Hommes > Hauts > Polos"},
    # Bas
    {"id": 1212, "title": "Jeans",               "full_title": "Hommes > Bas > Jeans"},
    {"id": 1213, "title": "Pantalons",           "full_title": "Hommes > Bas > Pantalons"},
    {"id": 1214, "title": "Shorts",              "full_title": "Hommes > Bas > Shorts"},
    {"id": 1215, "title": "Joggings",            "full_title": "Hommes > Bas > Joggings"},
    {"id": 2065, "title": "Leggings & collants", "full_title": "Hommes > Bas > Leggings"},
    # Manteaux & vestes
    {"id": 1209, "title": "Vestes",              "full_title": "Hommes > Manteaux & vestes > Vestes"},
    {"id": 1210, "title": "Manteaux",            "full_title": "Hommes > Manteaux & vestes > Manteaux"},
    {"id": 1211, "title": "Doudounes",           "full_title": "Hommes > Manteaux & vestes > Doudounes"},
    {"id": 2070, "title": "Parkas",              "full_title": "Hommes > Manteaux & vestes > Parkas"},
    {"id": 2071, "title": "Blazers & costumes",  "full_title": "Hommes > Manteaux & vestes > Blazers"},
    {"id": 2072, "title": "Bombers",             "full_title": "Hommes > Manteaux & vestes > Bombers"},
    {"id": 2073, "title": "Trench-coats",        "full_title": "Hommes > Manteaux & vestes > Trench-coats"},
    # Suits
    {"id": 1216, "title": "Costumes & smokings", "full_title": "Hommes > Costumes & smokings"},
    # Chaussures hommes
    {"id": 1217, "title": "Baskets",             "full_title": "Hommes > Chaussures > Baskets"},
    {"id": 1218, "title": "Bottines & boots",    "full_title": "Hommes > Chaussures > Bottines & boots"},
    {"id": 1219, "title": "Mocassins",           "full_title": "Hommes > Chaussures > Mocassins"},
    {"id": 1220, "title": "Sandales",            "full_title": "Hommes > Chaussures > Sandales"},
    {"id": 2080, "title": "Chaussures de sport", "full_title": "Hommes > Chaussures > Sport"},
    {"id": 2081, "title": "Derbies & richelieus","full_title": "Hommes > Chaussures > Derbies"},
    # Sacs & accessoires hommes
    {"id": 1221, "title": "Sacs & bagages",      "full_title": "Hommes > Sacs"},
    {"id": 2085, "title": "Sacs à dos",          "full_title": "Hommes > Sacs > Sacs à dos"},
    {"id": 2086, "title": "Bananes",             "full_title": "Hommes > Sacs > Bananes"},
    {"id": 1222, "title": "Ceintures",           "full_title": "Hommes > Accessoires > Ceintures"},
    {"id": 1223, "title": "Lunettes",            "full_title": "Hommes > Accessoires > Lunettes"},
    {"id": 1224, "title": "Montres",             "full_title": "Hommes > Accessoires > Montres"},
    {"id": 1225, "title": "Casquettes & chapeaux","full_title":"Hommes > Accessoires > Casquettes"},
    {"id": 1226, "title": "Écharpes & foulards", "full_title": "Hommes > Accessoires > Écharpes"},
    {"id": 2090, "title": "Bijoux",              "full_title": "Hommes > Accessoires > Bijoux"},
    {"id": 2091, "title": "Gants",               "full_title": "Hommes > Accessoires > Gants"},
    {"id": 2092, "title": "Cravates",            "full_title": "Hommes > Accessoires > Cravates"},
    # Sous-vêtements hommes
    {"id": 2095, "title": "Sous-vêtements",      "full_title": "Hommes > Sous-vêtements"},
    {"id": 2096, "title": "Chaussettes",         "full_title": "Hommes > Chaussettes"},
    {"id": 2097, "title": "Maillots de bain",    "full_title": "Hommes > Maillots de bain"},

    # ── ENFANTS ─────────────────────────────────────────────────────────────────
    {"id": 1231, "title": "Vêtements bébé",      "full_title": "Enfants > Bébé (0-24 mois) > Vêtements"},
    {"id": 1232, "title": "Chaussures bébé",     "full_title": "Enfants > Bébé (0-24 mois) > Chaussures"},
    {"id": 2101, "title": "Accessoires bébé",    "full_title": "Enfants > Bébé (0-24 mois) > Accessoires"},
    {"id": 1233, "title": "T-shirts garçon",     "full_title": "Enfants > Garçons > T-shirts"},
    {"id": 2102, "title": "Pantalons garçon",    "full_title": "Enfants > Garçons > Pantalons"},
    {"id": 2103, "title": "Vestes garçon",       "full_title": "Enfants > Garçons > Vestes"},
    {"id": 2104, "title": "Chaussures garçon",   "full_title": "Enfants > Garçons > Chaussures"},
    {"id": 1234, "title": "Robes fille",         "full_title": "Enfants > Filles > Robes"},
    {"id": 2105, "title": "T-shirts fille",      "full_title": "Enfants > Filles > T-shirts"},
    {"id": 2106, "title": "Pantalons fille",     "full_title": "Enfants > Filles > Pantalons"},
    {"id": 2107, "title": "Chaussures fille",    "full_title": "Enfants > Filles > Chaussures"},
    {"id": 1235, "title": "Jeans enfant",        "full_title": "Enfants > Bas > Jeans"},
    {"id": 1236, "title": "Chaussures enfant",   "full_title": "Enfants > Chaussures"},
    {"id": 1237, "title": "Jouets",              "full_title": "Enfants > Jouets & Jeux"},
    {"id": 1238, "title": "Livres enfant",       "full_title": "Enfants > Livres & Éducation"},
    {"id": 2110, "title": "Puériculture",        "full_title": "Enfants > Puériculture"},

    # ── MAISON ──────────────────────────────────────────────────────────────────
    {"id": 1781, "title": "Décoration",          "full_title": "Maison > Décoration"},
    {"id": 1782, "title": "Linge de maison",     "full_title": "Maison > Linge de maison"},
    {"id": 1783, "title": "Vaisselle",           "full_title": "Maison > Cuisine > Vaisselle"},
    {"id": 1784, "title": "Électroménager",      "full_title": "Maison > Cuisine > Électroménager"},
    {"id": 1785, "title": "Meubles",             "full_title": "Maison > Meubles"},
    {"id": 1786, "title": "Luminaires",          "full_title": "Maison > Luminaires"},
    {"id": 1787, "title": "Jardin & Plantes",    "full_title": "Maison > Jardin & Plantes"},
    {"id": 2120, "title": "Bougies & senteurs",  "full_title": "Maison > Décoration > Bougies"},
    {"id": 2121, "title": "Tableaux & art",      "full_title": "Maison > Décoration > Art"},
    {"id": 2122, "title": "Textiles déco",       "full_title": "Maison > Décoration > Textiles"},

    # ── SPORT ───────────────────────────────────────────────────────────────────
    {"id": 2390, "title": "Vêtements sport",     "full_title": "Sport > Vêtements de sport"},
    {"id": 2391, "title": "Chaussures sport",    "full_title": "Sport > Chaussures de sport"},
    {"id": 2392, "title": "Équipement sport",    "full_title": "Sport > Équipement"},
    {"id": 2393, "title": "Vélos",               "full_title": "Sport > Vélos & Cyclisme"},
    {"id": 2394, "title": "Ski & Snowboard",     "full_title": "Sport > Ski & Snowboard"},
    {"id": 2395, "title": "Football",            "full_title": "Sport > Football"},
    {"id": 2396, "title": "Running",             "full_title": "Sport > Running"},
    {"id": 2397, "title": "Natation",            "full_title": "Sport > Natation"},
    {"id": 2398, "title": "Tennis",              "full_title": "Sport > Tennis & Raquettes"},
    {"id": 2399, "title": "Yoga & Fitness",      "full_title": "Sport > Yoga & Fitness"},
    {"id": 2400, "title": "Randonnée",           "full_title": "Sport > Randonnée & Outdoor"},

    # ── DIVERTISSEMENT ───────────────────────────────────────────────────────────
    {"id": 1901, "title": "Livres",              "full_title": "Divertissement > Livres"},
    {"id": 1902, "title": "Musique (CD, vinyles)","full_title":"Divertissement > Musique"},
    {"id": 1903, "title": "Films & Séries",      "full_title": "Divertissement > Films & Séries"},
    {"id": 1905, "title": "Jeux vidéo",          "full_title": "Divertissement > Jeux vidéo"},
    {"id": 1906, "title": "Consoles",            "full_title": "Divertissement > Consoles"},
    {"id": 2130, "title": "Jeux de société",     "full_title": "Divertissement > Jeux de société"},
    {"id": 2131, "title": "BD & Manga",          "full_title": "Divertissement > BD & Manga"},

    # ── ÉLECTRONIQUE ─────────────────────────────────────────────────────────────
    {"id": 2640, "title": "Téléphones",          "full_title": "Électronique > Téléphones & Smartphones"},
    {"id": 2641, "title": "Tablettes",           "full_title": "Électronique > Tablettes"},
    {"id": 2642, "title": "Ordinateurs",         "full_title": "Électronique > Ordinateurs & Laptops"},
    {"id": 2643, "title": "Appareils photo",     "full_title": "Électronique > Appareils photo"},
    {"id": 2644, "title": "Casques & écouteurs", "full_title": "Électronique > Audio > Casques"},
    {"id": 2645, "title": "Enceintes",           "full_title": "Électronique > Audio > Enceintes"},
    {"id": 2646, "title": "Accessoires tech",    "full_title": "Électronique > Accessoires"},

    # ── BEAUTÉ ───────────────────────────────────────────────────────────────────
    {"id": 2200, "title": "Parfums",             "full_title": "Beauté > Parfums"},
    {"id": 2201, "title": "Soins visage",        "full_title": "Beauté > Soins > Visage"},
    {"id": 2202, "title": "Soins corps",         "full_title": "Beauté > Soins > Corps"},
    {"id": 2203, "title": "Maquillage",          "full_title": "Beauté > Maquillage"},
    {"id": 2204, "title": "Soins cheveux",       "full_title": "Beauté > Cheveux"},
]


@router.get("/categories")
async def get_categories(request: Request):
    """Return Vinted catalog categories (flattened tree)."""
    client = request.app.state.vinted_client

    await _ensure_session(client)

    try:
        data = await client.get("/catalog/categories")
        cats = (data.get("catalogs") or data.get("catalog_categories")
                or data.get("categories") or [])
        result = _flatten(cats)
        if result:
            return {"categories": result}
    except (VintedAuthError, VintedNetworkError):
        pass
    except Exception:
        pass

    # Fallback: return static category list
    return {"categories": STATIC_CATEGORIES}


@router.get("/debug")
async def debug_vinted(request: Request):
    """
    Live diagnostic: test the Vinted connection and return detailed info.
    Visit /api/vinted/debug in your browser to see what's happening.
    """
    client = request.app.state.vinted_client
    result = {
        "csrf_token": bool(client._csrf_token),
        "has_cookies": bool(client._cookies or (client._session and client._session.cookies)),
        "steps": [],
    }

    # Step 1: fetch CSRF
    try:
        resp = await client._session.get(client.base_url) if client._session else None
        if resp:
            result["homepage_status"] = resp.status_code
            result["homepage_content_type"] = resp.headers.get("content-type", "")
            result["homepage_is_html"] = "text/html" in resp.headers.get("content-type", "")
            # Check if Cloudflare challenge
            text_preview = resp.text[:300] if resp.text else ""
            result["cloudflare_challenge"] = "cf-browser-verification" in text_preview or "Just a moment" in text_preview
            result["steps"].append(f"Homepage: HTTP {resp.status_code}")
        else:
            result["steps"].append("No session initialized")
    except Exception as e:
        result["steps"].append(f"Homepage error: {e}")

    # Step 2: try catalog API
    try:
        data = await client.get("/catalog/items", params={"order": "newest_first", "per_page": 5})
        if "raw" in data:
            result["catalog_status"] = "ERROR: non-JSON response (Cloudflare/blocked)"
            result["catalog_preview"] = data["raw"][:300]
        else:
            items = data.get("items") or data.get("catalog_items") or []
            result["catalog_status"] = f"OK — {len(items)} items returned"
            result["catalog_keys"] = list(data.keys())
        result["steps"].append(f"Catalog API: {result.get('catalog_status','?')}")
    except Exception as e:
        result["catalog_status"] = f"ERROR: {e}"
        result["steps"].append(f"Catalog error: {e}")

    # Diagnosis
    if result.get("cloudflare_challenge"):
        result["diagnosis"] = (
            "BLOQUÉ PAR CLOUDFLARE. L'IP du serveur est bloquée. "
            "Solution : allez dans Paramètres et collez vos cookies Vinted "
            "(depuis votre navigateur connecté à Vinted)."
        )
    elif "OK" in str(result.get("catalog_status", "")):
        result["diagnosis"] = "CONNEXION OK — le bot devrait afficher des articles."
    else:
        result["diagnosis"] = (
            "Erreur de connexion. "
            "Solution : collez vos cookies Vinted dans l'onglet Paramètres."
        )

    return result
