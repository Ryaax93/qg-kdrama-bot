import discord
from discord.ext import commands, tasks
import asyncio
import random
import json
import os
import datetime
from collections import defaultdict
from discord import ui

# ============================================================
#  CONFIG — remplace TOKEN par ton vrai token
# ============================================================
TOKEN = os.getenv("TOKEN")
PREFIX = "."
# ============================================================

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)


# ---------- Stockage en mémoire ----------
xp_data = defaultdict(lambda: {"xp": 0, "level": 1})
economy_data = defaultdict(lambda: {"coins": 0, "tier": "Spectateur Débutant"})
# ── Variables manquantes ─────────────────────────────────────
message_count = defaultdict(int)     # {uid: nb_messages}
gacha_cooldowns = defaultdict(int)   # {uid: timestamp}
mariage_data = {}                    # {uid: uid_partenaire}
anniversaire_data = {}               # {uid: "JJ/MM"}
invitation_data = defaultdict(int)   # {uid: nb_invitations}

duels = {}
tickets = {}
cooldowns = {}
voice_clients = {}
queues = defaultdict(list)

# ---------- Stats arène & points d'amélioration ----------
def default_arena_stats():
    return {"pv_bonus": 0, "atk_bonus": 0, "def_bonus": 0, "end_bonus": 0}

arena_stats = defaultdict(default_arena_stats)   # {uid: {pv_bonus, atk_bonus, def_bonus, end_bonus}}
points_amelio = defaultdict(int)                  # {uid: points disponibles}

# ---------- Titres selon niveau ----------
TIERS = [
    (1,   "🌱 Académicien Débutant"),
    (5,   "⚔️ Chasseur de Rang E"),
    (10,  "🗡️ Chasseur de Rang D"),
    (15,  "💥 Chasseur de Rang C"),
    (20,  "🔥 Chasseur de Rang B"),
    (25,  "⚡ Chasseur de Rang A"),
    (30,  "💎 Chasseur de Rang S"),
    (40,  "👑 Pillier du QG"),
    (50,  "🌀 Maître des Arts Martiaux"),
    (60,  "☠️ Lune Supérieure"),
    (75,  "🐉 Roi des Malédictions"),
    (99,  "🌟 Monarque des Ombres"),
]

# Salons configurables
SALON_LEVELUP_ID = None   # Met l'ID du salon level up ici
SALON_CASINO_ID = None    # Met l'ID du salon casino ici
SALON_GACHA_ID = None     # Met l'ID du salon gacha ici
SALON_EVENT_ID = None     # Salon pour les events
SALON_GUIDE_ID = None      # Salon pour le guide (invasions, nuit de chasse, coffres, marché noir)
SALON_BOUTIQUE_ID = None  # Met l'ID du salon boutique ici
SALON_COMBAT_ID = None    # Met l'ID du salon pokebattle ici
SALON_DUEL_ID = None      # Met l'ID du salon duel/pvp ici
SALON_BIENVENUE_ID = None # Met l'ID du salon bienvenue ici
SALON_AUREVOIR_ID = None  # Met l'ID du salon aurevoir ici
SALON_BOOST_ID = None     # Met l'ID du salon boost ici
SALON_HOF_ID = None       # Met l'ID du salon hall of fame ici
SALON_REGLEMENT_ID = None # Met l'ID du salon règlement ici
ROLE_MEMBRE_NAME = "Membre"  # Nom du rôle à donner après acceptation
REGLEMENT_ROLE_ID = None      # ID du rôle règlement (plus fiable que le nom)
REGLEMENT_MSG_ID = None   # ID du message règlement (auto-rempli par setsalon)

CONFIG_FILE = "salons_config.json"

def sauvegarder_salons():
    """Sauvegarde tous les IDs de salons dans un fichier JSON"""
    data = {
        "SALON_LEVELUP_ID":   SALON_LEVELUP_ID,
        "SALON_CASINO_ID":    SALON_CASINO_ID,
        "SALON_GACHA_ID":     SALON_GACHA_ID,
        "SALON_EVENT_ID":     SALON_EVENT_ID,
        "SALON_GUIDE_ID":     SALON_GUIDE_ID,
        "SALON_BOUTIQUE_ID":  SALON_BOUTIQUE_ID,
        "SALON_COMBAT_ID":    SALON_COMBAT_ID,
        "SALON_DUEL_ID":      SALON_DUEL_ID,
        "SALON_BIENVENUE_ID": SALON_BIENVENUE_ID,
        "SALON_AUREVOIR_ID":  SALON_AUREVOIR_ID,
        "SALON_BOOST_ID":     SALON_BOOST_ID,
        "SALON_HOF_ID":       SALON_HOF_ID,
        "SALON_REGLEMENT_ID": SALON_REGLEMENT_ID,
        "ROLE_MEMBRE_NAME":   ROLE_MEMBRE_NAME,
        "REGLEMENT_ROLE_ID":  REGLEMENT_ROLE_ID,
        "REGLEMENT_MSG_ID":   REGLEMENT_MSG_ID,
        "CONQUETE_ZONE_IDS":  CONQUETE_ZONE_IDS,
    }
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        print(f"[Config] Erreur sauvegarde : {e}")

def charger_salons():
    """Charge les IDs de salons depuis le fichier JSON au démarrage"""
    global SALON_LEVELUP_ID, SALON_CASINO_ID, SALON_GACHA_ID, SALON_BOUTIQUE_ID, SALON_EVENT_ID, SALON_GUIDE_ID
    global SALON_COMBAT_ID, SALON_DUEL_ID, SALON_BIENVENUE_ID, SALON_AUREVOIR_ID
    global SALON_BOOST_ID, SALON_HOF_ID, SALON_REGLEMENT_ID, ROLE_MEMBRE_NAME, REGLEMENT_ROLE_ID, REGLEMENT_MSG_ID
    if not os.path.exists(CONFIG_FILE):
        return
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        SALON_LEVELUP_ID   = data.get("SALON_LEVELUP_ID")
        SALON_CASINO_ID    = data.get("SALON_CASINO_ID")
        SALON_GACHA_ID     = data.get("SALON_GACHA_ID")
        SALON_EVENT_ID     = data.get("SALON_EVENT_ID")
        SALON_GUIDE_ID     = data.get("SALON_GUIDE_ID")
        SALON_BOUTIQUE_ID  = data.get("SALON_BOUTIQUE_ID")
        SALON_COMBAT_ID    = data.get("SALON_COMBAT_ID")
        SALON_DUEL_ID      = data.get("SALON_DUEL_ID")
        SALON_BIENVENUE_ID = data.get("SALON_BIENVENUE_ID")
        SALON_AUREVOIR_ID  = data.get("SALON_AUREVOIR_ID")
        SALON_BOOST_ID     = data.get("SALON_BOOST_ID")
        SALON_HOF_ID       = data.get("SALON_HOF_ID")
        SALON_REGLEMENT_ID = data.get("SALON_REGLEMENT_ID")
        ROLE_MEMBRE_NAME   = data.get("ROLE_MEMBRE_NAME", "Membre")
        global REGLEMENT_ROLE_ID
        REGLEMENT_ROLE_ID  = int(data["REGLEMENT_ROLE_ID"]) if data.get("REGLEMENT_ROLE_ID") else None
        REGLEMENT_MSG_ID   = int(data["REGLEMENT_MSG_ID"]) if data.get("REGLEMENT_MSG_ID") else None
        CONQUETE_ZONE_IDS[:] = data.get("CONQUETE_ZONE_IDS", [])
        print("[Config] ✅ Salons chargés depuis salons_config.json")
    except Exception as e:
        print(f"[Config] Erreur chargement : {e}")

# Charger au démarrage
charger_salons()

HOF_MESSAGES = set()      # IDs des messages déjà dans le Hall of Fame
HOF_EMOJIS = {"😭", "🤣", "😂", "😹"}
HOF_SEUIL = 4

def get_tier(level):
    title = TIERS[0][1]
    for lvl, name in TIERS:
        if level >= lvl:
            title = name
    return title

# ============================================================
#  DONNÉES KDRAMA / ANIMÉ / GAMING
# ============================================================
KDRAMAS = [
    {"title": "Crash Landing on You", "genre": "Romance", "note": "⭐ 9.2/10", "emoji": "🪂", "image": "https://cdn.myanimelist.net/images/anime/1/106706.jpg"},
    {"title": "Goblin", "genre": "Fantasy/Romance", "note": "⭐ 9.5/10", "emoji": "🕯️", "image": "https://cdn.myanimelist.net/images/anime/1/83770.jpg"},
    {"title": "My Love from the Star", "genre": "Romance/SF", "note": "⭐ 8.9/10", "emoji": "⭐", "image": "https://cdn.myanimelist.net/images/anime/5/65514.jpg"},
    {"title": "Descendants of the Sun", "genre": "Romance/Action", "note": "⭐ 8.8/10", "emoji": "☀️", "image": "https://cdn.myanimelist.net/images/anime/11/78857.jpg"},
    {"title": "Reply 1988", "genre": "Slice of Life", "note": "⭐ 9.7/10", "emoji": "📼", "image": "https://cdn.myanimelist.net/images/anime/1/84217.jpg"},
    {"title": "Vincenzo", "genre": "Thriller/Comédie", "note": "⭐ 9.0/10", "emoji": "🦅", "image": "https://cdn.myanimelist.net/images/anime/1/107945.jpg"},
    {"title": "Itaewon Class", "genre": "Drama/Romance", "note": "⭐ 8.7/10", "emoji": "🍺", "image": "https://cdn.myanimelist.net/images/anime/1/103593.jpg"},
    {"title": "Kingdom", "genre": "Historique/Horreur", "note": "⭐ 9.1/10", "emoji": "👑", "image": "https://cdn.myanimelist.net/images/anime/1/96680.jpg"},
    {"title": "Squid Game", "genre": "Thriller", "note": "⭐ 8.0/10", "emoji": "🦑", "image": "https://cdn.myanimelist.net/images/anime/1/110969.jpg"},
    {"title": "Signal", "genre": "Policier/Thriller", "note": "⭐ 9.3/10", "emoji": "📻", "image": "https://cdn.myanimelist.net/images/anime/1/82892.jpg"},
    {"title": "Hospital Playlist", "genre": "Médical/Slice of Life", "note": "⭐ 9.4/10", "emoji": "🩺", "image": "https://cdn.myanimelist.net/images/anime/1/104103.jpg"},
    {"title": "Weightlifting Fairy Kim Bok-joo", "genre": "Romance/Sport", "note": "⭐ 8.9/10", "emoji": "🏋️", "image": "https://cdn.myanimelist.net/images/anime/1/85566.jpg"},
]

ANIMES = [
    {"title": "Attack on Titan", "genre": "Action/Drame", "note": "⭐ 9.1/10", "emoji": "⚔️", "image": "https://cdn.myanimelist.net/images/anime/10/47347.jpg"},
    {"title": "Demon Slayer", "genre": "Action/Aventure", "note": "⭐ 8.7/10", "emoji": "🗡️", "image": "https://cdn.myanimelist.net/images/anime/1/96652.jpg"},
    {"title": "One Piece", "genre": "Aventure", "note": "⭐ 9.0/10", "emoji": "🏴‍☠️", "image": "https://cdn.myanimelist.net/images/anime/6/73245.jpg"},
    {"title": "Death Note", "genre": "Psychologique/Thriller", "note": "⭐ 9.0/10", "emoji": "📓", "image": "https://cdn.myanimelist.net/images/anime/9/9453.jpg"},
    {"title": "Fullmetal Alchemist: Brotherhood", "genre": "Action/Fantasy", "note": "⭐ 9.5/10", "emoji": "⚗️", "image": "https://cdn.myanimelist.net/images/anime/1/27482.jpg"},
    {"title": "Haikyuu!!", "genre": "Sport/Drame", "note": "⭐ 9.1/10", "emoji": "🏐", "image": "https://cdn.myanimelist.net/images/anime/7/76014.jpg"},
    {"title": "Jujutsu Kaisen", "genre": "Action/Dark Fantasy", "note": "⭐ 8.8/10", "emoji": "💥", "image": "https://cdn.myanimelist.net/images/anime/1/105764.jpg"},
    {"title": "Vinland Saga", "genre": "Historique/Action", "note": "⭐ 9.0/10", "emoji": "🪓", "image": "https://cdn.myanimelist.net/images/anime/1/98922.jpg"},
    {"title": "Your Lie in April", "genre": "Romance/Musique", "note": "⭐ 9.3/10", "emoji": "🎹", "image": "https://cdn.myanimelist.net/images/anime/3/67177.jpg"},
    {"title": "Naruto Shippuden", "genre": "Action/Aventure", "note": "⭐ 8.7/10", "emoji": "🍥", "image": "https://cdn.myanimelist.net/images/anime/4/50361.jpg"},
]

GAMES = [
    {"title": "Genshin Impact", "genre": "RPG/Gacha", "emoji": "🌸", "image": "https://cdn.cloudflare.steamstatic.com/steam/apps/1452830/header.jpg"},
    {"title": "Valorant", "genre": "FPS Tactique", "emoji": "🎯", "image": "https://cdn.cloudflare.steamstatic.com/steam/apps/1274080/header.jpg"},
    {"title": "League of Legends", "genre": "MOBA", "emoji": "⚔️", "image": "https://cdn.cloudflare.steamstatic.com/steam/apps/2633200/header.jpg"},
    {"title": "Elden Ring", "genre": "Action RPG", "emoji": "💀", "image": "https://cdn.cloudflare.steamstatic.com/steam/apps/1245620/header.jpg"},
    {"title": "Stardew Valley", "genre": "Simulation", "emoji": "🌾", "image": "https://cdn.cloudflare.steamstatic.com/steam/apps/413150/header.jpg"},
    {"title": "Minecraft", "genre": "Sandbox", "emoji": "⛏️", "image": "https://cdn.cloudflare.steamstatic.com/steam/apps/1672970/header.jpg"},
    {"title": "Overwatch 2", "genre": "FPS", "emoji": "🦸", "image": "https://cdn.cloudflare.steamstatic.com/steam/apps/2357570/header.jpg"},
    {"title": "Hollow Knight", "genre": "Metroidvania", "emoji": "🦋", "image": "https://cdn.cloudflare.steamstatic.com/steam/apps/367520/header.jpg"},
]

# Quiz par catégorie
# Alias pour les noms d'anime/drama — accepte FR, EN, JP et abréviations
ANIME_ALIASES = {
    "attack on titan": ["attaque des titans", "shingeki no kyojin", "snk", "aot", "attack on titans"],
    "demon slayer": ["kimetsu no yaiba", "kny", "demon slayers"],
    "jujutsu kaisen": ["jjk", "jujutsu"],
    "my hero academia": ["boku no hero academia", "bnha", "mha", "boku no hero", "hero academia"],
    "fullmetal alchemist": ["fma", "full metal alchemist", "fullmetal alchemist brotherhood", "fmab"],
    "hunter x hunter": ["hxh", "hunter hunter"],
    "one piece": ["op"],
    "death note": ["dn"],
    "sword art online": ["sao"],
    "no game no life": ["ngnl"],
    "re zero": ["re:zero", "rezero", "re: zero starting life in another world"],
    "vinland saga": ["vinland"],
    "your lie in april": ["shigatsu wa kimi no uso", "shigatsu"],
    "code geass": ["geass"],
    "tokyo ghoul": ["tg"],
    "black clover": ["bc"],
    "solo leveling": ["only i level up", "na honjaman level up"],
    "squid game": ["squid games"],
    "boys over flowers": ["fleurs de garçons", "kkotboda namja"],
    "goblin": ["guardian the lonely and great god", "dokkaebi"],
    "crash landing on you": ["cloy", "atterrissage d'urgence pour vous"],
    "itaewon class": ["itaewon"],
    "vincenzo": [],
    "kingdom": [],
}

def normalize_str(s: str) -> str:
    """Normalise une chaîne : minuscules, sans accents, sans ponctuation"""
    import unicodedata, re as _re
    s = s.lower().strip()
    # Supprimer les accents
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    # Supprimer ponctuation sauf tirets
    s = _re.sub(r"[^\w\s-]", "", s)
    # Espaces multiples
    s = _re.sub(r"\s+", " ", s).strip()
    return s

def check_answer(reponse: str, correct: str) -> bool:
    """Vérifie si la réponse est correcte — tolère accents, ponctuation, abréviations"""
    rep_raw = reponse.lower().strip()
    cor_raw = correct.lower().strip()
    if rep_raw == cor_raw:
        return True
    # Normalisation accents/ponctuation
    rep_n = normalize_str(reponse)
    cor_n = normalize_str(correct)
    if rep_n == cor_n:
        return True
    # Réponse contenue dans la bonne (ou inverse) pour réponses partielles
    if rep_n and cor_n and (rep_n in cor_n or cor_n in rep_n):
        # Éviter faux positifs trop courts
        if len(rep_n) >= 3:
            return True
    # Chercher dans les alias
    for canonical, aliases in ANIME_ALIASES.items():
        groupe = [normalize_str(x) for x in [canonical] + aliases]
        if normalize_str(correct) in groupe and normalize_str(reponse) in groupe:
            return True
    # Accepter réponses multiples séparées par / ou |
    for alt in correct.split("/"):
        if normalize_str(reponse) == normalize_str(alt.strip()):
            return True
    return False

QUIZ_KDRAMA = [
    {"q": "Dans quel drama joue Lee Min-ho dans le rôle de Gu Jun-pyo ?", "a": "boys over flowers"},
    {"q": "Comment s'appelle le goblin dans le drama 'Goblin' ?", "a": "kim shin"},
    {"q": "Dans 'Crash Landing on You', dans quel pays atterrit Yoon Se-ri ?", "a": "corée du nord"},
    {"q": "Quel drama coréen a été le premier à entrer dans le top 1 mondial Netflix ?", "a": "squid game"},
    {"q": "Dans 'Reply 1988', dans quel quartier de Séoul vivent les personnages ?", "a": "ssangmun-dong"},
    {"q": "Dans quel drama Park Seo-joon tient un restaurant après avoir été viré ?", "a": "itaewon class"},
    {"q": "Quel acteur joue le rôle principal dans Vincenzo ?", "a": "song joong-ki"},
    {"q": "Dans Goblin, quelle est la profession de Ji Eun-tak ?", "a": "lycéenne"},
    {"q": "Combien d'épisodes compte la saison 1 de Squid Game ?", "a": "9"},
    {"q": "Dans Kingdom, quel est le nom du prince héritier ?", "a": "lee chang"},
    {"q": "Quel drama met en scène un avocat qui devient un mafiosi en Italie ?", "a": "vincenzo"},
    {"q": "Dans My Love from the Star, de quelle planète vient l'extraterrestre ?", "a": "kdm-2"},
    {"q": "Quel drama raconte l'histoire d'une héritière tombant en Corée du Nord ?", "a": "crash landing on you"},
    {"q": "Dans Descendants of the Sun, quel est le métier du personnage principal ?", "a": "soldat"},
    {"q": "Dans Hospital Playlist, combien d'amis médecins forment le groupe principal ?", "a": "5"},
    {"q": "Dans Signal, quel objet permet aux personnages de communiquer à travers le temps ?", "a": "talkie walkie"},
    {"q": "Dans Weightlifting Fairy Kim Bok-joo, quel sport pratique l'héroïne ?", "a": "haltérophilie"},
    {"q": "Quel acteur joue dans Crash Landing on You et Descendants of the Sun ?", "a": "hyun bin"},
    {"q": "Dans 'It's Okay to Not Be Okay', quel est le métier de la protagoniste féminine ?", "a": "auteure"},
    {"q": "Dans Goblin, qui est la fiancée du goblin ?", "a": "ji eun-tak"},
    {"q": "Quel drama coréen historique parle d'une épidémie de zombies pendant la période Joseon ?", "a": "kingdom"},
    {"q": "Dans Business Proposal, comment les deux personnages principaux se rencontrent-ils ?", "a": "blind date"},
    {"q": "Dans Twenty-Five Twenty-One, quel sport pratique l'héroïne ?", "a": "escrime"},
    {"q": "Dans Extraordinary Attorney Woo, de quelle condition est atteinte l'héroïne ?", "a": "autisme"},
    {"q": "Dans quel drama Song Hye-kyo joue une femme qui se venge après son divorce ?", "a": "the glory"},
    {"q": "Dans Juvenile Justice, quel est le métier de la protagoniste ?", "a": "juge"},
    {"q": "Dans Hometown Cha-Cha-Cha, dans quelle ville se passe l'histoire ?", "a": "gongjin"},
    {"q": "Dans My Mister, quel acteur joue le personnage principal masculin ?", "a": "lee sun-kyun"},
    {"q": "Dans Arthdal Chronicles, quel est le nom de la tribu principale ?", "a": "igutu"},
    {"q": "Dans Start-Up, comment s'appelle la startup que crée l'héroïne ?", "a": "samsan tech"},
    {"q": "Dans Move to Heaven, que fait le personnage principal comme métier ?", "a": "trauma cleaner"},
    {"q": "Dans Sweet Home, qu'est-ce que les humains deviennent ?", "a": "monstres"},
    {"q": "Dans Hellbound, qui mène une organisation religieuse appelée La Nouvelle Vérité ?", "a": "jung jin-soo"},
    {"q": "Dans Mr. Sunshine, dans quelle période historique se déroule le drama ?", "a": "joseon"},
    {"q": "Quel drama met en scène un système de simulation de vie passée ?", "a": "black mirror/be right back"},
    {"q": "Dans Pinocchio, quel est le syndrome éponyme dans le drama ?", "a": "hoquet quand on ment"},
    {"q": "Dans Reply 1994, comment s'appelle le personnage principal féminin ?", "a": "sung na-jung"},
    {"q": "Dans Nine: Nine Time Travels, combien de voyages dans le temps sont possibles ?", "a": "9"},
    {"q": "Dans The World of the Married, quel est le métier de l'héroïne ?", "a": "médecin"},
    {"q": "Dans Flower of Evil, quelle est la double vie du mari ?", "a": "tueur en série"},
    {"q": "Dans 'Voice', quel est le numéro d'urgence coréen ?", "a": "112"},
    {"q": "Dans When the Camellia Blooms, comment s'appelle le bar de l'héroïne ?", "a": "camellia"},
    {"q": "Dans D.P., que signifie D.P. ?", "a": "deserter pursuit"},
    {"q": "Dans Reborn Rich, en quelle année le protagoniste se réincarne-t-il ?", "a": "1987"},
    {"q": "Dans All of Us Are Dead, où se passe le drama ?", "a": "lycée"},
    {"q": "Dans Crash Course in Romance, quel est le métier de l'héroïne ?", "a": "restauratrice"},
    {"q": "Dans Doctor Slump, quel est le point commun des deux protagonistes ?", "a": "burnout"},
    {"q": "Dans Queen of Tears, quelle est la famille riche du drama ?", "a": "queens group"},
    {"q": "Dans My Demon, qui est le démon ?", "a": "do hyeok-nu"},
    {"q": "Dans Mask Girl, quel est le complexe principal de l'héroïne ?", "a": "son apparence physique"},
]

QUIZ_ANIME = [
    {"q": "Quel est le vrai nom de Light Yagami dans Death Note ?", "a": "light yagami"},
    {"q": "Dans Demon Slayer, quelle est la technique signature de Tanjiro avec l'eau ?", "a": "respiration de l'eau"},
    {"q": "Dans Demon Slayer, comment s'appelle la technique du Soleil de Tanjiro ?", "a": "hinokami kagura/danse du feu"},
    {"q": "Quel animé se passe dans le monde des Titans derrière des murs ?", "a": "attack on titan"},
    {"q": "Comment s'appelle le démon que Tanjiro affronte comme boss final dans Demon Slayer ?", "a": "muzan"},
    {"q": "Dans One Piece, quel est le fruit du diable de Luffy ?", "a": "gomu gomu"},
    {"q": "Quel est le prénom du personnage principal de Jujutsu Kaisen ?", "a": "yuji"},
    {"q": "Dans Your Lie in April, de quel instrument joue Kousei ?", "a": "piano"},
    {"q": "Combien de titans primordiaux existent dans Attack on Titan ?", "a": "9"},
    {"q": "Dans FMA Brotherhood, quel est l'équivalent sacrifié par Ed pour ramener Alphonse ?", "a": "son bras"},
    {"q": "Dans Naruto, quel est le nom du renard à 9 queues scellé en Naruto ?", "a": "kurama"},
    {"q": "Dans Jujutsu Kaisen, quel est le rang de Gojo Satoru ?", "a": "special de classe 1"},
    {"q": "Dans Attack on Titan, quel est le nom du titan de Eren au début ?", "a": "titan assaillant"},
    {"q": "Dans Demon Slayer, quelle est la couleur des yeux de Nezuko ?", "a": "rose"},
    {"q": "Dans Hunter x Hunter, quelle est la technique de Killua qui utilise l'électricité ?", "a": "godspeed"},
    {"q": "Dans Dragon Ball Z, sur quelle planète Goku est-il né ?", "a": "vegeta"},
    {"q": "Dans My Hero Academia, quel est le vrai nom du Quirk de Deku ?", "a": "one for all"},
    {"q": "Dans Tokyo Ghoul, que devient Ken Kaneki après une opération ?", "a": "demi-ghoul"},
    {"q": "Dans Black Clover, quelle magie possède Asta contrairement aux autres ?", "a": "aucune"},
    {"q": "Dans Solo Leveling, quel est le rang initial de Sung Jin-Woo ?", "a": "e"},
    {"q": "Dans Code Geass, quel pouvoir possède Lelouch ?", "a": "geass"},
    {"q": "Dans Re:Zero, comment s'appelle le pouvoir de Subaru ?", "a": "retour par la mort"},
    {"q": "Dans Fullmetal Alchemist, quel est le principe fondamental de l'alchimie ?", "a": "echange equivalent"},
    {"q": "Dans Naruto, quelle est la technique ultime de Naruto ?", "a": "rasengan"},
    {"q": "Dans Death Note, comment s'appelle le shinigami qui donne le Death Note à Light ?", "a": "ryuk"},
    {"q": "Dans Demon Slayer, combien y a-t-il de Piliers ?", "a": "9"},
    {"q": "Dans Jujutsu Kaisen, quelle malédiction est scellée dans Yuji ?", "a": "sukuna"},
    {"q": "Dans Hunter x Hunter, que veut trouver Gon comme objectif principal ?", "a": "son pere"},
    {"q": "Dans My Hero Academia, quel est le vrai nom d'All Might ?", "a": "toshinori yagi"},
    {"q": "Dans quel animé voit-on des personnages utiliser des respirations pour combattre des démons ?", "a": "demon slayer"},
    {"q": "Dans One Punch Man, pourquoi Saitama est-il si fort ?", "a": "entrainement intensif"},
    {"q": "Dans Naruto, quel est le groupe de méchants principaux ?", "a": "akatsuki"},
    {"q": "Dans Bleach, comment s'appelle l'épée de Ichigo ?", "a": "zangetsu"},
    {"q": "Dans Dragon Ball, quel est le niveau de puissance légendaire d'un Saiyan ?", "a": "super saiyan"},
    {"q": "Dans One Piece, comment s'appelle l'équipage de Luffy ?", "a": "chapeau de paille"},
    {"q": "Dans Naruto, qui est le sensei de l'équipe 7 ?", "a": "kakashi"},
    {"q": "Dans Jujutsu Kaisen, quelle est la technique de domaine de Gojo ?", "a": "infinity/infini"},
    {"q": "Dans Attack on Titan, quel est le nom du mur extérieur ?", "a": "maria"},
    {"q": "Dans Demon Slayer, quel Pilier est le mari de Aoi ?", "a": "tengen uzui"},
    {"q": "Dans Fullmetal Alchemist, comment s'appelle le pays principal ?", "a": "amestris"},
    {"q": "Dans Hunter x Hunter, quel est le nom de l'organisation des chasseurs ?", "a": "association des chasseurs"},
    {"q": "Dans My Hero Academia, comment s'appelle l'école de héros ?", "a": "ua"},
    {"q": "Dans Sword Art Online, quel est l'ID de Kirito dans le jeu ?", "a": "kirito"},
    {"q": "Dans Dragon Ball Z, qui est le rival principal de Goku ?", "a": "vegeta"},
    {"q": "Dans Bleach, qu'est-ce qu'un Bankai ?", "a": "liberation finale du zanpakuto"},
    {"q": "Dans Tokyo Ghoul, dans quel arrondissement de Tokyo se passe l'histoire ?", "a": "20ème"},
    {"q": "Dans One Piece, comment s'appelle le monde sous-marin de poissons-hommes ?", "a": "fishman island"},
    {"q": "Dans Naruto, quel est l'œil légendaire des Uchiha ?", "a": "sharingan"},
    {"q": "Dans Demon Slayer, quelle est la couleur de la respiration de Rengoku ?", "a": "flamme/rouge"},
    {"q": "Dans JJK, comment s'appelle l'école de Yuji ?", "a": "tokyo jujutsu high"},
    {"q": "Dans AoT, qui est le commandant du Survey Corps ?", "a": "erwin"},
    {"q": "Dans Black Clover, comment s'appelle le grimoire à 5 feuilles d'Asta ?", "a": "grimoire de la magie antimagie"},
    {"q": "Dans HxH, comment s'appelle la capacité de manipulation d'énergie ?", "a": "nen"},
    {"q": "Dans Overlord, quel niveau maximum possède Ainz ?", "a": "100"},
    {"q": "Dans Re:Zero, comment s'appelle la grande spirit de glace ?", "a": "emilia"},
    {"q": "Dans Vinland Saga, quel est le nom du mentor de Thorfinn ?", "a": "askeladd"},
    {"q": "Dans Mob Psycho 100, quel est le vrai prénom de Mob ?", "a": "shigeo"},
    {"q": "Dans Code Geass, quel est le nom du mecha de Lelouch ?", "a": "lancelot"},
    {"q": "Dans Berserk, comment s'appelle l'épée géante de Guts ?", "a": "dragonslayer"},
    {"q": "Dans Solo Leveling, comment s'appelle le système qui guide Jin-Woo ?", "a": "system"},
    {"q": "Dans Kimetsu no Yaiba, comment se nomme l'organisation des tueurs de démons ?", "a": "demon slayer corps"},
    {"q": "Dans Steins;Gate, que signifie El Psy Kongroo ?", "a": "rien/phrase inventee"},
    {"q": "Dans Cowboy Bebop, comment s'appelle le vaisseau des chasseurs de primes ?", "a": "bebop"},
    {"q": "Dans Parasyte, dans quelle partie du corps Migi s'est-il installé ?", "a": "main droite"},
    {"q": "Dans Made in Abyss, comment s'appelle l'abîme géant ?", "a": "the abyss"},
    {"q": "Dans Vinland Saga, de quel pays est originaire Thorfinn ?", "a": "islande"},
    {"q": "Dans Gintama, comment s'appelle le sabre en bois de Gintoki ?", "a": "bokuto"},
    {"q": "Dans Fate, quel est le vrai nom de Saber ?", "a": "artoria/arturia"},
    {"q": "Dans Tower of God, quel surnom a Bam ?", "a": "black turtle/vingt-cinquième bam"},
    {"q": "Dans Chainsaw Man, quelle est la forme finale de Makima ?", "a": "control devil"},
    {"q": "Dans Bungo Stray Dogs, quelle est l'organisation criminelle principale ?", "a": "la guilde du port"},
    {"q": "Dans Assassination Classroom, comment s'appelle la classe des personnages principaux ?", "a": "classe 3-e"},
    {"q": "Dans Rurouni Kenshin, quelle est la technique ultime de Kenshin ?", "a": "amakakeru ryu no hirameki"},
    {"q": "Dans Spirited Away, comment s'appelle le patron des bains ?", "a": "yubaba"},
    {"q": "Dans Fullmetal Alchemist, comment s'appellent les créatures homunculi ?", "a": "homunculi"},
    {"q": "Dans Naruto, combien de queues a le démon de Killer Bee ?", "a": "8"},
    {"q": "Dans One Piece, quel est le fruit du diable de Ace ?", "a": "mera mera"},
    {"q": "Dans Dragon Ball, comment s'appelle la technique d'énergie signature de Goku ?", "a": "kamehameha"},
    {"q": "Dans My Hero Academia, quelle est la capacité de Hawks ?", "a": "fierce wings/plumes"},
    {"q": "Dans Demon Slayer, qui est le Pilier du Vent ?", "a": "sanemi"},
    {"q": "Dans JJK, comment s'appelle la technique des 10 ombres de Megumi ?", "a": "dix ombres"},
    {"q": "Dans Black Clover, quel est le titre du chef des Magic Knights ?", "a": "magic emperor/roi des mages"},
    {"q": "Dans HxH, quel est le vrai nom de Killua ?", "a": "killua zoldyck"},
    {"q": "Dans Overlord, comment s'appelle la guilde d'Ainz ?", "a": "ainz ooal gown"},
]

QUIZ_GAMING = [
    {"q": "Dans Genshin Impact, quel est le nom de la région de départ ?", "a": "mondstadt"},
    {"q": "Dans Elden Ring, comment s'appelle le monde ouvert principal ?", "a": "entre-terre"},
    {"q": "Dans Valorant, combien de rounds faut-il gagner pour remporter une partie ?", "a": "13"},
    {"q": "Dans League of Legends, comment s'appelle la tour centrale à détruire ?", "a": "nexus"},
    {"q": "Dans Minecraft, quel matériau est le plus résistant ?", "a": "netherite"},
    {"q": "Quel est le nom du dragon final dans Skyrim ?", "a": "alduin"},
    {"q": "Dans Genshin Impact, quel élément représente Zhongli ?", "a": "geo"},
    {"q": "Dans Fortnite, combien de joueurs participent à une partie Battle Royale standard ?", "a": "100"},
    {"q": "Dans GTA V, combien de personnages jouables y a-t-il ?", "a": "3"},
    {"q": "Dans Pokémon, quelle est l'évolution finale de Salamèche ?", "a": "dracaufeu"},
    {"q": "Dans Zelda Breath of the Wild, quel est le nom du château principal ?", "a": "hyrule"},
    {"q": "Dans Dark Souls, comment s'appelle le boss final du premier jeu ?", "a": "gwyn"},
    {"q": "Dans Overwatch, quel est le rôle principal de Mercy ?", "a": "support"},
    {"q": "Dans Apex Legends, combien de joueurs composent une équipe standard ?", "a": "3"},
    {"q": "Dans Red Dead Redemption 2, quel est le nom du gang principal ?", "a": "van der linde"},
    {"q": "Dans Cyberpunk 2077, dans quelle ville futuriste se passe le jeu ?", "a": "night city"},
    {"q": "Dans Hollow Knight, comment s'appelle le royaume des insectes ?", "a": "hallownest"},
    {"q": "Dans FIFA, comment s'appelle le mode avec des cartes de joueurs à collectionner ?", "a": "ultimate team"},
    {"q": "Dans Call of Duty, comment s'appelle la carte Battle Royale principale de Warzone ?", "a": "verdansk"},
    {"q": "Dans Among Us, comment s'appelle le lieu central du vaisseau ?", "a": "cafeteria"},
    {"q": "Dans Genshin Impact, quel est le nom du protagoniste masculin par défaut ?", "a": "aether"},
    {"q": "Dans Pokémon Rouge/Bleu, quel est le premier Pokémon du Pokédex ?", "a": "bulbizarre"},
    {"q": "Dans Super Mario, comment s'appelle la princesse que Mario sauve toujours ?", "a": "peach"},
    {"q": "Dans Fortnite, comment s'appelle la zone qui rétrécit ?", "a": "tempete/storm"},
    {"q": "Dans Minecraft, comment s'appelle le boss final ?", "a": "ender dragon"},
    {"q": "Dans League of Legends, comment s'appelle la rivière qui divise la carte ?", "a": "riviere"},
    {"q": "Dans Valorant, quel agent peut se téléporter ?", "a": "jett/omen/yoru"},
    {"q": "Dans GTA San Andreas, comment s'appelle le personnage principal ?", "a": "cj/carl johnson"},
    {"q": "Dans Dark Souls 3, comment s'appelle le boss final secret ?", "a": "soul of cinder"},
    {"q": "Dans Zelda Ocarina of Time, comment s'appelle la fée de Link ?", "a": "navi"},
    {"q": "Dans Pokémon, comment s'appelle le champion de la ligue à Kanto ?", "a": "blue/gary"},
    {"q": "Dans Elden Ring, comment s'appelle la déesse de l'Anneau unique ?", "a": "marika"},
    {"q": "Dans Genshin, quel personnage est le Archon de l'eau ?", "a": "focalors/furina"},
    {"q": "Dans FIFA 23, quelle est la note du meilleur joueur ?", "a": "91"},
    {"q": "Dans Apex Legends, quel est le personnage de légende avec une barrière de bouclier ?", "a": "gibraltar"},
]

QUIZ_CULTURE = [
    {"q": "Quelle est la capitale de la Corée du Sud ?", "a": "seoul"},
    {"q": "En quelle année a eu lieu la Révolution française ?", "a": "1789"},
    {"q": "Qui a peint la Joconde ?", "a": "leonard de vinci"},
    {"q": "Quelle planète est la plus proche du Soleil ?", "a": "mercure"},
    {"q": "Combien de côtés a un hexagone ?", "a": "6"},
    {"q": "Quel est le plus grand océan du monde ?", "a": "pacifique"},
    {"q": "Dans quel pays se trouve la Tour de Pise ?", "a": "italie"},
    {"q": "Combien font 17 × 8 ?", "a": "136"},
    {"q": "Quelle est la langue la plus parlée au monde ?", "a": "mandarin"},
    {"q": "Qui a écrit Roméo et Juliette ?", "a": "shakespeare"},
    {"q": "Quelle est la capitale du Japon ?", "a": "tokyo"},
    {"q": "En quelle année l'homme a-t-il marché sur la Lune pour la première fois ?", "a": "1969"},
    {"q": "Quel est le plus grand pays du monde par superficie ?", "a": "russie"},
    {"q": "Combien de joueurs composent une équipe de football ?", "a": "11"},
    {"q": "Quel est le symbole chimique de l'or ?", "a": "au"},
    {"q": "Qui a inventé le téléphone ?", "a": "alexander graham bell"},
    {"q": "Quelle est la montagne la plus haute du monde ?", "a": "everest"},
    {"q": "Dans quel pays se trouve la Grande Muraille ?", "a": "chine"},
    {"q": "Combien de continents y a-t-il sur Terre ?", "a": "7"},
    {"q": "Qui a écrit Harry Potter ?", "a": "jk rowling"},
    {"q": "Quelle est la capitale de l'Australie ?", "a": "canberra"},
    {"q": "Quel est le plus petit pays du monde ?", "a": "vatican"},
    {"q": "En quelle année a eu lieu la Seconde Guerre mondiale ?", "a": "1939"},
    {"q": "Qui a peint La Nuit étoilée ?", "a": "van gogh"},
    {"q": "Quelle est la formule chimique de l'eau ?", "a": "h2o"},
    {"q": "Quel est le pays le plus peuplé du monde ?", "a": "inde"},
    {"q": "Combien de notes y a-t-il dans une octave ?", "a": "8"},
    {"q": "Quelle est la vitesse de la lumière (arrondie) ?", "a": "300000 km/s"},
    {"q": "Qui a écrit L'Odyssée ?", "a": "homere"},
    {"q": "Quelle est la devise de la France ?", "a": "liberte egalite fraternite"},
    {"q": "Quel est le fleuve le plus long du monde ?", "a": "nil/amazone"},
    {"q": "En quelle année a été fondée la compagnie Apple ?", "a": "1976"},
    {"q": "Qui a inventé la relativité générale ?", "a": "einstein"},
    {"q": "Quel est le pays avec le plus de volcans actifs ?", "a": "indonesie"},
    {"q": "Dans quelle ville se trouve le Colisée ?", "a": "rome"},
]


QUIZ_QG = QUIZ_KDRAMA + QUIZ_ANIME + QUIZ_GAMING  # Pour compatibilité

KDRAMA_QUOTES = [
    "\"Même si tu oublies tout, je me souviendrai pour deux.\" — Goblin 🕯️",
    "\"L'amour n'est pas une faiblesse, c'est ta plus grande force.\" — CLOY 🪂",
    "\"La vie est trop courte pour regarder de mauvais dramas.\" — Sagesse du QG 😄",
    "\"Quand tu tombes amoureux d'un drama, tu tombes amoureux d'une culture.\" — Philosophie Kdrama ✨",
    "\"Un bon Kdrama peut guérir n'importe quelle journée difficile.\" — Vérité absolue 🎬",
    "\"Le second lead syndrome est une maladie incurable.\" — Tout le fandom 😭",
]

ANIME_QUOTES = [
    "\"Je ne mourrai pas... C'est toi qui mourras !\" — Monkey D. Luffy ⚓",
    "\"La peur est nécessaire pour vivre.\" — Isayama 🗡️",
    "\"Un héros est quelqu'un qui ne lâche jamais.\" — Deku 💥",
    "\"Je vais devenir le meilleur dresseur... non attends, mauvais anime.\" — Tout le monde 😂",
    "\"Les larmes que tu verses aujourd'hui sont la pluie qui nourrit ta force de demain.\" — Your Lie in April 🎹",
]

ROASTS_QG = [
    "T'es le type qui spoile les Kdramas en vrai... 😤",
    "Tu skip les opening d'anime ? On peut plus rien faire pour toi.",
    "Tu regardes Squid Game et tu dis que c'est le meilleur Kdrama jamais fait. Classique.",
    "Même le second lead te préférerait pas.",
    "Ton tier list de Kdrama est une insulte à toute la Corée.",
    "T'as encore perdu au gacha et tu dis 'c'est biaisé'. On sait. 💀",
    "Ta team LoL a reporté ton profil comme 'menace au Kdrama'.",
]

# ============================================================
#  EVENTS
# ============================================================
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    # XP passif
    uid = str(message.author.id)
    message_count[uid] += 1
    xp_gain = random.randint(4, 10) if double_xp_event_actif else random.randint(2, 5)
    xp_data[uid]["xp"] += xp_gain
    needed = xp_data[uid]["level"] * 100
    if xp_data[uid]["xp"] >= needed:
        xp_data[uid]["level"] += 1
        xp_data[uid]["xp"] = 0
        new_tier = get_tier(xp_data[uid]["level"])
        points_amelio[uid] += 1
        new_level = xp_data[uid]["level"]

        # Barre de progression visuelle niveau
        next_tier_level = next((lvl for lvl, _ in TIERS if lvl > new_level), None)
        if next_tier_level:
            progress = new_level / next_tier_level
            filled = int(progress * 12)
            bar = "▰" * filled + "▱" * (12 - filled)
            next_tier_name = next(t for l, t in TIERS if l == next_tier_level)
            progression_txt = f"`{bar}` → {next_tier_name}"
        else:
            progression_txt = "🌟 **RANG MAXIMUM ATTEINT !**"

        embed = discord.Embed(
            title="",
            description=(
                f"## ⬆️  LEVEL UP  ⬆️\n"
                f"# Niveau **{new_level}** !\n\n"
                f"**{message.author.display_name}** vient de passer au niveau **{new_level}** !\n\n"
                f"✨ Nouveau titre : **{new_tier}**\n\n"
                f"{progression_txt}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🆙 **+1 point d'amélioration** disponible !\n"
                f"*Utilise* `.ameliorer` *pour booster tes stats d'arène*\n"
                f"*(PV • ATK • DEF • Endurance)*\n"
                f"━━━━━━━━━━━━━━━━━━━━"
            ),
            color=0xf1c40f
        )
        embed.set_thumbnail(url=message.author.display_avatar.url)
        embed.set_footer(text=f"⚔️ Points dispo : {points_amelio[uid]}  •  .ameliorer pour les dépenser !")
        # Envoyer dans le salon level up configuré ou dans le salon actuel
        levelup_channel = None
        if SALON_LEVELUP_ID:
            levelup_channel = message.guild.get_channel(SALON_LEVELUP_ID)
        await (levelup_channel or message.channel).send(embed=embed)

    # Jackpot communautaire
    await process_jackpot(message)
    # Clown
    await process_clown(message)
    # Conquête
    await process_conquete(message)
    # Voleur de minuit
    await process_voleur(message)
    await bot.process_commands(message)

@bot.event
async def on_voice_state_update(member, before, after):
    """Track le temps en vocal"""
    import time
    uid = str(member.id)
    if before.channel is None and after.channel is not None:
        # Rejoint un vocal
        voice_join_time[uid] = time.time()
    elif before.channel is not None and after.channel is None:
        # Quitte le vocal
        if uid in voice_join_time:
            minutes = int((time.time() - voice_join_time[uid]) / 60)
            voice_time[uid] += minutes
            del voice_join_time[uid]

# ============================================================
#  HELP — Redesigné par grandes catégories
# ============================================================
@bot.command(name="help")
async def help_cmd(ctx, categorie: str = None):
    """Affiche l'aide — .help"""
    pages = []

    # ── Page 0 — Accueil ─────────────────────────────────
    p0 = discord.Embed(
        title="",
        description=(
            "```\n"
            "╔══════════════════════════════════════╗\n"
            "║                                      ║\n"
            "║    🌸   A K A R I   B O T   🌸      ║\n"
            "║         QG  Kdrama  —  Aide          ║\n"
            "║                                      ║\n"
            "╚══════════════════════════════════════╝\n"
            "```\n"
            "◀️ ▶️ pour naviguer • Préfixe : **`.`**\n\n"
            "```\n"
            "1  — 🎰  Gacha\n"
            "2  — 💰  Économie\n"
            "3  — ⚔️   Combats & Quiz\n"
            "4  — 📊  Progression & Factions\n"
            "5  — 🎪  Events Auto & Spéciaux\n"
            "6  — 🎮  Commandes Events Joueurs\n"
            "7  — 💬  Social & Fun\n"
            "8  — 🛡️   Modération  [ admin ]\n"
            "9  — 🔧  Gacha & Cartes  [ admin ]\n"
            "10 — ⚙️   Économie & Config  [ admin ]\n"
            "```"
        ),
        color=0xff6b9d
    )
    p0.set_footer(text="Page 1/11 • QG Kdrama 🌸")
    pages.append(p0)

    # ── Page 1 — Gacha ────────────────────────────────────
    p1 = discord.Embed(title="🎰 Gacha", color=0x9b59b6)
    p1.add_field(name="🎲 Tirer & Claimer", value=(
        "`.ga` / `.roll` — Tirer une carte\n"
        "`.rolls` — Voir tes rolls restants\n"
        "`.invoke` — Invocation garantie Légendaire+ *(10 000p)*"
    ), inline=False)
    p1.add_field(name="📦 Ta Collection", value=(
        "`.gachastock [@joueur]` — Voir ta collection\n"
        "`.gacha <perso>` — Qui possède ce perso ?\n"
        "`.gachastats` — Classement des collections\n"
        "`.cartefav add/remove/voir <perso>` — Favoris *(max 3)*\n"
        "`.wishlist add/remove/voir <perso>` — Notif si la carte drop"
    ), inline=False)
    p1.add_field(name="🔄 Échanges & Duels", value=(
        "`.gachatrade @joueur <carte1> <carte2>` — Proposer un échange\n"
        "`.tradeshistory` — Historique des échanges\n"
        "`.cardduel @joueur <carte>` — Duel, gagnant prend les 2 cartes\n"
        "`.fusionner <perso>` — Fusionner des doublons\n"
        "`.gachagive @joueur <perso>` — Donner une carte"
    ), inline=False)
    p1.add_field(name="🖼️ Image", value=(
        "`.setimage <perso> <url>` — Changer l\'image de ta carte\n"
        "*Les admins peuvent setimage n\'importe quelle carte*"
    ), inline=False)
    p1.set_footer(text="Page 2/11 • QG Kdrama 🌸")
    pages.append(p1)

    # ── Page 2 — Économie ─────────────────────────────────
    p2 = discord.Embed(title="💰 Économie", color=0xf39c12)
    p2.add_field(name="💵 Gagner des Pièces", value=(
        "`.daily` — 100-200p *(24h)*\n"
        "`.travailler` — 50-150p *(4h)*\n"
        "`.braquage @joueur` — Vol risqué 30% succès *(6h)*\n"
        "`.missions` — Missions journalières\n"
        "`.investir <animé> <montant>` — Investir sur une série\n"
        "`.retourinvest` — Récupérer ses gains\n"
        "`.slot [mise]` — Slot machine 🎰\n"
        "`.jackpot` — Voir la cagnotte communautaire"
    ), inline=False)
    p2.add_field(name="🏦 Banque & Transfers", value=(
        "`.banque depot <montant>` — Déposer *(+10%/24h)*\n"
        "`.banque retrait` — Retirer avec intérêts\n"
        "`.balance [@joueur]` — Voir le solde\n"
        "`.pay @joueur <montant>` — Envoyer des pièces"
    ), inline=False)
    p2.add_field(name="🛒 Boutique & PvP", value=(
        "`.shop` — Catalogue *(3 pages ◀️▶️)*\n"
        "`.acheter <id>` — Acheter un item\n"
        "`.utiliser <item> @joueur` — Utiliser un item offensif\n"
        "`.marcheacheter <perso>` — Marché Noir 🕶️"
    ), inline=False)
    p2.set_footer(text="Page 3/11 • QG Kdrama 🌸")
    pages.append(p2)

    # ── Page 3 — Combats & Quiz ───────────────────────────
    p3 = discord.Embed(title="⚔️ Combats & Quiz", color=0xe74c3c)
    p3.add_field(name="🥊 Combat", value=(
        "`.arene @joueur` — PvP tour par tour\n"
        "`.pokebattle @joueur` — Combat 3v3 avec tes cartes\n"
        "`.cardduel @joueur <carte>` — Duel de cartes\n"
        "`.attaquerboss` — Attaquer le boss envahisseur\n"
        "`.liga` — Classement Elo mensuel"
    ), inline=False)
    p3.add_field(name="🎯 Quiz", value=(
        "`.quiz [thème]` — Quiz solo auto-enchaîné\n"
        "`.quizduel @joueur [thème]` — Duel 5 questions\n"
        "`.quizstop` — Arrêter le quiz en cours\n"
        "*Thèmes : kdrama • anime • gaming • culture • mix*"
    ), inline=False)
    p3.add_field(name="🐺 Loup Garou", value=(
        "`.lgcreate` — Créer une partie\n"
        "`.lgjoin` — Rejoindre la partie\n"
        "`.lgstart` — Lancer la partie *(hôte)*\n"
        "`.lgvote @joueur` — Voter pour éliminer\n"
        "`.lgnuit @cible` — Action nocturne\n"
        "`.lgsorciere save/kill @cible` — Sorcière\n"
        "`.lgstatus` — État de la partie\n"
        "`.lgstop` — Arrêter la partie\n"
        "`.lgroles` — Voir les rôles disponibles"
    ), inline=False)
    p3.add_field(name="🎮 Mini-Jeux", value=(
        "`.devine` — Devine le personnage\n"
        "`.rps <choix>` — Pierre Feuille Ciseaux\n"
        "`.pendu` — Pendu animé/drama"
    ), inline=False)

    p3.set_footer(text="Page 4/11 • QG Kdrama 🌸")
    pages.append(p3)

    # ── Page 4 — Progression & Factions ──────────────────
    p4 = discord.Embed(title="📊 Progression & Factions", color=0xf1c40f)
    p4.add_field(name="📈 XP & Niveaux", value=(
        "`.rank [@joueur]` — Niveau, XP et titre\n"
        "`.leaderboard` — Top 10 membres\n"
        "`.ameliorer` — Booster ses stats d\'arène\n"
        "`.snipe` — Voir le dernier message supprimé"
    ), inline=False)
    p4.add_field(name="⚔️ Factions", value=(
        "`.faction` — Voir les factions disponibles\n"
        "`.faction rejoindre <id>` — Rejoindre une faction\n"
        "`.faction info` — Ta faction & ta réputation\n"
        "`.faction classement` — Classement général"
    ), inline=False)
    p4.set_footer(text="Page 5/11 • QG Kdrama 🌸")
    pages.append(p4)

    # ── Page 5 — Events ───────────────────────────────────
    p5 = discord.Embed(title="🎪 Events — Planning & Liste", color=0x3498db)
    p5.add_field(name="📅 Hebdomadaires", value=(
        "**Lundi** 9h 🔮 Prophétie • 18h 📦 Coffre • 20h 🎲 Event léger\n"
        "**Mardi** 20h 🌙 Nuit Chasse OU 🕶️ Marché Noir\n"
        "**Mercredi** 2h 🌙 Heure Maudite • 19h 🌀 Double XP *(sem. paires)* • 20h 📦 Coffre\n"
        "**Jeudi** 20h 🎲 Event léger • 21h 🎰 Nuit Casino\n"
        "**Vendredi** 18h 🎴 Carte Mystère • 20h 🔥 Gros Event\n"
        "**Samedi** 15h 🎭 Imposteur • 18h 🎴 Carte Mystère • 20h 🔥 Gros Event • 23h ⚠️ Invasion\n"
        "**Dimanche** 16h 📦 Coffre • 17h 🔥 Gros Event • 19h 🎁 Colis Mystère • 20h 🏆 Classement"
    ), inline=False)
    p5.add_field(name="🔄 Rotation Gros Events Weekend", value=(
        "⚔️ Tournoi • 💀 Death Note • 🌍 Conquête\n"
        "⚡ Enchères • 🕵️ Parmi Nous • 🧩 Puzzle\n"
        "*Change chaque semaine — jamais le même 2 semaines de suite !*"
    ), inline=False)
    p5.add_field(name="📆 Mensuels", value=(
        "1er 💸 Jackpot • 8 🃏 Draft • 15 🏴‍☠️ Guerre + 👾 Boss\n"
        "22 🎪 Surprise + 👾 Boss • Dernier ven. 🌊 Vague de Légendes"
    ), inline=False)
    p5.add_field(name="🎭 Events Lançables — `.lancerevent <nom>`", value=(
        "`roue` `proces` `tournoi` `mine` `parminous` `fausserumeur`\n"
        "`encheres` `voleur` `wanted` `reve` `magicien` `clown`\n"
        "`corbeau` `pacifiste` `oracle` `pacte` `losers` `puzzle`\n"
        "`vaguelegendaires` `bossfinal` `deathnote` `alerterouge`\n"
        "`conquete` `prophetie` `colis` `coffre` `nuitcasino`\n"
        "`cartemystere` `doublexp` `nuitchasse` `marchenoir`\n"
        "`jackpot` `draft` `guerre` `heuremaudite` `classement`"
    ), inline=False)
    p5.add_field(name="📅 Planning", value="`.planning` — Voir le planning de la semaine + mois", inline=False)
    p5.set_footer(text="Page 6/11 • QG Kdrama 🌸")
    pages.append(p5)

    # ── Page 6 — Commandes Events Joueurs ─────────────────
    p6 = discord.Embed(title="🎮 Commandes des Events — Joueurs", color=0x9b59b6)
    p6.add_field(name="🕵️ Parmi Nous", value=(
        "`.eliminer @joueur` — Voler une carte *(imposteur only)*\n"
        "`.voter @joueur` — Voter pour éliminer"
    ), inline=True)
    p6.add_field(name="⚡ Enchères & Mine", value=(
        "`.miser <montant>` — Miser dans les enchères\n"
        "`.miner` — Extraire des pépites *(cd 2min)*"
    ), inline=True)
    p6.add_field(name="🎴 Wanted & Death Note", value=(
        "`.chasser @joueur` — Capturer la cible\n"
        "`.ecrire @joueur` — Écrire dans le Death Note"
    ), inline=True)
    p6.add_field(name="🎩 Magicien & Divers", value=(
        "`.sort <type> @joueur` — Lancer un sort *(double/bloquer/troll)*\n"
        "`.jedoute` — Signaler une fausse rumeur\n"
        "`.ouvrir` — Ouvrir un coffre ou colis"
    ), inline=True)
    p6.add_field(name="🦅 Corbeau", value=(
        "`.adopter` — Adopter le corbeau\n"
        "`.nourrir` — Nourrir *(améliore son humeur)*\n"
        "`.caresser` — Caresser *(+XP en réserve)*\n"
        "`.recup` — Récupérer pièces/XP/amélio"
    ), inline=True)
    p6.add_field(name="🏆 Rôles Gagnables", value=(
        "👑 **Champion du QG** — Tournoi *(permanent)*\n"
        "🕵️ **Détective du QG** — Parmi Nous *(permanent)*\n"
        "🧩 **Maître du Puzzle** — Puzzle *(permanent)*\n"
        "🎯 **Chasseur de Primes N°1** — Wanted *(perdable)*\n"
        "⚔️ **Roi de la Conquête** — Conquête *(perdable)*\n"
        "💰 **Baron des Enchères** — Enchères *(permanent)*\n"
        "⚔️ **Pourfendeur de Boss** — Boss Final *(permanent)*\n"
        "☠️ **Porteur du Destin** — Death Note *(permanent)*\n"
        "🌙 **Roi de la Narration** — Rêve Collectif *(permanent)*\n"
        "🎩 **Grand Magicien** — Magicien *(permanent)*\n"
        "🤡 **Clown du QG** — Temporaire"
    ), inline=False)
    p6.set_footer(text="Page 7/11 • QG Kdrama 🌸")
    pages.append(p6)

    # ── Page 7 — Social & Fun ─────────────────────────────
    p7 = discord.Embed(title="💬 Social & Fun", color=0xff6b9d)
    p7.add_field(name="💍 Social", value=(
        "`.marier @joueur` — Demande en mariage\n"
        "`.divorcer` — Divorce 💔\n"
        "`.anniversaire JJ/MM` — Enregistrer son anniv\n"
        "`.avatar [@joueur]` — Voir la photo de profil"
    ), inline=True)
    p7.add_field(name="😄 Fun", value=(
        "`.roast [@joueur]` — Vanne façon animé\n"
        "`.compliment [@joueur]` — Compliment stylé\n"
        "`.8ball <question>` — Boule magique\n"
        "`.meme` — Meme aléatoire 😂"
    ), inline=True)
    p7.add_field(name="🎬 Contenu", value=(
        "`.drama <titre>` — Infos drama\n"
        "`.anime <titre>` — Infos animé\n"
        "`.dramarec` / `.animerec` — Recommandation\n"
        "`.quote` / `.animequote` — Citation\n"
        "`.sorties` — Prochaines sorties"
    ), inline=True)
    p7.set_footer(text="Page 8/11 • QG Kdrama 🌸")
    pages.append(p7)

    # ── Page 8 — Modération (Admin) ───────────────────────
    p8 = discord.Embed(title="🛡️ Modération", description="⚠️ Réservé aux **admins**", color=0xe74c3c)
    p8.add_field(name="⚔️ Sanctions", value=(
        "`.ban @joueur [raison]` — Bannir\n"
        "`.kick @joueur [raison]` — Expulser\n"
        "`.warn @joueur [raison]` — Avertir\n"
        "`.mute @joueur [minutes]` — Mute\n"
        "`.unmute @joueur` — Retirer le mute"
    ), inline=True)
    p8.add_field(name="🔧 Salon", value=(
        "`.clear [nb]` / `.clear all` — Suppr messages\n"
        "`.slowmode [secondes]` — Slowmode\n"
        "`.lock` / `.unlock` — Verrouiller\n"
        "`.snipe` — Dernier message supprimé"
    ), inline=True)
    p8.add_field(name="🎭 Autorole & Config", value=(
        "`.autorole create <titre> | <desc>`\n"
        "`.autorole add <msg_id> <emoji> @role`\n"
        "`.autorole image <msg_id> <url>`\n"
        "`.autorole delete/list`\n\n"
        "`.setsalon <type>` — Configurer un salon\n"
        "`.setinvitation` — Activer le suivi invitations"
    ), inline=False)
    p8.set_footer(text="Page 9/11 • QG Kdrama 🌸")
    pages.append(p8)

    # ── Page 9 — Admin Gacha & Cartes ─────────────────────
    p9 = discord.Embed(title="🔧 Admin — Gacha & Cartes", description="⚠️ Réservé aux **admins**", color=0x9b59b6)
    p9.add_field(name="🎁 Donner / Retirer", value=(
        "`.givecard @joueur <perso>` — Donner une carte\n"
        "`.removecard @joueur <perso>` — Retirer une carte\n"
        "`.gacharesetall` — Reset total gacha ⚠️"
    ), inline=False)
    p9.add_field(name="✨ Créer & Modifier", value=(
        "`.addcard <nom> | <serie> | <rarete> | <emoji> | <url>`\n"
        "*Crée une carte custom — stats calculées auto*\n"
        "*Ex : `.addcard Sensei | QG Kdrama | Mythique | 👑 | url`*\n\n"
        "`.setimage <perso> <url>` — Changer l\'image d\'une carte\n"
        "*Admins : modifiable sans posséder la carte*"
    ), inline=False)
    p9.add_field(name="📋 Raretés valides", value=(
        "`Commun` • `Rare` • `Épique` • `Légendaire` • `Mythique`"
    ), inline=False)
    p9.add_field(name="Images en masse", value="`.setimages` — Ajouter images a plusieurs cartes", inline=False)
    p9.set_footer(text="Page 10/11 • QG Kdrama 🌸")
    pages.append(p9)

    # ── Page 10 — Admin Économie & Events ─────────────────
    p10 = discord.Embed(title="⚙️ Admin — Économie & Events", description="⚠️ Réservé aux **admins**", color=0x2ecc71)
    p10.add_field(name="💰 Économie", value=(
        "`.givepieces @joueur <montant>` — Donner des pièces\n"
        "`.retirerpieces @joueur <montant>` — Retirer des pièces\n"
        "`.givexp @joueur <montant>` — Donner de l\'XP\n"
        "`.retirerxp @joueur <montant>` — Retirer de l\'XP\n"
        "`.resetall` — Reset total pièces + XP + gacha ⚠️"
    ), inline=False)
    p10.add_field(name="🎪 Events", value=(
        "`.lancerevent <nom>` — Lancer un event manuellement\n"
        "`.lancerevent` — Liste de tous les events disponibles\n"
        "`.stopervent` — Arrêter l\'event en cours immédiatement\n\n"
        "`.setsalon <type>` — Configurer les salons\n"
        "*Types : gacha • boutique • casino • event • guide*\n"
        "*levelup • combat • bienvenue • aurevoir • boost*\n"
        "*halloffame • reglement @Role*"
    ), inline=False)
    p10.set_footer(text="Page 11/11 • QG Kdrama 🌸")
    pages.append(p10)



    index = [0]
    msg = await ctx.send(embed=pages[0])
    await msg.add_reaction("◀️")
    await msg.add_reaction("▶️")

    def check(reaction, user):
        return user == ctx.author and reaction.message.id == msg.id and str(reaction.emoji) in ["◀️", "▶️"]

    while True:
        try:
            reaction, user = await bot.wait_for("reaction_add", timeout=60.0, check=check)
            if str(reaction.emoji) == "▶️":
                index[0] = (index[0] + 1) % len(pages)
            elif str(reaction.emoji) == "◀️":
                index[0] = (index[0] - 1) % len(pages)
            await msg.edit(embed=pages[index[0]])
            try:
                await msg.remove_reaction(reaction.emoji, user)
            except:
                pass
        except asyncio.TimeoutError:
            try:
                await msg.clear_reactions()
            except:
                pass
            break


@bot.command(name="setimage")
async def setimage_cmd(ctx, *, args: str = None):
    """Change l'image d'une carte que tu possèdes — .setimage <perso> <url>"""
    if SALON_GACHA_ID and ctx.channel.id != SALON_GACHA_ID:
        salon = ctx.guild.get_channel(SALON_GACHA_ID)
        mention = salon.mention if salon else "le salon gacha"
        return await ctx.send(f"🎰 Cette commande c'est dans {mention} !", delete_after=5)

    if not args:
        return await ctx.send("❌ Usage : `.setimage <perso> <url imgur>`\nEx: `.setimage Nagumo Hajime https://i.imgur.com/xxx.jpg`")

    # Séparer le dernier mot (l'URL) du reste (le nom du perso)
    parts = args.strip().rsplit(" ", 1)
    if len(parts) < 2:
        return await ctx.send("❌ Usage : `.setimage <perso> <url imgur>`\nEx: `.setimage Nagumo Hajime https://i.imgur.com/xxx.jpg`")

    perso = parts[0].strip()
    url = parts[1].strip().strip("_").strip("*").strip("<").strip(">").strip()

    if not url.startswith("https://i.imgur.com/"):
        return await ctx.send("❌ Utilise uniquement des liens **imgur** ! (https://i.imgur.com/...)")

    uid = str(ctx.author.id)
    is_admin = ctx.author.guild_permissions.administrator
    key = perso.lower().strip()

    if key not in ANIME_CARDS_DB:
        matches = [k for k in ANIME_CARDS_DB if perso.lower() in ANIME_CARDS_DB[k]["nom"].lower()]
        if not matches:
            return await ctx.send(f"❌ Personnage `{perso}` introuvable !")
        key = matches[0]

    # Admin peut setimage sans posséder la carte
    if not is_admin:
        if claimed_cards.get(key) != uid:
            c = ANIME_CARDS_DB[key]
            owner_uid = claimed_cards.get(key)
            if owner_uid:
                member = ctx.guild.get_member(int(owner_uid))
                owner = member.display_name if member else "quelqu'un d'autre"
                return await ctx.send(f"❌ Tu ne possèdes pas **{c['nom']}** — elle appartient à **{owner}** !")
            else:
                return await ctx.send(f"❌ Tu ne possèdes pas **{c['nom']}** — personne ne la possède !")

    ANIME_CARDS_DB[key]["image"] = url
    c = ANIME_CARDS_DB[key]
    embed = discord.Embed(
        description=f"🖼️ L'image de **{c['nom']}** a été mise à jour !",
        color=RARETE_COULEURS.get(c["rarete"], 0x9b59b6)
    )
    embed.set_image(url=url)
    await ctx.send(embed=embed)

# ── givecard ──────────────────────────────────────────────────────
@bot.command(name="givecard")
@commands.has_permissions(administrator=True)
async def givecard_cmd(ctx, membre: discord.Member = None, *, perso: str = None):
    """Donne une carte à un membre — admin only"""
    if not membre or not perso:
        return await ctx.send("❌ Usage : `.givecard @joueur <perso>`\nEx: `.givecard @Ryaax naruto`")

    key = perso.lower().strip().replace(" ", "")
    if key not in ANIME_CARDS_DB:
        matches = [k for k in ANIME_CARDS_DB if perso.lower() in ANIME_CARDS_DB[k]["nom"].lower()]
        if not matches:
            return await ctx.send(f"❌ Personnage `{perso}` introuvable !")
        key = matches[0]

    c = ANIME_CARDS_DB[key]
    uid = str(membre.id)
    rarete_emoji = RARETE_EMOJI.get(c["rarete"], "🔵")
    couleur = RARETE_COULEURS.get(c["rarete"], 0x95a5a6)

    # Si déjà claimée par quelqu'un d'autre
    if key in claimed_cards and claimed_cards[key] != uid:
        old_uid = claimed_cards[key]
        old_member = ctx.guild.get_member(int(old_uid))
        old_name = old_member.display_name if old_member else f"<@{old_uid}>"
        # Retirer de l'ancienne collection
        if key in gacha_collections.get(old_uid, {}):
            del gacha_collections[old_uid][key]

    claimed_cards[key] = uid
    if key not in gacha_collections[uid]:
        gacha_collections[uid][key] = {"fusion": 0}

    embed = discord.Embed(
        title=f"🎁 Carte offerte !",
        description=(
            f"{rarete_emoji} **{c['nom']}** a été donnée à {membre.mention} !\n"
            f"*{c['serie']}* — **{c['rarete']}**"
        ),
        color=couleur
    )
    if c.get("image"):
        embed.set_thumbnail(url=c["image"])
    embed.set_footer(text=f"Don effectué par {ctx.author.display_name} 🎌")
    await ctx.send(embed=embed)

# ── removecard ────────────────────────────────────────────────────
@bot.command(name="removecard")
@commands.has_permissions(administrator=True)
async def removecard_cmd(ctx, membre: discord.Member = None, *, perso: str = None):
    """Retire une carte à un membre — admin only"""
    if not membre or not perso:
        return await ctx.send("❌ Usage : `.removecard @joueur <perso>`\nEx: `.removecard @Ryaax naruto`")

    key = perso.lower().strip().replace(" ", "")
    if key not in ANIME_CARDS_DB:
        matches = [k for k in ANIME_CARDS_DB if perso.lower() in ANIME_CARDS_DB[k]["nom"].lower()]
        if not matches:
            return await ctx.send(f"❌ Personnage `{perso}` introuvable !")
        key = matches[0]

    c = ANIME_CARDS_DB[key]
    uid = str(membre.id)
    rarete_emoji = RARETE_EMOJI.get(c["rarete"], "🔵")
    couleur = RARETE_COULEURS.get(c["rarete"], 0x95a5a6)

    # Vérifier que le membre possède bien la carte
    if claimed_cards.get(key) != uid:
        owner_uid = claimed_cards.get(key)
        if owner_uid:
            owner = ctx.guild.get_member(int(owner_uid))
            owner_name = owner.display_name if owner else f"<@{owner_uid}>"
            return await ctx.send(f"❌ **{membre.display_name}** ne possède pas **{c['nom']}** — elle appartient à **{owner_name}** !")
        else:
            return await ctx.send(f"❌ **{c['nom']}** n'est possédée par personne !")

    # Retirer la carte
    del claimed_cards[key]
    if key in gacha_collections.get(uid, {}):
        del gacha_collections[uid][key]
    if key in fusion_levels.get(uid, {}):
        del fusion_levels[uid][key]

    embed = discord.Embed(
        title="🗑️ Carte retirée !",
        description=(
            f"{rarete_emoji} **{c['nom']}** a été retirée de la collection de {membre.mention}.\n"
            f"*{c['serie']}* — **{c['rarete']}**\n\n"
            f"La carte est à nouveau disponible pour tout le monde."
        ),
        color=couleur
    )
    if c.get("image"):
        embed.set_thumbnail(url=c["image"])
    embed.set_footer(text=f"Action effectuée par {ctx.author.display_name} 🛡️")
    await ctx.send(embed=embed)


# ============================================================
#  QUIZ QG — Par catégorie + Mode Duel 1v1 + Multijoueur
# ============================================================
active_quiz = {}
quiz_duels = {}  # {channel_id: {players, scores, theme, round, total_rounds}}

QUIZ_THEMES = {
    "kdrama": QUIZ_KDRAMA,
    "anime": QUIZ_ANIME,
    "gaming": QUIZ_GAMING,
    "culture": QUIZ_CULTURE,
    "mix": QUIZ_KDRAMA + QUIZ_ANIME + QUIZ_GAMING + QUIZ_CULTURE,
}

THEME_LABELS = {
    "kdrama": "🎬 Kdrama",
    "anime": "✨ Animé",
    "gaming": "🎮 Gaming",
    "culture": "🌍 Culture Générale",
    "mix": "🎲 Mix",
}


@bot.command(name="quiz", aliases=["q"])
async def quiz(ctx, theme: str = "mix"):
    """Quiz solo en continu — .quiz [kdrama/anime/gaming/culture/mix]"""
    theme = theme.lower()
    if theme not in QUIZ_THEMES:
        return await ctx.send(f"❌ Thème invalide ! Choisis : `kdrama` `anime` `gaming` `culture` `mix`")
    if ctx.channel.id in active_quiz or ctx.channel.id in quiz_duels:
        return await ctx.send("❓ Un quiz est déjà en cours ici ! Tape `.quizstop` pour l'arrêter.")

    active_quiz[ctx.channel.id] = {"theme": theme, "running": True}
    questions_posees = []

    await ctx.send(embed=discord.Embed(
        description=f"🎯 Quiz **{THEME_LABELS[theme]}** lancé ! Tape `.quizstop` pour arrêter.\n⏳ 30 secondes par question — les questions s'enchaînent automatiquement !",
        color=0xf1c40f
    ))

    def check(m):
        return m.channel == ctx.channel and not m.author.bot

    while ctx.channel.id in active_quiz and active_quiz[ctx.channel.id].get("running"):
        # Piocher une question pas encore posée
        disponibles = [q for q in QUIZ_THEMES[theme] if q["q"] not in questions_posees]
        if not disponibles:
            questions_posees = []
            disponibles = QUIZ_THEMES[theme]

        q = random.choice(disponibles)
        questions_posees.append(q["q"])
        active_quiz[ctx.channel.id]["answer"] = q["a"]

        embed = discord.Embed(
            title=f"🎯 Quiz {THEME_LABELS[theme]}",
            description=f"**{q['q']}**",
            color=0xf1c40f
        )
        embed.set_footer(text="⏳ 30 secondes • Tape `.quizstop` pour arrêter")
        await ctx.send(embed=embed)

        try:
            while True:
                msg = await bot.wait_for("message", check=check, timeout=30)

                # Vérifier si le quiz a été stoppé pendant l'attente
                if ctx.channel.id not in active_quiz:
                    return

                correct = active_quiz[ctx.channel.id].get("answer", "")

                reponse = msg.content.lower().strip()
                if check_answer(reponse, correct):
                    prize = random.randint(30, 80)
                    economy_data[str(msg.author.id)]["coins"] += prize
                    xp_data[str(msg.author.id)]["xp"] += 30
                    await ctx.send(embed=discord.Embed(
                        description=f"✅ **{msg.author.display_name}** a trouvé ! **+{prize} pièces & +30 XP** 🎉\n*Prochaine question dans 3 secondes...*",
                        color=0x2ecc71
                    ))
                    break
                else:
                    # Mauvaise réponse → skip direct
                    await msg.add_reaction("❌")
                    await ctx.send(embed=discord.Embed(
                        description=f"❌ Mauvaise réponse ! La bonne réponse était : **{correct}**\n*Prochaine question dans 3 secondes...*",
                        color=0xe74c3c
                    ))
                    break

        except asyncio.TimeoutError:
            if ctx.channel.id not in active_quiz:
                return
            correct = active_quiz[ctx.channel.id].get("answer", "")
            await ctx.send(embed=discord.Embed(
                description=f"⏰ Temps écoulé ! La réponse était : **{correct}**\n*Prochaine question dans 3 secondes...*",
                color=0xe74c3c
            ))

        await asyncio.sleep(3)

@bot.command(name="quizstop")
async def quiz_stop(ctx):
    """Arrête le quiz en cours — .quizstop"""
    if ctx.channel.id in active_quiz:
        active_quiz.pop(ctx.channel.id, None)
        await ctx.send(embed=discord.Embed(
            description="🛑 Quiz arrêté !",
            color=0xe74c3c
        ))
    elif ctx.channel.id in quiz_duels:
        quiz_duels.pop(ctx.channel.id, None)
        await ctx.send(embed=discord.Embed(
            description="🛑 Quiz duel arrêté !",
            color=0xe74c3c
        ))
    else:
        await ctx.send("❌ Aucun quiz en cours ici !")



@bot.command(name="quizduel")
async def quiz_duel(ctx, theme: str = "mix", *opponents: discord.Member):
    """Duel quiz — .quizduel [theme] @joueur1 @joueur2 ...
    Ex: .quizduel kdrama @ami
    Ex: .quizduel anime @ami1 @ami2 @ami3"""
    theme = theme.lower()
    if theme not in QUIZ_THEMES:
        # Peut-être que c'est une mention pas un thème
        return await ctx.send(
            "❌ Utilise : `.quizduel <thème> @joueur1 @joueur2 ...`\n"
            "Thèmes : `kdrama` `anime` `gaming` `culture` `mix`\n"
            "Exemple : `.quizduel kdrama @ami`"
        )
    if not opponents:
        return await ctx.send("❌ Mentionne au moins un adversaire !\nEx: `.quizduel anime @ami`")
    if ctx.channel.id in active_quiz or ctx.channel.id in quiz_duels:
        return await ctx.send("❓ Un quiz est déjà en cours ici !")

    # Liste des joueurs : auteur + adversaires
    all_players = [ctx.author] + list(opponents)
    # Filtrer les bots
    all_players = [p for p in all_players if not p.bot]
    if len(all_players) < 2:
        return await ctx.send("❌ Il faut au moins 2 joueurs humains !")

    TOTAL_ROUNDS = 5
    quiz_duels[ctx.channel.id] = {
        "players": {p.id: {"name": p.display_name, "score": 0} for p in all_players},
        "theme": theme,
        "round": 0,
        "total": TOTAL_ROUNDS,
        "questions_used": [],
    }

    players_str = " vs ".join([f"**{p.display_name}**" for p in all_players])
    embed = discord.Embed(
        title=f"⚔️ Quiz Duel — {THEME_LABELS[theme]}",
        description=(
            f"{players_str}\n\n"
            f"**{TOTAL_ROUNDS} questions • Premier à répondre marque un point !**\n\n"
            "La partie commence dans 3 secondes... 🎯"
        ),
        color=0xff6b9d
    )
    await ctx.send(embed=embed)
    await asyncio.sleep(3)

    # Boucle des rounds
    player_ids = set(p.id for p in all_players)

    for round_num in range(1, TOTAL_ROUNDS + 1):
        if ctx.channel.id not in quiz_duels:
            break

        # Choisir une question pas encore posée
        available = [q for q in QUIZ_THEMES[theme] if q["a"] not in quiz_duels[ctx.channel.id]["questions_used"]]
        if not available:
            available = QUIZ_THEMES[theme]
        q = random.choice(available)
        quiz_duels[ctx.channel.id]["questions_used"].append(q["a"])

        embed = discord.Embed(
            title=f"🎯 Round {round_num}/{TOTAL_ROUNDS} — {THEME_LABELS[theme]}",
            description=f"**{q['q']}**",
            color=0xf1c40f
        )
        # Afficher le score actuel
        scores = quiz_duels[ctx.channel.id]["players"]
        score_str = " | ".join([f"{data['name']}: {data['score']}" for data in scores.values()])
        embed.set_footer(text=f"⏳ 20 secondes • Scores: {score_str}")
        await ctx.send(embed=embed)

        def check_duel(m):
            return m.channel == ctx.channel and m.author.id in player_ids and not m.author.bot

        answered = False
        end_time = asyncio.get_event_loop().time() + 20
        while not answered:
            remaining = end_time - asyncio.get_event_loop().time()
            if remaining <= 0:
                await ctx.send(embed=discord.Embed(
                    description=f"⏰ Temps écoulé ! La réponse était : **{q['a']}**",
                    color=0x95a5a6
                ))
                break
            try:
                msg = await bot.wait_for("message", check=check_duel, timeout=remaining)
                if ctx.channel.id not in quiz_duels:
                    break
                if check_answer(msg.content, q["a"]):
                    quiz_duels[ctx.channel.id]["players"][msg.author.id]["score"] += 1
                    score = quiz_duels[ctx.channel.id]["players"][msg.author.id]["score"]
                    await ctx.send(embed=discord.Embed(
                        description=f"✅ **{msg.author.display_name}** a trouvé ! ({score} pt{'s' if score > 1 else ''})",
                        color=0x2ecc71
                    ))
                    answered = True
                # Mauvaise réponse → on continue à écouter les autres
            except asyncio.TimeoutError:
                await ctx.send(embed=discord.Embed(
                    description=f"⏰ Temps écoulé ! La réponse était : **{q['a']}**",
                    color=0x95a5a6
                ))
                break

        await asyncio.sleep(2)

    # Fin du duel
    if ctx.channel.id not in quiz_duels:
        return

    final_scores = quiz_duels.pop(ctx.channel.id)["players"]
    sorted_scores = sorted(final_scores.values(), key=lambda x: x["score"], reverse=True)

    # Trouver le gagnant
    top_score = sorted_scores[0]["score"]
    winners = [p for p in sorted_scores if p["score"] == top_score]

    if len(winners) > 1:
        result = f"🤝 **Égalité !** {' et '.join([w['name'] for w in winners])} avec {top_score} point{'s' if top_score > 1 else ''} !"
        prize = 50
        for p in all_players:
            if final_scores[p.id]["score"] == top_score:
                economy_data[str(p.id)]["coins"] += prize
    else:
        winner = winners[0]
        result = f"🏆 **{winner['name']}** remporte le duel avec **{winner['score']} point{'s' if winner['score'] > 1 else ''}** !"
        # Donner des pièces au gagnant
        winner_id = next(pid for pid, data in final_scores.items() if data["name"] == winner["name"])
        prize = random.randint(80, 150)
        economy_data[str(winner_id)]["coins"] += prize
        xp_data[str(winner_id)]["xp"] += 50
        result += f"\n💰 +{prize} pièces & +50 XP !"

    embed = discord.Embed(
        title="🏆 Résultats du Quiz Duel !",
        description=result,
        color=0xf1c40f
    )
    scores_final = "\n".join([f"{'🥇' if i==0 else '🥈' if i==1 else '🥉' if i==2 else '▪️'} **{p['name']}** — {p['score']} pt{'s' if p['score'] > 1 else ''}" for i, p in enumerate(sorted_scores)])
    embed.add_field(name="📊 Classement final", value=scores_final, inline=False)
    await ctx.send(embed=embed)



# ============================================================
#  NIVEAUX / XP
# ============================================================
@bot.command(name="rank", aliases=["niveau","xp","profil"])
async def rank(ctx, member: discord.Member = None):
    member = member or ctx.author
    uid = str(member.id)
    lvl = xp_data[uid]["level"]
    xp = xp_data[uid]["xp"]
    needed = lvl * 100
    bar = "█" * int((xp / needed) * 20) + "░" * (20 - int((xp / needed) * 20))
    tier = get_tier(lvl)
    s = arena_stats[uid]
    pts = points_amelio[uid]
    hp_total  = 250 + s["pv_bonus"]  * 8
    end_total = 100 + s["end_bonus"] * 5
    embed = discord.Embed(title=f"📊 Fiche de {member.display_name}", color=0xff6b9d)
    embed.add_field(name="Titre", value=tier, inline=False)
    embed.add_field(name="Niveau", value=str(lvl))
    embed.add_field(name="XP", value=f"{xp}/{needed}")
    embed.add_field(name="Progression", value=f"`{bar}`", inline=False)
    embed.add_field(name="⚔️ Stats Arène", value=(
        f"❤️ **PV** : {hp_total} *(+{s['pv_bonus']*8})*\n"
        f"⚡ **Endurance** : {end_total} *(+{s['end_bonus']*5})*\n"
        f"🗡️ **ATK bonus** : +{s['atk_bonus']*3}\n"
        f"🛡️ **DEF bonus** : +{s['def_bonus']*3}\n"
        f"🆙 **Points dispo** : **{pts}**"
    ), inline=False)
    embed.set_footer(text="Utilise .ameliorer pour dépenser tes points !" if pts > 0 else "Gagne de l'XP pour obtenir des points d'amélioration !")
    embed.set_thumbnail(url=member.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name="ameliorer", aliases=["amelio", "upgrade", "up"])
async def ameliorer(ctx, stat: str = None):
    """Dépense tes points d'amélioration — .ameliorer <pv|atk|def|endurance>"""
    uid = str(ctx.author.id)
    pts = points_amelio[uid]
    s = arena_stats[uid]

    stats_valides = {
        "pv":        ("pv_bonus",  "❤️ PV",         "+8 HP max"),
        "atk":       ("atk_bonus", "🗡️ Attaque",    "+3 ATK"),
        "def":       ("def_bonus", "🛡️ Défense",    "+3 DEF"),
        "endurance": ("end_bonus", "⚡ Endurance",   "+5 END max"),
        "end":       ("end_bonus", "⚡ Endurance",   "+5 END max"),
    }

    # Affichage sans argument
    if not stat:
        embed = discord.Embed(
            title="🆙 Points d'amélioration",
            description=(
                f"Tu as **{pts} point(s)** disponible(s) !\n\n"
                f"Utilise `.ameliorer <stat>` pour dépenser un point :\n\n"
                f"`.ameliorer pv` — ❤️ **+8 HP max** *(actuellement {120 + s['pv_bonus']*8})*\n"
                f"`.ameliorer atk` — 🗡️ **+3 ATK bonus** *(actuellement +{s['atk_bonus']*3})*\n"
                f"`.ameliorer def` — 🛡️ **+3 DEF bonus** *(actuellement +{s['def_bonus']*3})*\n"
                f"`.ameliorer endurance` — ⚡ **+5 END max** *(actuellement {100 + s['end_bonus']*5})*\n\n"
                f"*1 point = 1 amélioration. Points gagnés à chaque level up !*"
            ),
            color=0x3498db
        )
        embed.set_footer(text="💡 Gagne des niveaux avec .daily .quiz .boss .arene !")
        return await ctx.send(embed=embed)

    stat = stat.lower()
    if stat not in stats_valides:
        return await ctx.send(
            f"❌ Stat invalide ! Choisis : `pv` • `atk` • `def` • `endurance`\n"
            f"Ex : `.ameliorer pv`"
        )

    if pts <= 0:
        return await ctx.send(embed=discord.Embed(
            description="❌ Tu n'as pas de points d'amélioration disponibles !\nGagne des niveaux pour en obtenir 🆙",
            color=0xe74c3c
        ))

    cle, label, effet = stats_valides[stat]
    s[cle] += 1
    points_amelio[uid] -= 1

    hp_total  = 250 + s["pv_bonus"]  * 8
    end_total = 100 + s["end_bonus"] * 5

    embed = discord.Embed(
        title="✅ Amélioration appliquée !",
        description=(
            f"**{label}** améliorée — **{effet}** !\n\n"
            f"❤️ **PV max** : {hp_total}\n"
            f"⚡ **END max** : {end_total}\n"
            f"🗡️ **ATK bonus** : +{s['atk_bonus']*3}\n"
            f"🛡️ **DEF bonus** : +{s['def_bonus']*3}\n\n"
            f"*Points restants : **{points_amelio[uid]}***"
        ),
        color=0x2ecc71
    )
    embed.set_footer(text="⚔️ Ces stats sont actives dans l'arène !")
    await ctx.send(embed=embed)



@bot.command(name="leaderboard", aliases=["top","classement","lb"])
async def leaderboard(ctx):
    sorted_data = sorted(xp_data.items(), key=lambda x: (x[1]["level"], x[1]["xp"]), reverse=True)[:10]
    desc = ""
    medals = ["🥇", "🥈", "🥉"]
    for i, (uid, data) in enumerate(sorted_data):
        medal = medals[i] if i < 3 else f"`{i+1}.`"
        try:
            user = await bot.fetch_user(int(uid))
            name = user.display_name
        except:
            name = f"Membre#{uid[:4]}"
        tier = get_tier(data["level"])
        desc += f"{medal} **{name}** — Niv.{data['level']} {tier}\n"
    await ctx.send(embed=discord.Embed(
        title="🏆 Classement QG Kdrama",
        description=desc or "Aucune donnée",
        color=0xf1c40f
    ))

# ============================================================
#  BOUTIQUE — ITEMS
# ============================================================
SHOP_ITEMS = [
    # ── Rôles exclusifs ──────────────────────────────────────
    {"id": "vip",          "nom": "⭐ VIP",                   "prix": 3000,  "desc": "Rôle VIP exclusif",              "cat": "role",   "daily": False},
    {"id": "drama_king",   "nom": "👑 Drama King",             "prix": 5000,  "desc": "Rôle Drama King légendaire",     "cat": "role",   "daily": False},
    {"id": "otaku",        "nom": "🌀 Oeil de Dieu",           "prix": 4000,  "desc": "Rôle Otaku ultime",              "cat": "role",   "daily": False},
    {"id": "gamer_pro",    "nom": "⚔️ Chasseur National",      "prix": 4500,  "desc": "Rôle Chasseur d'élite",         "cat": "role",   "daily": False},
    {"id": "shadow",       "nom": "🌑 Monarque des Ombres",    "prix": 6000,  "desc": "Rôle le plus rare",              "cat": "role",   "daily": False},
    {"id": "pillier",      "nom": "🔥 Pillier du Soleil",      "prix": 5500,  "desc": "Rôle Hashira légendaire",        "cat": "role",   "daily": False},
    # ── Boosts gacha ─────────────────────────────────────────
    {"id": "rolls_5",      "nom": "🎰 +5 Rolls",               "prix": 800,   "desc": "+5 rolls bonus",                 "cat": "boost",  "daily": False},
    {"id": "boost_rarete", "nom": "🎯 Boost Rareté",           "prix": 1200,  "desc": "×2 chance rares (5 rolls)",      "cat": "boost",  "daily": True},
    {"id": "double_xp",    "nom": "⚡ Double XP",               "prix": 600,   "desc": "Double XP pendant 1h",           "cat": "boost",  "daily": True},
    {"id": "oracle",       "nom": "🔮 Oracle",                  "prix": 2000,  "desc": "Révèle une carte cachée",        "cat": "boost",  "daily": True},
    {"id": "cadeau",       "nom": "🎁 Cadeau Mystère",          "prix": 1500,  "desc": "Carte Rare+ aléatoire",          "cat": "boost",  "daily": True},
    # ── Items PvP ────────────────────────────────────────────
    {"id": "freeze",       "nom": "❄️ Freeze",                  "prix": 1000,  "desc": "Bloque les cmds 30min",          "cat": "pvp",    "daily": True},
    {"id": "curse",        "nom": "💀 Malédiction",             "prix": 1200,  "desc": "-50% pièces cible",              "cat": "pvp",    "daily": True},
    {"id": "cadenas",      "nom": "🔒 Cadenas",                 "prix": 800,   "desc": "Bloque le claim 30min",          "cat": "pvp",    "daily": True},
    {"id": "bombe_gacha",  "nom": "💣 Bombe Gacha",             "prix": 2500,  "desc": "Force une perte de carte",       "cat": "pvp",    "daily": True},
    {"id": "vol_roll",     "nom": "🃏 Vol de Roll",             "prix": 900,   "desc": "Vole 2 rolls à la cible",        "cat": "pvp",    "daily": True},
    # ── Protection ───────────────────────────────────────────
    {"id": "protection",   "nom": "🌟 Protection Divine",       "prix": 2000,  "desc": "Immunité totale 2h",             "cat": "protect","daily": True},
    {"id": "amulette",     "nom": "🪬 Amulette",                "prix": 1800,  "desc": "Renvoie les attaques 20min",     "cat": "protect","daily": True},
    {"id": "shield",       "nom": "🛡️ Bouclier",               "prix": 1000,  "desc": "Bloque 1 attaque 30min",         "cat": "protect","daily": True},
    # ── Spéciaux ─────────────────────────────────────────────
    {"id": "double_rien",  "nom": "🎰 Double ou Rien",          "prix": 500,   "desc": "Double ou perd tes rolls",       "cat": "special","daily": True},
    {"id": "claim_10",     "nom": "⏱️ Claim -10min",            "prix": 2000,  "desc": "Réduit claim à 10min",           "cat": "special","daily": False},
]


# ============================================================
#  ÉCONOMIE
# ============================================================
@bot.command(name="daily", aliases=["journalier"])
async def daily(ctx):
    """Pièces journalières + roll bonus gacha"""
    uid = str(ctx.author.id)
    import time as _time
    now_dt = datetime.datetime.utcnow()
    now_ts = _time.time()

    # Pièces journalières
    last = cooldowns.get(f"daily_{uid}")
    if last and (now_dt - last).total_seconds() < 86400:
        reste = 86400 - (now_dt - last).total_seconds()
        h, m = divmod(int(reste) // 60, 60)
        return await ctx.send(f"⏳ Reviens dans **{h}h {m}m** pour tes pièces journalières !")

    gain = random.randint(150, 300)
    economy_data[uid]["coins"] += gain
    cooldowns[f"daily_{uid}"] = now_dt

    # Roll bonus gacha
    data = roll_data[uid]
    if now_ts - data["daily_reset"] >= 86400:
        data["daily_used"] = False
        data["daily_reset"] = now_ts

    roll_msg = ""
    if not data["daily_used"]:
        data["daily_used"] = True
        data["rolls"] = min(data["rolls"] + 1, ROLLS_MAX + 1)
        roll_msg = f"\n🎰 +1 roll bonus ! Tu as **{data['rolls']} rolls** disponibles"

    await ctx.send(embed=discord.Embed(
        description=f"💰 {ctx.author.mention} reçoit **{gain} pièces** ! Total : {economy_data[uid]['coins']}{roll_msg}",
        color=0x2ecc71
    ))

@bot.command(name="balance", aliases=["solde","pieces","coins"])
async def balance(ctx, member: discord.Member = None):
    member = member or ctx.author
    coins = economy_data[str(member.id)]["coins"]
    await ctx.send(embed=discord.Embed(
        description=f"💳 **{member.display_name}** possède **{coins} pièces**.",
        color=0xf39c12
    ))

@bot.command(name="pay", aliases=["donner","transfer"])
async def pay(ctx, member: discord.Member, amount: int):
    uid = str(ctx.author.id)
    if economy_data[uid]["coins"] < amount:
        return await ctx.send("❌ Pas assez de pièces !")
    economy_data[uid]["coins"] -= amount
    economy_data[str(member.id)]["coins"] += amount
    await ctx.send(embed=discord.Embed(
        description=f"💸 **{ctx.author.display_name}** a envoyé **{amount} pièces** à **{member.display_name}**.",
        color=0x27ae60
    ))

# ============================================================
#  MUSIQUE
# ============================================================
try:
    import yt_dlp
    MUSIC_AVAILABLE = True
except ImportError:
    MUSIC_AVAILABLE = False

YTDL_OPTS = {'format': 'bestaudio/best', 'quiet': True, 'noplaylist': True, 'default_search': 'ytsearch'}
FFMPEG_OPTS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

async def play_next(guild_id, channel):
    if queues[guild_id]:
        url, title = queues[guild_id].pop(0)
        vc = voice_clients.get(guild_id)
        if vc:
            source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTS)
            vc.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(guild_id, channel), bot.loop))
            await channel.send(embed=discord.Embed(description=f"🎵 **{title}**", color=0x1abc9c))

@bot.command()
async def play(ctx, *, query):
    if not MUSIC_AVAILABLE:
        return await ctx.send("⚠️ Installe yt-dlp : `pip install yt-dlp PyNaCl`")
    if not ctx.author.voice:
        return await ctx.send("❌ Rejoins un salon vocal d'abord !")
    vc = voice_clients.get(ctx.guild.id)
    if not vc:
        vc = await ctx.author.voice.channel.connect()
        voice_clients[ctx.guild.id] = vc
    with yt_dlp.YoutubeDL(YTDL_OPTS) as ydl:
        info = ydl.extract_info(query, download=False)
        if 'entries' in info:
            info = info['entries'][0]
        url = info['url']
        title = info.get('title', query)
    if vc.is_playing():
        queues[ctx.guild.id].append((url, title))
        await ctx.send(embed=discord.Embed(description=f"📋 Ajouté : **{title}**", color=0x9b59b6))
    else:
        queues[ctx.guild.id].insert(0, (url, title))
        await play_next(ctx.guild.id, ctx.channel)

@bot.command()
async def stop(ctx):
    vc = voice_clients.get(ctx.guild.id)
    if vc:
        queues[ctx.guild.id].clear()
        await vc.disconnect()
        del voice_clients[ctx.guild.id]
        await ctx.send("⏹️ Musique arrêtée.")

@bot.command()
async def skip(ctx):
    vc = voice_clients.get(ctx.guild.id)
    if vc and vc.is_playing():
        vc.stop()
        await ctx.send("⏭️ Piste suivante !")

@bot.command()
async def queue(ctx):
    q = queues[ctx.guild.id]
    if not q:
        return await ctx.send("📋 La file est vide.")
    desc = "\n".join([f"`{i+1}.` {t}" for i, (_, t) in enumerate(q[:10])])
    await ctx.send(embed=discord.Embed(title="🎶 File d'attente", description=desc, color=0x3498db))

# ============================================================
#  TICKETS
# ============================================================
@bot.command()
async def ticket(ctx):
    guild = ctx.guild
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
    }
    for role in guild.roles:
        if role.permissions.administrator:
            overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
    channel = await guild.create_text_channel(
        f"🎫-{ctx.author.name}",
        overwrites=overwrites
    )
    tickets[channel.id] = ctx.author.id
    embed = discord.Embed(
        title="🎫 Ticket ouvert — QG Kdrama",
        description=f"Bonjour {ctx.author.mention} ! 👋\nDécris ta demande et un staff te répondra bientôt.\nTape `.close` pour fermer ce ticket.",
        color=0xff6b9d
    )
    await channel.send(embed=embed)
    await ctx.send(embed=discord.Embed(description=f"✅ Ticket créé : {channel.mention}", color=0x2ecc71))

@bot.command()
async def close(ctx):
    if ctx.channel.id not in tickets:
        return await ctx.send("❌ Ce channel n'est pas un ticket.")
    await ctx.send("🔒 Fermeture dans 5 secondes...")
    await asyncio.sleep(5)
    await ctx.channel.delete()
    tickets.pop(ctx.channel.id, None)

# ============================================================
#  MODÉRATION
# ============================================================
@bot.command(name="ban", aliases=["bannir"])
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="Aucune raison fournie"):
    await member.ban(reason=reason)
    await ctx.send(embed=discord.Embed(description=f"🔨 **{member}** banni. Raison : {reason}", color=0xe74c3c))

@bot.command(name="kick", aliases=["expulser"])
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="Aucune raison fournie"):
    try:
        embed_mp = discord.Embed(
            title=f"👢 Tu as été expulsé de **{ctx.guild.name}**",
            description=f"📋 **Raison :** {reason}\n👮 **Par :** {ctx.author.display_name}",
            color=0xe74c3c
        )
        await member.send(embed=embed_mp)
    except:
        pass
    await member.kick(reason=reason)
    await ctx.send(embed=discord.Embed(description=f"👢 **{member}** kické. Raison : {reason}", color=0xe67e22))

@bot.command(name="mute", aliases=["silence"])
@commands.has_permissions(manage_roles=True)
async def mute(ctx, member: discord.Member, duration: int = 10):
    role = discord.utils.get(ctx.guild.roles, name="Muted")
    if not role:
        role = await ctx.guild.create_role(name="Muted")
        for ch in ctx.guild.channels:
            await ch.set_permissions(role, send_messages=False, speak=False)
    await member.add_roles(role)
    await ctx.send(embed=discord.Embed(description=f"🔇 **{member}** muté pour {duration} minute(s).", color=0x95a5a6))
    await asyncio.sleep(duration * 60)
    await member.remove_roles(role)

@bot.command(name="unmute", aliases=["unsilence"])
@commands.has_permissions(manage_roles=True)
async def unmute(ctx, member: discord.Member):
    role = discord.utils.get(ctx.guild.roles, name="Muted")
    if role in member.roles:
        await member.remove_roles(role)
        await ctx.send(embed=discord.Embed(description=f"🔊 **{member}** unmuté.", color=0x2ecc71))

@bot.command(name="clear", aliases=["purge"])
@commands.has_permissions(manage_messages=True)
async def clear_cmd(ctx, nombre: str = "10"):
    """Supprime des messages — .clear <nombre> ou .clear all"""
    if nombre.lower() == "all":
        deleted = await ctx.channel.purge(limit=None)
        msg = await ctx.send(f"🗑️ {len(deleted)} messages supprimés !", delete_after=3)
    else:
        try:
            n = int(nombre)
            if n < 1 or n > 1000:
                return await ctx.send("❌ Entre 1 et 1000 messages !")
            deleted = await ctx.channel.purge(limit=n + 1)
            msg = await ctx.send(f"🗑️ {len(deleted)-1} messages supprimés !", delete_after=3)
        except ValueError:
            await ctx.send("❌ Utilise `.clear <nombre>` ou `.clear all`")



# ============================================================
#  FUN
# ============================================================
@bot.command(name="roast")
async def roast(ctx, member: discord.Member = None):
    target = member or ctx.author
    await ctx.send(embed=discord.Embed(
        description=f"🔥 {target.mention} : {random.choice(ROASTS_QG)}",
        color=0xe74c3c
    ))

@bot.command(name="compliment")
async def compliment(ctx, member: discord.Member = None):
    compliments = [
        "Tu as le même charme que Lee Min-ho. Vraiment. 😍",
        "Ton goût en Kdrama est irréprochable, respect total. 🎬",
        "T'es le/la meilleur(e) de ce serveur, et tout le monde le sait. 👑",
        "Même Goblin serait jaloux de ta présence ici. 🕯️",
        "Tu es la raison pour laquelle ce serveur est incroyable. 💜",
    ]
    target = member or ctx.author
    await ctx.send(embed=discord.Embed(
        description=f"💖 {target.mention} : {random.choice(compliments)}",
        color=0xff6b9d
    ))

@bot.command(name="8ball")
async def eight_ball(ctx, *, question):
    responses = [
        "Absolument, comme dans Goblin ! ✨", "Sans aucun doute 🎬", "Oui, les étoiles le disent ⭐",
        "Le drama dit OUI 💜", "Hmm, même l'IA hésite...", "Demande à ton oppa 😅",
        "Non, le second lead dirait non aussi 😭", "Clairement non, comme une fin de drama triste 💔"
    ]
    await ctx.send(embed=discord.Embed(
        title="🎱 La boule magique du QG",
        description=f"**Question :** {question}\n**Réponse :** {random.choice(responses)}",
        color=0x8e44ad
    ))

@bot.command(name="rps", aliases=["chifoumi"])
async def rps(ctx, choix: str):
    options = ["pierre", "feuille", "ciseaux"]
    choix = choix.lower()
    if choix not in options:
        return await ctx.send("❌ Utilise : `pierre`, `feuille` ou `ciseaux`")
    bot_choix = random.choice(options)
    emojis = {"pierre": "🪨", "feuille": "📄", "ciseaux": "✂️"}
    if choix == bot_choix:
        result, color = "🤝 Égalité !", 0x95a5a6
    elif (choix == "pierre" and bot_choix == "ciseaux") or \
         (choix == "feuille" and bot_choix == "pierre") or \
         (choix == "ciseaux" and bot_choix == "feuille"):
        result, color = "🏆 Tu gagnes !", 0x2ecc71
        economy_data[str(ctx.author.id)]["coins"] += 20
    else:
        result, color = "💀 Tu perds !", 0xe74c3c
    await ctx.send(embed=discord.Embed(
        title="🎮 Pierre Feuille Ciseaux",
        description=f"Toi : {emojis[choix]}  |  Bot : {emojis[bot_choix]}\n\n**{result}**",
        color=color
    ))

@bot.command(name="dice", aliases=["de","d6"])
async def dice(ctx, faces: int = 6):
    await ctx.send(embed=discord.Embed(
        description=f"🎲 Tu lances un dé à {faces} faces... **{random.randint(1, faces)}** !",
        color=0xe67e22
    ))

@bot.command(name="meme")
async def meme(ctx):
    memes = [
        "https://i.imgflip.com/4t0m5.jpg",
        "https://i.imgflip.com/26am.jpg",
        "https://i.imgflip.com/2fm6x.jpg",
        "https://i.imgflip.com/1bij.jpg",
    ]
    embed = discord.Embed(title="😂 Meme du QG !", color=0xf1c40f)
    embed.set_image(url=random.choice(memes))
    await ctx.send(embed=embed)

# ============================================================
#  ERREURS
# ============================================================

@bot.command(name="lg")
async def loup_garou_help(ctx):
    """Affiche l'aide du Loup Garou"""
    embed = discord.Embed(
        title="🐺 Loup Garou — QG Kdrama",
        description="Le célèbre jeu de déduction social, version Discord !",
        color=0x2c3e50
    )
    embed.add_field(name="📋 Commandes", value=(
        "`.lgcreate` — Créer une partie\n"
        "`.lgjoin` — Rejoindre la partie en attente\n"
        "`.lgstart` — Lancer la partie (créateur uniquement)\n"
        "`.lgvote @joueur` — Voter pour éliminer quelqu'un (jour)\n"
        "`.lgnuit @cible` — Action de nuit (en MP avec le bot)\n"
        "`.lgstatus` — Voir les joueurs en vie\n"
        "`.lgstop` — Annuler la partie\n"
        "`.lgroles` — Voir tous les rôles disponibles"
    ), inline=False)
    embed.add_field(name="🎯 Min/Max joueurs", value="5 à 12 joueurs", inline=True)
    embed.add_field(name="⏱️ Durée moyenne", value="15–30 minutes", inline=True)
    embed.set_footer(text="🐺 Bonne chance... ou bonne chasse 😈")
    await ctx.send(embed=embed)

@bot.command(name="lgroles")
async def lg_roles_list(ctx):
    embed = discord.Embed(title="🃏 Rôles du Loup Garou", color=0x8e44ad)
    for role, data in LG_ROLES.items():
        embed.add_field(
            name=f"{data['emoji']} {role}",
            value=data['desc'],
            inline=False
        )
    await ctx.send(embed=embed)

@bot.command(name="lgcreate")
async def lg_create(ctx):
    gid = ctx.guild.id
    if gid in lg_games:
        return await ctx.send("❌ Une partie est déjà en cours ! Tape `.lgstop` pour l'annuler.")
    lg_games[gid] = {
        "state": "waiting",       # waiting | night | day | voting
        "host": ctx.author.id,
        "players": {},             # {user_id: {name, role, alive, power_used}}
        "channel": ctx.channel.id,
        "day": 0,
        "votes": {},               # {voter_id: target_id}
        "night_actions": {},       # {user_id: target_id}
        "lovers": [],              # [user_id, user_id]
        "witch_potions": {},       # {user_id: {"life": True, "death": True}}
        "eliminated_tonight": None,
    }
    # Le créateur rejoint automatiquement
    lg_games[gid]["players"][ctx.author.id] = {
        "name": ctx.author.display_name,
        "role": None,
        "alive": True,
        "power_used": False,
    }
    embed = discord.Embed(
        title="🐺 Partie de Loup Garou créée !",
        description=(
            f"**{ctx.author.display_name}** ouvre une partie de Loup Garou !\n\n"
            "Tape `.lgjoin` pour rejoindre.\n"
            "Le créateur tape `.lgstart` quand tout le monde est prêt.\n\n"
            f"**Joueurs inscrits (1) :** {ctx.author.display_name}"
        ),
        color=0x2c3e50
    )
    embed.set_footer(text="Minimum 5 joueurs pour démarrer 🐺")
    await ctx.send(embed=embed)

@bot.command(name="lgjoin")
async def lg_join(ctx):
    gid = ctx.guild.id
    if gid not in lg_games:
        return await ctx.send("❌ Aucune partie en attente. Tape `.lgcreate` pour en créer une.")
    game = lg_games[gid]
    if game["state"] != "waiting":
        return await ctx.send("❌ La partie a déjà commencé !")
    if ctx.author.id in game["players"]:
        return await ctx.send("❌ Tu es déjà inscrit !")
    if len(game["players"]) >= 12:
        return await ctx.send("❌ La partie est complète (12 joueurs max).")

    game["players"][ctx.author.id] = {
        "name": ctx.author.display_name,
        "role": None,
        "alive": True,
        "power_used": False,
    }
    names = ", ".join(p["name"] for p in game["players"].values())
    embed = discord.Embed(
        title="✅ Joueur rejoint !",
        description=f"**{ctx.author.display_name}** a rejoint la partie !\n\n**Joueurs ({len(game['players'])}) :** {names}",
        color=0x27ae60
    )
    await ctx.send(embed=embed)

LG_NARRATIONS = {
    "debut": [
        "La nuit tombe sur le village... Les habitants s'endorment, ignorant le danger qui rôde parmi eux. 🌙",
        "Bienvenue dans ce village maudit. Ce soir, les loups garous vont frapper. Qui survivra jusqu'à l'aube ? 🐺",
        "Le village est calme... trop calme. Quelque part parmi vous se cachent des loups garous. La chasse commence. 🕯️",
    ],
    "nuit": [
        "La nuit tombe... Fermez les yeux, villageois. Les créatures de la nuit se réveillent. 🌑",
        "Silence dans le village. La lune est pleine ce soir. Les loups ouvrent les yeux et choisissent leur proie. 🐺🌕",
        "Les ténèbres enveloppent le village. Les innocents dorment... mais pas tous. 🌙",
    ],
    "jour_mort": [
        "L'aube se lève sur le village... mais elle apporte de mauvaises nouvelles. Un corps a été découvert. ☀️💀",
        "Le soleil se lève. Les villageois sortent de chez eux et découvrent avec horreur ce qui s'est passé cette nuit. ☀️😱",
        "Le coq chante. Le village se réveille. Mais quelqu'un ne se réveillera jamais. ☀️🕯️",
    ],
    "jour_rien": [
        "Miracle ! Le village se réveille et tout le monde est en vie. Les loups n'ont pas frappé cette nuit. ☀️🍀",
        "L'aube arrive. Par chance, personne n'est mort cette nuit. Mais les loups attendent leur moment. ☀️",
    ],
    "vote": [
        "Le village doit se réunir et prendre une décision difficile. Qui parmi vous est un loup ? Votez ! ⚖️",
        "L'heure de vérité a sonné. Les villageois débattent, s'accusent. Un vote doit départager les suspects. 🗳️",
    ],
    "fin_village": [
        "Le dernier loup est éliminé ! Le village est sauvé ! Les habitants peuvent enfin dormir en paix. 🎉🏘️",
    ],
    "fin_loups": [
        "Les loups garous ont gagné. Ils contrôlent désormais le village. Les villageois n'ont pas su les démasquer. 🐺🏆",
    ],
}

async def lg_narrer(ctx, cle: str):
    """Envoie une narration textuelle atmosphérique pour le Loup Garou"""
    textes = LG_NARRATIONS.get(cle, [])
    if not textes:
        return
    texte = random.choice(textes)
    embed = discord.Embed(
        description=f"*{texte}*",
        color=0x2c2f33
    )
    embed.set_footer(text="🐺 Loup Garou — QG Kdrama")
    await ctx.send(embed=embed)

async def lg_narrer_vocal(ctx, cle: str):
    """Narration vocale TTS via gTTS dans le salon vocal"""
    textes = LG_NARRATIONS.get(cle, [])
    if not textes:
        return
    texte = random.choice(textes)

    # Toujours envoyer en texte (fallback garanti)
    embed = discord.Embed(description=f"*{texte}*", color=0x2c2f33)
    embed.set_footer(text="🐺 Loup Garou — QG Kdrama")
    await ctx.send(embed=embed)

    # Chercher un salon vocal avec des membres
    voice_channel = None
    for ch in ctx.guild.voice_channels:
        if len(ch.members) > 0:
            voice_channel = ch
            break
    if not voice_channel:
        return  # Personne en vocal, on skip narration audio

    vc = None
    try:
        from gtts import gTTS
        import io

        # Générer le TTS
        tts = gTTS(text=texte, lang='fr', slow=False)
        tmp_path = f"/tmp/lg_narr_{ctx.guild.id}.mp3"
        tts.save(tmp_path)  # save() plus fiable que write_to_fp()

        # Rejoindre le vocal
        if ctx.voice_client and ctx.voice_client.is_connected():
            await ctx.voice_client.move_to(voice_channel)
            vc = ctx.voice_client
        else:
            vc = await voice_channel.connect()

        # Attendre que le précédent son soit fini
        while vc.is_playing():
            await asyncio.sleep(0.3)

        # Jouer le TTS
        vc.play(discord.FFmpegPCMAudio(tmp_path))

        # Attendre la fin avant de déconnecter
        while vc.is_playing():
            await asyncio.sleep(0.5)
        await asyncio.sleep(0.5)

        # Ne déconnecter que si plus rien ne joue
        if vc.is_connected() and not vc.is_playing():
            await vc.disconnect()

    except Exception as e:
        # La narration texte a déjà été envoyée, on continue sans crash
        print(f"[LG Narration erreur] {e}")
        if vc and vc.is_connected():
            try:
                await vc.disconnect()
            except:
                pass


@bot.command(name="lgstart")
async def lg_start(ctx):
    gid = ctx.guild.id
    if gid not in lg_games:
        return await ctx.send("❌ Aucune partie en attente.")
    game = lg_games[gid]
    if ctx.author.id != game["host"]:
        return await ctx.send("❌ Seul le créateur peut lancer la partie.")
    if game["state"] != "waiting":
        return await ctx.send("❌ La partie a déjà commencé.")
    n = len(game["players"])
    if n < 5:
        return await ctx.send(f"❌ Il faut au moins 5 joueurs ! ({n}/5 actuellement)")

    # Distribuer les rôles
    compo = lg_get_compo(n)
    random.shuffle(compo)
    player_ids = list(game["players"].keys())
    random.shuffle(player_ids)

    for i, uid in enumerate(player_ids):
        game["players"][uid]["role"] = compo[i]

    # Initialiser potions sorcière
    for uid, p in game["players"].items():
        if p["role"] == "Sorcière":
            game["witch_potions"][uid] = {"life": True, "death": True}

    # Envoyer les rôles en DM
    failed_dm = []
    for uid, p in game["players"].items():
        role = p["role"]
        role_data = LG_ROLES[role]
        embed = discord.Embed(
            title=f"🃏 Ton rôle — QG Kdrama Loup Garou",
            description=(
                f"**{role_data['emoji']} {role}**\n\n"
                f"_{role_data['desc']}_\n\n"
                f"**Équipe :** {'🐺 Loups' if role_data['team'] == 'loups' else ('🤍 Solitaire' if role_data['team'] == 'loup_blanc' else '👨‍🌾 Village')}"
            ),
            color=0x8e44ad
        )
        # Montrer les coéquipiers loups
        if role in ["Loup Garou", "Loup Blanc"]:
            wolves = [pp["name"] for pid, pp in game["players"].items() if pp["role"] in ["Loup Garou", "Loup Blanc"] and pid != uid]
            if wolves:
                embed.add_field(name="🐺 Tes coéquipiers loups", value=", ".join(wolves), inline=False)
        embed.set_footer(text="Ne montre ce message à personne ! 🤫")
        try:
            member = ctx.guild.get_member(uid)
            await member.send(embed=embed)
        except:
            failed_dm.append(p["name"])

    game["state"] = "day"
    game["day"] = 1

    # Annonce publique
    embed = discord.Embed(
        title="🐺 La partie commence !",
        description=(
            f"**{n} joueurs** ont reçu leur rôle en DM !\n\n"
            f"{'⚠️ Ces joueurs ont les DM fermés, donne leur leur rôle manuellement : ' + ', '.join(failed_dm) if failed_dm else '✅ Tous les rôles ont été envoyés en DM !'}\n\n"
            "☀️ **Jour 1 — Discussion**\nDiscutez, suspectez, débattez !\n"
            "Quand vous êtes prêts à voter : `.lgvote @joueur`"
        ),
        color=0xf39c12
    )
    names_list = "\n".join([f"{LG_ROLES[p['role']]['emoji'] if False else '❓'} {p['name']}" for p in game["players"].values()])
    embed.add_field(name=f"👥 Joueurs ({n})", value=names_list, inline=False)
    await ctx.send(embed=embed)
    await lg_narrer_vocal(ctx, "debut")

    # Cupidon en premier si présent
    for uid, p in game["players"].items():
        if p["role"] == "Cupidon":
            member = ctx.guild.get_member(uid)
            try:
                players_list = "\n".join([f"`{pid}` — {pp['name']}" for pid, pp in game["players"].items()])
                await member.send(
                    embed=discord.Embed(
                        title="💘 Cupidon — Choisis les amoureux !",
                        description=f"Utilise `.lgnuit @joueur1 @joueur2` en MP pour lier deux amoureux.\n\n{players_list}",
                        color=0xff6b9d
                    )
                )
            except:
                pass

@bot.command(name="lgvote")
async def lg_vote(ctx, target: discord.Member = None):
    gid = ctx.guild.id
    if gid not in lg_games:
        return await ctx.send("❌ Aucune partie en cours.")
    game = lg_games[gid]
    if game["state"] != "day":
        return await ctx.send("❌ On ne vote que pendant le jour !")
    if ctx.author.id not in game["players"]:
        return await ctx.send("❌ Tu ne participes pas à cette partie.")
    if not game["players"][ctx.author.id]["alive"]:
        return await ctx.send("❌ Les morts ne votent pas... 💀")
    if target is None:
        return await ctx.send("❌ Mentionne un joueur : `.lgvote @joueur`")
    if target.id not in game["players"] or not game["players"][target.id]["alive"]:
        return await ctx.send("❌ Ce joueur n'est pas dans la partie ou est déjà éliminé.")
    if target.id == ctx.author.id:
        return await ctx.send("❌ Tu ne peux pas voter contre toi-même !")

    game["votes"][ctx.author.id] = target.id
    alive_voters = [uid for uid, p in game["players"].items() if p["alive"]]
    voted_count = len(game["votes"])

    embed = discord.Embed(
        description=f"🗳️ **{ctx.author.display_name}** vote contre **{target.display_name}** ({voted_count}/{len(alive_voters)} votes)",
        color=0xe67e22
    )
    await ctx.send(embed=embed)

    # Tous les vivants ont voté ?
    if voted_count >= len(alive_voters):
        await lg_resolve_vote(ctx, game, gid)

@bot.command(name="lgpass")
async def lg_pass_vote(ctx):
    """Forcer la résolution du vote (hôte uniquement)"""
    gid = ctx.guild.id
    if gid not in lg_games:
        return
    game = lg_games[gid]
    if ctx.author.id != game["host"]:
        return await ctx.send("❌ Réservé à l'hôte.")
    if game["state"] != "day":
        return await ctx.send("❌ Pas en phase de vote.")
    await lg_resolve_vote(ctx, game, gid)

async def lg_resolve_vote(ctx, game, gid):
    """Compte les votes et élimine le joueur le plus voté"""
    from collections import Counter
    count = Counter(game["votes"].values())
    if not count:
        await ctx.send("🗳️ Aucun vote exprimé. La nuit tombe sans élimination.")
    else:
        max_votes = max(count.values())
        top = [uid for uid, v in count.items() if v == max_votes]
        if len(top) > 1:
            eliminated_id = random.choice(top)
            await ctx.send(f"⚖️ Égalité dans les votes ! Le destin tranche...")
        else:
            eliminated_id = top[0]

        p = game["players"][eliminated_id]
        p["alive"] = False
        role = p["role"]
        role_data = LG_ROLES[role]

        embed = discord.Embed(
            title="☀️ Fin du vote villageois",
            description=(
                f"**{p['name']}** est éliminé(e) par le village avec **{count[eliminated_id]} vote(s)** !\n"
                f"Son rôle était : **{role_data['emoji']} {role}**"
            ),
            color=0xe74c3c
        )
        await ctx.send(embed=embed)

        # Amoureux ?
        if eliminated_id in game["lovers"]:
            lover_id = [l for l in game["lovers"] if l != eliminated_id][0]
            if game["players"][lover_id]["alive"]:
                game["players"][lover_id]["alive"] = False
                await ctx.send(embed=discord.Embed(
                    description=f"💔 **{game['players'][lover_id]['name']}** meurt de chagrin ! (amoureux(se) de {p['name']})",
                    color=0xff6b9d
                ))

        # Chasseur ?
        if role == "Chasseur":
            member = ctx.guild.get_member(eliminated_id)
            try:
                alive_others = [(uid, pp) for uid, pp in game["players"].items() if pp["alive"] and uid != eliminated_id]
                names = "\n".join([f"• {pp['name']}" for _, pp in alive_others])
                await member.send(embed=discord.Embed(
                    title="🏹 Chasseur — Tu peux tirer !",
                    description=f"Tu as été éliminé(e) ! Tu peux emporter quelqu'un avec toi.\nTape `.lgnuit @joueur` en MP pour tirer.\n\n{names}",
                    color=0xe67e22
                ))
            except:
                pass

    # Vérif victoire
    won, msg = lg_check_win(game)
    if won:
        await ctx.send(embed=discord.Embed(title="🏆 FIN DE PARTIE", description=msg, color=0xf1c40f))
        await lg_reveal_roles(ctx, game)
        del lg_games[gid]
        return

    # Passer à la nuit
    game["votes"] = {}
    game["night_actions"] = {}
    game["state"] = "night"
    game["eliminated_tonight"] = None

    alive_list = "\n".join([f"• {p['name']}" for p in game["players"].values() if p["alive"]])
    embed = discord.Embed(
        title=f"🌙 Nuit {game['day']} — Le village s'endort...",
        description=(
            "Les rôles spéciaux agissent maintenant !\n\n"
            "**Actions en MP avec le bot :**\n"
            "🐺 **Loups** → `.lgnuit @cible` pour choisir votre victime\n"
            "🔮 **Voyante** → `.lgnuit @cible` pour voir un rôle\n"
            "🧙 **Sorcière** → `.lgsorciere vie/mort @cible`\n\n"
            f"**Joueurs en vie :**\n{alive_list}"
        ),
        color=0x2c3e50
    )
    await ctx.send(embed=embed)
    await lg_narrer_vocal(ctx, "nuit")

    # Notifier les loups en DM
    wolves = [(uid, p) for uid, p in game["players"].items() if p["role"] in ["Loup Garou"] and p["alive"]]
    for uid, p in wolves:
        member = ctx.guild.get_member(uid)
        alive_villagers = [(i, pp) for i, pp in game["players"].items() if pp["alive"] and pp["role"] not in ["Loup Garou", "Loup Blanc"]]
        names = "\n".join([f"• {pp['name']}" for _, pp in alive_villagers])

@bot.command(name="acheter")
async def acheter_cmd(ctx, item_id: str = None):
    if SALON_BOUTIQUE_ID and ctx.channel.id != SALON_BOUTIQUE_ID:
        salon = ctx.guild.get_channel(SALON_BOUTIQUE_ID)
        mention = salon.mention if salon else "le salon boutique"
        await ctx.send(f"🛒 Psst — la boutique officielle c'est dans {mention} ! Mais je traite quand même ta commande ici 😉", delete_after=8)
    """Acheter un item de la boutique — .acheter <id>"""
    if not item_id:
        return await ctx.send("❌ Précise un item ! Consulte `.shop` pour la liste.")
    item = next((i for i in SHOP_ITEMS if i["id"] == item_id.lower()), None)
    if not item:
        return await ctx.send(f"❌ Item `{item_id}` introuvable ! Consulte `.shop`.")
    uid = str(ctx.author.id)
    solde = economy_data[uid]["coins"]
    if solde < item["prix"]:
        manque = item["prix"] - solde
        return await ctx.send(embed=discord.Embed(
            description=f"❌ Il te manque **{manque} pièces** pour acheter {item['nom']} !\nFais `.daily` ou `.quiz` pour en gagner 💰",
            color=0xe74c3c
        ))

    import time as _time
    now_t = _time.time()

    # ── Vérif daily ──────────────────────────────────────────
    if item.get("daily"):
        last = daily_item_usage[uid].get(item["id"], 0)
        if now_t - last < 86400:
            reste = int((86400 - (now_t - last)) // 3600)
            return await ctx.send(f"⏳ Cet item est limité 1x/jour ! Disponible dans **{reste}h**.")

    economy_data[uid]["coins"] -= item["prix"]
    if item.get("daily"):
        daily_item_usage[uid][item["id"]] = now_t

    iid = item["id"]

    # ── Double XP ────────────────────────────────────────────
    if iid == "double_xp":
        double_xp_users[ctx.author.id] = now_t + 3600
        return await ctx.send(embed=discord.Embed(
            description=f"⚡ {ctx.author.mention} a activé le **Double XP** pendant 1h ! 🎉",
            color=0x2ecc71))

    # ── Rôles ────────────────────────────────────────────────
    role_names = {"vip":"⭐ VIP","drama_king":"👑 Drama King","otaku":"🌀 Oeil de Dieu",
                  "gamer_pro":"⚔️ Chasseur National","shadow":"🌑 Monarque des Ombres","pillier":"🔥 Pillier du Soleil"}
    if iid in role_names:
        role = discord.utils.get(ctx.guild.roles, name=role_names[iid])
        if not role:
            role = await ctx.guild.create_role(name=role_names[iid], reason=f"Boutique QG")
        await ctx.author.add_roles(role)
        return await ctx.send(embed=discord.Embed(
            description=f"✅ {ctx.author.mention} a obtenu le rôle **{role_names[iid]}** ! 🎉",
            color=0x2ecc71))

    # ── Boosts rolls ─────────────────────────────────────────
    if iid == "rolls_5":
        roll_data[uid]["rolls"] = min(roll_data[uid]["rolls"] + 5, ROLLS_MAX + 5)
        return await ctx.send(embed=discord.Embed(
            description=f"🎰 {ctx.author.mention} a obtenu **+5 rolls** ! ({roll_data[uid]['rolls']} restants)",
            color=0x2ecc71))

    # ── Boost rareté ─────────────────────────────────────────
    if iid == "boost_rarete":
        rarity_boost[uid] = 5
        return await ctx.send(embed=discord.Embed(
            description=f"🎯 {ctx.author.mention} **Boost Rareté** actif pour les 5 prochains rolls ! ↑↑",
            color=0x9b59b6))

    # ── Claim timers ─────────────────────────────────────────
    if iid in ("claim_10","claim_15","claim_20"):
        mins_map = {"claim_10":10,"claim_15":15,"claim_20":20}
        claim_reduction[uid] = max(claim_reduction[uid], CLAIM_COOLDOWN_MINUTES - mins_map[iid])
        return await ctx.send(embed=discord.Embed(
            description=f"⚡ {ctx.author.mention} Claim réduit à **{mins_map[iid]} min** (permanent) !",
            color=0x2ecc71))

    # ── Protection Divine ─────────────────────────────────────
    if iid == "protection":
        shield_active[uid] = now_t + 7200  # 2h
        return await ctx.send(embed=discord.Embed(
            description=f"🌟 {ctx.author.mention} **Protection Divine** active pendant **2h** ! Immunité totale.",
            color=0xf1c40f))

    # ── Amulette ─────────────────────────────────────────────
    if iid == "amulette":
        if not hasattr(bot, 'amulette_active'):
            bot.amulette_active = {}
        bot.amulette_active[uid] = now_t + 1200  # 20 min
        return await ctx.send(embed=discord.Embed(
            description=f"🪬 {ctx.author.mention} **Amulette** active pendant **20 min** ! Tout sabotage sera renvoyé sur l'attaquant.",
            color=0x9b59b6))

    # ── Bouclier ─────────────────────────────────────────────
    if iid == "shield":
        shield_active[uid] = now_t + 1800
        return await ctx.send(embed=discord.Embed(
            description=f"🛡️ {ctx.author.mention} **Bouclier** actif pendant **30 min** !",
            color=0x3498db))

    # ── Double ou Rien ────────────────────────────────────────
    if iid == "double_rien":
        rolls_left = roll_data[uid]["rolls"]
        if rolls_left > 4:
            economy_data[uid]["coins"] += item["prix"]  # remboursement
            return await ctx.send(f"❌ Tu as encore **{rolls_left} rolls** ! Double ou Rien c'est pour quand t'as **4 rolls ou moins** !")
        if random.random() < 0.5:
            roll_data[uid]["rolls"] = min(rolls_left * 2, ROLLS_MAX)
            return await ctx.send(embed=discord.Embed(
                description=f"🎰 {ctx.author.mention} **DOUBLE !** Tu passes de {rolls_left} à **{roll_data[uid]['rolls']} rolls** ! 🍀",
                color=0x2ecc71))
        else:
            roll_data[uid]["rolls"] = 0
            return await ctx.send(embed=discord.Embed(
                description=f"🎰 {ctx.author.mention} **RIEN !** Tu perds tes {rolls_left} rolls... 😢",
                color=0xe74c3c))

    # ── Oracle ────────────────────────────────────────────────
    if iid == "oracle":
        available = [k for k in ANIME_CARDS_DB if k not in claimed_cards]
        if not available:
            economy_data[uid]["coins"] += item["prix"]
            return await ctx.send("❌ Toutes les cartes sont déjà claimées !")
        oracle_card = random.choice(available)
        if not hasattr(bot, 'oracle_active'):
            bot.oracle_active = {}
        bot.oracle_active["card"] = oracle_card
        bot.oracle_active["rolls_left"] = 3
        bot.oracle_active["chance"] = 0.2  # 1/5
        c_oracle = ANIME_CARDS_DB[oracle_card]
        salon = ctx.guild.get_channel(SALON_GACHA_ID) if SALON_GACHA_ID else ctx.channel
        embed_oracle = discord.Embed(
            title="🔮 L'Oracle a parlé...",
            description=f"Une carte mystérieuse rôde dans les prochains tirages !\n*Elle a 1 chance sur 5 de tomber dans les **3 prochains rolls** du serveur...*\n\n**Soyez prêts à claim !** ⚡",
            color=0x9b59b6
        )
        await (salon or ctx.channel).send(embed=embed_oracle)
        return

    # ── Cadeau Mystère ─────────────────────────────────────────
    if iid == "cadeau":
        rare_plus = [k for k in ANIME_CARDS_DB if ANIME_CARDS_DB[k]["rarete"] in ("Rare","Épique","Légendaire","Mythique") and k not in claimed_cards]
        if not rare_plus:
            economy_data[uid]["coins"] += item["prix"]
            return await ctx.send("❌ Plus de cartes disponibles Rare+ !")
        card_key = random.choice(rare_plus)
        claimed_cards[card_key] = uid
        gacha_collections[uid][card_key] = {"fusion": 0}
        c_gift = ANIME_CARDS_DB[card_key]
        r_emoji = RARETE_EMOJI.get(c_gift["rarete"], "🔵")
        embed_gift = discord.Embed(
            title="🎁 Cadeau Mystère !",
            description=f"{ctx.author.mention} a reçu **{c_gift['nom']}** {r_emoji} **{c_gift['rarete']}** !",
            color=RARETE_COULEURS.get(c_gift["rarete"], 0x95a5a6)
        )
        if c_gift.get("image"):
            embed_gift.set_thumbnail(url=c_gift["image"])
        return await ctx.send(embed=embed_gift)

    # ── Items PvP (nécessitent .utiliser @joueur) ─────────────
    if iid in ("freeze","curse","cadenas","bombe_gacha","fantome","malediction","vol_roll"):
        if not hasattr(bot, 'pending_items'):
            bot.pending_items = {}
        if uid not in bot.pending_items:
            bot.pending_items[uid] = {}
        bot.pending_items[uid][iid] = now_t
        return await ctx.send(embed=discord.Embed(
            description=f"✅ {ctx.author.mention} a acheté **{item['nom']}** !\nUtilise `.utiliser {iid} @joueur` pour l'activer ! ⚡",
            color=0xf39c12))

    await ctx.send(embed=discord.Embed(
        title="🛒 Achat réussi !",
        description=f"✅ {ctx.author.mention} a acheté **{item['nom']}** pour **{item['prix']} pièces** ! 🎉",
        color=0x2ecc71))

# ============================================================
#  VOL DE PIÈCES
# ============================================================
steal_cooldowns = {}

@bot.command(name="steal")
async def steal_cmd(ctx, target: discord.Member = None):
    """Tente de voler des pièces — .steal @joueur"""
    if not target:
        return await ctx.send("❌ Mentionne quelqu'un ! Ex: `.steal @ami`")
    if target.id == ctx.author.id:
        return await ctx.send("❌ Tu peux pas te voler toi-même 😂")
    if target.bot:
        return await ctx.send("❌ Tu peux pas voler un bot !")

    uid = ctx.author.id
    now = datetime.datetime.utcnow().timestamp()
    if uid in steal_cooldowns and now - steal_cooldowns[uid] < 3600:
        restant = int(3600 - (now - steal_cooldowns[uid]))
        mins = restant // 60
        return await ctx.send(f"⏳ Cooldown ! Tu peux revoler dans **{mins} minutes**.")

    steal_cooldowns[uid] = now
    target_coins = economy_data[str(target.id)]["coins"]

    if target_coins < 50:
        return await ctx.send(f"💸 **{target.display_name}** est trop pauvre, rien à voler !")

    # 45% de chance de réussir
    if random.random() < 0.45:
        montant = random.randint(50, min(200, target_coins))
        economy_data[str(ctx.author.id)]["coins"] += montant
        economy_data[str(target.id)]["coins"] -= montant
        await ctx.send(embed=discord.Embed(
            description=f"🦹 **{ctx.author.mention}** a volé **{montant} pièces** à {target.mention} ! 💰",
            color=0x2ecc71
        ))
    else:
        # Échec : perd 50-100 pièces
        amende = min(random.randint(50, 100), economy_data[str(ctx.author.id)]["coins"])
        economy_data[str(ctx.author.id)]["coins"] -= amende
        economy_data[str(target.id)]["coins"] += amende
        await ctx.send(embed=discord.Embed(
            description=f"🚨 **{ctx.author.mention}** s'est fait attraper en essayant de voler {target.mention} ! Amende : **{amende} pièces** 😂",
            color=0xe74c3c
        ))

# ============================================================
#  BANQUE
# ============================================================
bank_data = defaultdict(lambda: {"depot": 0, "depot_time": 0})

@bot.command(name="banque")
async def banque_cmd(ctx, action: str = None, montant: int = None):
    """
    .banque depot <montant> — Déposer des pièces (intérêts 5% / 24h)
    .banque retrait — Retirer tout avec intérêts
    .banque solde — Voir ton solde banque
    """
    uid = str(ctx.author.id)
    if not action:
        return await ctx.send("🏦 Usage: `.banque depot <montant>` | `.banque retrait` | `.banque solde`")

    action = action.lower()
    now = datetime.datetime.utcnow().timestamp()

    if action == "depot":
        if not montant or montant <= 0:
            return await ctx.send("❌ Précise un montant ! Ex: `.banque depot 200`")
        if economy_data[uid]["coins"] < montant:
            return await ctx.send(f"❌ Tu n'as que **{economy_data[uid]['coins']} pièces** !")
        economy_data[uid]["coins"] -= montant
        bank_data[uid]["depot"] += montant
        bank_data[uid]["depot_time"] = now
        await ctx.send(embed=discord.Embed(
            description=f"🏦 **{montant} pièces** déposées à la banque ! Tu gagneras **5% d'intérêts par 24h** 📈",
            color=0x2ecc71
        ))

    elif action == "retrait":
        depot = bank_data[uid]["depot"]
        if depot == 0:
            return await ctx.send("❌ Tu n'as rien en banque !")
        elapsed_days = (now - bank_data[uid]["depot_time"]) / 86400
        interets = int(depot * 0.05 * elapsed_days)
        total = depot + interets
        economy_data[uid]["coins"] += total
        bank_data[uid]["depot"] = 0
        bank_data[uid]["depot_time"] = 0
        await ctx.send(embed=discord.Embed(
            description=f"🏦 Retrait de **{total} pièces** ! (dépôt: {depot} + intérêts: {interets}) 💰",
            color=0x2ecc71
        ))

    elif action == "solde":
        depot = bank_data[uid]["depot"]
        if depot == 0:
            return await ctx.send("🏦 Tu n'as rien en banque. Fais `.banque depot <montant>` !")
        elapsed_days = (now - bank_data[uid]["depot_time"]) / 86400
        interets = int(depot * 0.05 * elapsed_days)
        await ctx.send(embed=discord.Embed(
            title="🏦 Ton compte bancaire",
            description=f"💰 Dépôt : **{depot} pièces**\n📈 Intérêts accumulés : **+{interets} pièces**\n💎 Total actuel : **{depot + interets} pièces**",
            color=0xf1c40f
        ))

# ============================================================
#  SONDAGES
# ============================================================

# ============================================================
#  GIVEAWAY
# ============================================================
active_giveaways = {}

@bot.command(name="giveaway")
@commands.has_permissions(manage_guild=True)
async def giveaway_cmd(ctx, duree: str = None, *, prix: str = None):
    """
    .giveaway <durée> <prix>
    Ex: .giveaway 24h Rôle VIP
    Ex: .giveaway 1h 500 pièces
    """
    if not duree or not prix:
        return await ctx.send('❌ Usage: `.giveaway <durée> <prix>`\nEx: `.giveaway 24h Rôle VIP`')

    # Parser la durée
    seconds = 0
    if "h" in duree:
        try: seconds = int(duree.replace("h", "")) * 3600
        except: pass
    elif "m" in duree:
        try: seconds = int(duree.replace("m", "")) * 60
        except: pass
    elif "j" in duree:
        try: seconds = int(duree.replace("j", "")) * 86400
        except: pass

    if seconds == 0:
        return await ctx.send("❌ Durée invalide ! Utilise `1h`, `30m`, `2j`...")

    embed = discord.Embed(
        title="🎉 GIVEAWAY !",
        description=(
            f"**Prix : {prix}**\n\n"
            f"Réagis avec 🎉 pour participer !\n"
            f"⏳ Fin dans : **{duree}**"
        ),
        color=0xf1c40f
    )
    embed.set_footer(text=f"Organisé par {ctx.author.display_name}")
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("🎉")

    active_giveaways[msg.id] = {"prix": prix, "channel": ctx.channel.id}

    await asyncio.sleep(seconds)

    # Récupérer les participants
    try:
        msg = await ctx.channel.fetch_message(msg.id)
        reaction = discord.utils.get(msg.reactions, emoji="🎉")
        if reaction:
            users = [u async for u in reaction.users() if not u.bot]
            if users:
                gagnant = random.choice(users)
                await ctx.send(embed=discord.Embed(
                    title="🎉 Fin du Giveaway !",
                    description=f"🏆 **{gagnant.mention}** remporte **{prix}** ! Félicitations ! 🎊",
                    color=0x2ecc71
                ))
            else:
                await ctx.send("😔 Personne n'a participé au giveaway...")
    except:
        pass
    active_giveaways.pop(msg.id, None)

# ============================================================
#  ANNIVERSAIRES
# ============================================================
anniversaires = {}  # {user_id: "JJ/MM"}

@bot.command(name="anniversaire")
async def anniversaire_cmd(ctx, date: str = None):
    """
    .anniversaire 25/03 — Enregistre ton anniversaire
    .anniversaire — Voir les prochains anniversaires
    """
    uid = str(ctx.author.id)
    if not date:
        if not anniversaires:
            return await ctx.send("🎂 Aucun anniversaire enregistré ! Utilise `.anniversaire JJ/MM`")
        embed = discord.Embed(title="🎂 Anniversaires du QG", color=0xff6b9d)
        for user_id, d in anniversaires.items():
            member = ctx.guild.get_member(int(user_id))
            if member:
                embed.add_field(name=member.display_name, value=f"🎂 {d}", inline=True)
        await ctx.send(embed=embed)
        return

    # Valider le format JJ/MM
    try:
        parts = date.split("/")
        if len(parts) != 2:
            raise ValueError
        jour, mois = int(parts[0]), int(parts[1])
        if not (1 <= jour <= 31 and 1 <= mois <= 12):
            raise ValueError
    except:
        return await ctx.send("❌ Format invalide ! Utilise `JJ/MM` — Ex: `.anniversaire 25/03`")

    anniversaires[uid] = date
    await ctx.send(embed=discord.Embed(
        description=f"🎂 Anniversaire de **{ctx.author.display_name}** enregistré le **{date}** ! 🎉",
        color=0xff6b9d
    ))

@tasks.loop(hours=24)
async def check_anniversaires():
    """Vérifie les anniversaires chaque jour"""
    today = datetime.datetime.now().strftime("%d/%m")
    for guild in bot.guilds:
        channel = (
            discord.utils.get(guild.text_channels, name="général") or
            guild.system_channel
        )
        if not channel:
            continue
        for user_id, date in anniversaires.items():
            if date == today:
                member = guild.get_member(int(user_id))
                if member:
                    embed = discord.Embed(
                        title="🎂 Joyeux Anniversaire !",
                        description=f"Toute la communauté du QG Kdrama souhaite un joyeux anniversaire à **{member.mention}** ! 🎉🎊🥳",
                        color=0xff6b9d
                    )
                    await channel.send(embed=embed)

@bot.event
async def on_ready():
    check_anniversaires.start()
    # Démarrer les tasks d'events
    # Nouvelles tasks planning
    for task in [invasion_samedi, classement_hebdo, prophetie_hebdo, planning_hebdo,
                 events_mensuels, heure_maudite_task, imposteur_task]:
        if not task.is_running():
            task.start()
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name="🎬 Kdrama • .help")
    )
    print(f"✅ Bot QG Kdrama connecté : {bot.user}")

# ============================================================
#  STATISTIQUES SERVEUR
# ============================================================
command_stats = defaultdict(int)  # {command_name: count}

@bot.event
async def on_command(ctx):
    command_stats[ctx.command.name] += 1

@bot.command(name="stats")
async def stats_cmd(ctx):
    """Statistiques du serveur"""
    guild = ctx.guild
    total_members = guild.member_count
    online = sum(1 for m in guild.members if m.status != discord.Status.offline and not m.bot)
    bots = sum(1 for m in guild.members if m.bot)
    humains = total_members - bots

    top_cmds = sorted(command_stats.items(), key=lambda x: x[1], reverse=True)[:5]
    top_str = "\n".join([f"• `.{cmd}` — {count} fois" for cmd, count in top_cmds]) or "Aucune commande utilisée"

    # Top 3 messages
    members_ids = [str(m.id) for m in guild.members if not m.bot]
    top_msg = sorted(
        [(uid, message_count[uid]) for uid in members_ids if message_count[uid] > 0],
        key=lambda x: x[1], reverse=True
    )[:3]
    medals = ["🥇", "🥈", "🥉"]
    top_msg_str = "\n".join([
        f"{medals[i]} <@{uid}> — **{count}** messages"
        for i, (uid, count) in enumerate(top_msg)
    ]) or "Pas encore de données"

    # Top 3 vocal
    top_vocal = sorted(
        [(uid, voice_time[uid]) for uid in members_ids if voice_time[uid] > 0],
        key=lambda x: x[1], reverse=True
    )[:3]
    top_vocal_str = "\n".join([
        f"{medals[i]} <@{uid}> — **{mins}** minutes"
        for i, (uid, mins) in enumerate(top_vocal)
    ]) or "Pas encore de données"

    embed = discord.Embed(title=f"📊 Statistiques — {guild.name}", color=0x5865F2)
    embed.add_field(name="👥 Membres", value=f"Total: {total_members}\nHumains: {humains}\nBots: {bots}\nEn ligne: {online}", inline=True)
    embed.add_field(name="💬 Salons", value=f"Texte: {len(guild.text_channels)}\nVocal: {len(guild.voice_channels)}", inline=True)
    embed.add_field(name="💬 Top 3 Messages", value=top_msg_str, inline=False)
    embed.add_field(name="🎤 Top 3 Vocal", value=top_vocal_str, inline=False)
    embed.add_field(name="🏆 Top Commandes", value=top_str, inline=False)
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    await ctx.send(embed=embed)

# ============================================================
#  MARIAGE
# ============================================================
mariages = {}  # {user_id: partner_id}
demandes_mariage = {}  # {demandeur_id: cible_id}

@bot.command(name="marier")
async def marier_cmd(ctx, cible: discord.Member = None):
    """Demande en mariage un membre — .marier @joueur"""
    if not cible:
        return await ctx.send("❌ Mentionne quelqu'un ! Ex: `.marier @ami`")
    if cible.bot:
        return await ctx.send("❌ Tu peux pas épouser un bot 😂")
    if cible.id == ctx.author.id:
        return await ctx.send("❌ Tu peux pas t'épouser toi-même 😂")
    if str(ctx.author.id) in mariages:
        return await ctx.send(f"❌ Tu es déjà marié(e) ! Utilise `.divorcer` d'abord.")

    demandes_mariage[ctx.author.id] = cible.id
    embed = discord.Embed(
        title="💍 Demande en Mariage !",
        description=(
            f"💜 **{ctx.author.mention}** demande en mariage **{cible.mention}** !\n\n"
            f"{cible.mention}, tape `.accepter` pour dire **Oui** 💍\n"
            f"ou `.refuser` pour dire Non 💔\n\n"
            f"_Tu as 60 secondes pour répondre..._"
        ),
        color=0xff6b9d
    )
    await ctx.send(embed=embed)

@bot.command(name="accepter")
async def accepter_mariage(ctx):
    """Accepte une demande en mariage"""
    demandeur_id = next((k for k, v in demandes_mariage.items() if v == ctx.author.id), None)
    if not demandeur_id:
        return await ctx.send("❌ Tu n'as aucune demande en mariage en attente !")

    demandeur = ctx.guild.get_member(demandeur_id)
    demandes_mariage.pop(demandeur_id, None)
    mariages[str(demandeur_id)] = ctx.author.id
    mariages[str(ctx.author.id)] = demandeur_id

    embed = discord.Embed(
        title="💍 Mariage du QG Kdrama ! 🎊",
        description=(
            f"🎉 **{demandeur.mention}** et **{ctx.author.mention}** sont maintenant mariés !\n\n"
            f"_Que leur amour soit aussi beau que celui de Crash Landing on You_ 💜🪂\n\n"
            f"Utilisez `.profil` pour voir votre statut !"
        ),
        color=0xff6b9d
    )
    await ctx.send(embed=embed)

@bot.command(name="refuser")
async def refuser_mariage(ctx):
    """Refuse une demande en mariage"""
    demandeur_id = next((k for k, v in demandes_mariage.items() if v == ctx.author.id), None)
    if not demandeur_id:
        return await ctx.send("❌ Tu n'as aucune demande en attente !")
    demandeur = ctx.guild.get_member(demandeur_id)
    demandes_mariage.pop(demandeur_id, None)
    await ctx.send(embed=discord.Embed(
        description=f"💔 **{ctx.author.mention}** a refusé la demande de **{demandeur.mention}**... 😢",
        color=0xe74c3c
    ))

@bot.command(name="divorcer")
async def divorcer_cmd(ctx):
    """Divorce — .divorcer"""
    uid = str(ctx.author.id)
    if uid not in mariages:
        return await ctx.send("❌ Tu n'es pas marié(e) !")
    partner_id = str(mariages[uid])
    partner = ctx.guild.get_member(int(partner_id))
    mariages.pop(uid, None)
    mariages.pop(partner_id, None)
    await ctx.send(embed=discord.Embed(
        description=f"💔 **{ctx.author.mention}** a divorcé... C'est triste 😢",
        color=0xe74c3c
    ))


# ============================================================
#  🎬 BRACKET TOURNOI
# ============================================================
BRACKET_KDRAMA = [
    {"nom": "Crash Landing on You"},
    {"nom": "Goblin"},
    {"nom": "Descendants of the Sun"},
    {"nom": "Vincenzo"},
    {"nom": "Itaewon Class"},
    {"nom": "True Beauty"},
    {"nom": "Business Proposal"},
    {"nom": "All of Us Are Dead"},
    {"nom": "Sweet Home"},
    {"nom": "The Glory"},
    {"nom": "Twenty-Five Twenty-One"},
    {"nom": "My Name"},
    {"nom": "Bloodhounds"},
    {"nom": "Squid Game"},
    {"nom": "Extraordinary Attorney Woo"},
    {"nom": "Start-Up"},
    {"nom": "Hotel Del Luna"},
    {"nom": "The King: Eternal Monarch"},
    {"nom": "Healer"},
    {"nom": "W: Two Worlds"},
    {"nom": "What's Wrong with Secretary Kim"},
    {"nom": "Kill Me, Heal Me"},
    {"nom": "Weightlifting Fairy Kim Bok-Joo"},
    {"nom": "My ID Is Gangnam Beauty"},
    {"nom": "Hometown Cha-Cha-Cha"},
    {"nom": "Penthouse"},
    {"nom": "Moon Lovers: Scarlet Heart Ryeo"},
    {"nom": "Uncanny Counter"},
    {"nom": "Nevertheless"},
    {"nom": "Because This Is My First Life"},
    {"nom": "The Red Sleeve"},
    {"nom": "Alchemy of Souls"},
    {"nom": "See You in My 19th Life"},
    {"nom": "D.P."},
    {"nom": "Signal"},
    {"nom": "Prison Playbook"},
    {"nom": "Hospital Playlist"},
    {"nom": "Romance Is a Bonus Book"},
    {"nom": "Legend of the Blue Sea"},
    {"nom": "Flower of Evil"},
    {"nom": "My Love From the Star"},
    {"nom": "Strong Woman Do Bong-Soon"},
    {"nom": "It's Okay to Not Be Okay"},
    {"nom": "Love Alarm"},
    {"nom": "Kingdom"},
    {"nom": "While You Were Sleeping"},
    {"nom": "The K2"},
    {"nom": "Abyss"},
    {"nom": "Celebrity"},
    {"nom": "Reply 1988"},
]

BRACKET_ANIME = [
    {"nom": "One Piece"},
    {"nom": "Naruto"},
    {"nom": "Bleach"},
    {"nom": "Dragon Ball Z"},
    {"nom": "Attack on Titan"},
    {"nom": "Demon Slayer"},
    {"nom": "Jujutsu Kaisen"},
    {"nom": "My Hero Academia"},
    {"nom": "Tokyo Ghoul"},
    {"nom": "Hunter x Hunter"},
    {"nom": "Death Note"},
    {"nom": "Fullmetal Alchemist: Brotherhood"},
    {"nom": "Chainsaw Man"},
    {"nom": "Fairy Tail"},
    {"nom": "Sword Art Online"},
    {"nom": "Solo Leveling"},
    {"nom": "Blue Lock"},
    {"nom": "Haikyuu!!"},
    {"nom": "Black Clover"},
    {"nom": "The Seven Deadly Sins"},
    {"nom": "Mob Psycho 100"},
    {"nom": "One Punch Man"},
    {"nom": "Fire Force"},
    {"nom": "Vinland Saga"},
    {"nom": "The Rising of the Shield Hero"},
    {"nom": "Code Geass"},
    {"nom": "Steins;Gate"},
    {"nom": "Toradora!"},
    {"nom": "Your Lie in April"},
    {"nom": "Re:Zero"},
    {"nom": "Darling in the Franxx"},
    {"nom": "The Promised Neverland"},
    {"nom": "Erased"},
    {"nom": "Parasyte -the maxim-"},
    {"nom": "Dr. Stone"},
    {"nom": "Kill la Kill"},
    {"nom": "Assassination Classroom"},
    {"nom": "Overlord"},
    {"nom": "Psycho-Pass"},
    {"nom": "Kuroko's Basketball"},
    {"nom": "Baki"},
    {"nom": "Record of Ragnarok"},
    {"nom": "Soul Eater"},
    {"nom": "Gurren Lagann"},
    {"nom": "Fate/Zero"},
    {"nom": "Trigun Stampede"},
    {"nom": "Noragami"},
    {"nom": "Jobless Reincarnation"},
    {"nom": "Tokyo Revengers"},
]

active_brackets = {}  # {guild_id: {theme, matchs, tour, votes, message_ids}}

@bot.command(name="bracket")
async def bracket_cmd(ctx, theme: str = None):
    """
    .bracket kdrama — Lance le tournoi des meilleurs Kdramas !
    .bracket anime  — Lance le tournoi des meilleurs Animés !
    """
    if not theme or theme.lower() not in ["kdrama", "anime"]:
        return await ctx.send("❌ Choisis un thème ! `.bracket kdrama` ou `.bracket anime`")

    gid = ctx.guild.id
    if gid in active_brackets:
        return await ctx.send("🏆 Un tournoi est déjà en cours ! Attends la fin.")

    theme = theme.lower()
    pool = BRACKET_KDRAMA if theme == "kdrama" else BRACKET_ANIME
    participants = random.sample(pool, 8)

    # Créer les matchs du 1er tour (4 matchs)
    matchs = [(participants[i], participants[i+1]) for i in range(0, 8, 2)]

    active_brackets[gid] = {
        "theme": theme,
        "matchs": matchs,
        "tour": 1,
        "gagnants": [],
        "votes_en_cours": {},
        "channel": ctx.channel.id,
    }

    emoji_theme = "🎬" if theme == "kdrama" else "✨"
    embed = discord.Embed(
        title=f"{emoji_theme} TOURNOI {'KDRAMA' if theme == 'kdrama' else 'ANIMÉ'} — QG Kdrama",
        description=(
            f"**8 {('dramas' if theme == 'kdrama' else 'animés')} s'affrontent !**\n"
            f"Le serveur vote pour chaque duel — 24h par match !\n\n"
            f"🏆 Le champion sera couronné meilleur {'drama' if theme == 'kdrama' else 'animé'} du QG !\n\n"
            f"**TABLEAU :**\n" +
            "\n".join([f"⚔️ **{m[0]['nom']}** vs **{m[1]['nom']}**" for m in matchs])
        ),
        color=0xf1c40f
    )
    await ctx.send(embed=embed)
    await asyncio.sleep(2)

    # Lancer le premier match
    await bracket_lancer_match(ctx, gid, 0)

async def bracket_lancer_match(ctx, gid, match_idx):
    """Lance un match du bracket avec vote — se résout dès que tout le monde a voté"""
    if gid not in active_brackets:
        return
    game = active_brackets[gid]
    matchs = game["matchs"]
    if match_idx >= len(matchs):
        await bracket_fin_tour(ctx, gid)
        return

    a, b = matchs[match_idx]
    channel = ctx.guild.get_channel(game["channel"])
    theme_label = "Kdrama" if game["theme"] == "kdrama" else "Animé"
    emoji_theme = "🎬" if game["theme"] == "kdrama" else "✨"

    embed = discord.Embed(
        title=f"⚔️ DUEL — Tour {game['tour']} • Match {match_idx+1}/{len(matchs)}",
        description=(
            f"## 🅰️ {a['nom']}\n"
            f"**VS**\n"
            f"## 🅱️ {b['nom']}\n\n"
            f"👆 **Vote 🅰️ ou 🅱️ sur ce message !**\n"
            f"⏳ Le match se clôture après **5 minutes** — ou `.bracketskip` pour passer maintenant !"
        ),
        color=0xe74c3c
    )
    embed.set_footer(text=f"{emoji_theme} Tournoi {theme_label} — QG Kdrama | 8 participants tirés au sort parmi {len(BRACKET_KDRAMA if game['theme'] == 'kdrama' else BRACKET_ANIME)}")

    msg = await channel.send(embed=embed)
    await msg.add_reaction("🅰️")
    await msg.add_reaction("🅱️")

    game["votes_en_cours"][match_idx] = {
        "message_id": msg.id,
        "a": a,
        "b": b,
    }

    # Attendre 5 minutes puis résoudre
    await asyncio.sleep(300)
    if gid in active_brackets and match_idx in active_brackets[gid]["votes_en_cours"]:
        await bracket_resoudre_match(ctx.guild, gid, match_idx)

async def bracket_resoudre_match(guild, gid, match_idx):
    """Résout un match en comptant les réactions"""
    if gid not in active_brackets:
        return
    game = active_brackets[gid]
    if match_idx not in game["votes_en_cours"]:
        return

    vote_data = game["votes_en_cours"].pop(match_idx)
    channel = guild.get_channel(game["channel"])

    try:
        msg = await channel.fetch_message(vote_data["message_id"])
        votes_a = votes_b = 0
        for r in msg.reactions:
            if str(r.emoji) == "🅰️":
                votes_a = r.count - 1
            elif str(r.emoji) == "🅱️":
                votes_b = r.count - 1
    except:
        votes_a, votes_b = 0, 0

    gagnant = vote_data["a"] if votes_a >= votes_b else vote_data["b"]
    perdant = vote_data["b"] if votes_a >= votes_b else vote_data["a"]
    game["gagnants"].append(gagnant)

    embed = discord.Embed(
        title=f"✅ Résultat — {vote_data['a']['nom']} vs {vote_data['b']['nom']}",
        description=f"🏆 **{gagnant['nom']}** remporte ce duel ! ({votes_a} vs {votes_b} votes)\n💔 {perdant['nom']} est éliminé...",
        color=0x2ecc71
    )
    if gagnant.get("image"):
        embed.set_thumbnail(url=gagnant["image"])
    await channel.send(embed=embed)

    # Lancer le prochain match
    next_idx = match_idx + 1
    if next_idx < len(game["matchs"]):
        fake_ctx = type('obj', (object,), {'guild': guild, 'channel': channel})()
        await bracket_lancer_match(fake_ctx, gid, next_idx)
    else:
        await bracket_fin_tour_guild(guild, gid)

async def bracket_fin_tour_guild(guild, gid):
    """Passe au tour suivant ou proclame le champion"""
    if gid not in active_brackets:
        return
    game = active_brackets[gid]
    channel = guild.get_channel(game["channel"])

    if len(game["gagnants"]) == 1:
        # Champion !
        champion = game["gagnants"][0]
        embed = discord.Embed(
            title=f"🏆 CHAMPION DU QG !",
            description=f"🎉 **{champion['nom']}** est élu meilleur {'drama' if game['theme'] == 'kdrama' else 'animé'} du QG Kdrama ! 👑",
            color=0xf1c40f
        )
        if champion.get("image"):
            embed.set_image(url=champion["image"])
        await channel.send(embed=embed)
        del active_brackets[gid]
        return

    # Nouveau tour
    game["tour"] += 1
    nouveaux_matchs = []
    gagnants = game["gagnants"]
    for i in range(0, len(gagnants) - 1, 2):
        nouveaux_matchs.append((gagnants[i], gagnants[i+1]))
    if len(gagnants) % 2 == 1:
        nouveaux_matchs.append((gagnants[-1], random.choice(gagnants[:-1])))

    game["matchs"] = nouveaux_matchs
    game["gagnants"] = []

    embed = discord.Embed(
        title=f"🏆 Tour {game['tour']} — {len(nouveaux_matchs)} match(s) !",
        description="\n".join([f"⚔️ **{m[0]['nom']}** vs **{m[1]['nom']}**" for m in nouveaux_matchs]),
        color=0xf1c40f
    )
    await channel.send(embed=embed)

    fake_ctx = type('obj', (object,), {'guild': guild, 'channel': channel})()
    await bracket_lancer_match(fake_ctx, gid, 0)

async def bracket_fin_tour(ctx, gid):
    await bracket_fin_tour_guild(ctx.guild, gid)

@bot.command(name="bracketskip")
@commands.has_permissions(manage_guild=True)
async def bracket_skip(ctx):
    """Résout le match en cours immédiatement (admin)"""
    gid = ctx.guild.id
    if gid not in active_brackets:
        return await ctx.send("❌ Aucun tournoi en cours !")
    game = active_brackets[gid]
    if not game["votes_en_cours"]:
        return await ctx.send("❌ Aucun vote en cours !")
    idx = list(game["votes_en_cours"].keys())[0]
    await bracket_resoudre_match(ctx.guild, gid, idx)

@bot.command(name="bracketstop")
@commands.has_permissions(manage_guild=True)
async def bracket_stop(ctx):
    """Annule le tournoi en cours (admin)"""
    gid = ctx.guild.id
    if gid not in active_brackets:
        return await ctx.send("❌ Aucun tournoi en cours !")
    del active_brackets[gid]
    await ctx.send("🛑 Tournoi annulé !")

# ============================================================
#  🎰 SLOT MACHINE
# ============================================================
SLOT_SYMBOLES = ["🌸", "🗡️", "🦊", "👑", "🐉", "💎", "🎭", "⚡"]
SLOT_GAINS = {
    3: {"🌸": 50, "🗡️": 100, "🦊": 150, "👑": 300, "🐉": 500, "💎": 750, "🎭": 200, "⚡": 400},
    2: 20,
}
slot_cooldowns = {}

@bot.command(name="slot")
async def slot_cmd(ctx, mise: int = 50):
    if SALON_CASINO_ID and ctx.channel.id != SALON_CASINO_ID:
        salon = ctx.guild.get_channel(SALON_CASINO_ID)
        mention = salon.mention if salon else f"le salon casino"
        return await ctx.send(f"🎰 Le casino c'est dans {mention} seulement !", delete_after=5)
    """🎰 Slot machine ! — .slot [mise] (min 10, max 500)"""
    uid = str(ctx.author.id)
    mise = max(10, min(500, mise))

    if economy_data[uid]["coins"] < mise:
        return await ctx.send(f"❌ Tu n'as pas assez de pièces ! (Tu as {economy_data[uid]['coins']} pièces)")

    now = datetime.datetime.utcnow().timestamp()
    if uid in slot_cooldowns and now - slot_cooldowns[uid] < 10:
        return await ctx.send(f"⏳ Attends encore {int(10 - (now - slot_cooldowns[uid]))} secondes !")

    slot_cooldowns[uid] = now
    economy_data[uid]["coins"] -= mise

    # Animation
    msg = await ctx.send("🎰 | ⏳ | ⏳ | ⏳ |")
    await asyncio.sleep(0.7)
    r1 = random.choice(SLOT_SYMBOLES)
    await msg.edit(content=f"🎰 | {r1} | ⏳ | ⏳ |")
    await asyncio.sleep(0.7)
    r2 = random.choice(SLOT_SYMBOLES)
    await msg.edit(content=f"🎰 | {r1} | {r2} | ⏳ |")
    await asyncio.sleep(0.7)
    r3 = random.choice(SLOT_SYMBOLES)
    await msg.edit(content=f"🎰 | {r1} | {r2} | {r3} |")

    resultats = [r1, r2, r3]

    if r1 == r2 == r3:
        gain = SLOT_GAINS[3].get(r1, 100) * (mise // 10)
        gain_final = gain * 2 if casino_boost_actif else gain
        economy_data[uid]["coins"] += gain_final
        embed = discord.Embed(
            title="🎰 JACKPOT !!!",
            description=f"**{r1} {r2} {r3}**\n\n🎉 **+{gain} pièces !** Tu as misé {mise} et gagné {gain} ! 💰",
            color=0xf1c40f
        )
    elif r1 == r2 or r2 == r3 or r1 == r3:
        gain = SLOT_GAINS[2] * (mise // 10)
        economy_data[uid]["coins"] += gain
        embed = discord.Embed(
            title="🎰 Paire !",
            description=f"**{r1} {r2} {r3}**\n\n✅ **+{gain} pièces !**",
            color=0x2ecc71
        )
    else:
        embed = discord.Embed(
            title="🎰 Pas de chance...",
            description=f"**{r1} {r2} {r3}**\n\n💸 Tu as perdu **{mise} pièces**.",
            color=0xe74c3c
        )

    embed.set_footer(text=f"💰 Solde : {economy_data[uid]['coins']} pièces")
    await ctx.send(embed=embed)

# ============================================================
#  🐉 BOSS DE SERVEUR
# ============================================================
BOSS_LIST = [
    {"nom": "Le Titan Colossal", "anime": "Attack on Titan", "hp_max": 2000, "emoji": "👹", "image": "https://upload.wikimedia.org/wikipedia/en/thumb/8/85/Colossal_Titan_AoT.png/220px-Colossal_Titan_AoT.png", "recompense": 37},
    {"nom": "Muzan Kibutsuji", "anime": "Demon Slayer", "hp_max": 1500, "emoji": "🧛", "image": "https://upload.wikimedia.org/wikipedia/en/thumb/7/78/Muzan_Kibutsuji.png/220px-Muzan_Kibutsuji.png", "recompense": 250},
    {"nom": "Kaguya Otsutsuki", "anime": "Naruto", "hp_max": 1800, "emoji": "🌙", "image": "https://upload.wikimedia.org/wikipedia/en/thumb/4/4e/Kaguya_Otsutsuki.png/220px-Kaguya_Otsutsuki.png", "recompense": 280},
    {"nom": "Ryuk (Death Note)", "anime": "Death Note", "hp_max": 1200, "emoji": "💀", "image": "https://upload.wikimedia.org/wikipedia/en/thumb/1/13/Ryuk_Death_Note.png/220px-Ryuk_Death_Note.png", "recompense": 200},
    {"nom": "Gilgamesh", "anime": "Fate/Zero", "hp_max": 2500, "emoji": "⚔️", "image": "https://upload.wikimedia.org/wikipedia/en/thumb/4/44/Gilgamesh_Fate.png/220px-Gilgamesh_Fate.png", "recompense": 400},
]

active_boss = {}  # {guild_id: {boss, hp, participants, msg}}

@bot.command(name="boss")
@commands.has_permissions(manage_guild=True)
async def boss_cmd(ctx):
    """Fait apparaître un boss de serveur ! (admin) — .boss"""
    gid = ctx.guild.id
    if gid in active_boss:
        return await ctx.send("⚔️ Un boss est déjà en cours ! Tape `.attaque` pour combattre !", delete_after=5)

    boss = random.choice(BOSS_LIST)

    def barre_boss(hp, hp_max):
        ratio = hp / hp_max
        filled = int(ratio * 14)
        empty = 14 - filled
        if ratio > 0.6:   c = "🟩"
        elif ratio > 0.3: c = "🟨"
        else:             c = "🟥"
        return c * filled + "⬛" * empty

    def build_boss_embed(hp, derniere_attaque=None):
        ratio = hp / boss["hp_max"]
        pct = int(ratio * 100)
        color = 0xe74c3c if ratio < 0.3 else 0xf39c12 if ratio < 0.6 else 0x2ecc71

        desc = (
            f"## {boss['emoji']} {boss['nom']}\n"
            f"*{boss['anime']}*\n\n"
            f"❤️ **{hp:,} / {boss['hp_max']:,} HP** — {pct}%\n"
            f"{barre_boss(hp, boss['hp_max'])}\n\n"
        )
        if derniere_attaque:
            desc += f"⚔️ {derniere_attaque}\n\n"
        desc += f"━━━━━━━━━━━━━━━━━━━━\n"
        desc += f"🗡️ Tape `.attaque` pour frapper ! *(cooldown 13s)*\n"
        desc += f"🏆 Récompense : **{boss['recompense']} pièces** pour tous + **+250 bonus** au coup fatal !"

        embed = discord.Embed(description=desc, color=color)
        embed.set_image(url=boss["image"])
        embed.set_footer(text=f"QG Kdrama — Boss Event ⚔️")
        return embed

    msg = await ctx.send(embed=build_boss_embed(boss["hp_max"]))

    active_boss[gid] = {
        "boss": boss,
        "hp": boss["hp_max"],
        "participants": {},
        "channel": ctx.channel.id,
        "msg": msg,
        "barre_fn": barre_boss,
        "embed_fn": build_boss_embed,
    }

@bot.command(name="attaque")
async def attaque_cmd(ctx):
    """Attaque le boss en cours ! — .attaque"""
    gid = ctx.guild.id
    if gid not in active_boss:
        return await ctx.send("❌ Aucun boss en cours ! Attends qu'un admin lance `.boss`", delete_after=5)

    game = active_boss[gid]
    if game["hp"] <= 0:
        return await ctx.send("💀 Le boss est déjà vaincu !", delete_after=5)

    uid = str(ctx.author.id)
    now = datetime.datetime.utcnow().timestamp()

    last = game["participants"].get(uid, {}).get("last_attack", 0)
    if now - last < 13:
        restant = int(13 - (now - last))
        return await ctx.send(f"⏳ Cooldown — **{restant}s** restants !", delete_after=4)

    # Supprimer le message de commande pour garder le salon propre
    try:
        await ctx.message.delete()
    except:
        pass

    niveau = xp_data[uid]["level"]
    degats = random.randint(10 + niveau * 2, 30 + niveau * 5)

    if uid not in game["participants"]:
        game["participants"][uid] = {"degats_total": 0, "last_attack": 0, "membre": ctx.author.display_name}

    game["participants"][uid]["degats_total"] += degats
    game["participants"][uid]["last_attack"] = now
    game["hp"] = max(0, game["hp"] - degats)

    boss = game["boss"]
    build_embed = game["embed_fn"]

    if game["hp"] <= 0:
        # ── Boss vaincu ──────────────────────────────────────
        recompense = boss["recompense"]
        economy_data[uid]["coins"] += 250
        for pid, data in game["participants"].items():
            economy_data[pid]["coins"] += recompense
            xp_data[pid]["xp"] += 50

        top_participants = sorted(
            game["participants"].values(),
            key=lambda x: x["degats_total"],
            reverse=True
        )[:8]
        classement = "\n".join([
            f"{'🥇' if i==0 else '🥈' if i==1 else '🥉' if i==2 else f'`{i+1}.`'} **{d['membre']}** — {d['degats_total']:,} dégâts"
            for i, d in enumerate(top_participants)
        ])

        win_embed = discord.Embed(
            description=(
                f"## 💀 {boss['emoji']} {boss['nom']} est vaincu !\n\n"
                f"⚔️ **{ctx.author.display_name}** porte le **coup fatal** — *-{degats} dégâts* 💀\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🏆 **Classement des dégâts**\n{classement}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 Tous les participants reçoivent **{recompense} pièces** !\n"
                f"🎯 Coup fatal : **{ctx.author.display_name}** +250 pièces bonus !"
            ),
            color=0xf1c40f
        )
        win_embed.set_thumbnail(url=boss["image"])
        win_embed.set_footer(text="⚔️ Boss Event terminé — QG Kdrama")

        try:
            await game["msg"].edit(embed=win_embed)
        except:
            await ctx.send(embed=win_embed)

        del active_boss[gid]

    else:
        # ── Mise à jour de l'embed boss ──────────────────────
        derniere = f"**{ctx.author.display_name}** inflige **{degats:,} dégâts** !"
        try:
            await game["msg"].edit(embed=build_embed(game["hp"], derniere))
        except:
            game["msg"] = await ctx.send(embed=build_embed(game["hp"], derniere))



# ============================================================
#  ⚔️ ARÈNE PVP
# ============================================================
ATTAQUES_PVP = [
    {"nom": "Rasengan", "anime": "Naruto", "degats": (25, 45), "emoji": "🌀"},
    {"nom": "Souffle de l'Eau", "anime": "Demon Slayer", "degats": (20, 40), "emoji": "🌊"},
    {"nom": "Génie Alchimique", "anime": "FMA", "degats": (22, 42), "emoji": "⚗️"},
    {"nom": "Kamehameha", "anime": "Dragon Ball", "degats": (30, 55), "emoji": "⚡"},
    {"nom": "Omnidirectionnel", "anime": "AoT", "degats": (28, 50), "emoji": "🗡️"},
    {"nom": "Domaine Expansif", "anime": "JJK", "degats": (35, 60), "emoji": "💥"},
    {"nom": "Regard du Sharingan", "anime": "Naruto", "degats": (20, 38), "emoji": "👁️"},
    {"nom": "Attaque des Titans", "anime": "AoT", "degats": (40, 65), "emoji": "👹"},
    {"nom": "Esquive Divine", "anime": "One Piece", "degats": (0, 0), "emoji": "💨", "esquive": True},
    {"nom": "Soin du Muguet", "anime": "Demon Slayer", "degats": (-30, -20), "emoji": "🌸", "soin": True},
]

active_arene = {}

@bot.command(name="arene", aliases=["duel","pvp"])
async def arene_cmd(ctx, adversaire: discord.Member = None):
    """⚔️ Combat PvP en arène ! — .arene @joueur"""
    if SALON_DUEL_ID and ctx.channel.id != SALON_DUEL_ID:
        salon = ctx.guild.get_channel(SALON_DUEL_ID)
        mention = salon.mention if salon else "le salon duel"
        return await ctx.send(f"⚔️ L'arène c'est dans {mention} !", delete_after=5)
    if not adversaire or adversaire.bot or adversaire.id == ctx.author.id:
        return await ctx.send("❌ Mentionne un adversaire valide ! Ex: `.arene @ami`")
    if ctx.channel.id in active_arene:
        return await ctx.send("⚔️ Un combat est déjà en cours ici !")

    uid1 = str(ctx.author.id)
    uid2 = str(adversaire.id)

    def get_stats(uid):
        s = arena_stats[uid]
        return (
            250 + s["pv_bonus"]  * 8,
            100 + s["end_bonus"] * 5,
            s["atk_bonus"] * 3,
            s["def_bonus"] * 3,
        )

    hp1_max, end1_max, atk1_b, def1_b = get_stats(uid1)
    hp2_max, end2_max, atk2_b, def2_b = get_stats(uid2)

    # ── Invitation ────────────────────────────────────────────
    class InviteView(ui.View):
        def __init__(self):
            super().__init__(timeout=30)
            self.accepted = None
            self.done = asyncio.Event()
        @ui.button(label="Accepter ✅", style=discord.ButtonStyle.success)
        async def accept(self, interaction, button):
            if interaction.user.id != adversaire.id:
                return await interaction.response.send_message("❌ Pas ton défi !", ephemeral=True)
            self.accepted = True; self.done.set(); self.stop()
            await interaction.response.defer()
        @ui.button(label="Refuser ❌", style=discord.ButtonStyle.danger)
        async def refuse(self, interaction, button):
            if interaction.user.id != adversaire.id:
                return await interaction.response.send_message("❌ Pas ton défi !", ephemeral=True)
            self.accepted = False; self.done.set(); self.stop()
            await interaction.response.edit_message(content=f"❌ {adversaire.display_name} refuse.", view=None)

    invite_view = InviteView()
    await ctx.send(
        f"⚔️ **{ctx.author.mention}** défie **{adversaire.mention}** en arène !\n"
        f"*{adversaire.display_name} a 30 secondes pour accepter...*",
        view=invite_view
    )
    try:
        await asyncio.wait_for(invite_view.done.wait(), timeout=31)
    except asyncio.TimeoutError:
        pass
    if not invite_view.accepted:
        return

    # ── Setup ─────────────────────────────────────────────────
    joueurs = [
        {"membre": ctx.author,  "hp": hp1_max, "hp_max": hp1_max, "end": end1_max, "end_max": end1_max,
         "atk_b": atk1_b, "def_b": def1_b, "esquive": False, "defense": False, "couleur": "🔴"},
        {"membre": adversaire,  "hp": hp2_max, "hp_max": hp2_max, "end": end2_max, "end_max": end2_max,
         "atk_b": atk2_b, "def_b": def2_b, "esquive": False, "defense": False, "couleur": "🔵"},
    ]
    active_arene[ctx.channel.id] = True
    tour_num  = 1
    tour_idx  = 0
    REGEN_END = 12
    historique = []

    ACTIONS_INFO = {
        0: {"nom": "Attaque",          "emoji": "⚔️",  "cout": 10, "lo": 25, "hi": 40, "desc": "Frappe fiable"},
        1: {"nom": "Frappe Chargée",   "emoji": "💥",  "cout": 30, "lo": 10, "hi": 65, "desc": "Risqué mais dévastateur"},
        2: {"nom": "Att. Spéciale",    "emoji": "🌀",  "cout": 20, "lo": 30, "hi": 50, "desc": "Puissante et stable"},
        3: {"nom": "Défense",          "emoji": "🛡️", "cout": 5,  "lo": 0,  "hi": 0,  "desc": "−50% dégâts reçus"},
        4: {"nom": "Soin",             "emoji": "🌿",  "cout": 8,  "lo": 0,  "hi": 0,  "desc": "+15-30 HP"},
        5: {"nom": "Esquive",          "emoji": "💨",  "cout": 15, "lo": 0,  "hi": 0,  "desc": "Esquive secrète"},
    }

    def barre(val, maxi, longueur=14):
        rempli = int((val / max(maxi, 1)) * longueur)
        return "█" * rempli + "░" * (longueur - rempli)

    def build_embed_combat():
        j1, j2 = joueurs[0], joueurs[1]
        p1 = j1["hp"] / j1["hp_max"]; p2 = j2["hp"] / j2["hp_max"]
        c1 = "🔴" if p1 < 0.3 else ("🟡" if p1 < 0.6 else "🟢")
        c2 = "🔴" if p2 < 0.3 else ("🟡" if p2 < 0.6 else "🟢")
        embed = discord.Embed(
            title=f"⚔️  {j1['membre'].display_name}  ✦  VS  ✦  {j2['membre'].display_name}",
            color=0xe74c3c
        )
        embed.add_field(name="\u200b", value=(
            f"**{j1['couleur']} {j1['membre'].display_name}**\n"
            f"{c1} `{barre(j1['hp'], j1['hp_max'])}` **{j1['hp']}/{j1['hp_max']} HP**\n"
            f"⚡ `{barre(j1['end'], j1['end_max'])}` {j1['end']}/{j1['end_max']} END"
        ), inline=True)
        embed.add_field(name="\u200b", value=(
            f"**{j2['couleur']} {j2['membre'].display_name}**\n"
            f"{c2} `{barre(j2['hp'], j2['hp_max'])}` **{j2['hp']}/{j2['hp_max']} HP**\n"
            f"⚡ `{barre(j2['end'], j2['end_max'])}` {j2['end']}/{j2['end_max']} END"
        ), inline=True)
        # Séparateur + dernière action en bas bien visible
        embed.add_field(name="​", value="​", inline=False)
        if historique:
            embed.add_field(
                name="╔══ DERNIÈRE ACTION ══╗",
                value=f"> {historique[-1]}",
                inline=False
            )
        else:
            embed.add_field(
                name="╔══ DERNIÈRE ACTION ══╗",
                value=f"> ⏳ En attente de la première action...",
                inline=False
            )
        embed.set_footer(text=f"Tour {tour_num} • Arène PvP — QG Kdrama")
        return embed

    def build_view_actions(attaquant):
        """Boutons avec puissance + coût END dans le label"""
        v = ui.View(timeout=35)
        j = attaquant
        chosen = {"val": None}
        done_ev = asyncio.Event()

        for idx, a in ACTIONS_INFO.items():
            end_ok = j["end"] >= a["cout"]
            if a["lo"] > 0:
                label = f"{a['emoji']} {a['nom']} ({a['lo']}-{a['hi']} dmg / {a['cout']}⚡)"
            elif a["nom"] == "Soin":
                label = f"{a['emoji']} {a['nom']} (+15-30 HP / {a['cout']}⚡)"
            elif a["nom"] == "Défense":
                label = f"{a['emoji']} {a['nom']} (−50% dmg / {a['cout']}⚡)"
            else:
                label = f"{a['emoji']} {a['nom']} (? / {a['cout']}⚡)"

            style = discord.ButtonStyle.danger   if idx in (0,1) else \
                    discord.ButtonStyle.primary  if idx == 2     else \
                    discord.ButtonStyle.secondary if idx in (3,5) else \
                    discord.ButtonStyle.success
            btn = ui.Button(
                label=label[:80],
                style=style,
                disabled=not end_ok,
                row=idx // 3
            )
            async def cb(interaction, i=idx, ev=done_ev, ch=chosen):
                if interaction.user.id != j["membre"].id:
                    return await interaction.response.send_message("❌ C'est pas ton tour !", ephemeral=True)
                ch["val"] = i
                ev.set()
                # Esquive : confirmation éphémère visible que par ce joueur
                if i == 5:
                    await interaction.response.send_message(
                        "🤫 **Esquive activée !** Ton adversaire ne sait pas que tu vas esquiver.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.defer()
                v.stop()
            btn.callback = cb
            v.add_item(btn)

        return v, chosen, done_ev

    # Embed de début
    embed_debut = discord.Embed(
        title="⚔️ COMBAT COMMENCE ⚔️",
        description=(
            f"**⚔️ {ctx.author.display_name} VS {adversaire.display_name} ⚔️**\n\n"
            f"🔴 {ctx.author.display_name} — {hp1_max} HP • {end1_max} END\n"
            f"🔵 {adversaire.display_name} — {hp2_max} HP • {end2_max} END\n\n"
            f"*Stats boostées par vos points d'amélioration !*\n"
            f"**{ctx.author.display_name} commence !**"
        ),
        color=0xe74c3c
    )
    embed_debut.set_footer(text="Arène PvP — QG Kdrama")
    await ctx.send(embed=embed_debut)
    combat_msg = await ctx.send(embed=build_embed_combat())

    # ── Boucle principale ─────────────────────────────────────
    while ctx.channel.id in active_arene:
        attaquant = joueurs[tour_idx]
        defenseur = joueurs[1 - tour_idx]
        attaquant["end"] = min(attaquant["end_max"], attaquant["end"] + REGEN_END)

        view, chosen, done_ev = build_view_actions(attaquant)

        await combat_msg.edit(
            content=f"🎮 {attaquant['membre'].mention} — **C'est ton tour !**",
            embed=build_embed_combat(),
            view=view
        )

        try:
            await asyncio.wait_for(done_ev.wait(), timeout=36)
        except asyncio.TimeoutError:
            chosen["val"] = 0
        view.stop()

        choix = chosen["val"] if chosen["val"] is not None else 0
        action = ACTIONS_INFO[choix]
        cout   = action["cout"]

        if attaquant["end"] < cout:
            choix = 0; action = ACTIONS_INFO[0]; cout = action["cout"]
            historique.append(f"⚡ {attaquant['membre'].display_name} manque d'END — attaque de base !")

        attaquant["end"] = max(0, attaquant["end"] - cout)
        nom_a = attaquant["membre"].display_name
        nom_d = defenseur["membre"].display_name

        if choix == 3:   # Défense
            attaquant["defense"] = True
            historique.append(f"🛡️ **{nom_a}** se défend ! *(dégâts −50% ce tour)*")

        elif choix == 4: # Soin
            soin = random.randint(15, 30)
            attaquant["hp"] = min(attaquant["hp_max"], attaquant["hp"] + soin)
            historique.append(f"🌿 **{nom_a}** se soigne — **+{soin} HP** !")

        elif choix == 5: # Esquive secrète
            attaquant["esquive"] = True
            # Pas de message public — juste l'ephemeral déjà envoyé via interaction
            historique.append(f"💨 **{nom_a}** se prépare... *(action secrète)*")

        else:  # Attaques 0 1 2
            base = random.randint(action["lo"], action["hi"]) + attaquant["atk_b"]
            base = max(1, base - defenseur["def_b"])
            critique = random.random() < 0.12
            if critique: base = int(base * 1.5)

            if defenseur["esquive"]:
                defenseur["esquive"] = False
                historique.append(f"💨 **{nom_a}** attaque... **{nom_d}** esquive ! *0 dégâts*")
            else:
                if defenseur["defense"]:
                    base //= 2
                    defenseur["defense"] = False
                defenseur["hp"] = max(0, defenseur["hp"] - base)
                crit = " ✦ ***CRITIQUE !***" if critique else ""
                historique.append(f"{action['emoji']} **{nom_a}** {action['nom'].lower()} — **−{base} HP** !{crit}")

        tour_num += 1
        tour_idx  = 1 - tour_idx

        ko = None
        if joueurs[0]["hp"] <= 0: ko = (joueurs[1], joueurs[0])
        if joueurs[1]["hp"] <= 0: ko = (joueurs[0], joueurs[1])

        if ko:
            winner, loser = ko
            active_arene.pop(ctx.channel.id, None)
            prize   = random.randint(100, 250)
            xp_gain = 40
            economy_data[str(winner["membre"].id)]["coins"] += prize
            xp_data[str(winner["membre"].id)]["xp"]         += xp_gain

            await combat_msg.edit(content=None, embed=build_embed_combat(), view=None)

            wname  = winner["membre"].display_name
            lname  = loser["membre"].display_name
            whp    = winner["hp"]; whpmax = winner["hp_max"]
            embed_fin = discord.Embed(title="🏆 FIN DU COMBAT 🏆", color=0xf1c40f)
            embed_fin.description = (
                f"**{wname} remporte l'arène !**\n\n"
                f"`{barre(whp, whpmax)}` **{whp} / {whpmax} HP restants**\n\n"
                f"💰 **+{prize} pièces** • ⭐ **+{xp_gain} XP**\n\n"
                f"*{lname} s'effondre... ☠️*"
            )
            embed_fin.set_footer(text="Arène PvP — QG Kdrama")
            await ctx.send(embed=embed_fin)
            return

        await combat_msg.edit(content=None, embed=build_embed_combat(), view=None)

@bot.command(name="pokebattle", aliases=["pb", "pokefight"])
async def pokebattle_cmd(ctx, adversaire: discord.Member = None):
    """⚔️ Combat 3v3 avec tes cartes gacha ! — .pokebattle @joueur"""
    if SALON_COMBAT_ID and ctx.channel.id != SALON_COMBAT_ID:
        salon = ctx.guild.get_channel(SALON_COMBAT_ID)
        mention = salon.mention if salon else "le salon combat"
        return await ctx.send(f"⚔️ Les combats de cartes c'est dans {mention} !", delete_after=5)
    if not adversaire or adversaire.bot or adversaire.id == ctx.author.id:
        return await ctx.send("❌ Mentionne un adversaire valide ! Ex: `.pokebattle @ami`")
    if ctx.channel.id in active_pokebattles:
        return await ctx.send("⚔️ Un combat est déjà en cours ici !")

    uid1 = str(ctx.author.id)
    uid2 = str(adversaire.id)
    col1 = gacha_collections[uid1]
    col2 = gacha_collections[uid2]
    if len(col1) < 3:
        return await ctx.send(f"❌ **{ctx.author.display_name}** n'a pas assez de cartes ! (minimum 3)")
    if len(col2) < 3:
        return await ctx.send(f"❌ **{adversaire.display_name}** n'a pas assez de cartes ! (minimum 3)")

    async def choisir_equipe(joueur):
        uid = str(joueur.id)
        col = gacha_collections[uid]
        order = collection_order.get(uid, [])
        all_keys = [k for k in order if k in col] + [k for k in col if k not in order]
        valid_keys = [k for k in all_keys if k in ANIME_CARDS_DB]
        if len(valid_keys) < 3:
            return None
        chosen  = []
        page    = [0]
        PAGE_SZ = 5
        done_ev = asyncio.Event()

        def build_view():
            v = ui.View(timeout=90)
            start = page[0] * PAGE_SZ
            keys_page = valid_keys[start:start + PAGE_SZ]
            total_pages = (len(valid_keys) - 1) // PAGE_SZ + 1
            for i2, key in enumerate(keys_page):
                c   = ANIME_CARDS_DB[key]
                lv  = fusion_levels[uid].get(key, 0)
                stars = "⭐" * lv if lv else ""
                already = key in [x["key"] for x in chosen]
                btn = ui.Button(
                    label=f"{c['nom'][:15]}{stars}",
                    emoji=c.get("emoji", "⚔️"),
                    style=discord.ButtonStyle.success if already else discord.ButtonStyle.secondary,
                    disabled=already,
                    row=i2 // 3
                )
                async def cb(interaction, k=key, card=c):
                    if interaction.user.id != joueur.id:
                        return await interaction.response.send_message("❌ Pas ton tour !", ephemeral=True)
                    lv2 = fusion_levels[uid].get(k, 0)
                    new_card = card.copy()
                    new_card["key"] = k
                    new_card["pv"]       = new_card["pv"]      + lv2 * 20
                    new_card["attaque"]  = new_card["attaque"] + lv2 * 15
                    new_card["defense"]  = new_card["defense"] + lv2 * 10
                    new_card["hp_actuel"] = new_card["pv"]
                    new_card["ko"] = False
                    chosen.append(new_card)
                    noms_choisis = " • ".join(f"{c2['emoji']} **{c2['nom']}**" for c2 in chosen)
                    if len(chosen) >= 3:
                        done_ev.set()
                        await interaction.response.edit_message(
                            content=f"✅ **{joueur.display_name}** — Équipe prête !\n{noms_choisis}",
                            view=None
                        )
                    else:
                        await interaction.response.edit_message(
                            content=f"⚔️ **{joueur.display_name}** — Choisis tes 3 cartes ({len(chosen)}/3) :\n✅ {noms_choisis}",
                            view=build_view()
                        )
                btn.callback = cb
                v.add_item(btn)
            if total_pages > 1:
                prev_btn = ui.Button(label="◀", style=discord.ButtonStyle.primary, disabled=page[0] == 0, row=2)
                info_btn = ui.Button(label=f"Page {page[0]+1}/{total_pages}", style=discord.ButtonStyle.secondary, disabled=True, row=2)
                next_btn = ui.Button(label="▶", style=discord.ButtonStyle.primary, disabled=page[0] >= total_pages - 1, row=2)
                async def prev_cb(interaction):
                    if interaction.user.id != joueur.id:
                        return await interaction.response.send_message("❌", ephemeral=True)
                    page[0] = max(0, page[0] - 1)
                    await interaction.response.edit_message(view=build_view())
                async def next_cb(interaction):
                    if interaction.user.id != joueur.id:
                        return await interaction.response.send_message("❌", ephemeral=True)
                    page[0] = min(total_pages - 1, page[0] + 1)
                    await interaction.response.edit_message(view=build_view())
                prev_btn.callback = prev_cb
                next_btn.callback = next_cb
                v.add_item(prev_btn); v.add_item(info_btn); v.add_item(next_btn)
            return v

        await ctx.send(
            content=f"⚔️ **{joueur.display_name}** — Choisis tes **3 cartes** (0/3) :",
            view=build_view()
        )
        try:
            await asyncio.wait_for(done_ev.wait(), timeout=90)
        except asyncio.TimeoutError:
            return None
        return chosen if len(chosen) >= 3 else None

    await ctx.send(embed=discord.Embed(
        description=(
            f"⚡ **{ctx.author.mention}** défie **{adversaire.mention}** — Combat 3v3 !\n"
            "Chacun choisit son équipe..."
        ),
        color=0x7000ff
    ))
    equipe1 = await choisir_equipe(ctx.author)
    if not equipe1:
        return await ctx.send(f"❌ **{ctx.author.display_name}** n'a pas choisi son équipe !")
    equipe2 = await choisir_equipe(adversaire)
    if not equipe2:
        return await ctx.send(f"❌ **{adversaire.display_name}** n'a pas choisi son équipe !")

    active_pokebattles[ctx.channel.id] = {
        "j1": {"membre": ctx.author,  "equipe": equipe1, "actif": 0},
        "j2": {"membre": adversaire,  "equipe": equipe2, "actif": 0},
        "tour": ctx.author.id,
        "tour_num": 1,
    }

    def carte_active(j): return j["equipe"][j["actif"]]

    def barre_pb(val, maxi, longueur=10):
        rempli = int((val / max(maxi, 1)) * longueur)
        return "█" * rempli + "░" * (longueur - rempli)

    def equipe_str(j):
        return " | ".join(
            f"{'💀' if c['ko'] else c['emoji']} {c['nom']} `{c['hp_actuel']}HP`"
            for c in j["equipe"]
        )

    def build_embed_pb():
        game = active_pokebattles.get(ctx.channel.id, {})
        j1_g = game.get("j1"); j2_g = game.get("j2")
        if not j1_g or not j2_g:
            return discord.Embed(title="Combat terminé")
        c1 = carte_active(j1_g); c2 = carte_active(j2_g)
        pct1 = c1["hp_actuel"] / max(c1["pv"], 1)
        pct2 = c2["hp_actuel"] / max(c2["pv"], 1)
        col1 = "🔴" if pct1 < 0.3 else ("🟡" if pct1 < 0.6 else "🟢")
        col2 = "🔴" if pct2 < 0.3 else ("🟡" if pct2 < 0.6 else "🟢")
        embed = discord.Embed(
            title=f"⚔️ {j1_g['membre'].display_name}  VS  {j2_g['membre'].display_name}",
            color=0x9b59b6
        )
        embed.add_field(name="\u200b", value=(
            f"🔴 **{j1_g['membre'].display_name}**\n"
            f"{c1['emoji']} **{c1['nom']}**\n"
            f"{col1} {barre_pb(c1['hp_actuel'], c1['pv'])} `{c1['hp_actuel']}/{c1['pv']}HP`\n"
            f"*Équipe :* {equipe_str(j1_g)}"
        ), inline=True)
        embed.add_field(name="\u200b", value=(
            f"🔵 **{j2_g['membre'].display_name}**\n"
            f"{c2['emoji']} **{c2['nom']}**\n"
            f"{col2} {barre_pb(c2['hp_actuel'], c2['pv'])} `{c2['hp_actuel']}/{c2['pv']}HP`\n"
            f"*Équipe :* {equipe_str(j2_g)}"
        ), inline=True)
        embed.set_footer(text=f"Tour {game.get('tour_num', 1)} • Combat 3v3 — QG Kdrama")
        return embed

    combat_msg = await ctx.send(embed=build_embed_pb())

    while ctx.channel.id in active_pokebattles:
        game = active_pokebattles[ctx.channel.id]
        j1_g = game["j1"]; j2_g = game["j2"]

        if all(c["ko"] for c in j1_g["equipe"]):
            del active_pokebattles[ctx.channel.id]
            economy_data[str(j2_g["membre"].id)]["coins"] += 300
            xp_data[str(j2_g["membre"].id)]["xp"] += 60
            await combat_msg.edit(embed=build_embed_pb(), view=None, content=None)
            await ctx.send(embed=discord.Embed(
                title="🏆 FIN DU COMBAT !",
                description=f"🎉 **{j2_g['membre'].mention}** remporte le combat 3v3 !\n💰 **+300 pièces** • ⭐ **+60 XP**",
                color=0xf1c40f
            ))
            return
        if all(c["ko"] for c in j2_g["equipe"]):
            del active_pokebattles[ctx.channel.id]
            economy_data[str(j1_g["membre"].id)]["coins"] += 300
            xp_data[str(j1_g["membre"].id)]["xp"] += 60
            await combat_msg.edit(embed=build_embed_pb(), view=None, content=None)
            await ctx.send(embed=discord.Embed(
                title="🏆 FIN DU COMBAT !",
                description=f"🎉 **{j1_g['membre'].mention}** remporte le combat 3v3 !\n💰 **+300 pièces** • ⭐ **+60 XP**",
                color=0xf1c40f
            ))
            return

        current = j1_g if game["tour"] == j1_g["membre"].id else j2_g
        other   = j2_g if game["tour"] == j1_g["membre"].id else j1_g
        while carte_active(current)["ko"]:
            current["actif"] = (current["actif"] + 1) % 3

        chosen_action = asyncio.Event()
        action_result = {"choix": None}

        class CombatButtons(ui.View):
            def __init__(self):
                super().__init__(timeout=45)
            async def check_p(self, interaction):
                if interaction.user.id != current["membre"].id:
                    await interaction.response.send_message("❌ Pas ton tour !", ephemeral=True)
                    return False
                return True
            @ui.button(label="Attaque 1 ⚔️", style=discord.ButtonStyle.danger, row=0)
            async def btn1(self, i, b):
                if not await self.check_p(i): return
                action_result["choix"] = 0; chosen_action.set(); self.stop(); await i.response.defer()
            @ui.button(label="Attaque 2 💥", style=discord.ButtonStyle.danger, row=0)
            async def btn2(self, i, b):
                if not await self.check_p(i): return
                action_result["choix"] = 1; chosen_action.set(); self.stop(); await i.response.defer()
            @ui.button(label="Attaque 3 🌀", style=discord.ButtonStyle.primary, row=0)
            async def btn3(self, i, b):
                if not await self.check_p(i): return
                action_result["choix"] = 2; chosen_action.set(); self.stop(); await i.response.defer()
            @ui.button(label="Changer 🔄", style=discord.ButtonStyle.secondary, row=1)
            async def btn_swap(self, i, b):
                if not await self.check_p(i): return
                action_result["choix"] = "swap"; chosen_action.set(); self.stop(); await i.response.defer()
            async def on_timeout(self):
                action_result["choix"] = 0; chosen_action.set()

        view = CombatButtons()
        await combat_msg.edit(
            content=f"🎮 {current['membre'].mention} — **C'est ton tour !**",
            embed=build_embed_pb(), view=view
        )
        try:
            await asyncio.wait_for(chosen_action.wait(), timeout=46)
        except asyncio.TimeoutError:
            action_result["choix"] = 0

        choix = action_result["choix"]
        carte_cur = carte_active(current)
        carte_adv = carte_active(other)

        if choix == "swap":
            dispo = [(i3, c) for i3, c in enumerate(current["equipe"]) if not c["ko"] and i3 != current["actif"]]
            if dispo:
                current["actif"] = dispo[0][0]
            game["tour"] = other["membre"].id
            game["tour_num"] += 1
            await combat_msg.edit(content=None, embed=build_embed_pb(), view=None)
            continue

        attaques = carte_cur.get("attaques", [])
        if isinstance(choix, int) and choix < len(attaques):
            base = attaques[choix].get("degats", 30)
            if base == 0: base = random.randint(20, 35)
        else:
            base = random.randint(25, 40)

        critique = random.random() < 0.12
        if critique: base = int(base * 1.5)
        ratio = carte_cur["attaque"] / max(carte_adv["defense"], 1)
        degats = int(base * min(ratio, 2.0))
        degats = max(5, degats)
        carte_adv["hp_actuel"] = max(0, carte_adv["hp_actuel"] - degats)

        if carte_adv["hp_actuel"] <= 0:
            carte_adv["ko"] = True
            next_idx = next((i4 for i4, c in enumerate(other["equipe"]) if not c["ko"]), None)
            if next_idx is not None:
                other["actif"] = next_idx

        game["tour"] = other["membre"].id
        game["tour_num"] += 1
        await combat_msg.edit(content=None, embed=build_embed_pb(), view=None)

@bot.command(name="pokestop", aliases=["stopcombat"])
async def pokestop(ctx):
    """Annule le combat en cours — .pokestop"""
    if ctx.channel.id in active_pokebattles:
        del active_pokebattles[ctx.channel.id]
        await ctx.send("🛑 Combat annulé !")
    else:
        await ctx.send("❌ Aucun combat en cours !")






# ============================================================
#  🃏 BASE DE DONNÉES CARTES GACHA
# ============================================================
ANIME_CARDS_DB = {
    # ── NARUTO ──────────────────────────────────────────────
    "naruto":    {"nom":"Naruto Uzumaki",  "serie":"Naruto",          "rarete":"Légendaire", "emoji":"🍥", "pv":220,"attaque":90,"defense":70,"image":"https://i.imgur.com/sDvyV8G.jpg","attaques":[{"nom":"Rasengan","emoji":"🌀","degats":45,"desc": "Frappe spirale"},{"nom":"Kage Bunshin","emoji":"👥","degats":35,"desc": "Clones"},{"nom":"Neuf Queues","emoji":"🦊","degats":60,"desc": "Puissance ultime"}],"faiblesse":"⚡","resistance":"🔥"},
    "sasuke":    {"nom":"Sasuke Uchiha",   "serie":"Naruto",          "rarete":"Légendaire", "emoji":"⚡", "pv":200,"attaque":95,"defense":75,"image":"https://i.imgur.com/4dx82Ou.jpg","attaques":[{"nom":"Chidori","emoji":"⚡","degats":50,"desc": "Foudre"},{"nom":"Sharingan","emoji":"👁️","degats":30,"desc": "Copie"},{"nom":"Amaterasu","emoji":"🔥","degats":65,"desc": "Flammes noires"}],"faiblesse":"💧","resistance":"⚡"},
    "sakura":    {"nom":"Sakura Haruno",   "serie":"Naruto",          "rarete":"Rare",       "emoji":"🌸", "pv":180,"attaque":75,"defense":85,"image":"https://i.imgur.com/OlSv1D1.jpg","attaques":[{"nom":"Frappe","emoji":"👊","degats":40,"desc": "Coup de poing"},{"nom":"Soin","emoji":"💚","degats":0,"desc": "Guérison"},{"nom":"Cent Frappe","emoji":"💥","degats":55,"desc": "Destruction"}],"faiblesse":"⚡","resistance":"🌸"},
    "kurapika":  {"nom":"Kurapika",        "serie":"HunterxHunter",   "rarete":"Légendaire",     "emoji":"🔗", "pv":195,"attaque":88,"defense":72,"image":"https://i.imgur.com/HNfrNAo.jpg","attaques":[{"nom":"Chaînes","emoji":"🔗","degats":45,"desc": "Emprisonne"},{"nom":"Jugement","emoji":"⚖️","degats":55,"desc": "Exécution"},{"nom":"Vol Cœur","emoji":"❤️","degats":70,"desc": "Fatal sur araignée"}],"faiblesse":"🔥","resistance":"🔗"},
    "shikamaru": {"nom":"Shikamaru Nara",  "serie":"Naruto",          "rarete":"Rare",       "emoji":"🦌", "pv":175,"attaque":70,"defense":80,"image":"https://i.imgur.com/P8VrZXS.jpg","attaques":[{"nom":"Kagemane","emoji":"🌑","degats":35,"desc": "Immobilise"},{"nom":"Ombre","emoji":"🌒","degats":45,"desc": "Contrôle"},{"nom":"Ombre Étreinte","emoji":"💀","degats":55,"desc": "Fatal"}],"faiblesse":"🔥","resistance":"🌑"},
    "obito":     {"nom":"Obito Uchiha",    "serie":"Naruto",          "rarete":"Légendaire",   "emoji":"👁️", "pv":230,"attaque":100,"defense":90,"image":"https://i.imgur.com/9DMerh1.jpg","attaques":[{"nom":"Kamui","emoji":"🌀","degats":60,"desc": "Intangibilité"},{"nom":"Sharingan","emoji":"👁️","degats":45,"desc": "Illusion"},{"nom":"Dix Queues","emoji":"🐉","degats":80,"desc": "Dévastateur"}],"faiblesse":"💧","resistance":"👁️"},
    # ── DEMON SLAYER ────────────────────────────────────────
    "inosuke":   {"nom":"Inosuke Hashibira","serie":"Demon Slayer",   "rarete":"Épique",       "emoji":"🐗", "pv":215,"attaque":90,"defense":65,"image":"https://i.imgur.com/At5236C.jpg","attaques":[{"nom":"Bête","emoji":"🐗","degats":50,"desc": "Respiration bête"},{"nom":"Poignard","emoji":"🗡️","degats":40,"desc": "Double lame"},{"nom":"Frenésie","emoji":"💢","degats":60,"desc": "Attaque sauvage"}],"faiblesse":"⚡","resistance":"🐗"},
    "nobara":    {"nom":"Nobara Kugisaki", "serie":"Jujutsu Kaisen",  "rarete":"Épique",       "emoji":"🔨", "pv":185,"attaque":82,"defense":68,"image":"https://i.imgur.com/UAfmEnA.jpg","attaques":[{"nom":"Clou Résonance","emoji":"🔨","degats":45,"desc": "Cloue l'ennemi"},{"nom":"Paille Poupée","emoji":"🪆","degats":55,"desc": "Vaudou"},{"nom":"Explosion","emoji":"💥","degats":65,"desc": "Détonation"}],"faiblesse":"🌊","resistance":"🔨"},
    # ── JUJUTSU KAISEN ──────────────────────────────────────
    # ── ONE PIECE ────────────────────────────────────────────
    "usopp":     {"nom":"Usopp",           "serie":"One Piece",       "rarete":"Commun",     "emoji":"🎯", "pv":170,"attaque":72,"defense":60,"image":"https://i.imgur.com/0kobHRe.jpg","attaques":[{"nom":"Sarbacane","emoji":"🎯","degats":35,"desc": "Précision"},{"nom":"Pop Green","emoji":"🌿","degats":40,"desc": "Plante explosive"},{"nom":"Sogeking","emoji":"⭐","degats":50,"desc": "Sniper légendaire"}],"faiblesse":"🔥","resistance":"🎯"},
    # ── SWORD ART ONLINE ─────────────────────────────────────
    "asuna":     {"nom":"Asuna Yuuki",     "serie":"SAO",             "rarete":"Légendaire", "emoji":"⚡", "pv":200,"attaque":93,"defense":76,"image":"https://i.imgur.com/qAWf8kO.jpg","attaques":[{"nom":"Linear","emoji":"⚡","degats":55,"desc": "Frappe éclair"},{"nom":"Lambent Light","emoji":"💛","degats":65,"desc": "Épée lumineuse"},{"nom":"Mother's Rosario","emoji":"🌹","degats":80,"desc": "Combo ultime"}],"faiblesse":"🔥","resistance":"⚡"},
    # ── DARLING IN THE FRANXX ────────────────────────────────
    "zerotwo":   {"nom":"Zero Two",        "serie":"Darling in the FranXX","rarete":"Mythique","emoji":"💗","pv":235,"attaque":102,"defense":80,"image":"https://i.imgur.com/z8RKZDk.jpg","attaques":[{"nom":"Strelizia","emoji":"🌺","degats":70,"desc": "Frappe pilote"},{"nom":"Griffes","emoji":"💅","degats":50,"desc": "Lacère"},{"nom":"Apus","emoji":"💗","degats":90,"desc": "Forme ultime"}],"faiblesse":"💧","resistance":"💗"},
    # ── GHOST IN THE SHELL ───────────────────────────────────
    "motoko":    {"nom":"Motoko Kusanagi", "serie":"Ghost in the Shell","rarete":"Épique",   "emoji":"🤖", "pv":200,"attaque":90,"defense":85,"image":"https://i.imgur.com/sKV6DLP.jpg","attaques":[{"nom":"Hack","emoji":"💻","degats":45,"desc": "Piratage"},{"nom":"Tachikoma","emoji":"🦾","degats":55,"desc": "Appui tactique"},{"nom":"Ghost","emoji":"👻","degats":65,"desc": "Invisibilité"}],"faiblesse":"⚡","resistance":"🤖"},
    # ── SPY X FAMILY ─────────────────────────────────────────
    "anya":      {"nom":"Anya Forger",     "serie":"Spy x Family",    "rarete":"Rare",       "emoji":"🌟", "pv":160,"attaque":65,"defense":70,"image":"https://i.imgur.com/AN18DVZ.jpg","attaques":[{"nom":"Télépathe","emoji":"🧠","degats":30,"desc": "Lit les pensées"},{"nom":"Heh","emoji":"😏","degats":40,"desc": "Sourire dévastateur"},{"nom":"Secret","emoji":"🌟","degats":50,"desc": "Pouvoir caché"}],"faiblesse":"🔥","resistance":"🧠"},
    "yor":       {"nom":"Yor Forger",      "serie":"Spy x Family",    "rarete":"Épique",     "emoji":"🌹", "pv":210,"attaque":94,"defense":78,"image":"https://i.imgur.com/zyzDBqB.jpg","attaques":[{"nom":"Épine","emoji":"🌹","degats":55,"desc": "Assassine"},{"nom":"Coup","emoji":"👊","degats":45,"desc": "Force surhumaine"},{"nom":"Thorn Princess","emoji":"🩸","degats":70,"desc": "Mode assassin"}],"faiblesse":"⚡","resistance":"🌹"},
    # ── FAIRY TAIL ───────────────────────────────────────────
    "natsu":     {"nom":"Natsu Dragneel",  "serie":"Fairy Tail",      "rarete":"Légendaire", "emoji":"🔥", "pv":220,"attaque":96,"defense":72,"image":"https://i.imgur.com/3My9M8G.jpg","attaques":[{"nom":"Roar du Dragon","emoji":"🔥","degats":60,"desc": "Souffle de feu"},{"nom":"Dragon Force","emoji":"🐉","degats":80,"desc": "Forme draconique"},{"nom":"Etherious","emoji":"💀","degats":95,"desc": "Démon ultime"}],"faiblesse":"💧","resistance":"🔥"},
    "lucy":      {"nom":"Lucy Heartfilia", "serie":"Fairy Tail",      "rarete":"Rare",       "emoji":"⭐", "pv":180,"attaque":76,"defense":74,"image":"https://i.imgur.com/MzIPqLA.jpg","attaques":[{"nom":"Invocation","emoji":"⭐","degats":45,"desc": "Esprits stellaires"},{"nom":"Aquarius","emoji":"💧","degats":55,"desc": "Vague destructrice"},{"nom":"Stardress","emoji":"✨","degats":65,"desc": "Fusion cosmique"}],"faiblesse":"🔥","resistance":"💧"},
    "laxus":     {"nom":"Laxus Dreyar",   "serie":"Fairy Tail",      "rarete":"Légendaire",     "emoji":"⚡", "pv":215,"attaque":97,"defense":80,"image":"https://i.imgur.com/R7pPgj2.jpg","attaques":[{"nom":"Tonnerre","emoji":"⚡","degats":60,"desc": "Frappe électrique"},{"nom":"Dragon Foudre","emoji":"🌩️","degats":75,"desc": "Dragon électrique"},{"nom":"Hell's Core","emoji":"💥","degats":85,"desc": "Destruction totale"}],"faiblesse":"🌊","resistance":"⚡"},
    # ── BLEACH ───────────────────────────────────────────────
    "aizen":     {"nom":"Sosuke Aizen",    "serie":"Bleach",          "rarete":"Mythique",   "emoji":"🦋", "pv":245,"attaque":108,"defense":95,"image":"https://i.imgur.com/rtSGfrn.jpg","attaques":[{"nom":"Kyoka Suigetsu","emoji":"🪞","degats":75,"desc": "Illusion parfaite"},{"nom":"Transcendance","emoji":"🦋","degats":90,"desc": "Au-delà du shinigami"},{"nom":"Hogyoku","emoji":"💎","degats":105,"desc": "Pouvoir absolu"}],"faiblesse":"💀","resistance":"🦋"},
    "kenpachi":  {"nom":"Kenpachi Zaraki", "serie":"Bleach",          "rarete":"Légendaire", "emoji":"⚔️", "pv":240,"attaque":105,"defense":75,"image":"https://i.imgur.com/NbnX1cV.jpg","attaques":[{"nom":"Slash","emoji":"⚔️","degats":65,"desc": "Coupe brute"},{"nom":"Nozarashi","emoji":"🪓","degats":80,"desc": "Shikai brutal"},{"nom":"Bankai","emoji":"💥","degats":95,"desc": "Berserker"}],"faiblesse":"🌀","resistance":"⚔️"},
    "ulquiorra": {"nom":"Ulquiorra Cifer", "serie":"Bleach",          "rarete":"Légendaire",     "emoji":"🖤", "pv":210,"attaque":96,"defense":88,"image":"https://i.imgur.com/TymaPDb.jpg","attaques":[{"nom":"Cero","emoji":"🖤","degats":60,"desc": "Rayon néant"},{"nom":"Lanza","emoji":"💚","degats":75,"desc": "Lance du tonnerre"},{"nom":"Segunda","emoji":"🦇","degats":90,"desc": "Résurrection 2ème"}],"faiblesse":"💛","resistance":"🖤"},
    "yhwach":    {"nom":"Yhwach",          "serie":"Bleach",          "rarete":"Légendaire",   "emoji":"👑", "pv":255,"attaque":115,"defense":100,"image":"https://i.imgur.com/UR1i6Tb.jpg","attaques":[{"nom":"Almighty","emoji":"👑","degats":100,"desc": "Voit tout"},{"nom":"Sankt Bogen","emoji":"🏹","degats":80,"desc": "Arc sacré"},{"nom":"Auswählen","emoji":"☠️","degats":110,"desc": "Sélection divine"}],"faiblesse":"💀","resistance":"👑"},
    # ── DRAGON BALL ──────────────────────────────────────────
    "krillin":   {"nom":"Krillin",         "serie":"Dragon Ball Z",   "rarete":"Commun",     "emoji":"😊", "pv":175,"attaque":70,"defense":72,"image":"https://i.imgur.com/bXQogaK.jpg","attaques":[{"nom":"Destructo Disc","emoji":"💿","degats":45,"desc": "Disque tranchant"},{"nom":"Kamehameha","emoji":"🌊","degats":35,"desc": "Version mini"},{"nom":"Kienzan","emoji":"⭕","degats":50,"desc": "Tranche tout"}],"faiblesse":"🟡","resistance":"💿"},
    # ── ATTACK ON TITAN ──────────────────────────────────────
    # ── MHA ──────────────────────────────────────────────────
    # ── DEATH NOTE ───────────────────────────────────────────
    "light":     {"nom":"Light Yagami",    "serie":"Death Note",      "rarete":"Légendaire", "emoji":"📓", "pv":175,"attaque":85,"defense":90,"image":"https://i.imgur.com/pKi0RvA.jpg","attaques":[{"nom":"Death Note","emoji":"📓","degats":80,"desc": "Écrit le nom"},{"nom":"Kira","emoji":"👁️","degats":65,"desc": "Jugement divin"},{"nom":"Stratégie","emoji":"♟️","degats":55,"desc": "Manipulation"}],"faiblesse":"🔍","resistance":"📓"},
    "l":         {"nom":"L Lawliet",       "serie":"Death Note",      "rarete":"Légendaire", "emoji":"🍬", "pv":170,"attaque":82,"defense":88,"image":"https://i.imgur.com/mh0S7OP.jpg","attaques":[{"nom":"Déduction","emoji":"🔍","degats":70,"desc": "Logique implacable"},{"nom":"Piège","emoji":"🪤","degats":60,"desc": "Tend un piège"},{"nom":"Justice","emoji":"⚖️","degats":75,"desc": "Révèle la vérité"}],"faiblesse":"📓","resistance":"🔍"},
    # ── STEINS GATE ──────────────────────────────────────────
    "okabe":     {"nom":"Rintaro Okabe",   "serie":"Steins;Gate",     "rarete":"Rare",     "emoji":"📡", "pv":180,"attaque":75,"defense":80,"image":"https://i.imgur.com/h8AR8Xt.jpg","attaques":[{"nom":"SERN","emoji":"📡","degats":45,"desc": "Manipulation temps"},{"nom":"Reading Steiner","emoji":"🌀","degats":55,"desc": "Sauts temporels"},{"nom":"El Psy Kongroo","emoji":"🧪","degats":65,"desc": "Science folle"}],"faiblesse":"💔","resistance":"📡"},
    "kurisu":    {"nom":"Kurisu Makise",   "serie":"Steins;Gate",     "rarete":"Épique",     "emoji":"🧪", "pv":175,"attaque":78,"defense":82,"image":"https://i.imgur.com/3n57wKG.jpg","attaques":[{"nom":"Théorie","emoji":"🧪","degats":50,"desc": "Intelligence pure"},{"nom":"PhDs","emoji":"📚","degats":40,"desc": "Savoir absolu"},{"nom":"Temps","emoji":"⏰","degats":65,"desc": "Maîtrise temporelle"}],"faiblesse":"💔","resistance":"🧪"},
    # ── COWBOY BEBOP ─────────────────────────────────────────
    "spike":     {"nom":"Spike Spiegel",   "serie":"Cowboy Bebop",    "rarete":"Légendaire", "emoji":"🚀", "pv":200,"attaque":91,"defense":76,"image":"https://i.imgur.com/gV63xoo.jpg","attaques":[{"nom":"Jeet Kune Do","emoji":"🥊","degats":55,"desc": "Arts martiaux"},{"nom":"Beretta","emoji":"🔫","degats":60,"desc": "Pistolero"},{"nom":"Dragon","emoji":"🐉","degats":75,"desc": "Technique secrète"}],"faiblesse":"💔","resistance":"🚀"},
    "faye":      {"nom":"Faye Valentine",  "serie":"Cowboy Bebop",    "rarete":"Épique",       "emoji":"💜", "pv":185,"attaque":82,"defense":70,"image":"https://i.imgur.com/1i8e1kK.jpg","attaques":[{"nom":"Pistolet","emoji":"🔫","degats":45,"desc": "Tir précis"},{"nom":"Séduction","emoji":"💜","degats":35,"desc": "Déstabilise"},{"nom":"Tir Rapide","emoji":"⚡","degats":55,"desc": "Rafale"}],"faiblesse":"🚀","resistance":"💜"},
    # ── VIOLET EVERGARDEN ────────────────────────────────────
    "violet":    {"nom":"Violet Evergarden","serie":"Violet Evergarden","rarete":"Épique",   "emoji":"💌", "pv":190,"attaque":86,"defense":80,"image":"https://i.imgur.com/q3rwJ3M.jpg","attaques":[{"nom":"Lames","emoji":"⚔️","degats":55,"desc": "Combat militaire"},{"nom":"Lettre","emoji":"💌","degats":40,"desc": "Émotion intense"},{"nom":"Soldat","emoji":"🪖","degats":70,"desc": "Instinct guerrier"}],"faiblesse":"💔","resistance":"💌"},
    # ── OVERLORD ─────────────────────────────────────────────
    "ainz":      {"nom":"Ainz Ooal Gown",  "serie":"Overlord",        "rarete":"Mythique",   "emoji":"💀", "pv":250,"attaque":112,"defense":98,"image":"https://i.imgur.com/fgV5T6r.jpg","attaques":[{"nom":"Grasp Heart","emoji":"💀","degats":90,"desc": "Stop cardiaque"},{"nom":"Fallen Down","emoji":"☠️","degats":100,"desc": "Annihilation"},{"nom":"True Death","emoji":"💀","degats":115,"desc": "Mort absolue"}],"faiblesse":"✨","resistance":"💀"},
    "albedo":    {"nom":"Albedo",           "serie":"Overlord",        "rarete":"Épique", "emoji":"🖤", "pv":220,"attaque":95,"defense":95,"image":"https://i.imgur.com/XBoMVup.jpg","attaques":[{"nom":"Bouclier","emoji":"🛡️","degats":50,"desc": "Défense ultime"},{"nom":"Frappe","emoji":"💥","degats":65,"desc": "Force démoniaque"},{"nom":"Valkyrie","emoji":"🖤","degats":80,"desc": "Mode combat"}],"faiblesse":"✨","resistance":"🖤"},
    # ── RE:ZERO ───────────────────────────────────────────────
    "subaru":    {"nom":"Subaru Natsuki",   "serie":"Re:Zero",         "rarete":"Épique",       "emoji":"💙", "pv":185,"attaque":72,"defense":70,"image":"https://i.imgur.com/hq5JhSO.jpg","attaques":[{"nom":"Retour","emoji":"⏪","degats":40,"desc": "Recommence"},{"nom":"Ombre","emoji":"🌑","degats":50,"desc": "Pouvoirs noirs"},{"nom":"Dévotion","emoji":"💙","degats":60,"desc": "Volonté pure"}],"faiblesse":"💔","resistance":"💙"},
    "emilia":    {"nom":"Emilia",           "serie":"Re:Zero",         "rarete":"Épique",     "emoji":"❄️", "pv":195,"attaque":85,"defense":78,"image":"https://i.imgur.com/gTrkjMj.jpg","attaques":[{"nom":"Glace","emoji":"❄️","degats":55,"desc": "Magie de glace"},{"nom":"Gel","emoji":"🧊","degats":65,"desc": "Congèle tout"},{"nom":"Barrière","emoji":"🛡️","degats":45,"desc": "Protection glacée"}],"faiblesse":"🔥","resistance":"❄️"},
    # ── BERSERK ──────────────────────────────────────────────
    "guts":      {"nom":"Guts",            "serie":"Berserk",         "rarete":"Légendaire",   "emoji":"⚫", "pv":245,"attaque":108,"defense":85,"image":"https://i.imgur.com/PgjWnwG.jpg","attaques":[{"nom":"Dragonslayer","emoji":"⚫","degats":85,"desc": "Épée géante"},{"nom":"Berserker","emoji":"🐺","degats":100,"desc": "Armure berserker"},{"nom":"Canonnade","emoji":"💥","degats":75,"desc": "Bras canon"}],"faiblesse":"💀","resistance":"⚫"},
    "griffith":  {"nom":"Griffith",        "serie":"Berserk",         "rarete":"Mythique",   "emoji":"🦅", "pv":240,"attaque":106,"defense":92,"image":"https://i.imgur.com/2pJDLG5.jpg","attaques":[{"nom":"Femto","emoji":"🦅","degats":90,"desc": "Apôtre divin"},{"nom":"Causalité","emoji":"🌑","degats":80,"desc": "Destin inévitable"},{"nom":"Godhand","emoji":"☠️","degats":105,"desc": "Dieu de la chair"}],"faiblesse":"⚫","resistance":"🦅"},
    # ── SPY X FAMILY / MOB PSYCHO / AUTRES ───────────────────
    "mob":       {"nom":"Shigeo Kageyama", "serie":"Mob Psycho 100",  "rarete":"Mythique",   "emoji":"🔮", "pv":235,"attaque":107,"defense":88,"image":"https://i.imgur.com/twihMkj.jpg","attaques":[{"nom":"100%","emoji":"🔮","degats":95,"desc": "Débordement psychique"},{"nom":"Télékinésie","emoji":"🌀","degats":65,"desc": "Manipulation objet"},{"nom":"???%","emoji":"💥","degats":115,"desc": "Au-delà de tout"}],"faiblesse":"💔","resistance":"🔮"},
    "reigen":    {"nom":"Reigen Arataka",  "serie":"Mob Psycho 100",  "rarete":"Rare",       "emoji":"👔", "pv":170,"attaque":68,"defense":85,"image":"https://i.imgur.com/8E78wJD.jpg","attaques":[{"nom":"Salt Splash","emoji":"🧂","degats":35,"desc": "Exorcise à sel"},{"nom":"Massage","emoji":"✋","degats":25,"desc": "Décontracte"},{"nom":"Arnaque","emoji":"👔","degats":45,"desc": "Trompe l'adversaire"}],"faiblesse":"🔮","resistance":"👔"},
    # ── MELIODAS / SEVEN DEADLY SINS ─────────────────────────
    "meliodas":  {"nom":"Meliodas",        "serie":"Seven Deadly Sins","rarete":"Mythique",  "emoji":"🐉", "pv":245,"attaque":110,"defense":90,"image":"https://i.imgur.com/zkxcN5n.jpg","attaques":[{"nom":"Full Counter","emoji":"🔄","degats":80,"desc": "Renvoie les attaques"},{"nom":"Revenge Counter","emoji":"💥","degats":95,"desc": "Accumulé x10"},{"nom":"Demon King","emoji":"🐉","degats":110,"desc": "Mode roi démon"}],"faiblesse":"✨","resistance":"🐉"},
    "escanor":   {"nom":"Escanor",         "serie":"Seven Deadly Sins","rarete":"Mythique",  "emoji":"☀️", "pv":240,"attaque":115,"defense":80,"image":"https://i.imgur.com/ob5Fqky.jpg","attaques":[{"nom":"Pride","emoji":"☀️","degats":95,"desc": "Orgueil solaire"},{"nom":"The One","emoji":"👑","degats":115,"desc": "Forme ultime"},{"nom":"Sunshine","emoji":"🌞","degats":85,"desc": "Chaleur divine"}],"faiblesse":"🌙","resistance":"☀️"},
    "ban":       {"nom":"Ban",             "serie":"Seven Deadly Sins","rarete":"Légendaire","emoji":"🍺", "pv":999,"attaque":88,"defense":999,"image":"https://i.imgur.com/37tOayw.jpg","attaques":[{"nom":"Vol","emoji":"🤏","degats":55,"desc": "Vole les stats"},{"nom":"Fox Hunt","emoji":"🦊","degats":70,"desc": "Frappe multiple"},{"nom":"Zero Sign","emoji":"∞","degats":80,"desc": "Immortalité parfaite"}],"faiblesse":"💔","resistance":"⚔️"},
    "arthur_ks": {"nom":"Arthur Pendragon","serie":"Seven Deadly Sins","rarete":"Légendaire","emoji":"🗡️", "pv":215,"attaque":98,"defense":85,"image":"https://i.imgur.com/drRQ5hX.jpg","attaques":[{"nom":"Excalibur","emoji":"🗡️","degats":70,"desc": "Épée sacrée"},{"nom":"Chaos","emoji":"🌀","degats":85,"desc": "Pouvoir du chaos"},{"nom":"Roi Chaos","emoji":"👑","degats":95,"desc": "Maître du chaos"}],"faiblesse":"💀","resistance":"🗡️"},
    # ── TOWER OF GOD ─────────────────────────────────────────
    "bam":       {"nom":"Twenty-Fifth Bam","serie":"Tower of God",    "rarete":"Légendaire",   "emoji":"🕯️", "pv":240,"attaque":104,"defense":86,"image":"https://i.imgur.com/43t3sLi.jpg","attaques":[{"nom":"Shinsu","emoji":"🕯️","degats":70,"desc": "Contrôle shinsu"},{"nom":"Baam","emoji":"⚡","degats":85,"desc": "Pouvoir irrégulier"},{"nom":"Thorn","emoji":"🌑","degats":100,"desc": "Fragment d'épine"}],"faiblesse":"🌊","resistance":"🕯️"},
    "white":     {"nom":"White (Arlen)",   "serie":"Tower of God",    "rarete":"Épique",     "emoji":"🤍", "pv":205,"attaque":95,"defense":80,"image":"https://i.imgur.com/oxHxTsI.jpg","attaques":[{"nom":"Fantôme","emoji":"🤍","degats":60,"desc": "Attaque spectrale"},{"nom":"Âme","emoji":"👻","degats":70,"desc": "Dévore l'âme"},{"nom":"Blade","emoji":"🗡️","degats":80,"desc": "Lame blanche"}],"faiblesse":"🕯️","resistance":"🤍"},
    # ── VINLAND SAGA ─────────────────────────────────────────
    "thorkell":  {"nom":"Thorkell",        "serie":"Vinland Saga",    "rarete":"Légendaire", "emoji":"🪓", "pv":235,"attaque":102,"defense":78,"image":"https://i.imgur.com/NPh93gb.jpg","attaques":[{"nom":"Hache","emoji":"🪓","degats":70,"desc": "Frappe titanesque"},{"nom":"Lancer","emoji":"🎯","degats":60,"desc": "Javeline précise"},{"nom":"Berserker","emoji":"💢","degats":85,"desc": "Rage viking"}],"faiblesse":"🏹","resistance":"🪓"},
    "thorfinn":  {"nom":"Thorfinn",        "serie":"Vinland Saga",    "rarete":"Légendaire",     "emoji":"🗡️", "pv":200,"attaque":92,"defense":74,"image":"https://i.imgur.com/SjwyGc4.jpg","attaques":[{"nom":"Dague","emoji":"🗡️","degats":50,"desc": "Double dague"},{"nom":"Fantôme","emoji":"💨","degats":65,"desc": "Vitesse fantôme"},{"nom":"Askeladd","emoji":"⚔️","degats":75,"desc": "Héritage"}],"faiblesse":"🪓","resistance":"🗡️"},
    # ── FULLMETAL ALCHEMIST ──────────────────────────────────
    "edward":    {"nom":"Edward Elric",    "serie":"FMA Brotherhood", "rarete":"Épique", "emoji":"⚗️", "pv":205,"attaque":90,"defense":80,"image":"https://i.imgur.com/5xTiio2.jpg","attaques":[{"nom":"Alchimie","emoji":"⚗️","degats":55,"desc": "Transmutation"},{"nom":"Lance","emoji":"🗡️","degats":65,"desc": "Bras alchimique"},{"nom":"Frappe","emoji":"💪","degats":75,"desc": "Poing automail"}],"faiblesse":"💧","resistance":"⚗️"},
    "alphonse":  {"nom":"Alphonse Elric",  "serie":"FMA Brotherhood", "rarete":"Épique",     "emoji":"🛡️", "pv":220,"attaque":85,"defense":95,"image":"https://i.imgur.com/Ge8EMLN.jpg","attaques":[{"nom":"Armure","emoji":"🛡️","degats":50,"desc": "Frappe d'armure"},{"nom":"Alchimie","emoji":"⚗️","degats":60,"desc": "Transmutation"},{"nom":"Flamme","emoji":"🔥","degats":70,"desc": "Alchimie de feu"}],"faiblesse":"⚡","resistance":"🛡️"},
    "roy":       {"nom":"Roy Mustang",     "serie":"FMA Brotherhood", "rarete":"Épique", "emoji":"🔥", "pv":195,"attaque":97,"defense":78,"image":"https://i.imgur.com/sCqq6aL.jpg","attaques":[{"nom":"Inferno","emoji":"🔥","degats":70,"desc": "Alchimie de feu"},{"nom":"Flamme","emoji":"🔥","degats":55,"desc": "Claquement de doigts"},{"nom":"Soleil","emoji":"☀️","degats":80,"desc": "Chaleur infernale"}],"faiblesse":"💧","resistance":"🔥"},
    # ── BAKI ─────────────────────────────────────────────────
    "baki":      {"nom":"Baki Hanma",      "serie":"Baki",            "rarete":"Légendaire", "emoji":"💪", "pv":220,"attaque":98,"defense":80,"image":"https://i.imgur.com/6kAHdw4.jpg","attaques":[{"nom":"Coordinatrice","emoji":"💪","degats":65,"desc": "Force brute"},{"nom":"Imitateur","emoji":"🦈","degats":75,"desc": "Copie n'importe quoi"},{"nom":"Tremblement","emoji":"💥","degats":85,"desc": "Frappe vibratoire"}],"faiblesse":"🔮","resistance":"💪"},
    "yujiro":    {"nom":"Yujiro Hanma",    "serie":"Baki",            "rarete":"Mythique",   "emoji":"👹", "pv":255,"attaque":120,"defense":95,"image":"https://i.imgur.com/q7nhyXN.jpg","attaques":[{"nom":"Démon","emoji":"👹","degats":100,"desc": "Dos démoniaque"},{"nom":"Coordinatrice","emoji":"💪","degats":85,"desc": "Force absolue"},{"nom":"Ogre","emoji":"☠️","degats":115,"desc": "L'être le plus fort"}],"faiblesse":"💔","resistance":"👹"},
    # ── HUNTER X HUNTER (AUTRES) ─────────────────────────────
    "meruem":    {"nom":"Meruem",          "serie":"HunterxHunter",   "rarete":"Mythique",   "emoji":"♟️", "pv":250,"attaque":118,"defense":100,"image":"https://i.imgur.com/ajOXRt1.jpg","attaques":[{"nom":"Hakai","emoji":"♟️","degats":95,"desc": "Destruction pure"},{"nom":"Absorption","emoji":"🍽️","degats":80,"desc": "Vole les pouvoirs"},{"nom":"Rose","emoji":"☠️","degats":110,"desc": "Après Rose"}],"faiblesse":"🌹","resistance":"♟️"},
    # ── HELLSING ─────────────────────────────────────────────
    "alucard":   {"nom":"Alucard",         "serie":"Hellsing",        "rarete":"Mythique",   "emoji":"🧛", "pv":999,"attaque":116,"defense":999,"image":"https://i.imgur.com/EoRtG4W.jpg","attaques":[{"nom":"Restriction 0","emoji":"🧛","degats":100,"desc": "Légion d'âmes"},{"nom":"Hell","emoji":"🩸","degats":85,"desc": "Régénération"},{"nom":"Alucard Mode","emoji":"☠️","degats":115,"desc": "Vrai vampire"}],"faiblesse":"✝️","resistance":"🩸"},
    # ── GINTAMA ──────────────────────────────────────────────
    "gintoki":   {"nom":"Gintoki Sakata",  "serie":"Gintama",         "rarete":"Légendaire", "emoji":"🍬", "pv":210,"attaque":95,"defense":82,"image":"https://i.imgur.com/pKHhZQx.jpg","attaques":[{"nom":"Bokuto","emoji":"🪵","degats":55,"desc": "Sabre en bois"},{"nom":"Shiroyasha","emoji":"⚪","degats":80,"desc": "Démon blanc"},{"nom":"Benizakura","emoji":"🌸","degats":90,"desc": "Sabre démon"}],"faiblesse":"💧","resistance":"⚪"},
    # ── PARASYTE ─────────────────────────────────────────────
    "shinichi_p":{"nom":"Shinichi Izumi",  "serie":"Parasyte",        "rarete":"Épique",     "emoji":"🧠", "pv":195,"attaque":88,"defense":82,"image":"https://i.imgur.com/U71h4AQ.jpg","attaques":[{"nom":"Migi","emoji":"🧠","degats":60,"desc": "Parasite droit"},{"nom":"Régénération","emoji":"💚","degats":45,"desc": "Se régénère"},{"nom":"Sens","emoji":"👁️","degats":70,"desc": "Sens surhumains"}],"faiblesse":"🔥","resistance":"🧠"},
    # ── MADE IN ABYSS ────────────────────────────────────────
    "reg":       {"nom":"Reg",             "serie":"Made in Abyss",   "rarete":"Épique",     "emoji":"🤖", "pv":200,"attaque":90,"defense":88,"image":"https://i.imgur.com/UGyjNna.jpg","attaques":[{"nom":"Incinerator","emoji":"🔆","degats":85,"desc": "Laser dévastateur"},{"nom":"Bras","emoji":"🦾","degats":55,"desc": "Extension bras"},{"nom":"Forge","emoji":"🔥","degats":70,"desc": "Chaleur intense"}],"faiblesse":"💧","resistance":"🤖"},
    # ── FATE ─────────────────────────────────────────────────
    "saber":     {"nom":"Saber (Artoria)", "serie":"Fate",            "rarete":"Légendaire",   "emoji":"⚔️", "pv":225,"attaque":103,"defense":90,"image":"https://i.imgur.com/ntmap4C.jpg","attaques":[{"nom":"Excalibur","emoji":"✨","degats":90,"desc": "Épée du roi"},{"nom":"Caliburn","emoji":"⚔️","degats":75,"desc": "Épée sacrée"},{"nom":"Rhongomyniad","emoji":"🏹","degats":85,"desc": "Lance de lumière"}],"faiblesse":"🌑","resistance":"⚔️"},
    "gilgamesh": {"nom":"Gilgamesh",       "serie":"Fate",            "rarete":"Légendaire",   "emoji":"👑", "pv":235,"attaque":112,"defense":88,"image":"https://i.imgur.com/I1Ee0CF.jpg","attaques":[{"nom":"Gate of Babylon","emoji":"🔶","degats":95,"desc": "Trésor du roi"},{"nom":"Ea","emoji":"🌍","degats":110,"desc": "Brise le monde"},{"nom":"Enkidu","emoji":"🔗","degats":80,"desc": "Chaîne divine"}],"faiblesse":"💚","resistance":"👑"},
    # ── DETECTIVE CONAN ──────────────────────────────────────
    "conan":     {"nom":"Shinichi Kudo",   "serie":"Detective Conan", "rarete":"Rare",       "emoji":"🔍", "pv":170,"attaque":75,"defense":80,"image":"https://i.imgur.com/OeZ10pT.jpg","attaques":[{"nom":"Déduction","emoji":"🔍","degats":55,"desc": "Résout tout"},{"nom":"Chaussure","emoji":"👟","degats":45,"desc": "Tir de précision"},{"nom":"Révèle","emoji":"💡","degats":65,"desc": "Démonte l'adversaire"}],"faiblesse":"📓","resistance":"🔍"},
    # ── KUROKO NO BASKET ─────────────────────────────────────
    "kuroko":    {"nom":"Tetsuya Kuroko",  "serie":"Kuroko no Basket","rarete":"Rare",       "emoji":"🏀", "pv":165,"attaque":70,"defense":75,"image":"https://i.imgur.com/MdR5ne3.jpg","attaques":[{"nom":"Passe Fantôme","emoji":"👻","degats":35,"desc": "Invisible"},{"nom":"Ignite Pass","emoji":"🏀","degats":45,"desc": "Passe furtive"},{"nom":"Meteor Drive","emoji":"⭐","degats":55,"desc": "Smash fantôme"}],"faiblesse":"👁️","resistance":"👻"},
    # ── KAITO KID ────────────────────────────────────────────
    "kaito":     {"nom":"Kaito Kid",       "serie":"Magic Kaito",     "rarete":"Rare",       "emoji":"🃏", "pv":175,"attaque":76,"defense":78,"image":"https://i.imgur.com/3kzs82L.jpg","attaques":[{"nom":"Illusion","emoji":"🃏","degats":45,"desc": "Trompe l'adversaire"},{"nom":"Cartes","emoji":"🎴","degats":40,"desc": "Cartes tranchantes"},{"nom":"Disparition","emoji":"💨","degats":55,"desc": "Échappe à tout"}],"faiblesse":"🔍","resistance":"🃏"},
    # ── KILLER BEE ───────────────────────────────────────────
    "killerbee": {"nom":"Killer Bee",      "serie":"Naruto",          "rarete":"Épique",     "emoji":"🐝", "pv":215,"attaque":94,"defense":80,"image":"https://i.imgur.com/xWtK4by.jpg","attaques":[{"nom":"Gyuki","emoji":"🐙","degats":70,"desc": "Huit queues"},{"nom":"Raps","emoji":"🎤","degats":40,"desc": "Choc sonore"},{"nom":"Jinchuriki","emoji":"🐝","degats":85,"desc": "Transformation"}],"faiblesse":"⚡","resistance":"🐝"},
    # ── NARUTO ENCORE ────────────────────────────────────────
    "minato":    {"nom":"Minato Namikaze", "serie":"Naruto",          "rarete":"Légendaire",   "emoji":"⚡", "pv":215,"attaque":106,"defense":85,"image":"https://i.imgur.com/6CZlrb7.jpg","attaques":[{"nom":"Rasengan","emoji":"🌀","degats":70,"desc": "Père du Rasengan"},{"nom":"Hiraishin","emoji":"⚡","degats":85,"desc": "Vol du Dieu"},{"nom":"Sceau","emoji":"✍️","degats":95,"desc": "Sacrifie tout"}],"faiblesse":"💧","resistance":"⚡"},
    # ── YAO HUI / MANHWA ─────────────────────────────────────
    "yama":      {"nom":"Yama (GoH)",      "serie":"God of High School","rarete":"Mythique",  "emoji":"🐯","pv":245,"attaque":111,"defense":88,"image":"https://i.imgur.com/p420qv7.jpg","attaques":[{"nom":"Tiger","emoji":"🐯","degats":85,"desc": "Arts martiaux"},{"nom":"Borrowed Power","emoji":"⚡","degats":95,"desc": "Pouvoir emprunté"},{"nom":"True Form","emoji":"💥","degats":110,"desc": "Forme vraie"}],"faiblesse":"🌊","resistance":"🐯"},
    "jinmori":   {"nom":"Jin Mo-Ri",       "serie":"God of High School","rarete":"Mythique",  "emoji":"🌪️","pv":248,"attaque":113,"defense":90,"image":"https://i.imgur.com/IwpTyww.jpg","attaques":[{"nom":"Hwi Chul","emoji":"🌪️","degats":80,"desc": "Tourbillon"},{"nom":"Mimicry","emoji":"🐒","degats":90,"desc": "Copie Goku"},{"nom":"Sun Wukong","emoji":"☁️","degats":110,"desc": "Roi singe"}],"faiblesse":"💀","resistance":"🌪️"},
    # ── KENSHIRO ─────────────────────────────────────────────
    "kenshiro":  {"nom":"Kenshiro",        "serie":"Hokuto no Ken",   "rarete":"Mythique",   "emoji":"☠️", "pv":240,"attaque":115,"defense":88,"image":"https://i.imgur.com/5QlIuRx.jpg","attaques":[{"nom":"Hokuto Shinken","emoji":"☠️","degats":95,"desc": "Tu es déjà mort"},{"nom":"Points Vitaux","emoji":"💢","degats":80,"desc": "Pression fatale"},{"nom":"Ryuken","emoji":"⭐","degats":110,"desc": "Étoile du Nord"}],"faiblesse":"🌊","resistance":"☠️"},
    # ── NOELLE ───────────────────────────────────────────────
    "noelle":    {"nom":"Noelle Silva",    "serie":"Black Clover",    "rarete":"Épique",     "emoji":"💧", "pv":200,"attaque":87,"defense":80,"image":"https://i.imgur.com/IE0nG9f.jpg","attaques":[{"nom":"Sea Dragon","emoji":"🐉","degats":65,"desc": "Dragon d'eau"},{"nom":"Bouclier","emoji":"💧","degats":45,"desc": "Mur aquatique"},{"nom":"Valkyrie","emoji":"⚔️","degats":80,"desc": "Armure de guerre"}],"faiblesse":"⚡","resistance":"💧"},
    # ── NARUTO (nouveaux) ────────────────────────────────────
    "itachi":    {"nom":"Itachi Uchiha",   "serie":"Naruto",          "rarete":"Légendaire",   "emoji":"🔴", "pv":225,"attaque":105,"defense":90,"image":"https://i.imgur.com/UIA8L7u.jpg","attaques":[{"nom":"Tsukuyomi","emoji":"🔴","degats":85,"desc": "Illusion infernale"},{"nom":"Amaterasu","emoji":"🔥","degats":75,"desc": "Flammes noires"},{"nom":"Susanoo","emoji":"🛡️","degats":95,"desc": "Armure divine"}],"faiblesse":"💧","resistance":"🔴"},
    "kakashi":   {"nom":"Kakashi Hatake",  "serie":"Naruto",          "rarete":"Légendaire", "emoji":"⚡", "pv":205,"attaque":96,"defense":85,"image":"https://i.imgur.com/XcHGLHb.jpg","attaques":[{"nom":"Chidori","emoji":"⚡","degats":65,"desc": "Mille oiseaux"},{"nom":"Sharingan","emoji":"👁️","degats":50,"desc": "Œil copieur"},{"nom":"Kamui","emoji":"🌀","degats":80,"desc": "Dimension autre"}],"faiblesse":"💧","resistance":"⚡"},
    "madara":    {"nom":"Madara Uchiha",   "serie":"Naruto",          "rarete":"Légendaire",   "emoji":"👁️", "pv":250,"attaque":115,"defense":95,"image":"https://i.imgur.com/FYEJwwH.jpg","attaques":[{"nom":"Meteore","emoji":"☄️","degats":100,"desc": "Fait tomber des meteores"},{"nom":"Susanoo","emoji":"⚔️","degats":90,"desc": "Guerrier colossal"},{"nom":"Edo Tensei","emoji":"💀","degats":110,"desc": "Immortel"}],"faiblesse":"💧","resistance":"👁️"},
    "kaguya":    {"nom":"Kaguya Otsutsuki","serie":"Naruto",          "rarete":"Mythique",   "emoji":"🌸", "pv":255,"attaque":118,"defense":100,"image":"https://i.imgur.com/6E9Q66v.jpg","attaques":[{"nom":"Ash Bones","emoji":"🦴","degats":100,"desc": "Os qui tuent"},{"nom":"Portail","emoji":"🌀","degats":90,"desc": "Dimension de cendres"},{"nom":"Omnipotence","emoji":"🌸","degats":115,"desc": "Chakra originel"}],"faiblesse":"⚡","resistance":"🌸"},
    # ── BLEACH (nouveaux) ────────────────────────────────────
    "ichigo":    {"nom":"Ichigo Kurosaki", "serie":"Bleach",          "rarete":"Légendaire",   "emoji":"🌙", "pv":235,"attaque":103,"defense":85,"image":"https://i.imgur.com/tGmGlBB.jpg","attaques":[{"nom":"Getsuga Tensho","emoji":"🌙","degats":70,"desc": "Lune tranchante"},{"nom":"Bankai","emoji":"💀","degats":85,"desc": "Tensa Zangetsu"},{"nom":"Final Getsuga","emoji":"☠️","degats":100,"desc": "Forme finale"}],"faiblesse":"🔥","resistance":"🌙"},
    # ── ATTACK ON TITAN (nouveaux) ────────────────────────────
    "levi":      {"nom":"Levi Ackerman",   "serie":"Attack on Titan", "rarete":"Légendaire",   "emoji":"⚔️", "pv":205,"attaque":105,"defense":80,"image":"https://i.imgur.com/cvXCIWl.jpg","attaques":[{"nom":"Tourbillon","emoji":"🌪️","degats":80,"desc": "Spin légendaire"},{"nom":"Lame","emoji":"⚔️","degats":60,"desc": "Précision absolue"},{"nom":"Ackerman","emoji":"💢","degats":95,"desc": "Pouvoir du clan"}],"faiblesse":"💥","resistance":"⚔️"},
    "eren":      {"nom":"Eren Yeager",     "serie":"Attack on Titan", "rarete":"Légendaire", "emoji":"🔑", "pv":225,"attaque":97,"defense":78,"image":"https://i.imgur.com/BE73Bud.jpg","attaques":[{"nom":"Titan","emoji":"👣","degats":65,"desc": "Transformation"},{"nom":"Rumbling","emoji":"🌍","degats":90,"desc": "Grondement"},{"nom":"Fondateur","emoji":"🔑","degats":100,"desc": "Titan fondateur"}],"faiblesse":"⚡","resistance":"🔑"},
    "erwin":     {"nom":"Erwin Smith",     "serie":"Attack on Titan", "rarete":"Épique",     "emoji":"🦅", "pv":190,"attaque":80,"defense":82,"image":"https://i.imgur.com/jV3h5SB.jpg","attaques":[{"nom":"Charge","emoji":"🦅","degats":55,"desc": "Charge héroïque"},{"nom":"Tactique","emoji":"♟️","degats":65,"desc": "Stratège brillant"},{"nom":"Sacrifice","emoji":"💀","degats":75,"desc": "Tout pour l'humanité"}],"faiblesse":"💥","resistance":"🦅"},
    "mikasa":    {"nom":"Mikasa Ackerman", "serie":"Attack on Titan", "rarete":"Légendaire", "emoji":"❤️", "pv":210,"attaque":100,"defense":82,"image":"https://i.imgur.com/vwLKjUw.jpg","attaques":[{"nom":"Lame","emoji":"⚔️","degats":65,"desc": "Précision"},{"nom":"Ackerman","emoji":"💢","degats":80,"desc": "Pouvoir clan"},{"nom":"Protection","emoji":"❤️","degats":70,"desc": "Protège Eren"}],"faiblesse":"💥","resistance":"❤️"},
    # ── DEMON SLAYER (nouveaux) ──────────────────────────────
    "tanjiro":   {"nom":"Tanjiro Kamado",  "serie":"Demon Slayer",    "rarete":"Légendaire",     "emoji":"🔥", "pv":205,"attaque":88,"defense":75,"image":"https://i.imgur.com/RmLMZaP.jpg","attaques":[{"nom":"Soleil Hinokami","emoji":"☀️","degats":60,"desc": "Respiration solaire"},{"nom":"Eau","emoji":"💧","degats":40,"desc": "Respiration eau"},{"nom":"Danse Flamme","emoji":"🔥","degats":55,"desc": "Danse ignée"}],"faiblesse":"🌊","resistance":"🔥"},
    "zenitsu":   {"nom":"Zenitsu Agatsuma","serie":"Demon Slayer",    "rarete":"Épique",       "emoji":"⚡", "pv":185,"attaque":86,"defense":65,"image":"https://i.imgur.com/xBnRNSv.jpg","attaques":[{"nom":"Tonnerre","emoji":"⚡","degats":60,"desc": "Respiration foudre"},{"nom":"Godspeed","emoji":"💨","degats":75,"desc": "Vitesse éclair"},{"nom":"Thunderclap","emoji":"🌩️","degats":85,"desc": "Coup unique"}],"faiblesse":"🌊","resistance":"⚡"},
    "nezuko":    {"nom":"Nezuko Kamado",   "serie":"Demon Slayer",    "rarete":"Épique",     "emoji":"🩷", "pv":200,"attaque":85,"defense":78,"image":"https://i.imgur.com/n9kTXuX.jpg","attaques":[{"nom":"Sang Explosion","emoji":"🩸","degats":65,"desc": "Flammes roses"},{"nom":"Démon","emoji":"👹","degats":55,"desc": "Transformation"},{"nom":"Soleil","emoji":"☀️","degats":75,"desc": "Résiste au soleil"}],"faiblesse":"🌊","resistance":"🩷"},
    "tengen":    {"nom":"Tengen Uzui",     "serie":"Demon Slayer",    "rarete":"Légendaire",     "emoji":"💥", "pv":210,"attaque":93,"defense":77,"image":"https://i.imgur.com/Mv099qN.jpg","attaques":[{"nom":"Son","emoji":"🎵","degats":60,"desc": "Respiration son"},{"nom":"Explosion","emoji":"💥","degats":75,"desc": "Détonation"},{"nom":"Flamboyant","emoji":"✨","degats":80,"desc": "Spectaculaire"}],"faiblesse":"🌊","resistance":"💥"},
    "muichiro":  {"nom":"Muichiro Tokito", "serie":"Demon Slayer",    "rarete":"Légendaire",     "emoji":"🌫️", "pv":195,"attaque":91,"defense":76,"image":"https://i.imgur.com/C9Q0GcG.jpg","attaques":[{"nom":"Brume","emoji":"🌫️","degats":60,"desc": "Respiration brume"},{"nom":"Brume 7","emoji":"🌊","degats":70,"desc": "7ème forme"},{"nom":"Démon","emoji":"💀","degats":80,"desc": "Marque du démon"}],"faiblesse":"🔥","resistance":"🌫️"},
    "giyu":      {"nom":"Giyu Tomioka",    "serie":"Demon Slayer",    "rarete":"Légendaire", "emoji":"💧", "pv":215,"attaque":97,"defense":83,"image":"https://i.imgur.com/oWIcMrV.jpg","attaques":[{"nom":"Eau 11","emoji":"💧","degats":70,"desc": "Onzième forme"},{"nom":"Calme","emoji":"🌊","degats":60,"desc": "Eau tranquille"},{"nom":"Pilier","emoji":"⚔️","degats":85,"desc": "Force de pilier"}],"faiblesse":"⚡","resistance":"💧"},
    "rengoku":   {"nom":"Kyojuro Rengoku", "serie":"Demon Slayer",    "rarete":"Légendaire", "emoji":"🔥", "pv":218,"attaque":99,"defense":80,"image":"https://i.imgur.com/utlCuQn.jpg","attaques":[{"nom":"Flamme 9","emoji":"🔥","degats":75,"desc": "Neuvième forme"},{"nom":"Pillier Feu","emoji":"🔥","degats":85,"desc": "Force du pilier feu"},{"nom":"Ardeur","emoji":"💪","degats":70,"desc": "Cœur enflammé"}],"faiblesse":"💧","resistance":"🔥"},
    "sanemi":    {"nom":"Sanemi Shinazugawa","serie":"Demon Slayer",  "rarete":"Légendaire", "emoji":"🌬️", "pv":212,"attaque":98,"defense":79,"image":"https://i.imgur.com/fHuqIaF.jpg","attaques":[{"nom":"Vent","emoji":"🌬️","degats":70,"desc": "Respiration vent"},{"nom":"Cyclone","emoji":"🌪️","degats":80,"desc": "Rafale"},{"nom":"Sang Rare","emoji":"🩸","degats":85,"desc": "Sang qui attire"}],"faiblesse":"🔥","resistance":"🌬️"},
    "akaza":     {"nom":"Akaza",           "serie":"Demon Slayer",    "rarete":"Légendaire",     "emoji":"🩸", "pv":220,"attaque":102,"defense":85,"image":"https://i.imgur.com/s3SbBSM.jpg","attaques":[{"nom":"Destruction","emoji":"💥","degats":75,"desc": "Style de combat"},{"nom":"Régén","emoji":"💚","degats":50,"desc": "Se régénère"},{"nom":"Lune 3","emoji":"🌙","degats":90,"desc": "Lune supérieure 3"}],"faiblesse":"☀️","resistance":"🩸"},
    # ── JJK (nouveaux) ──────────────────────────────────────
    "gojo":      {"nom":"Satoru Gojo",     "serie":"Jujutsu Kaisen",  "rarete":"Mythique",   "emoji":"♾️", "pv":250,"attaque":110,"defense":100,"image":"https://i.imgur.com/7n8Gmn3.jpg","attaques":[{"nom":"Infini","emoji":"♾️","degats":70,"desc": "Barrière infinie"},{"nom":"Hollow Purple","emoji":"💜","degats":90,"desc": "Destructeur"},{"nom":"Domaine","emoji":"🌐","degats":100,"desc": "Sure Hit"}],"faiblesse":"💀","resistance":"♾️"},
    "sukuna":    {"nom":"Ryomen Sukuna",   "serie":"Jujutsu Kaisen",  "rarete":"Mythique",   "emoji":"☠️", "pv":255,"attaque":118,"defense":95,"image":"https://i.imgur.com/UbB1tmt.jpg","attaques":[{"nom":"Dismantle","emoji":"✂️","degats":90,"desc": "Coupe tout"},{"nom":"Malédiction","emoji":"☠️","degats":100,"desc": "Énergie maudite"},{"nom":"Domaine","emoji":"🌑","degats":115,"desc": "Boucherie"}],"faiblesse":"♾️","resistance":"☠️"},
    "yuji":      {"nom":"Yuji Itadori",    "serie":"Jujutsu Kaisen",  "rarete":"Épique",     "emoji":"👊", "pv":220,"attaque":92,"defense":80,"image":"https://i.imgur.com/wxIT2y4.jpg","attaques":[{"nom":"Divergent Fist","emoji":"👊","degats":55,"desc": "Double impact"},{"nom":"Black Flash","emoji":"⚫","degats":70,"desc": "Distorsion maudite"},{"nom":"Sukuna","emoji":"☠️","degats":85,"desc": "Roi des malédictions"}],"faiblesse":"♾️","resistance":"👊"},
    "megumi":    {"nom":"Megumi Fushiguro","serie":"Jujutsu Kaisen",  "rarete":"Épique",     "emoji":"🐕", "pv":200,"attaque":88,"defense":82,"image":"https://i.imgur.com/VRQStsA.jpg","attaques":[{"nom":"Shikigami","emoji":"🐕","degats":60,"desc": "Invoque des bêtes"},{"nom":"Mahoraga","emoji":"☯️","degats":90,"desc": "Shikigami ultime"},{"nom":"Dix Ombres","emoji":"🌑","degats":75,"desc": "Technique des ombres"}],"faiblesse":"🔥","resistance":"🌑"},
    # ── ONE PIECE (nouveaux) ─────────────────────────────────
    "luffy":     {"nom":"Monkey D. Luffy", "serie":"One Piece",       "rarete":"Légendaire",   "emoji":"👒", "pv":240,"attaque":105,"defense":85,"image":"https://i.imgur.com/WaXKIPM.jpg","attaques":[{"nom":"Gear 5","emoji":"☁️","degats":80,"desc": "Nika libéré"},{"nom":"Gomu Gomu","emoji":"👊","degats":50,"desc": "Poing élastique"},{"nom":"Red Roc","emoji":"🔥","degats":70,"desc": "Frappe embrasée"}],"faiblesse":"⚡","resistance":"👊"},
    "zoro":      {"nom":"Roronoa Zoro",    "serie":"One Piece",       "rarete":"Légendaire", "emoji":"⚔️", "pv":215,"attaque":98,"defense":82,"image":"https://i.imgur.com/Nr66sRV.jpg","attaques":[{"nom":"Asura","emoji":"👹","degats":75,"desc": "Neuf lames"},{"nom":"Hiryu Kaen","emoji":"🔥","degats":60,"desc": "Dragon de feu"},{"nom":"Enma","emoji":"⚔️","degats":85,"desc": "Lame du roi"}],"faiblesse":"💧","resistance":"⚔️"},
    "mihawk":    {"nom":"Dracule Mihawk",  "serie":"One Piece",       "rarete":"Légendaire",   "emoji":"🗡️", "pv":225,"attaque":110,"defense":88,"image":"https://i.imgur.com/pB4lYTn.jpg","attaques":[{"nom":"Slash","emoji":"🗡️","degats":80,"desc": "Coupe l'air"},{"nom":"Yoru","emoji":"🌑","degats":95,"desc": "Épée noire"},{"nom":"Croix","emoji":"✝️","degats":100,"desc": "Croix du jugement"}],"faiblesse":"💥","resistance":"🗡️"},
    "kaido":     {"nom":"Kaido",           "serie":"One Piece",       "rarete":"Mythique",   "emoji":"🐲", "pv":260,"attaque":116,"defense":100,"image":"https://i.imgur.com/Q76UJEX.jpg","attaques":[{"nom":"Thunder Bagua","emoji":"🌩️","degats":100,"desc": "Frappe de masse"},{"nom":"Dragon","emoji":"🐲","degats":110,"desc": "Transformation dragon"},{"nom":"Haoshoku","emoji":"👑","degats":115,"desc": "Haki des rois"}],"faiblesse":"⚡","resistance":"🐲"},
    "shanks":    {"nom":"Shanks",          "serie":"One Piece",       "rarete":"Mythique",   "emoji":"🍶", "pv":245,"attaque":114,"defense":95,"image":"https://i.imgur.com/BkCK51H.jpg","attaques":[{"nom":"Haki","emoji":"👑","degats":90,"desc": "Haki des rois"},{"nom":"Griffe","emoji":"⚔️","degats":80,"desc": "Cicatrice de Shanks"},{"nom":"Ittoryu","emoji":"🗡️","degats":100,"desc": "Style une lame"}],"faiblesse":"💀","resistance":"🍶"},
    # ── DRAGON BALL (nouveaux) ───────────────────────────────
    "goku":      {"nom":"Son Goku",        "serie":"Dragon Ball",     "rarete":"Mythique",   "emoji":"🟡", "pv":250,"attaque":110,"defense":90,"image":"https://i.imgur.com/YbSpxzS.jpg","attaques":[{"nom":"Kamehameha","emoji":"🌊","degats":75,"desc": "Vague d'énergie"},{"nom":"Ultra Instinct","emoji":"🟡","degats":95,"desc": "Instinct supérieur"},{"nom":"Spirit Bomb","emoji":"☀️","degats":110,"desc": "Bombe du Génie"}],"faiblesse":"💀","resistance":"🟡"},
    "vegeta":    {"nom":"Vegeta",          "serie":"Dragon Ball",     "rarete":"Mythique", "emoji":"👑", "pv":230,"attaque":100,"defense":88,"image":"https://i.imgur.com/ld1LPss.jpg","attaques":[{"nom":"Big Bang","emoji":"💥","degats":70,"desc": "Explosion ultime"},{"nom":"Galick Gun","emoji":"💜","degats":60,"desc": "Rayon violet"},{"nom":"Ultra Ego","emoji":"👑","degats":90,"desc": "Ego transcendé"}],"faiblesse":"🟡","resistance":"👑"},
    "frieza":    {"nom":"Frieza",          "serie":"Dragon Ball",     "rarete":"Mythique",   "emoji":"❄️", "pv":240,"attaque":108,"defense":92,"image":"https://i.imgur.com/qIelqUS.jpg","attaques":[{"nom":"Death Beam","emoji":"❄️","degats":80,"desc": "Rayon mortel"},{"nom":"Black Frieza","emoji":"🖤","degats":110,"desc": "Forme ultime"},{"nom":"Supernova","emoji":"💫","degats":95,"desc": "Étoile de mort"}],"faiblesse":"🟡","resistance":"❄️"},
    "beerus":    {"nom":"Beerus",          "serie":"Dragon Ball Super","rarete":"Mythique",  "emoji":"🌌", "pv":255,"attaque":120,"defense":100,"image":"https://i.imgur.com/NDn5qKx.jpg","attaques":[{"nom":"Hakai","emoji":"💥","degats":100,"desc": "Destruction pure"},{"nom":"Sphere","emoji":"🌌","degats":110,"desc": "Sphère de destruction"},{"nom":"Dieu","emoji":"✨","degats":120,"desc": "Dieu de la destruction"}],"faiblesse":"💀","resistance":"🌌"},
    # ── MHA (nouveaux) ──────────────────────────────────────
    "allmight":  {"nom":"All Might",       "serie":"My Hero Academia","rarete":"Mythique",   "emoji":"💪", "pv":240,"attaque":112,"defense":88,"image":"https://i.imgur.com/5YVOpkT.jpg","attaques":[{"nom":"Detroit Smash","emoji":"💪","degats":90,"desc": "Frappe dévastatrice"},{"nom":"Carolina Smash","emoji":"💥","degats":80,"desc": "Croisée"},{"nom":"United States Smash","emoji":"🌍","degats":110,"desc": "Ultime"}],"faiblesse":"💀","resistance":"💪"},
    "deku":      {"nom":"Izuku Midoriya",  "serie":"My Hero Academia","rarete":"Légendaire",     "emoji":"💚", "pv":210,"attaque":90,"defense":75,"image":"https://i.imgur.com/aKjpPQs.jpg","attaques":[{"nom":"Detroit Smash","emoji":"💚","degats":60,"desc": "100% One for All"},{"nom":"Shoot Style","emoji":"🦵","degats":50,"desc": "Frappe de pied"},{"nom":"Float","emoji":"🌊","degats":70,"desc": "Full Cowl"}],"faiblesse":"🔥","resistance":"💚"},
    "bakugo":    {"nom":"Katsuki Bakugo",  "serie":"My Hero Academia","rarete":"Légendaire", "emoji":"💥", "pv":215,"attaque":100,"defense":76,"image":"https://i.imgur.com/jlLDh3h.jpg","attaques":[{"nom":"Explosion","emoji":"💥","degats":70,"desc": "Nitroglycérine"},{"nom":"Howitzer","emoji":"🌀","degats":85,"desc": "Tornado explosive"},{"nom":"AP Shot","emoji":"🔫","degats":75,"desc": "Tir ciblé"}],"faiblesse":"💧","resistance":"💥"},
    "shigaraki": {"nom":"Shigaraki Tomura","serie":"My Hero Academia","rarete":"Légendaire",   "emoji":"🖐️", "pv":235,"attaque":106,"defense":82,"image":"https://i.imgur.com/464ERG7.jpg","attaques":[{"nom":"Désintégration","emoji":"🖐️","degats":90,"desc": "Touche = mort"},{"nom":"AFO","emoji":"☠️","degats":105,"desc": "Pouvoir volé"},{"nom":"Decay","emoji":"💀","degats":95,"desc": "Tout se désagrège"}],"faiblesse":"💧","resistance":"🖐️"},
    # ── CODE GEASS ───────────────────────────────────────────
    "lelouch":   {"nom":"Lelouch vi Britannia","serie":"Code Geass",  "rarete":"Mythique", "emoji":"♟️", "pv":180,"attaque":85,"defense":82,"image":"https://i.imgur.com/T0AqdVz.jpg","attaques":[{"nom":"Geass","emoji":"👁️","degats":75,"desc": "Ordre absolu"},{"nom":"Tactique","emoji":"♟️","degats":60,"desc": "Génie militaire"},{"nom":"Zéro","emoji":"🃏","degats":80,"desc": "Masque de Zéro"}],"faiblesse":"💀","resistance":"♟️"},
    "suzaku":    {"nom":"Suzaku Kururugi",  "serie":"Code Geass",    "rarete":"Épique",     "emoji":"🌸", "pv":205,"attaque":93,"defense":80,"image":"https://i.imgur.com/b5cVGjx.jpg","attaques":[{"nom":"Lancelot","emoji":"🤖","degats":65,"desc": "Knightmare Frame"},{"nom":"Hadron","emoji":"💛","degats":75,"desc": "Canon hadron"},{"nom":"Geas","emoji":"🌸","degats":80,"desc": "Vivre pour ordonner"}],"faiblesse":"♟️","resistance":"🌸"},
    # ── SOLO LEVELING ────────────────────────────────────────
    "jinwoo":    {"nom":"Sung Jin-Woo",    "serie":"Solo Leveling",   "rarete":"Mythique",   "emoji":"🗡️", "pv":248,"attaque":115,"defense":95,"image":"https://i.imgur.com/cytYnaz.jpg","attaques":[{"nom":"Ombre","emoji":"🌑","degats":90,"desc": "Armée des ombres"},{"nom":"Dague","emoji":"🗡️","degats":80,"desc": "Lame d'ombre"},{"nom":"Monarque","emoji":"👑","degats":110,"desc": "Monarque des ombres"}],"faiblesse":"✨","resistance":"🗡️"},
    # ── BLACK CLOVER ─────────────────────────────────────────
    "asta":      {"nom":"Asta",            "serie":"Black Clover",    "rarete":"Épique", "emoji":"⚫", "pv":220,"attaque":97,"defense":80,"image":"https://i.imgur.com/zxT2yys.jpg","attaques":[{"nom":"Anti-Magie","emoji":"⚫","degats":75,"desc": "Annule la magie"},{"nom":"Black Divider","emoji":"🗡️","degats":85,"desc": "Coupe tout"},{"nom":"Démon","emoji":"👹","degats":95,"desc": "Fusion démoniaque"}],"faiblesse":"🔥","resistance":"⚫"},
    "yuno":      {"nom":"Yuno",            "serie":"Black Clover",    "rarete":"Épique",     "emoji":"🍀", "pv":210,"attaque":94,"defense":80,"image":"https://i.imgur.com/R9lnjWa.jpg","attaques":[{"nom":"Vent","emoji":"🍀","degats":65,"desc": "Magie du vent"},{"nom":"Spirit Dive","emoji":"🌪️","degats":80,"desc": "Fusion avec Sylph"},{"nom":"Étoile","emoji":"⭐","degats":85,"desc": "Magie d'étoile"}],"faiblesse":"🔥","resistance":"🍀"},
    "yami":      {"nom":"Yami Sukehiro",   "serie":"Black Clover",    "rarete":"Épique", "emoji":"🌑", "pv":218,"attaque":102,"defense":83,"image":"https://i.imgur.com/H5UTEEg.jpg","attaques":[{"nom":"Dark Magic","emoji":"🌑","degats":75,"desc": "Magie des ténèbres"},{"nom":"Kata","emoji":"⚔️","degats":65,"desc": "Style sabre"},{"nom":"Dimension Slash","emoji":"💀","degats":90,"desc": "Coupe la dimension"}],"faiblesse":"✨","resistance":"🌑"},
    # ── HXH (nouveaux) ──────────────────────────────────────
    "gon":       {"nom":"Gon Freecss",     "serie":"HunterxHunter",   "rarete":"Légendaire",     "emoji":"🌿", "pv":210,"attaque":85,"defense":70,"image":"https://i.imgur.com/JEAkcm9.jpg","attaques":[{"nom":"Jajanken","emoji":"✊","degats":50,"desc": "Papier/Pierre/Ciseaux"},{"nom":"Adult Gon","emoji":"💥","degats":100,"desc": "Forme adulte"},{"nom":"Jan Ken","emoji":"💪","degats":65,"desc": "Combo"}],"faiblesse":"⚡","resistance":"🌿"},
    "killua":    {"nom":"Killua Zoldyck",  "serie":"HunterxHunter",   "rarete":"Légendaire", "emoji":"⚡", "pv":205,"attaque":92,"defense":78,"image":"https://i.imgur.com/T0BJceE.jpg","attaques":[{"nom":"Godspeed","emoji":"⚡","degats":55,"desc": "Vitesse ultime"},{"nom":"Griffes","emoji":"🗡️","degats":40,"desc": "Lacère"},{"nom":"Éclair","emoji":"🌩️","degats":65,"desc": "Décharge"}],"faiblesse":"🌊","resistance":"⚡"},
    "hisoka":    {"nom":"Hisoka Morow",    "serie":"HunterxHunter",   "rarete":"Légendaire", "emoji":"🃏", "pv":215,"attaque":99,"defense":82,"image":"https://i.imgur.com/AdQSiCd.jpg","attaques":[{"nom":"Bungee Gum","emoji":"🎈","degats":65,"desc": "Gomme élastique"},{"nom":"Carte","emoji":"🃏","degats":55,"desc": "Cartes tranchantes"},{"nom":"Transmission","emoji":"⚡","degats":80,"desc": "Élasticité"}],"faiblesse":"💧","resistance":"🃏"},
    # ── FAIRY TAIL (Erza) ────────────────────────────────────
    "erza":      {"nom":"Erza Scarlet",    "serie":"Fairy Tail",      "rarete":"Légendaire", "emoji":"⚔️", "pv":218,"attaque":100,"defense":88,"image":"https://i.imgur.com/VGa6MhQ.jpg","attaques":[{"nom":"Armure","emoji":"🛡️","degats":65,"desc": "Changement d'armure"},{"nom":"Titania","emoji":"👸","degats":80,"desc": "Reine des fées"},{"nom":"Nakagami","emoji":"✨","degats":95,"desc": "Armure mythique"}],"faiblesse":"⚡","resistance":"⚔️"},
    # ── RUROUNI KENSHIN ──────────────────────────────────────
    "kenshin":   {"nom":"Kenshin Himura",  "serie":"Rurouni Kenshin", "rarete":"Légendaire", "emoji":"🌸", "pv":205,"attaque":97,"defense":80,"image":"https://i.imgur.com/6pVtY0C.jpg","attaques":[{"nom":"Battoujutsu","emoji":"🌸","degats":70,"desc": "Dégainage éclair"},{"nom":"Amakakeru","emoji":"⚡","degats":85,"desc": "Vol d'oiseau céleste"},{"nom":"Hiten Mitsurugi","emoji":"💨","degats":90,"desc": "Style céleste"}],"faiblesse":"💀","resistance":"🌸"},
    # ── TENSEI SHITARA SLIME ─────────────────────────────────
    "rimuru":    {"nom":"Rimuru Tempest",  "serie":"That Time I Got Reincarnated as a Slime","rarete":"Mythique","emoji":"💧","pv":245,"attaque":108,"defense":96,"image":"https://i.imgur.com/2kqDGwW.jpg","attaques":[{"nom":"Prédateur","emoji":"💧","degats":85,"desc": "Avale et copie"},{"nom":"Tempête","emoji":"🌪️","degats":95,"desc": "Magie ultime"},{"nom":"Dieu","emoji":"✨","degats":110,"desc": "Forme divine"}],"faiblesse":"💀","resistance":"💧"},
    # ── SAO (Kirito) ─────────────────────────────────────────
    "kirito":    {"nom":"Kirito",          "serie":"SAO",             "rarete":"Légendaire", "emoji":"⚔️", "pv":210,"attaque":95,"defense":80,"image":"https://i.imgur.com/I2OwE8u.jpg","attaques":[{"nom":"Double Lame","emoji":"⚔️","degats":65,"desc": "Deux épées"},{"nom":"Star Burst","emoji":"⭐","degats":80,"desc": "Frappe stellaire"},{"nom":"Underworld","emoji":"🌑","degats":90,"desc": "Chevalier intégral"}],"faiblesse":"💧","resistance":"⚔️"},
    # ── TOKYO GHOUL ──────────────────────────────────────────
    "kaneki":    {"nom":"Ken Kaneki",      "serie":"Tokyo Ghoul",     "rarete":"Légendaire",   "emoji":"🕷️", "pv":235,"attaque":104,"defense":88,"image":"https://i.imgur.com/PSZyDlw.jpg","attaques":[{"nom":"Kagune","emoji":"🕷️","degats":75,"desc": "Lames de kagune"},{"nom":"Roi Noir","emoji":"🖤","degats":90,"desc": "Transformation"},{"nom":"Dragon","emoji":"🐉","degats":105,"desc": "Forme dragon"}],"faiblesse":"☠️","resistance":"🕷️"},
    "rize":      {"nom":"Rize Kamishiro",  "serie":"Tokyo Ghoul",     "rarete":"Épique",     "emoji":"🌸", "pv":205,"attaque":96,"defense":80,"image":"https://i.imgur.com/qAhrKOO.jpg","attaques":[{"nom":"Kagune","emoji":"🌸","degats":70,"desc": "Multiples tentacules"},{"nom":"Ghoul","emoji":"👹","degats":80,"desc": "Puissance gourmet"},{"nom":"Prédateur","emoji":"🩸","degats":85,"desc": "Appétit sans fin"}],"faiblesse":"☠️","resistance":"🌸"},
    "arima":     {"nom":"Kishou Arima",    "serie":"Tokyo Ghoul",     "rarete":"Légendaire",   "emoji":"⚔️", "pv":228,"attaque":111,"defense":93,"image":"https://i.imgur.com/GEsZ3uD.jpg","attaques":[{"nom":"IXA","emoji":"⚔️","degats":85,"desc": "Quinque lame"},{"nom":"Yukimura","emoji":"🌸","degats":75,"desc": "Mille coups"},{"nom":"Owl","emoji":"🦉","degats":100,"desc": "Arima le Faucheur"}],"faiblesse":"💔","resistance":"⚔️"},
    # ── MAGIC EMPEROR (manhwa) ───────────────────────────────
    "zhuofan":   {"nom":"Zhuo Fan",        "serie":"Magic Emperor",   "rarete":"Mythique",   "emoji":"🌑", "pv":245,"attaque":112,"defense":90,"image":"https://i.imgur.com/gqEyuY0.jpg","attaques":[{"nom":"Démon","emoji":"🌑","degats":90,"desc": "Arts démoniaques"},{"nom":"Magie Noire","emoji":"🖤","degats":100,"desc": "Puissance obscure"},{"nom":"Empereur","emoji":"👑","degats":110,"desc": "Pouvoir impérial"}],"faiblesse":"✨","resistance":"🌑"},
    "yelin":     {"nom":"Ye Lin",          "serie":"Magic Emperor",   "rarete":"Épique", "emoji":"⚡", "pv":215,"attaque":98,"defense":83,"image":"https://i.imgur.com/Ml8v5UX.jpg","attaques":[{"nom":"Foudre","emoji":"⚡","degats":70,"desc": "Magie éclair"},{"nom":"Tempête","emoji":"🌩️","degats":80,"desc": "Orage magique"},{"nom":"Dragon","emoji":"🐉","degats":88,"desc": "Dragon de foudre"}],"faiblesse":"🌊","resistance":"⚡"},

    # ── NARUTO (persos secondaires) ─────────────────────────
    "rocklee":   {"nom":"Rock Lee",        "serie":"Naruto",          "rarete":"Épique",     "emoji":"🥊", "pv":195,"attaque":90,"defense":72,"image":"https://i.imgur.com/wzxlb6H.jpg","attaques":[{"nom":"Lotus Primaire","emoji":"🥊","degats":65,"desc": "Vitesse foudroyante"},{"nom":"Lotus Éblouissant","emoji":"💥","degats":80,"desc": "Poids retirés"},{"nom":"Coup de Pied","emoji":"🦵","degats":55,"desc": "Précision absolue"}],"faiblesse":"⚡","resistance":"🥊"},
    "konohamaru":{"nom":"Konohamaru Sarutobi","serie":"Naruto",       "rarete":"Rare",       "emoji":"🎭", "pv":175,"attaque":72,"defense":65,"image":"https://i.imgur.com/3VJ5ob5.jpg","attaques":[{"nom":"Rasengan","emoji":"🌀","degats":45,"desc": "Imite son sensei"},{"nom":"Sexy no Jutsu","emoji":"😏","degats":25,"desc": "Déstabilise"},{"nom":"Shuriken","emoji":"🌟","degats":40,"desc": "Précision"}],"faiblesse":"🔥","resistance":"🎭"},
    "kiba":       {"nom":"Kiba Inuzuka",   "serie":"Naruto",          "rarete":"Rare",       "emoji":"🐕", "pv":178,"attaque":74,"defense":66,"image":"https://i.imgur.com/ZBBmXG0.jpg","attaques":[{"nom":"Gatsuga","emoji":"🐕","degats":45,"desc": "Fang over Fang"},{"nom":"Akamaru","emoji":"🦴","degats":35,"desc": "Duo avec Akamaru"},{"nom":"Fang Fang","emoji":"💨","degats":50,"desc": "Tornade"}],"faiblesse":"⚡","resistance":"🐕"},
    "tenten":     {"nom":"Tenten",         "serie":"Naruto",          "rarete":"Commun",     "emoji":"📦", "pv":165,"attaque":68,"defense":62,"image":"https://i.imgur.com/f0TTVWk.jpg","attaques":[{"nom":"Armes","emoji":"📦","degats":38,"desc": "Lance des armes"},{"nom":"Kama","emoji":"⚔️","degats":30,"desc": "Faucille"},{"nom":"Bansho","emoji":"💫","degats":42,"desc": "Toutes les armes"}],"faiblesse":"🔥","resistance":"📦"},
    "sai":        {"nom":"Sai",            "serie":"Naruto",          "rarete":"Rare",       "emoji":"🖌️", "pv":172,"attaque":73,"defense":68,"image":"https://i.imgur.com/f1b1Kkd.jpg","attaques":[{"nom":"Dessin","emoji":"🖌️","degats":42,"desc": "Invoque des créatures"},{"nom":"Tigre","emoji":"🐯","degats":50,"desc": "Tigre d'encre"},{"nom":"Corde","emoji":"🪢","degats":38,"desc": "Immobilise"}],"faiblesse":"🔥","resistance":"🖌️"},
    # ── MHA (persos secondaires) ─────────────────────────────
    "presentmic":{"nom":"Present Mic",     "serie":"My Hero Academia","rarete":"Commun",     "emoji":"🎤", "pv":162,"attaque":65,"defense":60,"image":"https://i.imgur.com/5RdHtX8.jpg","attaques":[{"nom":"Cri","emoji":"🎤","degats":35,"desc": "Son dévastateur"},{"nom":"Amplification","emoji":"🔊","degats":45,"desc": "Volume max"},{"nom":"Son","emoji":"🌊","degats":38,"desc": "Onde sonique"}],"faiblesse":"🌀","resistance":"🎤"},
    # ── BLACK CLOVER (persos) ────────────────────────────────
    "luck":       {"nom":"Luck Voltia",    "serie":"Black Clover",    "rarete":"Épique",     "emoji":"⚡", "pv":190,"attaque":88,"defense":70,"image":"https://i.imgur.com/iubOOO7.jpg","attaques":[{"nom":"Foudre","emoji":"⚡","degats":60,"desc": "Vitesse électrique"},{"nom":"Éclair","emoji":"🌩️","degats":70,"desc": "Frappe multiple"},{"nom":"Rune","emoji":"✨","degats":75,"desc": "Runes de foudre"}],"faiblesse":"🌊","resistance":"⚡"},
    # ── DBZ (persos secondaires) ─────────────────────────────
    "yamcha":     {"nom":"Yamcha",         "serie":"Dragon Ball Z",   "rarete":"Commun",     "emoji":"🐺", "pv":160,"attaque":62,"defense":58,"image":"https://i.imgur.com/PAKAiXr.jpg","attaques":[{"nom":"Wolf Fang","emoji":"🐺","degats":32,"desc": "Poing du loup"},{"nom":"Kamehameha","emoji":"💫","degats":28,"desc": "Version faible"},{"nom":"Blitz","emoji":"⚡","degats":35,"desc": "Frappe rapide"}],"faiblesse":"🟡","resistance":"🐺"},

    # ── MYTHIQUE ─────────────────────────────────────────────
    "saitama":    {"nom":"Saitama",           "serie":"One Punch Man",    "rarete":"Mythique",   "emoji":"👊", "pv":999,"attaque":999,"defense":999,"image":"https://i.imgur.com/iMeJqxN.jpg","attaques":[{"nom":"Un seul coup","emoji":"👊","degats":999,"desc":"Instakill absolu"},{"nom":"Serious Punch","emoji":"💥","degats":999,"desc":"Détruit tout"},{"nom":"Consecutive Punches","emoji":"🌪️","degats":500,"desc":"Rafale infinie"}],"faiblesse":"💔","resistance":"👊"},
    "whis":       {"nom":"Whis",              "serie":"Dragon Ball Super", "rarete":"Mythique",   "emoji":"🪄", "pv":999,"attaque":998,"defense":998,"image":"https://i.imgur.com/SCSWxDk.jpg","attaques":[{"nom":"Temps inversé","emoji":"⏪","degats":200,"desc":"Annule toute action"},{"nom":"Bâton","emoji":"🪄","degats":500,"desc":"Frappe divine"},{"nom":"Réveil","emoji":"✨","degats":300,"desc":"Révèle la puissance"}],"faiblesse":"💀","resistance":"🪄"},
    "anos":       {"nom":"Anos Voldigoad",     "serie":"Misfit of Demon King","rarete":"Mythique", "emoji":"🩸","pv":999,"attaque":997,"defense":997,"image":"https://i.imgur.com/Sky6bPd.jpg","attaques":[{"nom":"Vendettas","emoji":"🩸","degats":900,"desc":"Anéantissement absolu"},{"nom":"Jeux Mort","emoji":"💀","degats":700,"desc":"Tue 1000 fois"},{"nom":"Démesure","emoji":"👑","degats":800,"desc":"Pouvoir infini"}],"faiblesse":"💔","resistance":"🩸"},
    "muzan":      {"nom":"Muzan Kibutsuji",    "serie":"Demon Slayer",    "rarete":"Mythique",   "emoji":"🌙", "pv":950,"attaque":120,"defense":110,"image":"https://i.imgur.com/amD1hXZ.jpg","attaques":[{"nom":"Sang Noir","emoji":"🌙","degats":100,"desc":"Sang démoniaque"},{"nom":"Régénération","emoji":"💚","degats":50,"desc":"Se régénère"},{"nom":"Roi Démons","emoji":"🌑","degats":120,"desc":"Puissance absolue"}],"faiblesse":"☀️","resistance":"🌙"},
    "garou":      {"nom":"Garou",              "serie":"One Punch Man",   "rarete":"Mythique",   "emoji":"🐺", "pv":280,"attaque":118,"defense":95,"image":"https://i.imgur.com/TQXoa3i.jpg","attaques":[{"nom":"Fist of Flowing Water","emoji":"🌊","degats":90,"desc":"Style martial"},{"nom":"Monstre","emoji":"🐺","degats":110,"desc":"Transformation"},{"nom":"God Garou","emoji":"💥","degats":130,"desc":"Forme divine"}],"faiblesse":"👊","resistance":"🐺"},
    "hashirama":  {"nom":"Hashirama Senju",    "serie":"Naruto",          "rarete":"Mythique",   "emoji":"🌿", "pv":300,"attaque":115,"defense":105,"image":"https://i.imgur.com/l3i058Z.jpg","attaques":[{"nom":"Mokuton","emoji":"🌿","degats":90,"desc":"Magie du bois"},{"nom":"Sage Mode","emoji":"🍃","degats":105,"desc":"Mode sage"},{"nom":"Bouddha Bois","emoji":"🗿","degats":120,"desc":"Colosse de bois"}],"faiblesse":"🔥","resistance":"🌿"},
    "pain":       {"nom":"Nagato/Pain",        "serie":"Naruto",          "rarete":"Mythique",   "emoji":"🔱", "pv":260,"attaque":112,"defense":95,"image":"https://i.imgur.com/uA77dW6.jpg","attaques":[{"nom":"Shinra Tensei","emoji":"🔱","degats":100,"desc":"Répulsion divine"},{"nom":"Chibaku Tensei","emoji":"🌑","degats":115,"desc":"Sphère de gravité"},{"nom":"Six Voies","emoji":"⚡","degats":90,"desc":"Six corps"}],"faiblesse":"💧","resistance":"🔱"},
    "toji":       {"nom":"Toji Fushiguro",     "serie":"Jujutsu Kaisen",  "rarete":"Mythique",   "emoji":"🗡️", "pv":250,"attaque":114,"defense":88,"image":"https://i.imgur.com/NzgqTBl.jpg","attaques":[{"nom":"Inventaire","emoji":"🗡️","degats":95,"desc":"Armes spectrales"},{"nom":"Zéro Energie","emoji":"⬛","degats":85,"desc":"Aucune énergie maudite"},{"nom":"Tueur","emoji":"💀","degats":110,"desc":"Assassin parfait"}],"faiblesse":"♾️","resistance":"🗡️"},
    "blackbeard": {"nom":"Barbe Noire",        "serie":"One Piece",       "rarete":"Mythique",   "emoji":"⚫", "pv":300,"attaque":116,"defense":98,"image":"https://i.imgur.com/DA6CfBP.jpg","attaques":[{"nom":"Tremblement","emoji":"🌍","degats":105,"desc":"Deux fruits"},{"nom":"Ténèbres","emoji":"⚫","degats":95,"desc":"Avale tout"},{"nom":"Yami Yami","emoji":"🌑","degats":110,"desc":"Gravité noire"}],"faiblesse":"⚡","resistance":"⚫"},
    "roger":      {"nom":"Gol D. Roger",       "serie":"One Piece",       "rarete":"Mythique",   "emoji":"🏴‍☠️","pv":280,"attaque":115,"defense":95,"image":"https://i.imgur.com/MHNBUvj.jpg","attaques":[{"nom":"Haki Roi","emoji":"👑","degats":105,"desc":"Conquête divine"},{"nom":"Épée","emoji":"⚔️","degats":90,"desc":"Maître épéiste"},{"nom":"Voix Monde","emoji":"🌊","degats":95,"desc":"Entend tout"}],"faiblesse":"💀","resistance":"🏴‍☠️"},
    "whitebeard": {"nom":"Barbe Blanche",      "serie":"One Piece",       "rarete":"Mythique",   "emoji":"🌊", "pv":350,"attaque":113,"defense":100,"image":"https://i.imgur.com/hD6V9QR.jpg","attaques":[{"nom":"Gura Gura","emoji":"🌊","degats":100,"desc":"Tremblement de mer"},{"nom":"Tsunami","emoji":"🌊","degats":110,"desc":"Vague géante"},{"nom":"Bisento","emoji":"🪓","degats":90,"desc":"Lance de guerre}"}],"faiblesse":"🔥","resistance":"🌊"},
    "dio":        {"nom":"Dio Brando",         "serie":"JoJo",            "rarete":"Mythique",   "emoji":"🧛", "pv":260,"attaque":111,"defense":92,"image":"https://i.imgur.com/sZdHO5z.jpg","attaques":[{"nom":"Za Warudo","emoji":"🕐","degats":95,"desc":"Stop time"},{"nom":"Knife","emoji":"🗡️","degats":75,"desc":"Couteaux gelés"},{"nom":"Road Roller","emoji":"🚗","degats":105,"desc":"écrase tout}"}],"faiblesse":"☀️","resistance":"🧛"},
    "giorno":     {"nom":"Giorno Giovanna",    "serie":"JoJo",            "rarete":"Mythique",   "emoji":"🌟", "pv":255,"attaque":110,"defense":90,"image":"https://i.imgur.com/sndc2al.jpg","attaques":[{"nom":"Gold Experience","emoji":"🌟","degats":85,"desc":"Donne la vie"},{"nom":"GER","emoji":"♾️","degats":120,"desc":"Retour à zéro"},{"nom":"Requin","emoji":"🦈","degats":90,"desc":"Transformation"}],"faiblesse":"💀","resistance":"🌟"},
    "makima":     {"nom":"Makima",             "serie":"Chainsaw Man",    "rarete":"Mythique",   "emoji":"👁️", "pv":260,"attaque":112,"defense":96,"image":"https://i.imgur.com/OxiYDGt.jpg","attaques":[{"nom":"Contrôle","emoji":"👁️","degats":95,"desc":"Contrôle tout"},{"nom":"Force","emoji":"💥","degats":100,"desc":"Accumule les morts"},{"nom":"Déesse","emoji":"🌸","degats":110,"desc":"Concept de contrôle}"}],"faiblesse":"💔","resistance":"👁️"},
    "netero":     {"nom":"Netero",             "serie":"HunterxHunter",   "rarete":"Mythique",   "emoji":"🙏", "pv":255,"attaque":113,"defense":90,"image":"https://i.imgur.com/hucISaO.jpg","attaques":[{"nom":"100 Type Guanyin","emoji":"🙏","degats":100,"desc":"Bouddha divin"},{"nom":"Poor Man's Rose","emoji":"☢️","degats":200,"desc":"Bombe nucléaire"},{"nom":"Vitesse","emoji":"⚡","degats":85,"desc":"Vitesse ultime}"}],"faiblesse":"♟️","resistance":"🙏"},
    "cid":        {"nom":"Cid Kagenou",        "serie":"The Eminence in Shadow","rarete":"Mythique","emoji":"🌑","pv":270,"attaque":112,"defense":92,"image":"https://i.imgur.com/d0emxwc.jpg","attaques":[{"nom":"I Am Atomic","emoji":"🌑","degats":120,"desc":"Destruction totale"},{"nom":"Shadow","emoji":"👤","degats":95,"desc":"Magie des ombres"},{"nom":"Flashy","emoji":"💥","degats":105,"desc":"Style spectaculaire}"}],"faiblesse":"✨","resistance":"🌑"},
    # ── LÉGENDAIRE ───────────────────────────────────────────
    "ace":        {"nom":"Portgas D. Ace",     "serie":"One Piece",       "rarete":"Légendaire", "emoji":"🔥", "pv":220,"attaque":98,"defense":78,"image":"https://i.imgur.com/MLPIlkk.jpg","attaques":[{"nom":"Mera Mera","emoji":"🔥","degats":70,"desc":"Feu absolu"},{"nom":"Hiken","emoji":"🔥","degats":80,"desc":"Poing de feu"},{"nom":"Entei","emoji":"☀️","degats":90,"desc":"Soleil de feu}"}],"faiblesse":"💧","resistance":"🔥"},
    "law":        {"nom":"Trafalgar Law",      "serie":"One Piece",       "rarete":"Légendaire", "emoji":"⚔️", "pv":210,"attaque":96,"defense":82,"image":"https://i.imgur.com/FIOCksy.jpg","attaques":[{"nom":"Room","emoji":"⚔️","degats":65,"desc":"Espace chirurgical"},{"nom":"Shambles","emoji":"🔄","degats":75,"desc":"Téléporte organes"},{"nom":"Gamma Knife","emoji":"💛","degats":85,"desc":"Détruit l'énergie}"}],"faiblesse":"🔥","resistance":"⚔️"},
    "sanji":      {"nom":"Sanji",              "serie":"One Piece",       "rarete":"Légendaire", "emoji":"🦵", "pv":215,"attaque":97,"defense":80,"image":"https://i.imgur.com/w4Xvi0m.jpg","attaques":[{"nom":"Ifrit Jambe","emoji":"🔥","degats":85,"desc":"Jambe de feu"},{"nom":"Diable Jambe","emoji":"🦵","degats":75,"desc":"Coup enflammé"},{"nom":"Germa","emoji":"⚡","degats":80,"desc":"Exosquelette}"}],"faiblesse":"💧","resistance":"🦵"},
    "robin":      {"nom":"Nico Robin",         "serie":"One Piece",       "rarete":"Légendaire", "emoji":"🌸", "pv":195,"attaque":88,"defense":78,"image":"https://i.imgur.com/HrbMy5H.jpg","attaques":[{"nom":"Cien Fleur","emoji":"🌸","degats":60,"desc":"Cent mains"},{"nom":"Gigante Fleur","emoji":"🌺","degats":80,"desc":"Forme géante"},{"nom":"Mil Fleur","emoji":"💐","degats":70,"desc":"Mille fleurs}"}],"faiblesse":"🔥","resistance":"🌸"},
    "jiraiya":    {"nom":"Jiraiya",            "serie":"Naruto",          "rarete":"Légendaire", "emoji":"🐸", "pv":220,"attaque":97,"defense":82,"image":"https://i.imgur.com/5oueuVT.jpg","attaques":[{"nom":"Rasengan","emoji":"🌀","degats":70,"desc":"Maître du Rasengan"},{"nom":"Crapaud Sage","emoji":"🐸","degats":85,"desc":"Mode sage"},{"nom":"Summoning","emoji":"🌊","degats":80,"desc":"Invocation crapaud}"}],"faiblesse":"⚡","resistance":"🐸"},
    "tsunade":    {"nom":"Tsunade",            "serie":"Naruto",          "rarete":"Légendaire", "emoji":"💚", "pv":230,"attaque":95,"defense":90,"image":"https://i.imgur.com/Q0HAKjM.jpg","attaques":[{"nom":"Frappe","emoji":"💚","degats":80,"desc":"Force surhumaine"},{"nom":"Byakugou","emoji":"💎","degats":90,"desc":"Sceau de force"},{"nom":"Soin","emoji":"✚","degats":50,"desc":"Guérison ultime}"}],"faiblesse":"⚡","resistance":"💚"},
    "todoroki":   {"nom":"Todoroki Shoto",     "serie":"MHA",             "rarete":"Légendaire", "emoji":"🌊", "pv":215,"attaque":96,"defense":83,"image":"https://i.imgur.com/VPawkjS.jpg","attaques":[{"nom":"Glace","emoji":"❄️","degats":70,"desc":"Moitié glace"},{"nom":"Feu","emoji":"🔥","degats":75,"desc":"Moitié feu"},{"nom":"Hellflame","emoji":"🌊","degats":90,"desc":"Feu paternel}"}],"faiblesse":"💧","resistance":"🌊"},
    "mirio":      {"nom":"Mirio Togata",       "serie":"MHA",             "rarete":"Légendaire", "emoji":"☀️", "pv":220,"attaque":96,"defense":82,"image":"https://i.imgur.com/rNEXoaC.jpg","attaques":[{"nom":"Perméation","emoji":"👻","degats":75,"desc":"Traverse tout"},{"nom":"Phantom","emoji":"☀️","degats":80,"desc":"Intangible"},{"nom":"Smash","emoji":"💥","degats":90,"desc":"Impact massif}"}],"faiblesse":"💀","resistance":"☀️"},
    "hawks":      {"nom":"Hawks",              "serie":"MHA",             "rarete":"Légendaire", "emoji":"🦅", "pv":205,"attaque":95,"defense":78,"image":"https://i.imgur.com/VBbla48.jpg","attaques":[{"nom":"Plumes","emoji":"🦅","degats":65,"desc":"Plumes tranchantes"},{"nom":"Fierce Wings","emoji":"🪶","degats":80,"desc":"Ailes puissantes"},{"nom":"Vitesse","emoji":"⚡","degats":75,"desc":"Ultra rapide}"}],"faiblesse":"🔥","resistance":"🦅"},
    "endeavor":   {"nom":"Endeavor",           "serie":"MHA",             "rarete":"Légendaire", "emoji":"🔥", "pv":218,"attaque":98,"defense":80,"image":"https://i.imgur.com/T0vftcD.jpg","attaques":[{"nom":"Prominence Burn","emoji":"🔥","degats":90,"desc":"Flamme suprême"},{"nom":"Hell Spider","emoji":"🕷️","degats":75,"desc":"Griffes de feu"},{"nom":"Flashfire","emoji":"💥","degats":85,"desc":"Poing de feu}"}],"faiblesse":"💧","resistance":"🔥"},
    # ── ÉPIQUE ───────────────────────────────────────────────
    "nami":       {"nom":"Nami",               "serie":"One Piece",       "rarete":"Épique",     "emoji":"🌩️", "pv":185,"attaque":82,"defense":70,"image":"https://i.imgur.com/VhpyfbD.jpg","attaques":[{"nom":"Zeus","emoji":"⚡","degats":65,"desc":"Foudre divine"},{"nom":"Clima-Tact","emoji":"🌩️","degats":55,"desc":"Météo weapon"},{"nom":"Thunderbolt","emoji":"💥","degats":70,"desc":"Tempête}"}],"faiblesse":"🔥","resistance":"💧"},
    "brook":      {"nom":"Brook",              "serie":"One Piece",       "rarete":"Épique",     "emoji":"💀", "pv":180,"attaque":85,"defense":68,"image":"https://i.imgur.com/oLfUYIJ.jpg","attaques":[{"nom":"Soul Solid","emoji":"❄️","degats":65,"desc":"Lame de glace"},{"nom":"Âme","emoji":"💀","degats":60,"desc":"Projection d'âme"},{"nom":"Blizzard","emoji":"🌨️","degats":72,"desc":"Tempête de glace}"}],"faiblesse":"🔥","resistance":"💀"},
    "franky":     {"nom":"Franky",             "serie":"One Piece",       "rarete":"Épique",     "emoji":"🤖", "pv":220,"attaque":88,"defense":85,"image":"https://i.imgur.com/QMYBqi8.jpg","attaques":[{"nom":"Radical Beam","emoji":"💥","degats":70,"desc":"Rayon laser"},{"nom":"Coup de Vent","emoji":"🌀","degats":60,"desc":"Rafale d'air"},{"nom":"Strong Right","emoji":"🤜","degats":65,"desc":"Poing géant}"}],"faiblesse":"⚡","resistance":"🤖"},
    "gaara":      {"nom":"Gaara",              "serie":"Naruto",          "rarete":"Épique",     "emoji":"🏜️", "pv":210,"attaque":88,"defense":92,"image":"https://i.imgur.com/t4Lx5Mp.jpg","attaques":[{"nom":"Sable","emoji":"🏜️","degats":65,"desc":"Armure de sable"},{"nom":"Tsunami Sable","emoji":"🌊","degats":75,"desc":"Vague de sable"},{"nom":"Shukaku","emoji":"🦝","degats":85,"desc":"Tanuki sableux}"}],"faiblesse":"🌊","resistance":"🏜️"},
    "hinata":     {"nom":"Hinata Hyuga",       "serie":"Naruto",          "rarete":"Épique",     "emoji":"💜", "pv":190,"attaque":85,"defense":80,"image":"https://i.imgur.com/Y1D5DxX.jpg","attaques":[{"nom":"Byakugan","emoji":"👁️","degats":60,"desc":"Œil blanc"},{"nom":"Palme douce","emoji":"💜","degats":70,"desc":"Frappe chakra"},{"nom":"Protection","emoji":"🌸","degats":75,"desc":"Rotation}"}],"faiblesse":"⚡","resistance":"💜"},
    "neji":       {"nom":"Neji Hyuga",         "serie":"Naruto",          "rarete":"Épique",     "emoji":"⚪", "pv":195,"attaque":88,"defense":82,"image":"https://i.imgur.com/RiuULe4.jpg","attaques":[{"nom":"Kaiten","emoji":"⚪","degats":70,"desc":"Rotation défense"},{"nom":"Jyuken","emoji":"👊","degats":65,"desc":"Frappe douce"},{"nom":"64 Palmes","emoji":"💫","degats":80,"desc":"Soixante-quatre frappes}"}],"faiblesse":"🔥","resistance":"⚪"},
    "denji":      {"nom":"Denji",              "serie":"Chainsaw Man",    "rarete":"Épique",     "emoji":"⛓️", "pv":215,"attaque":92,"defense":75,"image":"https://i.imgur.com/4Hz43RO.jpg","attaques":[{"nom":"Tronçonneuse","emoji":"⛓️","degats":75,"desc":"Bras tronçonneuse"},{"nom":"Full Power","emoji":"🩸","degats":85,"desc":"Sang activé"},{"nom":"Chainsaw","emoji":"💥","degats":90,"desc":"Transformation}"}],"faiblesse":"🔥","resistance":"⛓️"},
    "power":      {"nom":"Power",              "serie":"Chainsaw Man",    "rarete":"Épique",     "emoji":"🩸", "pv":205,"attaque":90,"defense":72,"image":"https://i.imgur.com/GaqW7HJ.jpg","attaques":[{"nom":"Marteau Sang","emoji":"🩸","degats":70,"desc":"Arme de sang"},{"nom":"Spear","emoji":"🗡️","degats":75,"desc":"Lance de sang"},{"nom":"Berserk","emoji":"💢","degats":85,"desc":"Mode berserk}"}],"faiblesse":"🔥","resistance":"🩸"},
    "aki":        {"nom":"Aki Hayakawa",       "serie":"Chainsaw Man",    "rarete":"Épique",     "emoji":"🦊", "pv":200,"attaque":87,"defense":75,"image":"https://i.imgur.com/79yrVQQ.jpg","attaques":[{"nom":"Renard","emoji":"🦊","degats":70,"desc":"Démon renard"},{"nom":"Futur","emoji":"🔮","degats":65,"desc":"Démon futur"},{"nom":"Épée","emoji":"⚔️","degats":75,"desc":"Clou maudit}"}],"faiblesse":"🔥","resistance":"🦊"},
    "byakuya":    {"nom":"Byakuya Kuchiki",    "serie":"Bleach",          "rarete":"Épique",     "emoji":"🌸", "pv":205,"attaque":90,"defense":85,"image":"https://i.imgur.com/jtkO5M4.jpg","attaques":[{"nom":"Senbonzakura","emoji":"🌸","degats":70,"desc":"Mille cerisiers"},{"nom":"Bankai","emoji":"💀","degats":85,"desc":"Kageyoshi"},{"nom":"Shikai","emoji":"🌸","degats":65,"desc":"Sakura infini}"}],"faiblesse":"⚡","resistance":"🌸"},
    "maki":       {"nom":"Maki Zen'in",        "serie":"Jujutsu Kaisen",  "rarete":"Épique",     "emoji":"🗡️", "pv":200,"attaque":91,"defense":80,"image":"https://i.imgur.com/9kmdiBl.jpg","attaques":[{"nom":"Arme Spéciale","emoji":"🗡️","degats":70,"desc":"Maîtrise armes"},{"nom":"Zéro Maléfique","emoji":"⬛","degats":80,"desc":"Sans énergie maudite"},{"nom":"Halberd","emoji":"⚔️","degats":75,"desc":"Hallebarde}"}],"faiblesse":"🔮","resistance":"🗡️"},
    "nanami":     {"nom":"Nanami Kento",       "serie":"Jujutsu Kaisen",  "rarete":"Épique",     "emoji":"👔", "pv":205,"attaque":90,"defense":83,"image":"https://i.imgur.com/SHe2w9H.jpg","attaques":[{"nom":"Ratio","emoji":"👔","degats":75,"desc":"Point faible 7:3"},{"nom":"Tranche","emoji":"🔪","degats":70,"desc":"Onde de lame"},{"nom":"Overtime","emoji":"⏰","degats":85,"desc":"Mode surtravail}"}],"faiblesse":"🔥","resistance":"👔"},
    "gyutaro":    {"nom":"Gyutaro",            "serie":"Demon Slayer",    "rarete":"Épique",     "emoji":"🩸", "pv":215,"attaque":95,"defense":80,"image":"https://i.imgur.com/rtnhB8P.jpg","attaques":[{"nom":"Sang Lame","emoji":"🩸","degats":75,"desc":"Faucilles de sang"},{"nom":"Venin","emoji":"☠️","degats":80,"desc":"Poison mortel"},{"nom":"Lune 6","emoji":"🌙","degats":90,"desc":"Lune supérieure 6}"}],"faiblesse":"☀️","resistance":"🩸"},
    "dabi":       {"nom":"Dabi",               "serie":"MHA",             "rarete":"Épique",     "emoji":"🔵", "pv":200,"attaque":90,"defense":72,"image":"https://i.imgur.com/DPJlwqi.jpg","attaques":[{"nom":"Flamme Bleu","emoji":"🔵","degats":75,"desc":"Feu bleu intense"},{"nom":"Blueflame","emoji":"💙","degats":80,"desc":"Brûle tout"},{"nom":"Flamme Max","emoji":"💥","degats":90,"desc":"Auto-destruction}"}],"faiblesse":"💧","resistance":"🔥"},
    "aizawa":     {"nom":"Aizawa Shouta",      "serie":"MHA",             "rarete":"Épique",     "emoji":"🎀", "pv":190,"attaque":85,"defense":80,"image":"https://i.imgur.com/7n4zOPF.jpg","attaques":[{"nom":"Effacement","emoji":"🎀","degats":65,"desc":"Annule les quirks"},{"nom":"Bandage","emoji":"⚡","degats":60,"desc":"Capture"},{"nom":"Erasure","emoji":"👁️","degats":70,"desc":"Regard effaceur}"}],"faiblesse":"💥","resistance":"🎀"},
    # ── RARE ─────────────────────────────────────────────────
    "kirishima":  {"nom":"Kirishima Eijiro",   "serie":"MHA",             "rarete":"Rare",       "emoji":"💎", "pv":185,"attaque":75,"defense":95,"image":"https://i.imgur.com/B5cSxTL.jpg","attaques":[{"nom":"Hardening","emoji":"💎","degats":55,"desc":"Corps dur comme roc"},{"nom":"Unbreakable","emoji":"🪨","degats":70,"desc":"Invincible"},{"nom":"Red Riot","emoji":"💪","degats":60,"desc":"Charge}"}],"faiblesse":"⚡","resistance":"💎"},
    # ── ÉPIQUE (mangas moins connus mais persos forts) ────────
    "kafka":      {"nom":"Hibino Kafka",       "serie":"Kaiju No. 8",     "rarete":"Épique",     "emoji":"🦖", "pv":210,"attaque":92,"defense":80,"image":"https://i.imgur.com/4LZEEsW.jpg","attaques":[{"nom":"Kaiju","emoji":"🦖","degats":80,"desc":"Transformation Kaiju"},{"nom":"Force","emoji":"💪","degats":70,"desc":"Force surhumaine"},{"nom":"Numéro 8","emoji":"8️⃣","degats":90,"desc":"Kaiju No.8}"}],"faiblesse":"🔫","resistance":"🦖"},
    "okarun":     {"nom":"Okarun",             "serie":"Dandadan",        "rarete":"Épique",     "emoji":"👾", "pv":195,"attaque":88,"defense":75,"image":"https://i.imgur.com/fsuOjOH.jpg","attaques":[{"nom":"Turbo Granny","emoji":"👾","degats":70,"desc":"Possession démon"},{"nom":"Pouvoir Alien","emoji":"🛸","degats":75,"desc":"Énergie extraterrestre"},{"nom":"Fusion","emoji":"💥","degats":85,"desc":"Fusion démon}"}],"faiblesse":"✝️","resistance":"👾"},
    "gennarumi":  {"nom":"Gen Narumi",         "serie":"Dandadan",        "rarete":"Épique",     "emoji":"🌙", "pv":200,"attaque":90,"defense":78,"image":"https://i.imgur.com/Zyybzpz.jpg","attaques":[{"nom":"Exorcisme","emoji":"🌙","degats":70,"desc":"Chasse les démons"},{"nom":"Magie","emoji":"✨","degats":65,"desc":"Arts occultes"},{"nom":"Rituel","emoji":"🔮","degats":80,"desc":"Pouvoir spirituel}"}],"faiblesse":"👾","resistance":"🌙"},
    "hoshina":    {"nom":"Soshiro Hoshina",    "serie":"Kaiju No. 8",     "rarete":"Légendaire", "emoji":"⚔️", "pv":215,"attaque":96,"defense":85,"image":"https://i.imgur.com/EUIk9Nv.jpg","attaques":[{"nom":"Lame Kaiju","emoji":"⚔️","degats":80,"desc":"Épées kaiju"},{"nom":"Vitesse","emoji":"⚡","degats":85,"desc":"Rapidité absolue"},{"nom":"Technique","emoji":"💫","degats":90,"desc":"Maîtrise parfaite}"}],"faiblesse":"🦖","resistance":"⚔️"},
    "ichikawa":   {"nom":"Reno Ichikawa",      "serie":"Kaiju No. 8",     "rarete":"Rare",       "emoji":"🔫", "pv":175,"attaque":78,"defense":70,"image":"https://i.imgur.com/vjN9wQd.jpg","attaques":[{"nom":"Fusil","emoji":"🔫","degats":60,"desc":"Arme anti-kaiju"},{"nom":"Défense","emoji":"🛡️","degats":45,"desc":"Position défensive"},{"nom":"Unité","emoji":"🤝","degats":55,"desc":"Combat en équipe}"}],"faiblesse":"🦖","resistance":"🔫"},

    "chiaotzu": {"nom": "Chiaotzu", "emoji": "🤖", "serie": "Dragon Ball Z", "rarete": "Commun", "pv": 80, "attaque": 15, "defense": 10, "image": "https://i.imgur.com/Ls6ZoNh.jpg", "attaques": [{"nom": "Psychokinésie", "emoji": "🧠", "degats": 30, "desc": "Lévitation d'objets"}, {"nom": "Attaque Suicide", "emoji": "💥", "degats": 50, "desc": "Explosion désespérée"}, {"nom": "Rafale Psychique", "emoji": "✨", "degats": 35, "desc": "Vague mentale"}], "faiblesse": "⚡", "resistance": "🤖"},
    "oolong": {"nom": "Oolong", "emoji": "🐷", "serie": "Dragon Ball Z", "rarete": "Commun", "pv": 60, "attaque": 10, "defense": 8, "image": "https://i.imgur.com/WQdxlJV.jpg", "attaques": [{"nom": "Transformation", "emoji": "🐷", "degats": 20, "desc": "Change de forme"}, {"nom": "Frappe Porcine", "emoji": "🐗", "degats": 25, "desc": "Coup de groin"}, {"nom": "Ruse", "emoji": "😈", "degats": 15, "desc": "Tromperie"}], "faiblesse": "⚡", "resistance": "🐷"},
    "celljr": {"nom": "Cell Jr", "emoji": "🟢", "serie": "Dragon Ball Z", "rarete": "Commun", "pv": 100, "attaque": 20, "defense": 15, "image": "https://i.imgur.com/rQZyE9r.jpg", "attaques": [{"nom": "Coup de Poing", "emoji": "👊", "degats": 35, "desc": "Frappe rapide"}, {"nom": "Souffle d'Énergie", "emoji": "💚", "degats": 45, "desc": "Rayon d'énergie"}, {"nom": "Onde Cellulaire", "emoji": "🟢", "degats": 40, "desc": "Attaque cellulaire"}], "faiblesse": "⚡", "resistance": "🟢"},
    "pilaf": {"nom": "Pilaf", "emoji": "🧙", "serie": "Dragon Ball Z", "rarete": "Commun", "pv": 50, "attaque": 5, "defense": 5, "image": "https://i.imgur.com/ljm3Pcx.jpg", "attaques": [{"nom": "Robot Pilaf", "emoji": "🤖", "degats": 20, "desc": "Armure mécanique"}, {"nom": "Cage", "emoji": "🔒", "degats": 15, "desc": "Emprisonnement"}, {"nom": "Ruse Machiavélique", "emoji": "😈", "degats": 10, "desc": "Plan diabolique"}], "faiblesse": "⚡", "resistance": "🧙"},
    "guldo": {"nom": "Guldo", "emoji": "👁️", "serie": "Dragon Ball Z", "rarete": "Commun", "pv": 90, "attaque": 18, "defense": 12, "image": "https://i.imgur.com/AyyXKRH.jpg", "attaques": [{"nom": "Arrêt du Temps", "emoji": "⏸️", "degats": 35, "desc": "Fige l'adversaire"}, {"nom": "Télékinésie", "emoji": "🧠", "degats": 30, "desc": "Force mentale"}, {"nom": "Rayon Paralysant", "emoji": "🟣", "degats": 25, "desc": "Immobilisation"}], "faiblesse": "⚡", "resistance": "👁️"},
    "jeice": {"nom": "Jeice", "emoji": "🔴", "serie": "Dragon Ball Z", "rarete": "Commun", "pv": 120, "attaque": 22, "defense": 18, "image": "https://i.imgur.com/HXvx4HN.jpg", "attaques": [{"nom": "Crusher Ball", "emoji": "🔴", "degats": 55, "desc": "Boule d'énergie"}, {"nom": "Nova Strike", "emoji": "🌟", "degats": 50, "desc": "Charge explosive"}, {"nom": "Full Power Energy Wave", "emoji": "💥", "degats": 45, "desc": "Rafale totale"}], "faiblesse": "⚡", "resistance": "🔴"},
    "burter": {"nom": "Burter", "emoji": "💨", "serie": "Dragon Ball Z", "rarete": "Commun", "pv": 130, "attaque": 25, "defense": 20, "image": "https://i.imgur.com/PJCchbh.jpg", "attaques": [{"nom": "Blue Hurricane", "emoji": "🌀", "degats": 50, "desc": "Tornado bleue"}, {"nom": "Hikou", "emoji": "💨", "degats": 45, "desc": "Vitesse maximale"}, {"nom": "Body Attack", "emoji": "💪", "degats": 40, "desc": "Charge corporelle"}], "faiblesse": "⚡", "resistance": "💨"},
    "recoome": {"nom": "Recoome", "emoji": "💪", "serie": "Dragon Ball Z", "rarete": "Commun", "pv": 150, "attaque": 28, "defense": 22, "image": "https://i.imgur.com/UIpkFSp.jpg", "attaques": [{"nom": "Recoome Beam", "emoji": "🔴", "degats": 60, "desc": "Rayon destructeur"}, {"nom": "Recoome Kick", "emoji": "👟", "degats": 50, "desc": "Coup de pied brutal"}, {"nom": "Recoome Eraser Gun", "emoji": "💥", "degats": 55, "desc": "Tir d'éradication"}], "faiblesse": "⚡", "resistance": "💪"},
    "raditz": {"nom": "Raditz", "emoji": "👨", "serie": "Dragon Ball Z", "rarete": "Commun", "pv": 140, "attaque": 26, "defense": 18, "image": "https://i.imgur.com/6C1qiWd.jpg", "attaques": [{"nom": "Double Sunday", "emoji": "🔴", "degats": 55, "desc": "Double rayon"}, {"nom": "Saturday Crush", "emoji": "💥", "degats": 50, "desc": "Écrasement"}, {"nom": "Mahogany Assault", "emoji": "👊", "degats": 45, "desc": "Assaut brutal"}], "faiblesse": "⚡", "resistance": "👨"},
    "nappa": {"nom": "Nappa", "emoji": "👨‍🦲", "serie": "Dragon Ball Z", "rarete": "Commun", "pv": 160, "attaque": 30, "defense": 25, "image": "https://i.imgur.com/4TBKP7u.jpg", "attaques": [{"nom": "Bomber DX", "emoji": "💥", "degats": 65, "desc": "Explosion massive"}, {"nom": "Volcano Explosion", "emoji": "🌋", "degats": 60, "desc": "Lave bouillante"}, {"nom": "Break Cannon", "emoji": "🔫", "degats": 55, "desc": "Canon destructeur"}], "faiblesse": "⚡", "resistance": "👨‍🦲"},
    "buumaigre": {"nom": "Buu Maigre", "emoji": "🍬", "serie": "Dragon Ball Z", "rarete": "Commun", "pv": 85, "attaque": 12, "defense": 8, "image": "https://i.imgur.com/klfd0MP.jpg", "attaques": [{"nom": "Genocide Attack", "emoji": "☠️", "degats": 75, "desc": "Extermination"}, {"nom": "Warp Kamehameha", "emoji": "💥", "degats": 80, "desc": "Kamehameha distortion"}, {"nom": "Human Extinction Attack", "emoji": "🌑", "degats": 70, "desc": "Anéantissement"}], "faiblesse": "⚡", "resistance": "🍬"},
    "puar": {"nom": "Puar", "emoji": "🐱", "serie": "Dragon Ball Z", "rarete": "Commun", "pv": 40, "attaque": 5, "defense": 5, "image": "https://i.imgur.com/xoEbJHh.jpg", "attaques": [{"nom": "Transformation", "emoji": "🐈", "degats": 15, "desc": "Copie d'ennemi"}, {"nom": "Griffe", "emoji": "🐾", "degats": 20, "desc": "Attaque féline"}, {"nom": "Ruse", "emoji": "😸", "degats": 10, "desc": "Esquive"}], "faiblesse": "⚡", "resistance": "🐱"},
    "babidi": {"nom": "Babidi", "emoji": "🧝", "serie": "Dragon Ball Z", "rarete": "Commun", "pv": 55, "attaque": 8, "defense": 6, "image": "https://i.imgur.com/TbVFfwD.jpg", "attaques": [{"nom": "Magie Babidi", "emoji": "🪄", "degats": 35, "desc": "Contrôle mental"}, {"nom": "Sort Maléfique", "emoji": "💜", "degats": 40, "desc": "Malédiction"}, {"nom": "Bouclier Magique", "emoji": "✨", "degats": 25, "desc": "Protection"}], "faiblesse": "⚡", "resistance": "🧝"},
    "spopovitch": {"nom": "Spopovitch", "emoji": "🤜", "serie": "Dragon Ball Z", "rarete": "Commun", "pv": 110, "attaque": 20, "defense": 15, "image": "https://i.imgur.com/498OBCg.jpg", "attaques": [{"nom": "Frappe Brutale", "emoji": "👊", "degats": 40, "desc": "Coup sans pitié"}, {"nom": "Résistance", "emoji": "💪", "degats": 35, "desc": "Ignorer la douleur"}, {"nom": "Charge", "emoji": "🏃", "degats": 30, "desc": "Ruée violente"}], "faiblesse": "⚡", "resistance": "🤜"},
    "mrpopo": {"nom": "Mr Popo", "emoji": "🌑", "serie": "Dragon Ball Z", "rarete": "Commun", "pv": 75, "attaque": 12, "defense": 10, "image": "https://i.imgur.com/rzPjawD.jpg", "attaques": [{"nom": "Arts Martiaux", "emoji": "🥋", "degats": 45, "desc": "Techniques ancestrales"}, {"nom": "Frappe Mystérieuse", "emoji": "🌑", "degats": 40, "desc": "Coup ésotérique"}, {"nom": "Gardien", "emoji": "🛡️", "degats": 30, "desc": "Défense absolue"}], "faiblesse": "⚡", "resistance": "🌑"},
    "yamu": {"nom": "Yamu", "emoji": "🤛", "serie": "Dragon Ball Z", "rarete": "Commun", "pv": 105, "attaque": 19, "defense": 14, "image": "https://i.imgur.com/lgxeTO7.jpg", "attaques": [{"nom": "Absorber l'Énergie", "emoji": "⚡", "degats": 35, "desc": "Vol de ki"}, {"nom": "Frappe Rapide", "emoji": "💨", "degats": 30, "desc": "Attaque furtive"}, {"nom": "Coup Traître", "emoji": "🗡️", "degats": 40, "desc": "Trahison"}], "faiblesse": "⚡", "resistance": "🤛"},
    "videl": {"nom": "Videl", "emoji": "👧", "serie": "Dragon Ball Z", "rarete": "Commun", "pv": 95, "attaque": 18, "defense": 14, "image": "https://i.imgur.com/TlSc4jR.jpg", "attaques": [{"nom": "Coup de Poing Satan", "emoji": "👊", "degats": 40, "desc": "Héritage Satan"}, {"nom": "Jet de Ki", "emoji": "💚", "degats": 35, "desc": "Débutante en ki"}, {"nom": "Attaque Volante", "emoji": "🦅", "degats": 45, "desc": "Combat aérien"}], "faiblesse": "⚡", "resistance": "👧"},
    "chichi": {"nom": "Chi-Chi", "emoji": "👩", "serie": "Dragon Ball Z", "rarete": "Commun", "pv": 70, "attaque": 14, "defense": 10, "image": "https://i.imgur.com/V49V1AJ.jpg", "attaques": [{"nom": "Coup de Pied Volant", "emoji": "🦵", "degats": 45, "desc": "Frappe maternelle"}, {"nom": "Colère de Mère", "emoji": "😠", "degats": 55, "desc": "Rage légendaire"}, {"nom": "Arts Martiaux", "emoji": "🥋", "degats": 40, "desc": "Techniques apprises"}], "faiblesse": "⚡", "resistance": "👩"},
    "bulma": {"nom": "Bulma", "emoji": "👱‍♀️", "serie": "Dragon Ball Z", "rarete": "Commun", "pv": 50, "attaque": 8, "defense": 6, "image": "https://i.imgur.com/CuRdkfj.jpg", "attaques": [{"nom": "Pistolet", "emoji": "🔫", "degats": 30, "desc": "Tir précis"}, {"nom": "Gadget Capsule", "emoji": "💊", "degats": 35, "desc": "Technologie Capsule Corp"}, {"nom": "Robot de Combat", "emoji": "🤖", "degats": 45, "desc": "Armure mécanique"}], "faiblesse": "⚡", "resistance": "👱‍♀️"},
    "mrSatan": {"nom": "Mr Satan", "emoji": "🥊", "serie": "Dragon Ball Z", "rarete": "Commun", "pv": 88, "attaque": 16, "defense": 12, "image": "https://i.imgur.com/gMzLZve.jpg", "attaques": [{"nom": "Dynamic Mess Em Up Punch", "emoji": "👊", "degats": 35, "desc": "Punching star"}, {"nom": "Rolling Satan Punch", "emoji": "🌀", "degats": 40, "desc": "Coup tournoyant"}, {"nom": "Present for You", "emoji": "💣", "degats": 30, "desc": "Grenade"}], "faiblesse": "⚡", "resistance": "🥊"},
    "ebisu": {"nom": "Ebisu", "emoji": "🕶️", "serie": "Naruto", "rarete": "Commun", "pv": 80, "attaque": 14, "defense": 12, "image": "https://i.imgur.com/E7tlhOH.jpg", "attaques": [{"nom": "Frappe Ecchi", "emoji": "😳", "degats": 20, "desc": "Attaque gênante"}, {"nom": "Jutsu Pervers", "emoji": "🌸", "degats": 15, "desc": "Technique honteuse"}, {"nom": "Shunshin", "emoji": "💨", "degats": 25, "desc": "Déplacement rapide"}], "faiblesse": "⚡", "resistance": "🕶️"},
    "iruka": {"nom": "Iruka Umino", "emoji": "📚", "serie": "Naruto", "rarete": "Commun", "pv": 85, "attaque": 16, "defense": 13, "image": "https://i.imgur.com/jJg9gWq.jpg", "attaques": [{"nom": "Kunai", "emoji": "🗡️", "degats": 30, "desc": "Lancer précis"}, {"nom": "Shuriken", "emoji": "⭐", "degats": 25, "desc": "Projection d'étoiles"}, {"nom": "Jutsu de Transformation", "emoji": "👤", "degats": 20, "desc": "Déguisement parfait"}], "faiblesse": "⚡", "resistance": "📚"},
    "ino": {"nom": "Ino Yamanaka", "emoji": "🌸", "serie": "Naruto", "rarete": "Commun", "pv": 75, "attaque": 13, "defense": 11, "image": "https://i.imgur.com/6pcNDvB.jpg", "attaques": [{"nom": "Jutsu de Transfert Mental", "emoji": "🧠", "degats": 40, "desc": "Contrôle du corps"}, {"nom": "Nin-Jutsu Floral", "emoji": "🌸", "degats": 35, "desc": "Attaque florale"}, {"nom": "Shintenshin", "emoji": "💜", "degats": 45, "desc": "Possession mentale"}], "faiblesse": "⚡", "resistance": "🌸"},
    "choji": {"nom": "Choji Akimichi", "emoji": "🍖", "serie": "Naruto", "rarete": "Commun", "pv": 90, "attaque": 16, "defense": 14, "image": "https://i.imgur.com/0haGoIw.jpg", "attaques": [{"nom": "Jutsu Expansion", "emoji": "💪", "degats": 50, "desc": "Corps géant"}, {"nom": "Cho-Baika", "emoji": "🔵", "degats": 55, "desc": "Expansion maximale"}, {"nom": "Frappe Roulante", "emoji": "⚫", "degats": 60, "desc": "Boule humaine"}], "faiblesse": "⚡", "resistance": "🍖"},
    "kankuro": {"nom": "Kankuro", "emoji": "🎭", "serie": "Naruto", "rarete": "Commun", "pv": 88, "attaque": 17, "defense": 13, "image": "https://i.imgur.com/bdRuDAU.jpg", "attaques": [{"nom": "Karasu", "emoji": "🪆", "degats": 45, "desc": "Marionnette corbeau"}, {"nom": "Kuroari", "emoji": "🖤", "degats": 50, "desc": "Marionnette noire"}, {"nom": "Sanshouo", "emoji": "🦎", "degats": 55, "desc": "Marionnette défensive"}], "faiblesse": "⚡", "resistance": "🎭"},
    "anko": {"nom": "Anko Mitarashi", "emoji": "🍡", "serie": "Naruto", "rarete": "Commun", "pv": 92, "attaque": 18, "defense": 14, "image": "https://i.imgur.com/9ioyert.jpg", "attaques": [{"nom": "Juinjutsu", "emoji": "🐍", "degats": 45, "desc": "Malédiction serpent"}, {"nom": "Mille Serpents", "emoji": "🐍", "degats": 55, "desc": "Essaim de serpents"}, {"nom": "Kakuzu de Serpent", "emoji": "☠️", "degats": 50, "desc": "Morsure empoisonnée"}], "faiblesse": "⚡", "resistance": "🍡"},
    "izumo": {"nom": "Izumo Kamizuki", "emoji": "🗡️", "serie": "Naruto", "rarete": "Commun", "pv": 78, "attaque": 14, "defense": 12, "image": "https://i.imgur.com/JOu1umT.jpg", "attaques": [{"nom": "Kunai Combiné", "emoji": "🗡️", "degats": 35, "desc": "Binôme tactique"}, {"nom": "Formation Équipe", "emoji": "🤝", "degats": 30, "desc": "Attaque coordonnée"}, {"nom": "Jutsu Eau", "emoji": "💧", "degats": 40, "desc": "Vague liquide"}], "faiblesse": "⚡", "resistance": "🗡️"},
    "kotetsu": {"nom": "Kotetsu Hagane", "emoji": "⚔️", "serie": "Naruto", "rarete": "Commun", "pv": 78, "attaque": 14, "defense": 12, "image": "https://i.imgur.com/DlRzvyY.jpg", "attaques": [{"nom": "Naginata", "emoji": "⚔️", "degats": 40, "desc": "Lance tournoyante"}, {"nom": "Formation Binôme", "emoji": "🤝", "degats": 35, "desc": "Combo tactique"}, {"nom": "Jutsu Terre", "emoji": "🌍", "degats": 30, "desc": "Mur de terre"}], "faiblesse": "⚡", "resistance": "⚔️"},
    "moegi": {"nom": "Moegi", "emoji": "🍀", "serie": "Naruto", "rarete": "Commun", "pv": 60, "attaque": 10, "defense": 8, "image": "https://i.imgur.com/WeWmVwc.jpg", "attaques": [{"nom": "Jutsu Bois", "emoji": "🌿", "degats": 30, "desc": "Branches lianes"}, {"nom": "Mokuton Débutant", "emoji": "🌱", "degats": 25, "desc": "Végétation naissante"}, {"nom": "Frappe Konoha", "emoji": "👊", "degats": 20, "desc": "Esprit du village"}], "faiblesse": "⚡", "resistance": "🍀"},
    "hanabi": {"nom": "Hanabi Hyuga", "emoji": "🎆", "serie": "Naruto", "rarete": "Commun", "pv": 70, "attaque": 13, "defense": 11, "image": "https://i.imgur.com/t29BUBj.jpg", "attaques": [{"nom": "Byakugan", "emoji": "👁️", "degats": 45, "desc": "Vision céleste"}, {"nom": "Jūken", "emoji": "✋", "degats": 50, "desc": "Frappe douce"}, {"nom": "Protection des 8 Trigrammes", "emoji": "🔵", "degats": 55, "desc": "Bouclier rotatif"}], "faiblesse": "⚡", "resistance": "🎆"},
    "hidan": {"nom": "Hidan", "emoji": "✝️", "serie": "Naruto", "rarete": "Commun", "pv": 95, "attaque": 20, "defense": 15, "image": "https://i.imgur.com/G7pZkhI.jpg", "attaques": [{"nom": "Rituel de Jashin", "emoji": "☠️", "degats": 70, "desc": "Malédiction mortelle"}, {"nom": "Faux Immortelle", "emoji": "⚔️", "degats": 65, "desc": "Lame de Jashin"}, {"nom": "Lien de Sang", "emoji": "🩸", "degats": 75, "desc": "Douleur partagée"}], "faiblesse": "⚡", "resistance": "✝️"},
    "kakuzu": {"nom": "Kakuzu", "emoji": "🧵", "serie": "Naruto", "rarete": "Commun", "pv": 100, "attaque": 22, "defense": 18, "image": "https://i.imgur.com/a1qKNly.jpg", "attaques": [{"nom": "Cœur de Feu", "emoji": "🔥", "degats": 65, "desc": "Masque igné"}, {"nom": "Cœur de Foudre", "emoji": "⚡", "degats": 70, "desc": "Masque électrique"}, {"nom": "Fils de la Mort", "emoji": "🖤", "degats": 75, "desc": "Tentacules noirs"}], "faiblesse": "⚡", "resistance": "🧵"},
    "coby": {"nom": "Coby", "emoji": "🐟", "serie": "One Piece", "rarete": "Commun", "pv": 65, "attaque": 11, "defense": 9, "image": "https://i.imgur.com/D6I5q8r.jpg", "attaques": [{"nom": "Pistol", "emoji": "👊", "degats": 30, "desc": "Coup Haki débutant"}, {"nom": "Soru", "emoji": "💨", "degats": 25, "desc": "Six Techniques Marine"}, {"nom": "Haki d'Observation", "emoji": "👁️", "degats": 35, "desc": "Sens aiguisés"}], "faiblesse": "⚡", "resistance": "🐟"},
    "helmeppo": {"nom": "Helmeppo", "emoji": "🔪", "serie": "One Piece", "rarete": "Commun", "pv": 68, "attaque": 12, "defense": 10, "image": "https://i.imgur.com/75dmyw6.jpg", "attaques": [{"nom": "Deux Sabers", "emoji": "⚔️", "degats": 35, "desc": "Double épée"}, {"nom": "Coup Cross", "emoji": "✂️", "degats": 30, "desc": "Attaque croisée"}, {"nom": "Soru", "emoji": "💨", "degats": 25, "desc": "Six Techniques"}], "faiblesse": "⚡", "resistance": "🔪"},
    "richie": {"nom": "Richie", "emoji": "🦁", "serie": "One Piece", "rarete": "Commun", "pv": 90, "attaque": 17, "defense": 13, "image": "https://i.imgur.com/JzbTwwD.jpg", "attaques": [{"nom": "Morsure de Lion", "emoji": "🦁", "degats": 45, "desc": "Attaque animale"}, {"nom": "Charge Féline", "emoji": "🐆", "degats": 50, "desc": "Ruée de fauve"}, {"nom": "Rugissement", "emoji": "📣", "degats": 35, "desc": "Déstabilise"}], "faiblesse": "⚡", "resistance": "🦁"},
    "alvida": {"nom": "Alvida", "emoji": "🍎", "serie": "One Piece", "rarete": "Commun", "pv": 85, "attaque": 16, "defense": 12, "image": "https://i.imgur.com/6DoLNt8.jpg", "attaques": [{"nom": "Smooth Smooth", "emoji": "🌸", "degats": 40, "desc": "Corps glissant"}, {"nom": "Bûcher", "emoji": "🪵", "degats": 35, "desc": "Coup de gourdin"}, {"nom": "Impact Rebond", "emoji": "💥", "degats": 45, "desc": "Glissement fatal"}], "faiblesse": "⚡", "resistance": "🍎"},
    "wapol": {"nom": "Wapol", "emoji": "🍽️", "serie": "One Piece", "rarete": "Commun", "pv": 100, "attaque": 19, "defense": 15, "image": "https://i.imgur.com/ME6sNT9.jpg", "attaques": [{"nom": "Baku Baku", "emoji": "😮", "degats": 40, "desc": "Mange et absorbe"}, {"nom": "Wapol's Munch", "emoji": "🦷", "degats": 35, "desc": "Morsure dévorante"}, {"nom": "Baku Baku no Mi", "emoji": "🤖", "degats": 50, "desc": "Corps fusionné"}], "faiblesse": "⚡", "resistance": "🍽️"},
    "buggy": {"nom": "Buggy le Clown", "emoji": "🤡", "serie": "One Piece", "rarete": "Commun", "pv": 95, "attaque": 18, "defense": 14, "image": "https://i.imgur.com/zaPTd4C.jpg", "attaques": [{"nom": "Bara Bara Chou", "emoji": "🎪", "degats": 45, "desc": "Corps séparé"}, {"nom": "Bara Bara Festival", "emoji": "🔪", "degats": 50, "desc": "Pluie de tranchants"}, {"nom": "Muggy Ball", "emoji": "💣", "degats": 55, "desc": "Bombe de précision"}], "faiblesse": "⚡", "resistance": "🤡"},
    "mohji": {"nom": "Mohji", "emoji": "🐻", "serie": "One Piece", "rarete": "Commun", "pv": 70, "attaque": 13, "defense": 10, "image": "https://i.imgur.com/yO9O84d.jpg", "attaques": [{"nom": "Richie Attaque", "emoji": "🦁", "degats": 40, "desc": "Charge de lion"}, {"nom": "Coup d'Épaule", "emoji": "👊", "degats": 30, "desc": "Frappe brute"}, {"nom": "Morsure de Richie", "emoji": "🦷", "degats": 35, "desc": "Attaque animale"}], "faiblesse": "⚡", "resistance": "🐻"},
    "cabaji": {"nom": "Cabaji", "emoji": "🤸", "serie": "One Piece", "rarete": "Commun", "pv": 75, "attaque": 14, "defense": 11, "image": "https://i.imgur.com/MoaRmJd.jpg", "attaques": [{"nom": "Unicycle Attack", "emoji": "🎡", "degats": 40, "desc": "Roue mortelle"}, {"nom": "Top Spin", "emoji": "🌀", "degats": 45, "desc": "Tourbillon"}, {"nom": "Gyro Move", "emoji": "⚙️", "degats": 35, "desc": "Technique de cirque"}], "faiblesse": "⚡", "resistance": "🤸"},
    "jango": {"nom": "Jango", "emoji": "🌙", "serie": "One Piece", "rarete": "Commun", "pv": 72, "attaque": 13, "defense": 10, "image": "https://i.imgur.com/A6fISXf.jpg", "attaques": [{"nom": "Hypnose", "emoji": "👁️", "degats": 35, "desc": "Sommeil forcé"}, {"nom": "Chakram", "emoji": "⭕", "degats": 45, "desc": "Anneaux tranchants"}, {"nom": "Danse Hypnotique", "emoji": "💃", "degats": 30, "desc": "Confusion mentale"}], "faiblesse": "⚡", "resistance": "🌙"},
    "bonclay": {"nom": "Bon Clay", "emoji": "🦢", "serie": "One Piece", "rarete": "Commun", "pv": 88, "attaque": 17, "defense": 13, "image": "https://i.imgur.com/LoOhxYu.jpg", "attaques": [{"nom": "Mane Mane no Mi", "emoji": "👤", "degats": 50, "desc": "Copie parfaite"}, {"nom": "Ballet Kenpo", "emoji": "🩰", "degats": 45, "desc": "Arts martiaux dansés"}, {"nom": "Okama Kenpo", "emoji": "👠", "degats": 55, "desc": "Technique des Okama"}], "faiblesse": "⚡", "resistance": "🦢"},
    "foxy": {"nom": "Foxy", "emoji": "🦊", "serie": "One Piece", "rarete": "Commun", "pv": 82, "attaque": 15, "defense": 12, "image": "https://i.imgur.com/MKVeZsg.jpg", "attaques": [{"nom": "Noro Noro Beam", "emoji": "🟡", "degats": 50, "desc": "Ralentissement 30s"}, {"nom": "Slow Beam", "emoji": "💛", "degats": 45, "desc": "Flash ralentisseur"}, {"nom": "Power Rush", "emoji": "💥", "degats": 40, "desc": "Charge ralentie"}], "faiblesse": "⚡", "resistance": "🦊"},
    "mineta": {"nom": "Mineta", "emoji": "🍇", "serie": "My Hero Academia", "rarete": "Commun", "pv": 55, "attaque": 9, "defense": 7, "image": "https://i.imgur.com/DV0c9Sa.jpg", "attaques": [{"nom": "Pop Off", "emoji": "🟣", "degats": 35, "desc": "Boules collantes"}, {"nom": "Grape Buckler", "emoji": "🛡️", "degats": 30, "desc": "Bouclier raisin"}, {"nom": "Super Grape Rush", "emoji": "💥", "degats": 40, "desc": "Pluie de raisins"}], "faiblesse": "⚡", "resistance": "🍇"},
    "sero": {"nom": "Sero Hanta", "emoji": "🧻", "serie": "My Hero Academia", "rarete": "Commun", "pv": 72, "attaque": 13, "defense": 11, "image": "https://i.imgur.com/bFBAIFm.jpg", "attaques": [{"nom": "Tape Binding", "emoji": "🟫", "degats": 50, "desc": "Ligotage de bande"}, {"nom": "Tape Swing", "emoji": "💨", "degats": 45, "desc": "Balancement"}, {"nom": "Tape Capture", "emoji": "🎯", "degats": 55, "desc": "Capture de bande"}], "faiblesse": "⚡", "resistance": "🧻"},
    "aoyama": {"nom": "Aoyama Yuga", "emoji": "⭐", "serie": "My Hero Academia", "rarete": "Commun", "pv": 68, "attaque": 12, "defense": 9, "image": "https://i.imgur.com/BxGZJIL.jpg", "attaques": [{"nom": "Navel Laser", "emoji": "⭐", "degats": 35, "desc": "Rayon du nombril"}, {"nom": "Can't Stop Twinkling", "emoji": "🌟", "degats": 40, "desc": "Bouclier laser"}, {"nom": "Shining Spot", "emoji": "✨", "degats": 30, "desc": "Point brillant"}], "faiblesse": "⚡", "resistance": "⭐"},
    "hagakure": {"nom": "Hagakure Toru", "emoji": "👻", "serie": "My Hero Academia", "rarete": "Commun", "pv": 60, "attaque": 10, "defense": 8, "image": "https://i.imgur.com/mHsMwlA.jpg", "attaques": [{"nom": "Light Refraction", "emoji": "🌈", "degats": 35, "desc": "Réfraction lumineuse"}, {"nom": "Invisibility", "emoji": "👻", "degats": 40, "desc": "Invisibilité totale"}, {"nom": "Flash Gauntlets", "emoji": "⚡", "degats": 45, "desc": "Gants de flash"}], "faiblesse": "⚡", "resistance": "👻"},
    "ojiro": {"nom": "Ojiro Mashirao", "emoji": "🐒", "serie": "My Hero Academia", "rarete": "Commun", "pv": 75, "attaque": 14, "defense": 12, "image": "https://i.imgur.com/XwG9qOE.jpg", "attaques": [{"nom": "Tail Strike", "emoji": "🌀", "degats": 40, "desc": "Coup de queue"}, {"nom": "Martial Arts Combo", "emoji": "🥋", "degats": 45, "desc": "Combo d'arts martiaux"}, {"nom": "Tornado Tail", "emoji": "🌪️", "degats": 50, "desc": "Queue tornade"}], "faiblesse": "⚡", "resistance": "🐒"},
    "thomas": {"nom": "Thomas", "emoji": "😐", "serie": "Attack on Titan", "rarete": "Commun", "pv": 50, "attaque": 8, "defense": 6, "image": "https://i.imgur.com/ahh7Com.jpg", "attaques": [{"nom": "Frappe Brute", "emoji": "👊", "degats": 40, "desc": "Coup de brute"}, {"nom": "Rage Attack", "emoji": "💢", "degats": 45, "desc": "Attaque enragée"}, {"nom": "Power Move", "emoji": "💪", "degats": 35, "desc": "Mouvement de force"}], "faiblesse": "⚡", "resistance": "😐"},
    "daz": {"nom": "Daz", "emoji": "😶", "serie": "Attack on Titan", "rarete": "Commun", "pv": 55, "attaque": 9, "defense": 7, "image": "https://i.imgur.com/JzbTwwD.jpg", "attaques": [{"nom": "Dice Dice no Mi", "emoji": "🎲", "degats": 60, "desc": "Lames tranchantes"}, {"nom": "Razor Edge", "emoji": "✂️", "degats": 65, "desc": "Coupe tout"}, {"nom": "Blade Rush", "emoji": "🗡️", "degats": 55, "desc": "Ruée de lames"}], "faiblesse": "⚡", "resistance": "😶"},
    "samuel": {"nom": "Samuel", "emoji": "😑", "serie": "Attack on Titan", "rarete": "Commun", "pv": 52, "attaque": 8, "defense": 6, "image": "https://i.imgur.com/JzbTwwD.jpg", "attaques": [{"nom": "Frappe de Base", "emoji": "👊", "degats": 30, "desc": "Coup direct"}, {"nom": "Technique Secrète", "emoji": "🌀", "degats": 35, "desc": "Art martial"}, {"nom": "Endurance", "emoji": "💪", "degats": 25, "desc": "Résistance"}], "faiblesse": "⚡", "resistance": "😑"},
    "tonpa": {"nom": "Tonpa", "emoji": "🧃", "serie": "HunterxHunter", "rarete": "Commun", "pv": 60, "attaque": 10, "defense": 8, "image": "https://i.imgur.com/P3fsw0E.jpg", "attaques": [{"nom": "Jus Laxatif", "emoji": "🧃", "degats": 20, "desc": "Affaiblit l'ennemi"}, {"nom": "Manipulation Psycho", "emoji": "😈", "degats": 15, "desc": "Déstabilisation mentale"}, {"nom": "Piège", "emoji": "🕳️", "degats": 25, "desc": "Embuscade traître"}], "faiblesse": "⚡", "resistance": "🧃"},
    "pokkle": {"nom": "Pokkle", "emoji": "🏹", "serie": "HunterxHunter", "rarete": "Commun", "pv": 70, "attaque": 13, "defense": 10, "image": "https://i.imgur.com/e6jBMaX.jpg", "attaques": [{"nom": "Arc et Flèches Nen", "emoji": "🏹", "degats": 40, "desc": "Tir de Nen"}, {"nom": "Rainbow", "emoji": "🌈", "degats": 45, "desc": "Flèches colorées"}, {"nom": "Flèche Empoisonnée", "emoji": "☠️", "degats": 50, "desc": "Poison létal"}], "faiblesse": "⚡", "resistance": "🏹"},
    "hanataro": {"nom": "Hanataro Yamada", "emoji": "💊", "serie": "Bleach", "rarete": "Commun", "pv": 65, "attaque": 11, "defense": 9, "image": "https://i.imgur.com/pHxnJ3G.jpg", "attaques": [{"nom": "Hisagomaru", "emoji": "💉", "degats": 30, "desc": "Absorbe les blessures"}, {"nom": "Soin Shinigami", "emoji": "🩹", "degats": 25, "desc": "Guérison rapide"}, {"nom": "Relâche Blessures", "emoji": "💥", "degats": 50, "desc": "Libère l'énergie absorbée"}], "faiblesse": "⚡", "resistance": "💊"},
    "donkanonji": {"nom": "Don Kanonji", "emoji": "📺", "serie": "Bleach", "rarete": "Commun", "pv": 55, "attaque": 9, "defense": 7, "image": "https://i.imgur.com/0mrQRon.jpg", "attaques": [{"nom": "Kanon Ball", "emoji": "🔵", "degats": 35, "desc": "Boule spirituelle"}, {"nom": "Cri Bakudo", "emoji": "📣", "degats": 30, "desc": "Cri purificateur"}, {"nom": "Frappe de Héros", "emoji": "👊", "degats": 40, "desc": "Coup héroïque"}], "faiblesse": "⚡", "resistance": "📺"},
    "keigo": {"nom": "Keigo Asano", "emoji": "🐔", "serie": "Bleach", "rarete": "Commun", "pv": 50, "attaque": 7, "defense": 6, "image": "https://i.imgur.com/KxrABAv.jpg", "attaques": [{"nom": "Fuite Rapide", "emoji": "💨", "degats": 20, "desc": "Esquive experte"}, {"nom": "Jet d'Objet", "emoji": "📦", "degats": 15, "desc": "Lance n'importe quoi"}, {"nom": "Pleurs Désespérés", "emoji": "😭", "degats": 10, "desc": "Déstabilise l'ennemi"}], "faiblesse": "⚡", "resistance": "🐔"},
    "mizuiro": {"nom": "Mizuiro Kojima", "emoji": "📱", "serie": "Bleach", "rarete": "Commun", "pv": 48, "attaque": 7, "defense": 5, "image": "https://i.imgur.com/VHWPYMs.jpg", "attaques": [{"nom": "Téléphone Portable", "emoji": "📱", "degats": 15, "desc": "Distraction"}, {"nom": "Stratégie Calme", "emoji": "🧠", "degats": 20, "desc": "Analyse tactique"}, {"nom": "Coup Surprise", "emoji": "👊", "degats": 25, "desc": "Attaque inattendue"}], "faiblesse": "⚡", "resistance": "📱"},
    "kazuma": {"nom": "Kazuma Sato", "emoji": "🧢", "serie": "Konosuba", "rarete": "Commun", "pv": 65, "attaque": 12, "defense": 9, "image": "https://i.imgur.com/enjMPoo.jpg", "attaques": [{"nom": "Explosion Kritika", "emoji": "💥", "degats": 35, "desc": "Attaque critique"}, {"nom": "Drain Touch", "emoji": "👻", "degats": 30, "desc": "Vol de points de vie"}, {"nom": "Lucky Roll", "emoji": "🎲", "degats": 25, "desc": "Chance aléatoire"}], "faiblesse": "⚡", "resistance": "🧢"},
    "aqua": {"nom": "Aqua", "emoji": "💧", "serie": "Konosuba", "rarete": "Commun", "pv": 70, "attaque": 11, "defense": 8, "image": "https://i.imgur.com/8rNReMB.jpg", "attaques": [{"nom": "Sacred Break Spell", "emoji": "💧", "degats": 40, "desc": "Brise les malédictions"}, {"nom": "God Requiem", "emoji": "🌊", "degats": 55, "desc": "Requiem divin"}, {"nom": "Purification", "emoji": "✨", "degats": 35, "desc": "Purifie les morts-vivants"}], "faiblesse": "⚡", "resistance": "💧"},
    "megumin": {"nom": "Megumin", "emoji": "💥", "serie": "Konosuba", "rarete": "Commun", "pv": 60, "attaque": 20, "defense": 5, "image": "https://i.imgur.com/tyeydlp.jpg", "attaques": [{"nom": "Explosion", "emoji": "💥", "degats": 80, "desc": "L'unique sort"}, {"nom": "Explosion Avancée", "emoji": "💥", "degats": 85, "desc": "Version améliorée"}, {"nom": "Explosion Critique", "emoji": "💀", "degats": 90, "desc": "Explosion maximale"}], "faiblesse": "⚡", "resistance": "💥"},
    "darkness": {"nom": "Darkness", "emoji": "🛡️", "serie": "Konosuba", "rarete": "Commun", "pv": 120, "attaque": 8, "defense": 30, "image": "https://i.imgur.com/JzbTwwD.jpg", "attaques": [{"nom": "Masochistic Guard", "emoji": "🛡️", "degats": 25, "desc": "Absorbe les coups"}, {"nom": "Holy Sword", "emoji": "⚔️", "degats": 35, "desc": "Lame sacrée"}, {"nom": "Crusader Charge", "emoji": "🏃", "degats": 30, "desc": "Charge croisée"}], "faiblesse": "⚡", "resistance": "🛡️"},
    "elfman": {"nom": "Elfman Strauss", "emoji": "💪", "serie": "Fairy Tail", "rarete": "Commun", "pv": 95, "attaque": 18, "defense": 15, "image": "https://i.imgur.com/9ZPNM8f.jpg", "attaques": [{"nom": "Take Over Bête", "emoji": "🐺", "degats": 55, "desc": "Transformation bête"}, {"nom": "Beast Soul", "emoji": "🦁", "degats": 60, "desc": "Âme de bête"}, {"nom": "Full Body Take Over", "emoji": "💪", "degats": 65, "desc": "Prise de corps totale"}], "faiblesse": "⚡", "resistance": "💪"},
    "jet": {"nom": "Jet", "emoji": "💨", "serie": "Fairy Tail", "rarete": "Commun", "pv": 75, "attaque": 14, "defense": 11, "image": "https://i.imgur.com/JzbTwwD.jpg", "attaques": [{"nom": "Jet Propulsion", "emoji": "💨", "degats": 50, "desc": "Vitesse maximale"}, {"nom": "Sky Kick", "emoji": "🦵", "degats": 55, "desc": "Coup aérien"}, {"nom": "Supersonic Strike", "emoji": "⚡", "degats": 60, "desc": "Frappe sonique"}], "faiblesse": "⚡", "resistance": "💨"},
    "droy": {"nom": "Droy", "emoji": "🌿", "serie": "Fairy Tail", "rarete": "Commun", "pv": 72, "attaque": 13, "defense": 10, "image": "https://i.imgur.com/RCiD6JL.jpg", "attaques": [{"nom": "Magie des Plantes", "emoji": "🌿", "degats": 35, "desc": "Contrôle végétal"}, {"nom": "Flèche Végétale", "emoji": "🌱", "degats": 40, "desc": "Tir végétal"}, {"nom": "Bouclier Épineux", "emoji": "🌵", "degats": 30, "desc": "Mur d'épines"}], "faiblesse": "⚡", "resistance": "🌿"},
    "speedwagon": {"nom": "Speedwagon", "emoji": "🎩", "serie": "JoJo", "rarete": "Commun", "pv": 65, "attaque": 12, "defense": 9, "image": "https://i.imgur.com/MNQUd3I.jpg", "attaques": [{"nom": "Chapeau Tranchant", "emoji": "🎩", "degats": 35, "desc": "Lame de chapeau"}, {"nom": "Bravado", "emoji": "💪", "degats": 30, "desc": "Courage héroïque"}, {"nom": "Soutien Tactique", "emoji": "🤝", "degats": 25, "desc": "Aide précieuse"}], "faiblesse": "⚡", "resistance": "🎩"},
    "polnareff": {"nom": "Polnareff", "emoji": "🗡️", "serie": "JoJo", "rarete": "Commun", "pv": 80, "attaque": 16, "defense": 12, "image": "https://i.imgur.com/KD7QyWH.jpg", "attaques": [{"nom": "Silver Chariot", "emoji": "⚔️", "degats": 60, "desc": "Épée rapide"}, {"nom": "Silver Chariot Requiem", "emoji": "🌑", "degats": 75, "desc": "Âmes échangées"}, {"nom": "Thousand Swords", "emoji": "🗡️", "degats": 65, "desc": "Mille épées"}], "faiblesse": "⚡", "resistance": "🗡️"},
    "avdol": {"nom": "Muhammad Avdol", "emoji": "🔥", "serie": "JoJo", "rarete": "Commun", "pv": 82, "attaque": 17, "defense": 13, "image": "https://i.imgur.com/DfX89ry.jpg", "attaques": [{"nom": "Magician's Red", "emoji": "🔥", "degats": 65, "desc": "Oiseau de feu"}, {"nom": "Crossfire Hurricane", "emoji": "🌪️", "degats": 70, "desc": "Feu tournoyant"}, {"nom": "Red Bind", "emoji": "🔴", "degats": 60, "desc": "Chaînes de flammes"}], "faiblesse": "⚡", "resistance": "🔥"},
    "akkun": {"nom": "Akkun", "emoji": "😰", "serie": "Tokyo Revengers", "rarete": "Commun", "pv": 55, "attaque": 9, "defense": 7, "image": "https://i.imgur.com/PYv67d3.jpg", "attaques": [{"nom": "Batte de Baseball", "emoji": "⚾", "degats": 25, "desc": "Coup de batte"}, {"nom": "Rage Soudaine", "emoji": "😤", "degats": 30, "desc": "Frappe impulsive"}, {"nom": "Intimidation", "emoji": "😠", "degats": 20, "desc": "Regard menaçant"}], "faiblesse": "⚡", "resistance": "😰"},
    "yamagishi": {"nom": "Yamagishi", "emoji": "😅", "serie": "Tokyo Revengers", "rarete": "Commun", "pv": 50, "attaque": 8, "defense": 6, "image": "https://i.imgur.com/34FzbI3.jpg", "attaques": [{"nom": "Analyse Tactique", "emoji": "🧠", "degats": 20, "desc": "Stratégie"}, {"nom": "Soutien", "emoji": "🤝", "degats": 15, "desc": "Aide alliés"}, {"nom": "Frappe Surprise", "emoji": "👊", "degats": 25, "desc": "Inattendu"}], "faiblesse": "⚡", "resistance": "😅"},
    "otto": {"nom": "Otto Suwen", "emoji": "🗣️", "serie": "Re:Zero", "rarete": "Commun", "pv": 62, "attaque": 10, "defense": 9, "image": "https://i.imgur.com/yj239Dw.jpg", "attaques": [{"nom": "Magie Animale", "emoji": "🦋", "degats": 40, "desc": "Communication animale"}, {"nom": "Invocation", "emoji": "📣", "degats": 45, "desc": "Appel des bêtes"}, {"nom": "Barrière Mentale", "emoji": "🧠", "degats": 35, "desc": "Protection psychique"}], "faiblesse": "⚡", "resistance": "🗣️"},
    "malty": {"nom": "Malty Melromarc", "emoji": "🎭", "serie": "The Rising of the Shield Hero", "rarete": "Commun", "pv": 60, "attaque": 11, "defense": 8, "image": "https://i.imgur.com/1XTtPVw.jpg", "attaques": [{"nom": "Manipulation Politique", "emoji": "👑", "degats": 30, "desc": "Fausse accusation"}, {"nom": "Magie Feu", "emoji": "🔥", "degats": 40, "desc": "Flammes traîtresses"}, {"nom": "Trahison", "emoji": "🗡️", "degats": 35, "desc": "Coup dans le dos"}], "faiblesse": "⚡", "resistance": "🎭"},
    "corkus": {"nom": "Corkus", "emoji": "😤", "serie": "Berserk", "rarete": "Commun", "pv": 70, "attaque": 13, "defense": 10, "image": "https://i.imgur.com/4sywNUP.jpg", "attaques": [{"nom": "Épée", "emoji": "⚔️", "degats": 35, "desc": "Coup de lame"}, {"nom": "Frustration", "emoji": "😤", "degats": 30, "desc": "Frappe agacée"}, {"nom": "Mépris", "emoji": "👎", "degats": 20, "desc": "Démoralise"}], "faiblesse": "⚡", "resistance": "😤"},
    "sekke": {"nom": "Sekke Bronzazza", "emoji": "🥉", "serie": "Black Clover", "rarete": "Commun", "pv": 62, "attaque": 11, "defense": 9, "image": "https://i.imgur.com/qEHztQO.jpg", "attaques": [{"nom": "Bronze Magie", "emoji": "🥉", "degats": 30, "desc": "Magie médiocre"}, {"nom": "Fanfaronnade", "emoji": "💬", "degats": 20, "desc": "Bluff"}, {"nom": "Frappe Cuivrée", "emoji": "🥉", "degats": 25, "desc": "Coup de bronze"}], "faiblesse": "⚡", "resistance": "🥉"},
    "tamaki": {"nom": "Tamaki Kotatsu", "emoji": "🐱", "serie": "Fire Force", "rarete": "Commun", "pv": 78, "attaque": 15, "defense": 12, "image": "https://i.imgur.com/RHyuh47.jpg", "attaques": [{"nom": "Magie du Feu", "emoji": "🔥", "degats": 55, "desc": "Flammes de pompier"}, {"nom": "Abi Geri", "emoji": "🦵", "degats": 50, "desc": "Coup de pied ardent"}, {"nom": "Crimson Fire Brush", "emoji": "🌋", "degats": 60, "desc": "Pinceau de feu"}], "faiblesse": "⚡", "resistance": "🐱"},
    "iris": {"nom": "Iris", "emoji": "⛪", "serie": "Fire Force", "rarete": "Commun", "pv": 60, "attaque": 8, "defense": 9, "image": "https://i.imgur.com/Q0YdrNY.jpg", "attaques": [{"nom": "Magie Feu", "emoji": "🔥", "degats": 55, "desc": "Puissance de feu divine"}, {"nom": "Spear", "emoji": "⚔️", "degats": 60, "desc": "Lance sacrée"}, {"nom": "Divine Protection", "emoji": "✨", "degats": 50, "desc": "Bénédiction divine"}], "faiblesse": "⚡", "resistance": "⛪"},
    "akkum": {"nom": "Aira Shiratori", "emoji": "🌟", "serie": "Dandadan", "rarete": "Commun", "pv": 70, "attaque": 12, "defense": 10, "image": "https://i.imgur.com/xqs2Gev.jpg", "attaques": [{"nom": "Magie Vent", "emoji": "🌬️", "degats": 40, "desc": "Rafale aérienne"}, {"nom": "Grace d'Ange", "emoji": "🕊️", "degats": 35, "desc": "Légèreté aérienne"}, {"nom": "Spirale Aérienne", "emoji": "🌀", "degats": 45, "desc": "Tourbillon d'air"}], "faiblesse": "⚡", "resistance": "🌟"},
    "connie": {"nom": "Connie Springer", "emoji": "⚔️", "serie": "Attack on Titan", "rarete": "Commun", "pv": 72, "attaque": 14, "defense": 11, "image": "https://i.imgur.com/UP38Q1k.jpg", "attaques": [{"nom": "Lames ODM", "emoji": "⚔️", "degats": 50, "desc": "Manœuvre tridimensionnelle"}, {"nom": "Titan Armor", "emoji": "🔱", "degats": 55, "desc": "Titan mâchoire"}, {"nom": "Frappe Acrobatique", "emoji": "💨", "degats": 45, "desc": "Attaque en plein vol"}], "faiblesse": "⚡", "resistance": "⚔️"},
    "loke": {"nom": "Loke", "emoji": "♌", "serie": "Fairy Tail", "rarete": "Commun", "pv": 85, "attaque": 16, "defense": 12, "image": "https://i.imgur.com/JzbTwwD.jpg", "attaques": [{"nom": "Regulus Impact", "emoji": "🦁", "degats": 60, "desc": "Impact du lion"}, {"nom": "Regulus Armor", "emoji": "🌟", "degats": 55, "desc": "Armure stellaire"}, {"nom": "Leo Burst", "emoji": "💛", "degats": 65, "desc": "Explosion solaire"}], "faiblesse": "⚡", "resistance": "♌"},
    "koichi": {"nom": "Koichi Hirose", "emoji": "🐸", "serie": "JoJo", "rarete": "Commun", "pv": 68, "attaque": 12, "defense": 10, "image": "https://i.imgur.com/D8Aadew.jpg", "attaques": [{"nom": "Echoes Act 1", "emoji": "🔊", "degats": 40, "desc": "Sons traumatisants"}, {"nom": "Echoes Act 2", "emoji": "📢", "degats": 50, "desc": "Mots écrits sur corps"}, {"nom": "Echoes Act 3", "emoji": "⚡", "degats": 60, "desc": "Gravité sonique"}], "faiblesse": "⚡", "resistance": "🐸"},
    "tenshinhan": {"nom": "Tenshinhan", "emoji": "👁️", "serie": "Dragon Ball Z", "rarete": "Rare", "pv": 200, "attaque": 45, "defense": 35, "image": "https://i.imgur.com/3YDRHe9.jpg", "attaques": [{"nom": "Kikoho", "emoji": "💥", "degats": 70, "desc": "Canon de ki"}, {"nom": "Neo Tri-Beam", "emoji": "⚡", "degats": 80, "desc": "Néo tri-rayon"}, {"nom": "Volleyball Fist", "emoji": "🏐", "degats": 65, "desc": "Poing volleyball"}], "faiblesse": "⚡", "resistance": "👁️"},
    "piccolo": {"nom": "Piccolo", "emoji": "💚", "serie": "Dragon Ball Z", "rarete": "Rare", "pv": 220, "attaque": 50, "defense": 40, "image": "https://i.imgur.com/V5eQN61.jpg", "attaques": [{"nom": "Makankosappo", "emoji": "💚", "degats": 70, "desc": "Rayon perforateur"}, {"nom": "Hellzone Grenade", "emoji": "💥", "degats": 75, "desc": "Grenades de l'enfer"}, {"nom": "Giant Form", "emoji": "🐉", "degats": 80, "desc": "Forme géante"}], "faiblesse": "⚡", "resistance": "💚"},
    "goten": {"nom": "Goten", "emoji": "👶", "serie": "Dragon Ball Z", "rarete": "Rare", "pv": 210, "attaque": 48, "defense": 38, "image": "https://i.imgur.com/ChVkoHe.jpg", "attaques": [{"nom": "Kamehameha", "emoji": "💥", "degats": 50, "desc": "Rayon d'énergie"}, {"nom": "Masenko", "emoji": "🌟", "degats": 45, "desc": "Rayon démon"}, {"nom": "Super Saiyan", "emoji": "✨", "degats": 55, "desc": "Transformation SS"}], "faiblesse": "⚡", "resistance": "👶"},
    "trunksenfant": {"nom": "Trunks (enfant)", "emoji": "⚔️", "serie": "Dragon Ball Z", "rarete": "Rare", "pv": 215, "attaque": 50, "defense": 40, "image": "https://i.imgur.com/y49vSMv.jpg", "attaques": [{"nom": "Sword Slash", "emoji": "⚔️", "degats": 50, "desc": "Coup d'épée"}, {"nom": "Kamehameha", "emoji": "💥", "degats": 55, "desc": "Kamehameha"}, {"nom": "Super Saiyan", "emoji": "✨", "degats": 60, "desc": "Super Saiyan"}], "faiblesse": "⚡", "resistance": "⚔️"},
    "masterroshi": {"nom": "Master Roshi", "emoji": "🐢", "serie": "Dragon Ball Z", "rarete": "Rare", "pv": 190, "attaque": 44, "defense": 33, "image": "https://i.imgur.com/M6bRwMB.jpg", "attaques": [{"nom": "Kamehameha Original", "emoji": "💥", "degats": 65, "desc": "Kamehameha original"}, {"nom": "MAX Power", "emoji": "💪", "degats": 70, "desc": "Puissance maximale"}, {"nom": "Bankoku Bikkuri Sho", "emoji": "⚡", "degats": 75, "desc": "Frappe foudrayante"}], "faiblesse": "⚡", "resistance": "🐢"},
    "zarbon": {"nom": "Zarbon", "emoji": "💎", "serie": "Dragon Ball Z", "rarete": "Rare", "pv": 230, "attaque": 52, "defense": 42, "image": "https://i.imgur.com/iAiojTr.jpg", "attaques": [{"nom": "Elegant Pursuit", "emoji": "💚", "degats": 55, "desc": "Poursuite élégante"}, {"nom": "Monster Form", "emoji": "👹", "degats": 70, "desc": "Forme monstre"}, {"nom": "Bloody Sauce", "emoji": "💥", "degats": 65, "desc": "Sauce sanglante"}], "faiblesse": "⚡", "resistance": "💎"},
    "dodoria": {"nom": "Dodoria", "emoji": "🌸", "serie": "Dragon Ball Z", "rarete": "Rare", "pv": 225, "attaque": 51, "defense": 41, "image": "https://i.imgur.com/ZQBlxBN.jpg", "attaques": [{"nom": "Finger Beam", "emoji": "🔴", "degats": 55, "desc": "Rayon du doigt"}, {"nom": "Dodoria Headbutt", "emoji": "💥", "degats": 60, "desc": "Coup de tête"}, {"nom": "Maximum Buster", "emoji": "💫", "degats": 65, "desc": "Rafale maximale"}], "faiblesse": "⚡", "resistance": "🌸"},
    "captainginyu": {"nom": "Captain Ginyu", "emoji": "🐸", "serie": "Dragon Ball Z", "rarete": "Rare", "pv": 240, "attaque": 55, "defense": 44, "image": "https://i.imgur.com/gHswpfY.jpg", "attaques": [{"nom": "Body Change", "emoji": "🔄", "degats": 60, "desc": "Échange de corps"}, {"nom": "Milky Cannon", "emoji": "🌟", "degats": 65, "desc": "Canon laiteux"}, {"nom": "Fighting Pose", "emoji": "💪", "degats": 55, "desc": "Pose de combat"}], "faiblesse": "⚡", "resistance": "🐸"},
    "temari": {"nom": "Temari", "emoji": "🌬️", "serie": "Naruto", "rarete": "Rare", "pv": 195, "attaque": 44, "defense": 34, "image": "https://i.imgur.com/0k8xkUw.jpg", "attaques": [{"nom": "Wind Scythe", "emoji": "🌬️", "degats": 60, "desc": "Faucille de vent"}, {"nom": "Cyclone Scythe", "emoji": "🌀", "degats": 70, "desc": "Faucille cyclone"}, {"nom": "Wind Release: Great Task of the Dragon", "emoji": "🐲", "degats": 75, "desc": "Dragon de vent"}], "faiblesse": "⚡", "resistance": "🌬️"},
    "asuma": {"nom": "Asuma Sarutobi", "emoji": "🚬", "serie": "Naruto", "rarete": "Rare", "pv": 205, "attaque": 47, "defense": 37, "image": "https://i.imgur.com/ETWXGX5.jpg", "attaques": [{"nom": "Fuma Shuriken", "emoji": "⭐", "degats": 50, "desc": "Shuriken géant"}, {"nom": "Wind Release: Dust Cloud", "emoji": "💨", "degats": 55, "desc": "Nuage de vent"}, {"nom": "Chakra Blades", "emoji": "⚔️", "degats": 60, "desc": "Lames de chakra"}], "faiblesse": "⚡", "resistance": "🚬"},
    "kurenai": {"nom": "Kurenai Yuhi", "emoji": "🌺", "serie": "Naruto", "rarete": "Rare", "pv": 192, "attaque": 43, "defense": 33, "image": "https://i.imgur.com/Ff8hnaz.jpg", "attaques": [{"nom": "Genjutsu", "emoji": "🌸", "degats": 55, "desc": "Illusion avancée"}, {"nom": "Demonic Illusion", "emoji": "👁️", "degats": 60, "desc": "Illusion démonique"}, {"nom": "Cherry Blossom Impact", "emoji": "🌺", "degats": 65, "desc": "Impact de cerisier"}], "faiblesse": "⚡", "resistance": "🌺"},
    "yamato": {"nom": "Yamato", "emoji": "🪵", "serie": "Naruto", "rarete": "Rare", "pv": 210, "attaque": 49, "defense": 39, "image": "https://i.imgur.com/Cv9YpcR.jpg", "attaques": [{"nom": "Inu Inu no Mi Mythical Zoan", "emoji": "🐉", "degats": 75, "desc": "Forme Ōkuninushi"}, {"nom": "Thunderbolt", "emoji": "⚡", "degats": 80, "desc": "Coup de foudre"}, {"nom": "Ice Dragon's Breath", "emoji": "❄️", "degats": 70, "desc": "Souffle de glace"}], "faiblesse": "⚡", "resistance": "🪵"},
    "deidara": {"nom": "Deidara", "emoji": "💣", "serie": "Naruto", "rarete": "Rare", "pv": 200, "attaque": 48, "defense": 35, "image": "https://i.imgur.com/KpYxLSW.jpg", "attaques": [{"nom": "C1 - Araignée", "emoji": "💣", "degats": 60, "desc": "Petites bombes"}, {"nom": "C3 - Grande Bombe", "emoji": "💥", "degats": 80, "desc": "Bombe géante"}, {"nom": "C0 - Nuke", "emoji": "☢️", "degats": 95, "desc": "Bombe nucléaire"}], "faiblesse": "⚡", "resistance": "💣"},
    "sasori": {"nom": "Sasori", "emoji": "🪆", "serie": "Naruto", "rarete": "Rare", "pv": 198, "attaque": 47, "defense": 36, "image": "https://i.imgur.com/PZxzyLv.jpg", "attaques": [{"nom": "Red Secret Technique", "emoji": "🔴", "degats": 75, "desc": "Technique secrète rouge"}, {"nom": "Hundred Puppet Match", "emoji": "💀", "degats": 80, "desc": "Cent marionnettes"}, {"nom": "Hiruko", "emoji": "🦂", "degats": 70, "desc": "Marionnette scorpion"}], "faiblesse": "⚡", "resistance": "🪆"},
    "kabuto": {"nom": "Kabuto Yakushi", "emoji": "🐍", "serie": "Naruto", "rarete": "Rare", "pv": 205, "attaque": 48, "defense": 37, "image": "https://i.imgur.com/LaVdS18.jpg", "attaques": [{"nom": "Sage Jutsu", "emoji": "🐍", "degats": 70, "desc": "Mode sage"}, {"nom": "Edo Tensei", "emoji": "☠️", "degats": 75, "desc": "Réincarnation immortelle"}, {"nom": "Flesh Slithering", "emoji": "🧬", "degats": 65, "desc": "Manipulation cellulaire"}], "faiblesse": "⚡", "resistance": "🐍"},
    "smoker": {"nom": "Smoker", "emoji": "🌫️", "serie": "One Piece", "rarete": "Rare", "pv": 215, "attaque": 50, "defense": 40, "image": "https://i.imgur.com/7i5i7h3.jpg", "attaques": [{"nom": "White Out", "emoji": "💨", "degats": 55, "desc": "Fumée étouffante"}, {"nom": "Smoke Launcher", "emoji": "🌫️", "degats": 50, "desc": "Lance-fumée"}, {"nom": "Jitte Fumée", "emoji": "⚡", "degats": 60, "desc": "Seastone + fumée"}], "faiblesse": "⚡", "resistance": "🌫️"},
    "bellamy": {"nom": "Bellamy", "emoji": "🦁", "serie": "One Piece", "rarete": "Rare", "pv": 205, "attaque": 48, "defense": 38, "image": "https://i.imgur.com/TADQZSS.jpg", "attaques": [{"nom": "Spring Hopper", "emoji": "🦘", "degats": 55, "desc": "Saut de ressort"}, {"nom": "Spring Death Knock", "emoji": "💥", "degats": 65, "desc": "Coup de ressort fatal"}, {"nom": "Bane Bane", "emoji": "⚙️", "degats": 50, "desc": "Bonds mortels"}], "faiblesse": "⚡", "resistance": "🦁"},
    "missvalentine": {"nom": "Miss Valentine", "emoji": "💛", "serie": "One Piece", "rarete": "Rare", "pv": 190, "attaque": 44, "defense": 33, "image": "https://i.imgur.com/x2evVSX.jpg", "attaques": [{"nom": "Kilo Kilo 10k", "emoji": "💎", "degats": 45, "desc": "Poids 10000kg"}, {"nom": "Kilo Kilo 1", "emoji": "🪶", "degats": 40, "desc": "Légèreté absolue"}, {"nom": "Impact Masse", "emoji": "💥", "degats": 50, "desc": "Écrasement gravitaire"}], "faiblesse": "⚡", "resistance": "💛"},
    "mr5": {"nom": "Mr 5", "emoji": "💣", "serie": "One Piece", "rarete": "Rare", "pv": 195, "attaque": 45, "defense": 35, "image": "https://i.imgur.com/XGHd5fn.jpg", "attaques": [{"nom": "Bomb Bomb", "emoji": "💣", "degats": 55, "desc": "Explosion corporelle"}, {"nom": "Mucus Bomb", "emoji": "🟢", "degats": 50, "desc": "Bombe de mucus"}, {"nom": "Nose Fancy Cannon", "emoji": "👃", "degats": 60, "desc": "Canon nasal"}], "faiblesse": "⚡", "resistance": "💣"},
    "tashigi": {"nom": "Tashigi", "emoji": "⚔️", "serie": "One Piece", "rarete": "Rare", "pv": 188, "attaque": 43, "defense": 33, "image": "https://i.imgur.com/iZLo8au.jpg", "attaques": [{"nom": "Shigure", "emoji": "⚔️", "degats": 50, "desc": "Lame trempée d'eau"}, {"nom": "Haki d'Armement", "emoji": "🟤", "degats": 45, "desc": "Lame endurcit"}, {"nom": "Rokushiki Partiel", "emoji": "💨", "degats": 40, "desc": "Techniques marines"}], "faiblesse": "⚡", "resistance": "⚔️"},
    "crocobase": {"nom": "Crocodile", "emoji": "🐊", "serie": "One Piece", "rarete": "Rare", "pv": 220, "attaque": 50, "defense": 40, "image": "https://i.imgur.com/lQsrDPU.jpg", "attaques": [{"nom": "Ground Secant", "emoji": "🌪️", "degats": 65, "desc": "Mur de sable tranchant"}, {"nom": "Desert Spada", "emoji": "⚔️", "degats": 70, "desc": "Lame de désert"}, {"nom": "Desert Grande Espada", "emoji": "☠️", "degats": 75, "desc": "Épée géante de sable"}], "faiblesse": "⚡", "resistance": "🐊"},
    "tokoyami": {"nom": "Tokoyami Fumikage", "emoji": "🐦", "serie": "My Hero Academia", "rarete": "Rare", "pv": 200, "attaque": 46, "defense": 36, "image": "https://i.imgur.com/XGQO6Ao.jpg", "attaques": [{"nom": "Dark Shadow", "emoji": "🖤", "degats": 55, "desc": "Ombre combattante"}, {"nom": "Black Abyss", "emoji": "🌑", "degats": 65, "desc": "Abîme obscur"}, {"nom": "Ragnarök", "emoji": "☠️", "degats": 70, "desc": "Déchaînement ténébreux"}], "faiblesse": "⚡", "resistance": "🐦"},
    "uraraka": {"nom": "Uraraka Ochaco", "emoji": "🌸", "serie": "My Hero Academia", "rarete": "Rare", "pv": 185, "attaque": 42, "defense": 32, "image": "https://i.imgur.com/ih0tKWb.jpg", "attaques": [{"nom": "Zero Gravity", "emoji": "🌸", "degats": 50, "desc": "Apesanteur"}, {"nom": "Meteor Shower", "emoji": "☄️", "degats": 65, "desc": "Pluie de météores"}, {"nom": "Comet Home Run", "emoji": "🌟", "degats": 60, "desc": "Frappe cosmique"}], "faiblesse": "⚡", "resistance": "🌸"},
    "iida": {"nom": "Iida Tenya", "emoji": "🏃", "serie": "My Hero Academia", "rarete": "Rare", "pv": 195, "attaque": 44, "defense": 36, "image": "https://i.imgur.com/KHUHYgm.jpg", "attaques": [{"nom": "Recipro Burst", "emoji": "💨", "degats": 55, "desc": "Turbo-propulsion"}, {"nom": "Recipro Extend", "emoji": "⚡", "degats": 65, "desc": "Extension maximale"}, {"nom": "Recipro Turbo", "emoji": "🔥", "degats": 70, "desc": "Ultime accélération"}], "faiblesse": "⚡", "resistance": "🏃"},
    "yaoyorozu": {"nom": "Yaoyorozu Momo", "emoji": "⚙️", "serie": "My Hero Academia", "rarete": "Rare", "pv": 190, "attaque": 43, "defense": 34, "image": "https://i.imgur.com/79pubHU.jpg", "attaques": [{"nom": "Création", "emoji": "✨", "degats": 40, "desc": "Crée n'importe quoi"}, {"nom": "Canon anti-émeute", "emoji": "💥", "degats": 55, "desc": "Arme créée"}, {"nom": "Gilet isolant", "emoji": "🛡️", "degats": 35, "desc": "Défense créée"}], "faiblesse": "⚡", "resistance": "⚙️"},
    "kaminari": {"nom": "Kaminari Denki", "emoji": "⚡", "serie": "My Hero Academia", "rarete": "Rare", "pv": 182, "attaque": 42, "defense": 31, "image": "https://i.imgur.com/uRwc6Xb.jpg", "attaques": [{"nom": "Indiscriminate Shock", "emoji": "⚡", "degats": 55, "desc": "Décharge électrique"}, {"nom": "Watt-kun", "emoji": "🟡", "degats": 50, "desc": "Décharge ciblée"}, {"nom": "Thunderclap Flash", "emoji": "⚡", "degats": 65, "desc": "Éclair concentré"}], "faiblesse": "⚡", "resistance": "⚡"},
    "vlad": {"nom": "Vlad King", "emoji": "🩸", "serie": "My Hero Academia", "rarete": "Rare", "pv": 210, "attaque": 48, "defense": 38, "image": "https://i.imgur.com/u7oL7Z8.jpg", "attaques": [{"nom": "Blood Control", "emoji": "🩸", "degats": 55, "desc": "Sang solidifié"}, {"nom": "Blood Shield", "emoji": "🛡️", "degats": 50, "desc": "Bouclier sanguin"}, {"nom": "Blood Whip", "emoji": "🩸", "degats": 60, "desc": "Fouet de sang"}], "faiblesse": "⚡", "resistance": "🩸"},
    "sasha": {"nom": "Sasha Blouse", "emoji": "🍖", "serie": "Attack on Titan", "rarete": "Rare", "pv": 188, "attaque": 43, "defense": 32, "image": "https://i.imgur.com/5JwHT7z.jpg", "attaques": [{"nom": "Flèche Précise", "emoji": "🏹", "degats": 45, "desc": "Tir de précision"}, {"nom": "Couteau de Chasse", "emoji": "🗡️", "degats": 40, "desc": "Lame rapide"}, {"nom": "Sens du Chasseur", "emoji": "👁️", "degats": 35, "desc": "Instinct sauvage"}], "faiblesse": "⚡", "resistance": "🍖"},
    "jean": {"nom": "Jean Kirstein", "emoji": "🐴", "serie": "Attack on Titan", "rarete": "Rare", "pv": 192, "attaque": 44, "defense": 33, "image": "https://i.imgur.com/cldsnpV.jpg", "attaques": [{"nom": "Lames d'Acier", "emoji": "⚔️", "degats": 50, "desc": "Attaque ODM"}, {"nom": "Contre-Attaque", "emoji": "🔄", "degats": 45, "desc": "Parade et riposte"}, {"nom": "Moral d'Acier", "emoji": "💪", "degats": 40, "desc": "Détermination"}], "faiblesse": "⚡", "resistance": "🐴"},
    "historia": {"nom": "Historia Reiss", "emoji": "👑", "serie": "Attack on Titan", "rarete": "Rare", "pv": 180, "attaque": 40, "defense": 31, "image": "https://i.imgur.com/JzbTwwD.jpg", "attaques": [{"nom": "Épée de Roi", "emoji": "👑", "degats": 50, "desc": "Lame royale"}, {"nom": "Determination", "emoji": "💪", "degats": 45, "desc": "Volonté d'acier"}, {"nom": "Smash", "emoji": "⚔️", "degats": 55, "desc": "Frappe royale"}], "faiblesse": "⚡", "resistance": "👑"},
    "ymir": {"nom": "Ymir", "emoji": "🦶", "serie": "Attack on Titan", "rarete": "Rare", "pv": 200, "attaque": 46, "defense": 35, "image": "https://i.imgur.com/JzbTwwD.jpg", "attaques": [{"nom": "Titan Mâchoire", "emoji": "🦷", "degats": 60, "desc": "Morsure titanesque"}, {"nom": "Griffes Titan", "emoji": "🐾", "degats": 55, "desc": "Griffes acérées"}, {"nom": "Transformation Rapide", "emoji": "⚡", "degats": 65, "desc": "Titan éclair"}], "faiblesse": "⚡", "resistance": "🦶"},
    "petra": {"nom": "Petra Ral", "emoji": "🌼", "serie": "Attack on Titan", "rarete": "Rare", "pv": 185, "attaque": 43, "defense": 33, "image": "https://i.imgur.com/JzbTwwD.jpg", "attaques": [{"nom": "Lames ODM", "emoji": "⚔️", "degats": 50, "desc": "Attaque précise"}, {"nom": "Frappe Combinée", "emoji": "🤝", "degats": 45, "desc": "Combo d'équipe"}, {"nom": "Contre Rapide", "emoji": "💨", "degats": 55, "desc": "Riposte éclair"}], "faiblesse": "⚡", "resistance": "🌼"},
    "floch": {"nom": "Floch Forster", "emoji": "🔫", "serie": "Attack on Titan", "rarete": "Rare", "pv": 190, "attaque": 44, "defense": 33, "image": "https://i.imgur.com/JzbTwwD.jpg", "attaques": [{"nom": "Lames ODM", "emoji": "⚔️", "degats": 45, "desc": "Attaque volante"}, {"nom": "Tir Furtif", "emoji": "🔫", "degats": 50, "desc": "Coup de feu"}, {"nom": "Fanatic Strike", "emoji": "😤", "degats": 55, "desc": "Frappe fanatique"}], "faiblesse": "⚡", "resistance": "🔫"},
    "renji": {"nom": "Renji Abarai", "emoji": "🐉", "serie": "Bleach", "rarete": "Rare", "pv": 205, "attaque": 48, "defense": 37, "image": "https://i.imgur.com/JzbTwwD.jpg", "attaques": [{"nom": "Zabimaru", "emoji": "🐍", "degats": 55, "desc": "Serpent d'os"}, {"nom": "Bankai Hihio Zabimaru", "emoji": "💀", "degats": 70, "desc": "Squelette de serpent"}, {"nom": "Hikotsu Taiho", "emoji": "💥", "degats": 65, "desc": "Canon osseux"}], "faiblesse": "⚡", "resistance": "🐉"},
    "ikkaku": {"nom": "Ikkaku Madarame", "emoji": "🔱", "serie": "Bleach", "rarete": "Rare", "pv": 200, "attaque": 47, "defense": 36, "image": "https://i.imgur.com/JzbTwwD.jpg", "attaques": [{"nom": "Hōzukimaru", "emoji": "⚔️", "degats": 50, "desc": "Lance divisée"}, {"nom": "Bankai Ryūmon Hōzukimaru", "emoji": "🐉", "degats": 70, "desc": "Dragon de lance"}, {"nom": "San no Mai", "emoji": "🌸", "degats": 60, "desc": "Troisième danse"}], "faiblesse": "⚡", "resistance": "🔱"},
    "rangiku": {"nom": "Rangiku Matsumoto", "emoji": "🍷", "serie": "Bleach", "rarete": "Rare", "pv": 198, "attaque": 46, "defense": 35, "image": "https://i.imgur.com/JzbTwwD.jpg", "attaques": [{"nom": "Haineko", "emoji": "🌸", "degats": 50, "desc": "Cendres de chat"}, {"nom": "Cendres Tranchantes", "emoji": "⚡", "degats": 55, "desc": "Lames de cendres"}, {"nom": "Tempête de Cendres", "emoji": "🌪️", "degats": 60, "desc": "Tourbillon de lames"}], "faiblesse": "⚡", "resistance": "🍷"},
    "izuru": {"nom": "Izuru Kira", "emoji": "🌪️", "serie": "Bleach", "rarete": "Rare", "pv": 193, "attaque": 45, "defense": 34, "image": "https://i.imgur.com/JzbTwwD.jpg", "attaques": [{"nom": "Wabisuke", "emoji": "⚖️", "degats": 55, "desc": "Double le poids"}, {"nom": "Poids Infini", "emoji": "🏋️", "degats": 65, "desc": "Écrasement gravitaire"}, {"nom": "Cage de Culpabilité", "emoji": "🔒", "degats": 50, "desc": "Emprisonnement"}], "faiblesse": "⚡", "resistance": "🌪️"},
    "chad": {"nom": "Yasutora Chad", "emoji": "💪", "serie": "Bleach", "rarete": "Rare", "pv": 210, "attaque": 49, "defense": 38, "image": "https://i.imgur.com/JzbTwwD.jpg", "attaques": [{"nom": "Brazo Derecho del Gigante", "emoji": "🦾", "degats": 60, "desc": "Bras droit géant"}, {"nom": "Brazo Izquierda del Diablo", "emoji": "😈", "degats": 70, "desc": "Bras gauche démoniaque"}, {"nom": "El Directo", "emoji": "💥", "degats": 65, "desc": "Frappe directe"}], "faiblesse": "⚡", "resistance": "💪"},
    "uryu": {"nom": "Uryu Ishida", "emoji": "🏹", "serie": "Bleach", "rarete": "Rare", "pv": 200, "attaque": 47, "defense": 36, "image": "https://i.imgur.com/eg1x8Zi.jpg", "attaques": [{"nom": "Licht Regen", "emoji": "🏹", "degats": 55, "desc": "Pluie de flèches"}, {"nom": "Seele Schneider", "emoji": "⚔️", "degats": 60, "desc": "Lame spirituelle"}, {"nom": "Quincy Final Form", "emoji": "✨", "degats": 70, "desc": "Pouvoir ultime"}], "faiblesse": "⚡", "resistance": "🏹"},
    "leorio": {"nom": "Leorio Paradinight", "emoji": "🩺", "serie": "HunterxHunter", "rarete": "Rare", "pv": 188, "attaque": 43, "defense": 32, "image": "https://i.imgur.com/ZeRU0Pg.jpg", "attaques": [{"nom": "Nen Médical", "emoji": "💉", "degats": 40, "desc": "Soin offensif"}, {"nom": "Télékinésie Nen", "emoji": "🔵", "degats": 45, "desc": "Projection de poing"}, {"nom": "Poing Nen", "emoji": "👊", "degats": 50, "desc": "Frappe spirituelle"}], "faiblesse": "⚡", "resistance": "🩺"},
    "illumi": {"nom": "Illumi Zoldyck", "emoji": "📌", "serie": "HunterxHunter", "rarete": "Rare", "pv": 215, "attaque": 50, "defense": 39, "image": "https://i.imgur.com/NeFo0aX.jpg", "attaques": [{"nom": "Nen Manipulation", "emoji": "🪡", "degats": 60, "desc": "Contrôle par aiguilles"}, {"nom": "Aiguilles Mortelles", "emoji": "💉", "degats": 65, "desc": "Paralysie fatale"}, {"nom": "Armée Manipulée", "emoji": "👥", "degats": 70, "desc": "Horde contrôlée"}], "faiblesse": "⚡", "resistance": "📌"},
    "juvia": {"nom": "Juvia Lockser", "emoji": "💧", "serie": "Fairy Tail", "rarete": "Rare", "pv": 200, "attaque": 46, "defense": 36, "image": "https://i.imgur.com/6jjacAq.jpg", "attaques": [{"nom": "Water Lock", "emoji": "💧", "degats": 60, "desc": "Prison d'eau"}, {"nom": "Sierra", "emoji": "🌊", "degats": 65, "desc": "Lames d'eau"}, {"nom": "Water Nebula", "emoji": "🌀", "degats": 70, "desc": "Nébuleuse liquide"}], "faiblesse": "⚡", "resistance": "💧"},
    "gajeel": {"nom": "Gajeel Redfox", "emoji": "⛓️", "serie": "Fairy Tail", "rarete": "Rare", "pv": 210, "attaque": 49, "defense": 38, "image": "https://i.imgur.com/Bij0me3.jpg", "attaques": [{"nom": "Iron Club", "emoji": "⚙️", "degats": 60, "desc": "Matraque de fer"}, {"nom": "Iron Dragon's Roar", "emoji": "🔩", "degats": 70, "desc": "Rugissement du dragon"}, {"nom": "Black Iron Dragon", "emoji": "🖤", "degats": 75, "desc": "Dragon de fer noir"}], "faiblesse": "⚡", "resistance": "⛓️"},
    "wendy": {"nom": "Wendy Marvell", "emoji": "🌀", "serie": "Fairy Tail", "rarete": "Rare", "pv": 185, "attaque": 42, "defense": 33, "image": "https://i.imgur.com/lCguz5s.jpg", "attaques": [{"nom": "Sky Dragon's Roar", "emoji": "💨", "degats": 60, "desc": "Rugissement dragon céleste"}, {"nom": "Shredding Wedding", "emoji": "🌀", "degats": 65, "desc": "Mariage déchirant"}, {"nom": "Dragonification", "emoji": "🐉", "degats": 75, "desc": "Transformation dragon"}], "faiblesse": "⚡", "resistance": "🌀"},
    "joseph": {"nom": "Joseph Joestar", "emoji": "🧤", "serie": "JoJo", "rarete": "Rare", "pv": 200, "attaque": 47, "defense": 36, "image": "https://i.imgur.com/8PlNFLr.jpg", "attaques": [{"nom": "Ripple Overdrive", "emoji": "🌊", "degats": 60, "desc": "Hamon overdrive"}, {"nom": "Hermit Purple", "emoji": "🍇", "degats": 65, "desc": "Violine hermite"}, {"nom": "Caesar's Technique", "emoji": "✨", "degats": 70, "desc": "Héritage de César"}], "faiblesse": "⚡", "resistance": "🧤"},
    "caesar": {"nom": "Caesar Zeppeli", "emoji": "🫧", "serie": "JoJo", "rarete": "Rare", "pv": 195, "attaque": 45, "defense": 35, "image": "https://i.imgur.com/72ILubC.jpg", "attaques": [{"nom": "Onde Hamon", "emoji": "🌊", "degats": 50, "desc": "Vague Hamon"}, {"nom": "Hamon Technique", "emoji": "✨", "degats": 55, "desc": "Technique Hamon avancée"}, {"nom": "Zoom Punch", "emoji": "👊", "degats": 60, "desc": "Poing allongé Hamon"}], "faiblesse": "⚡", "resistance": "🫧"},
    "okuyasu": {"nom": "Okuyasu Nijimura", "emoji": "✋", "serie": "JoJo", "rarete": "Rare", "pv": 200, "attaque": 47, "defense": 36, "image": "https://i.imgur.com/JzbTwwD.jpg", "attaques": [{"nom": "The Hand", "emoji": "✋", "degats": 65, "desc": "Efface l'espace"}, {"nom": "Space Erasure", "emoji": "🌑", "degats": 70, "desc": "Suppression spatiale"}, {"nom": "Baka Punch", "emoji": "👊", "degats": 55, "desc": "Coup brut"}], "faiblesse": "⚡", "resistance": "✋"},
    "chifuyu": {"nom": "Chifuyu Matsuno", "emoji": "🐱", "serie": "Tokyo Revengers", "rarete": "Rare", "pv": 192, "attaque": 44, "defense": 33, "image": "https://i.imgur.com/JzbTwwD.jpg", "attaques": [{"nom": "Lame Rapide", "emoji": "⚔️", "degats": 55, "desc": "Frappe de lame"}, {"nom": "Poing d'Acier", "emoji": "👊", "degats": 50, "desc": "Coup de poing"}, {"nom": "Vite Comme l'Éclair", "emoji": "💨", "degats": 60, "desc": "Vitesse de combat"}], "faiblesse": "⚡", "resistance": "🐱"},
    "draken": {"nom": "Ken Ryuguji (Draken)", "emoji": "🐉", "serie": "Tokyo Revengers", "rarete": "Rare", "pv": 215, "attaque": 50, "defense": 40, "image": "https://i.imgur.com/sdfXTHr.jpg", "attaques": [{"nom": "Dragon Kick", "emoji": "🐉", "degats": 65, "desc": "Coup de dragon"}, {"nom": "Tatouage Dragon", "emoji": "🐲", "degats": 70, "desc": "Frappe tatoueuse"}, {"nom": "Biker Strike", "emoji": "🏍️", "degats": 60, "desc": "Attaque de motard"}], "faiblesse": "⚡", "resistance": "🐉"},
    "hinata_hq": {"nom": "Shoyo Hinata", "emoji": "🏐", "serie": "Haikyuu", "rarete": "Rare", "pv": 170, "attaque": 40, "defense": 28, "image": "https://i.imgur.com/Zq4DX3F.jpg", "attaques": [{"nom": "Magie Feu", "emoji": "🔥", "degats": 55, "desc": "Flammes Adolla"}, {"nom": "Ignition Ability", "emoji": "🌸", "degats": 60, "desc": "Aptitude d'ignition"}, {"nom": "Fire Tornado", "emoji": "🌪️", "degats": 65, "desc": "Tornade de feu"}], "faiblesse": "⚡", "resistance": "🏐"},
    "kageyama": {"nom": "Tobio Kageyama", "emoji": "🏐", "serie": "Haikyuu", "rarete": "Rare", "pv": 175, "attaque": 42, "defense": 29, "image": "https://i.imgur.com/JzbTwwD.jpg", "attaques": [{"nom": "Smash Set", "emoji": "🏐", "degats": 45, "desc": "Combinaison parfaite"}, {"nom": "Imperial Eyes", "emoji": "👁️", "degats": 50, "desc": "Regard royal"}, {"nom": "Speed Set", "emoji": "💨", "degats": 40, "desc": "Passe ultra-rapide"}], "faiblesse": "⚡", "resistance": "🏐"},
    "arthurf": {"nom": "Arthur Boyle", "emoji": "⚔️", "serie": "Fire Force", "rarete": "Rare", "pv": 205, "attaque": 48, "defense": 36, "image": "https://i.imgur.com/zJikG6Q.jpg", "attaques": [{"nom": "Magie Feu Royale", "emoji": "👑", "degats": 55, "desc": "Flammes de prince"}, {"nom": "Royal Slash", "emoji": "⚔️", "degats": 60, "desc": "Lame royale enflammée"}, {"nom": "Sovereign Inferno", "emoji": "🌋", "degats": 65, "desc": "Brasier souverain"}], "faiblesse": "⚡", "resistance": "⚔️"},
    "finn": {"nom": "Finn Ames", "emoji": "🌟", "serie": "Mashle", "rarete": "Rare", "pv": 185, "attaque": 43, "defense": 33, "image": "https://i.imgur.com/JzbTwwD.jpg", "attaques": [{"nom": "Water Magic", "emoji": "💧", "degats": 40, "desc": "Magie aquatique"}, {"nom": "Ice Strike", "emoji": "❄️", "degats": 45, "desc": "Frappe de glace"}, {"nom": "Aqua Blast", "emoji": "🌊", "degats": 50, "desc": "Jet d'eau"}], "faiblesse": "⚡", "resistance": "🌟"},
    "dotmashle": {"nom": "Dot Barrett", "emoji": "💢", "serie": "Mashle", "rarete": "Rare", "pv": 200, "attaque": 47, "defense": 36, "image": "https://i.imgur.com/JzbTwwD.jpg", "attaques": [{"nom": "Heavy Artillery", "emoji": "💥", "degats": 60, "desc": "Artillerie lourde"}, {"nom": "Machine Gun", "emoji": "🔫", "degats": 55, "desc": "Rafale"}, {"nom": "Explosion Fist", "emoji": "👊", "degats": 65, "desc": "Poing explosif"}], "faiblesse": "⚡", "resistance": "💢"},
    "magna": {"nom": "Magna Swing", "emoji": "🔥", "serie": "Black Clover", "rarete": "Rare", "pv": 192, "attaque": 44, "defense": 33, "image": "https://i.imgur.com/qH2W7pZ.jpg", "attaques": [{"nom": "Magie du Feu", "emoji": "🔥", "degats": 45, "desc": "Flammes magiques"}, {"nom": "Exploding Fireball", "emoji": "💥", "degats": 50, "desc": "Boule de feu"}, {"nom": "Flame Magic", "emoji": "🌋", "degats": 55, "desc": "Magie de flamme"}], "faiblesse": "⚡", "resistance": "🔥"},
    "gauche": {"nom": "Gauche Adlai", "emoji": "🪞", "serie": "Black Clover", "rarete": "Rare", "pv": 195, "attaque": 45, "defense": 34, "image": "https://i.imgur.com/hMWHQ4G.jpg", "attaques": [{"nom": "Magie des Miroirs", "emoji": "🪞", "degats": 50, "desc": "Reflet dupliqué"}, {"nom": "Mirror Magic", "emoji": "✨", "degats": 55, "desc": "Clone de miroir"}, {"nom": "Reflet Attaque", "emoji": "💫", "degats": 60, "desc": "Attaque réfléchie"}], "faiblesse": "⚡", "resistance": "🪞"},
    "raphtalia": {"nom": "Raphtalia", "emoji": "🦊", "serie": "The Rising of the Shield Hero", "rarete": "Rare", "pv": 200, "attaque": 46, "defense": 35, "image": "https://i.imgur.com/slo211S.jpg", "attaques": [{"nom": "Épée du Raccoon", "emoji": "⚔️", "degats": 50, "desc": "Lame de raton laveur"}, {"nom": "Spiral Strike", "emoji": "🌀", "degats": 55, "desc": "Frappe en spirale"}, {"nom": "Blood Screech", "emoji": "🩸", "degats": 45, "desc": "Cri de sang"}], "faiblesse": "⚡", "resistance": "🦊"},
    "judeau": {"nom": "Judeau", "emoji": "🗡️", "serie": "Berserk", "rarete": "Rare", "pv": 185, "attaque": 43, "defense": 32, "image": "https://i.imgur.com/HPPvOXA.jpg", "attaques": [{"nom": "Couteaux de Lancer", "emoji": "🗡️", "degats": 40, "desc": "Précision mortelle"}, {"nom": "Jugement", "emoji": "⚔️", "degats": 45, "desc": "Lame du destin"}, {"nom": "Frappe Berserk", "emoji": "💀", "degats": 50, "desc": "Attaque sombre"}], "faiblesse": "⚡", "resistance": "🗡️"},
    "android17": {"nom": "Android 17", "emoji": "☯️", "serie": "Dragon Ball Z", "rarete": "Épique", "pv": 420, "attaque": 95, "defense": 78, "image": "https://i.imgur.com/5YdjhKz.jpg", "attaques": [{"nom": "Barrier", "emoji": "🔵", "degats": 55, "desc": "Barrière d'énergie"}, {"nom": "Accel Dance", "emoji": "⚡", "degats": 65, "desc": "Combo avec C18"}, {"nom": "Power Blitz", "emoji": "💥", "degats": 70, "desc": "Rayon d'énergie"}], "faiblesse": "⚡", "resistance": "☯️"},
    "android18": {"nom": "Android 18", "emoji": "☯️", "serie": "Dragon Ball Z", "rarete": "Épique", "pv": 415, "attaque": 93, "defense": 76, "image": "https://i.imgur.com/9sO1NWf.jpg", "attaques": [{"nom": "Photon Flash", "emoji": "💛", "degats": 65, "desc": "Rayon lumineux"}, {"nom": "Accel Dance", "emoji": "⚡", "degats": 60, "desc": "Combo avec C17"}, {"nom": "High Tension", "emoji": "💥", "degats": 70, "desc": "Décharge maximale"}], "faiblesse": "⚡", "resistance": "☯️"},
    "cellparfait": {"nom": "Cell (Parfait)", "emoji": "💎", "serie": "Dragon Ball Z", "rarete": "Épique", "pv": 440, "attaque": 100, "defense": 82, "image": "https://i.imgur.com/C0yiDwl.jpg", "attaques": [{"nom": "Solar Kamehameha", "emoji": "☀️", "degats": 85, "desc": "Kamehameha solaire"}, {"nom": "Galick Cannon", "emoji": "💥", "degats": 80, "desc": "Canon galick"}, {"nom": "Full Power Energy Wave", "emoji": "🟢", "degats": 90, "desc": "Onde totale"}], "faiblesse": "⚡", "resistance": "💎"},
    "gotenks": {"nom": "Gotenks", "emoji": "👊", "serie": "Dragon Ball Z", "rarete": "Épique", "pv": 435, "attaque": 98, "defense": 79, "image": "https://i.imgur.com/sENwCrn.jpg", "attaques": [{"nom": "Galactic Donut", "emoji": "🍩", "degats": 65, "desc": "Anneau d'énergie"}, {"nom": "Super Ghost Kamikaze", "emoji": "👻", "degats": 75, "desc": "Fantômes kamikazes"}, {"nom": "Continuous Die Die Missiles", "emoji": "💥", "degats": 80, "desc": "Missiles continus"}], "faiblesse": "⚡", "resistance": "👊"},
    "cooler": {"nom": "Cooler", "emoji": "❄️", "serie": "Dragon Ball Z", "rarete": "Épique", "pv": 450, "attaque": 102, "defense": 84, "image": "https://i.imgur.com/kTiv7z4.jpg", "attaques": [{"nom": "Death Beam", "emoji": "💜", "degats": 70, "desc": "Rayon de mort"}, {"nom": "Death Flash", "emoji": "💥", "degats": 75, "desc": "Éclair fatal"}, {"nom": "Supernova", "emoji": "🌑", "degats": 85, "desc": "Méga nova"}], "faiblesse": "⚡", "resistance": "❄️"},
    "orochimaru": {"nom": "Orochimaru", "emoji": "🐍", "serie": "Naruto", "rarete": "Épique", "pv": 415, "attaque": 93, "defense": 76, "image": "https://i.imgur.com/912UszF.jpg", "attaques": [{"nom": "Kusanagi Sword", "emoji": "⚔️", "degats": 70, "desc": "Épée Kusanagi"}, {"nom": "Dead Soul Jutsu", "emoji": "☠️", "degats": 75, "desc": "Jutsu des âmes mortes"}, {"nom": "Eight Branches", "emoji": "🐍", "degats": 80, "desc": "Huit branches"}], "faiblesse": "⚡", "resistance": "🐍"},
    "konan": {"nom": "Konan", "emoji": "📜", "serie": "Naruto", "rarete": "Épique", "pv": 400, "attaque": 90, "defense": 74, "image": "https://i.imgur.com/HzC900u.jpg", "attaques": [{"nom": "Paper Shuriken", "emoji": "📄", "degats": 60, "desc": "Shuriken de papier"}, {"nom": "Paper Drizzle", "emoji": "🌧️", "degats": 70, "desc": "Pluie de papier"}, {"nom": "Six Hundred Billion Paper Bombs", "emoji": "💥", "degats": 90, "desc": "Bombes de papier"}], "faiblesse": "⚡", "resistance": "📜"},
    "katakuri": {"nom": "Katakuri", "emoji": "🍩", "serie": "One Piece", "rarete": "Épique", "pv": 445, "attaque": 101, "defense": 83, "image": "https://i.imgur.com/vfzIr7R.jpg", "attaques": [{"nom": "Mochi Mochi", "emoji": "🍡", "degats": 70, "desc": "Corps de mochi"}, {"nom": "Zan Giri Mochi", "emoji": "💥", "degats": 80, "desc": "Coupe mochi"}, {"nom": "Red Mochi Armor", "emoji": "🔴", "degats": 75, "desc": "Armure de mochi"}], "faiblesse": "⚡", "resistance": "🍩"},
    "roblucci": {"nom": "Rob Lucci", "emoji": "🐆", "serie": "One Piece", "rarete": "Épique", "pv": 435, "attaque": 98, "defense": 80, "image": "https://i.imgur.com/OqBlCGc.jpg", "attaques": [{"nom": "Rokuogan", "emoji": "💥", "degats": 75, "desc": "Six King Gun"}, {"nom": "Soru Rokuogan", "emoji": "⚡", "degats": 80, "desc": "Soru + Six King"}, {"nom": "Leopard Form", "emoji": "🐆", "degats": 70, "desc": "Forme léopard"}], "faiblesse": "⚡", "resistance": "🐆"},
    "enel": {"nom": "Enel", "emoji": "⚡", "serie": "One Piece", "rarete": "Épique", "pv": 420, "attaque": 95, "defense": 78, "image": "https://i.imgur.com/yMIM8D5.jpg", "attaques": [{"nom": "El Thor", "emoji": "⚡", "degats": 75, "desc": "Éclair divin"}, {"nom": "Kari", "emoji": "🌩️", "degats": 80, "desc": "Micro onde"}, {"nom": "Amaru", "emoji": "💛", "degats": 85, "desc": "Forme divine"}], "faiblesse": "⚡", "resistance": "⚡"},
    "doflamingo": {"nom": "Doflamingo", "emoji": "🕊️", "serie": "One Piece", "rarete": "Épique", "pv": 440, "attaque": 100, "defense": 82, "image": "https://i.imgur.com/PPFbKzA.jpg", "attaques": [{"nom": "Parasite", "emoji": "🕹️", "degats": 70, "desc": "Contrôle des corps"}, {"nom": "Birdcage", "emoji": "🔴", "degats": 80, "desc": "Cage d'oiseaux"}, {"nom": "God Thread", "emoji": "🕸️", "degats": 85, "desc": "Fils divins"}], "faiblesse": "⚡", "resistance": "🕊️"},
    "marco": {"nom": "Marco le Phénix", "emoji": "🦅", "serie": "One Piece", "rarete": "Épique", "pv": 430, "attaque": 97, "defense": 80, "image": "https://i.imgur.com/41zNRCO.jpg", "attaques": [{"nom": "Blue Flames", "emoji": "💙", "degats": 70, "desc": "Flammes bleues régénératrices"}, {"nom": "Phoenix Form", "emoji": "🐦", "degats": 75, "desc": "Forme phénix"}, {"nom": "Blue Fire Inferno", "emoji": "💥", "degats": 80, "desc": "Inferno bleu"}], "faiblesse": "⚡", "resistance": "🦅"},
    "sabo": {"nom": "Sabo", "emoji": "🔥", "serie": "One Piece", "rarete": "Épique", "pv": 425, "attaque": 96, "defense": 79, "image": "https://i.imgur.com/MX8frrO.jpg", "attaques": [{"nom": "Dragon's Breath Fist", "emoji": "🔥", "degats": 75, "desc": "Poing souffle de dragon"}, {"nom": "Mera Mera no Mi", "emoji": "🔥", "degats": 80, "desc": "Fruit flamme"}, {"nom": "Fire Fist", "emoji": "💥", "degats": 70, "desc": "Poing de feu"}], "faiblesse": "⚡", "resistance": "🔥"},
    "toga": {"nom": "Toga Himiko", "emoji": "🩸", "serie": "My Hero Academia", "rarete": "Épique", "pv": 395, "attaque": 89, "defense": 72, "image": "https://i.imgur.com/KfQa8Rz.jpg", "attaques": [{"nom": "Transform", "emoji": "🩸", "degats": 60, "desc": "Transformation sanguine"}, {"nom": "Blood Sucking", "emoji": "💉", "degats": 65, "desc": "Aspiration de sang"}, {"nom": "Twin Impact", "emoji": "💥", "degats": 70, "desc": "Double impact"}], "faiblesse": "⚡", "resistance": "🩸"},
    "overhaul": {"nom": "Overhaul", "emoji": "🦠", "serie": "My Hero Academia", "rarete": "Épique", "pv": 430, "attaque": 97, "defense": 79, "image": "https://i.imgur.com/1YJZ1rg.jpg", "attaques": [{"nom": "Disassembly", "emoji": "💥", "degats": 75, "desc": "Désassemblage"}, {"nom": "Reassembly", "emoji": "🔄", "degats": 70, "desc": "Réassemblage"}, {"nom": "Plague Bullets", "emoji": "💉", "degats": 80, "desc": "Balles de peste"}], "faiblesse": "⚡", "resistance": "🦠"},
    "muscular": {"nom": "Muscular", "emoji": "💪", "serie": "My Hero Academia", "rarete": "Épique", "pv": 450, "attaque": 102, "defense": 82, "image": "https://i.imgur.com/s9SpLak.jpg", "attaques": [{"nom": "Muscle Augmentation", "emoji": "💪", "degats": 75, "desc": "Augmentation musculaire"}, {"nom": "Optical Fiber Muscles", "emoji": "🔵", "degats": 80, "desc": "Muscles à fibre optique"}, {"nom": "Max Muscle Engage", "emoji": "💥", "degats": 85, "desc": "Engagement musculaire max"}], "faiblesse": "⚡", "resistance": "💪"},
    "shinra": {"nom": "Shinra Kusakabe", "emoji": "🔥", "serie": "Fire Force", "rarete": "Épique", "pv": 415, "attaque": 93, "defense": 76, "image": "https://i.imgur.com/EHSOtr3.jpg", "attaques": [{"nom": "Rapid Fire", "emoji": "🔥", "degats": 65, "desc": "Feu rapide"}, {"nom": "Adolla Burst", "emoji": "🌸", "degats": 75, "desc": "Explosion Adolla"}, {"nom": "Hysterical Strength", "emoji": "💥", "degats": 80, "desc": "Force hystérique"}], "faiblesse": "⚡", "resistance": "🔥"},
    "burns": {"nom": "Leonard Burns", "emoji": "🔥", "serie": "Fire Force", "rarete": "Épique", "pv": 435, "attaque": 98, "defense": 81, "image": "https://i.imgur.com/NCR7mPK.jpg", "attaques": [{"nom": "Rapid Fire Inferno", "emoji": "🔥", "degats": 65, "desc": "Feu rapide"}, {"nom": "Core Drive: Blowtorch", "emoji": "💥", "degats": 70, "desc": "Flambeau central"}, {"nom": "Towering Inferno", "emoji": "🌋", "degats": 75, "desc": "Inferno géant"}], "faiblesse": "⚡", "resistance": "🔥"},
    "benimaru": {"nom": "Benimaru Shinmon", "emoji": "🔥", "serie": "Fire Force", "rarete": "Épique", "pv": 440, "attaque": 100, "defense": 82, "image": "https://i.imgur.com/WQdhN22.jpg", "attaques": [{"nom": "Homura Undulation", "emoji": "🔥", "degats": 65, "desc": "Vague de flammes"}, {"nom": "Crimson Moon", "emoji": "🌕", "degats": 70, "desc": "Lune cramoisie"}, {"nom": "Fist of Purgatory", "emoji": "💥", "degats": 75, "desc": "Poing du purgatoire"}], "faiblesse": "⚡", "resistance": "🔥"},
    "mash": {"nom": "Mash Burnedead", "emoji": "💪", "serie": "Mashle", "rarete": "Épique", "pv": 445, "attaque": 101, "defense": 83, "image": "https://i.imgur.com/ETOIMgo.jpg", "attaques": [{"nom": "Magic Muscle", "emoji": "💪", "degats": 65, "desc": "Muscle magique"}, {"nom": "Jugglus Juggler", "emoji": "🤹", "degats": 70, "desc": "Jonglage mortel"}, {"nom": "Mash Fist", "emoji": "👊", "degats": 75, "desc": "Poing de Mash"}], "faiblesse": "⚡", "resistance": "💪"},
    "lanceep": {"nom": "Lance Crown", "emoji": "🌹", "serie": "Mashle", "rarete": "Épique", "pv": 420, "attaque": 95, "defense": 78, "image": "https://i.imgur.com/TOpeVUp.jpg", "attaques": [{"nom": "Spell Bullet", "emoji": "🪄", "degats": 45, "desc": "Balle magique"}, {"nom": "Infinity Bullet", "emoji": "∞", "degats": 50, "desc": "Balle infinie"}, {"nom": "Divine Bullet", "emoji": "✨", "degats": 55, "desc": "Balle divine"}], "faiblesse": "⚡", "resistance": "🌹"},
    "lichtbc": {"nom": "Licht", "emoji": "⚔️", "serie": "Black Clover", "rarete": "Épique", "pv": 435, "attaque": 98, "defense": 80, "image": "https://i.imgur.com/17Bjofy.jpg", "attaques": [{"nom": "Sword Magic", "emoji": "⚔️", "degats": 70, "desc": "Magie des épées"}, {"nom": "Demon Sword Licht", "emoji": "😈", "degats": 80, "desc": "Épée démon"}, {"nom": "Ultimate Anti-Magic", "emoji": "🌑", "degats": 85, "desc": "Anti-magie ultime"}], "faiblesse": "⚡", "resistance": "⚔️"},
    "mereoleona": {"nom": "Mereoleona Vermillion", "emoji": "🦁", "serie": "Black Clover", "rarete": "Épique", "pv": 440, "attaque": 100, "defense": 81, "image": "https://i.imgur.com/JMhLymg.jpg", "attaques": [{"nom": "Purgatory Flame", "emoji": "🔥", "degats": 75, "desc": "Flamme du purgatoire"}, {"nom": "Calidus Brachium", "emoji": "💥", "degats": 80, "desc": "Brasier brûlant"}, {"nom": "Volcano Burst", "emoji": "🌋", "degats": 85, "desc": "Explosion volcanique"}], "faiblesse": "⚡", "resistance": "🦁"},
    "julius": {"nom": "Julius Novachrono", "emoji": "⏰", "serie": "Black Clover", "rarete": "Épique", "pv": 430, "attaque": 97, "defense": 79, "image": "https://i.imgur.com/wEc5g2E.jpg", "attaques": [{"nom": "Chrono Anastasis", "emoji": "⏳", "degats": 85, "desc": "Résurrection temporelle"}, {"nom": "Time Magic", "emoji": "⏰", "degats": 80, "desc": "Magie du temps"}, {"nom": "Chronos", "emoji": "🕰️", "degats": 90, "desc": "Maître du temps"}], "faiblesse": "⚡", "resistance": "⏰"},
    "zenon": {"nom": "Zenon Zogratis", "emoji": "💀", "serie": "Black Clover", "rarete": "Épique", "pv": 435, "attaque": 99, "defense": 80, "image": "https://i.imgur.com/N8kGT5u.jpg", "attaques": [{"nom": "Devil Union", "emoji": "😈", "degats": 80, "desc": "Union avec le diable"}, {"nom": "Bone Magic", "emoji": "🦴", "degats": 75, "desc": "Magie des os"}, {"nom": "Spatial Magic", "emoji": "🌑", "degats": 85, "desc": "Magie spatiale"}], "faiblesse": "⚡", "resistance": "💀"},
    "sakamotoe": {"nom": "Taro Sakamoto", "emoji": "🛒", "serie": "Sakamoto Days", "rarete": "Épique", "pv": 440, "attaque": 100, "defense": 82, "image": "https://i.imgur.com/9wbD2Tt.jpg", "attaques": [{"nom": "Perfect Assassination", "emoji": "🗡️", "degats": 75, "desc": "Assassinat parfait"}, {"nom": "Business Style", "emoji": "💼", "degats": 70, "desc": "Style d'affaires"}, {"nom": "Cool Escape", "emoji": "😎", "degats": 65, "desc": "Esquive cool"}], "faiblesse": "⚡", "resistance": "🛒"},
    "shinae": {"nom": "Shin Asakura", "emoji": "👊", "serie": "Sakamoto Days", "rarete": "Épique", "pv": 415, "attaque": 94, "defense": 76, "image": "https://i.imgur.com/JzbTwwD.jpg", "attaques": [{"nom": "Magie Feu", "emoji": "🔥", "degats": 50, "desc": "Flammes d'ignition"}, {"nom": "Pillar Fire", "emoji": "🌋", "degats": 55, "desc": "Colonne de feu"}, {"nom": "Burning Attack", "emoji": "💥", "degats": 60, "desc": "Assaut enflammé"}], "faiblesse": "⚡", "resistance": "👊"},
    "sakurawb": {"nom": "Haruka Sakura", "emoji": "🌸", "serie": "Wind Breaker", "rarete": "Épique", "pv": 420, "attaque": 95, "defense": 77, "image": "https://i.imgur.com/JzbTwwD.jpg", "attaques": [{"nom": "Brawl Strike", "emoji": "👊", "degats": 50, "desc": "Combat de rue"}, {"nom": "Relentless Assault", "emoji": "💪", "degats": 55, "desc": "Assaut implacable"}, {"nom": "Berserker Mode", "emoji": "🔥", "degats": 60, "desc": "Rage berserker"}], "faiblesse": "⚡", "resistance": "🌸"},
    "suowb": {"nom": "Tomoya Suo", "emoji": "⚡", "serie": "Wind Breaker", "rarete": "Épique", "pv": 425, "attaque": 96, "defense": 78, "image": "https://i.imgur.com/JzbTwwD.jpg", "attaques": [{"nom": "Expert Kick", "emoji": "🦵", "degats": 45, "desc": "Coup de pied expert"}, {"nom": "Combo Rush", "emoji": "💥", "degats": 50, "desc": "Combo rapide"}, {"nom": "Counter", "emoji": "🔄", "degats": 40, "desc": "Contre-attaque"}], "faiblesse": "⚡", "resistance": "⚡"},
    "mikeye": {"nom": "Manjiro Sano (Mikey)", "emoji": "🛵", "serie": "Tokyo Revengers", "rarete": "Épique", "pv": 445, "attaque": 101, "defense": 82, "image": "https://i.imgur.com/sdfXTHr.jpg", "attaques": [{"nom": "Invincible", "emoji": "💪", "degats": 75, "desc": "Invincibilité légendaire"}, {"nom": "Nuclear Kick", "emoji": "💥", "degats": 80, "desc": "Coup nucléaire"}, {"nom": "Dark Impulse", "emoji": "🖤", "degats": 85, "desc": "Impulsion sombre"}], "faiblesse": "⚡", "resistance": "🛵"},
    "baji": {"nom": "Keisuke Baji", "emoji": "⚡", "serie": "Tokyo Revengers", "rarete": "Épique", "pv": 420, "attaque": 95, "defense": 77, "image": "https://i.imgur.com/A4TigIm.jpg", "attaques": [{"nom": "Frappe Explosive", "emoji": "💥", "degats": 65, "desc": "Coup de délinquant"}, {"nom": "Sabre de Baji", "emoji": "⚔️", "degats": 60, "desc": "Lame tranchante"}, {"nom": "Gang Strike", "emoji": "🔥", "degats": 70, "desc": "Attaque de gang"}], "faiblesse": "⚡", "resistance": "⚡"},
    "chahae": {"nom": "Cha Hae-In", "emoji": "⚔️", "serie": "Solo Leveling", "rarete": "Épique", "pv": 425, "attaque": 96, "defense": 78, "image": "https://i.imgur.com/PVzfmpD.jpg", "attaques": [{"nom": "Lunatic Slash", "emoji": "⚔️", "degats": 70, "desc": "Coupe lunaire"}, {"nom": "Final Blow", "emoji": "💥", "degats": 75, "desc": "Coup final"}, {"nom": "Wind Sword", "emoji": "💨", "degats": 65, "desc": "Lame de vent"}], "faiblesse": "⚡", "resistance": "⚔️"},
    "thomasandre": {"nom": "Thomas Andre", "emoji": "🏋️", "serie": "Solo Leveling", "rarete": "Épique", "pv": 450, "attaque": 102, "defense": 84, "image": "https://i.imgur.com/ahh7Com.jpg", "attaques": [{"nom": "Ruler's Authority", "emoji": "👑", "degats": 80, "desc": "Autorité du souverain"}, {"nom": "Dominator", "emoji": "💪", "degats": 85, "desc": "Dominateur"}, {"nom": "Iron Body", "emoji": "🦾", "degats": 75, "desc": "Corps de fer"}], "faiblesse": "⚡", "resistance": "🏋️"},
    "okamome": {"nom": "Momo Ayase", "emoji": "👁️", "serie": "Dandadan", "rarete": "Épique", "pv": 410, "attaque": 92, "defense": 75, "image": "https://i.imgur.com/TEJ6KZr.jpg", "attaques": [{"nom": "Devil No. 4", "emoji": "😈", "degats": 65, "desc": "Démon numéro 4"}, {"nom": "Binding Curse", "emoji": "🔒", "degats": 70, "desc": "Malédiction liante"}, {"nom": "Atsushi Strike", "emoji": "💥", "degats": 75, "desc": "Frappe d'Atsushi"}], "faiblesse": "⚡", "resistance": "👁️"},
    "rudeus": {"nom": "Rudeus Greyrat", "emoji": "📚", "serie": "Mushoku Tensei", "rarete": "Épique", "pv": 420, "attaque": 95, "defense": 77, "image": "https://i.imgur.com/3Ih34qF.jpg", "attaques": [{"nom": "Void Magic", "emoji": "🌑", "degats": 75, "desc": "Magie du vide"}, {"nom": "Touki", "emoji": "💪", "degats": 70, "desc": "Énergie corporelle"}, {"nom": "Megaton Taihou", "emoji": "💥", "degats": 80, "desc": "Canon de mégatonnes"}], "faiblesse": "⚡", "resistance": "📚"},
    "ragnaep": {"nom": "Ragna", "emoji": "⚔️", "serie": "Ragna Crimson", "rarete": "Épique", "pv": 430, "attaque": 97, "defense": 79, "image": "https://i.imgur.com/ShjRIz1.jpg", "attaques": [{"nom": "Shadow Strike", "emoji": "🌑", "degats": 65, "desc": "Frappe d'ombre"}, {"nom": "Darkness Slash", "emoji": "⚔️", "degats": 70, "desc": "Entaille ténèbres"}, {"nom": "Nacht Form", "emoji": "🖤", "degats": 75, "desc": "Forme de nuit"}], "faiblesse": "⚡", "resistance": "⚔️"},
    "gohanssj2": {"nom": "Gohan (SSJ2 vs Cell)", "emoji": "⚡", "serie": "Dragon Ball Z", "rarete": "Légendaire", "pv": 720, "attaque": 165, "defense": 133, "image": "https://i.imgur.com/FW9Uddq.jpg", "attaques": [{"nom": "Father-Son Kamehameha", "emoji": "💥", "degats": 90, "desc": "Kamehameha père-fils"}, {"nom": "Masenko Ha", "emoji": "🌟", "degats": 80, "desc": "Rayon de démon"}, {"nom": "Ultimate Gohan", "emoji": "👁️", "degats": 95, "desc": "Puissance ultime"}], "faiblesse": "⚡", "resistance": "⚡"},
    "jiren": {"nom": "Jiren", "emoji": "🔴", "serie": "Dragon Ball Super", "rarete": "Légendaire", "pv": 750, "attaque": 172, "defense": 140, "image": "https://i.imgur.com/z1ZKU2Y.jpg", "attaques": [{"nom": "Power Impact", "emoji": "💥", "degats": 85, "desc": "Impact de puissance"}, {"nom": "Overpowering Pressure", "emoji": "🔴", "degats": 90, "desc": "Pression écrasante"}, {"nom": "Full Power", "emoji": "🌟", "degats": 95, "desc": "Puissance absolue"}], "faiblesse": "⚡", "resistance": "🔴"},
    "android21": {"nom": "Android 21", "emoji": "🧬", "serie": "Dragon Ball Z", "rarete": "Légendaire", "pv": 730, "attaque": 167, "defense": 135, "image": "https://i.imgur.com/sqse0MZ.jpg", "attaques": [{"nom": "Sweet Tooth", "emoji": "🍬", "degats": 65, "desc": "Absorbe les capacités"}, {"nom": "Connoisseur Cut", "emoji": "🔪", "degats": 70, "desc": "Coupe de connaisseur"}, {"nom": "Hunger Pang", "emoji": "💥", "degats": 75, "desc": "Faim dévorante"}], "faiblesse": "⚡", "resistance": "🧬"},
    "broly": {"nom": "Broly (DBS)", "emoji": "💚", "serie": "Dragon Ball Super", "rarete": "Légendaire", "pv": 760, "attaque": 175, "defense": 142, "image": "https://i.imgur.com/c0oACBA.jpg", "attaques": [{"nom": "Gigantic Omega", "emoji": "💚", "degats": 85, "desc": "Onde verte dévastatrice"}, {"nom": "Blaster Meteor", "emoji": "💥", "degats": 90, "desc": "Météore d'énergie"}, {"nom": "Chou Masenkou", "emoji": "🟢", "degats": 80, "desc": "Super rayon démoniaque"}], "faiblesse": "⚡", "resistance": "💚"},
    "gogeta": {"nom": "Gogeta (SSJ Blue)", "emoji": "💙", "serie": "Dragon Ball Super", "rarete": "Légendaire", "pv": 780, "attaque": 180, "defense": 145, "image": "https://i.imgur.com/7rZvNsk.jpg", "attaques": [{"nom": "Stardust Fall", "emoji": "💫", "degats": 90, "desc": "Pluie d'étoiles"}, {"nom": "Soul Punisher", "emoji": "💥", "degats": 95, "desc": "Poinçon d'âme"}, {"nom": "Bluff Kamehameha", "emoji": "⚡", "degats": 85, "desc": "Kamehameha bluff"}], "faiblesse": "⚡", "resistance": "💙"},
    "vegito": {"nom": "Vegito (SSJ Blue)", "emoji": "💙", "serie": "Dragon Ball Super", "rarete": "Légendaire", "pv": 780, "attaque": 180, "defense": 145, "image": "https://i.imgur.com/COP7cnj.jpg", "attaques": [{"nom": "Final Kamehameha", "emoji": "💥", "degats": 95, "desc": "Kamehameha final"}, {"nom": "Spirit Sword", "emoji": "⚔️", "degats": 90, "desc": "Épée d'esprit"}, {"nom": "Big Bang Kamehameha", "emoji": "🌟", "degats": 100, "desc": "BBK"}], "faiblesse": "⚡", "resistance": "💙"},
    "mightguy": {"nom": "Might Guy (8 Portes)", "emoji": "🔥", "serie": "Naruto", "rarete": "Légendaire", "pv": 720, "attaque": 165, "defense": 133, "image": "https://i.imgur.com/RRUkedp.jpg", "attaques": [{"nom": "Evening Elephant", "emoji": "🐘", "degats": 85, "desc": "Éléphant du soir"}, {"nom": "Night Guy", "emoji": "🌙", "degats": 95, "desc": "Gars de nuit"}, {"nom": "Eight Inner Gates Formation", "emoji": "💀", "degats": 90, "desc": "8 portes ouvertes"}], "faiblesse": "⚡", "resistance": "🔥"},
    "tobirama": {"nom": "Tobirama Senju", "emoji": "💧", "serie": "Naruto", "rarete": "Légendaire", "pv": 715, "attaque": 163, "defense": 132, "image": "https://i.imgur.com/6qXLw0N.jpg", "attaques": [{"nom": "Hiraishin no Jutsu", "emoji": "⚡", "degats": 75, "desc": "Téléportation"}, {"nom": "Suiton Senjutsu", "emoji": "💧", "degats": 80, "desc": "Arts sages de l'eau"}, {"nom": "Shadow Clone", "emoji": "👥", "degats": 70, "desc": "Créateur des clones"}], "faiblesse": "⚡", "resistance": "💧"},
    "bigmom": {"nom": "Big Mom", "emoji": "🍬", "serie": "One Piece", "rarete": "Légendaire", "pv": 760, "attaque": 175, "defense": 142, "image": "https://i.imgur.com/jP0GMXL.jpg", "attaques": [{"nom": "Prometheus", "emoji": "☀️", "degats": 75, "desc": "Soleil vivant"}, {"nom": "Zeus", "emoji": "⚡", "degats": 80, "desc": "Tonnerre vivant"}, {"nom": "Soul Pocus", "emoji": "💀", "degats": 85, "desc": "Vol d'âme"}], "faiblesse": "⚡", "resistance": "🍬"},
    "admiralkizaru": {"nom": "Kizaru", "emoji": "⚡", "serie": "One Piece", "rarete": "Légendaire", "pv": 730, "attaque": 167, "defense": 135, "image": "https://i.imgur.com/bxRummG.jpg", "attaques": [{"nom": "Pika Pika", "emoji": "✨", "degats": 80, "desc": "Vitesse lumière"}, {"nom": "Yasakani no Magatama", "emoji": "💛", "degats": 85, "desc": "Pluie de lumière"}, {"nom": "Yata Mirror", "emoji": "🪞", "degats": 75, "desc": "Miroir laser"}], "faiblesse": "⚡", "resistance": "⚡"},
    "admiralaokiji": {"nom": "Aokiji", "emoji": "❄️", "serie": "One Piece", "rarete": "Légendaire", "pv": 735, "attaque": 168, "defense": 136, "image": "https://i.imgur.com/Z2KRYQd.jpg", "attaques": [{"nom": "Ice Age", "emoji": "❄️", "degats": 70, "desc": "Congélation de l'océan"}, {"nom": "Ice Time", "emoji": "🧊", "degats": 65, "desc": "Stalagmite de glace"}, {"nom": "Ice Block: Pheasant Beak", "emoji": "💙", "degats": 75, "desc": "Coup de glace"}], "faiblesse": "⚡", "resistance": "❄️"},
    "admiralakainu": {"nom": "Akainu", "emoji": "🌋", "serie": "One Piece", "rarete": "Légendaire", "pv": 750, "attaque": 172, "defense": 140, "image": "https://i.imgur.com/WUQYoFP.jpg", "attaques": [{"nom": "Ryūsei Kazan", "emoji": "🌋", "degats": 75, "desc": "Météores de lave"}, {"nom": "Meigo", "emoji": "🔥", "degats": 80, "desc": "Poing de magma"}, {"nom": "Great Eruption", "emoji": "💥", "degats": 85, "desc": "Éruption totale"}], "faiblesse": "⚡", "resistance": "🌋"},
    "stark": {"nom": "Coyote Starrk", "emoji": "🐺", "serie": "Bleach", "rarete": "Légendaire", "pv": 720, "attaque": 165, "defense": 133, "image": "https://i.imgur.com/eNW4b7c.jpg", "attaques": [{"nom": "Los Lobos", "emoji": "🐺", "degats": 75, "desc": "Meute de loups"}, {"nom": "Cero Metralleta", "emoji": "💥", "degats": 80, "desc": "Grêle de Cero"}, {"nom": "Twin Guns", "emoji": "🔫", "degats": 70, "desc": "Pistolets jumeaux"}], "faiblesse": "⚡", "resistance": "🐺"},
    "barragan": {"nom": "Barragan", "emoji": "👑", "serie": "Bleach", "rarete": "Légendaire", "pv": 730, "attaque": 167, "defense": 135, "image": "https://i.imgur.com/jbuhrOW.jpg", "attaques": [{"nom": "Arrogante", "emoji": "💀", "degats": 75, "desc": "Faucille de la mort"}, {"nom": "Respira", "emoji": "☠️", "degats": 80, "desc": "Souffle de mort"}, {"nom": "Gran Caída", "emoji": "🖤", "degats": 85, "desc": "Grande chute"}], "faiblesse": "⚡", "resistance": "👑"},
    "shunsui": {"nom": "Shunsui Kyoraku", "emoji": "🌸", "serie": "Bleach", "rarete": "Légendaire", "pv": 725, "attaque": 166, "defense": 134, "image": "https://i.imgur.com/E3QWGx6.jpg", "attaques": [{"nom": "Katen Kyōkotsu", "emoji": "🌸", "degats": 75, "desc": "Deux lames en fleurs"}, {"nom": "Bankai Katen Kyōkotsu", "emoji": "💀", "degats": 85, "desc": "Bankai fatal"}, {"nom": "Play Dead", "emoji": "🎭", "degats": 70, "desc": "Jouer la mort"}], "faiblesse": "⚡", "resistance": "🌸"},
    "unohana": {"nom": "Retsu Unohana", "emoji": "🌊", "serie": "Bleach", "rarete": "Légendaire", "pv": 720, "attaque": 165, "defense": 133, "image": "https://i.imgur.com/sJdxlRr.jpg", "attaques": [{"nom": "Minazuki", "emoji": "💀", "degats": 80, "desc": "Stand de guérison/mort"}, {"nom": "Healing Arts", "emoji": "💉", "degats": 70, "desc": "Arts de guérison"}, {"nom": "Kenpachi's Origin", "emoji": "⚔️", "degats": 85, "desc": "Origine du Kenpachi"}], "faiblesse": "⚡", "resistance": "🌊"},
    "chrollo": {"nom": "Chrollo Lucilfer", "emoji": "📖", "serie": "HunterxHunter", "rarete": "Légendaire", "pv": 735, "attaque": 168, "defense": 136, "image": "https://i.imgur.com/oSuczS8.jpg", "attaques": [{"nom": "Indoor Fish", "emoji": "🐟", "degats": 65, "desc": "Poisson en bocal"}, {"nom": "Skill Hunter", "emoji": "📖", "degats": 75, "desc": "Vol de talent"}, {"nom": "Order Stamp", "emoji": "📛", "degats": 70, "desc": "Tampon d'ordre"}], "faiblesse": "⚡", "resistance": "📖"},
    "neferpitou": {"nom": "Neferpitou", "emoji": "🐱", "serie": "HunterxHunter", "rarete": "Légendaire", "pv": 740, "attaque": 170, "defense": 138, "image": "https://i.imgur.com/X9f9pyY.jpg", "attaques": [{"nom": "Nen Manipulation", "emoji": "👁️", "degats": 75, "desc": "Manipulation du Nen"}, {"nom": "Terpsichora", "emoji": "💃", "degats": 80, "desc": "Danse mortelle"}, {"nom": "Doctor Blythe", "emoji": "💉", "degats": 70, "desc": "Chirurgie Nen"}], "faiblesse": "⚡", "resistance": "🐱"},
    "silva": {"nom": "Silva Zoldyck", "emoji": "🗡️", "serie": "HunterxHunter", "rarete": "Légendaire", "pv": 730, "attaque": 167, "defense": 135, "image": "https://i.imgur.com/1HUdAyr.jpg", "attaques": [{"nom": "Nen Assassin", "emoji": "💀", "degats": 75, "desc": "Nen d'assassin"}, {"nom": "Bungee Gum Type", "emoji": "⚡", "degats": 70, "desc": "Type Bungee Gum"}, {"nom": "Silver Killer", "emoji": "🗡️", "degats": 80, "desc": "Tueur d'argent"}], "faiblesse": "⚡", "resistance": "🗡️"},
    "zeno_z": {"nom": "Zeno Zoldyck", "emoji": "🐉", "serie": "HunterxHunter", "rarete": "Légendaire", "pv": 735, "attaque": 168, "defense": 136, "image": "https://i.imgur.com/OOnUGGv.jpg", "attaques": [{"nom": "Shadow Step", "emoji": "👣", "degats": 70, "desc": "Pas d'ombre"}, {"nom": "Silent Kill", "emoji": "🗡️", "degats": 75, "desc": "Meurtre silencieux"}, {"nom": "Zoldyck Technique", "emoji": "💀", "degats": 80, "desc": "Technique Zoldyck"}], "faiblesse": "⚡", "resistance": "🐉"},
    "afo": {"nom": "All For One", "emoji": "☠️", "serie": "My Hero Academia", "rarete": "Légendaire", "pv": 750, "attaque": 172, "defense": 140, "image": "https://i.imgur.com/4926kae.jpg", "attaques": [{"nom": "All For One", "emoji": "👁️", "degats": 85, "desc": "Vol de capacités"}, {"nom": "Air Cannon", "emoji": "💨", "degats": 75, "desc": "Canon d'air"}, {"nom": "Rivet Stab", "emoji": "🔩", "degats": 80, "desc": "Pieux métalliques"}], "faiblesse": "⚡", "resistance": "☠️"},
    "gyomei": {"nom": "Gyomei Himejima", "emoji": "⛓️", "serie": "Demon Slayer", "rarete": "Légendaire", "pv": 740, "attaque": 170, "defense": 138, "image": "https://i.imgur.com/YtrUnvL.jpg", "attaques": [{"nom": "Stone Breathing First Form", "emoji": "🪨", "degats": 70, "desc": "Première forme pierre"}, {"nom": "Roar", "emoji": "📣", "degats": 75, "desc": "Rugissement dévastateur"}, {"nom": "Transparent World", "emoji": "👁️", "degats": 80, "desc": "Monde transparent"}], "faiblesse": "⚡", "resistance": "⛓️"},
    "mitsuri": {"nom": "Mitsuri Kanroji", "emoji": "💗", "serie": "Demon Slayer", "rarete": "Légendaire", "pv": 720, "attaque": 165, "defense": 133, "image": "https://i.imgur.com/jtoItwO.jpg", "attaques": [{"nom": "Love Breathing First Form", "emoji": "💗", "degats": 70, "desc": "Première forme amour"}, {"nom": "Sixth Form: Cat-Legged Winds", "emoji": "🌸", "degats": 75, "desc": "Vents de chat"}, {"nom": "Slashing Whirlwind", "emoji": "🌀", "degats": 80, "desc": "Tourbillon tranchant"}], "faiblesse": "⚡", "resistance": "💗"},
    "obanai": {"nom": "Obanai Iguro", "emoji": "🐍", "serie": "Demon Slayer", "rarete": "Légendaire", "pv": 715, "attaque": 163, "defense": 132, "image": "https://i.imgur.com/yNIPY2y.jpg", "attaques": [{"nom": "Serpent Breathing", "emoji": "🐍", "degats": 70, "desc": "Respiration du serpent"}, {"nom": "Ninth Form: Constriction", "emoji": "🌀", "degats": 75, "desc": "Neuvième forme"}, {"nom": "Kaburamaru Support", "emoji": "🐍", "degats": 65, "desc": "Soutien du serpent"}], "faiblesse": "⚡", "resistance": "🐍"},
    "doma": {"nom": "Doma", "emoji": "❄️", "serie": "Demon Slayer", "rarete": "Légendaire", "pv": 735, "attaque": 168, "defense": 136, "image": "https://i.imgur.com/IBoGpOh.jpg", "attaques": [{"nom": "Scavenge", "emoji": "❄️", "degats": 70, "desc": "Absorption des âmes"}, {"nom": "Crystalline Orb", "emoji": "💎", "degats": 75, "desc": "Orbe cristallin"}, {"nom": "Glacial Realm", "emoji": "🌨️", "degats": 80, "desc": "Domaine glaciaire"}], "faiblesse": "⚡", "resistance": "❄️"},
    "kokushibo": {"nom": "Kokushibo", "emoji": "🌙", "serie": "Demon Slayer", "rarete": "Légendaire", "pv": 755, "attaque": 173, "defense": 141, "image": "https://i.imgur.com/3jSkSj0.jpg", "attaques": [{"nom": "Moon Breathing First Form", "emoji": "🌙", "degats": 80, "desc": "Première forme lune"}, {"nom": "Burning Slashes", "emoji": "🌑", "degats": 85, "desc": "Entailles ardentes"}, {"nom": "Crescent Moon Slashes", "emoji": "⚔️", "degats": 90, "desc": "Entailles croissant"}], "faiblesse": "⚡", "resistance": "🌙"},
    "spade": {"nom": "Dante Zogratis", "emoji": "🖤", "serie": "Black Clover", "rarete": "Légendaire", "pv": 740, "attaque": 170, "defense": 138, "image": "https://i.imgur.com/Bp0jw1D.jpg", "attaques": [{"nom": "Lucifero", "emoji": "😈", "degats": 85, "desc": "Puissance du diable"}, {"nom": "Gravity Magique", "emoji": "⬛", "degats": 80, "desc": "Magie gravitationnelle"}, {"nom": "Dark Clover", "emoji": "🍀", "degats": 75, "desc": "Trèfle noir"}], "faiblesse": "⚡", "resistance": "🖤"},
    "yuta": {"nom": "Yuta Okkotsu", "emoji": "💜", "serie": "Jujutsu Kaisen", "rarete": "Légendaire", "pv": 745, "attaque": 171, "defense": 139, "image": "https://i.imgur.com/iVcKXD4.jpg", "attaques": [{"nom": "Rika", "emoji": "👻", "degats": 80, "desc": "Esprit maudit Rika"}, {"nom": "Cursed Speech Copy", "emoji": "📣", "degats": 85, "desc": "Copie de parole maudite"}, {"nom": "Infinity Copy", "emoji": "∞", "degats": 90, "desc": "Copie infinie"}], "faiblesse": "⚡", "resistance": "💜"},
    "kashimo": {"nom": "Hajime Kashimo", "emoji": "⚡", "serie": "Jujutsu Kaisen", "rarete": "Légendaire", "pv": 730, "attaque": 167, "defense": 135, "image": "https://i.imgur.com/5ILrG0l.jpg", "attaques": [{"nom": "Electric Discharge", "emoji": "⚡", "degats": 80, "desc": "Décharge électrique"}, {"nom": "Genju Kohasaku", "emoji": "🌩️", "degats": 85, "desc": "Technique du faux animal"}, {"nom": "Beast Form", "emoji": "🐉", "degats": 90, "desc": "Forme bestiale"}], "faiblesse": "⚡", "resistance": "⚡"},
    "choso": {"nom": "Choso", "emoji": "🩸", "serie": "Jujutsu Kaisen", "rarete": "Légendaire", "pv": 715, "attaque": 163, "defense": 132, "image": "https://i.imgur.com/HBNSQtw.jpg", "attaques": [{"nom": "Piercing Blood", "emoji": "🩸", "degats": 65, "desc": "Sang perforant"}, {"nom": "Supernova", "emoji": "💥", "degats": 75, "desc": "Supernova sanguine"}, {"nom": "Blood Meteorite", "emoji": "☄️", "degats": 80, "desc": "Météorite de sang"}], "faiblesse": "⚡", "resistance": "🩸"},
    "crimson": {"nom": "Crimson", "emoji": "🔴", "serie": "Ragna Crimson", "rarete": "Légendaire", "pv": 750, "attaque": 172, "defense": 140, "image": "https://i.imgur.com/BZy8XUs.jpg", "attaques": [{"nom": "Shadow Monarch Strike", "emoji": "🌑", "degats": 75, "desc": "Frappe du monarque"}, {"nom": "Ruler's Authority", "emoji": "👑", "degats": 80, "desc": "Autorité royale"}, {"nom": "Death Knight", "emoji": "☠️", "degats": 85, "desc": "Chevalier de mort"}], "faiblesse": "⚡", "resistance": "🔴"},
    "naofumil": {"nom": "Naofumi Iwatani", "emoji": "🛡️", "serie": "The Rising of the Shield Hero", "rarete": "Légendaire", "pv": 740, "attaque": 165, "defense": 145, "image": "https://i.imgur.com/dsFYYLS.jpg", "attaques": [{"nom": "Wrath Flame", "emoji": "🔥", "degats": 70, "desc": "Flamme de colère"}, {"nom": "Shield Counter", "emoji": "🛡️", "degats": 65, "desc": "Contre de bouclier"}, {"nom": "Iron Maiden Curse", "emoji": "⛓️", "degats": 75, "desc": "Malédiction d'armure"}], "faiblesse": "⚡", "resistance": "🛡️"},
    "filo": {"nom": "Filo", "emoji": "🐣", "serie": "The Rising of the Shield Hero", "rarete": "Légendaire", "pv": 710, "attaque": 160, "defense": 131, "image": "https://i.imgur.com/w6BThoA.jpg", "attaques": [{"nom": "Wing Strike", "emoji": "🐦", "degats": 40, "desc": "Coup d'aile"}, {"nom": "Filolial Kick", "emoji": "🦵", "degats": 45, "desc": "Coup de pied magique"}, {"nom": "Wind Slash", "emoji": "💨", "degats": 50, "desc": "Tranchant d'air"}], "faiblesse": "⚡", "resistance": "🐣"},
    "ruijerd": {"nom": "Ruijerd Superdia", "emoji": "⚡", "serie": "Mushoku Tensei", "rarete": "Légendaire", "pv": 740, "attaque": 170, "defense": 138, "image": "https://i.imgur.com/NpLm3dY.jpg", "attaques": [{"nom": "Lance Superd", "emoji": "🔱", "degats": 70, "desc": "Lance légendaire"}, {"nom": "Superd Strike", "emoji": "💥", "degats": 80, "desc": "Frappe des Superd"}, {"nom": "Final Thrust", "emoji": "💀", "degats": 85, "desc": "Poussée finale"}], "faiblesse": "⚡", "resistance": "⚡"},
    "halibel": {"nom": "Tier Harribel", "emoji": "🦈", "serie": "Bleach", "rarete": "Légendaire", "pv": 715, "attaque": 163, "defense": 132, "image": "https://i.imgur.com/6ao1jhz.jpg", "attaques": [{"nom": "Tiburon", "emoji": "🦈", "degats": 70, "desc": "Requin transformé"}, {"nom": "Cascada", "emoji": "🌊", "degats": 75, "desc": "Cascade d'eau"}, {"nom": "La Gota", "emoji": "💧", "degats": 65, "desc": "La goutte"}], "faiblesse": "⚡", "resistance": "🦈"},
    "gildarts": {"nom": "Gildarts Clive", "emoji": "💥", "serie": "Fairy Tail", "rarete": "Légendaire", "pv": 745, "attaque": 171, "defense": 139, "image": "https://i.imgur.com/U8so0Qd.jpg", "attaques": [{"nom": "Crush", "emoji": "💥", "degats": 80, "desc": "Écrasement total"}, {"nom": "Caste Destruction", "emoji": "💀", "degats": 85, "desc": "Destruction de château"}, {"nom": "Accident Crush", "emoji": "🌋", "degats": 90, "desc": "Broyage accidentel"}], "faiblesse": "⚡", "resistance": "💥"},
    "jellal": {"nom": "Jellal Fernandes", "emoji": "✨", "serie": "Fairy Tail", "rarete": "Légendaire", "pv": 730, "attaque": 167, "defense": 135, "image": "https://i.imgur.com/dVR705B.jpg", "attaques": [{"nom": "Heavenly Body Magic", "emoji": "✨", "degats": 70, "desc": "Magie céleste"}, {"nom": "Sema", "emoji": "💫", "degats": 80, "desc": "Bombe météorite"}, {"nom": "Grand Chariot", "emoji": "🌟", "degats": 85, "desc": "Sept étoiles"}], "faiblesse": "⚡", "resistance": "✨"},
    "zenousama": {"nom": "Zeno-Sama", "emoji": "👶", "serie": "Dragon Ball Super", "rarete": "Mythique", "pv": 9999, "attaque": 999, "defense": 999, "image": "https://i.imgur.com/QyPDWvD.jpg", "attaques": [{"nom": "Erase", "emoji": "⬛", "degats": 100, "desc": "Efface tout"}, {"nom": "Multiverse Destruction", "emoji": "💀", "degats": 95, "desc": "Détruit les univers"}, {"nom": "Absolute Power", "emoji": "✨", "degats": 100, "desc": "Puissance absolue"}], "faiblesse": "⚡", "resistance": "👶"},
    "grandpretre": {"nom": "Grand Prêtre", "emoji": "👼", "serie": "Dragon Ball Super", "rarete": "Mythique", "pv": 1500, "attaque": 350, "defense": 300, "image": "https://i.imgur.com/lT6k1Hg.jpg", "attaques": [{"nom": "Divine Erasure", "emoji": "✨", "degats": 90, "desc": "Effacement divin"}, {"nom": "Angel's Touch", "emoji": "👼", "degats": 85, "desc": "Toucher angélique"}, {"nom": "Destruction Absolute", "emoji": "💀", "degats": 95, "desc": "Destruction absolue"}], "faiblesse": "⚡", "resistance": "👼"},
    "isshiki": {"nom": "Isshiki Otsutsuki", "emoji": "🌑", "serie": "Naruto", "rarete": "Mythique", "pv": 1300, "attaque": 300, "defense": 250, "image": "https://i.imgur.com/agAerjl.jpg", "attaques": [{"nom": "Sukunahikona", "emoji": "⬛", "degats": 85, "desc": "Miniaturise tout"}, {"nom": "Daikokuten", "emoji": "📦", "degats": 90, "desc": "Stockage dimensionnel"}, {"nom": "Boruto-ban", "emoji": "💥", "degats": 95, "desc": "Frappe absolue"}], "faiblesse": "⚡", "resistance": "🌑"},
    "momoshiki": {"nom": "Momoshiki Otsutsuki", "emoji": "🍑", "serie": "Naruto", "rarete": "Mythique", "pv": 1280, "attaque": 290, "defense": 240, "image": "https://i.imgur.com/SPBKQIg.jpg", "attaques": [{"nom": "Rinnegan Absorption", "emoji": "👁️", "degats": 85, "desc": "Absorption Rinnegan"}, {"nom": "Expanded Vanishing Rasengan", "emoji": "🌀", "degats": 90, "desc": "Rasengan géant"}, {"nom": "God Tree", "emoji": "🌳", "degats": 95, "desc": "Arbre divin"}], "faiblesse": "⚡", "resistance": "🍑"},
    "imsama": {"nom": "Im-Sama", "emoji": "👁️", "serie": "One Piece", "rarete": "Mythique", "pv": 1400, "attaque": 320, "defense": 270, "image": "https://i.imgur.com/4FkukvY.jpg", "attaques": [{"nom": "Destruction", "emoji": "💀", "degats": 95, "desc": "Puissance absolue"}, {"nom": "Obliteration", "emoji": "🌑", "degats": 90, "desc": "Oblitération totale"}, {"nom": "World Control", "emoji": "👁️", "degats": 100, "desc": "Contrôle du monde"}], "faiblesse": "⚡", "resistance": "👁️"},
    "yoriichi": {"nom": "Yoriichi Tsugikuni", "emoji": "🌅", "serie": "Demon Slayer", "rarete": "Mythique", "pv": 1400, "attaque": 322, "defense": 268, "image": "https://i.imgur.com/blBxnnO.jpg", "attaques": [{"nom": "Transparent World", "emoji": "👁️", "degats": 85, "desc": "Monde transparent"}, {"nom": "Sun Breathing", "emoji": "☀️", "degats": 95, "desc": "Respiration du soleil"}, {"nom": "Thirteenth Form", "emoji": "🌅", "degats": 100, "desc": "Treizième forme"}], "faiblesse": "⚡", "resistance": "🌅"},
    "antares": {"nom": "Antares", "emoji": "🌑", "serie": "Solo Leveling", "rarete": "Mythique", "pv": 1420, "attaque": 325, "defense": 272, "image": "https://i.imgur.com/CEsQ9Kn.jpg", "attaques": [{"nom": "Fera Géante", "emoji": "🐺", "degats": 75, "desc": "Forme bestiale"}, {"nom": "Griffe du Chaos", "emoji": "💀", "degats": 80, "desc": "Déchirure dimensionnelle"}, {"nom": "Rugissement Fatal", "emoji": "👾", "degats": 85, "desc": "Son destructeur"}], "faiblesse": "⚡", "resistance": "🌑"},
    "luciusfull": {"nom": "Lucius Zogratis", "emoji": "☀️", "serie": "Black Clover", "rarete": "Mythique", "pv": 1380, "attaque": 316, "defense": 263, "image": "https://i.imgur.com/P5NrsCF.jpg", "attaques": [{"nom": "Lucifero Power", "emoji": "👿", "degats": 85, "desc": "Puissance de Lucifer"}, {"nom": "Gravity Magic", "emoji": "⬛", "degats": 80, "desc": "Magie gravitationnelle"}, {"nom": "Supreme Devil Power", "emoji": "💀", "degats": 90, "desc": "Puissance suprême"}], "faiblesse": "⚡", "resistance": "☀️"},
    "laplace": {"nom": "Laplace", "emoji": "🌪️", "serie": "Mushoku Tensei", "rarete": "Mythique", "pv": 1320, "attaque": 302, "defense": 252, "image": "https://i.imgur.com/JzbTwwD.jpg", "attaques": [{"nom": "Magie Mécanique", "emoji": "⚙️", "degats": 55, "desc": "Engrenages magiques"}, {"nom": "Precision Strike", "emoji": "🎯", "degats": 60, "desc": "Attaque précise"}, {"nom": "System Override", "emoji": "💻", "degats": 65, "desc": "Surcharge"}], "faiblesse": "⚡", "resistance": "🌪️"},
    "shadowfull": {"nom": "Shadow (True Form)", "emoji": "🌑", "serie": "The Eminence in Shadow", "rarete": "Mythique", "pv": 1350, "attaque": 310, "defense": 258, "image": "https://i.imgur.com/cRhS3i4.jpg", "attaques": [{"nom": "I Am the Shadow", "emoji": "🌑", "degats": 90, "desc": "Je suis l'ombre"}, {"nom": "Perfection", "emoji": "💀", "degats": 95, "desc": "Forme parfaite"}, {"nom": "Absolute Darkness", "emoji": "⬛", "degats": 100, "desc": "Ténèbres absolues"}], "faiblesse": "⚡", "resistance": "🌑"},
    "lindwurm": {"nom": "Lindwurm", "emoji": "🐉", "serie": "Ragna Crimson", "rarete": "Mythique", "pv": 1300, "attaque": 300, "defense": 250, "image": "https://i.imgur.com/JzbTwwD.jpg", "attaques": [{"nom": "Morsure de Serpent", "emoji": "🐍", "degats": 55, "desc": "Venin mortel"}, {"nom": "Corps Gigantesque", "emoji": "🐲", "degats": 60, "desc": "Écrasement"}, {"nom": "Souffle de Glace", "emoji": "❄️", "degats": 65, "desc": "Gel"}], "faiblesse": "⚡", "resistance": "🐉"},
    "toppohakai": {"nom": "Toppo (Hakai)", "emoji": "🟣", "serie": "Dragon Ball Super", "rarete": "Mythique", "pv": 1260, "attaque": 288, "defense": 238, "image": "https://i.imgur.com/fSf1u96.jpg", "attaques": [{"nom": "Pure Hakai", "emoji": "⬛", "degats": 95, "desc": "Destruction pure"}, {"nom": "Destruction Blast", "emoji": "💥", "degats": 90, "desc": "Souffle de destruction"}, {"nom": "God Form", "emoji": "👑", "degats": 100, "desc": "Forme divine"}], "faiblesse": "⚡", "resistance": "🟣"},
    "jonathan": {"nom": "Jonathan Joestar", "emoji": "🤜", "serie": "JoJo", "rarete": "Commun", "pv": 85, "attaque": 16, "defense": 13, "image": "https://i.imgur.com/Tkv1a3e.jpg", "attaques": [{"nom": "Zoom Punch", "emoji": "👊", "degats": 50, "desc": "Poing Hamon allongé"}, {"nom": "Overdrive", "emoji": "🌊", "degats": 55, "desc": "Vague Hamon"}, {"nom": "Big Overdrive", "emoji": "💥", "degats": 65, "desc": "Grande onde Hamon"}], "faiblesse": "⚡", "resistance": "🤜"},
    "narumisho": {"nom": "Narumi Sho", "emoji": "🕵️", "serie": "MHA vigilante", "rarete": "Commun", "pv": 70, "attaque": 13, "defense": 10, "image": "https://i.imgur.com/Uopntmk.jpg", "attaques": [{"nom": "Magie Feu", "emoji": "🔥", "degats": 50, "desc": "Flammes de pompier"}, {"nom": "Samouraï Fire", "emoji": "⚔️", "degats": 55, "desc": "Lame enflammée"}, {"nom": "Phoenix Blow", "emoji": "🌸", "degats": 60, "desc": "Frappe phénix"}], "faiblesse": "⚡", "resistance": "🕵️"},
    "kouichi": {"nom": "Kouichi Haimawari", "emoji": "💨", "serie": "MHA vigilante", "rarete": "Commun", "pv": 68, "attaque": 12, "defense": 10, "image": "https://i.imgur.com/xXCITQ8.jpg", "attaques": [{"nom": "Slide and Glide", "emoji": "💨", "degats": 30, "desc": "Glissement rapide"}, {"nom": "Bounce", "emoji": "🔵", "degats": 35, "desc": "Rebond"}, {"nom": "Mouve Mouve", "emoji": "🌊", "degats": 40, "desc": "Surfeur héroïque"}], "faiblesse": "⚡", "resistance": "💨"},
    "kazuho": {"nom": "Kazuho Haneyama", "emoji": "🦋", "serie": "MHA vigilante", "rarete": "Commun", "pv": 65, "attaque": 11, "defense": 9, "image": "https://i.imgur.com/4OzcWm0.jpg", "attaques": [{"nom": "Pop Step", "emoji": "💃", "degats": 35, "desc": "Saut acrobatique"}, {"nom": "Kick", "emoji": "🦵", "degats": 30, "desc": "Coup de pied"}, {"nom": "Evasion", "emoji": "💨", "degats": 25, "desc": "Esquive rapide"}], "faiblesse": "⚡", "resistance": "🦋"},
    "gideon": {"nom": "Gideon Crossvalid", "emoji": "📚", "serie": "The Beginning After the End", "rarete": "Commun", "pv": 72, "attaque": 13, "defense": 11, "image": "https://i.imgur.com/JzbTwwD.jpg", "attaques": [{"nom": "Analyse Stratégique", "emoji": "🧠", "degats": 45, "desc": "Tactique militaire"}, {"nom": "Command Strike", "emoji": "⚔️", "degats": 50, "desc": "Frappe commandée"}, {"nom": "Shield Wall", "emoji": "🛡️", "degats": 40, "desc": "Mur de boucliers"}], "faiblesse": "⚡", "resistance": "📚"},
    "reginald": {"nom": "Reginald Raizel", "emoji": "🧛", "serie": "Noblesse", "rarete": "Commun", "pv": 80, "attaque": 15, "defense": 12, "image": "https://i.imgur.com/1O2BkZE.jpg", "attaques": [{"nom": "Noble Power", "emoji": "👑", "degats": 65, "desc": "Puissance noble"}, {"nom": "Soul Control", "emoji": "🔮", "degats": 70, "desc": "Contrôle des âmes"}, {"nom": "Physical Strengthen", "emoji": "💪", "degats": 75, "desc": "Force vampirique"}], "faiblesse": "⚡", "resistance": "🧛"},
    "yukimichi": {"nom": "Yukimichi Tsurumi", "emoji": "❄️", "serie": "Sakamoto Days", "rarete": "Commun", "pv": 75, "attaque": 14, "defense": 11, "image": "https://i.imgur.com/JzbTwwD.jpg", "attaques": [{"nom": "Frappe Calculée", "emoji": "🧮", "degats": 40, "desc": "Coup analysé"}, {"nom": "Tactique", "emoji": "🎯", "degats": 35, "desc": "Stratégie"}, {"nom": "Combat Froid", "emoji": "❄️", "degats": 45, "desc": "Attaque sans émotion"}], "faiblesse": "⚡", "resistance": "❄️"},
    "ryou_com": {"nom": "Ryou Kurokiba", "emoji": "🍴", "serie": "Food Wars", "rarete": "Commun", "pv": 65, "attaque": 12, "defense": 9, "image": "https://i.imgur.com/cu3sS8W.jpg", "attaques": [{"nom": "Wild Cooking", "emoji": "🔪", "degats": 50, "desc": "Cuisine sauvage"}, {"nom": "Blood Cuisine", "emoji": "🩸", "degats": 55, "desc": "Plat violent"}, {"nom": "Sea Urchin Pasta", "emoji": "🍝", "degats": 60, "desc": "Plat signature"}], "faiblesse": "⚡", "resistance": "🍴"},
    "fumiya": {"nom": "Fumiya Tomozaki", "emoji": "🎮", "serie": "Bottom-tier Character Tomozaki", "rarete": "Commun", "pv": 55, "attaque": 8, "defense": 7, "image": "https://i.imgur.com/DWeuClR.jpg", "attaques": [{"nom": "Analyse Sociale", "emoji": "🧠", "degats": 25, "desc": "Comprend les gens"}, {"nom": "Stratégie Gaming", "emoji": "🎮", "degats": 30, "desc": "Tactique de jeu"}, {"nom": "Effort Maximal", "emoji": "💪", "degats": 35, "desc": "Progression continue"}], "faiblesse": "⚡", "resistance": "🎮"},
    "joske": {"nom": "Josuke Higashikata", "emoji": "💜", "serie": "JoJo", "rarete": "Rare", "pv": 200, "attaque": 47, "defense": 36, "image": "https://i.imgur.com/EPb3V6Q.jpg", "attaques": [{"nom": "Crazy Diamond", "emoji": "💎", "degats": 60, "desc": "Poing réparateur"}, {"nom": "Crazy Diamond Restore", "emoji": "✨", "degats": 55, "desc": "Restauration offensive"}, {"nom": "Crazy Diamond Fusion", "emoji": "💥", "degats": 70, "desc": "Fusion destructrice"}], "faiblesse": "⚡", "resistance": "💜"},
    "roji": {"nom": "Rohan Kishibe", "emoji": "📓", "serie": "JoJo", "rarete": "Rare", "pv": 190, "attaque": 44, "defense": 33, "image": "https://i.imgur.com/i5KeD6y.jpg", "attaques": [{"nom": "Heaven's Door", "emoji": "📖", "degats": 60, "desc": "Ouvre comme un livre"}, {"nom": "Lecture Forcée", "emoji": "👁️", "degats": 55, "desc": "Lit et modifie"}, {"nom": "Commande Absolue", "emoji": "✍️", "degats": 65, "desc": "Écrit la réalité"}], "faiblesse": "⚡", "resistance": "📓"},
    "gyro": {"nom": "Gyro Zeppeli", "emoji": "🔩", "serie": "JoJo", "rarete": "Rare", "pv": 205, "attaque": 48, "defense": 37, "image": "https://i.imgur.com/8uaa3YP.jpg", "attaques": [{"nom": "Ball Breaker", "emoji": "⚙️", "degats": 60, "desc": "Spin supérieur"}, {"nom": "Trueno Infinito", "emoji": "⚡", "degats": 65, "desc": "Tonnerre infini"}, {"nom": "Tir de Spin", "emoji": "🌀", "degats": 55, "desc": "Projectile rotatif"}], "faiblesse": "⚡", "resistance": "🔩"},
    "mikaela": {"nom": "Mikaela Hyakuya", "emoji": "🧛", "serie": "Owari no Seraph", "rarete": "Rare", "pv": 205, "attaque": 48, "defense": 37, "image": "https://i.imgur.com/lrnezr7.jpg", "attaques": [{"nom": "Épée de Démon", "emoji": "🗡️", "degats": 60, "desc": "Lame démoniaque"}, {"nom": "Sang de Vampire", "emoji": "🩸", "degats": 55, "desc": "Régénération"}, {"nom": "Frappe Vampire", "emoji": "🦇", "degats": 65, "desc": "Vitesse surnaturelle"}], "faiblesse": "⚡", "resistance": "🧛"},
    "yuichiro": {"nom": "Yuichiro Hyakuya", "emoji": "⚔️", "serie": "Owari no Seraph", "rarete": "Rare", "pv": 200, "attaque": 46, "defense": 35, "image": "https://i.imgur.com/CrHTsmJ.jpg", "attaques": [{"nom": "Asuramaru", "emoji": "😈", "degats": 65, "desc": "Démon libéré"}, {"nom": "Technique Cursed Gear", "emoji": "⚔️", "degats": 60, "desc": "Arme maudite"}, {"nom": "Black Demon Series", "emoji": "🖤", "degats": 70, "desc": "Démon suprême"}], "faiblesse": "⚡", "resistance": "⚔️"},
    "nanatsu": {"nom": "Nanatsu Tokushima", "emoji": "🗡️", "serie": "Hell's Paradise", "rarete": "Rare", "pv": 195, "attaque": 45, "defense": 34, "image": "https://i.imgur.com/JzbTwwD.jpg", "attaques": [{"nom": "Magie Feu", "emoji": "🔥", "degats": 45, "desc": "Flammes contrôlées"}, {"nom": "Fire Wall", "emoji": "🧱", "degats": 50, "desc": "Mur de feu"}, {"nom": "Flame Lance", "emoji": "🔥", "degats": 55, "desc": "Lance enflammée"}], "faiblesse": "⚡", "resistance": "🗡️"},
    "sagiri": {"nom": "Sagiri Yamada", "emoji": "⚔️", "serie": "Hell's Paradise", "rarete": "Rare", "pv": 195, "attaque": 45, "defense": 34, "image": "https://i.imgur.com/hnOh7ju.jpg", "attaques": [{"nom": "Tsubaki", "emoji": "⚔️", "degats": 55, "desc": "Lame d'exécuteur"}, {"nom": "Coupe Nette", "emoji": "🗡️", "degats": 60, "desc": "Décapitation"}, {"nom": "Fantôme Tueur", "emoji": "👻", "degats": 50, "desc": "Frappe spectrale"}], "faiblesse": "⚡", "resistance": "⚔️"},
    "gachiaka": {"nom": "Rudo", "emoji": "🗑️", "serie": "Gachiakuta", "rarete": "Rare", "pv": 200, "attaque": 47, "defense": 35, "image": "https://i.imgur.com/OD9tpq7.jpg", "attaques": [{"nom": "Épée Sauvage", "emoji": "⚔️", "degats": 45, "desc": "Lame brute"}, {"nom": "Rage Bestiale", "emoji": "🦁", "degats": 50, "desc": "Fureur animale"}, {"nom": "Instinct", "emoji": "🌑", "degats": 40, "desc": "Combat instinctif"}], "faiblesse": "⚡", "resistance": "🗑️"},
    "tadashi": {"nom": "Tadashi Kariya", "emoji": "🪡", "serie": "Gachiakuta", "rarete": "Rare", "pv": 192, "attaque": 44, "defense": 33, "image": "https://i.imgur.com/JzbTwwD.jpg", "attaques": [{"nom": "Bitto", "emoji": "🦟", "degats": 55, "desc": "Moustiques de Nen"}, {"nom": "Blood Drain", "emoji": "🩸", "degats": 60, "desc": "Aspiration de sang"}, {"nom": "Poison Bite", "emoji": "☠️", "degats": 65, "desc": "Morsure empoisonnée"}], "faiblesse": "⚡", "resistance": "🪡"},
    "soma_r": {"nom": "Soma Yukihira", "emoji": "🍳", "serie": "Food Wars", "rarete": "Rare", "pv": 182, "attaque": 42, "defense": 31, "image": "https://i.imgur.com/OWRs0x0.jpg", "attaques": [{"nom": "Furikake Rice", "emoji": "🍚", "degats": 45, "desc": "Plat surprise"}, {"nom": "Salmon Roast", "emoji": "🐟", "degats": 50, "desc": "Cuisson parfaite"}, {"nom": "Yukihira Style", "emoji": "🍳", "degats": 55, "desc": "Cuisine rebelle"}], "faiblesse": "⚡", "resistance": "🍳"},
    "alice_r": {"nom": "Alice Nakiri", "emoji": "🔬", "serie": "Food Wars", "rarete": "Rare", "pv": 185, "attaque": 43, "defense": 32, "image": "https://i.imgur.com/mUnqSa3.jpg", "attaques": [{"nom": "Cuisine Moléculaire", "emoji": "🧪", "degats": 55, "desc": "Science culinaire"}, {"nom": "Deconstruction", "emoji": "⚗️", "degats": 60, "desc": "Décomposition parfaite"}, {"nom": "Alice's World", "emoji": "🌍", "degats": 65, "desc": "Plat mondial"}], "faiblesse": "⚡", "resistance": "🔬"},
    "sen_r": {"nom": "Erina Nakiri", "emoji": "👑", "serie": "Food Wars", "rarete": "Rare", "pv": 183, "attaque": 42, "defense": 31, "image": "https://i.imgur.com/wZ8mpoH.jpg", "attaques": [{"nom": "God's Tongue", "emoji": "👅", "degats": 60, "desc": "Palais divin"}, {"nom": "Critique Divine", "emoji": "⚡", "degats": 65, "desc": "Jugement suprême"}, {"nom": "Nakiri Style", "emoji": "👑", "degats": 70, "desc": "Excellence absolue"}], "faiblesse": "⚡", "resistance": "👑"},
    "hakari": {"nom": "Kinji Hakari", "emoji": "🎰", "serie": "Jujutsu Kaisen", "rarete": "Rare", "pv": 205, "attaque": 48, "defense": 37, "image": "https://i.imgur.com/EWUa6kE.jpg", "attaques": [{"nom": "Jackpot Idle Death Gamble", "emoji": "🎰", "degats": 75, "desc": "Jackpot mortel"}, {"nom": "Cursed Technique Reversal", "emoji": "♾️", "degats": 70, "desc": "Inversion de technique"}, {"nom": "Unlimited Rotation", "emoji": "🌀", "degats": 80, "desc": "Rotation infinie"}], "faiblesse": "⚡", "resistance": "🎰"},
    "higuruma": {"nom": "Hiromi Higuruma", "emoji": "⚖️", "serie": "Jujutsu Kaisen", "rarete": "Rare", "pv": 198, "attaque": 46, "defense": 35, "image": "https://i.imgur.com/bzmXdQf.jpg", "attaques": [{"nom": "Deadly Sentencing", "emoji": "⚖️", "degats": 65, "desc": "Sentence mortelle"}, {"nom": "Extase", "emoji": "🪄", "degats": 70, "desc": "Confiscation d'arme"}, {"nom": "Gavel of Judgement", "emoji": "🔨", "degats": 60, "desc": "Marteau judiciaire"}], "faiblesse": "⚡", "resistance": "⚖️"},
    "angel": {"nom": "Rin Suzunome", "emoji": "🎵", "serie": "Wistoria", "rarete": "Rare", "pv": 190, "attaque": 44, "defense": 33, "image": "https://i.imgur.com/JzbTwwD.jpg", "attaques": [{"nom": "Analyse", "emoji": "🧠", "degats": 30, "desc": "Observation tactique"}, {"nom": "Frappe Technique", "emoji": "🎯", "degats": 35, "desc": "Coup précis"}, {"nom": "Soutien", "emoji": "✨", "degats": 25, "desc": "Aide alliés"}], "faiblesse": "⚡", "resistance": "🎵"},
    "will": {"nom": "Will Serfort", "emoji": "⚡", "serie": "Wistoria", "rarete": "Rare", "pv": 205, "attaque": 48, "defense": 37, "image": "https://i.imgur.com/CXSqYtO.jpg", "attaques": [{"nom": "Magie Feu", "emoji": "🔥", "degats": 50, "desc": "Flammes académiques"}, {"nom": "Fire Lance", "emoji": "🔥", "degats": 55, "desc": "Lance enflammée"}, {"nom": "Inferno", "emoji": "🌋", "degats": 60, "desc": "Brasier intense"}], "faiblesse": "⚡", "resistance": "⚡"},
    "mimasaka": {"nom": "Subaru Mimasaka", "emoji": "🪞", "serie": "Food Wars", "rarete": "Rare", "pv": 188, "attaque": 44, "defense": 33, "image": "https://i.imgur.com/KsiSZog.jpg", "attaques": [{"nom": "Imitation Parfaite", "emoji": "👤", "degats": 60, "desc": "Copie exacte"}, {"nom": "Copy Strike", "emoji": "🎭", "degats": 65, "desc": "Attaque copiée"}, {"nom": "Predict and Strike", "emoji": "🔮", "degats": 70, "desc": "Prédit et frappe"}], "faiblesse": "⚡", "resistance": "🪞"},
    "mucho": {"nom": "Mucho", "emoji": "🩸", "serie": "Tokyo Revengers", "rarete": "Rare", "pv": 200, "attaque": 47, "defense": 36, "image": "https://i.imgur.com/JzbTwwD.jpg", "attaques": [{"nom": "String String", "emoji": "🧵", "degats": 55, "desc": "Fils tranchants"}, {"nom": "Thread Bind", "emoji": "🔒", "degats": 50, "desc": "Ligotage"}, {"nom": "Thread Slash", "emoji": "✂️", "degats": 60, "desc": "Coupe les fils"}], "faiblesse": "⚡", "resistance": "🩸"},
    "kokonoi": {"nom": "Kokonoi Hajime", "emoji": "💰", "serie": "Tokyo Revengers", "rarete": "Rare", "pv": 193, "attaque": 45, "defense": 34, "image": "https://i.imgur.com/T0L4mb4.jpg", "attaques": [{"nom": "Finance Strike", "emoji": "💴", "degats": 40, "desc": "Richesse en attaque"}, {"nom": "Money Rain", "emoji": "💰", "degats": 45, "desc": "Pluie d'argent"}, {"nom": "Cold Calculation", "emoji": "🧊", "degats": 50, "desc": "Coup calculé"}], "faiblesse": "⚡", "resistance": "💰"},
    "gabuep": {"nom": "Gabimaru (Ninja)", "emoji": "🔥", "serie": "Hell's Paradise", "rarete": "Épique", "pv": 430, "attaque": 97, "defense": 79, "image": "https://i.imgur.com/n2oz8Dn.jpg", "attaques": [{"nom": "Hollow Strike", "emoji": "🔥", "degats": 70, "desc": "Frappe vide"}, {"nom": "Fire Jutsu", "emoji": "🌋", "degats": 75, "desc": "Jutsu enflammé"}, {"nom": "Assassination Art", "emoji": "🗡️", "degats": 80, "desc": "Art de l'assassin"}], "faiblesse": "⚡", "resistance": "🔥"},
    "nagumofull": {"nom": "Nagumo Hajime (Full)", "emoji": "⚙️", "serie": "Arifureta", "rarete": "Épique", "pv": 445, "attaque": 101, "defense": 83, "image": "https://i.imgur.com/6PkjK1t.jpg", "attaques": [{"nom": "Broken Limit", "emoji": "💥", "degats": 85, "desc": "Limite brisée"}, {"nom": "Death Hammer", "emoji": "🔨", "degats": 90, "desc": "Marteau de mort"}, {"nom": "Abyss Power", "emoji": "🌑", "degats": 95, "desc": "Pouvoir de l'abîme"}], "faiblesse": "⚡", "resistance": "⚙️"},
    "jiroep": {"nom": "Jiro Yamada", "emoji": "🎵", "serie": "Sakamoto Days", "rarete": "Épique", "pv": 415, "attaque": 93, "defense": 76, "image": "https://i.imgur.com/JzbTwwD.jpg", "attaques": [{"nom": "Coup Ordinaire", "emoji": "👊", "degats": 25, "desc": "Frappe normale"}, {"nom": "Défense", "emoji": "🛡️", "degats": 20, "desc": "Parade"}, {"nom": "Attaque Simple", "emoji": "⚔️", "degats": 30, "desc": "Combat basique"}], "faiblesse": "⚡", "resistance": "🎵"},
    "izanaep": {"nom": "Izana Kurokawa (Pleine Puissance)", "emoji": "🦋", "serie": "Tokyo Revengers", "rarete": "Épique", "pv": 440, "attaque": 100, "defense": 82, "image": "https://i.imgur.com/sbsK3sl.jpg", "attaques": [{"nom": "Sabre du Roi", "emoji": "⚔️", "degats": 70, "desc": "Lame de Tokyo Manji"}, {"nom": "Frappe Royale", "emoji": "👑", "degats": 75, "desc": "Coup de chef"}, {"nom": "Rage de Roi", "emoji": "💥", "degats": 80, "desc": "Colère absolue"}], "faiblesse": "⚡", "resistance": "🦋"},
    "hantaep": {"nom": "Hanta Sero (Full)", "emoji": "🧻", "serie": "My Hero Academia", "rarete": "Épique", "pv": 400, "attaque": 90, "defense": 73, "image": "https://i.imgur.com/JzbTwwD.jpg", "attaques": [{"nom": "Tape Full Cowl", "emoji": "🟫", "degats": 55, "desc": "Bande pleine puissance"}, {"nom": "Cellophane Shoot", "emoji": "🎯", "degats": 60, "desc": "Tir de bande"}, {"nom": "Ultimate Wrap", "emoji": "🌀", "degats": 65, "desc": "Enroulement total"}], "faiblesse": "⚡", "resistance": "🧻"},
    "kanaep": {"nom": "Kanao Tsuyuri (Full)", "emoji": "🌸", "serie": "Demon Slayer", "rarete": "Épique", "pv": 430, "attaque": 97, "defense": 79, "image": "https://i.imgur.com/wDD0iSX.jpg", "attaques": [{"nom": "Flower Breathing Final Form", "emoji": "🌸", "degats": 75, "desc": "Forme finale fleur"}, {"nom": "Scarlet Spider Lily", "emoji": "🌺", "degats": 80, "desc": "Lys araignée écarlate"}, {"nom": "See-Through World", "emoji": "👁️", "degats": 85, "desc": "Monde transparent"}], "faiblesse": "⚡", "resistance": "🌸"},
    "genyaep": {"nom": "Genya Shinazugawa (Full)", "emoji": "🔫", "serie": "Demon Slayer", "rarete": "Épique", "pv": 435, "attaque": 98, "defense": 80, "image": "https://i.imgur.com/AaQT1PZ.jpg", "attaques": [{"nom": "Rengoku", "emoji": "🔥", "degats": 70, "desc": "Purgatoire"}, {"nom": "Demon Power", "emoji": "😈", "degats": 75, "desc": "Pouvoir démoniaque"}, {"nom": "Full Demon Form", "emoji": "👹", "degats": 80, "desc": "Forme démon totale"}], "faiblesse": "⚡", "resistance": "🔫"},
    "volcanica": {"nom": "Volcanica", "emoji": "🐉", "serie": "Re:Zero", "rarete": "Légendaire", "pv": 760, "attaque": 175, "defense": 142, "image": "https://i.imgur.com/JzbTwwD.jpg", "attaques": [{"nom": "Souffle de Dragon", "emoji": "🔥", "degats": 75, "desc": "Feu draconique"}, {"nom": "Scale Armor", "emoji": "🐉", "degats": 65, "desc": "Défense écailleuse"}, {"nom": "Dragon Roar", "emoji": "👾", "degats": 70, "desc": "Rugissement destructeur"}], "faiblesse": "⚡", "resistance": "🐉"},
    "rikiep": {"nom": "Riki Nura", "emoji": "👺", "serie": "Nurarihyon no Mago", "rarete": "Légendaire", "pv": 730, "attaque": 167, "defense": 135, "image": "https://i.imgur.com/JzbTwwD.jpg", "attaques": [{"nom": "Magie Vent", "emoji": "🌬️", "degats": 45, "desc": "Rafale de vent"}, {"nom": "Storm Blade", "emoji": "⚔️", "degats": 50, "desc": "Lame de tempête"}, {"nom": "Gale Force", "emoji": "🌪️", "degats": 55, "desc": "Force du vent"}], "faiblesse": "⚡", "resistance": "👺"},
    "arthurl": {"nom": "Arthur Leywin (Dragon)", "emoji": "🐉", "serie": "The Beginning After the End", "rarete": "Légendaire", "pv": 745, "attaque": 171, "defense": 139, "image": "https://i.imgur.com/zJikG6Q.jpg", "attaques": [{"nom": "Dragon Heritage", "emoji": "🐉", "degats": 85, "desc": "Héritage draconique"}, {"nom": "Destruction", "emoji": "💥", "degats": 90, "desc": "Destruction pure"}, {"nom": "Absolute Void", "emoji": "🌑", "degats": 95, "desc": "Vide sans fond"}], "faiblesse": "⚡", "resistance": "🐉"},
    "takemichi_l": {"nom": "Takemichi (Futur)", "emoji": "⏰", "serie": "Tokyo Revengers", "rarete": "Légendaire", "pv": 720, "attaque": 165, "defense": 133, "image": "https://i.imgur.com/sbsK3sl.jpg", "attaques": [{"nom": "Time Leap Strike", "emoji": "⏰", "degats": 65, "desc": "Frappe temporelle"}, {"nom": "Resolve Punch", "emoji": "💪", "degats": 70, "desc": "Poing de résolution"}, {"nom": "Final Stand", "emoji": "🔥", "degats": 75, "desc": "Dernier combat"}], "faiblesse": "⚡", "resistance": "⏰"},
    "reinmyth": {"nom": "Reinhard van Astrea (Divine)", "emoji": "⚔️", "serie": "Re:Zero", "rarete": "Mythique", "pv": 1380, "attaque": 316, "defense": 263, "image": "https://i.imgur.com/DDdI6qL.jpg", "attaques": [{"nom": "Divine Protection", "emoji": "✨", "degats": 90, "desc": "Protection divine"}, {"nom": "Sword Saint", "emoji": "⚔️", "degats": 95, "desc": "Saint épéiste"}, {"nom": "Dragon Sword", "emoji": "🐉", "degats": 100, "desc": "Épée du dragon"}], "faiblesse": "⚡", "resistance": "⚔️"},
    "diavolo": {"nom": "Diavolo (King Crimson)", "emoji": "💀", "serie": "JoJo", "rarete": "Mythique", "pv": 1280, "attaque": 292, "defense": 242, "image": "https://i.imgur.com/FNa1SzP.jpg", "attaques": [{"nom": "Time Erasure", "emoji": "⏩", "degats": 85, "desc": "Efface le temps"}, {"nom": "Epitaph Vision", "emoji": "👁️", "degats": 80, "desc": "Vision prophétique"}, {"nom": "Killer Punch", "emoji": "💥", "degats": 90, "desc": "Poing du roi"}], "faiblesse": "⚡", "resistance": "💀"},
    "pucci": {"nom": "Enrico Pucci (Made in Heaven)", "emoji": "⏰", "serie": "JoJo", "rarete": "Mythique", "pv": 1300, "attaque": 298, "defense": 248, "image": "https://i.imgur.com/owvBCPl.jpg", "attaques": [{"nom": "Time Acceleration", "emoji": "⏰", "degats": 90, "desc": "Vitesse absolue"}, {"nom": "Universe Reset", "emoji": "🌌", "degats": 95, "desc": "Reset cosmique"}, {"nom": "Made in Heaven", "emoji": "✨", "degats": 100, "desc": "Perfection ultime"}], "faiblesse": "⚡", "resistance": "⏰"},
    "toppo": {"nom": "Toppo", "serie": "Dragon Ball Super", "rarete": "Épique", "emoji": "🏋️", "pv": 280, "attaque": 110, "defense": 95, "image": "https://i.imgur.com/fSf1u96.jpg", "attaques": [{"nom": "Justice Kick", "emoji": "🦵", "degats": 70, "desc": "Coup de justice"}, {"nom": "Hakai", "emoji": "⬛", "degats": 90, "desc": "Destruction divine"}, {"nom": "God of Destruction Energy", "emoji": "💥", "degats": 85, "desc": "Énergie destructrice"}], "faiblesse": "🌀", "resistance": "⚡"},
    "reinhard_van_astrea": {"nom": "Reinhard van Astrea", "serie": "Re:Zero", "rarete": "Mythique", "emoji": "⚔️", "pv": 380, "attaque": 140, "defense": 130, "image": "https://i.imgur.com/DDdI6qL.jpg", "attaques": [{"nom": "Attaque Ultime", "emoji": "💥", "degats": 80, "desc": "Puissance absolue"}, {"nom": "Domination", "emoji": "👑", "degats": 70, "desc": "Contrôle total"}, {"nom": "Destruction", "emoji": "💀", "degats": 90, "desc": "Fin de partie"}], "faiblesse": "🌀", "resistance": "⚡"},
    "diavolo": {"nom": "Diavolo", "serie": "JoJo's Bizarre Adventure", "rarete": "Légendaire", "emoji": "👑", "pv": 290, "attaque": 115, "defense": 100, "image": "https://i.imgur.com/FNa1SzP.jpg", "attaques": [{"nom": "King Crimson", "emoji": "⏩", "degats": 75, "desc": "Efface le futur"}, {"nom": "Epitaph", "emoji": "👁️", "degats": 70, "desc": "Prévoit l'avenir"}, {"nom": "Time Skip", "emoji": "⏱️", "degats": 80, "desc": "Saut temporel"}], "faiblesse": "🌀", "resistance": "⚡"},
    "enrico_pucci": {"nom": "Enrico Pucci", "serie": "JoJo's Bizarre Adventure", "rarete": "Légendaire", "emoji": "⏳", "pv": 270, "attaque": 120, "defense": 95, "image": "https://i.imgur.com/owvBCPl.jpg", "attaques": [{"nom": "Whitesnake", "emoji": "🐍", "degats": 70, "desc": "Stand venimeux"}, {"nom": "C-Moon", "emoji": "🌙", "degats": 80, "desc": "Inverser gravité"}, {"nom": "Made in Heaven", "emoji": "⏰", "degats": 90, "desc": "Accélération du temps"}], "faiblesse": "🌀", "resistance": "⚡"},
    "arthur_leywin": {"nom": "Arthur Leywin", "serie": "The Beginning After the End", "rarete": "Légendaire", "emoji": "⚡", "pv": 300, "attaque": 125, "defense": 110, "image": "https://i.imgur.com/zJikG6Q.jpg", "attaques": [{"nom": "Destruction Rune", "emoji": "⚡", "degats": 70, "desc": "Rune destructrice"}, {"nom": "Absolute Void", "emoji": "🌑", "degats": 80, "desc": "Vide absolu"}, {"nom": "Seraphic Gate", "emoji": "✨", "degats": 85, "desc": "Portail séraphique"}], "faiblesse": "🌀", "resistance": "⚡"},
    "naofumi": {"nom": "Naofumi", "serie": "The Rising of the Shield Hero", "rarete": "Épique", "emoji": "🛡️", "pv": 240, "attaque": 80, "defense": 130, "image": "https://i.imgur.com/dsFYYLS.jpg", "attaques": [{"nom": "Iron Maiden", "emoji": "🛡️", "degats": 65, "desc": "Armure de fer"}, {"nom": "Shield Prison", "emoji": "🔒", "degats": 70, "desc": "Prison de bouclier"}, {"nom": "Wrath Shield", "emoji": "🔥", "degats": 75, "desc": "Bouclier de colère"}], "faiblesse": "🌀", "resistance": "⚡"},
    "ruijerd": {"nom": "Ruijerd", "serie": "Mushoku Tensei", "rarete": "Épique", "emoji": "💚", "pv": 270, "attaque": 115, "defense": 95, "image": "https://i.imgur.com/NpLm3dY.jpg", "attaques": [{"nom": "Spear Technique", "emoji": "🔱", "degats": 65, "desc": "Technique de lance"}, {"nom": "Dead End Lance", "emoji": "💀", "degats": 75, "desc": "Lance de fin"}, {"nom": "Superd's Pride", "emoji": "💚", "degats": 70, "desc": "Fierté des Superd"}], "faiblesse": "🌀", "resistance": "⚡"},
    "takemichi": {"nom": "Takemichi", "serie": "Tokyo Revengers", "rarete": "Rare", "emoji": "🔥", "pv": 170, "attaque": 75, "defense": 80, "image": "https://i.imgur.com/sbsK3sl.jpg", "attaques": [{"nom": "Fist of Tears", "emoji": "😢", "degats": 50, "desc": "Poing des larmes"}, {"nom": "Never Give Up", "emoji": "💪", "degats": 55, "desc": "Jamais abandonner"}, {"nom": "Future Memory", "emoji": "🔮", "degats": 60, "desc": "Mémoire du futur"}], "faiblesse": "🌀", "resistance": "⚡"},
    "gabimaru": {"nom": "Gabimaru", "serie": "Hell's Paradise", "rarete": "Épique", "emoji": "🔥", "pv": 265, "attaque": 120, "defense": 85, "image": "https://i.imgur.com/n2oz8Dn.jpg", "attaques": [{"nom": "Ninpou: Iwa Haru", "emoji": "🔥", "degats": 65, "desc": "Jutsu de feu"}, {"nom": "Ninpou: Arashi", "emoji": "💨", "degats": 70, "desc": "Jutsu de vent"}, {"nom": "Shinobi Strike", "emoji": "🗡️", "degats": 75, "desc": "Frappe de ninja"}], "faiblesse": "🌀", "resistance": "⚡"},
    "nagumo": {"nom": "Nagumo", "serie": "Arifureta", "rarete": "Légendaire", "emoji": "🔫", "pv": 290, "attaque": 130, "defense": 100, "image": "https://i.imgur.com/6PkjK1t.jpg", "attaques": [{"nom": "Schlagen Firm", "emoji": "🔫", "degats": 70, "desc": "Canon solide"}, {"nom": "Cross Velts", "emoji": "⚔️", "degats": 75, "desc": "Épées croisées"}, {"nom": "Arifureta Style", "emoji": "💀", "degats": 80, "desc": "Style sans pitié"}], "faiblesse": "🌀", "resistance": "⚡"},
}

# ============================================================
#  🎰 GACHA — Système style Mudae
# ============================================================

# Collections et fusions
gacha_collections = defaultdict(dict)   # {uid: {card_key: {"fusion": 0}}}
fusion_levels = defaultdict(lambda: defaultdict(int))  # {uid: {card_key: level}}

# Cartes claimées sur le serveur — uniques
claimed_cards = {}   # {card_key: user_id}
collection_order = {}  # {uid: [card_key, ...]} — ordre perso de la collection

# Rolls
ROLLS_MAX = 10
ROLLS_RESET_HOURS = 6        # Admin peut modifier via .setrollreset
roll_data = defaultdict(lambda: {"rolls": ROLLS_MAX, "last_reset": 0.0, "daily_used": False, "daily_reset": 0.0})

# Claim cooldown
CLAIM_COOLDOWN_MINUTES = 30  # Peut être réduit via shop
claim_cooldown = defaultdict(float)   # {uid: last_claim_timestamp}
claim_reduction = defaultdict(int)    # {uid: minutes de réduction achetés}
gacha_wishlist = defaultdict(set)     # {uid: {card_key, ...}}
claim_freeze = {}       # {uid: unfreeze_timestamp}
claim_curse = {}       # {uid: curse_end_timestamp}
shield_active = {}     # {uid: shield_end_timestamp}
rarity_boost = {}      # {uid: rolls_restants_avec_boost}
daily_item_usage = defaultdict(lambda: defaultdict(float))  # {uid: {item_id: last_use_timestamp}}

# Probabilités gacha
RARETE_EMOJI = {
    "Mythique":   "🔴",
    "Légendaire": "🟠",
    "Épique":     "🟣",
    "Rare":       "🔵",
    "Commun":     "⚪",
}

RARETE_COULEURS = {
    "Mythique":   0xe74c3c,
    "Légendaire": 0xe67e22,
    "Épique":     0x9b59b6,
    "Rare":       0x3498db,
    "Commun":     0x95a5a6,
}

GACHA_RATES = {
    "Mythique":   5,     # ~0.05%
    "Légendaire": 70,    # ~0.7%
    "Épique":     500,   # ~5%
    "Rare":       2200,  # ~22%
    "Commun":     7215,  # ~72.15%
}

def gacha_tirage(boost=False):
    """Tire une carte dispo (non claimée) selon les probabilités"""
    available = [k for k in ANIME_CARDS_DB if k not in claimed_cards]
    if not available:
        return None
    rates = dict(GACHA_RATES)
    if boost:
        rates["Commun"] = 50
        rates["Rare"] = 80
        rates["Épique"] = 40
        rates["Légendaire"] = 20
        rates["Mythique"] = 5
    pool = []
    for key in available:
        c = ANIME_CARDS_DB[key]
        rarete = c["rarete"] if c["rarete"] in rates else "Commun"
        pool.extend([key] * rates[rarete])
    return random.choice(pool) if pool else None

def get_roll_cooldown_seconds(uid):
    """Retourne le temps restant avant reset des rolls en secondes"""
    import time
    data = roll_data[uid]
    elapsed = time.time() - data["last_reset"]
    total = ROLLS_RESET_HOURS * 3600
    remaining = total - elapsed
    return max(0, remaining)

def get_claim_cooldown_seconds(uid):
    """Retourne le temps restant avant pouvoir claim"""
    import time
    now_t = time.time()
    cooldown = max(0, CLAIM_COOLDOWN_MINUTES - claim_reduction[uid])
    # Malédiction active ? +5 min
    if uid in claim_curse and claim_curse[uid] > now_t:
        cooldown += 5
    elapsed = now_t - claim_cooldown[uid]
    remaining = (cooldown * 60) - elapsed
    return max(0, remaining)

def build_gacha_embed(uid, key, rolls_left):
    """Construit l'embed de tirage gacha style Mudae"""
    import time
    c = ANIME_CARDS_DB[key]
    level = fusion_levels[uid][key]
    rarete_emoji = RARETE_EMOJI.get(c["rarete"], "🔵")
    couleur = RARETE_COULEURS.get(c["rarete"], 0x95a5a6)
    stars = "⭐" * level if level > 0 else ""

    boost_atk = level * 15
    boost_def = level * 10
    boost_pv = level * 20

    embed = discord.Embed(
        title=f"{c['emoji']} {c['nom']} {stars}",
        description=f"*{c['serie']}* {rarete_emoji} **{c['rarete']}**",
        color=couleur
    )

    image = c.get("image")
    if image:
        embed.set_image(url=image)

    embed.add_field(
        name="📊 Stats",
        value=f"❤️ **{c['pv'] + boost_pv}** PV | ⚔️ **{c['attaque'] + boost_atk}** ATK | 🛡️ **{c['defense'] + boost_def}** DEF",
        inline=False
    )

    attaques_str = "\n".join([
        f"{a['emoji']} **{a['nom']}** — `{a['degats']} dégâts`"
        for a in c["attaques"]
    ])
    embed.add_field(name="⚔️ Attaques", value=attaques_str, inline=False)
    embed.set_footer(text=f"🎰 Rolls restants : {rolls_left} • ❤️ Claim en 30s • .rolls pour voir tes rolls")
    return embed

@bot.command(name="ga", aliases=["g", "roll", "r"])
async def ga_cmd(ctx):
    """Tire une carte gacha — .ga"""
    import time

    # Vérif salon
    if SALON_GACHA_ID and ctx.channel.id != SALON_GACHA_ID:
        salon = ctx.guild.get_channel(SALON_GACHA_ID)
        mention = salon.mention if salon else "le salon gacha"
        return await ctx.send(f"🎰 Le gacha c'est dans {mention} !", delete_after=5)

    uid = str(ctx.author.id)
    now = time.time()
    data = roll_data[uid]

    # Reset rolls si délai écoulé
    if now - data["last_reset"] >= ROLLS_RESET_HOURS * 3600:
        data["rolls"] = ROLLS_MAX
        data["last_reset"] = now

    if data["rolls"] <= 0:
        remaining = get_roll_cooldown_seconds(uid)
        h = int(remaining // 3600)
        m = int((remaining % 3600) // 60)
        return await ctx.send(
            f"❌ Plus de rolls ! Recharge dans **{h}h{m:02d}min**\n"
            f"💡 Achète +10 rolls en boutique avec `.shop`",
            delete_after=10
        )

    data["rolls"] -= 1
    # Boost rareté actif ?
    boost_actif = uid in rarity_boost and rarity_boost[uid] > 0
    key = gacha_tirage(boost=boost_actif)
    if boost_actif:
        rarity_boost[uid] -= 1
        if rarity_boost[uid] <= 0:
            del rarity_boost[uid]

    if not key:
        return await ctx.send("😮 Toutes les cartes ont été claimées ! Les admins peuvent ajouter de nouveaux persos.")

    c = ANIME_CARDS_DB[key]
    already_owned = uid in [v for v in claimed_cards.values()] and key in [k for k, v in claimed_cards.items() if v == uid]
    already_claimed_by_other = key in claimed_cards and claimed_cards[key] != uid

    embed = build_gacha_embed(uid, key, data["rolls"])

    # Emoji selon si déjà claimée
    if already_claimed_by_other or already_owned:
        react_emoji = "⚡"
    else:
        react_emoji = "❤️"

    msg = await ctx.send(embed=embed)
    await msg.add_reaction(react_emoji)

    # Ping wishlist au drop
    if react_emoji == "❤️":
        wishers = []
        for wuid, wlist in gacha_wishlist.items():
            if key in wlist:
                member = ctx.guild.get_member(int(wuid))
                if member:
                    wishers.append(member.mention)
        if wishers:
            await ctx.send(
                f"🌟 {' '.join(wishers)} — **{c['nom']}** de ta wishlist vient de drop ! Vite ! ❤️",
                delete_after=28
            )

    if react_emoji == "❤️":
        def check(reaction, user):
            return (
                str(reaction.emoji) == "❤️"
                and reaction.message.id == msg.id
                and not user.bot
            )

        try:
            reaction, claimer = await bot.wait_for("reaction_add", check=check, timeout=30)
            claimer_uid = str(claimer.id)

            # Vérif claim cooldown
            claim_remaining = get_claim_cooldown_seconds(claimer_uid)
            if claim_remaining > 0:
                mins = int(claim_remaining // 60)
                secs = int(claim_remaining % 60)
                return await ctx.send(
                    f"⏳ {claimer.mention} doit attendre encore **{mins}m{secs:02d}s** avant de claim !",
                    delete_after=8
                )

            # Claim !
            claimed_cards[key] = claimer_uid
            claim_cooldown[claimer_uid] = time.time()

            if key not in gacha_collections[claimer_uid]:
                gacha_collections[claimer_uid][key] = {"fusion": 0}

            # Message public de claim
            rarete_emoji_pub = RARETE_EMOJI.get(c["rarete"], "🔵")
            await ctx.send(f"🎴 **{claimer.display_name}** vient de claim **{c['nom']}** {rarete_emoji_pub} !")

            # Mettre à jour l'embed
            level = fusion_levels[claimer_uid][key]
            stars = "⭐" * level if level > 0 else ""
            rarete_emoji = RARETE_EMOJI.get(c["rarete"], "🔵")
            couleur = RARETE_COULEURS.get(c["rarete"], 0x95a5a6)

            claimed_embed = discord.Embed(
                title=f"{c['emoji']} {c['nom']} {stars} — Claimé ! ✅",
                description=f"*{c['serie']}* {rarete_emoji} **{c['rarete']}**\n\n💜 **{claimer.display_name}** a claimé cette carte !",
                color=couleur
            )
            if c.get("image"):
                claimed_embed.set_image(url=c["image"])
            claimed_embed.set_footer(text=f"❤️ Claim reset dans {CLAIM_COOLDOWN_MINUTES - claim_reduction[claimer_uid]} min • .gachastock pour voir ta collection")
            await msg.edit(embed=claimed_embed)
            try:
                await msg.clear_reactions()
            except:
                pass

            # Ping wishlist — notifier les joueurs qui voulaient cette carte
            wishlist_pings = []
            for wuid, wlist in gacha_wishlist.items():
                if key in wlist and wuid != claimer_uid:
                    member = msg.guild.get_member(int(wuid))
                    if member:
                        wishlist_pings.append(member.mention)
            if wishlist_pings:
                await msg.channel.send(
                    f"💔 {' '.join(wishlist_pings)} — **{c['nom']}** de ta wishlist vient d'être claimé par **{claimer.display_name}** !",
                    delete_after=15
                )

        except asyncio.TimeoutError:
            # Personne n'a claimé — garder l'embed intact, juste retirer les réactions
            try:
                await msg.clear_reactions()
                rarete_emoji = RARETE_EMOJI.get(c["rarete"], "🔵")
                couleur = RARETE_COULEURS.get(c["rarete"], 0x95a5a6)
                level = fusion_levels[uid][key]
                stars = "⭐" * level if level > 0 else ""
                boost_atk = level * 15
                boost_def = level * 10
                boost_pv  = level * 20
                expired_embed = discord.Embed(
                    title=f"{c['emoji']} {c['nom']} {stars}",
                    description=f"*{c['serie']}* {rarete_emoji} **{c['rarete']}**",
                    color=couleur
                )
                if c.get("image"):
                    expired_embed.set_image(url=c["image"])
                expired_embed.add_field(
                    name="📊 Stats",
                    value=f"❤️ **{c['pv']+boost_pv}** PV | ⚔️ **{c['attaque']+boost_atk}** ATK | 🛡️ **{c['defense']+boost_def}** DEF",
                    inline=False
                )
                attaques_str = "\n".join([
                    f"{a['emoji']} **{a['nom']}** — `{a['degats']} dégâts`"
                    for a in c["attaques"]
                ])
                expired_embed.add_field(name="⚔️ Attaques", value=attaques_str, inline=False)
                expired_embed.set_footer(text="⏰ Claim expiré — personne n'a réclamé cette carte !")
                await msg.edit(embed=expired_embed)
            except:
                pass

@bot.command(name="rolls", aliases=["ro"])
async def rolls_cmd(ctx):
    """Voir tes rolls restants — .rolls"""
    import time

    if SALON_GACHA_ID and ctx.channel.id != SALON_GACHA_ID:
        salon = ctx.guild.get_channel(SALON_GACHA_ID)
        mention = salon.mention if salon else "le salon gacha"
        return await ctx.send(f"🎰 Le gacha c'est dans {mention} !", delete_after=5)

    uid = str(ctx.author.id)
    now = time.time()
    data = roll_data[uid]

    # Reset rolls si délai écoulé
    if now - data["last_reset"] >= ROLLS_RESET_HOURS * 3600:
        data["rolls"] = ROLLS_MAX
        data["last_reset"] = now

    rolls_left = data["rolls"]
    roll_remaining = get_roll_cooldown_seconds(uid)
    rh = int(roll_remaining // 3600)
    rm = int((roll_remaining % 3600) // 60)

    claim_remaining = get_claim_cooldown_seconds(uid)
    cm = int(claim_remaining // 60)
    cs = int(claim_remaining % 60)

    cooldown_claim = max(0, CLAIM_COOLDOWN_MINUTES - claim_reduction[uid])

    embed = discord.Embed(title=f"🎰 Rolls de {ctx.author.display_name}", color=0x9b59b6)
    embed.add_field(
        name="🎲 Rolls",
        value=f"**{rolls_left}/{ROLLS_MAX}** disponibles\n"
              + (f"Recharge dans **{rh}h{rm:02d}min**" if rolls_left < ROLLS_MAX else "✅ Rechargé !"),
        inline=True
    )
    embed.add_field(
        name="❤️ Claim",
        value=f"Cooldown : **{cooldown_claim} min**\n"
              + (f"Dispo dans **{cm}m{cs:02d}s**" if claim_remaining > 0 else "✅ Prêt à claim !"),
        inline=True
    )
    daily_remaining = 86400 - (now - data["daily_reset"])
    dr = int(daily_remaining // 3600)
    dm = int((daily_remaining % 3600) // 60)
    embed.add_field(
        name="🎁 Daily",
        value="✅ Disponible !" if not data["daily_used"] else f"⏳ Dans **{dr}h{dm:02d}min**",
        inline=True
    )
    await ctx.send(embed=embed)

@bot.command(name="setrollreset")
@commands.has_permissions(administrator=True)
async def setrollreset(ctx, heures: int = None):
    """Configure le temps de recharge des rolls — .setrollreset <heures>"""
    global ROLLS_RESET_HOURS
    if not heures or heures < 1 or heures > 24:
        return await ctx.send("❌ Précise un nombre d'heures entre 1 et 24 ! Ex: `.setrollreset 6`")
    ROLLS_RESET_HOURS = heures
    await ctx.send(f"✅ Rolls rechargés toutes les **{heures}h** maintenant !")

@bot.command(name="gachastock", aliases=["gs", "collection", "coll"])
async def gachastock(ctx, membre_ou_perso: str = None):
    """Voir ta collection gacha style Mudae — .gachastock [@joueur] [perso]"""
    if SALON_GACHA_ID and ctx.channel.id != SALON_GACHA_ID:
        salon = ctx.guild.get_channel(SALON_GACHA_ID)
        mention = salon.mention if salon else "le salon gacha"
        return await ctx.send(f"🎰 Le gacha c'est dans {mention} !", delete_after=5)

    # Déterminer si c'est un membre ou un nom de perso
    target = ctx.author
    start_key = None

    if membre_ou_perso:
        # Essayer de convertir en membre
        try:
            target = await commands.MemberConverter().convert(ctx, membre_ou_perso)
        except:
            # C'est un nom de perso — on commence par ce perso
            start_key = membre_ou_perso.lower()

    uid = str(target.id)
    collection = gacha_collections[uid]

    if not collection:
        return await ctx.send(
            f"📭 {'Ta collection est vide !' if target == ctx.author else f'La collection de **{target.display_name}** est vide !'}\n"
            f"Tape `.ga` pour tirer !"
        )

    # Récupérer les clés dans l'ordre sauvegardé
    order = collection_order.get(uid, [])
    # Ajouter les cartes pas encore dans l'ordre
    all_keys = [k for k in order if k in collection] + [k for k in collection if k not in order]

    # Trouver l'index de départ
    start_idx = 0
    if start_key and start_key in all_keys:
        start_idx = all_keys.index(start_key)

    index = [start_idx]

    def build_embed(i):
        key = all_keys[i]
        c = ANIME_CARDS_DB[key]
        level = fusion_levels[uid][key]
        stars = "⭐" * level
        rarete_emoji = RARETE_EMOJI.get(c["rarete"], "🔵")
        couleur = RARETE_COULEURS.get(c["rarete"], 0x95a5a6)
        boost_atk = level * 15
        boost_def = level * 10
        boost_pv = level * 20

        embed = discord.Embed(
            title=f"{c['emoji']} {c['nom']} {stars}",
            description=f"*{c['serie']}* {rarete_emoji} **{c['rarete']}**",
            color=couleur
        )
        if c.get("image"):
            embed.set_image(url=c["image"])

        embed.add_field(
            name="📊 Stats",
            value=f"❤️ **{c['pv'] + boost_pv}** PV | ⚔️ **{c['attaque'] + boost_atk}** ATK | 🛡️ **{c['defense'] + boost_def}** DEF",
            inline=False
        )
        attaques_str = "\n".join([
            f"{a['emoji']} **{a['nom']}** — `{a['degats']} dégâts`"
            for a in c["attaques"]
        ])
        embed.add_field(name="⚔️ Attaques", value=attaques_str, inline=False)

        tokens = collection[key].get("fusion_tokens", 0) if isinstance(collection[key], dict) else 0
        if tokens > 0:
            embed.add_field(name="🔮 Fusion", value=f"**{tokens}/2** tokens • `.fusionner {key}`", inline=True)

        embed.set_footer(text=f"Carte {i+1}/{len(all_keys)} • Collection de {target.display_name} • .gacha ordre pour réorganiser")
        return embed

    msg = await ctx.send(embed=build_embed(index[0]))

    if len(all_keys) > 1:
        await msg.add_reaction("◀️")
        await msg.add_reaction("▶️")

        def check(reaction, user):
            return (
                user == ctx.author
                and str(reaction.emoji) in ["◀️", "▶️"]
                and reaction.message.id == msg.id
            )

        while True:
            try:
                reaction, user = await bot.wait_for("reaction_add", check=check, timeout=60)
                if str(reaction.emoji) == "▶️":
                    index[0] = (index[0] + 1) % len(all_keys)
                elif str(reaction.emoji) == "◀️":
                    index[0] = (index[0] - 1) % len(all_keys)
                await msg.edit(embed=build_embed(index[0]))
                try:
                    await msg.remove_reaction(reaction.emoji, user)
                except:
                    pass
            except asyncio.TimeoutError:
                try:
                    await msg.clear_reactions()
                except:
                    pass
                break

@bot.command(name="gacha", aliases=["gc"])
async def gacha_cmd(ctx, sous_cmd: str = None, *args):
    """Commandes gacha — .gacha ordre naruto 1 luffy 2"""
    if SALON_GACHA_ID and ctx.channel.id != SALON_GACHA_ID:
        salon = ctx.guild.get_channel(SALON_GACHA_ID)
        mention = salon.mention if salon else "le salon gacha"
        return await ctx.send(f"🎰 Le gacha c'est dans {mention} !", delete_after=5)

    if sous_cmd and sous_cmd.lower() == "ordre":
        uid = str(ctx.author.id)
        collection = gacha_collections[uid]

        if not collection:
            return await ctx.send("❌ Ta collection est vide !")

        if not args or len(args) % 2 != 0:
            return await ctx.send("❌ Format : `.gacha ordre naruto 1 luffy 2 gojo 3`")

        # Parser les paires perso/position
        order = collection_order.get(uid, list(collection.keys()))
        # S'assurer que toutes les cartes sont dans l'ordre
        for key in collection:
            if key not in order:
                order.append(key)

        pairs = list(args)
        erreurs = []
        changes = {}

        for i in range(0, len(pairs), 2):
            perso = pairs[i].lower()
            try:
                pos = int(pairs[i+1]) - 1  # 0-indexed
            except:
                erreurs.append(f"`{pairs[i+1]}` n'est pas un numéro valide")
                continue

            if perso not in collection:
                erreurs.append(f"`{perso}` pas dans ta collection")
                continue

            if pos < 0 or pos >= len(order):
                erreurs.append(f"Position `{pos+1}` invalide (max {len(order)})")
                continue

            changes[perso] = pos

        if erreurs:
            return await ctx.send("❌ Erreurs :\n" + "\n".join(erreurs))

        # Appliquer les changements
        new_order = [k for k in order if k not in changes]
        for perso, pos in sorted(changes.items(), key=lambda x: x[1]):
            pos = min(pos, len(new_order))
            new_order.insert(pos, perso)

        # S'assurer que toutes les cartes sont présentes
        for key in collection:
            if key not in new_order:
                new_order.append(key)

        collection_order[uid] = new_order

        result = "\n".join([
            f"`{i+1}` — {ANIME_CARDS_DB[k]['emoji']} **{ANIME_CARDS_DB[k]['nom']}**"
            for i, k in enumerate(new_order) if k in ANIME_CARDS_DB
        ])
        embed = discord.Embed(
            title="✅ Collection réorganisée !",
            description=result,
            color=0x2ecc71
        )
        await ctx.send(embed=embed)
    else:
        # Soit "recent", soit un nom de perso
        if sous_cmd and sous_cmd.lower() == "recent":
            # Dernières cartes claimées
            if not claimed_cards:
                return await ctx.send("Aucune carte claimée pour l'instant !")
            lines = []
            for key, uid in list(claimed_cards.items())[-10:]:
                if key in ANIME_CARDS_DB:
                    c = ANIME_CARDS_DB[key]
                    member = ctx.guild.get_member(int(uid))
                    name = member.display_name if member else f"<@{uid}>"
                    rarete_emoji = RARETE_EMOJI.get(c["rarete"], "🔵")
                    lines.append(f"{rarete_emoji} **{c['nom']}** — claimé par **{name}**")
            embed = discord.Embed(
                title="🕐 Dernières cartes claimées",
                description="\n".join(lines) if lines else "Aucune carte récente",
                color=0x9b59b6
            )
            return await ctx.send(embed=embed)

        # Chercher un perso par nom
        query = sous_cmd or ""
        if args:
            query = query + " " + " ".join(args)
        query = query.lower().strip()

        if not query:
            return await ctx.send("💡 Commandes gacha :\n`.ga` — Tirer une carte\n`.gacha <perso>` — Voir qui possède une carte\n`.gacha recent` — Dernières cartes claimées\n`.gacha ordre naruto 1 luffy 2` — Réorganiser ta collection\n`.gachastock` — Voir ta collection\n`.rolls` — Voir tes rolls")

        # Cherche la carte
        key = query.replace(" ", "")
        if key not in ANIME_CARDS_DB:
            # Recherche approximative par nom
            matches = [k for k in ANIME_CARDS_DB if query in ANIME_CARDS_DB[k]["nom"].lower()]
            if not matches:
                matches = [k for k in ANIME_CARDS_DB if any(w in k for w in query.split())]
            if not matches:
                return await ctx.send(f"❌ Personnage `{query}` introuvable !")
            key = matches[0]

        c = ANIME_CARDS_DB[key]
        rarete_emoji = RARETE_EMOJI.get(c["rarete"], "🔵")
        couleur = RARETE_COULEURS.get(c["rarete"], 0x95a5a6)

        if key in claimed_cards:
            owner_uid = claimed_cards[key]
            member = ctx.guild.get_member(int(owner_uid))
            owner_name = member.display_name if member else f"<@{owner_uid}>"
            fusion_lvl = fusion_levels.get(owner_uid, {}).get(key, 0)
            stars = "⭐" * fusion_lvl if fusion_lvl > 0 else ""
            desc = f"*{c['serie']}* {rarete_emoji} **{c['rarete']}**\n\n💜 Possédée par **{owner_name}** {stars}"
        else:
            desc = f"*{c['serie']}* {rarete_emoji} **{c['rarete']}**\n\n✨ Cette carte est **disponible** — personne ne la possède !"

        embed = discord.Embed(title=f"{c['emoji']} {c['nom']}", description=desc, color=couleur)
        if c.get("image"):
            embed.set_image(url=c["image"])
        embed.add_field(
            name="📊 Stats",
            value=f"❤️ **{c['pv']}** PV | ⚔️ **{c['attaque']}** ATK | 🛡️ **{c['defense']}** DEF",
            inline=False
        )
        attaques_str = "\n".join([f"{a['emoji']} **{a['nom']}** — `{a['degats']} dégâts`" for a in c["attaques"]])
        embed.add_field(name="⚔️ Attaques", value=attaques_str, inline=False)
        await ctx.send(embed=embed)

@bot.command(name="wishlist", aliases=["wl", "wish"])
async def wishlist_cmd(ctx, action: str = None, *, perso: str = None):
    """Gère ta wishlist — .wishlist add naruto | .wishlist remove naruto | .wishlist"""
    if SALON_GACHA_ID and ctx.channel.id != SALON_GACHA_ID:
        salon = ctx.guild.get_channel(SALON_GACHA_ID)
        mention = salon.mention if salon else "le salon gacha"
        return await ctx.send(f"🎰 La wishlist c'est dans {mention} !", delete_after=5)

    uid = str(ctx.author.id)
    wlist = gacha_wishlist[uid]

    # Afficher la wishlist
    if not action or action.lower() in ["liste", "list", "voir"]:
        if not wlist:
            return await ctx.send(embed=discord.Embed(
                description=f"📋 {ctx.author.mention} Ta wishlist est vide !\nAjoute des persos avec `.wishlist add <perso>`",
                color=0x9b59b6
            ))
        embed = discord.Embed(
            title=f"💫 Wishlist de {ctx.author.display_name}",
            color=0x9b59b6
        )
        lines = []
        for key in wlist:
            if key in ANIME_CARDS_DB:
                c = ANIME_CARDS_DB[key]
                rarete_emoji = RARETE_EMOJI.get(c["rarete"], "🔵")
                claimed = "✅ Claimée" if key in claimed_cards else "⏳ Disponible"
                lines.append(f"{rarete_emoji} **{c['nom']}** — {claimed}")
            else:
                lines.append(f"❓ `{key}`")
        embed.description = "\n".join(lines)
        embed.set_footer(text=f"{len(wlist)} perso(s) dans ta wishlist • Tu seras pingé dès qu'ils dropent !")
        return await ctx.send(embed=embed)

    if not perso:
        return await ctx.send("❌ Précise un personnage ! Ex: `.wishlist add naruto`")

    key = perso.lower().strip()
    if key not in ANIME_CARDS_DB:
        # Cherche approximatif
        matches = [k for k in ANIME_CARDS_DB if perso.lower() in ANIME_CARDS_DB[k]["nom"].lower()]
        if matches:
            key = matches[0]
        else:
            return await ctx.send(f"❌ Personnage `{perso}` introuvable ! Vérifie le nom avec `.gachastock`")

    c = ANIME_CARDS_DB[key]
    rarete_emoji = RARETE_EMOJI.get(c["rarete"], "🔵")

    if action.lower() in ["add", "ajouter", "+"]:
        if key in wlist:
            return await ctx.send(f"⚠️ **{c['nom']}** est déjà dans ta wishlist !")
        if len(wlist) >= 10:
            return await ctx.send("❌ Wishlist pleine ! Maximum **10 persos**. Retire en avec `.wishlist remove <perso>`")
        wlist.add(key)
        await ctx.send(embed=discord.Embed(
            description=f"💫 {rarete_emoji} **{c['nom']}** ajouté à ta wishlist ! Tu seras pingé dès qu'il drop 🔔",
            color=RARETE_COULEURS.get(c["rarete"], 0x9b59b6)
        ))

    elif action.lower() in ["remove", "retirer", "supprimer", "-"]:
        if key not in wlist:
            return await ctx.send(f"⚠️ **{c['nom']}** n'est pas dans ta wishlist !")
        wlist.discard(key)
        await ctx.send(embed=discord.Embed(
            description=f"🗑️ **{c['nom']}** retiré de ta wishlist.",
            color=0x95a5a6
        ))
    else:
        await ctx.send("❌ Action inconnue ! Utilise `add`, `remove` ou laisse vide pour voir ta liste")

@bot.command(name="fusionner", aliases=["fus", "fusion"])
async def fusionner(ctx, perso: str = None):
    """Fusionne 3 cartes identiques pour un boost — .fusionner naruto"""
    if SALON_GACHA_ID and ctx.channel.id != SALON_GACHA_ID:
        salon = ctx.guild.get_channel(SALON_GACHA_ID)
        mention = salon.mention if salon else "le salon gacha"
        return await ctx.send(f"🎰 Le gacha c'est dans {mention} !", delete_after=5)

    if not perso:
        return await ctx.send("❌ Ex: `.fusionner naruto`")

    uid = str(ctx.author.id)
    key = perso.lower()

    if key not in ANIME_CARDS_DB:
        return await ctx.send(f"❌ Personnage `{perso}` introuvable !")

    if key not in gacha_collections[uid]:
        return await ctx.send(f"❌ Tu ne possèdes pas **{ANIME_CARDS_DB[key]['nom']}** !")

    level = fusion_levels[uid][key]
    if level >= 3:
        return await ctx.send(f"⭐⭐⭐ **{ANIME_CARDS_DB[key]['nom']}** est déjà au niveau de fusion max !")

    # Compter les doublons — cartes claimées par l'utilisateur du même perso
    # Pour la fusion on a besoin que la carte soit déjà claim + 2 autres exemplaires
    # Dans ce système chaque perso est unique donc la fusion se fait avec des tickets de fusion
    # qu'on gagne en claimant une carte déjà possédée (boost)
    fusion_tokens = gacha_collections[uid][key].get("fusion_tokens", 0)
    if fusion_tokens < 2:
        return await ctx.send(
            f"❌ Tu as besoin de **2 tokens de fusion** pour booster **{ANIME_CARDS_DB[key]['nom']}** !\n"
            f"Tu en as **{fusion_tokens}/2**\n"
            f"💡 Claim la même carte en mode boost pour obtenir des tokens !"
        )

    gacha_collections[uid][key]["fusion_tokens"] -= 2
    fusion_levels[uid][key] += 1
    new_level = fusion_levels[uid][key]
    c = ANIME_CARDS_DB[key]
    stars = "⭐" * new_level

    embed = discord.Embed(
        title=f"✨ FUSION ! {c['emoji']} {c['nom']} {stars}",
        description=f"*{c['serie']}* {RARETE_EMOJI.get(c['rarete'], '🔵')} **{c['rarete']}**",
        color=RARETE_COULEURS.get(c["rarete"], 0x95a5a6)
    )
    if c.get("image"):
        embed.set_image(url=c["image"])
    boost = new_level
    embed.add_field(
        name="📈 Stats boostées",
        value=f"❤️ +{boost*20} PV | ⚔️ +{boost*15} ATK | 🛡️ +{boost*10} DEF",
        inline=False
    )
    embed.set_footer(text=f"Fusion {new_level}/3 • Tokens restants : {gacha_collections[uid][key].get('fusion_tokens', 0)}")
    await ctx.send(embed=embed)

# (ancien système supprimé — voir nouveau système gacha au-dessus)

# ============================================================
#  CONFIGURATION SALONS
# ============================================================
async def send_salon_embed(channel, t):
    """Envoie l'embed d'information dans le salon configuré"""
    if t == "guide":
        # ── Embed 0 — Bienvenue ──────────────────────────────
        e0 = discord.Embed(
            title="🌸 Bienvenue sur le QG Kdrama !",
            description=(
                "```\n"
                "╔════════════════════════════════════╗\n"
                "║   🌸   Q G   K D R A M A   🌸   ║\n"
                "║  ──────────────────────────────  ║\n"
                "║  Kdrama • Animé • Gaming          ║\n"
                "║  Le serveur qui ne dort jamais    ║\n"
                "╚════════════════════════════════════╝\n"
                "```\n"
                "Salut et bienvenue ! 👋\n\n"
                "On a un bot complet avec **gacha**, **économie**, **events automatiques** et plein de surprises.\n\n"
                "📖 **Lis ce guide** — 2 minutes et tu sais tout !\n\n"
                "**Préfixe : `.`** — Tape `.help` pour toutes les commandes."
            ),
            color=0xff6b9d
        )
        e0.set_footer(text="QG Kdrama • Guide du serveur 🌸")
        await channel.send(embed=e0)

        # ── Embed 1 — Économie ───────────────────────────────
        e1 = discord.Embed(
            title="💰 L'Économie — Gagne des Pièces",
            description="Les **pièces** servent à tout — rôles, items, cartes rares. Voilà comment en gagner.",
            color=0xf39c12
        )
        e1.add_field(name="💵 Sources de pièces", value=(
            "`.daily` — **100-200 pièces** / 24h\n"
            "`.travailler` — **50-150 pièces** / 4h\n"
            "`.quiz` — **10-15 pièces** par bonne réponse\n"
            "`.arene @joueur` — **100-250 pièces** si victoire\n"
            "`.missions` — missions journalières\n"
            "`.braquage @joueur` — vol risqué 30% succès\n"
            "`.investir <animé> <montant>` — ×1.5 à ×3 si ça trend"
        ), inline=False)
        e1.add_field(name="🏦 Banque — +10% intérêts/24h", value=(
            "`.banque depot <montant>` — déposer\n"
            "`.banque retrait` — récupérer avec intérêts\n"
            "`.balance` — voir ton solde"
        ), inline=False)
        e1.add_field(name="💸 Jackpot Communautaire", value=(
            "1x/mois la cagnotte est lancée — chaque message = **+1 pièce**\n"
            "À **1500 pièces** → redistribution aux membres actifs !\n"
            "`.jackpot` — voir l'avancée en temps réel"
        ), inline=False)
        e1.set_footer(text="💡 Fais .daily et .travailler tous les jours !")
        await channel.send(embed=e1)

        # ── Embed 2 — Gacha ──────────────────────────────────
        e2 = discord.Embed(
            title="🎰 Le Gacha — Collecte des Cartes",
            description="Plus de **174 personnages** — Gojo, Luffy, Naruto, Saitama... Chaque carte est **unique sur le serveur**.",
            color=0x9b59b6
        )
        e2.add_field(name="🎲 Comment tirer ?", value=(
            "`.ga` ou `.roll` — tire une carte\n"
            "**10 rolls** rechargés toutes les **6h**\n"
            "Réagis **❤️** en **30 secondes** pour claim !\n"
            "`.rolls` — voir tes rolls restants"
        ), inline=False)
        e2.add_field(name="⭐ Raretés", value=(
            "⚪ **Commun** • 🔵 **Rare** • 🟣 **Épique**\n"
            "🟠 **Légendaire** • 🔴 **Mythique** *(ultra rare !)*"
        ), inline=True)
        e2.add_field(name="✨ Invocation Spéciale", value=(
            "`.invoke` — **10 000 pièces**\n"
            "Garantit **Légendaire minimum** !"
        ), inline=True)
        e2.add_field(name="📦 Collection & Échanges", value=(
            "`.gachastock` — ta collection\n"
            "`.gacha <perso>` — qui possède ce perso ?\n"
            "`.cartefav add <perso>` — favoris (max 3)\n"
            "`.wishlist add <perso>` — notif si la carte drop\n"
            "`.gachastats` — classement des collections\n"
            "`.gachatrade @joueur <c1> <c2>` — échange\n"
            "`.cardduel @joueur <carte>` — duel de cartes !"
        ), inline=False)
        e2.set_footer(text="💡 Active la wishlist pour être notifié en premier !")
        await channel.send(embed=e2)

        # ── Embed 3 — Boutique ───────────────────────────────
        e3 = discord.Embed(
            title="🛒 La Boutique — Dépense tes Pièces",
            description="`.shop` pour tout voir — **3 pages** ◀️ ▶️",
            color=0xe67e22
        )
        e3.add_field(name="🎭 Rôles Exclusifs", value=(
            "`shadow` 🌑 Monarque des Ombres — **3000p**\n"
            "`pillier` 🔥 Pillier du Soleil — **2000p**\n"
            "`drama_king` 👑 Roi des Malédictions — **1500p**"
        ), inline=False)
        e3.add_field(name="⚔️ Items PvP — Sabote tes adversaires !", value=(
            "💣 `bombe_gacha` — force un joueur à perdre une carte **8000p**\n"
            "🔒 `cadenas` — bloque son claim 30min **4000p**\n"
            "🌟 `protection` — immunité totale 2h **5000p**\n"
            "🪬 `amulette` — renvoie les sabotages **2500p**\n"
            "🔮 `oracle` — carte mystère 1/5 chance **499p**\n"
            "🎰 `double_rien` — double tes rolls ou les perds **200p**\n"
            "→ `.acheter <id>` puis `.utiliser <item> @joueur`"
        ), inline=False)
        e3.add_field(name="🕶️ Marché Noir", value=(
            "Chaque semaine des cartes rares en vente 24h !\n"
            "`.marcheacheter <perso>` quand c'est actif"
        ), inline=False)
        e3.set_footer(text="`.shop` page 3 pour tous les items PvP !")
        await channel.send(embed=e3)

        # ── Embed 4 — Combats ────────────────────────────────
        e4 = discord.Embed(
            title="⚔️ Combats & Progression",
            description="Bats tes adversaires, monte en niveau, booste tes stats !",
            color=0xe74c3c
        )
        e4.add_field(name="🏟️ Modes de Combat", value=(
            "`.arene @joueur` — PvP tour par tour → pièces + XP + Elo\n"
            "`.pokebattle @joueur` — combat 3v3 avec tes cartes\n"
            "`.cardduel @joueur <carte>` — le gagnant prend les deux cartes\n"
            "`.quiz [thème]` — quiz solo ou `.quizduel @joueur`\n"
            "`.liga` — classement Elo mensuel"
        ), inline=False)
        e4.add_field(name="📊 XP & Niveaux", value=(
            "`.rank` — niveau, XP et titre\n"
            "À chaque level up → **+1 point d'amélioration**\n"
            "`.ameliorer` — booster tes stats d'arène (ATK/DEF/PV/END)\n"
            "💡 *Ces stats comptent en arène ET en Guerre des Factions !*"
        ), inline=False)
        e4.set_footer(text="🏆 Classement hebdo chaque dimanche soir — Top 3 récompensé !")
        await channel.send(embed=e4)

        # ── Embed 5 — Factions ───────────────────────────────
        e5 = discord.Embed(
            title="⚔️ Factions & Guerre",
            description="Rejoins une faction, bats des boss, amène ta faction à la gloire !",
            color=0x9b59b6
        )
        e5.add_field(name="🏴‍☠️ Les 6 Factions", value=(
            f"{FACTIONS['akatsuki']['emoji']} **Akatsuki** `akatsuki`\n"
            f"{FACTIONS['surveycorps']['emoji']} **Bataillon d'Exploration** `surveycorps`\n"
            f"{FACTIONS['strawhat']['emoji']} **Équipage du Chapeau de Paille** `strawhat`\n"
            f"{FACTIONS['phantomtroupe']['emoji']} **Phantom Troupe** `phantomtroupe`\n"
            f"{FACTIONS['gotei13']['emoji']} **Gotei 13** `gotei13`\n"
            f"{FACTIONS['ua']['emoji']} **Lycée U.A.** `ua`\n\n"
            "`.faction rejoindre <id>` pour rejoindre !"
        ), inline=False)
        e5.add_field(name="⚡ Gagner de la Réputation", value=(
            "• Coup final sur un boss → **+50 rep**\n"
            "• Participer à une invasion → **+10 rep**\n"
            "• Gagner la Guerre des Factions → **+100 rep + 500 pièces**\n"
            "`.faction classement` — voir le classement"
        ), inline=False)
        e5.set_footer(text="💡 Guerre des Factions 1x/mois — boss géant, faction gagnante récompensée !")
        await channel.send(embed=e5)

        # ── Embed 6 — Events Auto ────────────────────────────
        e6 = discord.Embed(
            title="🎪 Events Automatiques",
            description="Des events arrivent **automatiquement** — surveille le salon events !",
            color=0x3498db
        )
        e6.add_field(name="📅 Hebdomadaires", value=(
            "📦 **Coffre** lun/mer/dim → `.ouvrir` *(@here)*\n"
            "⚠️ **Invasion Boss** samedi 23h → `.attaquerboss`\n"
            "*(Si pas vaincu → revient +20% PV le lendemain !)*\n"
            "🌙 **Nuit de Chasse** → Mythique x2 pendant 2h\n"
            "🎰 **Nuit Casino** → Slot x2 pendant 1h\n"
            "🌀 **Double XP** → XP x2 pendant 1h\n"
            "🎴 **Carte Mystère** ven/sam/dim → bonne ou troll ? 👀\n"
            "🌙 **Heure Maudite** → 2h du mat, Épique x2 (30min)\n"
            "🎭 **Imposteur** → fausse carte 9999 ATK 😈"
        ), inline=False)
        e6.add_field(name="📆 Mensuels", value=(
            "🃏 **Draft de Cartes** → 3 cartes Épique gratuites\n"
            "🏴‍☠️ **Guerre des Factions** → boss géant\n"
            "🎪 **Event Surprise** → annonce 1h avant\n"
            "💸 **Jackpot** → cagnotte 1500p redistribuée\n"
            "🔮 **Prophétie** → animé béni +10% stats arène"
        ), inline=False)
        e6.add_field(name="🏆 Classement Hebdo — Dimanche 20h", value=(
            "Top 3 de la semaine (messages + vocal) :\n"
            "🥇 **+300p** • 🥈 **+200p** • 🥉 **+100p**"
        ), inline=False)
        e6.set_footer(text="🔔 Active les notifs du salon events pour ne jamais rater !")
        await channel.send(embed=e6)

        # ── Embed 7 — Events Spéciaux ────────────────────────
        e7 = discord.Embed(
            title="🎭 Events Spéciaux Interactifs",
            description="Des events uniques déclenchés par les admins ou automatiquement !",
            color=0x9b59b6
        )
        e7.add_field(name="🎲 Chance & Hasard", value=(
            "🎲 **Roue de la Fortune** — effet random sur tout le serveur\n"
            "⚡ **Enchères Interdites** — mise secrète, égalité = tout perdu\n"
            "💎 **Mine d'Or** — extrait des pépites, évite la pépite maudite !"
        ), inline=False)
        e7.add_field(name="🕵️ Social & Stratégie", value=(
            "🕵️ **Parmi Nous** — un imposteur vole tes cartes, trouvez-le !\n"
            "💀 **Death Note** — 2 noms, mais le retour est double...\n"
            "🎩 **Le Magicien** — sorts anonymes sur les membres\n"
            "🎴 **Wanted** — prime sur un membre, chasseurs en action !"
        ), inline=False)
        e7.add_field(name="⚔️ Compétition", value=(
            "⚔️ **Tournoi du QG** — bracket automatique, gagnant = Champion\n"
            "🌍 **Conquête du QG** — factions vs zones, titre Roi de la Conquête\n"
            "🌊 **Vague de Légendes** — 10 cartes Légendaires en 10 min !\n"
            "👾 **Boss Final** — boss avec personnalité qui insulte et contre-attaque 😈"
        ), inline=False)
        e7.add_field(name="🎭 Fun & Chaos", value=(
            "⚖️ **Procès du QG** — accusé de crimes ridicules, les jurés votent\n"
            "🤡 **Le Clown** — un membre répété en version ridicule\n"
            "🐦‍⬛ **Le Corbeau** — adopte-le, il a ses propres humeurs\n"
            "📰 **Fausse Rumeur** — test de sang froid, `.jedoute` pour gagner\n"
            "🔴 **Alerte Rouge** — 10 min de silence puis... quelque chose arrive"
        ), inline=False)
        e7.set_footer(text="`.lancerevent <nom>` pour les lancer (admin)")
        await channel.send(embed=e7)

        # ── Embed 8 — Démarrage ──────────────────────────────
        e8 = discord.Embed(
            title="⚡ Par Où Commencer ?",
            description="T'es nouveau ? Voilà les **5 premières choses** à faire !",
            color=0x2ecc71
        )
        e8.add_field(name="🚀 Les 5 Premiers Pas", value=(
            "**1.** `.daily` — pièces du jour\n"
            "**2.** `.ga` — ta première carte gacha\n"
            "**3.** `.faction rejoindre <id>` — rejoins une faction\n"
            "**4.** `.missions` — tes missions du jour\n"
            "**5.** `.travailler` — pièces supplémentaires"
        ), inline=False)
        e8.add_field(name="📋 Commandes Rapides", value=(
            "`.help` — toutes les commandes\n"
            "`.balance` — ton solde\n"
            "`.gachastock` — ta collection\n"
            "`.rank` — ton niveau\n"
            "`.shop` — la boutique\n"
            "`.jackpot` — la cagnotte"
        ), inline=True)
        e8.add_field(name="🎯 Objectifs Long Terme", value=(
            "💰 Économise **10 000p** pour `.invoke`\n"
            "🔴 Obtiens une carte **Mythique**\n"
            "🏆 Sois dans le **Top 3 hebdo**\n"
            "⚔️ Aide ta faction à gagner la **Guerre**\n"
            "👑 Remporte le **Tournoi du QG**"
        ), inline=True)
        e8.set_footer(text="Bonne chance et bienvenue sur le QG Kdrama ! 🌸")
        await channel.send(embed=e8)
        return

    if t == "gacha":
        # Embed 1 — Présentation & Commandes
        embed1 = discord.Embed(
            title="🎰 Bienvenue au Gacha — QG Kdrama",
            description=(
                "Tire des cartes de personnages animé/manga, construis ta collection unique et affronte les autres membres !\n\n"
                "*Le système fonctionne comme **Mudae** — chaque carte est unique sur le serveur, une fois claimée elle appartient à quelqu'un.*"
            ),
            color=0x9b59b6
        )
        embed1.add_field(name="🎮 Commandes principales", value=(
            "`.ga` `.g` `.roll` `.r` — Tire une carte aléatoire\n"
            "`.rolls` `.ro` — Voir tes rolls restants & ton cooldown claim\n"
            "`.daily` — 150-300 pièces + **1 roll bonus** (toutes les 24h)\n"
            "`.gachastock` `.gs` `.coll` [@joueur] — Ta collection avec ◀️ ▶️\n"
            "`.gacha <perso>` — Voir une carte & qui la possède\n"
            "`.gacha recent` — Les dernières cartes claimées sur le serveur\n"
            "`.gacha ordre naruto 1 luffy 2` — Réorganiser ta collection\n"
            "`.fusionner <perso>` `.fus` — Booster une carte avec des tokens ⭐\n"
            "`.wishlist add <perso>` `.wl add` — Ajouter un perso à ta wishlist\n"
            "`.wishlist` `.wl` — Voir ta wishlist (max 10 persos)\n"
            "`.setimage <perso> <url>` — Changer l'image de **ta** carte\n"
        "`.gachagive @membre <perso>` — Offrir une de tes cartes\n"
        "`.gachatrade @membre <ta carte> <sa carte>` — Proposer un échange\n"
        "`.gacharesetall` — Reset total du gacha (admin)"
        ), inline=False)
        embed1.set_footer(text="📖 Lis les autres embeds pour les règles, raretés et items boutique !")
        await channel.send(embed=embed1)

        # Embed 2 — Règles du jeu
        embed2 = discord.Embed(
            title="📜 Règles du Gacha",
            color=0x9b59b6
        )
        embed2.add_field(name="🎲 Rolls & Claim", value=(
            "• Tu as **10 rolls** rechargés automatiquement toutes les **6h**\n"
            "• Quand une carte apparaît avec ❤️ → tu as **30 secondes** pour la claim !\n"
            "• Tu ne peux claimer qu'**une carte toutes les 30 min** — pas de spam\n"
            "• Une carte claimée est **unique** — elle n'apparaîtra plus jamais en tirage\n"
            "• Carte déjà claimée → affichée avec ⚡, personne d'autre ne peut la prendre"
        ), inline=False)
        embed2.add_field(name="💫 Wishlist", value=(
            "• Ajoute jusqu'à **10 persos** à ta wishlist avec `.wl add <perso>`\n"
            "• Dès qu'un perso de ta wishlist **drop** → tu es **pingé instantanément** 🔔\n"
            "• Si quelqu'un le claim avant toi → tu reçois un ping de consolation 💔\n"
            "• Retire un perso avec `.wl remove <perso>`"
        ), inline=False)
        embed2.add_field(name="⭐ Système de Fusion", value=(
            "• Si tu claims une carte que tu **possèdes déjà** → tu reçois un **token de fusion** 🪙\n"
            "• Accumule **2 tokens** puis utilise `.fusionner <perso>` pour booster ta carte\n"
            "• ⭐+1 : **+20 PV • +15 ATK • +10 DEF**\n"
            "• ⭐+2 : **+40 PV • +30 ATK • +20 DEF**\n"
            "• ⭐+3 : **+60 PV • +45 ATK • +30 DEF** *(niveau maximum)*\n"
            "• Une carte boostée est **plus puissante en combat** `.pokebattle`"
        ), inline=False)
        embed2.set_footer(text="📖 Voir aussi les raretés & items boutique dans les embeds suivants !")
        await channel.send(embed=embed2)

        # Embed 3 — Raretés
        embed3 = discord.Embed(
            title="💎 Raretés & Taux de Drop",
            description="Plus la rareté est haute, plus la carte est puissante en combat et rare à obtenir !",
            color=0x9b59b6
        )
        embed3.add_field(name="Taux normaux", value=(
            "🔵 **Commun** — 76.49%\n"
            "⭐ **Rare** — 20%\n"
            "💜 **Épique** — 3%\n"
            "👑 **Légendaire** — 0.5%\n"
            "🔮 **Mythique** — 0.01%"
        ), inline=True)
        embed3.add_field(name="Avec 🎯 Boost Rareté", value=(
            "🔵 **Commun** — 50%\n"
            "⭐ **Rare** — 27%\n"
            "💜 **Épique** — 14%\n"
            "👑 **Légendaire** — 7.5%\n"
            "🔮 **Mythique** — 1.5%"
        ), inline=True)
        embed3.add_field(name="⚔️ Stats par rareté", value=(
            "🔵 Commun — stats faibles\n"
            "⭐ Rare — stats correctes\n"
            "💜 Épique — stats solides\n"
            "👑 Légendaire — stats élevées\n"
            "🔮 Mythique — stats maximales 👑"
        ), inline=False)
        embed3.set_footer(text="🔮 Mythique = 1 chance sur 10 000... Bonne chance !")
        await channel.send(embed=embed3)

        # Embed 4 — Items boutique liés au gacha
        embed4 = discord.Embed(
            title="🛒 Items Boutique — Pouvoirs Gacha & PvP",
            description="Ces items s'achètent avec `.acheter <id>` et impactent le gacha !",
            color=0xf39c12
        )
        embed4.add_field(name="⚡ Boosts", value=(
            "`rolls_5` — 🎰 **+5 Rolls** → **700p**\n"
            "`boost_rarete` — 🎯 **Boost Rareté** *(1x/jour)* → **1500p**\n"
            "`claim_20/15/10` — ⚡ **Claim réduit** *(permanent)* → **800/1500/3000p**"
        ), inline=False)
        embed4.add_field(name="⚔️ Items PvP", value=(
            "`bombe_gacha` — 💣 **8000p** • `cadenas` — 🔒 **4000p**\n"
            "`amulette` — 🪬 **2500p** • `cadeau` — 🎁 **900p**\n"
            "`fantome` — 👻 **800p** • `malediction` — 🎭 **700p**\n"
            "`vol_roll` — 🎯 **500p** • `oracle` — 🔮 **499p**\n"
            "`shield` — 🛡️ **600p** • `double_rien` — 🎰 **200p**\n"
            "→ `.utiliser <item> @joueur` pour activer !"
        ), inline=False)
        embed4.set_footer(text="💰 Gagne des pièces avec .daily • .quiz • .boss • .duel • .arene")
        await channel.send(embed=embed4)

    elif t == "levelup":
        embed1 = discord.Embed(
            title="📊 Progression — XP & Niveaux",
            description=(
                "Ce salon affiche les notifications de **level up** du serveur !\n"
                "Chaque message, victoire et action te rapporte de l'XP 📈"
            ),
            color=0xf1c40f
        )
        embed1.add_field(name="📈 Comment gagner de l'XP ?", value=(
            "💬 **Chatter** → 2-5 XP par message\n"
            "🎯 **Gagner un quiz** → +30 XP\n"
            "🃏 **Claimer une carte gacha** → +20 XP\n"
            "🏟️ **Gagner une arène** → +40 XP\n"
            "🐉 **Tuer un boss** → +50 XP\n"
            "⚡ **Double XP** disponible en boutique → **300p**"
        ), inline=False)
        embed1.add_field(name="🏆 Titres par niveau", value=(
            "Niv.1 🌱 Académicien Débutant\n"
            "Niv.5 ⚔️ Chasseur Rang E\n"
            "Niv.10 🗡️ Chasseur Rang D\n"
            "Niv.15 💥 Chasseur Rang C\n"
            "Niv.20 🔥 Chasseur Rang B\n"
            "Niv.25 ⚡ Chasseur Rang A\n"
            "Niv.30 💎 Chasseur Rang S\n"
            "Niv.40 👑 Pillier du QG\n"
            "Niv.50 🌀 Maître des Arts Martiaux\n"
            "Niv.60 ☠️ Lune Supérieure\n"
            "Niv.75 🐉 Roi des Malédictions\n"
            "Niv.99 🌟 Monarque des Ombres"
        ), inline=False)
        embed1.add_field(name="🎮 Commandes", value=(
            "`.rank [@joueur]` — Voir ton niveau, XP et titre\n"
            "`.leaderboard` — Top 10 membres les plus actifs du serveur"
        ), inline=False)
        embed1.set_footer(text="📊 Les notifications de level up apparaissent ici automatiquement !")
        await channel.send(embed=embed1)

    elif t == "boutique":
        embed1 = discord.Embed(
            title="🛒 Boutique — QG Kdrama",
            description="Dépense tes pièces pour des avantages exclusifs !\nTape `.shop` pour voir les prix et acheter 💰",
            color=0xf39c12
        )
        embed1.add_field(name="💡 Comment acheter ?", value=(
            "`.shop` — Voir tous les items & prix *(3 pages : ◀️ ▶️)*\n"
            "`.acheter <id>` — Acheter un item *(ex: `.acheter vip`)*\n"
            "`.utiliser <item> @joueur` — Utiliser un item PvP\n"
            "`.balance` — Voir ton solde de pièces"
        ), inline=False)
        embed1.add_field(name="🎭 Rôles Exclusifs", value=(
            "`shadow` — 🌑 **Monarque des Ombres** → **3000p**\n"
            "`pillier` — 🔥 **Pillier du Soleil** → **2000p**\n"
            "`drama_king` — 👑 **Roi des Malédictions** → **1500p**\n"
            "`otaku` — 🌀 **Oeil de Dieu** → **1200p**\n"
            "`vip` — 💎 **Rang S VIP** → **1000p**\n"
            "`gamer_pro` — ⚔️ **Chasseur National** → **800p**"
        ), inline=False)
        embed1.add_field(name="⚡ Boosts & Rolls", value=(
            "`claim_10` — ⚡ **Claim 10 min** *(permanent)* → **3000p**\n"
            "`boost_rarete` — 🎯 **Boost Rareté** *(1x/jour)* → **1500p**\n"
            "`claim_15` — ⚡ **Claim 15 min** *(permanent)* → **1500p**\n"
            "`claim_20` — ⚡ **Claim 20 min** *(permanent)* → **800p**\n"
            "`rolls_5` — 🎰 **+5 Rolls** → **700p**\n"
            "`double_xp` — ⚡ **Double XP 1h** → **300p**"
        ), inline=False)
        embed1.add_field(name="⚔️ Items PvP — Sabotage & Défense", value=(
            "`bombe_gacha` — 💣 **Bombe Gacha** → **8000p** *(fait perdre une carte !)*\n"
            "`protection` — 🌟 **Protection Divine** → **5000p** *(immunité 2h)*\n"
            "`cadenas` — 🔒 **Cadenas** → **4000p** *(bloque claim 30min)*\n"
            "`amulette` — 🪬 **Amulette** → **2500p** *(renvoie sabotage 20min)*\n"
            "`cadeau` — 🎁 **Cadeau Mystère** → **900p** *(carte Rare+)*\n"
            "`fantome` — 👻 **Fantôme** → **800p** *(carte invisible 30min)*\n"
            "`malediction` — 🎭 **Malédiction Rare** → **700p** *(prochain roll = Commun)*\n"
            "`vol_roll` — 🎯 **Vol de Roll** → **500p** *(max 3x/joueur)*\n"
            "`oracle` — 🔮 **Oracle** → **499p** *(1/5 chance de drop en 3 rolls)*\n"
            "`shield` — 🛡️ **Bouclier** → **600p** *(protège 30min)*\n"
            "`freeze` — 🧊 **Sceau Ombres** → **500p** *(bloque claim 10s)*\n"
            "`double_rien` — 🎰 **Double ou Rien** → **200p** *(≤4 rolls requis)*"
        ), inline=False)
        embed1.set_footer(text="💰 Gagne des pièces : .daily • .quiz • .boss • .duel • .arene • .slot")
        await channel.send(embed=embed1)

    elif t == "casino":
        embed1 = discord.Embed(
            title="🎰 Casino — QG Kdrama",
            description=(
                "Bienvenue au Casino du QG ! Tente ta chance à la slot machine...\n"
                "*La maison gagne toujours — mais parfois elle perd 😈*"
            ),
            color=0xe74c3c
        )
        embed1.add_field(name="🎮 Comment jouer", value=(
            "`.slot [mise]` — Lance la slot machine\n"
            "• Mise **minimum : 10 pièces**\n"
            "• Mise **maximum : 500 pièces**\n"
            "• Cooldown **10 secondes** entre chaque spin\n\n"
            "*Ex : `.slot 100` pour miser 100 pièces*"
        ), inline=False)
        embed1.add_field(name="🏆 Tableau des gains", value=(
            "🐉🐉🐉 — **x10** la mise *(JACKPOT !)*\n"
            "💎💎💎 — **x7** la mise\n"
            "👑👑👑 — **x5** la mise\n"
            "⚡⚡⚡ — **x4** la mise\n"
            "🔥🔥🔥 — **x3** la mise\n"
            "🎭🎭🎭 — **x2.5** la mise\n"
            "2 symboles identiques — **x1.5** la mise\n"
            "Aucune correspondance — ❌ mise perdue"
        ), inline=False)
        embed1.add_field(name="💡 Conseils", value=(
            "• Commence petit pour tester ta chance\n"
            "• Fais `.daily` chaque jour pour renflouer tes pièces\n"
            "• Mets de côté à la banque avec `.banque depot` pour sécuriser tes gains\n"
            "• Le casino est **réservé à ce salon** uniquement"
        ), inline=False)
        embed1.set_footer(text="💰 Gagne des pièces avec .daily • .quiz • .boss • .duel avant de jouer !")
        await channel.send(embed=embed1)

    elif t == "combat":
        embed1 = discord.Embed(
            title="🃏 Combat Cartes — QG Kdrama",
            description=(
                "Affronte d'autres joueurs en **combat 3v3** avec tes cartes gacha !\n"
                "*Plus tes cartes sont rares et fusionnées, plus tu es puissant !*"
            ),
            color=0xe74c3c
        )
        embed1.add_field(name="🎮 Commandes", value=(
            "`.pokebattle @joueur` — Défier un joueur en combat 3v3\n"
            "`.pokestop` — Annuler un combat en cours"
        ), inline=False)
        embed1.add_field(name="📜 Déroulement du combat", value=(
            "**1.** Le bot sélectionne automatiquement tes **3 meilleures cartes**\n"
            "**2.** Chaque carte a ses propres stats : **PV • ATK • DEF**\n"
            "**3.** À chaque tour, choisis parmi 3 actions :\n"
            "   ⚔️ **Attaque normale** — dégâts stables\n"
            "   💥 **Attaque spéciale** — dégâts élevés mais moins précis\n"
            "   🛡️ **Défense** — réduit les dégâts reçus ce tour\n"
            "**4.** La carte adverse riposte automatiquement\n"
            "**5.** Quand une carte tombe à 0 PV → carte suivante !\n"
            "**6.** L'équipe encore debout gagne 🏆"
        ), inline=False)
        embed1.add_field(name="⭐ Impact de la rareté & fusion", value=(
            "🔵 Commun → stats faibles\n"
            "⭐ Rare → stats correctes\n"
            "💜 Épique → stats solides\n"
            "👑 Légendaire → stats élevées\n"
            "🔮 Mythique → stats maximales\n\n"
            "• Chaque fusion ⭐ ajoute +20PV +15ATK +10DEF à ta carte\n"
            "• Max ⭐+3 : +60PV +45ATK +30DEF de bonus !"
        ), inline=False)
        embed1.add_field(name="🏆 Récompenses", value=(
            "• Victoire → **+150 pièces & +60 XP**\n"
            "• Défaite → pas de pièces mais de l'expérience !"
        ), inline=False)
        embed1.add_field(name="💡 Conseils stratégiques", value=(
            "• Claim des cartes **Légendaires/Mythiques** en gacha pour dominer\n"
            "• Fusionne tes cartes avec `.fusionner <perso>` pour les booster\n"
            "• Utilise la défense face aux attaquants puissants\n"
            "• Garde ta meilleure carte pour la fin !"
        ), inline=False)
        embed1.set_footer(text="🎰 Commence par claimer des cartes en gacha !")
        await channel.send(embed=embed1)

    elif t == "bienvenue":
        embed = discord.Embed(
            title="✅ Salon Bienvenue configuré !",
            description=(
                "Ce salon accueillera les nouveaux membres avec un embed stylé contenant :\n\n"
                "🎌 Un message de bienvenue personnalisé\n"
                "🏅 Le numéro du membre *(ex: Tu es le 42ème membre !)*\n"
                "🖼️ L'avatar du nouveau membre\n"
                "📊 Le compteur total de membres\n\n"
                "*L'embed s'affiche automatiquement à chaque arrivée.*"
            ),
            color=0x2ecc71
        )
        embed.set_footer(text="Configuration — QG Kdrama 🎌")
        await channel.send(embed=embed)

    elif t == "aurevoir":
        embed = discord.Embed(
            title="✅ Salon Aurevoir configuré !",
            description=(
                "Ce salon affichera un message quand un membre quitte le serveur :\n\n"
                "💔 Le nom du membre qui est parti\n"
                "🖼️ Son avatar\n"
                "📊 Le nombre de membres restants\n\n"
                "*L'embed s'affiche automatiquement à chaque départ.*"
            ),
            color=0x95a5a6
        )
        embed.set_footer(text="Configuration — QG Kdrama 💔")
        await channel.send(embed=embed)

    elif t == "boost":
        embed = discord.Embed(
            title="✅ Salon Boost configuré !",
            description=(
                "Ce salon affichera un embed stylé à chaque nouveau boost :\n\n"
                "💎 Mention du boosteur\n"
                "🏅 Son rang de boosteur *(1er, 2ème...)*\n"
                "🖼️ Son avatar\n"
                "📊 Compteur total de boosts\n\n"
                "*L'embed s'affiche automatiquement à chaque boost.*"
            ),
            color=0xff73fa
        )
        embed.set_footer(text="Configuration — QG Kdrama 💎")
        await channel.send(embed=embed)

    elif t == "halloffame":
        embed = discord.Embed(
            title="✅ Salon Hall of Fame configuré !",
            description=(
                "Ce salon recevra automatiquement les messages les plus drôles du serveur !\n\n"
                "**Emojis déclencheurs :** 😭 🤣 😂 😹\n"
                "**Seuil :** 4 réactions sur un même message\n\n"
                "Dès qu'un message atteint **4 réactions** → copié ici avec auteur + lien original.\n\n"
                "*Un message ne peut apparaître qu'une seule fois — pas de doublon !*"
            ),
            color=0xf1c40f
        )
        embed.set_footer(text="Configuration — QG Kdrama 🏆")
        await channel.send(embed=embed)

    elif t == "reglement":
        embed = discord.Embed(
            title="⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯  ⌑  ＱＧ  ＫＤＲＡＭＡ ⌑  ⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯",
            description=(
                "Bienvenue dans la **V2**. Un espace dédié à la passion des dramas, des animés et du gaming.\n"
                "Merci de respecter ces directives pour le confort de tous.\n"
            ),
            color=0x2c2f33
        )
        embed.add_field(
            name="Ⅰ.  ＣＯＮＤＵＩＴＥ  ＆  ＥＴＨＩＱＵＥ",
            value=(
                "**Respect Absolu** ⎯ Aucune insulte, propos haineux (racisme, sexisme, homophobie) ou harcèlement ne sera toléré.\n"
                "**Maturité** ⎯ On débat, on donne son avis, mais on reste courtois même si on n'aime pas le même drama ou perso d'anime."
            ),
            inline=False
        )
        embed.add_field(
            name="Ⅱ.  ＣＵＬＴＵＲＥ  ＮＯ-ＳＰＯＩＬ",
            value=(
                "**Spoiler Alert** ⎯ L'utilisation des balises `||` anti spoil est obligatoire pour tout élément clé d'une intrigue (fin de drama, mort de perso, etc.).\n"
                "**Espaces Dédiés** ⎯ Merci de poster vos contenus dans les salons appropriés (#anime, #kdrama, #gaming)."
            ),
            inline=False
        )
        embed.add_field(
            name="Ⅲ.  ＳＥＣＵＲＩＴＥ  ＆  ＣＯＮＴＥＮＵ",
            value=(
                "**Publicité** ⎯ Toute promotion non autorisée (serveur, réseaux sociaux) en public ou en DM est proscrite.\n"
                "**Contenu** ⎯ Aucun contenu NSFW (choquant ou sexuel) n'est autorisé sur le serveur."
            ),
            inline=False
        )
        embed.add_field(
            name="🛡️  ＭＯＤＥＲＡＴＩＯＮ",
            value="Le staff veille au grain. Tout manquement répété entraînera un avertissement ou un bannissement définitif.",
            inline=False
        )
        embed.add_field(
            name="\u200b",
            value="✅ **Réagis avec ✅ ci-dessous pour accepter le règlement et accéder au serveur.**",
            inline=False
        )
        embed.set_footer(text="QG Kdrama — En acceptant, tu t'engages à respecter ces règles.")
        msg = await channel.send(embed=embed)
        await msg.add_reaction("✅")
        # Sauvegarder l'ID du message règlement
        global REGLEMENT_MSG_ID
        REGLEMENT_MSG_ID = msg.id
        sauvegarder_salons()

    elif t == "duel":
        embed1 = discord.Embed(
            title="⚔️ Combat & PvP — QG Kdrama",
            description=(
                "Prouve que t'es le plus fort du QG !\n"
                "**Arène PvP**, **Boss commun** et **Quiz Duel** 🔥"
            ),
            color=0xe67e22
        )
        embed1.add_field(name="🏟️ Arène PvP — Combat interactif tour par tour", value=(
            "`.arene @joueur` — Lance un combat\n\n"
            "• L'adversaire **accepte ou refuse** avec ✅ ❌\n"
            "• Un seul embed se met à jour en temps réel 🎮\n"
            "• **Barres de vie et d'endurance visuelles** ❤️ ⚡\n"
            "• Actions via **réactions** — pas besoin de taper !\n"
            "• **30s** pour choisir, sinon attaque automatique\n"
            "• Victoire → **+100-250 pièces & +40 XP** 🏆"
        ), inline=False)
        embed1.add_field(name="⚡ Système d'Endurance", value=(
            "Chaque action coûte de l'endurance *(⚡)* :\n\n"
            "⚔️ Attaque Normale — **-10 END**\n"
            "💥 Attaque Chargée — **-30 END** *(attention !)*\n"
            "🌀 Attaque Spéciale — **-20 END**\n"
            "🛡️ Défense — **-5 END**\n"
            "🌿 Soin — **-8 END**\n"
            "💨 Esquive — **-15 END**\n\n"
            "📈 **+12 END** récupérés automatiquement à chaque tour\n"
            "*Si ton endurance est trop basse → attaque normale forcée !*"
        ), inline=False)
        embed1.add_field(name="🆙 Points d'Amélioration — Personnalise tes stats !", value=(
            "À chaque **level up** tu gagnes **1 point d'amélioration** !\n\n"
            "`.ameliorer` — Voir tes stats & points disponibles\n"
            "`.ameliorer pv` — ❤️ **+8 HP max** par point\n"
            "`.ameliorer atk` — 🗡️ **+3 ATK bonus** par point\n"
            "`.ameliorer def` — 🛡️ **+3 DEF bonus** par point\n"
            "`.ameliorer endurance` — ⚡ **+5 END max** par point\n\n"
            "*Tes stats améliorées sont actives dans toutes les arènes !*"
        ), inline=False)
        embed1.add_field(name="🐉 Boss Commun — Tout le monde attaque !", value=(
            "`.boss` — Invoque un boss *(admin only)*\n"
            "`.attaque` — Frappe le boss ! *(cooldown 13s)*\n\n"
            "• **Tout le monde** peut participer en même temps\n"
            "• **Coup fatal** → **+250 pièces bonus** 🎯\n"
            "• Récompenses partagées entre tous les participants"
        ), inline=False)
        embed1.add_field(name="🎯 Quiz Duel", value=(
            "`.quizduel [thème] @joueur` — 5 questions en duel\n"
            "*Thèmes : kdrama • anime • gaming • culture • mix*\n"
            "Victoire → **80-150 pièces** 💰"
        ), inline=False)
        embed1.set_footer(text="⚔️ Gagne des niveaux → .rank • .ameliorer • plus fort en arène !")
        await channel.send(embed=embed1)






# ============================================================
#  SETSALON — Configure ou désactive un salon (toggle)
# ============================================================
@bot.command(name="setsalon")
@commands.has_permissions(administrator=True)
async def setsalon_cmd(ctx, type_salon: str = None, role: discord.Role = None):
    """Configure ou désactive un salon — .setsalon casino | .setsalon reglement @Role"""
    global SALON_LEVELUP_ID, SALON_CASINO_ID, SALON_GACHA_ID, SALON_BOUTIQUE_ID, SALON_EVENT_ID, SALON_GUIDE_ID
    global SALON_COMBAT_ID, SALON_DUEL_ID, SALON_BIENVENUE_ID, SALON_AUREVOIR_ID
    global SALON_BOOST_ID, SALON_HOF_ID, SALON_REGLEMENT_ID, ROLE_MEMBRE_NAME, REGLEMENT_ROLE_ID

    TYPES = {
        "levelup":    ("SALON_LEVELUP_ID",    "level up"),
        "casino":     ("SALON_CASINO_ID",     "casino"),
        "gacha":      ("SALON_GACHA_ID",      "gacha"),
        "boutique":   ("SALON_BOUTIQUE_ID",   "boutique"),
        "combat":     ("SALON_COMBAT_ID",     "combat cartes"),
        "duel":       ("SALON_DUEL_ID",       "duel & PvP"),
        "bienvenue":  ("SALON_BIENVENUE_ID",  "bienvenue"),
        "aurevoir":   ("SALON_AUREVOIR_ID",   "aurevoir"),
        "boost":      ("SALON_BOOST_ID",      "boost"),
        "halloffame": ("SALON_HOF_ID",        "hall of fame"),
        "reglement":  ("SALON_REGLEMENT_ID",  "règlement"),
        "event":      ("SALON_EVENT_ID",      "events"),
        "guide":      ("SALON_GUIDE_ID",      "guide"),
    }

    if not type_salon or type_salon.lower() not in TYPES:
        return await ctx.send(
            "❌ Usage : `.setsalon levelup` | `casino` | `gacha` | `boutique` | `guide` | `combat` | "
            "`duel` | `bienvenue` | `aurevoir` | `boost` | `halloffame` | `reglement @Role`"
        )

    t = type_salon.lower()
    var_name, label = TYPES[t]

    # ── Cas spécial : règlement ──────────────────────────────
    if t == "reglement":
        if not role:
            return await ctx.send("❌ Pour le règlement, mentionne le rôle à donner !\nEx: `.setsalon reglement @Membres`")
        ROLE_MEMBRE_NAME = role.name
        REGLEMENT_ROLE_ID = role.id
        SALON_REGLEMENT_ID = ctx.channel.id
        sauvegarder_salons()
        await ctx.send(f"✅ Salon **règlement** configuré sur {ctx.channel.mention} ! Rôle attribué : **{role.name}** 👥")
        await send_salon_embed(ctx.channel, "reglement")
        return

    # ── Lire la valeur actuelle ───────────────────────────────
    vals = {
        "SALON_LEVELUP_ID":    SALON_LEVELUP_ID,
        "SALON_CASINO_ID":     SALON_CASINO_ID,
        "SALON_GACHA_ID":      SALON_GACHA_ID,
        "SALON_BOUTIQUE_ID":   SALON_BOUTIQUE_ID,
        "SALON_COMBAT_ID":     SALON_COMBAT_ID,
        "SALON_DUEL_ID":       SALON_DUEL_ID,
        "SALON_BIENVENUE_ID":  SALON_BIENVENUE_ID,
        "SALON_AUREVOIR_ID":   SALON_AUREVOIR_ID,
        "SALON_BOOST_ID":      SALON_BOOST_ID,
        "SALON_HOF_ID":        SALON_HOF_ID,
        "SALON_EVENT_ID":      SALON_EVENT_ID,
        "SALON_GUIDE_ID":      SALON_GUIDE_ID,
    }
    current = vals.get(var_name)

    def set_var(vname, value):
        global SALON_LEVELUP_ID, SALON_CASINO_ID, SALON_GACHA_ID, SALON_BOUTIQUE_ID, SALON_EVENT_ID, SALON_GUIDE_ID
        global SALON_COMBAT_ID, SALON_DUEL_ID, SALON_BIENVENUE_ID, SALON_AUREVOIR_ID
        global SALON_BOOST_ID, SALON_HOF_ID
        if vname == "SALON_LEVELUP_ID":    SALON_LEVELUP_ID    = value
        elif vname == "SALON_CASINO_ID":   SALON_CASINO_ID     = value
        elif vname == "SALON_GACHA_ID":    SALON_GACHA_ID      = value
        elif vname == "SALON_BOUTIQUE_ID": SALON_BOUTIQUE_ID   = value
        elif vname == "SALON_COMBAT_ID":   SALON_COMBAT_ID     = value
        elif vname == "SALON_DUEL_ID":     SALON_DUEL_ID       = value
        elif vname == "SALON_BIENVENUE_ID":SALON_BIENVENUE_ID  = value
        elif vname == "SALON_AUREVOIR_ID": SALON_AUREVOIR_ID   = value
        elif vname == "SALON_BOOST_ID":    SALON_BOOST_ID      = value
        elif vname == "SALON_HOF_ID":      SALON_HOF_ID        = value
        elif vname == "SALON_EVENT_ID":    SALON_EVENT_ID      = value
        elif vname == "SALON_GUIDE_ID":    SALON_GUIDE_ID      = value

    # ── TOGGLE ────────────────────────────────────────────────
    # Même salon et déjà actif → DÉSACTIVER
    if current == ctx.channel.id:
        set_var(var_name, None)
        sauvegarder_salons()
        await ctx.send(embed=discord.Embed(
            description=f"🔕 Salon **{label}** **désactivé** — la restriction est levée.",
            color=0xe74c3c
        ))

    # Même salon mais None (désactivé) OU autre salon → ACTIVER + embed
    else:
        set_var(var_name, ctx.channel.id)
        sauvegarder_salons()
        await ctx.send(embed=discord.Embed(
            description=f"✅ Salon **{label}** **activé** sur {ctx.channel.mention} !",
            color=0x2ecc71
        ))
        await send_salon_embed(ctx.channel, t)

# ============================================================
#  UTILISER item offensif
# ============================================================
@bot.command(name="utiliser")
async def utiliser_cmd(ctx, item_type: str = None, cible: discord.Member = None):
    """Utilise un item offensif sur un joueur — .utiliser <item> @joueur"""
    import time as _time
    if not item_type or not cible:
        return await ctx.send("❌ Usage : `.utiliser <item> @joueur`\nItems : `freeze` `curse` `cadenas` `bombe_gacha` `fantome` `malediction` `vol_roll`")

    uid = str(ctx.author.id)
    uid_cible = str(cible.id)
    now_ts = _time.time()
    itype = item_type.lower()

    # Vérif que le joueur a bien l'item
    pending = getattr(bot, 'pending_items', {})
    if uid not in pending or itype not in pending.get(uid, {}):
        return await ctx.send(f"❌ Tu n\'as pas l\'item `{itype}` ! Achète-le avec `.acheter {itype}`")

    # Vérif amulette sur la cible
    amulette = getattr(bot, 'amulette_active', {})
    if uid_cible in amulette and amulette[uid_cible] > now_ts:
        # Renvoyer sur l'attaquant
        if uid in pending and itype in pending[uid]:
            del pending[uid][itype]
        return await ctx.send(embed=discord.Embed(
            title="🪬 Amulette activée !",
            description=f"**{cible.display_name}** est protégé par une **Amulette** ! Le sabotage se retourne contre **{ctx.author.mention}** ! 😈",
            color=0x9b59b6
        ))

    # Vérif protection divine
    if uid_cible in shield_active and shield_active[uid_cible] > now_ts:
        if uid in pending and itype in pending[uid]:
            del pending[uid][itype]
        restant = int((shield_active[uid_cible] - now_ts) // 60)
        return await ctx.send(f"🌟 **{cible.display_name}** est sous **Protection Divine** ! ({restant} min restantes)")

    # Vérif bouclier basique
    if itype in ("freeze","curse") and uid_cible in shield_active and shield_active[uid_cible] > now_ts:
        return await ctx.send(f"🛡️ **{cible.display_name}** est protégé par un bouclier !")

    # Consommer l'item
    if uid in pending and itype in pending.get(uid,{}):
        del pending[uid][itype]

    # ── FREEZE ───────────────────────────────────────────────
    if itype == "freeze":
        claim_freeze[uid_cible] = now_ts + 10
        await ctx.send(embed=discord.Embed(title="🧊 Sceau des Ombres !",
            description=f"**{cible.mention}** ne peut plus claim pendant **10 secondes** ! 😈", color=0x3498db))

    # ── CURSE ────────────────────────────────────────────────
    elif itype == "curse":
        claim_curse[uid_cible] = now_ts + 300
        await ctx.send(embed=discord.Embed(title="⏳ Malédiction !",
            description=f"**{cible.mention}** a +5 min sur son claim cooldown ! 😈", color=0x9b59b6))

    # ── CADENAS ──────────────────────────────────────────────
    elif itype == "cadenas":
        claim_freeze[uid_cible] = now_ts + 1800  # 30 min
        await ctx.send(embed=discord.Embed(title="🔒 Cadenas !",
            description=f"**{cible.mention}** ne peut plus claim pendant **30 minutes** ! 🔒", color=0xe74c3c))

    # ── BOMBE GACHA ──────────────────────────────────────────
    elif itype == "bombe_gacha":
        # Trouver la dernière carte claimée par la cible
        cible_cards = [k for k,v in claimed_cards.items() if v == uid_cible]
        if not cible_cards:
            return await ctx.send(f"❌ **{cible.display_name}** n'a aucune carte claimée !")
        # Prendre la dernière
        lost_key = cible_cards[-1]
        lost_card = ANIME_CARDS_DB[lost_key]
        del claimed_cards[lost_key]
        if uid_cible in gacha_collections and lost_key in gacha_collections[uid_cible]:
            del gacha_collections[uid_cible][lost_key]
        r_emoji = RARETE_EMOJI.get(lost_card["rarete"], "🔵")
        await ctx.send(embed=discord.Embed(title="💣 Bombe Gacha !",
            description=f"**{cible.mention}** perd sa carte **{lost_card['nom']}** {r_emoji} ! 💥\n*Envoyée dans le néant...*",
            color=0xe74c3c))
        # Notifier la victime en MP
        try:
            await cible.send(embed=discord.Embed(
                description=f"💣 **{ctx.author.display_name}** t'a posé une Bombe Gacha ! Tu as perdu **{lost_card['nom']}** {r_emoji} !",
                color=0xe74c3c))
        except: pass

    # ── FANTÔME ───────────────────────────────────────────────
    elif itype == "fantome":
        cible_cards = [k for k,v in claimed_cards.items() if v == uid_cible]
        if not cible_cards:
            return await ctx.send(f"❌ **{cible.display_name}** n'a aucune carte !")
        ghost_key = random.choice(cible_cards)
        ghost_card = ANIME_CARDS_DB[ghost_key]
        if not hasattr(bot, 'ghost_cards'):
            bot.ghost_cards = {}
        bot.ghost_cards[f"{uid_cible}_{ghost_key}"] = now_ts + 1800  # 30 min
        await ctx.send(embed=discord.Embed(title="👻 Fantôme !",
            description=f"Une carte de **{cible.mention}** devient invisible pendant **30 min** ! 👻",
            color=0x9b59b6))

    # ── MALÉDICTION RARE ──────────────────────────────────────
    elif itype == "malediction":
        # Vérif 1x par joueur par jour
        if not hasattr(bot, 'malediction_targets'):
            bot.malediction_targets = {}
        today = int(now_ts // 86400)
        key_mal = f"{uid}_{uid_cible}_{today}"
        if key_mal in bot.malediction_targets:
            return await ctx.send(f"❌ Tu as déjà maudit **{cible.display_name}** aujourd'hui !")
        bot.malediction_targets[key_mal] = True
        if not hasattr(bot, 'malediction_active'):
            bot.malediction_active = {}
        bot.malediction_active[uid_cible] = now_ts + 3600  # 1h
        await ctx.send(embed=discord.Embed(title="🎭 Malédiction Rare !",
            description=f"**{cible.mention}** ne tirera que des cartes **Communes** lors de son prochain roll ! 😈",
            color=0x9b59b6))

    # ── VOL DE ROLL ───────────────────────────────────────────
    elif itype == "vol_roll":
        if not hasattr(bot, 'vol_roll_counts'):
            bot.vol_roll_counts = {}
        count_key = f"{uid}_{uid_cible}"
        current = bot.vol_roll_counts.get(count_key, 0)
        if current >= 3:
            return await ctx.send(f"❌ Tu as déjà volé **3 rolls** à **{cible.display_name}** ! (limite atteinte)")
        if roll_data[uid_cible]["rolls"] <= 0:
            return await ctx.send(f"❌ **{cible.display_name}** n'a plus de rolls à voler !")
        roll_data[uid_cible]["rolls"] = max(0, roll_data[uid_cible]["rolls"] - 1)
        roll_data[uid]["rolls"] = min(roll_data[uid]["rolls"] + 1, ROLLS_MAX + 5)
        bot.vol_roll_counts[count_key] = current + 1
        await ctx.send(embed=discord.Embed(title="🎯 Vol de Roll !",
            description=f"**{ctx.author.mention}** vole 1 roll à **{cible.mention}** ! ({current+1}/3 vols sur ce joueur)",
            color=0xf39c12))

    else:
        await ctx.send(f"❌ Item `{itype}` inconnu !")

# ============================================================
#  GESTION GLOBALE DES ERREURS — anti-crash
# ============================================================
@bot.event
async def on_error(event, *args, **kwargs):
    import traceback
    print(f"❌ Erreur dans l'événement '{event}':")
    traceback.print_exc()

@bot.event
async def on_command_error(ctx, error):
    import traceback
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        return await ctx.send(f"❌ Argument manquant ! Tape `.help {ctx.command}` pour voir l'utilisation.")
    if isinstance(error, commands.CommandOnCooldown):
        return await ctx.send(f"⏳ Cooldown ! Réessaie dans **{error.retry_after:.1f}s**.")
    if isinstance(error, commands.MissingPermissions):
        return await ctx.send("❌ Tu n'as pas la permission !")
    # Log toutes les autres erreurs sans faire crasher le bot
    print(f"❌ Erreur commande '{ctx.command}': {type(error).__name__}: {error}")
    traceback.print_exc()

# ============================================================
#  🆕 NOUVELLES COMMANDES
# ============================================================

# Stockage snipe
snipe_data = {}  # {channel_id: {"content": str, "author": str, "avatar": str}}

@bot.event
async def on_message_delete(message):
    if message.author.bot or not message.content:
        return
    snipe_data[message.channel.id] = {
        "content": message.content,
        "author":  message.author.display_name,
        "avatar":  str(message.author.display_avatar.url),
    }

@bot.command(name="snipe")
async def snipe_cmd(ctx):
    """Affiche le dernier message supprimé — .snipe"""
    data = snipe_data.get(ctx.channel.id)
    if not data:
        return await ctx.send("❌ Aucun message supprimé récemment dans ce salon !")
    embed = discord.Embed(
        description=data["content"],
        color=0xe74c3c
    )
    embed.set_author(name=data["author"], icon_url=data["avatar"])
    embed.set_footer(text="💀 Message supprimé")
    await ctx.send(embed=embed)

@bot.command(name="avatar", aliases=["av", "pp"])
async def avatar_cmd(ctx, membre: discord.Member = None):
    """Affiche l'avatar d'un membre — .avatar @membre"""
    cible = membre or ctx.author
    embed = discord.Embed(
        title=f"🖼️ Avatar de {cible.display_name}",
        color=0x9b59b6
    )
    embed.set_image(url=cible.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name="choisir", aliases=["pick","winner"])
async def choisir_cmd(ctx, message_id: str = None):
    """Choisit un gagnant aléatoire parmi les réactions d'un message — .choisir <message_id>"""
    if not message_id or not message_id.isdigit():
        return await ctx.send("❌ Utilise : `.choisir <ID du message>`\nCopie l'ID du message en faisant clic droit → Copier l'ID")
    try:
        msg = await ctx.channel.fetch_message(int(message_id))
    except:
        return await ctx.send("❌ Message introuvable dans ce salon !")
    if not msg.reactions:
        return await ctx.send("❌ Ce message n'a aucune réaction !")
    # Récupérer tous les membres qui ont réagi
    participants = set()
    for reaction in msg.reactions:
        async for user in reaction.users():
            if not user.bot:
                participants.add(user)
    if not participants:
        return await ctx.send("❌ Aucun participant trouvé !")
    gagnant = random.choice(list(participants))
    embed = discord.Embed(
        title="🎉 Gagnant tiré au sort !",
        description=f"**{gagnant.mention}** remporte le tirage ! 🏆\n*Parmi {len(participants)} participant(s)*",
        color=0xf1c40f
    )
    await ctx.send(embed=embed)

@bot.command(name="warn")
@commands.has_permissions(manage_messages=True)
async def warn_cmd(ctx, membre: discord.Member = None, *, raison: str = "Aucune raison précisée"):
    """Avertit un membre — .warn @membre <raison>"""
    if not membre:
        return await ctx.send("❌ Mentionne un membre ! Ex: `.warn @membre comportement irrespectueux`")
    if membre.bot:
        return await ctx.send("❌ On peut pas avertir un bot !")
    embed_mp = discord.Embed(
        title="⚠️ Avertissement",
        description=(
            f"Tu as reçu un avertissement sur **{ctx.guild.name}**\n\n"
            f"📋 **Raison :** {raison}\n"
            f"👮 **Par :** {ctx.author.display_name}"
        ),
        color=0xff6600
    )
    try:
        await membre.send(embed=embed_mp)
        mp_sent = "✅ MP envoyé"
    except:
        mp_sent = "❌ MP impossible (MPs fermés)"
    embed_pub = discord.Embed(
        description=f"⚠️ **{membre.mention}** a été averti\n📋 Raison : {raison}\n{mp_sent}",
        color=0xff6600
    )
    await ctx.send(embed=embed_pub)

@bot.command(name="slowmode", aliases=["slow"])
@commands.has_permissions(manage_channels=True)
async def slowmode_cmd(ctx, secondes: int = 0):
    """Active le slowmode — .slowmode <secondes> (0 = désactiver)"""
    if secondes < 0 or secondes > 21600:
        return await ctx.send("❌ Entre 0 et 21600 secondes !")
    await ctx.channel.edit(slowmode_delay=secondes)
    if secondes == 0:
        await ctx.send("✅ Slowmode désactivé !")
    else:
        await ctx.send(f"✅ Slowmode activé : **{secondes} secondes** entre chaque message")

@bot.command(name="lock")
@commands.has_permissions(manage_channels=True)
async def lock_cmd(ctx, salon: discord.TextChannel = None):
    """Verrouille un salon — .lock [#salon]"""
    channel = salon or ctx.channel
    overwrite = channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False
    await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send(f"🔒 {channel.mention} est maintenant verrouillé !")

@bot.command(name="unlock")
@commands.has_permissions(manage_channels=True)
async def unlock_cmd(ctx, salon: discord.TextChannel = None):
    """Déverrouille un salon — .unlock [#salon]"""
    channel = salon or ctx.channel
    overwrite = channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = None
    await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send(f"🔓 {channel.mention} est maintenant déverrouillé !")

# ─── Commandes animés/dramas/quotes (réparées) ───────────────

ANIME_RECS = [
    ("Vinland Saga", "⚔️", "Viking épique — trahison, vengeance et rédemption"),
    ("Mushishi", "🍄", "Contemplatif et poétique — esprits de la nature"),
    ("Ping Pong The Animation", "🏓", "Sport animé le plus unique jamais fait"),
    ("Planetes", "🚀", "Hard SF — éboueurs de l'espace"),
    ("Paranoia Agent", "😰", "Thriller psychologique surréaliste de Satoshi Kon"),
    ("Tatami Galaxy", "🌀", "Boucle temporelle et choix de vie"),
    ("Kaiji", "🎲", "Survie et jeux d'argent — tension maximale"),
    ("Legend of the Galactic Heroes", "🌌", "Space opera politique légendaire"),
    ("Monster", "🎭", "Thriller psychologique — médecin vs serial killer"),
    ("Nana", "🎸", "Drame musical adulte et émouvant"),
    ("Fruits Basket", "🌸", "Romance et trauma — magnifiquement écrit"),
    ("Toradora", "🐉", "Romance scolaire — tsundere iconique"),
    ("Clannad After Story", "💙", "Larmoyant et magnifique — grandir ensemble"),
]

DRAMA_RECS = [
    ("My Mister", "🏙️", "Le drama le plus poignant de la décennie"),
    ("Reply 1988", "📼", "Nostalgie pure — amitié et famille"),
    ("Misaeng", "💼", "Drama de bureau le plus réaliste"),
    ("Signal", "📻", "Thriller temporel haletant"),
    ("Flower of Evil", "🌹", "Thriller conjugal → impossible de lâcher"),
    ("The World of the Married", "💔", "Drame de vengeance intense"),
    ("Move to Heaven", "📦", "Drama qui te brise le cœur mais te reconstruit"),
    ("Our Blues", "🌊", "Anthologie des vies ordinaires de Jeju"),
    ("Beyond Evil", "🔍", "Thriller policier — meilleur duo de l'année"),
    ("Juvenile Justice", "⚖️", "Crimes de mineurs — très sombre mais brillant"),
]

ANIMEQUOTES = [
    ("*« Les humains forts ne sont pas ceux qui ne pleurent pas — ce sont ceux qui pleurent et se relèvent. »*", "Monkey D. Luffy — One Piece 🏴‍☠️"),
    ("*« Si tu ne te bats pas, tu ne peux pas gagner. »*", "Eren Yeager — Attack on Titan ⚔️"),
    ("*« La douleur nous permet de grandir. »*", "Pain — Naruto 🌀"),
    ("*« Un seul coup suffit. »*", "Saitama — One Punch Man 👊"),
    ("*« Le chemin vers le sommet n'a pas de raccourcis. »*", "Rock Lee — Naruto 🔥"),
    ("*« Je ne reculerai jamais et je ne regretterai rien. »*", "Naruto Uzumaki — Naruto 🍥"),
    ("*« Peu importe combien tu es blessé, redresse-toi. »*", "Izuku Midoriya — MHA 💚"),
    ("*« Deviens si fort que personne ne puisse te briser. »*", "Vegeta — Dragon Ball Z 👑"),
    ("*« Ceux qui abandonnent leurs amis sont pire que des ordures. »*", "Kakashi — Naruto ⚡"),
    ("*« Je protègerai ceux que j'aime, quoi qu'il arrive. »*", "Tanjiro — Demon Slayer 🔥"),
    ("*« Le destin n'est pas écrit à l'avance. »*", "Lelouch — Code Geass ♟️"),
    ("*« Si tu trouves quelque chose de précieux, bats-toi pour le garder. »*", "Gojo Satoru — JJK ♾️"),
    ("*« Être le plus fort ne suffit pas. Tu dois avoir une raison de te battre. »*", "Levi Ackerman — AoT ⚔️"),
]

QUOTES_KDRAMA = [
    ("*« Même si tu oublies tout, je me souviendrai pour deux. »*", "Goblin 🕯️"),
    ("*« L'amour n'est pas une faiblesse, c'est ta plus grande force. »*", "Crash Landing on You 🪂"),
    ("*« Les gens ne changent pas. Mais les circonstances, si. »*", "My Mister 🏙️"),
    ("*« On ne choisit pas d'où on vient, mais on choisit où on va. »*", "Itaewon Class 🍺"),
    ("*« Même dans les ténèbres, une petite lumière suffit. »*", "Kingdom 👑"),
    ("*« Le passé ne peut pas être changé, mais le futur, lui, t'appartient. »*", "Signal 📻"),
    ("*« Aimer quelqu'un, c'est lui donner le pouvoir de te briser. »*", "The World of the Married 💔"),
    ("*« Parfois, disparaître est la meilleure façon de protéger ceux qu'on aime. »*", "Reply 1988 📼"),
]

@bot.command(name="animerec", aliases=["anirec"])
async def animerec_cmd(ctx):
    """Recommande un animé aléatoire — .animerec"""
    titre, emoji, desc = random.choice(ANIME_RECS)
    embed = discord.Embed(
        title=f"{emoji} Recommandation Animé",
        description=f"## {titre}\n{desc}",
        color=0x9b59b6
    )
    embed.set_footer(text="Tape .animerec pour une autre reco !")
    await ctx.send(embed=embed)

@bot.command(name="dramarec")
async def dramarec_cmd(ctx):
    """Recommande un drama aléatoire — .dramarec"""
    titre, emoji, desc = random.choice(DRAMA_RECS)
    embed = discord.Embed(
        title=f"{emoji} Recommandation Kdrama",
        description=f"## {titre}\n{desc}",
        color=0xff6b9d
    )
    embed.set_footer(text="Tape .dramarec pour une autre reco !")
    await ctx.send(embed=embed)

@bot.command(name="animequote", aliases=["aquote"])
async def animequote_cmd(ctx):
    """Citation d'animé aléatoire — .animequote"""
    texte, auteur = random.choice(ANIMEQUOTES)
    embed = discord.Embed(
        description=f"{texte}\n\n— *{auteur}*",
        color=0x9b59b6
    )
    await ctx.send(embed=embed)

@bot.command(name="quote")
async def quote_cmd(ctx):
    """Citation aléatoire animé ou kdrama — .quote"""
    all_quotes = [(t, f"Animé — {a}") for t, a in ANIMEQUOTES] + [(t, f"Kdrama — {a}") for t, a in QUOTES_KDRAMA]
    texte, source = random.choice(all_quotes)
    embed = discord.Embed(
        description=f"{texte}\n\n— *{source}*",
        color=0xf1c40f
    )
    await ctx.send(embed=embed)

@bot.command(name="anime")
async def anime_cmd(ctx, *, titre: str = None):
    """Infos sur un animé — .anime <titre>"""
    if not titre:
        return await ctx.send("❌ Utilise : `.anime <titre>` — Ex: `.anime attack on titan`")
    embed = discord.Embed(
        title=f"🔍 Recherche : {titre}",
        description=f"Pour des infos complètes sur **{titre}**, consulte :\n🌐 [MyAnimeList](https://myanimelist.net/search/all?q={titre.replace(' ','+')})\n📺 [Anilist](https://anilist.co/search/anime?search={titre.replace(' ','+')})",
        color=0x9b59b6
    )
    await ctx.send(embed=embed)

@bot.command(name="drama")
async def drama_cmd(ctx, *, titre: str = None):
    """Infos sur un drama — .drama <titre>"""
    if not titre:
        return await ctx.send("❌ Utilise : `.drama <titre>` — Ex: `.drama goblin`")
    embed = discord.Embed(
        title=f"🔍 Recherche : {titre}",
        description=f"Pour des infos complètes sur **{titre}**, consulte :\n🌐 [MDL](https://mydramalist.com/search?q={titre.replace(' ','+')})\n🎬 [Viki](https://www.viki.com/explore?q={titre.replace(' ','+')})",
        color=0xff6b9d
    )
    await ctx.send(embed=embed)

# ─── Sorties (à venir uniquement, séparées) ──────────────────

@bot.command(name="sorties")
async def sorties_cmd(ctx):
    """Affiche les prochaines sorties dramas & animés — .sorties"""
    animes = [s for s in SORTIES if "Animé" in s["type"]]
    kdramas = [s for s in SORTIES if "Kdrama" in s["type"] or "drama" in s["type"].lower()]
    embed = discord.Embed(
        title="📅 Prochaines Sorties",
        color=0xff6b9d
    )
    if animes:
        embed.add_field(
            name="✨ ANIMÉS",
            value="\n".join(f"**{s['titre']}** — {s['date']} • {s['plateforme']}" for s in animes),
            inline=False
        )
    if kdramas:
        embed.add_field(
            name="🎬 KDRAMAS",
            value="\n".join(f"**{s['titre']}** — {s['date']} • {s['plateforme']}" for s in kdramas),
            inline=False
        )
    embed.set_footer(text="💡 Liste mise à jour manuellement")
    await ctx.send(embed=embed)

# ─── Système d'invitations ───────────────────────────────────

invite_tracker  = {}   # {invited_user_id: inviter_user_id}
invite_counts   = defaultdict(int)   # {inviter_user_id: count}
guild_invites   = {}   # cache {guild_id: {code: uses}}
SALON_INVITATION_ID = None  # salon où afficher les invitations

@bot.event
async def on_invite_create(invite):
    if invite.guild:
        if invite.guild.id not in guild_invites:
            guild_invites[invite.guild.id] = {}
        guild_invites[invite.guild.id][invite.code] = invite.uses or 0

@bot.command(name="setinvitation")
@commands.has_permissions(administrator=True)
async def setinvitation_cmd(ctx):
    """Définit le salon actuel pour les logs d'invitations — .setinvitation"""
    global SALON_INVITATION_ID
    SALON_INVITATION_ID = ctx.channel.id
    await ctx.send(embed=discord.Embed(
        description=f"✅ Salon d'invitation configuré sur {ctx.channel.mention} !\nLes nouvelles invitations seront affichées ici.",
        color=0x2ecc71
    ))

@bot.command(name="invitations", aliases=["invites","inv"])
async def invitations_cmd(ctx, membre: discord.Member = None):
    """Voir le nombre d'invitations — .invitations [@membre]"""
    cible = membre or ctx.author
    count = invite_counts[str(cible.id)]
    embed = discord.Embed(
        title="🔗 Invitations",
        description=f"**{cible.display_name}** a invité **{count}** membre(s) sur le serveur ! 🎉",
        color=0x2ecc71
    )
    await ctx.send(embed=embed)

@bot.command(name="topinvitations", aliases=["topinvites"])
async def topinvitations_cmd(ctx):
    """Classement des membres qui ont le plus invité — .topinvitations"""
    if not invite_counts:
        return await ctx.send("❌ Aucune invitation enregistrée pour l'instant !")
    sorted_invites = sorted(invite_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    desc = ""
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    for i, (uid, count) in enumerate(sorted_invites):
        member = ctx.guild.get_member(int(uid))
        name = member.display_name if member else f"Membre {uid}"
        desc += f"{medals[i]} **{name}** — {count} invitation(s)\n"
    embed = discord.Embed(
        title="🏆 Top Invitations",
        description=desc,
        color=0xf1c40f
    )
    await ctx.send(embed=embed)

# ─── Sondage simplifié ───────────────────────────────────────

@bot.command(name="sondage", aliases=["poll"])
async def sondage_cmd(ctx, *, question: str = None):
    """Crée un sondage rapide — .sondage <question>"""
    if not question:
        return await ctx.send("❌ Utilise : `.sondage <ta question>`\nEx: `.sondage Demon Slayer ou JJK ?`")
    embed = discord.Embed(
        title="📊 Sondage",
        description=f"**{question}**",
        color=0x3498db
    )
    embed.set_footer(text=f"Sondage de {ctx.author.display_name}")
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    await msg.add_reaction("🤷")
    try:
        await ctx.message.delete()
    except:
        pass

# ─── .kick avec motif en MP ──────────────────────────────────


# ============================================================
#  🎭 SYSTÈME AUTOROLE
# ============================================================

autorole_panels = {}   
reaction_roles = {}    # {msg_id: {emoji: role_id}}# {guild_id: [{message_id, channel_id, roles: [{emoji, role_id, label}], image}]}
AUTOROLE_FILE = "autorole_config.json"

def save_autorole():
    try:
        with open(AUTOROLE_FILE, "w") as f:
            import json as _json
            _json.dump(autorole_panels, f)
    except:
        pass

def load_autorole():
    global autorole_panels
    try:
        import json as _json
        with open(AUTOROLE_FILE, "r") as f:
            autorole_panels = _json.load(f)
    except:
        autorole_panels = {}

@bot.command(name="autorole")
@commands.has_permissions(administrator=True)
async def autorole_cmd(ctx, *, args: str = None):
    """Crée un panel autorole — .autorole help"""
    if not args or args == "help":
        embed = discord.Embed(
            title="🎭 Système Autorole",
            description=(
                "**Créer un panel autorole interactif avec réactions**\n\n"
                "**Étape 1 — Créer le panel :**\n"
                "`.autorole create <titre> | <description>`\n"
                "*Ex: `.autorole create Choisis ton rôle | Réagis pour obtenir un rôle !`*\n\n"
                "**Étape 2 — Ajouter des rôles :**\n"
                "`.autorole add <message_id> <emoji> @role <label>`\n"
                "*Ex: `.autorole add 123456789 🎬 @Kdrama Fan Drama`*\n\n"
                "**Étape 3 — Ajouter une image (optionnel) :**\n"
                "`.autorole image <message_id> <url>`\n\n"
                "**Supprimer un panel :**\n"
                "`.autorole delete <message_id>`\n\n"
                "**Voir les panels actifs :**\n"
                "`.autorole list`"
            ),
            color=0x9b59b6
        )
        return await ctx.send(embed=embed)

    parts = args.split(" ", 1)
    sub = parts[0].lower()

    # ── Créer un panel ──
    if sub == "create":
        if len(parts) < 2 or "|" not in parts[1]:
            return await ctx.send("❌ Usage : `.autorole create <titre> | <description>`")
        titre, desc = parts[1].split("|", 1)
        embed = discord.Embed(
            title=titre.strip(),
            description=desc.strip(),
            color=0x9b59b6
        )
        embed.set_footer(text="Réagis avec les emojis ci-dessous pour obtenir un rôle !")
        msg = await ctx.send(embed=embed)
        guild_id = str(ctx.guild.id)
        if guild_id not in autorole_panels:
            autorole_panels[guild_id] = []
        autorole_panels[guild_id].append({
            "message_id": str(msg.id),
            "channel_id": str(ctx.channel.id),
            "roles": [],
            "image": None
        })
        save_autorole()
        await ctx.send(f"✅ Panel créé ! ID du message : `{msg.id}`\nAjoute des rôles avec `.autorole add {msg.id} <emoji> @role <label>`", delete_after=15)

    # ── Ajouter un rôle ──
    elif sub == "add":
        sub_parts = parts[1].split(" ", 3) if len(parts) > 1 else []
        if len(sub_parts) < 3:
            return await ctx.send("❌ Usage : `.autorole add <message_id> <emoji> @role [label]`")
        msg_id = sub_parts[0]
        emoji = sub_parts[1]
        role_mention = sub_parts[2]
        label = sub_parts[3] if len(sub_parts) > 3 else ""
        # Trouver le rôle
        role = None
        if ctx.message.role_mentions:
            role = ctx.message.role_mentions[0]
        else:
            role_id = role_mention.strip("<@&>")
            if role_id.isdigit():
                role = ctx.guild.get_role(int(role_id))
        if not role:
            return await ctx.send("❌ Rôle introuvable ! Mentionne le rôle avec @")
        # Trouver le panel
        guild_id = str(ctx.guild.id)
        panel = None
        for p in autorole_panels.get(guild_id, []):
            if p["message_id"] == msg_id:
                panel = p
                break
        if not panel:
            return await ctx.send("❌ Panel introuvable ! Vérifie l'ID du message.")
        # Ajouter le rôle au panel
        panel["roles"].append({"emoji": emoji, "role_id": str(role.id), "label": label or role.name})
        save_autorole()
        # Modifier l'embed
        try:
            channel = ctx.guild.get_channel(int(panel["channel_id"]))
            msg = await channel.fetch_message(int(msg_id))
            embed = msg.embeds[0]
            roles_text = "\n".join([f"{r['emoji']} — **{r['label']}**" for r in panel["roles"]])
            embed.clear_fields()
            embed.add_field(name="Rôles disponibles", value=roles_text, inline=False)
            await msg.edit(embed=embed)
            await msg.add_reaction(emoji)
        except Exception as e:
            print(f"Autorole add error: {e}")
        await ctx.send(f"✅ Rôle **{role.name}** ajouté avec l'emoji {emoji} !", delete_after=5)

    # ── Ajouter une image ──
    elif sub == "image":
        sub_parts = parts[1].split(" ", 1) if len(parts) > 1 else []
        if len(sub_parts) < 2:
            return await ctx.send("❌ Usage : `.autorole image <message_id> <url>`")
        msg_id, url = sub_parts[0], sub_parts[1]
        guild_id = str(ctx.guild.id)
        for p in autorole_panels.get(guild_id, []):
            if p["message_id"] == msg_id:
                p["image"] = url
                save_autorole()
                try:
                    channel = ctx.guild.get_channel(int(p["channel_id"]))
                    msg = await channel.fetch_message(int(msg_id))
                    embed = msg.embeds[0]
                    embed.set_image(url=url)
                    await msg.edit(embed=embed)
                    await ctx.send("✅ Image ajoutée au panel !", delete_after=5)
                except Exception as e:
                    await ctx.send(f"❌ Erreur : {e}")
                return
        await ctx.send("❌ Panel introuvable !")

    # ── Supprimer un panel ──
    elif sub == "delete":
        msg_id = parts[1].strip() if len(parts) > 1 else ""
        guild_id = str(ctx.guild.id)
        panels = autorole_panels.get(guild_id, [])
        new_panels = [p for p in panels if p["message_id"] != msg_id]
        if len(new_panels) == len(panels):
            return await ctx.send("❌ Panel introuvable !")
        autorole_panels[guild_id] = new_panels
        save_autorole()
        await ctx.send("✅ Panel supprimé !")

    # ── Lister les panels ──
    elif sub == "list":
        guild_id = str(ctx.guild.id)
        panels = autorole_panels.get(guild_id, [])
        if not panels:
            return await ctx.send("❌ Aucun panel autorole configuré !")
        desc = ""
        for p in panels:
            channel = ctx.guild.get_channel(int(p["channel_id"]))
            chan_name = channel.mention if channel else "salon supprimé"
            roles_count = len(p["roles"])
            desc += f"📌 Message `{p['message_id']}` dans {chan_name} — {roles_count} rôle(s)\n"
        embed = discord.Embed(title="🎭 Panels Autorole actifs", description=desc, color=0x9b59b6)
        await ctx.send(embed=embed)

# autorole géré dans on_raw_reaction_add principal

# autorole remove géré dans on_raw_reaction_remove principal


# ── gachagive ─────────────────────────────────────────────────────
@bot.command(name="gachagive", aliases=["gcgive","cardgive"])
async def gachagive_cmd(ctx, membre: discord.Member = None, *, perso: str = None):
    """Donne une de tes cartes à un membre — .gachagive @membre <perso>"""
    if SALON_GACHA_ID and ctx.channel.id != SALON_GACHA_ID:
        salon = ctx.guild.get_channel(SALON_GACHA_ID)
        mention = salon.mention if salon else "le salon gacha"
        return await ctx.send(f"🎰 Cette commande c'est dans {mention} !", delete_after=5)
    if not membre or not perso:
        return await ctx.send("❌ Usage : `.gachagive @membre <perso>`\nEx: `.gachagive @Ryaax naruto`")
    if membre == ctx.author:
        return await ctx.send("❌ Tu peux pas te donner une carte à toi-même !")
    if membre.bot:
        return await ctx.send("❌ Tu peux pas donner une carte à un bot !")

    uid = str(ctx.author.id)
    key = perso.lower().strip().replace(" ", "")
    if key not in ANIME_CARDS_DB:
        matches = [k for k in ANIME_CARDS_DB if perso.lower() in ANIME_CARDS_DB[k]["nom"].lower()]
        if not matches:
            return await ctx.send(f"❌ Personnage `{perso}` introuvable !")
        key = matches[0]

    c = ANIME_CARDS_DB[key]
    if claimed_cards.get(key) != uid:
        return await ctx.send(f"❌ Tu ne possèdes pas **{c['nom']}** !")

    target_uid = str(membre.id)
    # Transférer
    claimed_cards[key] = target_uid
    if uid in gacha_collections and key in gacha_collections[uid]:
        del gacha_collections[uid][key]
    gacha_collections[target_uid][key] = {"fusion": 0}

    rarete_emoji = RARETE_EMOJI.get(c["rarete"], "🔵")
    couleur = RARETE_COULEURS.get(c["rarete"], 0x95a5a6)
    embed = discord.Embed(
        title="🎁 Carte offerte !",
        description=f"{ctx.author.mention} a offert **{c['nom']}** {rarete_emoji} à {membre.mention} !",
        color=couleur
    )
    if c.get("image"):
        embed.set_thumbnail(url=c["image"])
    await ctx.send(embed=embed)

# ── gachatrade ─────────────────────────────────────────────────────
@bot.command(name="gachatrade", aliases=["gctrade","cardtrade"])
async def gachatrade_cmd(ctx, membre: discord.Member = None, ma_carte: str = None, *, sa_carte: str = None):
    """Propose un échange de carte — .gachatrade @membre <ma carte> <sa carte>"""
    if SALON_GACHA_ID and ctx.channel.id != SALON_GACHA_ID:
        salon = ctx.guild.get_channel(SALON_GACHA_ID)
        mention = salon.mention if salon else "le salon gacha"
        return await ctx.send(f"🎰 Cette commande c'est dans {mention} !", delete_after=5)
    if not membre or not ma_carte or not sa_carte:
        return await ctx.send("❌ Usage : `.gachatrade @membre <ta carte> <sa carte>`\nEx: `.gachatrade @Ryaax naruto gojo`")
    if membre == ctx.author:
        return await ctx.send("❌ Tu peux pas trader avec toi-même !")
    if membre.bot:
        return await ctx.send("❌ Tu peux pas trader avec un bot !")

    uid = str(ctx.author.id)
    target_uid = str(membre.id)

    # Trouver ma carte
    key1 = ma_carte.lower().strip().replace(" ", "")
    if key1 not in ANIME_CARDS_DB:
        matches = [k for k in ANIME_CARDS_DB if ma_carte.lower() in ANIME_CARDS_DB[k]["nom"].lower()]
        if not matches:
            return await ctx.send(f"❌ Carte `{ma_carte}` introuvable !")
        key1 = matches[0]

    # Trouver sa carte
    key2 = sa_carte.lower().strip().replace(" ", "")
    if key2 not in ANIME_CARDS_DB:
        matches = [k for k in ANIME_CARDS_DB if sa_carte.lower() in ANIME_CARDS_DB[k]["nom"].lower()]
        if not matches:
            return await ctx.send(f"❌ Carte `{sa_carte}` introuvable !")
        key2 = matches[0]

    c1 = ANIME_CARDS_DB[key1]
    c2 = ANIME_CARDS_DB[key2]

    if claimed_cards.get(key1) != uid:
        return await ctx.send(f"❌ Tu ne possèdes pas **{c1['nom']}** !")
    if claimed_cards.get(key2) != target_uid:
        return await ctx.send(f"❌ **{membre.display_name}** ne possède pas **{c2['nom']}** !")

    r1 = RARETE_EMOJI.get(c1["rarete"], "🔵")
    r2 = RARETE_EMOJI.get(c2["rarete"], "🔵")

    embed = discord.Embed(
        title="🔄 Proposition d'échange !",
        description=(
            f"{ctx.author.mention} propose à {membre.mention} :\n\n"
            f"**{c1['nom']}** {r1} ↔️ **{c2['nom']}** {r2}\n\n"
            f"{membre.mention} — réponds ✅ pour accepter ou ❌ pour refuser !"
        ),
        color=0xf1c40f
    )
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")

    def check(reaction, user):
        return user.id == membre.id and reaction.message.id == msg.id and str(reaction.emoji) in ["✅","❌"]

    try:
        reaction, user = await bot.wait_for("reaction_add", timeout=60.0, check=check)
        if str(reaction.emoji) == "✅":
            # Effectuer l'échange
            claimed_cards[key1] = target_uid
            claimed_cards[key2] = uid
            if uid in gacha_collections:
                gacha_collections[uid].pop(key1, None)
                gacha_collections[uid][key2] = {"fusion": 0}
            if target_uid in gacha_collections:
                gacha_collections[target_uid].pop(key2, None)
                gacha_collections[target_uid][key1] = {"fusion": 0}
            embed_ok = discord.Embed(
                title="✅ Échange effectué !",
                description=f"**{c1['nom']}** {r1} ↔️ **{c2['nom']}** {r2}\nL'échange a bien eu lieu !",
                color=0x2ecc71
            )
            await msg.edit(embed=embed_ok)
            try: await msg.clear_reactions()
            except: pass
        else:
            embed_no = discord.Embed(
                description=f"❌ **{membre.display_name}** a refusé l'échange.",
                color=0xe74c3c
            )
            await msg.edit(embed=embed_no)
            try: await msg.clear_reactions()
            except: pass
    except asyncio.TimeoutError:
        embed_to = discord.Embed(
            description="⏰ Échange expiré — pas de réponse dans les 60 secondes.",
            color=0x95a5a6
        )
        await msg.edit(embed=embed_to)
        try: await msg.clear_reactions()
        except: pass

# ── gacharesetall ──────────────────────────────────────────────────
@bot.command(name="gacharesetall")
@commands.has_permissions(administrator=True)
async def gacharesetall_cmd(ctx):
    """Remet le gacha à zéro — admin only — .gacharesetall"""
    embed = discord.Embed(
        title="⚠️ RESET TOTAL DU GACHA",
        description=(
            "Tu es sur le point de **tout remettre à zéro** :\n"
            "• Toutes les cartes claimées perdues\n"
            "• Toutes les collections effacées\n"
            "• Tous les niveaux de fusion réinitialisés\n"
            "• Tous les rolls réinitialisés\n\n"
            "Réagis ✅ pour confirmer ou ❌ pour annuler."
        ),
        color=0xe74c3c
    )
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")

    def check(reaction, user):
        return user == ctx.author and reaction.message.id == msg.id and str(reaction.emoji) in ["✅","❌"]

    try:
        reaction, user = await bot.wait_for("reaction_add", timeout=30.0, check=check)
        if str(reaction.emoji) == "✅":
            claimed_cards.clear()
            gacha_collections.clear()
            fusion_levels.clear()
            roll_data.clear()
            claim_cooldown.clear()
            claim_reduction.clear()
            gacha_wishlist.clear()
            rarity_boost.clear()
            collection_order.clear()
            embed_ok = discord.Embed(
                title="✅ Gacha remis à zéro !",
                description="Toutes les cartes, collections et données gacha ont été réinitialisées.\nLe jeu repart de zéro !",
                color=0x2ecc71
            )
            await msg.edit(embed=embed_ok)
        else:
            await msg.edit(embed=discord.Embed(description="❌ Reset annulé.", color=0x95a5a6))
        try: await msg.clear_reactions()
        except: pass
    except asyncio.TimeoutError:
        await msg.edit(embed=discord.Embed(description="⏰ Reset annulé — timeout.", color=0x95a5a6))
        try: await msg.clear_reactions()
        except: pass


# ============================================================
# ============================================================
#  💰 ÉCONOMIE AVANCÉE & NOUVELLES FEATURES
# ============================================================

import random as _random

travailler_cd = {}
braquage_cd = {}
investissements = {}
missions_data = {}
liga_data = {}
faction_data = {}
faction_rep = {}
marche_noir_actif = {}
invasion_active = {}
coffre_actif = {}
nuit_chasse_active = False

JOBS = [
    ("🍜 Cuisinier chez Sanji", 80, 150),
    ("⚔️ Entraîneur au Survey Corps", 60, 120),
    ("🃏 Dealer de cartes gacha", 90, 140),
    ("🔮 Oracle du QG", 70, 130),
    ("📺 Critique d'animé", 50, 100),
    ("🎯 Chasseur de primes", 100, 160),
    ("🍥 Vendeur de ramen", 60, 110),
    ("🐸 Apprenti de Jiraiya", 85, 145),
]

ANIMES_INVESTISSEMENT = [
    "Demon Slayer S3", "Jujutsu Kaisen S3", "One Piece",
    "Solo Leveling S2", "Chainsaw Man S3", "Bleach TYBW",
    "Dandadan S2", "Kaiju No.8 S2", "Blue Lock S3",
    "Black Clover Film", "Naruto Next Gen", "Vinland Saga S3",
]

FACTIONS = {
    "akatsuki":      {"emoji": "<:Rougeakatsuki:1484620623652061337>", "nom": "Akatsuki",                      "serie": "Naruto"},
    "surveycorps":   {"emoji": "<:Blancbataillondexploration:1484620708641505360>", "nom": "Bataillon d'Exploration", "serie": "AoT"},
    "strawhat":      {"emoji": "<:Blancmugiwara:1484620802677538816>", "nom": "Équipage du Chapeau de Paille", "serie": "One Piece"},
    "phantomtroupe": {"emoji": "🕷️", "nom": "Phantom Troupe",         "serie": "HxH"},
    "gotei13":       {"emoji": "🌸", "nom": "Gotei 13",                "serie": "Bleach"},
    "ua":            {"emoji": "🍃", "nom": "Lycée U.A.",              "serie": "MHA"},
}

BOSS_INVASIONS = [
    {"nom": "Muzan Kibutsuji", "emoji": "🌙", "pv": 5000, "serie": "Demon Slayer", "image": "https://i.imgur.com/amD1hXZ.jpg"},
    {"nom": "Sosuke Aizen",    "emoji": "🦋", "pv": 4500, "serie": "Bleach",       "image": "https://i.imgur.com/rtSGfrn.jpg"},
    {"nom": "Madara Uchiha",   "emoji": "👁️", "pv": 6000, "serie": "Naruto",       "image": "https://i.imgur.com/FYEJwwH.jpg"},
    {"nom": "All For One",     "emoji": "☠️", "pv": 4000, "serie": "MHA",          "image": "https://i.imgur.com/4926kae.jpg"},
    {"nom": "Yhwach",          "emoji": "👑", "pv": 5500, "serie": "Bleach",        "image": "https://i.imgur.com/UR1i6Tb.jpg"},
    {"nom": "Meruem",          "emoji": "♟️", "pv": 4800, "serie": "HxH",           "image": "https://i.imgur.com/ajOXRt1.jpg"},
]

# ── .travailler ──────────────────────────────────────────────
@bot.command(name="travailler", aliases=["work", "boulot"])
async def travailler_cmd(ctx):
    """Travaille pour gagner des pièces — .travailler (cooldown 4h)"""
    import time as _t
    uid = str(ctx.author.id)
    now = _t.time()
    if now - travailler_cd.get(uid, 0) < 14400:
        reste = int((14400 - (now - travailler_cd[uid])) // 60)
        h, m = reste // 60, reste % 60
        return await ctx.send(embed=discord.Embed(description=f"😴 Épuisé ! Retravailler dans **{h}h{m:02d}min**", color=0x95a5a6))
    job, mn, mx = _random.choice(JOBS)
    gain = _random.randint(mn, mx)
    economy_data[uid]["coins"] += gain
    travailler_cd[uid] = now
    await ctx.send(embed=discord.Embed(title=f"💼 {job}", description=f"{ctx.author.mention} gagne **{gain} pièces** ! 💰\n*Prochain travail dans 4h*", color=0x2ecc71))

# ── .braquage ─────────────────────────────────────────────────
@bot.command(name="braquage", aliases=["rob"])
async def braquage_cmd(ctx, cible: discord.Member = None):
    """Tente un braquage — .braquage @joueur"""
    import time as _t
    if not cible:
        return await ctx.send("❌ Mentionne quelqu'un ! Ex: `.braquage @joueur`")
    if cible == ctx.author:
        return await ctx.send("❌ Tu peux pas te braquer toi-même 😂")
    uid = str(ctx.author.id)
    uid_c = str(cible.id)
    now = _t.time()
    if now - braquage_cd.get(uid, 0) < 21600:
        reste = int((21600 - (now - braquage_cd[uid])) // 60)
        return await ctx.send(f"⏳ Attends encore **{reste} min** avant de braquer !")
    cible_coins = economy_data[uid_c]["coins"]
    if cible_coins < 200:
        return await ctx.send(f"💸 **{cible.display_name}** est trop pauvre (moins de 200 pièces) !")
    braquage_cd[uid] = now
    if _random.random() < 0.30:
        vol = _random.randint(int(cible_coins * 0.20), int(cible_coins * 0.40))
        economy_data[uid]["coins"] += vol
        economy_data[uid_c]["coins"] -= vol
        await ctx.send(embed=discord.Embed(title="🦹 Braquage réussi !", description=f"{ctx.author.mention} a braqué **{vol} pièces** à {cible.mention} ! 💰", color=0x2ecc71))
        try:
            await cible.send(f"🚨 **{ctx.author.display_name}** t'a braqué **{vol} pièces** !")
        except:
            pass
    else:
        amende = min(_random.randint(100, 300), economy_data[uid]["coins"])
        economy_data[uid]["coins"] -= amende
        economy_data[uid_c]["coins"] += amende
        await ctx.send(embed=discord.Embed(title="🚔 Braquage raté !", description=f"{ctx.author.mention} s'est fait attraper ! Amende : **{amende} pièces** 😂", color=0xe74c3c))

# ── .investir ─────────────────────────────────────────────────
@bot.command(name="investir", aliases=["invest"])
async def investir_cmd(ctx, *, args: str = None):
    """Investis sur un animé récent — .investir <animé> <montant>"""
    import time as _t
    uid = str(ctx.author.id)
    if not args:
        liste = "\n".join([f"• `{a}`" for a in ANIMES_INVESTISSEMENT])
        return await ctx.send(embed=discord.Embed(title="📈 Animés disponibles", description=f"**Usage :** `.investir One Piece 500`\n\n{liste}", color=0x3498db))
    parts = args.rsplit(" ", 1)
    if len(parts) < 2 or not parts[1].isdigit():
        return await ctx.send("❌ Usage : `.investir <animé> <montant>`\nEx: `.investir One Piece 500`")
    serie, montant = parts[0].strip(), int(parts[1])
    match = next((a for a in ANIMES_INVESTISSEMENT if serie.lower() in a.lower()), None)
    if not match:
        return await ctx.send(f"❌ **{serie}** pas dans la liste ! Tape `.investir` pour voir les animés.")
    if economy_data[uid]["coins"] < montant:
        return await ctx.send(f"❌ Pas assez de pièces ! Solde : **{economy_data[uid]['coins']}**")
    if montant < 100 or montant > 5000:
        return await ctx.send("❌ Investissement : min **100p**, max **5000p** !")
    economy_data[uid]["coins"] -= montant
    if uid not in investissements:
        investissements[uid] = {}
    investissements[uid][match] = {"montant": montant, "timestamp": _t.time()}
    await ctx.send(embed=discord.Embed(title="📈 Investissement placé !", description=f"{ctx.author.mention} investit **{montant} pièces** sur **{match}** !\n*Si ça trend dans les 48h → jusqu'à **x3** le retour !*", color=0x3498db))

@bot.command(name="retourinvest", aliases=["rinvest"])
async def retourinvest_cmd(ctx):
    """Récupère le retour — .retourinvest"""
    import time as _t
    uid = str(ctx.author.id)
    invests = investissements.get(uid, {})
    if not invests:
        return await ctx.send("❌ Aucun investissement actif ! Utilise `.investir` pour commencer.")
    now, total, resultats, to_remove = _t.time(), 0, [], []
    for serie, data in invests.items():
        if now - data["timestamp"] < 3600:
            resultats.append(f"⏳ **{serie}** — résultats dans {int((3600-(now-data['timestamp']))//60)} min")
            continue
        if _random.random() < 0.40:
            mult = round(_random.uniform(1.5, 3.0), 1)
            retour = int(data["montant"] * mult)
            total += retour
            resultats.append(f"📈 **{serie}** — TREND ! x{mult} → **+{retour} pièces** 🔥")
        else:
            resultats.append(f"📉 **{serie}** — Pas de trend... **-{data['montant']} pièces** 💸")
        to_remove.append(serie)
    for s in to_remove:
        del investissements[uid][s]
    if total > 0:
        economy_data[uid]["coins"] += total
    embed = discord.Embed(title="📊 Résultats d'investissement", description="\n".join(resultats) if resultats else "Aucun résultat.", color=0x2ecc71 if total > 0 else 0xe74c3c)
    if total > 0:
        embed.set_footer(text=f"💰 Total gagné : +{total} pièces !")
    await ctx.send(embed=embed)

# ── .missions ─────────────────────────────────────────────────
@bot.command(name="missions", aliases=["mission"])
async def missions_cmd(ctx):
    """Voir tes missions journalières — .missions"""
    import time as _t
    uid = str(ctx.author.id)
    today = int(_t.time() // 86400)
    if uid not in missions_data or missions_data[uid].get("jour") != today:
        missions_data[uid] = {
            "jour": today,
            "missions": [
                {"id": "quiz5",    "desc": "Réponds correctement à 5 quiz",  "objectif": 5,  "progres": 0, "recompense": 200, "done": False},
                {"id": "duel3",    "desc": "Gagne 3 duels en arène",         "objectif": 3,  "progres": 0, "recompense": 300, "done": False},
                {"id": "roll10",   "desc": "Tire 10 cartes gacha",           "objectif": 10, "progres": 0, "recompense": 150, "done": False},
                {"id": "claim1",   "desc": "Claim 1 carte gacha",            "objectif": 1,  "progres": 0, "recompense": 250, "done": False},
                {"id": "travail1", "desc": "Travaille 1 fois",               "objectif": 1,  "progres": 0, "recompense": 100, "done": False},
            ]
        }
    missions = missions_data[uid]["missions"]
    total_dispo = sum(m["recompense"] for m in missions if not m["done"])
    desc = ""
    for m in missions:
        strike = "~~" if m["done"] else ""
        status = "✅" if m["done"] else f"**{m['progres']}/{m['objectif']}**"
        desc += f"{strike}{m['desc']} — **{m['recompense']}p** {status}{strike}\n"
    embed = discord.Embed(title="📋 Missions Journalières", description=desc, color=0xf1c40f)
    embed.set_footer(text=f"💰 Récompenses restantes : {total_dispo} pièces • Reset dans {24 - int((_t.time() % 86400) // 3600)}h")
    await ctx.send(embed=embed)

def update_mission(uid, mission_id, amount=1):
    import time as _t
    today = int(_t.time() // 86400)
    if uid not in missions_data or missions_data[uid].get("jour") != today:
        return
    for m in missions_data[uid]["missions"]:
        if m["id"] == mission_id and not m["done"]:
            m["progres"] = min(m["progres"] + amount, m["objectif"])
            if m["progres"] >= m["objectif"]:
                m["done"] = True
                economy_data[uid]["coins"] += m["recompense"]
            break

# ── .liga ─────────────────────────────────────────────────────
@bot.command(name="liga", aliases=["elo", "classementliga"])
async def liga_cmd(ctx):
    """Classement Liga Elo mensuel — .liga"""
    import datetime as _dt
    saison = _dt.datetime.now().strftime("%Y-%m")
    if not liga_data:
        return await ctx.send(embed=discord.Embed(description="🏆 Aucune partie de Liga jouée !\nJoue en `.arene` pour gagner des points Elo !", color=0xf1c40f))
    scores = [(uid, d) for uid, d in liga_data.items() if d.get("saison") == saison]
    scores.sort(key=lambda x: x[1].get("elo", 1000), reverse=True)
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    desc = ""
    for i, (uid, d) in enumerate(scores[:10]):
        member = ctx.guild.get_member(int(uid))
        name = member.display_name if member else f"<@{uid}>"
        desc += f"{medals[i]} **{name}** — **{d.get('elo', 1000)} Elo** ({d.get('wins', 0)}V/{d.get('losses', 0)}D)\n"
    embed = discord.Embed(title=f"🏆 Liga — Saison {saison}", description=desc or "Aucun joueur cette saison !", color=0xf1c40f)
    embed.set_footer(text="Joue en .arene pour gagner des points Elo ! Reset en fin de mois 🔄")
    await ctx.send(embed=embed)

def update_liga(uid, victoire: bool):
    import datetime as _dt, random as _r
    saison = _dt.datetime.now().strftime("%Y-%m")
    if uid not in liga_data or liga_data[uid].get("saison") != saison:
        liga_data[uid] = {"elo": 1000, "wins": 0, "losses": 0, "saison": saison}
    if victoire:
        liga_data[uid]["elo"] += _r.randint(20, 35)
        liga_data[uid]["wins"] += 1
    else:
        liga_data[uid]["elo"] = max(100, liga_data[uid]["elo"] - _r.randint(15, 25))
        liga_data[uid]["losses"] += 1

# ── .faction ──────────────────────────────────────────────────
@bot.command(name="faction", aliases=["factions"])
async def faction_cmd(ctx, action: str = None, *, nom: str = None):
    """Gère les factions — .faction | .faction rejoindre <id> | .faction leave | .faction info | .faction classement"""
    uid = str(ctx.author.id)

    FACTION_ROLES_MAP = {
        "akatsuki":      ("🔴 Akatsuki",                  0xc0392b),
        "surveycorps":   ("💙 Bataillon d\'Exploration", 0x2980b9),
        "strawhat":      ("🏴 Chapeau de Paille",         0xe67e22),
        "phantomtroupe": ("🕷️ Phantom Troupe",            0x2c2f33),
        "gotei13":       ("🌸 Gotei 13",                  0x9b59b6),
        "ua":            ("💚 Lycée U.A.",                0x27ae60),
    }

    async def get_faction_role(guild, fid):
        if fid not in FACTION_ROLES_MAP:
            return None
        rname, rcolor = FACTION_ROLES_MAP[fid]
        role = discord.utils.get(guild.roles, name=rname)
        if not role:
            try:
                role = await guild.create_role(name=rname, color=discord.Color(rcolor), mentionable=True)
            except:
                return None
        return role

    async def retirer_roles_faction(member, guild):
        for fid, (rname, _) in FACTION_ROLES_MAP.items():
            r = discord.utils.get(guild.roles, name=rname)
            if r and r in member.roles:
                try: await member.remove_roles(r)
                except: pass

    if not action or action.lower() in ["liste", "list"]:
        desc = ""
        for fid, fd in FACTIONS.items():
            nb = sum(1 for u, f in faction_data.items() if f == fid)
            emoji = fd.get("emoji", "")
            nom_f = fd.get("nom", fid)
            serie = fd.get("serie", "")
            desc += f"{emoji} **{nom_f}** (`{fid}`) — {nb} membre(s) — *{serie}*\n"
        embed = discord.Embed(
            title="⚔️ Factions du QG",
            description=desc + "\n`.faction rejoindre <id>` pour rejoindre !",
            color=0x9b59b6
        )
        return await ctx.send(embed=embed)

    if action.lower() in ["rejoindre", "join"]:
        if not nom:
            return await ctx.send("❌ Ex: `.faction rejoindre akatsuki`")
        fid = nom.lower().strip().replace(" ", "")
        if fid not in FACTIONS:
            return await ctx.send(f"❌ Faction `{fid}` introuvable ! Tape `.faction` pour la liste.")
        old_fid = faction_data.get(uid)
        if old_fid == fid:
            return await ctx.send("❌ Tu es déjà dans cette faction !")
        await retirer_roles_faction(ctx.author, ctx.guild)
        faction_data[uid] = fid
        faction_rep[uid] = faction_rep.get(uid, 0)
        fd = FACTIONS[fid]
        role = await get_faction_role(ctx.guild, fid)
        if role:
            try: await ctx.author.add_roles(role)
            except: pass
        role_txt = f" Rôle {role.mention} attribué !" if role else ""
        embed = discord.Embed(
            title=f"{fd.get('emoji','')} Faction rejointe !",
            description=f"{ctx.author.mention} a rejoint **{fd.get('nom',fid)}** !{role_txt}",
            color=0x2ecc71
        )
        return await ctx.send(embed=embed)

    if action.lower() in ["leave", "quitter", "partir"]:
        fid = faction_data.get(uid)
        if not fid:
            return await ctx.send("❌ T\'as pas de faction à quitter !")
        fd = FACTIONS.get(fid, {})
        await retirer_roles_faction(ctx.author, ctx.guild)
        del faction_data[uid]
        return await ctx.send(embed=discord.Embed(
            description=f"👋 {ctx.author.mention} a quitté **{fd.get('nom', fid)}**. Rôle retiré.",
            color=0xe74c3c
        ))

    if action.lower() in ["info", "moi"]:
        fid = faction_data.get(uid)
        if not fid:
            return await ctx.send("❌ T\'as pas de faction ! `.faction rejoindre <id>`")
        fd = FACTIONS[fid]
        rep = faction_rep.get(uid, 0)
        role = await get_faction_role(ctx.guild, fid)
        role_txt = f"\n**Rôle :** {role.mention}" if role else ""
        embed = discord.Embed(
            title=f"{fd.get('emoji','')} Ta Faction",
            description=f"**Faction :** {fd.get('nom',fid)}\n**Réputation :** {rep} pts\n**Série :** {fd.get('serie','')}{role_txt}",
            color=0x9b59b6
        )
        return await ctx.send(embed=embed)

    if action.lower() in ["classement", "top"]:
        scores = {}
        for u, fid in faction_data.items():
            scores[fid] = scores.get(fid, 0) + faction_rep.get(u, 0)
        if not scores:
            return await ctx.send("❌ Aucune réputation de faction pour l\'instant !")
        sorted_f = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        desc = ""
        for i, (fid, rep) in enumerate(sorted_f[:5]):
            fd = FACTIONS.get(fid, {})
            desc += f"{medals[i]} {fd.get('emoji','')} **{fd.get('nom',fid)}** — **{rep} pts**\n"
        return await ctx.send(embed=discord.Embed(title="⚔️ Classement des Factions", description=desc, color=0x9b59b6))


# ── .attaquerboss ─────────────────────────────────────────────
@bot.command(name="attaquerboss", aliases=["ab", "attackboss"])
async def attaquerboss_cmd(ctx):
    """Attaque le boss envahisseur — .attaquerboss"""
    import time as _t
    gid = ctx.guild.id
    if gid not in invasion_active or not invasion_active[gid].get("actif"):
        return await ctx.send("❌ Aucune invasion en cours !", delete_after=5)
    uid = str(ctx.author.id)
    boss = invasion_active[gid]
    now = _t.time()
    last = boss["attaquants"].get(uid, {}).get("last", 0)
    if now - last < 30:
        return await ctx.send(f"⏳ Attends encore **{int(30-(now-last))}s** !", delete_after=5)
    top_cards = [k for k, v in claimed_cards.items() if v == uid]
    atk_bonus = sum(ANIME_CARDS_DB.get(k, {}).get("attaque", 50) for k in top_cards[:3])
    degats = random.randint(100, 300) + atk_bonus // 10
    if uid not in boss["attaquants"]:
        boss["attaquants"][uid] = {"total": 0, "last": 0}
    boss["attaquants"][uid]["total"] += degats
    boss["attaquants"][uid]["last"] = now
    boss["pv"] = max(0, boss["pv"] - degats)
    pct = boss["pv"] / boss["max_pv"]
    barre = "🟥" * int(pct * 10) + "⬛" * (10 - int(pct * 10))
    if boss["pv"] <= 0:
        boss["actif"] = False
        recompense = random.randint(500, 1500)
        economy_data[uid]["coins"] += recompense
        faction_rep[uid] = faction_rep.get(uid, 0) + 50
        for att_uid in boss["attaquants"]:
            if att_uid != uid:
                economy_data[att_uid]["coins"] += random.randint(50, 200)
                faction_rep[att_uid] = faction_rep.get(att_uid, 0) + 10
        embed = discord.Embed(title=f"💀 {boss['emoji']} {boss['nom']} vaincu !", description=f"**{ctx.author.mention}** a porté le coup fatal !\n🏆 **+{recompense} pièces** + **+50 rep faction** !", color=0x2ecc71)
        await ctx.send(embed=embed)
        del invasion_active[gid]
    else:
        await ctx.send(embed=discord.Embed(title=f"⚔️ {boss['emoji']} {boss['nom']}", description=f"{ctx.author.mention} inflige **{degats} dégâts** !\n{barre} **{boss['pv']:,}/{boss['max_pv']:,} PV**", color=0xe67e22))

# ── .marcheacheter ────────────────────────────────────────────
@bot.command(name="marcheacheter", aliases=["mnbuy"])
async def marcheacheter_cmd(ctx, perso: str = None):
    """Acheter au marché noir — .marcheacheter <perso>"""
    import time as _t
    if not perso:
        if not marche_noir_actif:
            return await ctx.send("❌ Le marché noir est fermé !")
        desc = ""
        for k, data in marche_noir_actif.items():
            if data["expires"] > _t.time():
                c = ANIME_CARDS_DB.get(k, {})
                r = RARETE_EMOJI.get(c.get("rarete", ""), "🔵")
                desc += f"{r} **{c.get('nom', k)}** — **{data['prix']:,} pièces** → `.marcheacheter {k}`\n"
        return await ctx.send(embed=discord.Embed(title="🕶️ Marché Noir", description=desc or "Vide !", color=0x2c3e50))
    uid = str(ctx.author.id)
    key = perso.lower().strip()
    if key not in marche_noir_actif:
        return await ctx.send("❌ Cette carte n'est pas au marché noir !")
    data = marche_noir_actif[key]
    if data["expires"] < _t.time():
        del marche_noir_actif[key]
        return await ctx.send("❌ Cette offre a expiré !")
    if key in claimed_cards:
        return await ctx.send("❌ Cette carte a déjà été achetée !")
    if economy_data[uid]["coins"] < data["prix"]:
        return await ctx.send(f"❌ Il te manque **{data['prix'] - economy_data[uid]['coins']} pièces** !")
    economy_data[uid]["coins"] -= data["prix"]
    claimed_cards[key] = uid
    gacha_collections[uid][key] = {"fusion": 0}
    del marche_noir_actif[key]
    c = ANIME_CARDS_DB[key]
    r = RARETE_EMOJI.get(c["rarete"], "🔵")
    embed = discord.Embed(title="🕶️ Achat au Marché Noir !", description=f"{ctx.author.mention} a acheté **{c['nom']}** {r} pour **{data['prix']:,} pièces** !", color=0x2c3e50)
    if c.get("image"):
        embed.set_thumbnail(url=c["image"])
    await ctx.send(embed=embed)

# ── Events automatiques ───────────────────────────────────────

# ── .cartefav ─────────────────────────────────────────────────
cartes_favorites = {}   # {uid: [key1, key2, key3]}
trade_history = []      # [{from, to, card1, card2, timestamp}]

@bot.command(name="cartefav", aliases=["favcard","favorite"])
async def cartefav_cmd(ctx, action: str = None, *, perso: str = None):
    """Gère tes cartes favorites — .cartefav add/remove/voir <perso>"""
    uid = str(ctx.author.id)
    if not action or action.lower() in ["voir","list","show"]:
        favs = cartes_favorites.get(uid, [])
        if not favs:
            return await ctx.send("⭐ Pas encore de cartes favorites ! `.cartefav add <perso>`")
        embed = discord.Embed(title=f"⭐ Cartes Favorites de {ctx.author.display_name}", color=0xf1c40f)
        for i, key in enumerate(favs, 1):
            if key in ANIME_CARDS_DB:
                c = ANIME_CARDS_DB[key]
                r = RARETE_EMOJI.get(c["rarete"], "🔵")
                embed.add_field(name=f"#{i} {c['emoji']} {c['nom']}", value=f"{r} {c['rarete']} • {c['serie']}", inline=True)
        if favs and ANIME_CARDS_DB.get(favs[0], {}).get("image"):
            embed.set_thumbnail(url=ANIME_CARDS_DB[favs[0]]["image"])
        return await ctx.send(embed=embed)
    if action.lower() == "add":
        if not perso:
            return await ctx.send("❌ Ex: `.cartefav add naruto`")
        key = perso.lower().strip().replace(" ", "")
        if key not in ANIME_CARDS_DB:
            matches = [k for k in ANIME_CARDS_DB if perso.lower() in ANIME_CARDS_DB[k]["nom"].lower()]
            if not matches:
                return await ctx.send(f"❌ Personnage `{perso}` introuvable !")
            key = matches[0]
        if claimed_cards.get(key) != uid:
            return await ctx.send(f"❌ Tu ne possèdes pas **{ANIME_CARDS_DB[key]['nom']}** !")
        if uid not in cartes_favorites:
            cartes_favorites[uid] = []
        if key in cartes_favorites[uid]:
            return await ctx.send(f"⭐ **{ANIME_CARDS_DB[key]['nom']}** est déjà dans tes favoris !")
        if len(cartes_favorites[uid]) >= 3:
            return await ctx.send("❌ Maximum **3 cartes favorites** ! Retire-en une avec `.cartefav remove <perso>`")
        cartes_favorites[uid].append(key)
        await ctx.send(f"⭐ **{ANIME_CARDS_DB[key]['nom']}** ajouté à tes favoris !")
    elif action.lower() == "remove":
        if not perso:
            return await ctx.send("❌ Ex: `.cartefav remove naruto`")
        key = perso.lower().strip().replace(" ", "")
        if key not in ANIME_CARDS_DB:
            matches = [k for k in ANIME_CARDS_DB if perso.lower() in ANIME_CARDS_DB[k]["nom"].lower()]
            if not matches:
                return await ctx.send(f"❌ Personnage `{perso}` introuvable !")
            key = matches[0]
        favs = cartes_favorites.get(uid, [])
        if key not in favs:
            return await ctx.send(f"❌ **{ANIME_CARDS_DB[key]['nom']}** n'est pas dans tes favoris !")
        favs.remove(key)
        await ctx.send(f"✅ **{ANIME_CARDS_DB[key]['nom']}** retiré de tes favoris !")

# ── .tradeshistory ────────────────────────────────────────────
@bot.command(name="tradeshistory", aliases=["trades","historiquetrades"])
async def tradeshistory_cmd(ctx):
    """Voir les derniers échanges du serveur — .tradeshistory"""
    if not trade_history:
        return await ctx.send("❌ Aucun échange enregistré pour l'instant !")
    import datetime as _dt
    desc = ""
    for t in trade_history[-10:][::-1]:
        ts = _dt.datetime.fromtimestamp(t["timestamp"]).strftime("%d/%m %H:%M")
        c1 = ANIME_CARDS_DB.get(t["card1"], {}).get("nom", t["card1"])
        c2 = ANIME_CARDS_DB.get(t["card2"], {}).get("nom", "?")
        desc += f"**{t['from']}** ↔️ **{t['to']}** — {c1} ↔️ {c2} *({ts})*\n"
    embed = discord.Embed(title="🔄 Historique des Échanges", description=desc, color=0x9b59b6)
    await ctx.send(embed=embed)

# ── .gachastats ───────────────────────────────────────────────
@bot.command(name="gachastats", aliases=["gcstats","collectionstats"])
async def gachastats_cmd(ctx):
    """Classement des collections — .gachastats"""
    if not gacha_collections:
        return await ctx.send("❌ Aucune collection pour l'instant !")
    rarete_pts = {"Mythique": 100, "Légendaire": 50, "Épique": 20, "Rare": 5, "Commun": 1}
    scores = []
    for uid, coll in gacha_collections.items():
        if not coll:
            continue
        member = ctx.guild.get_member(int(uid))
        if not member:
            continue
        mythiques = sum(1 for k in coll if ANIME_CARDS_DB.get(k, {}).get("rarete") == "Mythique")
        valeur = sum(rarete_pts.get(ANIME_CARDS_DB.get(k, {}).get("rarete", "Commun"), 1) for k in coll)
        scores.append((member.display_name, len(coll), mythiques, valeur))
    scores.sort(key=lambda x: x[3], reverse=True)
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    desc = ""
    for i, (nom, total, myth, val) in enumerate(scores[:10]):
        desc += f"{medals[i]} **{nom}** — {total} cartes • {myth} 🔴 Mythiques • **{val} pts**\n"
    embed = discord.Embed(title="🏆 Classement des Collections", description=desc, color=0xf1c40f)
    await ctx.send(embed=embed)

# ── .invoke ───────────────────────────────────────────────────
@bot.command(name="invoke")
async def invoke_cmd(ctx):
    """Invocation spéciale — garantit Légendaire+ — .invoke (10000 pièces)"""
    import time as _t
    uid = str(ctx.author.id)
    prix = 10000
    if SALON_GACHA_ID and ctx.channel.id != SALON_GACHA_ID:
        salon = ctx.guild.get_channel(SALON_GACHA_ID)
        return await ctx.send(f"🎰 L'invocation c'est dans {salon.mention if salon else 'le salon gacha'} !", delete_after=5)
    if economy_data[uid]["coins"] < prix:
        return await ctx.send(embed=discord.Embed(
            description=f"❌ L'invocation coûte **{prix} pièces** ! Tu as seulement **{economy_data[uid]['coins']}** pièces.",
            color=0xe74c3c))
    available = [k for k in ANIME_CARDS_DB if k not in claimed_cards and ANIME_CARDS_DB[k]["rarete"] in ("Légendaire","Mythique")]
    if not available:
        return await ctx.send("❌ Plus de cartes Légendaire+ disponibles !")
    economy_data[uid]["coins"] -= prix
    key = random.choice(available)
    c = ANIME_CARDS_DB[key]
    r_emoji = RARETE_EMOJI.get(c["rarete"], "🟠")
    couleur = RARETE_COULEURS.get(c["rarete"], 0xe67e22)
    embed = discord.Embed(
        title=f"✨ INVOCATION SPÉCIALE — {c['emoji']} {c['nom']}",
        description=f"*{c['serie']}* {r_emoji} **{c['rarete']}**",
        color=couleur)
    if c.get("image"):
        embed.set_image(url=c["image"])
    embed.add_field(name="📊 Stats", value=f"❤️ **{c['pv']}** PV | ⚔️ **{c['attaque']}** ATK | 🛡️ **{c['defense']}** DEF", inline=False)
    embed.set_footer(text="✨ Garantie Légendaire+ • Réagis ❤️ pour claim dans 30s !")
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("❤️")
    def check_invoke(r, u):
        return str(r.emoji) == "❤️" and r.message.id == msg.id and not u.bot
    try:
        reaction, claimer = await bot.wait_for("reaction_add", timeout=30.0, check=check_invoke)
        if key in claimed_cards:
            return await ctx.send("⚡ Trop tard, quelqu'un a déjà claim !")
        claimed_cards[key] = str(claimer.id)
        gacha_collections[str(claimer.id)][key] = {"fusion": 0}
        r2 = RARETE_EMOJI.get(c["rarete"], "🟠")
        await ctx.send(f"✨ **{claimer.display_name}** a claim **{c['nom']}** {r2} via Invocation Spéciale !")
    except asyncio.TimeoutError:
        await ctx.send(f"⏰ Invocation expirée — **{c['nom']}** retourne dans le néant...")

# ── .cardduel ─────────────────────────────────────────────────
@bot.command(name="cardduel", aliases=["duelcarte","cduels"])
async def cardduel_cmd(ctx, adversaire: discord.Member = None, *, ma_carte: str = None):
    """Duel de cartes — mise une carte, le gagnant prend les deux — .cardduel @joueur <carte>"""
    if SALON_GACHA_ID and ctx.channel.id != SALON_GACHA_ID:
        salon = ctx.guild.get_channel(SALON_GACHA_ID)
        return await ctx.send(f"🎰 Le duel de cartes c'est dans {salon.mention if salon else 'le salon gacha'} !", delete_after=5)
    if not adversaire or not ma_carte:
        return await ctx.send("❌ Usage : `.cardduel @joueur <ta carte>`\nEx: `.cardduel @Ryaax naruto`")
    if adversaire == ctx.author:
        return await ctx.send("❌ Tu peux pas te défier toi-même !")
    if adversaire.bot:
        return await ctx.send("❌ Tu peux pas défier un bot !")
    uid = str(ctx.author.id)
    uid_adv = str(adversaire.id)
    key = ma_carte.lower().strip().replace(" ", "")
    if key not in ANIME_CARDS_DB:
        matches = [k for k in ANIME_CARDS_DB if ma_carte.lower() in ANIME_CARDS_DB[k]["nom"].lower()]
        if not matches:
            return await ctx.send(f"❌ Carte `{ma_carte}` introuvable !")
        key = matches[0]
    c = ANIME_CARDS_DB[key]
    if claimed_cards.get(key) != uid:
        return await ctx.send(f"❌ Tu ne possèdes pas **{c['nom']}** !")
    r_emoji = RARETE_EMOJI.get(c["rarete"], "🔵")
    embed = discord.Embed(
        title="⚔️ Défi de Carte !",
        description=f"{ctx.author.mention} défie {adversaire.mention} !\n\n🎴 Carte mise en jeu : **{c['nom']} ** {r_emoji}\n\n{adversaire.mention} — réagis ✅ pour accepter ou ❌ pour refuser !",
        color=RARETE_COULEURS.get(c["rarete"], 0x9b59b6))
    if c.get("image"):
        embed.set_thumbnail(url=c["image"])
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    def check(reaction, user):
        return user == adversaire and reaction.message.id == msg.id and str(reaction.emoji) in ["✅","❌"]
    try:
        reaction, user = await bot.wait_for("reaction_add", timeout=60.0, check=check)
        if str(reaction.emoji) == "❌":
            return await msg.edit(embed=discord.Embed(description=f"❌ **{adversaire.display_name}** a refusé le défi.", color=0xe74c3c))
        # Adversaire accepte — il doit choisir sa carte
        await ctx.send(f"✅ {adversaire.mention} — quelle carte tu mises ? Réponds avec le nom de ta carte ici !")
        def check_carte(m):
            return m.author == adversaire and m.channel == ctx.channel
        try:
            rep = await bot.wait_for("message", timeout=30.0, check=check_carte)
            key2 = rep.content.lower().strip().replace(" ", "")
            if key2 not in ANIME_CARDS_DB:
                matches2 = [k for k in ANIME_CARDS_DB if rep.content.lower() in ANIME_CARDS_DB[k]["nom"].lower()]
                if not matches2:
                    return await ctx.send(f"❌ Carte `{rep.content}` introuvable !")
                key2 = matches2[0]
            c2 = ANIME_CARDS_DB[key2]
            if claimed_cards.get(key2) != uid_adv:
                return await ctx.send(f"❌ **{adversaire.display_name}** ne possède pas **{c2['nom']}** !")
            # Combat — basé sur ATK + random
            score1 = c["attaque"] + c["pv"] // 10 + random.randint(1, 50)
            score2 = c2["attaque"] + c2["pv"] // 10 + random.randint(1, 50)
            if score1 > score2:
                winner, loser_uid, win_key, lose_key, win_c, lose_c = ctx.author, uid_adv, key2, key, c2, c
            else:
                winner, loser_uid, win_key, lose_key, win_c, lose_c = adversaire, uid, key, key2, c, c2
            winner_uid = str(winner.id)
            # Transfert
            claimed_cards[win_key] = winner_uid
            claimed_cards[lose_key] = winner_uid
            gacha_collections[winner_uid][win_key] = {"fusion": 0}
            gacha_collections[winner_uid][lose_key] = {"fusion": 0}
            if win_key in gacha_collections.get(loser_uid, {}):
                del gacha_collections[loser_uid][win_key]
            r1 = RARETE_EMOJI.get(win_c["rarete"], "🔵")
            r2 = RARETE_EMOJI.get(lose_c["rarete"], "🔵")
            embed_result = discord.Embed(
                title=f"🏆 {winner.display_name} remporte le duel !",
                description=f"**{win_c['nom']}** {r1} vs **{lose_c['nom']}** {r2}\n\n🎴 **{winner.mention}** récupère les deux cartes !",
                color=0x2ecc71)
            await ctx.send(embed=embed_result)
        except asyncio.TimeoutError:
            await ctx.send(f"⏰ **{adversaire.display_name}** n'a pas choisi de carte à temps !")
    except asyncio.TimeoutError:
        await msg.edit(embed=discord.Embed(description="⏰ Défi expiré — pas de réponse.", color=0x95a5a6))
        try:
            await msg.clear_reactions()
        except:
            pass

# ============================================================
#  🎪 SYSTÈME D'EVENTS COMPLET
# ============================================================

import random as _r
import asyncio as _asyncio

# ── Variables globales events ─────────────────────────────────
event_en_cours = False          # Un seul event à la fois
jackpot_cagnotte = 0            # Cagnotte communautaire
jackpot_actif = False           # Jackpot en cours
jackpot_derniere_explosion = 0  # Timestamp dernière explosion
jackpot_cooldowns = {}          # {uid: last_timestamp}
jackpot_contributions = {}      # {uid: total_contribue}
serie_benie = None              # Série bénie cette semaine
serie_benie_fin = 0             # Timestamp fin bénédiction
casino_boost_actif = False      # Nuit casino x2
heure_maudite_active = False    # Heure maudite active
double_xp_event_actif = False   # Double XP event actif
boss_revanche = None            # Boss revanche si pas vaincu
imposteur_actif = {}            # {guild_id: card_key}

MESSAGES_RAGEBAIT = [
    "😂 LOOOOOL t'as claim une carte à 9999 ATK et... c'est du vent ! La carte Imposteur disparaît dans tes mains ! T'as été TROP gourmand frérot 💀",
    "🤡 GG t'as claim la carte la plus puissante du serveur... sauf que c'était un fake ! Retourne farm tes pièces 😭",
    "💀 AHAHAHAH t'y as cru hein ! La carte Imposteur te nargue depuis le début. Aucune carte pour toi aujourd'hui mon gars 😈",
    "🎭 Tu pensais vraiment avoir une carte à 9999 ATK ? En 2024 ? Mon gars réveille-toi, c'était L'IMPOSTEUR 😂 Skill issue.",
    "☠️ La carte t'a regardé droit dans les yeux et a dit NON. Imposteur du Gacha : 1 — Toi : 0. Come back quand t'es prêt 💅",
]

# ── Helper : obtenir salon event ──────────────────────────────
def get_event_channel(guild, ctx=None):
    # Toujours le salon event configuré en priorité absolue
    if SALON_EVENT_ID:
        ch = guild.get_channel(SALON_EVENT_ID)
        if ch: return ch
    # Si pas de salon event → system channel
    # ctx.channel n'est JAMAIS utilisé pour les annonces d'events
    return guild.system_channel

def get_gacha_role(guild):
    return discord.utils.get(guild.roles, name="🎴┃Gacha")

# ── .jackpot ──────────────────────────────────────────────────
@bot.command(name="jackpot", aliases=["cagnotte","pot"])
async def jackpot_cmd(ctx):
    """Voir l'avancée de la cagnotte — .jackpot"""
    import time as _t
    objectif = 1500
    pct = min(jackpot_cagnotte / objectif * 100, 100)
    filled = int(pct / 10)
    barre = "🟡" * filled + "⬛" * (10 - filled)
    
    top_contrib = sorted(jackpot_contributions.items(), key=lambda x: x[1], reverse=True)[:3]
    contrib_str = ""
    for uid, pts in top_contrib:
        member = ctx.guild.get_member(int(uid))
        name = member.display_name if member else f"<@{uid}>"
        contrib_str += f"• **{name}** — {pts} pièces contribuées\n"
    
    statut = "🟢 **Jackpot actif !** Chaque message = +1 pièce" if jackpot_actif else "🔴 Jackpot inactif pour l'instant"
    
    embed = discord.Embed(
        title="💸 Jackpot Communautaire",
        description=f"{statut}\n\n{barre} **{jackpot_cagnotte}/{objectif} pièces**\n*{pct:.0f}% rempli*",
        color=0xf1c40f
    )
    if contrib_str:
        embed.add_field(name="🏆 Top Contributeurs", value=contrib_str, inline=False)
    embed.add_field(name="💡 Comment contribuer ?", value="Envoie des messages dans le serveur quand le jackpot est actif !\n*1 pièce/message (cooldown 1 min invisible)*", inline=False)
    
    if jackpot_derniere_explosion > 0:
        import datetime as _dt
        last = _dt.datetime.fromtimestamp(jackpot_derniere_explosion).strftime("%d/%m/%Y")
        embed.set_footer(text=f"Dernière explosion : {last} • Max 1x/mois")
    
    await ctx.send(embed=embed)

# ── Contribution jackpot dans on_message ─────────────────────
async def process_jackpot(message):
    global jackpot_cagnotte, jackpot_actif
    import time as _t
    if not jackpot_actif or message.author.bot:
        return
    uid = str(message.author.id)
    now = _t.time()
    # Cooldown 1 min invisible
    if now - jackpot_cooldowns.get(uid, 0) < 60:
        return
    # Plafond perso 100 pièces
    if jackpot_contributions.get(uid, 0) >= 100:
        return
    jackpot_cooldowns[uid] = now
    jackpot_contributions[uid] = jackpot_contributions.get(uid, 0) + 1
    jackpot_cagnotte += 1
    # Explosion !
    if jackpot_cagnotte >= 5000:
        jackpot_actif = False
        await declencher_jackpot_explosion(message.guild, message.channel)

async def declencher_jackpot_explosion(guild, channel):
    global jackpot_cagnotte, jackpot_derniere_explosion, jackpot_contributions
    import time as _t
    jackpot_derniere_explosion = _t.time()
    # Trouver les 5 membres les plus pauvres ayant envoyé 3+ messages aujourd'hui
    membres_actifs = [(uid, economy_data[uid]["coins"]) 
                      for uid in jackpot_contributions 
                      if jackpot_contributions[uid] >= 3]
    membres_actifs.sort(key=lambda x: x[1])  # Plus pauvres en premier
    gagnants = membres_actifs[:5]
    part = jackpot_cagnotte // max(len(gagnants), 1)
    desc = f"💸 La cagnotte a atteint **{jackpot_cagnotte} pièces** !\n\n**Redistribution aux plus pauvres actifs :**\n"
    for uid, solde in gagnants:
        economy_data[uid]["coins"] += part
        member = guild.get_member(int(uid))
        name = member.display_name if member else f"<@{uid}>"
        desc += f"• **{name}** — +**{part} pièces** (solde était {solde}p)\n"
    embed = discord.Embed(title="💥 JACKPOT EXPLOSÉ !", description=desc, color=0xf1c40f)
    event_ch = get_event_channel(guild)
    await (event_ch or channel).send(embed=embed)
    # Reset
    jackpot_cagnotte = 0
    jackpot_contributions.clear()

# ── TASKS D'EVENTS ────────────────────────────────────────────

# Invasion samedi 23h (fixe)
@tasks.loop(hours=24)
async def invasion_samedi():
    import datetime as _dt
    now = _dt.datetime.now()
    if now.weekday() != 5 or now.hour != 23:  # 5 = samedi
        return
    for guild in bot.guilds:
        try:
            channel = get_event_channel(guild, ctx)
            if not channel:
                continue
            boss = _r.choice(BOSS_INVASIONS).copy()
            invasion_active[guild.id] = {**boss, "max_pv": boss["pv"], "attaquants": {}, "actif": True, "debut": __import__('time').time()}
            embed = discord.Embed(
                title=f"⚠️ INVASION DU SAMEDI ! {boss['emoji']} {boss['nom']} attaque !",
                description=f"**{boss['nom']}** de *{boss['serie']}* envahit le QG !\n\n❤️ **PV :** {boss['pv']:,}\n\nTape `.attaquerboss` pour défendre ! Coup final = récompense spéciale 🏆",
                color=0xe74c3c
            )
            if boss.get("image"):
                embed.set_thumbnail(url=boss["image"])
            await channel.send("@everyone", embed=embed)
            # Vérif revanche après 2h
            await asyncio.sleep(7200)
            if guild.id in invasion_active and invasion_active[guild.id].get("actif"):
                # Boss pas vaincu → revanche demain +20% PV
                pv_boost = int(boss["pv"] * 1.2)
                boss_revanche_data = {**boss, "pv": pv_boost, "max_pv": pv_boost, "attaquants": {}, "actif": False, "revanche": True}
                invasion_active[guild.id]["actif"] = False
                embed_escape = discord.Embed(
                    title=f"😤 {boss['emoji']} {boss['nom']} s'échappe !",
                    description=f"Le boss n'a pas été vaincu...\n⚠️ Il reviendra **demain plus fort** avec **{pv_boost:,} PV** (+20%) ! Préparez-vous !",
                    color=0x95a5a6
                )
                await channel.send(embed=embed_escape)
                # Stocker pour demain
                bot.boss_revanche = boss_revanche_data
        except Exception as e:
            print(f"Invasion samedi error: {e}")

# Classement hebdo dimanche soir
@tasks.loop(hours=24)
async def classement_hebdo():
    import datetime as _dt
    now = _dt.datetime.now()
    if now.weekday() != 6 or now.hour != 20:  # 6 = dimanche, 20h
        return
    for guild in bot.guilds:
        try:
            channel = guild.get_channel(SALON_LEVELUP_ID) if SALON_LEVELUP_ID else get_event_channel(guild)
            if not channel:
                continue
            # Top 3 par messages + temps vocal
            scores = []
            for member in guild.members:
                if member.bot:
                    continue
                uid = str(member.id)
                msgs = message_count.get(uid, 0)
                voc = voice_time.get(uid, 0)
                score = msgs * 2 + voc
                if score > 0:
                    scores.append((member, msgs, voc, score))
            scores.sort(key=lambda x: x[3], reverse=True)
            if not scores:
                continue
            medals = ["🥇", "🥈", "🥉"]
            rewards = [300, 200, 100]
            desc = "**Classement de la semaine sur le QG Kdrama !**\n\n"
            for i, (member, msgs, voc, score) in enumerate(scores[:3]):
                reward = rewards[i]
                economy_data[str(member.id)]["coins"] += reward
                desc += f"{medals[i]} **{member.display_name}** — {msgs} messages • {voc} min vocal • **+{reward} pièces** 🎉\n"
            if len(scores) > 3:
                desc += f"\n*+{len(scores)-3} autres membres actifs cette semaine !*"
            embed = discord.Embed(title="🏆 Classement Hebdomadaire", description=desc, color=0xf1c40f)
            embed.set_footer(text="Les compteurs repartent à zéro la semaine prochaine !")
            await channel.send("@everyone", embed=embed)
            # Reset compteurs hebdo
            message_count.clear()
        except Exception as e:
            print(f"Classement hebdo error: {e}")

# Prophétie lundi matin
@tasks.loop(hours=24)
async def prophetie_hebdo():
    import datetime as _dt, time as _t
    now = _dt.datetime.now()
    if now.weekday() != 0 or now.hour != 9:  # 0 = lundi, 9h
        return
    global serie_benie, serie_benie_fin
    series_dispo = list(set(c["serie"] for c in ANIME_CARDS_DB.values()))
    serie_benie = _r.choice(series_dispo)
    serie_benie_fin = _t.time() + 604800  # 7 jours
    for guild in bot.guilds:
        try:
            channel = get_event_channel(guild, ctx)
            if not channel:
                continue
            role = get_gacha_role(guild)
            mention = role.mention if role else ""
            cartes_benies = [c["nom"] for c in ANIME_CARDS_DB.values() if c["serie"] == serie_benie]
            embed = discord.Embed(
                title="🔮 Prophétie Hebdomadaire",
                description=f"*Les anciens ont parlé...*\n\n✨ Cette semaine, l'animé **{serie_benie}** est **BÉNI** !\n\nToutes ses cartes ont **+10% de stats** en arène pendant **7 jours** !\n\n*Cartes concernées : {', '.join(cartes_benies[:5])}{'...' if len(cartes_benies) > 5 else ''}*",
                color=0x9b59b6
            )
            await channel.send(mention, embed=embed)
        except Exception as e:
            print(f"Prophétie error: {e}")

# Planning hebdo aléatoire
@tasks.loop(hours=24)
async def planning_hebdo():
    import datetime as _dt
    global event_en_cours
    now = _dt.datetime.now()
    hour = now.hour
    weekday = now.weekday()  # 0=lun, 1=mar... 6=dim
    semaine = now.isocalendar()[1]
    today = now.date()

    # ── ROTATION GROS EVENTS WEEKEND (6 events, jamais le même 2 semaines) ──
    ROTATION_WEEKEND = [
        lancer_tournoi,
        lancer_death_note,
        lancer_conquete,
        lancer_encheres,
        lancer_parminous,
        lancer_puzzle_collectif,
    ]
    idx_ven = semaine % len(ROTATION_WEEKEND)
    idx_sam = (semaine + 2) % len(ROTATION_WEEKEND)
    idx_dim = (semaine + 4) % len(ROTATION_WEEKEND)
    # S'assurer que les 3 sont différents
    if idx_sam == idx_ven: idx_sam = (idx_sam + 1) % len(ROTATION_WEEKEND)
    if idx_dim == idx_ven or idx_dim == idx_sam: idx_dim = (idx_dim + 1) % len(ROTATION_WEEKEND)

    event_vendredi = ROTATION_WEEKEND[idx_ven]
    event_samedi   = ROTATION_WEEKEND[idx_sam]
    event_dimanche = ROTATION_WEEKEND[idx_dim]

    # ── EVENTS LÉGERS ALÉATOIRES (jeudi soir + lundi soir) ──
    EVENTS_LEGERS = [
        lancer_proces, lancer_roue_fortune, lancer_fausse_rumeur,
        lancer_oracle_maudit, lancer_clown, lancer_event_pacifiste,
        lancer_pacte, lancer_voleur_minuit, lancer_magicien,
        lancer_reve_collectif, lancer_festival_losers, lancer_mine_or,
        lancer_wanted,
    ]

    # ══════════════════════════════════════════════════════════
    # LUNDI
    # ══════════════════════════════════════════════════════════
    # Lundi 9h → Prophétie Hebdo
    if weekday == 0 and hour == 9:
        await lancer_prophetie_hebdo()
        return

    # Lundi 18h → Coffre
    if weekday == 0 and hour == 18 and not event_en_cours:
        await lancer_coffre_planifie()
        return

    # Lundi 20h → Event léger aléatoire
    if weekday == 0 and hour == 20 and not event_en_cours:
        await _r.choice(EVENTS_LEGERS)()
        return

    # ══════════════════════════════════════════════════════════
    # MARDI
    # ══════════════════════════════════════════════════════════
    # Mardi 20h → Nuit de Chasse OU Marché Noir (jamais ensemble)
    if weekday == 1 and hour == 20 and not event_en_cours:
        if _r.random() < 0.5:
            await lancer_nuit_chasse_event()
        else:
            await lancer_marche_noir_event()
        return

    # ══════════════════════════════════════════════════════════
    # MERCREDI
    # ══════════════════════════════════════════════════════════
    # Mercredi 2h → Heure Maudite
    if weekday == 2 and hour == 2 and not event_en_cours:
        await lancer_heure_maudite()
        return

    # Mercredi 19h → Double XP semaines paires
    if weekday == 2 and hour == 19 and semaine % 2 == 0 and not event_en_cours:
        await lancer_double_xp_event()
        return

    # Mercredi 20h → Coffre
    if weekday == 2 and hour == 20 and not event_en_cours:
        await lancer_coffre_planifie()
        return

    # ══════════════════════════════════════════════════════════
    # JEUDI
    # ══════════════════════════════════════════════════════════
    # Jeudi 20h → Event léger aléatoire
    if weekday == 3 and hour == 20 and not event_en_cours:
        await _r.choice(EVENTS_LEGERS)()
        return

    # Jeudi 21h → Nuit Casino
    if weekday == 3 and hour == 21 and not event_en_cours:
        await lancer_nuit_casino()
        return

    # ══════════════════════════════════════════════════════════
    # VENDREDI
    # ══════════════════════════════════════════════════════════
    # Vendredi 18h → Carte Mystère (33%)
    if weekday == 4 and hour == 18 and not event_en_cours:
        if _r.random() < 0.33:
            await lancer_carte_mystere()
        return

    # Vendredi 20h → GROS EVENT rotation
    if weekday == 4 and hour == 20 and not event_en_cours:
        await event_vendredi()
        return

    # ══════════════════════════════════════════════════════════
    # SAMEDI
    # ══════════════════════════════════════════════════════════
    # Samedi 15h → Imposteur du Gacha
    if weekday == 5 and hour == 15 and not event_en_cours:
        await lancer_imposteur()
        return

    # Samedi 18h → Carte Mystère (33%)
    if weekday == 5 and hour == 18 and not event_en_cours:
        if _r.random() < 0.33:
            await lancer_carte_mystere()
        return

    # Samedi 20h → GROS EVENT rotation
    if weekday == 5 and hour == 20 and not event_en_cours:
        await event_samedi()
        return

    # Samedi 23h → Invasion Boss
    if weekday == 5 and hour == 23 and not event_en_cours:
        await lancer_invasion_boss()
        return

    # ══════════════════════════════════════════════════════════
    # DIMANCHE
    # ══════════════════════════════════════════════════════════
    # Dimanche 16h → Coffre
    if weekday == 6 and hour == 16 and not event_en_cours:
        await lancer_coffre_planifie()
        return

    # Dimanche 17h → GROS EVENT rotation
    if weekday == 6 and hour == 17 and not event_en_cours:
        await event_dimanche()
        return

    # Dimanche 19h → Colis Mystère (40%)
    if weekday == 6 and hour == 19 and not event_en_cours:
        if _r.random() < 0.4:
            await lancer_colis_mystere()
        return

    # Dimanche 20h → Classement Hebdo
    if weekday == 6 and hour == 20:
        await lancer_classement_hebdo()
        return


@tasks.loop(hours=24)
async def events_mensuels():
    import datetime as _dt
    now = _dt.datetime.now()
    if now.day not in (1, 8, 15, 22) and not _est_dernier_vendredi(now):
        return
    hour = now.hour
    if hour != 18:
        return

    if now.day == 1:
        await lancer_jackpot()
    elif now.day == 8:
        await lancer_draft_cartes()
    elif now.day == 15:
        await lancer_guerre_factions()
        await lancer_boss_final()   # Boss Final 1er passage
    elif now.day == 22:
        await lancer_event_surprise()
        await lancer_boss_final()   # Boss Final 2ème passage
    elif _est_dernier_vendredi(now):
        await lancer_vague_legendaires()  # Vague 1x/mois seulement

def _est_dernier_vendredi(dt):
    import datetime as _dt
    if dt.weekday() != 4:  # 4 = vendredi
        return False
    prochain = dt + _dt.timedelta(days=7)
    return prochain.month != dt.month


@tasks.loop(hours=24)
async def heure_maudite_task():
    import datetime as _dt
    now = _dt.datetime.now()
    if now.weekday() != 2 or now.hour != 2:
        return
    await lancer_heure_maudite()

# Imposteur Gacha : samedi 15h (avant invasion)
@tasks.loop(hours=24)
async def imposteur_task():
    import datetime as _dt
    now = _dt.datetime.now()
    if now.weekday() != 5 or now.hour != 15:
        return
    await lancer_imposteur()

# ── Fonctions de lancement ────────────────────────────────────

async def lancer_coffre_planifie(ctx=None):
    global event_en_cours
    import time as _t
    event_en_cours = True
    for guild in bot.guilds:
        try:
            channel = get_event_channel(guild, ctx)
            if not channel: continue
            gain = _r.randint(200, 600)
            coffre_actif[channel.id] = {"contenu": gain, "expires": _t.time() + 300}
            embed = discord.Embed(
                title="📦 COFFRE MYSTÉRIEUX !",
                description=(
                    f"Un coffre contenant **{gain} pièces** vient d'apparaître !\n\n"
                    "💡 Tape `.ouvrir` dans **n'importe quel salon** pour l'ouvrir !\n"
                    "⚡ **Premier arrivé, premier servi !**\n"
                    f"⏰ Disparaît dans **5 minutes**"
                ),
                color=0xf1c40f
            )
            msg = await channel.send("@everyone", embed=embed)
            await asyncio.sleep(300)
            if channel.id in coffre_actif:
                del coffre_actif[channel.id]
                await msg.delete()
        except Exception as e:
            print(f"Coffre planifié error: {e}")
    event_en_cours = False

async def lancer_nuit_casino(ctx=None):
    global event_en_cours, casino_boost_actif
    event_en_cours = True
    casino_boost_actif = True
    for guild in bot.guilds:
        try:
            channel = get_event_channel(guild, ctx)
            casino_ch = guild.get_channel(SALON_CASINO_ID) if SALON_CASINO_ID else None
            if not channel: continue
            embed = discord.Embed(
                title="🎰 NUIT DU CASINO !",
                description=f"Les gains du slot sont **x2** pendant **1 heure** !\n{'Rendez-vous dans ' + casino_ch.mention if casino_ch else 'Allez jouer au casino !'} 🎲",
                color=0xe74c3c
            )
            msg = await channel.send("@everyone", embed=embed)
            await asyncio.sleep(3600)
            casino_boost_actif = False
            await msg.delete()
            await channel.send(embed=discord.Embed(description="🎰 La Nuit du Casino est terminée ! Les gains reviennent à la normale.", color=0x95a5a6))
        except Exception as e:
            print(f"Nuit casino error: {e}")
    event_en_cours = False

async def lancer_carte_mystere(ctx=None):
    global event_en_cours
    import time as _t
    if not SALON_EVENT_ID and not SALON_GACHA_ID:
        return  # Pas de salon configuré, on annule
    event_en_cours = True
    for guild in bot.guilds:
        try:
            channel_event = get_event_channel(guild)
            channel_gacha = guild.get_channel(SALON_GACHA_ID) if SALON_GACHA_ID else None
            if not channel_event or not channel_gacha:
                continue  # Salons pas configurés sur ce serveur
            role = get_gacha_role(guild)
            mention = role.mention if role else ""
            if not channel_event: continue

            # Annonce dans salon event
            embed_annonce = discord.Embed(
                title="🎴 Carte Mystère !",
                description=f"Une carte mystérieuse va apparaître dans {channel_gacha.mention if channel_gacha else 'le salon gacha'} dans **30 secondes** !\nSoyez prêts — elle disparaît en **5 minutes** ! ⚡",
                color=0x9b59b6
            )
            await channel_event.send(mention, embed=embed_annonce)
            await asyncio.sleep(30)

            # Choisir la carte (bonne ou troll 50/50)
            if _r.random() < 0.3:  # 30% imposteur
                # Carte imposteur
                embed_carte = discord.Embed(
                    title="❓ CARTE MYSTÈRE",
                    description="**??? ATK • ??? DEF • ??? PV**\n\n*Claim pour révéler !*\n\nRéagis ❤️ pour claim !",
                    color=0x2c3e50
                )
                embed_carte.set_image(url="https://i.imgur.com/JzbTwwD.jpg")
                embed_carte.set_footer(text="⚡ Disponible 5 minutes seulement !")
                msg = await (channel_gacha or channel_event).send(embed=embed_carte)
                await msg.add_reaction("❤️")

                def check_mystere(r, u):
                    return str(r.emoji) == "❤️" and r.message.id == msg.id and not u.bot

                try:
                    reaction, claimer = await bot.wait_for("reaction_add", timeout=300.0, check=check_mystere)
                    ragebait = _r.choice(MESSAGES_RAGEBAIT)
                    await msg.delete()
                    await (channel_gacha or channel_event).send(f"{claimer.mention} {ragebait}")
                except asyncio.TimeoutError:
                    await msg.delete()
            else:
                # Vraie carte aléatoire (Épique+)
                available = [k for k in ANIME_CARDS_DB if k not in claimed_cards and ANIME_CARDS_DB[k]["rarete"] in ("Épique", "Légendaire", "Mythique")]
                if not available:
                    event_en_cours = False
                    return
                key = _r.choice(available)
                c = ANIME_CARDS_DB[key]
                embed_carte = discord.Embed(
                    title="❓ CARTE MYSTÈRE",
                    description="*Une énergie mystérieuse émane de cette carte...*\n\nRéagis ❤️ pour claim et découvrir ce que c'est !",
                    color=0x9b59b6
                )
                embed_carte.set_footer(text="⚡ Disponible 5 minutes seulement !")
                msg = await (channel_gacha or channel_event).send(embed=embed_carte)
                await msg.add_reaction("❤️")

                def check_mystere2(r, u):
                    return str(r.emoji) == "❤️" and r.message.id == msg.id and not u.bot

                try:
                    reaction, claimer = await bot.wait_for("reaction_add", timeout=300.0, check=check_mystere2)
                    claimed_cards[key] = str(claimer.id)
                    gacha_collections[str(claimer.id)][key] = {"fusion": 0}
                    r_emoji = RARETE_EMOJI.get(c["rarete"], "🔵")
                    couleur = RARETE_COULEURS.get(c["rarete"], 0x9b59b6)
                    embed_reveal = discord.Embed(
                        title=f"✨ RÉVÉLATION — {c['emoji']} {c['nom']} !",
                        description=f"*{c['serie']}* {r_emoji} **{c['rarete']}**\n\n**{claimer.mention}** a claim la carte mystère !",
                        color=couleur
                    )
                    if c.get("image"):
                        embed_reveal.set_image(url=c["image"])
                    await msg.delete()
                    await (channel_gacha or channel_event).send(embed=embed_reveal)
                except asyncio.TimeoutError:
                    await msg.delete()
                    await (channel_gacha or channel_event).send(embed=discord.Embed(description="⏰ La carte mystère a disparu sans être claimée...", color=0x95a5a6))
        except Exception as e:
            print(f"Carte mystère error: {e}")
    event_en_cours = False

async def lancer_double_xp_event(ctx=None):
    global event_en_cours, double_xp_event_actif
    event_en_cours = True
    double_xp_event_actif = True
    for guild in bot.guilds:
        try:
            channel = get_event_channel(guild, ctx)
            if not channel: continue
            embed = discord.Embed(
                title="🌀 EVENT DOUBLE XP !",
                description="**Tout rapporte x2 XP pendant 1 heure !**\n\n💬 Chat • 🎯 Quiz • ⚔️ Arène • 🃏 Combat cartes\n\nSpammez les activités, c'est le moment ! 🔥",
                color=0x3498db
            )
            msg = await channel.send("@everyone", embed=embed)
            await asyncio.sleep(3600)
            double_xp_event_actif = False
            await msg.delete()
            await channel.send(embed=discord.Embed(description="🌀 L'Event Double XP est terminé ! Retour à la normale.", color=0x95a5a6))
        except Exception as e:
            print(f"Double XP event error: {e}")
    event_en_cours = False

async def lancer_nuit_chasse_event(ctx=None):
    global event_en_cours, nuit_chasse_active
    event_en_cours = True
    nuit_chasse_active = True
    for guild in bot.guilds:
        try:
            channel = get_event_channel(guild, ctx)
            if not channel: continue
            role = get_gacha_role(guild)
            mention = role.mention if role else ""
            embed = discord.Embed(
                title="🌙 NUIT DE CHASSE !",
                description=f"🔴 Les taux **Mythique** sont **DOUBLÉS** pendant **2 heures** !\n\nC'est le moment de roll ! `.ga` `.roll`",
                color=0x9b59b6
            )
            msg = await channel.send(mention, embed=embed)
            await asyncio.sleep(7200)
            nuit_chasse_active = False
            await msg.delete()
        except Exception as e:
            print(f"Nuit chasse error: {e}")
    event_en_cours = False

async def lancer_marche_noir_event(ctx=None):
    global event_en_cours
    event_en_cours = True
    import time as _t

    ITEMS_MN = [
        # Cartes
        {"type": "carte", "rarete": "Mythique", "prix": 10000},
        {"type": "carte", "rarete": "Légendaire", "prix": 6000},
        {"type": "carte", "rarete": "Épique", "prix": 3500},
        # Rôles exclusifs
        {"type": "role", "nom": "🕶️ Fantôme", "desc": "Rôle exclusif Marché Noir", "prix": 8000, "color": 0x2c2f33},
        {"type": "role", "nom": "💀 Contrebandier", "desc": "Rôle rare du marché illégal", "prix": 5000, "color": 0x8b0000},
        {"type": "role", "nom": "🐍 Serpent d\'Or", "desc": "Pour les plus riches", "prix": 12000, "color": 0xf39c12},
        # Items PvP
        {"type": "item", "id": "bombe_gacha", "nom": "💣 Bombe Gacha", "desc": "Force une perte de carte", "prix": 7000},
        {"type": "item", "id": "protection", "nom": "🌟 Protection Divine", "desc": "Immunité 2h", "prix": 4500},
        {"type": "item", "id": "amulette", "nom": "🪬 Amulette", "desc": "Renvoie les attaques", "prix": 2000},
        {"type": "item", "id": "cadenas", "nom": "🔒 Cadenas", "desc": "Bloque le claim 30min", "prix": 3500},
    ]

    for guild in bot.guilds:
        try:
            channel_event = get_event_channel(guild, ctx)
            if not channel_event: continue

            # Salon temporaire sombre
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            }
            try:
                salon_mn = await guild.create_text_channel("🕶️・marche-noir", overwrites=overwrites)
            except:
                salon_mn = channel_event

            # Choisir 5 items aléatoires
            _r.shuffle(ITEMS_MN)
            items_choisis = []
            for item in ITEMS_MN:
                if item["type"] == "carte":
                    cartes = [k for k in ANIME_CARDS_DB if k not in claimed_cards and ANIME_CARDS_DB[k]["rarete"] == item["rarete"]]
                    if cartes:
                        k = _r.choice(cartes)
                        c = ANIME_CARDS_DB[k]
                        items_choisis.append({**item, "key": k, "nom": c["nom"], "emoji": c["emoji"], "image": c.get("image","")})
                else:
                    items_choisis.append(item)
                if len(items_choisis) >= 5:
                    break

            if not items_choisis:
                event_en_cours = False
                return

            # Stocker dans marche_noir_actif
            marche_noir_actif.clear()
            for i, item in enumerate(items_choisis):
                marche_noir_actif[i] = {**item, "vendu": False, "expires": _t.time() + 7200}

            # Embed annonce dans event
            embed_annonce = discord.Embed(
                title="🕶️ LE MARCHÉ NOIR S\'OUVRE",
                description=(
                    "```\n"
                    "╔════════════════════════════════╗\n"
                    "║  🕶️   M A R C H É   N O I R   🕶️  ║\n"
                    "║  ──────────────────────────  ║\n"
                    "║  Marchandises rares...         ║\n"
                    "║  Prix exorbitants...           ║\n"
                    "║  Durée limitée...              ║\n"
                    "║  Soyez discrets.               ║\n"
                    "╚════════════════════════════════╝\n"
                    "```\n"
                    f"Les portes du marché illégal s\'ouvrent dans {salon_mn.mention}\n"
                    "⏰ **2 heures** avant fermeture"
                ),
                color=0x1a1a1a
            )
            await channel_event.send("@everyone", embed=embed_annonce)

            # Embed catalogue dans salon marché noir
            desc_catalogue = "**— MARCHANDISES DISPONIBLES —**\n\n"
            for i, item in enumerate(items_choisis):
                if item["type"] == "carte":
                    r_emoji = RARETE_EMOJI.get(item["rarete"], "")
                    desc_catalogue += f"`[{i}]` {item.get('emoji','')} **{item['nom']}** {r_emoji} — **{item['prix']:,}p** → `.marcheacheter {i}`\n"
                elif item["type"] == "role":
                    desc_catalogue += f"`[{i}]` **{item['nom']}** *(rôle exclusif)* — **{item['prix']:,}p** → `.marcheacheter {i}`\n"
                elif item["type"] == "item":
                    desc_catalogue += f"`[{i}]` **{item['nom']}** *(item PvP)* — **{item['prix']:,}p** → `.marcheacheter {i}`\n"

            embed_catalogue = discord.Embed(
                title="🕶️ CATALOGUE — Marché Noir",
                description=desc_catalogue,
                color=0x1a1a1a
            )
            embed_catalogue.set_footer(text="⚠️ Transactions anonymes — aucune garantie — durée limitée")
            await salon_mn.send(embed=embed_catalogue)

            await asyncio.sleep(7200)

            # Fermeture
            marche_noir_actif.clear()
            if salon_mn != channel_event:
                asyncio.create_task(supprimer_salon_temp(salon_mn, 7, guild, "Marché Noir"))

        except Exception as e:
            print(f"Marché Noir error: {e}")
    event_en_cours = False


async def lancer_jackpot(ctx=None):
    global jackpot_actif, jackpot_cagnotte, jackpot_contributions
    # Jackpot tourne en arrière-plan — ne bloque PAS event_en_cours
    import time as _t
    jackpot_actif = True
    jackpot_cagnotte = 0
    jackpot_contributions.clear()
    for guild in bot.guilds:
        try:
            channel = get_event_channel(guild, ctx)
            if not channel: continue
            embed = discord.Embed(
                title="💸 JACKPOT COMMUNAUTAIRE LANCÉ !",
                description="**Chaque message = +1 pièce dans la cagnotte !**\n\nObjectif : **1500 pièces** → redistribution aux 5 membres les plus pauvres actifs !\n\nTape `.jackpot` pour suivre l'avancée en temps réel 📊\n\n*Cooldown invisible de 1min entre contributions • Max 100p/membre*",
                color=0xf1c40f
            )
            await channel.send("@everyone", embed=embed)
        except Exception as e:
            print(f"Jackpot error: {e}")

async def lancer_draft_cartes(ctx=None):
    global event_en_cours
    event_en_cours = True
    for guild in bot.guilds:
        try:
            channel_event = get_event_channel(guild)
            channel_gacha = guild.get_channel(SALON_GACHA_ID) if SALON_GACHA_ID else channel_event
            role = get_gacha_role(guild)
            mention = role.mention if role else ""
            if not channel_event: continue
            available = [k for k in ANIME_CARDS_DB if k not in claimed_cards and ANIME_CARDS_DB[k]["rarete"] == "Épique"]
            if len(available) < 3:
                event_en_cours = False
                return
            cartes_draft = _r.sample(available, 3)
            embed_annonce = discord.Embed(
                title="🃏 DRAFT DE CARTES !",
                description=f"3 cartes Épique vont apparaître une par une dans {channel_gacha.mention if channel_gacha else 'le salon gacha'} !\nPremier à réagir ❤️ prend la carte ! Une toutes les **5 minutes** ⚡",
                color=0x9b59b6
            )
            await channel_event.send(mention, embed=embed_annonce)
            await asyncio.sleep(30)
            for i, key in enumerate(cartes_draft):
                c = ANIME_CARDS_DB[key]
                r_emoji = RARETE_EMOJI.get(c["rarete"], "🟣")
                embed = discord.Embed(
                    title=f"🃏 Carte {i+1}/3 — {c['emoji']} {c['nom']}",
                    description=f"*{c['serie']}* {r_emoji} **{c['rarete']}**\n\n❤️ **ATK {c['attaque']} • DEF {c['defense']} • PV {c['pv']}**\n\nPremier à réagir ❤️ la prend !",
                    color=RARETE_COULEURS.get(c["rarete"], 0x9b59b6)
                )
                if c.get("image"):
                    embed.set_image(url=c["image"])
                embed.set_footer(text="⚡ Disponible 5 minutes !")
                msg = await (channel_gacha or channel_event).send(embed=embed)
                await msg.add_reaction("❤️")
                def check_draft(r, u, k=key):
                    return str(r.emoji) == "❤️" and r.message.id == msg.id and not u.bot
                try:
                    reaction, claimer = await bot.wait_for("reaction_add", timeout=300.0, check=check_draft)
                    claimed_cards[key] = str(claimer.id)
                    gacha_collections[str(claimer.id)][key] = {"fusion": 0}
                    await msg.delete()
                    await (channel_gacha or channel_event).send(f"🎉 **{claimer.display_name}** a récupéré **{c['nom']}** {r_emoji} !")
                except asyncio.TimeoutError:
                    await msg.delete()
                    await (channel_gacha or channel_event).send(f"⏰ **{c['nom']}** n'a pas été claimé...")
                if i < 2:
                    await asyncio.sleep(300)
        except Exception as e:
            print(f"Draft cartes error: {e}")
    event_en_cours = False

async def lancer_guerre_factions(ctx=None):
    global event_en_cours
    event_en_cours = True
    for guild in bot.guilds:
        try:
            channel_event = get_event_channel(guild, ctx)
            if not channel_event: continue

            # Créer salon visible uniquement par les membres de factions
            FACTION_ROLES_NAMES = ["🔴 Akatsuki", "💙 Bataillon d\'Exploration",
                                    "🏴\u200d☠️ Équipage du Chapeau de Paille",
                                    "🕷️ Phantom Troupe", "🌸 Gotei 13", "💚 Lycée U.A."]
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            }
            for rname in FACTION_ROLES_NAMES:
                role = discord.utils.get(guild.roles, name=rname)
                if role:
                    overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

            try:
                salon_guerre = await guild.create_text_channel("⚔️・guerre-des-factions", overwrites=overwrites)
            except:
                salon_guerre = channel_event

            # Mentions factions
            mentions_factions = []
            for rname in FACTION_ROLES_NAMES:
                role = discord.utils.get(guild.roles, name=rname)
                if role:
                    mentions_factions.append(role.mention)

            mention_str = " ".join(mentions_factions) if mentions_factions else "@everyone"

            # Boss géant
            boss = _r.choice(BOSS_INVASIONS).copy()
            pv_boss = boss["pv"] * 3
            invasion_active[guild.id] = {**boss, "pv": pv_boss, "max_pv": pv_boss, "attaquants": {}, "actif": True, "guerre": True}

            embed = discord.Embed(
                title=f"🏴‍☠️ GUERRE DES FACTIONS",
                description=(
                    f"Un boss légendaire défie les factions !\n\n"
                    f"❤️ **{pv_boss:,} PV** — 3x plus résistant !\n\n"
                    "`.attaquerboss` pour combattre !\n"
                    "La faction ayant infligé le plus de dégâts gagne :\n"
                    "💰 **+500 pièces** + **+100 réputation** !"
                ),
                color=0x8b0000
            )

            # Construire mentions factions uniquement
            faction_mentions = []
            for fid in FACTIONS.keys():
                fname = {
                    "akatsuki": "🔴 Akatsuki",
                    "surveycorps": "💙 Bataillon d\'Exploration",
                    "strawhat": "🏴 Chapeau de Paille",
                    "phantomtroupe": "🕷️ Phantom Troupe",
                    "gotei13": "🌸 Gotei 13",
                    "ua": "💚 Lycée U.A.",
                }.get(fid, "")
                r = discord.utils.get(guild.roles, name=fname)
                if r: faction_mentions.append(r.mention)
            ping_str = " ".join(faction_mentions) if faction_mentions else "@everyone"
            await channel_event.send(f"{ping_str}", embed=embed)
            await salon_guerre.send(f"{ping_str}", embed=embed)

            await asyncio.sleep(7200)

            # Résultats
            inv = invasion_active.get(guild.id, {})
            attaquants = inv.get("attaquants", {})
            faction_degats = {}
            for uid, degats in attaquants.items():
                fid = faction_data.get(uid)
                if fid:
                    faction_degats[fid] = faction_degats.get(fid, 0) + degats

            if faction_degats:
                winner_fid = max(faction_degats, key=faction_degats.get)
                fd = FACTIONS.get(winner_fid, {})
                membres_winners = [guild.get_member(int(uid)) for uid, fid in faction_data.items() if fid == winner_fid and guild.get_member(int(uid))]
                mentions_winners = " ".join([m.mention for m in membres_winners[:10] if m])
                for uid, fid in faction_data.items():
                    if fid == winner_fid:
                        economy_data[uid]["coins"] += 500
                        faction_rep[uid] = faction_rep.get(uid, 0) + 100

                embed_result = discord.Embed(
                    title="🏆 Faction Victorieuse de la Guerre !",
                    description=f"{mentions_winners}\n\n**+500 pièces** + **+100 réputation** pour chaque membre !",
                    color=0xf1c40f
                )
                await channel_event.send(embed=embed_result)
                await salon_guerre.send(embed=embed_result)

            if guild.id in invasion_active:
                del invasion_active[guild.id]
            asyncio.create_task(supprimer_salon_temp(salon_guerre, 7, guild, "Guerre des Factions"))

        except Exception as e:
            print(f"Guerre factions error: {e}")
    event_en_cours = False


async def lancer_event_surprise(ctx=None):
    global event_en_cours
    if event_en_cours:
        return
    for guild in bot.guilds:
        try:
            channel = get_event_channel(guild, ctx)
            if not channel: continue
            embed_annonce = discord.Embed(
                title="⚠️ EVENT SURPRISE",
                description="*Un event mystérieux arrive dans **1 heure**...*\n\n**Soyez prêts !** 👀",
                color=0x95a5a6
            )
            await channel.send("@everyone", embed=embed_annonce)
        except Exception as e:
            print(f"Event surprise annonce error: {e}")
    await asyncio.sleep(3600)
    events_possibles = [lancer_coffre_planifie, lancer_nuit_casino, lancer_carte_mystere, lancer_double_xp_event, lancer_nuit_chasse_event, lancer_draft_cartes]
    await _r.choice(events_possibles)()

async def lancer_heure_maudite(ctx=None):
    global event_en_cours, double_xp_event_actif
    event_en_cours = True
    for guild in bot.guilds:
        try:
            channel = get_event_channel(guild, ctx)
            if not channel: continue
            gacha_ch = guild.get_channel(SALON_GACHA_ID) if SALON_GACHA_ID else channel
            embed = discord.Embed(
                title="🌙 L'HEURE MAUDITE",
                description=(
                    "```\n"
                    "╔═══════════════════════════════╗\n"
                    "║  🌑  H E U R E  M A U D I T E  🌑  ║\n"
                    "║  ─────────────────────────  ║\n"
                    "║   Il est 2h du matin...       ║\n"
                    "║   Les ombres s\'éveillent...   ║\n"
                    "║   Les cartes Épique surgissent ║\n"
                    "╚═══════════════════════════════╝\n"
                    "```\n"
                    "Les cartes **Épique** ont **×2 de chance** d\'apparaître\n"
                    "pendant les **30 prochaines minutes** !\n\n"
                    "*Ne dormez pas... ou alors dormez — pendant que les autres farm 😈*"
                ),
                color=0x1a1a2e
            )
            await channel.send(f"{GACHA_MENTION}", embed=embed)
            if gacha_ch and gacha_ch != channel:
                await gacha_ch.send(f"{GACHA_MENTION}", embed=discord.Embed(
                    description="🌑 **L\'Heure Maudite** est active — ×2 chance sur les **Épique** pendant **30 min** !",
                    color=0x1a1a2e
                ))
            await asyncio.sleep(1800)
            await channel.send(embed=discord.Embed(
                description="🌙 L\'Heure Maudite s\'estompe... les ombres se retirent.",
                color=0x95a5a6
            ))
        except Exception as e:
            print(f"Heure maudite error: {e}")
    event_en_cours = False


async def lancer_imposteur(ctx=None):
    for guild in bot.guilds:
        try:
            channel_gacha = guild.get_channel(SALON_GACHA_ID) if SALON_GACHA_ID else get_event_channel(guild)
            if not channel_gacha: continue
            embed = discord.Embed(
                title="🎴 ??? CARTE INCONNUE ???",
                description="**ATK : 9999 • DEF : 9999 • PV : 9999**\n\n*Une énergie démoniaque émane de cette carte...*\n*Elle semble indestructible...*\n\nRéagis ❤️ pour claim si tu l'oses ! ⚡",
                color=0x000000
            )
            embed.set_footer(text="🔥 ULTRA RARE — DISPONIBLE 1H")
            msg = await channel_gacha.send(embed=embed)
            await msg.add_reaction("❤️")
            def check_imp(r, u):
                return str(r.emoji) == "❤️" and r.message.id == msg.id and not u.bot
            try:
                reaction, claimer = await bot.wait_for("reaction_add", timeout=3600.0, check=check_imp)
                ragebait = _r.choice(MESSAGES_RAGEBAIT)
                await msg.delete()
                await channel_gacha.send(f"{claimer.mention} {ragebait}")
            except asyncio.TimeoutError:
                await msg.delete()
        except Exception as e:
            print(f"Imposteur error: {e}")


# ============================================================
#  🔧 COMMANDES ADMIN — GESTION ÉCONOMIE & XP
# ============================================================

@bot.command(name="givepieces", aliases=["addpieces", "donnerpieces"])
@commands.has_permissions(administrator=True)
async def givepieces_cmd(ctx, membre: discord.Member = None, montant: int = None):
    """Donne des pièces à un membre — .givepieces @joueur <montant>"""
    if not membre or not montant:
        return await ctx.send("❌ Usage : `.givepieces @joueur <montant>`")
    if montant <= 0:
        return await ctx.send("❌ Le montant doit être positif !")
    uid = str(membre.id)
    economy_data[uid]["coins"] += montant
    embed = discord.Embed(
        title="💰 Pièces attribuées",
        description=f"**+{montant:,} pièces** donnés à {membre.mention}\nNouveau solde : **{economy_data[uid]['coins']:,} pièces**",
        color=0x2ecc71
    )
    embed.set_footer(text=f"Action effectuée par {ctx.author.display_name}")
    await ctx.send(embed=embed)

@bot.command(name="retirerpieces", aliases=["removepieces", "deduirepieces"])
@commands.has_permissions(administrator=True)
async def retirerpieces_cmd(ctx, membre: discord.Member = None, montant: int = None):
    """Retire des pièces à un membre — .retirerpieces @joueur <montant>"""
    if not membre or not montant:
        return await ctx.send("❌ Usage : `.retirerpieces @joueur <montant>`")
    if montant <= 0:
        return await ctx.send("❌ Le montant doit être positif !")
    uid = str(membre.id)
    avant = economy_data[uid]["coins"]
    economy_data[uid]["coins"] = max(0, economy_data[uid]["coins"] - montant)
    retire = avant - economy_data[uid]["coins"]
    embed = discord.Embed(
        title="💸 Pièces retirées",
        description=f"**-{retire:,} pièces** retirés à {membre.mention}\nNouveau solde : **{economy_data[uid]['coins']:,} pièces**",
        color=0xe74c3c
    )
    embed.set_footer(text=f"Action effectuée par {ctx.author.display_name}")
    await ctx.send(embed=embed)

@bot.command(name="givexp", aliases=["addxp", "donnerxp"])
@commands.has_permissions(administrator=True)
async def givexp_cmd(ctx, membre: discord.Member = None, montant: int = None):
    """Donne de l'XP à un membre — .givexp @joueur <montant>"""
    if not membre or not montant:
        return await ctx.send("❌ Usage : `.givexp @joueur <montant>`")
    if montant <= 0:
        return await ctx.send("❌ Le montant doit être positif !")
    uid = str(membre.id)
    xp_data[uid]["xp"] += montant
    # Vérifier level up
    needed = xp_data[uid]["level"] * 100
    levels_gained = 0
    while xp_data[uid]["xp"] >= needed:
        xp_data[uid]["level"] += 1
        xp_data[uid]["xp"] -= needed
        needed = xp_data[uid]["level"] * 100
        levels_gained += 1
    embed = discord.Embed(
        title="⭐ XP attribué",
        description=(
            f"**+{montant:,} XP** donnés à {membre.mention}\n"
            f"Niveau actuel : **{xp_data[uid]['level']}**\n"
            f"XP actuel : **{xp_data[uid]['xp']}/{xp_data[uid]['level']*100}**"
            + (f"\n🎉 **+{levels_gained} niveau(x) gagné(s) !**" if levels_gained else "")
        ),
        color=0xf1c40f
    )
    embed.set_footer(text=f"Action effectuée par {ctx.author.display_name}")
    await ctx.send(embed=embed)

@bot.command(name="retirerxp", aliases=["removexp", "deduirexp"])
@commands.has_permissions(administrator=True)
async def retirerxp_cmd(ctx, membre: discord.Member = None, montant: int = None):
    """Retire de l'XP à un membre — .retirerxp @joueur <montant>"""
    if not membre or not montant:
        return await ctx.send("❌ Usage : `.retirerxp @joueur <montant>`")
    if montant <= 0:
        return await ctx.send("❌ Le montant doit être positif !")
    uid = str(membre.id)
    avant_xp = xp_data[uid]["xp"]
    avant_lvl = xp_data[uid]["level"]
    xp_data[uid]["xp"] = max(0, xp_data[uid]["xp"] - montant)
    embed = discord.Embed(
        title="📉 XP retiré",
        description=(
            f"**-{montant:,} XP** retirés à {membre.mention}\n"
            f"Niveau actuel : **{xp_data[uid]['level']}**\n"
            f"XP actuel : **{xp_data[uid]['xp']}/{xp_data[uid]['level']*100}**"
        ),
        color=0xe74c3c
    )
    embed.set_footer(text=f"Action effectuée par {ctx.author.display_name}")
    await ctx.send(embed=embed)

@bot.command(name="resetall", aliases=["fullreset"])
@commands.has_permissions(administrator=True)
async def resetall_cmd(ctx):
    """Reset complet — XP, pièces et gacha — .resetall"""
    embed_confirm = discord.Embed(
        title="⚠️ RESET TOTAL",
        description=(
            "Tu es sur le point de **tout reset** :\n\n"
            "💰 Toutes les pièces → 0\n"
            "⭐ Tous les niveaux XP → 0\n"
            "🎴 Toutes les cartes gacha → libérées\n\n"
            "**Cette action est irréversible !**\n"
            "Réagis ✅ pour confirmer ou ❌ pour annuler."
        ),
        color=0xe74c3c
    )
    msg = await ctx.send(embed=embed_confirm)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")

    def check(reaction, user):
        return user == ctx.author and reaction.message.id == msg.id and str(reaction.emoji) in ["✅", "❌"]

    try:
        reaction, user = await bot.wait_for("reaction_add", timeout=30.0, check=check)
        if str(reaction.emoji) == "❌":
            await msg.edit(embed=discord.Embed(description="❌ Reset annulé.", color=0x95a5a6))
            await msg.clear_reactions()
            return

        # Reset pièces
        for uid in economy_data:
            economy_data[uid]["coins"] = 0
            economy_data[uid]["bank"] = 0

        # Reset XP
        for uid in xp_data:
            xp_data[uid]["xp"] = 0
            xp_data[uid]["level"] = 1

        # Reset gacha
        claimed_cards.clear()
        gacha_collections.clear()
        fusion_levels.clear()
        cartes_favorites.clear()
        trade_history.clear()

        # Reset points amélio
        points_amelio.clear()
        arena_stats.clear()

        embed_done = discord.Embed(
            title="✅ Reset total effectué",
            description=(
                "Tout a été remis à zéro :\n\n"
                "💰 Pièces → **0**\n"
                "⭐ Niveaux → **1**\n"
                "🎴 Cartes → **libérées**\n"
                "📊 Stats arène → **reset**"
            ),
            color=0x2ecc71
        )
        embed_done.set_footer(text=f"Reset effectué par {ctx.author.display_name}")
        await msg.edit(embed=embed_done)
        await msg.clear_reactions()

    except asyncio.TimeoutError:
        await msg.edit(embed=discord.Embed(description="⏰ Confirmation expirée — reset annulé.", color=0x95a5a6))
        await msg.clear_reactions()


# ============================================================
#  🎪 EVENTS V2 — SYSTÈME COMPLET
# ============================================================

# ── Variables globales ────────────────────────────────────────
tournoi_inscriptions = {}    # {guild_id: [user_id, ...]}
parminous_game = {}          # {guild_id: {imposteur, victimes, cartes_volees, votes}}
lg_games = {}                # {guild_id: game_data} — Loup Garou
encheres_actives = {}        # {guild_id: {carte_key, mises: {uid: montant}, msg_id}}
wanted_actif = {}            # {guild_id: {cible_id, prime, crimes, chasseurs}}
mine_actif = {}              # {guild_id: {pepites, joueurs: {uid: total}, malédiction_pos}}
roue_actif = {}              # {guild_id: bool}
oracle_prophecies = {}       # {uid: prophecy}
pacte_actif = {}             # {guild_id: [(uid1, uid2), ...]}
death_note = {}              # {guild_id: {porteur: uid, victimes: [], utilisations: 0}}
clown_actif = {}             # {guild_id: uid}
canard_actif = {}            # {guild_id: {proprio: uid, humeur: str}}
virus_carte = {}             # {guild_id: {carte_key, porteur: uid, effets: []}}
magicien_actif = {}          # {guild_id: {magicien: uid, sorts_restants: 3}}
conquete_zones = {}          # {guild_id: {zone_id: faction_id}}
conquete_role_id = {}        # {guild_id: role_id}
puzzle_actif = {}            # {guild_id: {carte_key, scores: {uid: int}, fragment: int}}
fausse_rumeur_active = {}    # {guild_id: {douteurs: {uid: bool}, debut: timestamp}}
vague_actif = {}             # {guild_id: bool}
CONQUETE_ZONE_IDS = []       # IDs des salons de conquête configurés

CRIMES_FICTIFS = [
    "avoir volé le ramen de Naruto pendant son sommeil",
    "avoir prétendu que Sasuke était le meilleur personnage de Naruto",
    "avoir spoilé la fin de Attack on Titan dans le chat",
    "avoir dit que Shanks était surestimé",
    "avoir refusé de partager ses cartes Mythique",
    "avoir battu 12 membres en arène pendant qu'ils dormaient",
    "avoir fait semblant d'être AFK pendant 3h pour éviter les duels",
    "avoir claim une carte que tout le monde voulait à 3h du matin",
    "avoir dit que Gojo était moins fort qu'il en a l'air",
    "avoir perdu intentionnellement pour faire monter la prime de quelqu'un",
]

PROPHECIES = [
    "perdra ses 3 prochains duels consécutifs",
    "verra ses pièces diminuer de 10% au prochain .daily",
    "recevra une carte Commune lors de son prochain roll",
    "sera la prochaine cible d'un item PvP",
    "échouera lors de sa prochaine tentative d'investissement",
    "verra sa meilleure carte convoitée par quelqu'un",
    "perdra 50 pièces mystérieusement cette nuit",
    "aura son prochain quiz raté même s'il connaît la réponse",
]

SORTS_MAGICIEN = ["double_pieces", "bloquer_commandes", "carte_troll"]

CREATURES = [
    {"nom": "Kyubi", "capacite": "double_xp", "desc": "Double ton XP pendant 30 min"},
    {"nom": "Dragon Bleu", "capacite": "boost_rolls", "desc": "+3 rolls bonus"},
    {"nom": "Phénix", "capacite": "ressusciter", "desc": "Récupère tes pièces perdues une fois"},
    {"nom": "Kitsune", "capacite": "vol_pieces", "desc": "Vole 50p à un membre random"},
    {"nom": "Tanuki", "capacite": "illusion", "desc": "Cache ton solde pendant 1h"},
    {"nom": "Ryū", "capacite": "bonus_arene", "desc": "+20% de dégâts en arène"},
]

# ── Helper : créer/obtenir un rôle automatiquement ────────────
async def get_or_create_role(guild, nom, couleur=0x9b59b6, mentionable=True):
    role = discord.utils.get(guild.roles, name=nom)
    if not role:
        try:
            role = await guild.create_role(
                name=nom,
                color=discord.Color(couleur),
                mentionable=mentionable,
                reason="Rôle créé automatiquement par Akari"
            )
        except:
            pass
    return role

# ── Helper : créer un salon temporaire ───────────────────────
async def creer_salon_temp(guild, nom, categorie_nom=None):
    try:
        categorie = None
        if categorie_nom:
            categorie = discord.utils.get(guild.categories, name=categorie_nom)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }
        salon = await guild.create_text_channel(nom, overwrites=overwrites, category=categorie)
        return salon
    except:
        return None

async def supprimer_salon_temp(salon, delai=7, guild=None, nom_event=""):
    await asyncio.sleep(delai)
    try:
        # Annonce dans salon event avant suppression
        if guild and nom_event:
            # Forcer le salon event pour l'annonce de fin
            channel_event = guild.get_channel(SALON_EVENT_ID) if SALON_EVENT_ID else guild.system_channel
            if channel_event and channel_event != salon:
                embed_fin = discord.Embed(
                    description=f"✅ **{nom_event}** est terminé ! Merci d'avoir participé 🎉",
                    color=0x2ecc71
                )
                try:
                    await channel_event.send(embed=embed_fin)
                except:
                    pass
        await salon.delete()
    except:
        pass

# ── .lancerevent ──────────────────────────────────────────────
@bot.command(name="lancerevent", aliases=["le", "event"])
@commands.has_permissions(administrator=True)
async def lancerevent_cmd(ctx, nom: str = None):
    """Lance un event manuellement — .lancerevent <nom>"""
    events_dispo = {
        # ── Events spéciaux ──
        "roue": lancer_roue_fortune,
        "proces": lancer_proces,
        "tournoi": lancer_tournoi,
        "mine": lancer_mine_or,
        "parminous": lancer_parminous,
        "fausserumeur": lancer_fausse_rumeur,
        "encheres": lancer_encheres,
        "voleur": lancer_voleur_minuit,
        "wanted": lancer_wanted,
        "reve": lancer_reve_collectif,
        "magicien": lancer_magicien,
        "clown": lancer_clown,
        "corbeau": lancer_corbeau,
        "pacifiste": lancer_event_pacifiste,
        "oracle": lancer_oracle_maudit,
        "pacte": lancer_pacte,
        "losers": lancer_festival_losers,
        "puzzle": lancer_puzzle_collectif,
        # ── Events automatiques ──
        "coffre": lancer_coffre_planifie,
        "nuitcasino": lancer_nuit_casino,
        "cartemystere": lancer_carte_mystere,
        "doublexp": lancer_double_xp_event,
        "nuitchasse": lancer_nuit_chasse_event,
        "marchenoir": lancer_marche_noir_event,
        "jackpot": lancer_jackpot,
        "draft": lancer_draft_cartes,
        "guerre": lancer_guerre_factions,
        "surprise": lancer_event_surprise,
        "heuremaudite": lancer_heure_maudite,
        "imposteur": lancer_imposteur,
        "classement": lancer_classement_hebdo,
        "colis": lancer_colis_mystere,
        "vaguelegendaires": lancer_vague_legendaires,
        "bossfinal": lancer_boss_final,
        "deathnote": lancer_death_note,
        "alerterouge": lancer_alerte_rouge,
        "conquete": lancer_conquete,
        "prophetie": lancer_prophetie_accomplie,
        "prophetiehebdo": lancer_prophetie_hebdo,
    }

    if not nom:
        tous = list(events_dispo.keys())
        desc = (
            "Tous les events sont **automatiques** selon le planning.\n"
            "Les admins peuvent aussi en lancer un à tout moment.\n\n"
            + " • ".join(f"`{k}`" for k in tous)
        )
        return await ctx.send(embed=discord.Embed(
            title="🎪 Events — `.lancerevent <nom>`",
            description=desc,
            color=0x9b59b6
        ))

    if nom.lower() not in events_dispo:
        return await ctx.send(f"❌ Event `{nom}` introuvable ! Tape `.lancerevent` pour la liste.")

    if event_en_cours:
        return await ctx.send("❌ Un event est déjà en cours ! Attends qu'il se termine.")

    channel_ev = get_event_channel(ctx.guild)
    if channel_ev:
        await ctx.send(f"✅ Lancement de **{nom}** — annonce dans {channel_ev.mention} !", delete_after=5)
    else:
        await ctx.send(f"⚠️ Fais `.setsalon event` d'abord ! Pour l'instant annonce dans le system channel.", delete_after=8)
    await events_dispo[nom.lower()]()

# ══════════════════════════════════════════════════════════════
#  EVENTS — FONCTIONS
# ══════════════════════════════════════════════════════════════

# ── 🎲 ROUE DE LA FORTUNE ─────────────────────────────────────
async def lancer_roue_fortune(ctx=None):
    global event_en_cours
    event_en_cours = True

    cases = [
        {"emoji": "💰", "nom": "Jackpot", "desc": "×2 pièces pour tout le monde !", "positif": True},
        {"emoji": "🎰", "nom": "Rolls Bonus", "desc": "+3 rolls pour tout le monde !", "positif": True},
        {"emoji": "🃏", "nom": "Carte Épique", "desc": "Une carte Épique va pop dans le prochain tirage !", "positif": True},
        {"emoji": "⭐", "nom": "XP Boost", "desc": "×2 XP pendant 1h !", "positif": True},
        {"emoji": "💸", "nom": "Crise", "desc": "-30% pièces pour tout le monde...", "positif": False},
        {"emoji": "🔒", "nom": "Panne", "desc": "Tous les rolls bloqués pendant 30 min !", "positif": False},
        {"emoji": "👁️", "nom": "Malédiction", "desc": "Le membre le plus actif perd 500 pièces !", "positif": False},
        {"emoji": "🎁", "nom": "Mystère", "desc": "Un effet aléatoire s'applique...", "positif": True},
    ]

    for guild in bot.guilds:
        try:
            channel = get_event_channel(guild, ctx)
            if not channel: continue

            roue_emojis = ["💰","🎰","🃏","⭐","💸","🔒","👁️","🎁"]
            roue_emojis = ["💰","🎰","🃏","⭐","💸","🔒","👁️","🎁"]
            embed = discord.Embed(
                title="🎲 LA ROUE DE LA FORTUNE DU QG",
                description=(
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "**Personne ne contrôle son destin...**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "```\n[ 💰 🎰 🃏 ⭐ 💸 🔒 👁️ 🎁 ]\n```\n"
                    "*La roue tourne...*"
                ),
                color=0xf1c40f
            )
            msg = await channel.send("@everyone", embed=embed)

            # Animation roue
            import random as _rand
            frames = [
                "```\n[ 💰 🎰 🃏 ⭐ 💸 🔒 👁️ 🎁 ]\n     ↑```",
                "```\n[ 🎰 🃏 ⭐ 💸 🔒 👁️ 🎁 💰 ]\n          ↑```",
                "```\n[ 🃏 ⭐ 💸 🔒 👁️ 🎁 💰 🎰 ]\n               ↑```",
                "```\n[ ⭐ 💸 🔒 👁️ 🎁 💰 🎰 🃏 ]\n                    ↑```",
                "```\n[ 💸 🔒 👁️ 🎁 💰 🎰 🃏 ⭐ ]\n                         ↑```",
            ]
            for frame in frames:
                embed.description = (
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "**La roue tourne... 🌀**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    + frame
                )
                await msg.edit(embed=embed)
                await asyncio.sleep(1.5)

            await asyncio.sleep(2)
            case = _r.choice(cases)

            visuel = {
                "Jackpot": "```\n╔══════════════════╗\n║  💰  J A C K P O T  💰  ║\n║  ×2 PIÈCES POUR TOUS !  ║\n╚══════════════════╝\n```",
                "Rolls Bonus": "```\n╔══════════════════╗\n║  🎰  ROLLS BONUS  🎰  ║\n║  +3 ROLLS POUR TOUS !  ║\n╚══════════════════╝\n```",
                "Carte Épique": "```\n╔══════════════════╗\n║  🃏  CARTE ÉPIQUE  🃏  ║\n║  POP AU PROCHAIN TIRAGE ║\n╚══════════════════╝\n```",
                "XP Boost": "```\n╔══════════════════╗\n║  ⭐  XP BOOST  ⭐  ║\n║  ×2 XP PENDANT 1H !    ║\n╚══════════════════╝\n```",
                "Crise": "```\n╔══════════════════╗\n║  💸  C R I S E  💸  ║\n║  -30% PIÈCES... 😱    ║\n╚══════════════════╝\n```",
                "Panne": "```\n╔══════════════════╗\n║  🔒  P A N N E  🔒  ║\n║  ROLLS BLOQUÉS 30MIN    ║\n╚══════════════════╝\n```",
                "Malédiction": "```\n╔══════════════════╗\n║  👁️  MALÉDICTION  👁️  ║\n║  LE +ACTIF PERD 500P... ║\n╚══════════════════╝\n```",
                "Mystère": "```\n╔══════════════════╗\n║  🎁   MYSTÈRE  🎁  ║\n║  EFFET INCONNU...  👀  ║\n╚══════════════════╝\n```",
            }.get(case["nom"], "")

            embed_result = discord.Embed(
                title=f"{case['emoji']} LA ROUE S'ARRÊTE SUR... {case['nom'].upper()} !",
                description=(
                    f"{visuel}\n\n"
                    f"**{case['desc']}**"
                ),
                color=0x2ecc71 if case['positif'] else 0xe74c3c
            )

            # Appliquer l'effet
            if case['nom'] == "Jackpot":
                for uid in economy_data:
                    economy_data[uid]['coins'] = int(economy_data[uid]['coins'] * 2)
            elif case['nom'] == "XP Boost":
                global double_xp_event_actif
                double_xp_event_actif = True
                asyncio.create_task(asyncio.sleep(3600))
            elif case['nom'] == "Crise":
                for uid in economy_data:
                    economy_data[uid]['coins'] = int(economy_data[uid]['coins'] * 0.7)
            elif case['nom'] == "Malédiction":
                if message_count:
                    top_uid = max(message_count, key=message_count.get)
                    economy_data[top_uid]['coins'] = max(0, economy_data[top_uid]['coins'] - 500)
                    m = guild.get_member(int(top_uid))
                    embed_result.description += f"\n\n💀 Victime : **{m.display_name if m else top_uid}**"

            await msg.delete()
            await channel.send(embed=embed_result)

        except Exception as e:
            print(f"Roue fortune error: {e}")

    for guild in bot.guilds:
            try:
                ch = guild.get_channel(SALON_EVENT_ID) if SALON_EVENT_ID else guild.system_channel
                if ch:
                    await ch.send(embed=discord.Embed(
                        description="✅ **Roue de la Fortune** terminée ! Merci d\'avoir participé 🎉",
                        color=0x2ecc71
                    ))
            except: pass
    event_en_cours = False

# ── 🎭 PROCÈS DU QG ───────────────────────────────────────────
async def lancer_proces(ctx=None):
    global event_en_cours
    event_en_cours = True
    for guild in bot.guilds:
        try:
            channel_event = get_event_channel(guild, ctx)
            if not channel_event: continue
            membres_actifs = [m for m in guild.members if not m.bot and str(m.id) in economy_data]
            if len(membres_actifs) < 3:
                await channel_event.send("❌ Pas assez de membres actifs (minimum 3) !")
                event_en_cours = False
                return
            accuse = _r.choice(membres_actifs)
            crime = _r.choice(CRIMES_FICTIFS)
            mise = 100
            embed = discord.Embed(
                title="⚖️ LE TRIBUNAL DU QG KDRAMA",
                description=(
                    "```\n"
                    "═══════════════════════════════\n"
                    "  ⚖️  SÉANCE EXTRAORDINAIRE  ⚖️  \n"
                    "═══════════════════════════════\n"
                    "```\n"
                    f"**L'ACCUSÉ :** {accuse.mention}\n"
                    f"**CRIME :** *{crime}*\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🗳️ **Votez pendant 60 secondes !**\n\n"
                    f"✅ **COUPABLE** → {accuse.mention} perd **{mise} pièces** redistribuées\n"
                    f"❌ **INNOCENT** → Les faux accusateurs perdent **{mise} pièces**\n\n"
                    "*L'honneur du QG est entre vos mains...*"
                ),
                color=0xe67e22
            )
            embed.set_thumbnail(url=accuse.display_avatar.url)
            embed.set_footer(text="⚖️ Le silence est coupable — votez !")
            msg = await channel_event.send(embed=embed)
            await msg.add_reaction("✅")
            await msg.add_reaction("❌")
            await asyncio.sleep(60)
            msg = await channel_event.fetch_message(msg.id)
            coupable_voters = []
            innocent_voters = []
            for reaction in msg.reactions:
                async for user in reaction.users():
                    if user.bot or user == accuse: continue
                    if str(reaction.emoji) == "✅": coupable_voters.append(user)
                    elif str(reaction.emoji) == "❌": innocent_voters.append(user)
            if len(coupable_voters) > len(innocent_voters):
                economy_data[str(accuse.id)]['coins'] = max(0, economy_data[str(accuse.id)]['coins'] - mise)
                part = mise // max(len(coupable_voters), 1)
                for voter in coupable_voters:
                    economy_data[str(voter.id)]['coins'] += part
                verdict = f"⚖️ **COUPABLE !** {accuse.mention} perd **{mise} pièces** redistribuées aux jurés !"
                color = 0xe74c3c
            else:
                economy_data[str(accuse.id)]['coins'] += mise
                for voter in coupable_voters:
                    economy_data[str(voter.id)]['coins'] = max(0, economy_data[str(voter.id)]['coins'] - mise)
                verdict = f"⚖️ **INNOCENT !** {accuse.mention} reçoit **{mise} pièces** ! Les faux accusateurs sont punis !"
                color = 0x2ecc71
            await channel_event.send(embed=discord.Embed(title="⚖️ VERDICT", description=verdict, color=color))
        except Exception as e:
            print(f"Procès error: {e}")
    for guild in bot.guilds:
            try:
                ch = guild.get_channel(SALON_EVENT_ID) if SALON_EVENT_ID else guild.system_channel
                if ch:
                    await ch.send(embed=discord.Embed(
                        description="✅ **Procès du QG** terminé — le verdict est rendu ! Merci d\'avoir participé 🎉",
                        color=0x2ecc71
                    ))
            except: pass
    event_en_cours = False

# ── 📰 FAUSSE RUMEUR ──────────────────────────────────────────

async def lancer_tournoi(ctx=None):
    global event_en_cours
    event_en_cours = True

    for guild in bot.guilds:
        try:
            channel = get_event_channel(guild, ctx)
            if not channel: continue

            # Annonce inscriptions
            embed_inscrit = discord.Embed(
                title="⚔️ LE GRAND TOURNOI DU QG",
                description=(
                    "```\n"
                    "╔═══════════════════════════════╗\n"
                    "║   ⚔️   GRAND TOURNOI   ⚔️   ║\n"
                    "║        QG  KDRAMA             ║\n"
                    "║  ─────────────────────────  ║\n"
                    "║  Un seul survivant.           ║\n"
                    "║  Un seul Champion.            ║\n"
                    "╚═══════════════════════════════╝\n"
                    "```\n"
                    "Réagis ⚔️ pour t\'inscrire — **2 minutes** !\n\n"
                    "🏆 **Récompenses Gagnant :**\n"
                    "💰 **+500 pièces**\n"
                    "⚡ **+2 points d\'amélioration**\n"
                    "👑 Rôle **Champion du QG** *(permanent)*"
                ),
                color=0xe74c3c
            )
            msg_inscrit = await channel.send(embed=embed_inscrit)
            await msg_inscrit.add_reaction("⚔️")

            await asyncio.sleep(120)

            # Récupérer inscrits
            msg_inscrit = await channel.fetch_message(msg_inscrit.id)
            inscrits = []
            for reaction in msg_inscrit.reactions:
                if str(reaction.emoji) == "⚔️":
                    async for user in reaction.users():
                        if not user.bot:
                            inscrits.append(user)

            if len(inscrits) < 2:
                await channel.send(embed=discord.Embed(description="❌ Pas assez de participants pour le tournoi (minimum 2) !", color=0xe74c3c))
                event_en_cours = False
                return

            # Créer salon temporaire
            salon_tournoi = await creer_salon_temp(guild, "⚔️・tournoi-qg")
            if salon_tournoi:
                try:
                    await salon_tournoi.send(embed=discord.Embed(
                        title="⚔️ TOURNOI DU QG",
                        description="Réagis ⚔️ pour t'inscrire ! Gagnant → +500p + 2pts amélio + 👑 Champion du QG",
                        color=0x3498db
                    ))
                except:
                    pass
            if salon_tournoi:
                pass
            if not salon_tournoi:
                salon_tournoi = channel

            _r.shuffle(inscrits)

            embed_bracket = discord.Embed(
                title="⚔️ BRACKET DU TOURNOI",
                description="\n".join([f"**{i+1}.** {u.display_name}" for i, u in enumerate(inscrits)]),
                color=0xe74c3c
            )
            await salon_tournoi.send(embed=embed_bracket)
            await asyncio.sleep(5)

            # Générer les matchs
            participants = inscrits.copy()
            tour = 1
            while len(participants) > 1:
                await salon_tournoi.send(embed=discord.Embed(
                    title=f"⚔️ Tour {tour}",
                    color=0xe74c3c
                ))
                gagnants = []
                _r.shuffle(participants)

                for i in range(0, len(participants) - 1, 2):
                    j1 = participants[i]
                    j2 = participants[i+1]

                    # Simuler un combat basé sur stats
                    uid1, uid2 = str(j1.id), str(j2.id)
                    s1 = arena_stats.get(uid1, {})
                    s2 = arena_stats.get(uid2, {})
                    score1 = (s1.get('atk_bonus',0) + s1.get('def_bonus',0)) * 10 + _r.randint(1, 100)
                    score2 = (s2.get('atk_bonus',0) + s2.get('def_bonus',0)) * 10 + _r.randint(1, 100)
                    gagnant = j1 if score1 > score2 else j2
                    perdant = j2 if score1 > score2 else j1

                    embed_match = discord.Embed(
                        description=f"⚔️ **{j1.display_name}** vs **{j2.display_name}**\n🏆 **{gagnant.display_name}** remporte le match !",
                        color=0xf1c40f
                    )
                    await salon_tournoi.send(embed=embed_match)
                    gagnants.append(gagnant)
                    await asyncio.sleep(3)

                # Si nombre impair le dernier passe directement
                if len(participants) % 2 == 1:
                    bye = participants[-1]
                    gagnants.append(bye)
                    await salon_tournoi.send(f"🎯 **{bye.display_name}** passe directement au tour suivant !")

                participants = gagnants
                tour += 1
                await asyncio.sleep(5)

            # Gagnant final
            champion = participants[0]
            uid_champ = str(champion.id)
            economy_data[uid_champ]['coins'] += 500
            points_amelio[uid_champ] = points_amelio.get(uid_champ, 0) + 2

            # Rôle Champion
            role_champ = await get_or_create_role(guild, "👑 Champion du QG", 0xf1c40f)
            if role_champ:
                try:
                    await champion.add_roles(role_champ)
                except:
                    pass

            embed_winner = discord.Embed(
                title="🏆 CHAMPION DU TOURNOI !",
                description=(
                    f"**{champion.display_name}** remporte le Tournoi du QG !\n\n"
                    f"💰 **+500 pièces**\n"
                    f"⚡ **+2 points d'amélioration**\n"
                    f"👑 Rôle **Champion du QG** attribué !"
                ),
                color=0xf1c40f
            )
            embed_winner.set_thumbnail(url=champion.display_avatar.url)
            await salon_tournoi.send(embed=embed_winner)
            await channel.send(embed=embed_winner)

            # Supprimer salon temp après 5 min
            if salon_tournoi != channel:
                asyncio.create_task(supprimer_salon_temp(salon_tournoi, 300))

        except Exception as e:
            print(f"Tournoi error: {e}")

    event_en_cours = False

# ── 💎 MINE D'OR ──────────────────────────────────────────────
async def lancer_mine_or(ctx=None):
    global event_en_cours
    event_en_cours = True
    for guild in bot.guilds:
        try:
            channel_event = get_event_channel(guild, ctx)
            if not channel_event: continue
            pepites_total = 500
            salon_mine = await creer_salon_temp(guild, "⛏️・mine-or")
            if salon_mine:
                try:
                    await salon_mine.send(embed=discord.Embed(
                        title="⛏️ MINE D'OR",
                        description="`.miner` toutes les 2min | 💎 1 pépite = 2p | 💀 Pépite maudite = tu perds tout ! ⏰ 20min",
                        color=0x3498db
                    ))
                except:
                    pass
            if salon_mine:
                pass
            if not salon_mine: salon_mine = channel_event
            malédiction_pos = _r.randint(50, pepites_total - 50)
            mine_actif[guild.id] = {
                "pepites": pepites_total,
                "joueurs": {},
                "malédiction": malédiction_pos,
                "total_extrait": 0,
                "channel_id": salon_mine.id,
                "finie": [False],
                "last_mine": {}
            }
            embed = discord.Embed(
                title="⛏️ LA MINE D'OR",
                description=(
                    "```\n"
                    "╔═══════════════════════════════╗\n"
                    f"║  💎  {pepites_total} PÉPITES DISPONIBLES  💎  ║\n"
                    "║  ─────────────────────────  ║\n"
                    "║  🪨🪨🪨💎🪨🪨💀🪨💎🪨🪨  ║\n"
                    "║     Quelque part là-dedans... ║\n"
                    "║     une pépite MAUDITE attend ║\n"
                    "╚═══════════════════════════════╝\n"
                    "```\n"
                    "`.miner` — extraire des pépites *(cooldown 2 min)*\n\n"
                    "💎 **1 pépite = 2 pièces** à la fin\n"
                    "💀 **Pépite maudite** = tu perds TOUT ce que tu as extrait\n\n"
                    f"⏰ **20 minutes** ou jusqu'à épuisement !"
                ),
                color=0xf1c40f
            )
            await salon_mine.send(embed=embed)
            await channel_event.send(embed=discord.Embed(
                description=f"⛏️ Une **Mine d'Or** vient d'apparaître dans {salon_mine.mention} ! Tapez `.miner` pour extraire !",
                color=0xf1c40f
            ))
            await asyncio.sleep(1200)
            data = mine_actif.get(guild.id, {})
            if data and not data.get("finie", [True])[0]:
                await _finaliser_mine(guild, salon_mine, data)
                data["finie"] = [True]
            if guild.id in mine_actif:
                del mine_actif[guild.id]
            if salon_mine != channel_event:
                asyncio.create_task(supprimer_salon_temp(salon_mine, 7, guild, "Mine d'Or"))
        except Exception as e:
            print(f"Mine or error: {e}")
    event_en_cours = False

# ── 🌙 VOLEUR DE MINUIT ────────────────────────────────────────

async def _finaliser_mine(guild, channel, data):
    joueurs = data.get("joueurs", {})
    if not joueurs:
        await channel.send(embed=discord.Embed(description="⛏️ Personne n'a miné... la mine s'effondre !", color=0x95a5a6))
        return

    desc = "⛏️ **Mine épuisée ! Résultats :**\n\n"
    for uid, pepites in sorted(joueurs.items(), key=lambda x: x[1], reverse=True):
        member = guild.get_member(int(uid))
        name = member.display_name if member else uid
        gains = pepites * 2  # 1 pépite = 2 pièces (pas trop broken)
        economy_data[uid]['coins'] += gains
        desc += f"⛏️ **{name}** — {pepites} pépites → **+{gains} pièces**\n"

    embed = discord.Embed(title="⛏️ Mine Épuisée !", description=desc, color=0xf1c40f)
    await channel.send(embed=embed)

# ── 🕵️ PARMI NOUS ─────────────────────────────────────────────
async def lancer_parminous(ctx=None):
    global event_en_cours
    event_en_cours = True

    for guild in bot.guilds:
        try:
            channel = get_event_channel(guild, ctx)
            if not channel: continue

            membres_actifs = [m for m in guild.members if not m.bot and str(m.id) in economy_data]
            if len(membres_actifs) < 4:
                await channel.send("❌ Pas assez de membres actifs pour Parmi Nous (minimum 4) !")
                event_en_cours = False
                return

            # Créer salon temporaire
            salon_jeu = await creer_salon_temp(guild, "🕵️・among-us-qg")
            if salon_jeu:
                try:
                    await salon_jeu.send(embed=discord.Embed(
                        title="🕵️ PARMI NOUS",
                        description="Imposteur (DM) → `.eliminer @joueur` | Innocent → `.voter @joueur` pour éliminer | ⏰ 5 minutes",
                        color=0x3498db
                    ))
                except:
                    pass
            if not salon_jeu: salon_jeu = channel

            imposteur = _r.choice(membres_actifs)
            innocents = [m for m in membres_actifs if m != imposteur]

            # MP à l'imposteur
            if elu == imp_id:
                embed_fin = discord.Embed(
                    title="✅ L'IMPOSTEUR A ÉTÉ TROUVÉ !",
                    description=f"**{imposteur.display_name}** était l'imposteur !\n\nTous les innocents reçoivent **+{reward} pièces** !\n🕵️ Rôle **Détective du QG** attribué !",
                    color=0x2ecc71
                )
            else:
                # Imposteur gagne — garde ses cartes
                cartes = game.get("cartes_volees", {}).get(imp_id, [])
                embed_fin = discord.Embed(
                    title="🔴 L'IMPOSTEUR S'EN EST SORTI !",
                    description=(
                        f"**{imposteur.display_name}** était l'imposteur et a survécu !\n"
                        f"Il garde **{len(cartes)} carte(s)** volée(s) !"
                    ),
                    color=0xe74c3c
                )

            await salon_jeu.send(embed=embed_fin)
            await channel.send(embed=embed_fin)

            if guild.id in parminous_game:
                del parminous_game[guild.id]

            if salon_jeu != channel:
                asyncio.create_task(supprimer_salon_temp(salon_jeu, 60))

        except Exception as e:
            print(f"Parmi nous error: {e}")

    event_en_cours = False

# ── ⚡ ENCHÈRES INTERDITES ─────────────────────────────────────
async def lancer_encheres(ctx=None):
    global event_en_cours
    event_en_cours = True
    for guild in bot.guilds:
        try:
            channel_event = get_event_channel(guild, ctx)
            if not channel_event: continue
            legendaires = [k for k in ANIME_CARDS_DB if k not in claimed_cards and ANIME_CARDS_DB[k]['rarete'] in ('Légendaire','Mythique')]
            if not legendaires:
                legendaires = [k for k in ANIME_CARDS_DB if k not in claimed_cards and ANIME_CARDS_DB[k]['rarete'] == 'Épique']
            if not legendaires:
                event_en_cours = False
                return
            carte_key = _r.choice(legendaires)
            c = ANIME_CARDS_DB[carte_key]
            r_emoji = RARETE_EMOJI.get(c['rarete'], '🟠')
            couleur = RARETE_COULEURS.get(c['rarete'], 0xe67e22)
            mises = {}
            salon_enc = await creer_salon_temp(guild, "⚡・encheres-qg")
            if salon_enc:
                try:
                    await salon_enc.send(embed=discord.Embed(
                        title="⚡ ENCHÈRES INTERDITES",
                        description="`.miser <montant>` pour enchérir | ⚠️ Même montant que quelqu'un = vous perdez tous les deux !",
                        color=0x3498db
                    ))
                except:
                    pass
            if salon_enc:
                pass
            if not salon_enc: salon_enc = channel_event
            encheres_actives[guild.id] = {"carte_key": carte_key, "mises": mises, "salon_id": salon_enc.id, "actif": True}
            embed_carte = discord.Embed(
                title="⚡ ENCHÈRES INTERDITES",
                description=(
                    f"{r_emoji} **{c['emoji']} {c['nom']}** — *{c['serie']}*\n\n"
                    f"❤️ **{c['pv']} PV** | ⚔️ **{c['attaque']} ATK** | 🛡️ **{c['defense']} DEF**\n\n"
                    "Tape `.miser <montant>` pour enchérir !\n"
                    "⚠️ Si **deux personnes misent le même montant** → les deux perdent leur mise et la carte disparaît !\n"
                    "⏰ **3 minutes** pour enchérir !"
                ),
                color=couleur
            )
            if c.get('image') and 'imgur' in c.get('image',''):
                embed_carte.set_image(url=c['image'])
            await salon_enc.send(embed=embed_carte)
            await channel_event.send(embed=discord.Embed(
                description=f"⚡ Les **Enchères Interdites** sont ouvertes dans {salon_enc.mention} !\nCarte en jeu : **{c['nom']}** {r_emoji}",
                color=couleur
            ))
            await asyncio.sleep(180)
            data = encheres_actives.get(guild.id, {})
            mises = data.get("mises", {})
            if not mises:
                await salon_enc.send(embed=discord.Embed(description="❌ Aucune mise — la carte disparaît !", color=0x95a5a6))
            else:
                montant_max = max(mises.values())
                gagnants = [uid for uid, m in mises.items() if m == montant_max]
                if len(gagnants) > 1:
                    for uid in gagnants:
                        economy_data[uid]['coins'] = max(0, economy_data[uid]['coins'] - montant_max)
                    noms = [f"<@{uid}>" for uid in gagnants]
                    await salon_enc.send(embed=discord.Embed(
                        title="💥 ÉGALITÉ FATALE !",
                        description=f"{' et '.join(noms)} ont misé **{montant_max:,}p** chacun !\nIls perdent leur mise et la carte disparaît !",
                        color=0xe74c3c
                    ))
                else:
                    winner_uid = gagnants[0]
                    economy_data[winner_uid]['coins'] = max(0, economy_data[winner_uid]['coins'] - montant_max)
                    claimed_cards[carte_key] = winner_uid
                    gacha_collections[winner_uid][carte_key] = {"fusion": 0}
                    winner_m = guild.get_member(int(winner_uid))
                    role_baron = await get_or_create_role(guild, "💰 Baron des Enchères", 0xf39c12)
                    if role_baron and winner_m:
                        try: await winner_m.add_roles(role_baron)
                        except: pass
                    await salon_enc.send(embed=discord.Embed(
                        title=f"🏆 <@{winner_uid}> remporte les enchères !",
                        description=f"**{c['nom']}** {r_emoji} adjugé pour **{montant_max:,} pièces** !\n💰 Rôle **Baron des Enchères** attribué !",
                        color=0x2ecc71
                    ))
            if guild.id in encheres_actives:
                del encheres_actives[guild.id]
            if salon_enc != channel_event:
                asyncio.create_task(supprimer_salon_temp(salon_enc, 7, guild, "Enchères Interdites"))
        except Exception as e:
            print(f"Enchères error: {e}")
    event_en_cours = False

# ── ⛏️ MINE D'OR ──────────────────────────────────────────────

async def lancer_voleur_minuit(ctx=None):
    global event_en_cours
    event_en_cours = True
    for guild in bot.guilds:
        try:
            channel_event = get_event_channel(guild, ctx)
            if not channel_event: continue
            membres = [m for m in guild.members if not m.bot and economy_data[str(m.id)]['coins'] > 0]
            if not membres:
                event_en_cours = False
                return
            voleur = _r.choice(membres)
            voleur_uid = str(voleur.id)
            try:
                await voleur.send(embed=discord.Embed(
                    title="🌙 Tu es Le Voleur de Minuit !",
                    description=(
                        "Chaque message que tu envoies cette nuit te rapporte des pièces volées !\n"
                        "Sois discret... tu seras révélé dans 1h !"
                    ),
                    color=0x2c2f33
                ))
            except: pass
            wanted_actif[guild.id] = {"voleur": voleur_uid, "total_vole": 0}
            embed = discord.Embed(
                title="🌙 NUIT DES VOLEURS",
                description=(
                    "Quelqu'un vole des pièces cette nuit...\n\n"
                    "*Des pièces disparaissent mystérieusement des coffres*\n\n"
                    "Le voleur sera révélé dans **1 heure** !"
                ),
                color=0x2c2f33
            )
            await channel_event.send(embed=embed)
            await asyncio.sleep(3600)
            data = wanted_actif.get(guild.id, {})
            total = data.get("total_vole", 0)
            embed_reveal = discord.Embed(
                title="🌅 Le Voleur est Révélé !",
                description=f"{voleur.mention} était **Le Voleur de Minuit** !\nIl a volé **{total} pièces** cette nuit 😈",
                color=0xe74c3c
            )
            embed_reveal.set_thumbnail(url=voleur.display_avatar.url)
            await channel_event.send(embed=embed_reveal)
            if guild.id in wanted_actif:
                del wanted_actif[guild.id]
        except Exception as e:
            print(f"Voleur minuit error: {e}")
    for guild in bot.guilds:
            try:
                ch = guild.get_channel(SALON_EVENT_ID) if SALON_EVENT_ID else guild.system_channel
                if ch:
                    await ch.send(embed=discord.Embed(
                        description="✅ **Voleur de Minuit** — le calme revient cette nuit. Merci d\'avoir participé 🎉",
                        color=0x2ecc71
                    ))
            except: pass
    event_en_cours = False

# ── 🎴 WANTED ─────────────────────────────────────────────────

async def lancer_wanted(ctx=None):
    global event_en_cours
    event_en_cours = True
    for guild in bot.guilds:
        try:
            channel_event = get_event_channel(guild, ctx)
            if not channel_event: continue
            salon_wanted = await creer_salon_temp(guild, "💀・wanted-qg")
            if salon_wanted:
                try:
                    await salon_wanted.send(embed=discord.Embed(
                        title="🎴 WANTED",
                        description="`.chasser @cible` pour capturer et gagner la prime ! 📈 Prime +100p/30min ⏰ 2 heures",
                        color=0x3498db
                    ))
                except:
                    pass
            if salon_wanted:
                pass
            if not salon_wanted: salon_wanted = channel_event
            membres = [m for m in guild.members if not m.bot]
            if not membres:
                event_en_cours = False
                return
            cible = _r.choice(membres)
            crime = _r.choice(CRIMES_FICTIFS)
            prime = _r.randint(500, 2000)
            embed = discord.Embed(
                title="💀 ─── AVIS DE RECHERCHE ───",
                description=(
                    "```\n"
                    "╔════════════════════════════════╗\n"
                    "║    ☠️  W A N T E D  ☠️         ║\n"
                    "║     ─ QG KDRAMA BUREAU ─       ║\n"
                    "╚════════════════════════════════╝\n"
                    "```\n"
                    f"👤 **{cible.display_name.upper()}** {cible.mention}\n\n"
                    f"📜 **CHEF D'ACCUSATION :**\n"
                    f"*{crime}*\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"💰 **PRIME : {prime:,} PIÈCES**\n"
                    f"*(+100p toutes les 30 min)*\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"🎯 `.chasser @{cible.display_name}` pour capturer !\n"
                    "⏰ **2 heures** avant expiration"
                ),
                color=0xc0392b
            )
            embed.set_thumbnail(url=cible.display_avatar.url)
            embed.set_footer(text="💀 QG Kdrama — Bureau des Chasseurs de Primes")
            wanted_actif[guild.id] = {
                "cible": str(cible.id),
                "prime": prime,
                "crime": crime,
                "salon": salon_wanted.id,
                "debut": __import__('time').time()
            }
            await salon_wanted.send(embed=embed)
            await channel_event.send(embed=discord.Embed(
                description=f"💀 Un **Avis de Recherche** est apparu dans {salon_wanted.mention} !\n{cible.mention} est recherché — Prime : **{prime:,} pièces** !",
                color=0xc0392b
            ))
            for _ in range(4):
                await asyncio.sleep(1800)
                if guild.id not in wanted_actif: break
                wanted_actif[guild.id]['prime'] += 100
                new_prime = wanted_actif[guild.id]['prime']
                await salon_wanted.send(embed=discord.Embed(
                    description=f"📈 La prime sur {cible.mention} monte à **{new_prime:,} pièces** !",
                    color=0xf39c12
                ))
            if guild.id in wanted_actif:
                await salon_wanted.send(embed=discord.Embed(
                    description=f"⏰ L'Avis de Recherche expire — {cible.mention} s'échappe ! La prime disparaît.",
                    color=0x95a5a6
                ))
                del wanted_actif[guild.id]
            if salon_wanted != channel_event:
                asyncio.create_task(supprimer_salon_temp(salon_wanted, 7, guild, "Wanted"))
        except Exception as e:
            print(f"Wanted error: {e}")
    event_en_cours = False

# ── 🌙 RÊVE COLLECTIF ─────────────────────────────────────────

async def lancer_fausse_rumeur(ctx=None):
    global event_en_cours
    event_en_cours = True
    rumeurs = [
        "🚨 BREAKING : Les cartes Mythique vont être supprimées dans 1 heure !",
        "🚨 BREAKING : Le bot va reset toutes les pièces dans 30 minutes !",
        "🚨 BREAKING : Les rolls vont coûter 500 pièces à partir de maintenant !",
        "🚨 BREAKING : Le serveur va fermer définitivement ce soir à minuit !",
        "🚨 BREAKING : Une nouvelle rareté au-dessus de Mythique vient d'être ajoutée — payante !",
    ]
    for guild in bot.guilds:
        try:
            channel_event = get_event_channel(guild, ctx)
            if not channel_event: continue
            rumeur = _r.choice(rumeurs)
            douteurs = {}  # uid: True — secret, pas visible
            embed = discord.Embed(
                title="📰 ANNONCE OFFICIELLE",
                description=(
                    f"{rumeur}\n\n"
                    "*Vous avez 60 secondes pour réagir...*\n\n"
                    "Si tu penses que c'est un **mensonge** tape `.jedoute` !"
                ),
                color=0xe74c3c
            )
            await channel_event.send("@everyone", embed=embed)
            # Stocker la rumeur active pour jedoute
            import time as _t
            fausse_rumeur_active[guild.id] = {"douteurs": douteurs, "debut": _t.time()}
            await asyncio.sleep(60)
            # Révélation
            nb_douteurs = len(douteurs)
            gains = 150
            desc = (
                f"😂 **C'ÉTAIT UNE FAUSSE RUMEUR !**\n\n"
                f"*{rumeur}*\n\n"
                f"**{nb_douteurs} membre(s)** ont gardé leur calme et reçoivent **+{gains} pièces** !\n"
            )
            if douteurs:
                mentions = " ".join([f"<@{uid}>" for uid in douteurs.keys()])
                desc += f"\n🧠 Bravo : {mentions}"
            await channel_event.send(embed=discord.Embed(
                title="📰 RÉVÉLATION", description=desc, color=0x2ecc71
            ))
            if guild.id in fausse_rumeur_active:
                del fausse_rumeur_active[guild.id]
        except Exception as e:
            print(f"Fausse rumeur error: {e}")
    event_en_cours = False

# ── ⚡ ENCHÈRES INTERDITES ─────────────────────────────────────

async def lancer_reve_collectif(ctx=None):
    global event_en_cours
    event_en_cours = True
    reves = [
        "Tu te retrouves dans le monde de Demon Slayer mais tout le monde parle de kdrama coréen...",
        "Gojo et Luffy ont ouvert un restaurant de ramen mais Naruto a mangé tout le stock...",
        "Tu es dans Soul Society mais les Shinigami font des battle rap au lieu de se battre...",
        "L'équipage du Chapeau de Paille a trouvé le One Piece... c'est une clé USB avec tous les épisodes de Bleach...",
        "Saitama cherche un adversaire fort mais tous les méchants veulent juste son autographe...",
    ]
    for guild in bot.guilds:
        try:
            channel_event = get_event_channel(guild, ctx)
            if not channel_event: continue
            salon_reve = await creer_salon_temp(guild, "🌙・reve-collectif")
            if salon_reve:
                try:
                    await salon_reve.send(embed=discord.Embed(
                        title="🌙 RÊVE COLLECTIF",
                        description="Continue l'histoire ! 👍 Like les messages | 🏆 Le plus liké → Roi de la Narration ⏰ 5min",
                        color=0x3498db
                    ))
                except:
                    pass
            if salon_reve:
                pass
            if not salon_reve: salon_reve = channel_event
            reve = _r.choice(reves)
            embed = discord.Embed(
                title="🌙 RÊVE COLLECTIF",
                description=(
                    f"*Tout le monde s'endort...*\n\n"
                    f"💭 **{reve}**\n\n"
                    "Continuez l'histoire dans ce salon !\n"
                    "Le message le plus **liké** gagne le rôle **Roi de la Narration** !\n"
                    "⏰ **5 minutes** pour écrire !"
                ),
                color=0x9b59b6
            )
            await salon_reve.send(embed=embed)
            await channel_event.send(embed=discord.Embed(
                description=f"🌙 Le **Rêve Collectif** commence dans {salon_reve.mention} ! Continuez l'histoire !",
                color=0x9b59b6
            ))
            await asyncio.sleep(300)
            best_msg = None
            best_likes = 0
            async for msg in salon_reve.history(limit=50):
                if msg.author.bot: continue
                total = sum(r.count for r in msg.reactions)
                if total > best_likes:
                    best_likes = total
                    best_msg = msg
            if best_msg:
                role_narr = await get_or_create_role(guild, "🌙 Roi de la Narration", 0x9b59b6)
                if role_narr:
                    try: await best_msg.author.add_roles(role_narr)
                    except: pass
                await salon_reve.send(embed=discord.Embed(
                    title="🌙 Fin du Rêve !",
                    description=f"{best_msg.author.mention} a écrit la meilleure suite et reçoit le rôle **Roi de la Narration** ! 👑",
                    color=0x9b59b6
                ))
            if salon_reve != channel_event:
                asyncio.create_task(supprimer_salon_temp(salon_reve, 7, guild, "Rêve Collectif"))
        except Exception as e:
            print(f"Rêve collectif error: {e}")
    event_en_cours = False

# ── 🎩 LE MAGICIEN ────────────────────────────────────────────

async def lancer_magicien(ctx=None):
    global event_en_cours
    event_en_cours = True
    for guild in bot.guilds:
        try:
            channel_event = get_event_channel(guild, ctx)
            if not channel_event: continue
            membres = [m for m in guild.members if not m.bot]
            if not membres:
                event_en_cours = False
                return
            magicien = _r.choice(membres)
            # Créer salon privé visible uniquement par le magicien
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                magicien: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            }
            try:
                salon_mag = await guild.create_text_channel("🎩・salon-du-magicien", overwrites=overwrites)
            except:
                salon_mag = None
            if salon_mag:
                try:
                    await salon_mag.send(embed=discord.Embed(
                        title="🎩 TU ES LE MAGICIEN",
                        description="`.sort double @joueur` `.sort bloquer @joueur` `.sort troll @joueur` | 3 sorts anonymes !",
                        color=0x3498db
                    ))
                except:
                    pass
            # Créer salon privé visible uniquement par le magicien
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                magicien: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            }
            try:
                salon_mag = await guild.create_text_channel("🎩・salon-du-magicien", overwrites=overwrites)
            except:
                salon_mag = None
            magicien_actif[guild.id] = {
                "magicien": str(magicien.id),
                "sorts_restants": 3,
                "sorts_lances": [],
                "salon": salon_mag.id if salon_mag else None
            }
            if salon_mag:
                pass
                await salon_mag.send(embed=discord.Embed(
                    title="🎩 Bienvenue, Magicien !",
                    description=(
                        f"{magicien.mention} tu as **3 sorts** à lancer anonymement !\n\n"
                        "`.sort double @joueur` — Doubler ses pièces\n"
                        "`.sort bloquer @joueur` — Bloquer ses commandes 30min\n"
                        "`.sort troll @joueur` — Lui donner une carte Commune nulle\n\n"
                        "Mentionne directement le membre ici — personne ne voit ce salon !\n"
                        "⏰ **30 minutes** — Sois stratégique 😈"
                    ),
                    color=0x9b59b6
                ))
            await channel_event.send(embed=discord.Embed(
                title="🎩 LE MAGICIEN",
                description=(
                    "Un **Magicien mystérieux** rôde sur le serveur !\n\n"
                    "Il peut lancer **3 sorts anonymes** sur n'importe quel membre :\n"
                    "✨ Doubler des pièces\n"
                    "🔒 Bloquer des commandes\n"
                    "🃏 Donner une carte troll\n\n"
                    "Il sera révélé dans **30 minutes** !"
                ),
                color=0x9b59b6
            ))
            await asyncio.sleep(1800)
            data = magicien_actif.get(guild.id, {})
            sorts = data.get("sorts_lances", [])
            desc_sorts = "\n".join([f"• `{s['type']}` sur {s['cible']}" for s in sorts]) if sorts else "Aucun sort lancé..."
            embed_reveal = discord.Embed(
                title=f"🎩 Le Magicien était {magicien.mention} !",
                description=f"**Sorts lancés :**\n{desc_sorts}",
                color=0x9b59b6
            )
            embed_reveal.set_thumbnail(url=magicien.display_avatar.url)
            role_mag = await get_or_create_role(guild, "🎩 Grand Magicien", 0x9b59b6)
            if role_mag:
                try: await magicien.add_roles(role_mag)
                except: pass
            await channel_event.send(embed=embed_reveal)
            if guild.id in magicien_actif:
                del magicien_actif[guild.id]
            if salon_mag:
                pass
                asyncio.create_task(supprimer_salon_temp(salon_mag, 7, guild, "Le Magicien"))
        except Exception as e:
            print(f"Magicien error: {e}")
    event_en_cours = False

# ── 🤡 LE CLOWN ───────────────────────────────────────────────

async def lancer_clown(ctx=None):
    global event_en_cours
    event_en_cours = True
    for guild in bot.guilds:
        try:
            channel_event = get_event_channel(guild, ctx)
            if not channel_event: continue
            membres = [m for m in guild.members if not m.bot]
            if not membres:
                event_en_cours = False
                return
            clown = _r.choice(membres)
            clown_actif[guild.id] = str(clown.id)
            role_clown = await get_or_create_role(guild, "🤡 Clown du QG", 0xff6b9d)
            if role_clown:
                try: await clown.add_roles(role_clown)
                except: pass
            embed = discord.Embed(
                title="🤡 LE CLOWN DU QG",
                description=(
                    f"{clown.mention} a été désigné **Clown du QG** !\n\n"
                    "Tout ce qu'il dit sera répété par le bot en version ridicule 🤡\n\n"
                    f"Il peut se libérer si quelqu'un répond à un de ses messages avec 😂 !\n"
                    "⏰ **30 minutes** maximum !"
                ),
                color=0xff6b9d
            )
            await channel_event.send(embed=embed)
            await asyncio.sleep(1800)
            if guild.id in clown_actif:
                del clown_actif[guild.id]
                if role_clown:
                    try: await clown.remove_roles(role_clown)
                    except: pass
                await channel_event.send(embed=discord.Embed(
                    description=f"🤡 {clown.mention} est enfin libéré de sa malédiction de Clown !",
                    color=0x95a5a6
                ))
        except Exception as e:
            print(f"Clown error: {e}")
    event_en_cours = False

# ── 🔮 ORACLE MAUDIT ──────────────────────────────────────────

async def lancer_canard(ctx=None):
    """Alias pour compatibilité — lance le Corbeau"""
    await lancer_corbeau(ctx)

async def lancer_corbeau(ctx=None):
    global event_en_cours
    event_en_cours = True
    humeurs = [
        {"nom": "généreux", "desc": "Il ramène des **pièces** à son propriétaire 💰"},
        {"nom": "voleur",   "desc": "Il vole des **pièces** aux autres membres 😈"},
        {"nom": "sage",     "desc": "Il apporte de l\'**XP** à son propriétaire ⭐"},
        {"nom": "mystique", "desc": "Il peut rapporter un **point d\'amélioration** 💎"},
        {"nom": "grognon",  "desc": "Il vole des **pièces** à son propriétaire 😤"},
    ]
    for guild in bot.guilds:
        try:
            channel = get_event_channel(guild, ctx)
            if not channel: continue
            humeur = _r.choice(humeurs)
            canard_actif[guild.id] = {"proprio": None, "humeur": humeur["nom"], "adopte": False}

            embed = discord.Embed(
                title="🐦‍⬛ UN CORBEAU APPARAÎT !",
                description=(
                    "```\n"
                    "╔═══════════════════════════════╗\n"
                    "║   🦅  C O R B E A U  🦅       ║\n"
                    "║  ─────────────────────────  ║\n"
                    "║  Il observe... il attend...  ║\n"
                    "╚═══════════════════════════════╝\n"
                    "```\n"
                    f"Humeur : **{humeur['nom']}** — {humeur['desc']}\n\n"
                    "`.adopter` — Prendre le corbeau\n"
                    "`.nourrir` — Nourrir *(améliore son humeur)*\n"
                    "`.caresser` — Caresser *(crée un lien)*\n"
                    "`.recup` — Récupérer ce qu\'il a ramené\n\n"
                    "⏰ Il disparaît dans **20 minutes** !"
                ),
                color=0x2c2f33
            )
            await channel.send("@everyone", embed=embed)

            # Effets toutes les 5 min
            for tick in range(4):
                await asyncio.sleep(300)
                data = canard_actif.get(guild.id, {})
                if not data or not data.get("proprio"):
                    continue
                proprio_id = data["proprio"]
                proprio = guild.get_member(int(proprio_id))
                if not proprio: continue
                humeur_nom = data["humeur"]

                if humeur_nom == "généreux":
                    gain = _r.randint(50, 150)
                    data["reserve"] = data.get("reserve", 0) + gain
                    await channel.send(f"🐦‍⬛ Le corbeau de {proprio.mention} est parti en chasse... il rapporte **{gain} pièces** en réserve ! `.recup` pour les récupérer")

                elif humeur_nom == "voleur":
                    victimes = [m for m in guild.members if not m.bot and str(m.id) != proprio_id and economy_data[str(m.id)]['coins'] > 20]
                    if victimes:
                        v = _r.choice(victimes)
                        vol = _r.randint(30, 100)
                        economy_data[str(v.id)]['coins'] = max(0, economy_data[str(v.id)]['coins'] - vol)
                        data["reserve"] = data.get("reserve", 0) + vol
                        await channel.send(f"🐦‍⬛ Le corbeau de {proprio.mention} a volé **{vol} pièces** à {v.mention} ! `.recup` pour les récupérer 😈")

                elif humeur_nom == "sage":
                    xp_gain = _r.randint(20, 60)
                    data["reserve_xp"] = data.get("reserve_xp", 0) + xp_gain
                    await channel.send(f"🐦‍⬛ Le corbeau de {proprio.mention} médite... **+{xp_gain} XP** en réserve ! `.recup` pour récupérer")

                elif humeur_nom == "mystique":
                    if tick == 3 and _r.random() < 0.3:  # 30% chance au dernier tick
                        data["reserve_amelio"] = 1
                        await channel.send(f"🐦‍⬛ Le corbeau de {proprio.mention} revient avec quelque chose de rare... 💎 `.recup` vite !")

                elif humeur_nom == "grognon":
                    vol = _r.randint(20, 80)
                    economy_data[proprio_id]['coins'] = max(0, economy_data[proprio_id]['coins'] - vol)
                    await channel.send(f"🐦‍⬛ Le corbeau de {proprio.mention} est de mauvaise humeur... **-{vol} pièces** 😤")

            # Fin de l'event
            data = canard_actif.get(guild.id, {})
            if data and data.get("proprio"):
                proprio = guild.get_member(int(data["proprio"]))
                await channel.send(embed=discord.Embed(
                    description=f"🐦‍⬛ Le corbeau de {proprio.mention if proprio else '???'} s\'envole... Tape `.recup` pour récupérer ses derniers dons !",
                    color=0x95a5a6
                ))
            else:
                await channel.send(embed=discord.Embed(description="🐦‍⬛ Le corbeau repart sans avoir été adopté...", color=0x95a5a6))

            await asyncio.sleep(60)
            if guild.id in canard_actif:
                del canard_actif[guild.id]

        except Exception as e:
            print(f"Corbeau error: {e}")
    event_en_cours = False


async def lancer_event_pacifiste(ctx=None):
    global event_en_cours
    event_en_cours = True

    for guild in bot.guilds:
        try:
            channel = get_event_channel(guild, ctx)
            if not channel: continue

            embed = discord.Embed(
                title="🌈 EVENT PACIFISTE",
                description=(
                    "Pendant **1 heure** — paix totale sur le serveur !\n\n"
                    "❌ Aucun combat, vol, sabotage ou item PvP\n"
                    "✅ Chaque message = **+2 pièces** automatiquement\n"
                    "✅ Chaque message = **+3 XP** automatiquement\n\n"
                    "Test de patience pour les plus agressifs 😄"
                ),
                color=0x2ecc71
            )
            await channel.send("@everyone", embed=embed)

            # Activer le mode pacifiste
            global double_xp_event_actif
            double_xp_event_actif = True

            await asyncio.sleep(3600)

            double_xp_event_actif = False
            await channel.send(embed=discord.Embed(
                description="🌈 L'Event Pacifiste est terminé ! Les hostilités peuvent reprendre 😈",
                color=0x95a5a6
            ))

        except Exception as e:
            print(f"Pacifiste error: {e}")

    event_en_cours = False

# ── 🔮 ORACLE MAUDIT ──────────────────────────────────────────
async def lancer_oracle_maudit(ctx=None):
    global event_en_cours
    event_en_cours = True
    for guild in bot.guilds:
        try:
            channel_event = get_event_channel(guild, ctx)
            if not channel_event: continue
            membres_actifs = [m for m in guild.members if not m.bot and str(m.id) in economy_data]
            embed = discord.Embed(
                title="🔮 L'ORACLE MAUDIT",
                description=(
                    "L'Oracle a des visions sombres...\n\n"
                    "Il prédit l'avenir de chaque membre actif — les prophéties **deviendront réalité** dans les 2h qui suivent !\n\n"
                    "*Les destinées sont scellées...*"
                ),
                color=0x9b59b6
            )
            await channel_event.send(embed=embed)
            await asyncio.sleep(3)
            for membre in membres_actifs[:8]:
                prophecy = _r.choice(PROPHECIES)
                oracle_prophecies[str(membre.id)] = prophecy
                await channel_event.send(embed=discord.Embed(
                    description=f"🔮 {membre.mention} — *{prophecy}*",
                    color=0x9b59b6
                ))
                await asyncio.sleep(2)
            await asyncio.sleep(7200)
            oracle_prophecies.clear()
            await channel_event.send(embed=discord.Embed(
                description="🔮 Les prophéties de l'Oracle sont accomplies... le voile se lève.",
                color=0x95a5a6
            ))
        except Exception as e:
            print(f"Oracle error: {e}")
    for guild in bot.guilds:
            try:
                ch = guild.get_channel(SALON_EVENT_ID) if SALON_EVENT_ID else guild.system_channel
                if ch:
                    await ch.send(embed=discord.Embed(
                        description="✅ **Oracle Maudit** — les prophéties s'accomplissent... Merci d\'avoir participé 🎉",
                        color=0x2ecc71
                    ))
            except: pass
    event_en_cours = False

# ── 🌑 LE PACTE ───────────────────────────────────────────────

async def lancer_pacte(ctx=None):
    global event_en_cours
    event_en_cours = True
    for guild in bot.guilds:
        try:
            channel_event = get_event_channel(guild, ctx)
            if not channel_event: continue
            membres = [m for m in guild.members if not m.bot and str(m.id) in economy_data]
            if len(membres) < 2:
                event_en_cours = False
                return
            _r.shuffle(membres)
            paires = [(membres[i], membres[i+1]) for i in range(0, len(membres)-1, 2)]
            desc_paires = ""
            for a, b in paires:
                desc_paires += f"🔗 {a.mention} ↔️ {b.mention}\n"
            embed = discord.Embed(
                title="🌑 LE PACTE",
                description=(
                    "Des membres ont été liés par un pacte mystérieux !\n\n"
                    "Pendant **2 heures** leurs économies sont **fusionnées** :\n"
                    "Ce que l'un gagne → l'autre gagne aussi\n"
                    "Ce que l'un perd → l'autre perd aussi\n\n"
                    f"**Paires liées :**\n{desc_paires}\n"
                    "Coopérez... ou sabotez-vous mutuellement 😈"
                ),
                color=0x2c3e50
            )
            await channel_event.send(embed=embed)
            pacte_actif[guild.id] = [(str(a.id), str(b.id)) for a, b in paires]
            for a, b in paires:
                try:
                    await a.send(f"🌑 Tu es lié à {b.mention} — ce qu'il/elle gagne tu le gagnes, ce qu'il/elle perd tu le perds !")
                    await b.send(f"🌑 Tu es lié à {a.mention} — ce qu'il/elle gagne tu le gagnes, ce qu'il/elle perd tu le perds !")
                except: pass
            await asyncio.sleep(7200)
            if guild.id in pacte_actif:
                del pacte_actif[guild.id]
            await channel_event.send(embed=discord.Embed(
                description="🌑 Le Pacte prend fin... les liens se brisent.",
                color=0x95a5a6
            ))
        except Exception as e:
            print(f"Pacte error: {e}")
    event_en_cours = False

# ── 🎪 FESTIVAL DES LOSERS ────────────────────────────────────

async def lancer_festival_losers(ctx=None):
    global event_en_cours
    event_en_cours = True
    for guild in bot.guilds:
        try:
            channel_event = get_event_channel(guild, ctx)
            if not channel_event: continue
            eligibles = [
                m for m in guild.members
                if not m.bot and economy_data[str(m.id)]['coins'] < 500
            ]
            if not eligibles:
                await channel_event.send(embed=discord.Embed(
                    description="🎪 Festival des Losers annulé — tout le monde est trop riche ! 😄",
                    color=0x95a5a6
                ))
                event_en_cours = False
                return
            mentions = " ".join([m.mention for m in eligibles[:10]])
            embed = discord.Embed(
                title="🎪 FESTIVAL DES LOSERS",
                description=(
                    f"**{len(eligibles)} membres** sont éligibles !\n\n"
                    "Condition : moins de **500 pièces**\n\n"
                    f"**Participants :** {mentions}\n\n"
                    "Chaque éligible reçoit des **pièces bonus**, de l'**XP** et ses **rolls rechargés** !\n"
                    "Les riches ne peuvent pas interférer 😄"
                ),
                color=0xf1c40f
            )
            await channel_event.send(embed=embed)
            for membre in eligibles:
                uid = str(membre.id)
                bonus_pieces = _r.randint(300, 800)
                bonus_xp = _r.randint(50, 150)
                economy_data[uid]['coins'] += bonus_pieces
                xp_data[uid]['xp'] += bonus_xp
                gacha_cooldowns[uid] = 0
                try:
                    await membre.send(embed=discord.Embed(
                        title="🎪 Festival des Losers !",
                        description=f"Tu es éligible ! **+{bonus_pieces} pièces**, **+{bonus_xp} XP** et rolls rechargés !",
                        color=0xf1c40f
                    ))
                except: pass
        except Exception as e:
            print(f"Festival losers error: {e}")
    for guild in bot.guilds:
            try:
                ch = guild.get_channel(SALON_EVENT_ID) if SALON_EVENT_ID else guild.system_channel
                if ch:
                    await ch.send(embed=discord.Embed(
                        description="✅ **Festival des Losers** terminé — remontez la pente ! Merci d\'avoir participé 🎉",
                        color=0x2ecc71
                    ))
            except: pass
    event_en_cours = False

# ── 🧩 PUZZLE COLLECTIF ───────────────────────────────────────

async def lancer_puzzle_collectif(ctx=None):
    global event_en_cours
    event_en_cours = True
    for guild in bot.guilds:
        try:
            channel_event = get_event_channel(guild, ctx)
            if not channel_event: continue
            epiques = [k for k in ANIME_CARDS_DB if k not in claimed_cards and ANIME_CARDS_DB[k]['rarete'] == 'Épique']
            if not epiques:
                event_en_cours = False
                return
            carte_key = _r.choice(epiques)
            c = ANIME_CARDS_DB[carte_key]
            salon_puzzle = await creer_salon_temp(guild, "🧩・puzzle-collectif")
            if salon_puzzle:
                try:
                    await salon_puzzle.send(embed=discord.Embed(
                        title="🧩 PUZZLE COLLECTIF",
                        description="Indices toutes les 2min → tape le nom ! 🏆 Plus de points = claim la carte Épique !",
                        color=0x3498db
                    ))
                except:
                    pass
            if salon_puzzle:
                pass
            if not salon_puzzle: salon_puzzle = channel_event
            scores_puzzle = {}
            puzzle_actif[guild.id] = {"carte_key": carte_key, "scores": scores_puzzle, "fragment": 0, "actif": True}
            embed_annonce = discord.Embed(
                title="🧩 PUZZLE COLLECTIF",
                description=(
                    f"Un personnage mystérieux est caché dans {salon_puzzle.mention} !\n\n"
                    "Des fragments vont apparaître toutes les **2 minutes**\n"
                    "Premier à trouver le nom à chaque fragment gagne des points !\n"
                    "Celui avec le plus de points **claim la carte Épique** !"
                ),
                color=0x9b59b6
            )
            await channel_event.send(embed=embed_annonce)
            await salon_puzzle.send(embed=discord.Embed(
                title="🧩 PUZZLE — Trouvez le personnage !",
                description="Les indices arrivent... préparez-vous !",
                color=0x9b59b6
            ))
            indices = [
                f"Ce personnage vient de la série **{c['serie']}**",
                f"Sa rareté est **{c['rarete']}**",
                f"Il a **{c['pv']} PV** et **{c['attaque']} ATK**",
                f"Son emoji est **{c['emoji']}**",
                f"Son nom commence par **{c['nom'][0].upper()}**",
                f"Son nom fait **{len(c['nom'])} lettres**",
                f"Son nom contient **{c['nom'][len(c['nom'])//2].upper()}**",
                f"Les 2 premières lettres sont **{c['nom'][:2].upper()}**",
                f"Les 3 premières lettres sont **{c['nom'][:3].upper()}**",
                f"*DERNIER INDICE* — commence par **{c['nom'][:4].upper()}**",
            ]
            already_found = False
            for i, indice in enumerate(indices):
                if already_found: break
                embed_indice = discord.Embed(
                    title=f"🧩 Fragment {i+1}/10",
                    description=f"{indice}\n\nTape le nom du personnage dans ce salon !",
                    color=0x9b59b6
                )
                await salon_puzzle.send(embed=embed_indice)
                def check_puzzle(m, ch=salon_puzzle):
                    return not m.author.bot and m.channel == ch
                try:
                    rep = await bot.wait_for("message", timeout=120.0, check=check_puzzle)
                    if c['nom'].lower() in rep.content.lower():
                        uid = str(rep.author.id)
                        scores_puzzle[uid] = scores_puzzle.get(uid, 0) + (10 - i)
                        await salon_puzzle.send(f"✅ {rep.author.mention} trouve ! **+{10-i} points** !")
                        already_found = True
                    else:
                        await salon_puzzle.send(f"❌ Pas tout à fait... prochain indice dans 2 min !", delete_after=10)
                except asyncio.TimeoutError:
                    await salon_puzzle.send(f"⏰ Personne n'a trouvé ce fragment...")
            if scores_puzzle:
                winner_uid = max(scores_puzzle, key=scores_puzzle.get)
                winner = guild.get_member(int(winner_uid))
                claimed_cards[carte_key] = winner_uid
                gacha_collections[winner_uid][carte_key] = {"fusion": 0}
                r_emoji = RARETE_EMOJI.get(c['rarete'], '🟣')
                role_puzzle = await get_or_create_role(guild, "🧩 Maître du Puzzle", 0x9b59b6)
                if role_puzzle and winner:
                    try: await winner.add_roles(role_puzzle)
                    except: pass
                await salon_puzzle.send(embed=discord.Embed(
                    title=f"🧩 C'était {c['nom']} !",
                    description=f"{winner.mention if winner else winner_uid} remporte **{c['nom']}** {r_emoji} avec **{scores_puzzle[winner_uid]} points** !\n🧩 Rôle **Maître du Puzzle** attribué !",
                    color=0x2ecc71
                ))
            if guild.id in puzzle_actif:
                del puzzle_actif[guild.id]
            if salon_puzzle != channel_event:
                asyncio.create_task(supprimer_salon_temp(salon_puzzle, 7, guild, "Puzzle Collectif"))
        except Exception as e:
            print(f"Puzzle error: {e}")
    event_en_cours = False

# ── 🌊 VAGUE DE LÉGENDES ──────────────────────────────────────

async def lancer_vague_legendaires(ctx=None):
    global event_en_cours
    event_en_cours = True
    for guild in bot.guilds:
        try:
            channel_event = get_event_channel(guild, ctx)
            channel_gacha = guild.get_channel(SALON_GACHA_ID) if SALON_GACHA_ID else channel_event
            if not channel_event: continue
            legendaires = [k for k in ANIME_CARDS_DB if k not in claimed_cards and ANIME_CARDS_DB[k]['rarete'] in ('Légendaire', 'Mythique')]
            if len(legendaires) < 5:
                event_en_cours = False
                return
            _r.shuffle(legendaires)
            cartes_vague = legendaires[:10]
            embed_annonce = discord.Embed(
                title="🌊 VAGUE DE LÉGENDES",
                description=(
                    "```\n"
                    "╔════════════════════════════════════╗\n"
                    "║  🌊  VAGUE DE LÉGENDES  🌊  ║\n"
                    "║  ──────────────────────────────  ║\n"
                    "║    10 CARTES EN 10 MINUTES !      ║\n"
                    "║    Une toutes les 25 secondes     ║\n"
                    "╚════════════════════════════════════╝\n"
                    "```\n"
                    f"Rendez-vous dans {channel_gacha.mention} !\n\n"
                    "⚡ Annoncée **10 secondes avant** chaque drop\n"
                    "❤️ **25 secondes** pour claim — pas de seconde chance !"
                ),
                color=0xf1c40f
            )
            await channel_event.send("<@&1484584133513580605>", embed=embed_annonce)
            await asyncio.sleep(10)
            for i, carte_key in enumerate(cartes_vague):
                if carte_key in claimed_cards: continue
                c = ANIME_CARDS_DB[carte_key]
                r_emoji = RARETE_EMOJI.get(c['rarete'], '🟠')
                await channel_gacha.send(embed=discord.Embed(
                    description=f"⚡ **Dans 10 secondes** — {c['emoji']} **{c['nom']}** {r_emoji} !",
                    color=0xf39c12
                ))
                await asyncio.sleep(10)
                if carte_key in claimed_cards: continue
                couleur = RARETE_COULEURS.get(c['rarete'], 0xf1c40f)
                embed_carte = discord.Embed(
                    title=f"{c['emoji']} {c['nom']}",
                    description=f"*{c['serie']}* {r_emoji} **{c['rarete']}**\n\n❤️ **{c['pv']} PV** | ⚔️ **{c['attaque']} ATK** | 🛡️ **{c['defense']} DEF**\n\nRéagis ❤️ pour claim !",
                    color=couleur
                )
                if c.get('image') and 'imgur' in c.get('image',''):
                    embed_carte.set_image(url=c['image'])
                embed_carte.set_footer(text="⚡ 25 secondes pour claim !")
                msg = await channel_gacha.send(embed=embed_carte)
                await msg.add_reaction("❤️")
                def check_vague(r, u, k=carte_key):
                    return str(r.emoji) == "❤️" and r.message.id == msg.id and not u.bot
                try:
                    reaction, claimer = await bot.wait_for("reaction_add", timeout=25.0, check=check_vague)
                    if carte_key not in claimed_cards:
                        claimed_cards[carte_key] = str(claimer.id)
                        gacha_collections[str(claimer.id)][carte_key] = {"fusion": 0}
                        await channel_gacha.send(f"✅ {claimer.mention} claim **{c['nom']}** {r_emoji} !")
                except asyncio.TimeoutError:
                    await channel_gacha.send(f"⏰ **{c['nom']}** n'a pas été claimé...")
                if i < len(cartes_vague) - 1:
                    await asyncio.sleep(5)
            await channel_event.send(embed=discord.Embed(
                description="🌊 La Vague de Légendes est terminée ! Merci d'avoir participé 🎉",
                color=0x95a5a6
            ))
        except Exception as e:
            print(f"Vague légendaires error: {e}")
    event_en_cours = False

# ── 👾 BOSS FINAL ─────────────────────────────────────────────

async def lancer_boss_final(ctx=None):
    global event_en_cours
    event_en_cours = True
    repliques_moquerie = [
        "C'est tout ce que t'as ? Mon grand-mère frappe plus fort ! 😂",
        "Pitoyable... J'ai dormi pendant tout ça.",
        "Tu appelles ça une attaque ? Rentrez chez vous.",
        "Je bâille d'ennui... Quelqu'un de sérieux ?",
    ]
    repliques_fort = [
        "Tiens tiens... enfin quelqu'un qui mérite mon attention.",
        "Pas mal... mais c'est pas suffisant.",
        "Je commence à sentir quelque chose... de la DOULEUR ? Non impossible.",
    ]
    repliques_contreattaque = [
        "Tu croyais que j'allais rester sans répondre ?",
        "Mon tour. Profites-en pour compter tes pièces...",
        "Leçon : ne jamais frapper un boss sans s'attendre à une réponse.",
    ]
    for guild in bot.guilds:
        try:
            channel_event = get_event_channel(guild, ctx)
            if not channel_event: continue
            salon_boss = await creer_salon_temp(guild, "👾・boss-final")
            if salon_boss:
                try:
                    await salon_boss.send(embed=discord.Embed(
                        title="👾 BOSS FINAL",
                        description="`.attaquerboss` pour attaquer ! ⚠️ Le boss contre-attaque | 🏆 Coup de grâce → Pourfendeur de Boss",
                        color=0x3498db
                    ))
                except:
                    pass
            if salon_boss:
                pass
            if not salon_boss: salon_boss = channel_event
            boss = _r.choice(BOSS_INVASIONS).copy()
            pv_boss = boss['pv'] * 2
            invasion_active[guild.id] = {**boss, "pv": pv_boss, "max_pv": pv_boss, "attaquants": {}, "actif": True, "boss_final": True, "salon": salon_boss.id}
            embed = discord.Embed(
                title=f"👾 BOSS FINAL — {boss['emoji']} {boss['nom']}",
                description=(
                    f"```\n"
                    f"╔═══════════════════════════════╗\n"
                    f"║  ☠️  {boss['nom'].upper()[:22]}  ☠️  ║\n"
                    f"║  Série : {boss['serie'][:20]}  ║\n"
                    f"║  PV : {pv_boss:,} (2x normal)        ║\n"
                    f"╚═══════════════════════════════╝\n"
                    f"```\n"
                    f"**{boss['nom']}** se réveille dans {salon_boss.mention} avec une rage noire...\n\n"
                    "⚠️ Ce boss **parle, se moque et contre-attaque** !\n"
                    "`.attaquerboss` dans le salon pour le combattre !"
                ),
                color=0x8b0000
            )
            if boss.get('image'):
                embed.set_thumbnail(url=boss['image'])
            await channel_event.send("@everyone", embed=embed)
            await salon_boss.send(embed=discord.Embed(
                description=f"*{boss['nom']} : \"Vous osez me défier ? Intéressant...\"*",
                color=0x8b0000
            ))
            last_reply = __import__('time').time()
            while guild.id in invasion_active and invasion_active[guild.id].get('actif'):
                await asyncio.sleep(20)
                now = __import__('time').time()
                if now - last_reply < 30: continue
                inv = invasion_active.get(guild.id, {})
                if not inv.get('actif'): break
                pct = inv['pv'] / inv['max_pv']
                attaquants = inv.get('attaquants', {})
                if attaquants and _r.random() < 0.5:
                    victime_uid = _r.choice(list(attaquants.keys()))
                    victime = guild.get_member(int(victime_uid))
                    if victime:
                        vol = _r.randint(50, 200)
                        economy_data[victime_uid]['coins'] = max(0, economy_data[victime_uid]['coins'] - vol)
                        await salon_boss.send(embed=discord.Embed(
                            description=f"{boss['emoji']} *\"{_r.choice(repliques_contreattaque)}\"*\n\n💥 {victime.mention} perd **{vol} pièces** !",
                            color=0x8b0000
                        ))
                elif pct > 0.7:
                    await salon_boss.send(embed=discord.Embed(
                        description=f"{boss['emoji']} *\"{_r.choice(repliques_moquerie)}\"*",
                        color=0x8b0000
                    ))
                else:
                    await salon_boss.send(embed=discord.Embed(
                        description=f"{boss['emoji']} *\"{_r.choice(repliques_fort)}\"*",
                        color=0xe74c3c
                    ))
                last_reply = now
            if salon_boss != channel_event:
                asyncio.create_task(supprimer_salon_temp(salon_boss, 7, guild, "Boss Final"))
        except Exception as e:
            print(f"Boss final error: {e}")
    event_en_cours = False

# ── 🔴 ALERTE ROUGE ───────────────────────────────────────────

async def lancer_death_note(ctx=None):
    global event_en_cours
    event_en_cours = True

    for guild in bot.guilds:
        try:
            channel = get_event_channel(guild, ctx)
            if not channel: continue

            salon_dn = await creer_salon_temp(guild, "💀・death-note-qg")
            if salon_dn:
                try:
                    await salon_dn.send(embed=discord.Embed(
                        title="💀 DEATH NOTE",
                        description="`.ecrire @joueur` pour frapper (2 max) | ⚠️ Après le 2ème nom → tout revient en double !",
                        color=0x3498db
                    ))
                except:
                    pass
            if salon_dn:
                pass
            if not salon_dn: salon_dn = channel

            membres = [m for m in guild.members if not m.bot]
            if not membres:
                event_en_cours = False
                return

            porteur = _r.choice(membres)

            death_note[guild.id] = {
                "porteur": str(porteur.id),
                "victimes": [],
                "utilisations": 0,
                "salon": salon_dn.id
            }

            embed_reveal = discord.Embed(
                title=f"💀 {porteur_m.display_name if porteur_m else '???'} possédait le Death Note !",
                description=(
                    f"**{len(victimes)} victim(es)** ciblée(s)\n\n"
                    f"{desc_retour if desc_retour else 'Le porteur n\'a pas utilisé le Death Note.'}"
                ),
                color=0xe74c3c
            )
            if porteur_m:
                embed_reveal.set_thumbnail(url=porteur_m.display_avatar.url)

            await salon_dn.send(embed=embed_reveal)
            await channel.send(embed=embed_reveal)

            if guild.id in death_note:
                del death_note[guild.id]

            if salon_dn != channel:
                asyncio.create_task(supprimer_salon_temp(salon_dn, 300))

        except Exception as e:
            print(f"Death Note error: {e}")

    event_en_cours = False

# ── 🔴 ALERTE ROUGE ───────────────────────────────────────────
async def lancer_alerte_rouge(ctx=None):
    global event_en_cours
    event_en_cours = True
    for guild in bot.guilds:
        try:
            channel_event = get_event_channel(guild, ctx)
            if not channel_event: continue
            embed_silence = discord.Embed(
                description=(
                    "```\n"
                    "█████████████████████████\n"
                    "█                       █\n"
                    "█   🔴  A L E R T E  🔴  █\n"
                    "█        R O U G E       █\n"
                    "█                       █\n"
                    "█████████████████████████\n"
                    "```\n"
                    "*...*"
                ),
                color=0xff0000
            )
            msg_alerte = await channel_event.send("@everyone", embed=embed_silence)
            await asyncio.sleep(90)
            await msg_alerte.edit(embed=discord.Embed(
                description=(
                    "```\n"
                    "█████████████████████████\n"
                    "█   🔴  A L E R T E  🔴  █\n"
                    "█████████████████████████\n"
                    "```\n"
                    "*Quelque chose se prépare dans l'ombre...*\n\n"
                    "||Restez attentifs.||"
                ),
                color=0xff0000
            ))
            await asyncio.sleep(90)
            for i in [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]:
                bars = "🟥" * i + "⬛" * (10 - i)
                await channel_event.send(embed=discord.Embed(
                    description=f"```\n⚠️  ALERTE  ⚠️\n{bars}\n   {i:02d}s\n```",
                    color=0xff0000
                ))
                await asyncio.sleep(1)
            embed_reveal = discord.Embed(
                title="💥 ÇA COMMENCE !",
                description="L'Alerte Rouge était le prélude à quelque chose d'énorme...",
                color=0xff0000
            )
            await channel_event.send("@everyone", embed=embed_reveal)
            event_en_cours = False
            # Déclencher event surprise
            events_surprise = [lancer_vague_legendaires, lancer_tournoi, lancer_encheres]
            await _r.choice(events_surprise)(ctx=ctx)
        except Exception as e:
            print(f"Alerte rouge error: {e}")
    event_en_cours = False

# ── 🌍 CONQUÊTE DU QG ─────────────────────────────────────────

async def lancer_conquete(ctx=None):
    global event_en_cours
    event_en_cours = True
    for guild in bot.guilds:
        try:
            channel_event = get_event_channel(guild, ctx)
            if not channel_event: continue
            salon_cqt = await creer_salon_temp(guild, "🌍・conquete-qg")
            if salon_cqt:
                try:
                    await salon_cqt.send(embed=discord.Embed(
                        title="🌍 CONQUÊTE DU QG",
                        description="Soyez la faction la + active dans chaque zone ! Chaque message = +1pt ⏰ 1 heure",
                        color=0x3498db
                    ))
                except:
                    pass
            if salon_cqt:
                pass
            if not salon_cqt: salon_cqt = channel_event
            # Zones : utiliser les salons configurés ou fallback automatique
            zones = []
            if CONQUETE_ZONE_IDS:
                for zid in CONQUETE_ZONE_IDS:
                    ch = guild.get_channel(zid)
                    if ch: zones.append(ch)
            if not zones:
                for ch in guild.text_channels:
                    perms = ch.permissions_for(guild.default_role)
                    if perms.read_messages and perms.send_messages and ch != channel_event and ch != salon_cqt:
                        zones.append(ch)
                zones = zones[:6]
            if not zones:
                await channel_event.send("❌ Pas de salons accessibles pour la Conquête !")
                event_en_cours = False
                return
            zone_messages = {str(z.id): {} for z in zones}
            embed = discord.Embed(
                title="🌍 CONQUÊTE DU QG",
                description=(
                    "Les factions s'affrontent pour contrôler les zones du serveur !\n\n"
                    "**Comment conquérir ?** Soyez la faction la plus active dans chaque salon !\n\n"
                    "**Zones à conquérir :**\n" +
                    "\n".join([f"• {z.mention}" for z in zones]) +
                    "\n\n⏰ **1 heure** de conquête !\n"
                    "Suivez l'avancement dans " + salon_cqt.mention
                ),
                color=0xe74c3c
            )
            await channel_event.send("@everyone", embed=embed)
            await salon_cqt.send(embed=discord.Embed(
                description="📊 Tableau de bord de la Conquête — mises à jour toutes les 20 min !",
                color=0xe74c3c
            ))
            conquete_zones[guild.id] = {"zones": {str(z.id): None for z in zones}, "messages": zone_messages, "actif": True}
            for update in range(3):
                await asyncio.sleep(1200)
                scores_factions = {}
                for zone_id, msgs in zone_messages.items():
                    if msgs:
                        winner_faction = max(msgs, key=msgs.get)
                        conquete_zones[guild.id]["zones"][zone_id] = winner_faction
                        scores_factions[winner_faction] = scores_factions.get(winner_faction, 0) + 1
                if scores_factions:
                    desc_update = f"**Mise à jour {update+1}/3 :**\n\n"
                    for fid, count in sorted(scores_factions.items(), key=lambda x: x[1], reverse=True):
                        fd = FACTIONS.get(fid, {})
                        desc_update += f"{fd.get('emoji','')} **{fd.get('nom',fid)}** — {count} zone(s)\n"
                    await salon_cqt.send(embed=discord.Embed(description=desc_update, color=0xe67e22))
            scores_finaux = {}
            for zone_id, msgs in zone_messages.items():
                if msgs:
                    winner_faction = max(msgs, key=msgs.get)
                    scores_finaux[winner_faction] = scores_finaux.get(winner_faction, 0) + 1
            if scores_finaux:
                faction_gagnante = max(scores_finaux, key=scores_finaux.get)
                fd = FACTIONS.get(faction_gagnante, {})
                old_role = discord.utils.get(guild.roles, name="⚔️ Roi de la Conquête")
                if old_role:
                    for member in old_role.members:
                        try: await member.remove_roles(old_role)
                        except: pass
                role_cqt = await get_or_create_role(guild, "⚔️ Roi de la Conquête", 0xe74c3c)
                membres_faction = [guild.get_member(int(uid)) for uid, fid in faction_data.items() if fid == faction_gagnante and guild.get_member(int(uid))]
                for m in membres_faction:
                    if m and role_cqt:
                        try: await m.add_roles(role_cqt)
                        except: pass
                mentions_gagnants = " ".join([m.mention for m in membres_faction[:5]]) if membres_faction else ""
                embed_winner = discord.Embed(
                    title=f"🏆 {fd.get('emoji','')} {fd.get('nom',faction_gagnante)} remporte la Conquête !",
                    description=(
                        f"**{scores_finaux[faction_gagnante]}/{len(zones)} zones** contrôlées !\n\n"
                        f"{mentions_gagnants}\n\n"
                        "Rôle **Roi de la Conquête** attribué ! *(perdable à la prochaine Conquête)*"
                    ),
                    color=0xf1c40f
                )
                await salon_cqt.send(embed=embed_winner)
                await channel_event.send(embed=embed_winner)
            if guild.id in conquete_zones:
                del conquete_zones[guild.id]
            if salon_cqt != channel_event:
                asyncio.create_task(supprimer_salon_temp(salon_cqt, 7, guild, "Conquête du QG"))
        except Exception as e:
            print(f"Conquête error: {e}")
    event_en_cours = False

# ── 🌊 PROPHÉTIE S'ACCOMPLIT ──────────────────────────────────

async def lancer_prophetie_accomplie(ctx=None):
    global event_en_cours, serie_benie
    event_en_cours = True
    if not serie_benie:
        serie_benie = "Naruto"
    lore_events = {
        "Naruto": ("Madara a lancé le Mugen Tsukuyomi sur le QG !", "🌙", "akatsuki"),
        "One Piece": ("Barbe Blanche a déclaré la guerre au QG !", "🏴‍☠️", "strawhat"),
        "Demon Slayer": ("Muzan attaque le QG à l'aube !", "🌸", None),
        "Bleach": ("Aizen a trahi le Gotei 13 et attaque le QG !", "🦋", "gotei13"),
        "Attack on Titan": ("Les Titans ont franchi les murs du QG !", "⚔️", "surveycorps"),
        "My Hero Academia": ("All For One attaque le QG !", "💥", "ua"),
    }
    for guild in bot.guilds:
        try:
            channel_event = get_event_channel(guild, ctx)
            if not channel_event: continue
            lore = lore_events.get(serie_benie, (f"Une force de {serie_benie} envahit le QG !", "🌀", None))
            faction_liee = lore[2]
            embed = discord.Embed(
                title=f"🌊 LA PROPHÉTIE S'ACCOMPLIT — {lore[1]} {serie_benie.upper()}",
                description=(
                    f"**{lore[0]}**\n\n"
                    f"Pendant **2 heures** :\n"
                    f"• Les cartes **{serie_benie}** ont **+20% de stats** en arène\n"
                    f"• Les rolls ont **×3 de chance** de tomber sur **{serie_benie}**\n"
                    f"• Les membres de la faction liée reçoivent **+200 pièces** !"
                ),
                color=0x9b59b6
            )
            await channel_event.send("@everyone", embed=embed)
            if faction_liee:
                membres_recompenses = []
                for uid, fid in faction_data.items():
                    if fid == faction_liee:
                        economy_data[uid]['coins'] += 200
                        m = guild.get_member(int(uid))
                        if m: membres_recompenses.append(m.mention)
                if membres_recompenses:
                    await channel_event.send(embed=discord.Embed(
                        description=f"💰 **+200 pièces** pour : {' '.join(membres_recompenses[:10])}",
                        color=0xf1c40f
                    ))
            await asyncio.sleep(7200)
            await channel_event.send(embed=discord.Embed(
                description=f"🌊 La Prophétie de **{serie_benie}** est accomplie. Le calme revient...",
                color=0x95a5a6
            ))
        except Exception as e:
            print(f"Prophétie error: {e}")
    for guild in bot.guilds:
            try:
                ch = guild.get_channel(SALON_EVENT_ID) if SALON_EVENT_ID else guild.system_channel
                if ch:
                    await ch.send(embed=discord.Embed(
                        description="✅ **Prophétie Accomplie** — le calme revient sur le QG... Merci d\'avoir participé 🎉",
                        color=0x2ecc71
                    ))
            except: pass
    event_en_cours = False



async def miser_cmd(ctx, montant: int = None):
    """Miser dans les enchères — .miser <montant>"""
    gid = ctx.guild.id
    if gid not in encheres_actives or not encheres_actives[gid].get("actif"):
        return await ctx.send("❌ Pas d'enchères actives !", delete_after=5)
    if not montant or montant <= 0:
        return await ctx.send("❌ Montant invalide !", delete_after=5)
    uid = str(ctx.author.id)
    if economy_data[uid]['coins'] < montant:
        return await ctx.send(f"❌ Tu n'as pas assez de pièces ! Solde : **{economy_data[uid]['coins']:,}p**", delete_after=5)
    encheres_actives[gid]["mises"][uid] = montant
    await ctx.send(f"✅ Mise de **{montant:,} pièces** enregistrée !", delete_after=5)
    try:
        await ctx.message.delete()
    except:
        pass

@bot.command(name="miner")
async def miner_cmd(ctx):
    """Miner des pépites — .miner"""
    import time as _t
    gid = ctx.guild.id
    if gid not in mine_actif or not mine_actif[gid]:
        return await ctx.send("❌ Pas de mine active !", delete_after=5)

    data = mine_actif[gid]
    uid = str(ctx.author.id)

    # Cooldown 2 min
    last = data.get("last_mine", {}).get(uid, 0)
    if _t.time() - last < 120:
        reste = int(120 - (_t.time() - last))
        return await ctx.send(f"⏳ Attends encore **{reste}s** avant de reminer !", delete_after=5)

    if not data.get("last_mine"):
        data["last_mine"] = {}
    data["last_mine"][uid] = _t.time()

    if data["pepites"] <= 0:
        return await ctx.send("❌ La mine est épuisée !", delete_after=5)

    # Pépite maudite ?
    total_extrait = sum(data["joueurs"].values())
    if total_extrait == data.get("malédiction", -1):
        data["joueurs"][uid] = 0  # Perd tout
        await ctx.send(f"💀 **{ctx.author.display_name}** a extrait la **PÉPITE MAUDITE** ! Il perd tout ce qu'il avait extrait !", delete_after=10)
        return

    extrait = _r.randint(1, min(30, data["pepites"]))
    data["pepites"] = max(0, data["pepites"] - extrait)
    data["joueurs"][uid] = data["joueurs"].get(uid, 0) + extrait

    await ctx.send(f"⛏️ **{ctx.author.display_name}** extrait **{extrait} pépites** ! Total : **{data['joueurs'][uid]}** | Restantes : **{data['pepites']}**", delete_after=10)

    if data["pepites"] <= 0:
        channel = ctx.guild.get_channel(data.get("channel_id", 0)) or ctx.channel
        await _finaliser_mine(ctx.guild, channel, data)
        data["finie"] = [True]
        if gid in mine_actif:
            del mine_actif[gid]

@bot.command(name="chasser")
async def chasser_cmd(ctx, cible: discord.Member = None):
    """Chasser la cible Wanted — .chasser @joueur"""
    gid = ctx.guild.id
    if gid not in wanted_actif:
        return await ctx.send("❌ Pas d'avis de recherche actif !", delete_after=5)
    data = wanted_actif[gid]
    # Accepter mention ou ID
    if not cible:
        return await ctx.send("❌ Mentionne la cible ! Ex: `.chasser @joueur`", delete_after=5)
    if str(cible.id) != str(data.get("cible","")):
        cible_member = ctx.guild.get_member(int(data["cible"])) if data.get("cible") else None
        nom_cible = cible_member.display_name if cible_member else "???"
        return await ctx.send(f"❌ La cible est **{nom_cible}** — mentionne la bonne personne !", delete_after=5)
    uid = str(ctx.author.id)
    prime = data["prime"]
    economy_data[uid]['coins'] += prime
    economy_data[data["cible"]]['coins'] = max(0, economy_data[data["cible"]]['coins'] - prime // 2)
    del wanted_actif[gid]
    # Retirer l'ancien rôle chasseur
    old_chasseur = discord.utils.get(ctx.guild.roles, name="🎯 Chasseur de Primes N°1")
    if old_chasseur:
        for m in old_chasseur.members:
            try: await m.remove_roles(old_chasseur)
            except: pass
    role_chasseur = await get_or_create_role(ctx.guild, "🎯 Chasseur de Primes N°1", 0xc0392b)
    if role_chasseur:
        try: await ctx.author.add_roles(role_chasseur)
        except: pass
    # Fin de l'event
    if ctx.guild.id in wanted_actif:
        del wanted_actif[ctx.guild.id]
    event_en_cours = False
    # Annonce dans salon event
    ch_ev = ctx.guild.get_channel(SALON_EVENT_ID) if SALON_EVENT_ID else ctx.guild.system_channel
    embed_win = discord.Embed(
        title="🎯 WANTED — CIBLE CAPTURÉE !",
        description=(
            f"**{ctx.author.mention}** a capturé {cible.mention} et récupère **{prime:,} pièces** !\n"
            f"🎯 Rôle **Chasseur de Primes N°1** attribué !"
        ),
        color=0x2ecc71
    )
    if ch_ev:
        await ch_ev.send(embed=embed_win)
    await ctx.send(embed=embed_win, delete_after=5)

@bot.command(name="eliminer")
async def eliminer_cmd(ctx, cible: discord.Member = None):
    """Éliminer un joueur (imposteur uniquement) — .eliminer @joueur"""
    gid = ctx.guild.id
    if gid not in parminous_game:
        return await ctx.send("❌ Pas de partie Parmi Nous active !", delete_after=5)
    game = parminous_game[gid]
    uid = str(ctx.author.id)
    if uid != game["imposteur"]:
        return await ctx.send("❌ T'es pas l'imposteur !", delete_after=5)
    if not cible or cible.bot:
        return await ctx.send("❌ Cible invalide !", delete_after=5)
    if str(cible.id) in game["victimes"]:
        return await ctx.send("❌ Tu as déjà volé cette personne !", delete_after=5)
    if len(game["victimes"]) >= 7:
        return await ctx.send("❌ Maximum 7 vols atteint !", delete_after=5)

    # Vol aléatoire d'une carte
    cible_cartes = [k for k, v in claimed_cards.items() if v == str(cible.id)]
    if not cible_cartes:
        return await ctx.send("❌ Cette personne n'a pas de cartes !", delete_after=5)

    carte_volee = _r.choice(cible_cartes)
    claimed_cards[carte_volee] = uid
    if uid not in gacha_collections:
        gacha_collections[uid] = {}
    gacha_collections[uid][carte_volee] = {"fusion": 0}
    if carte_volee in gacha_collections.get(str(cible.id), {}):
        del gacha_collections[str(cible.id)][carte_volee]

    game["victimes"].append(str(cible.id))
    if uid not in game["cartes_volees"]:
        game["cartes_volees"][uid] = []
    game["cartes_volees"][uid].append(carte_volee)

    c = ANIME_CARDS_DB.get(carte_volee, {})
    try:
        await ctx.message.delete()
        await ctx.author.send(f"✅ Tu as volé **{c.get('nom', carte_volee)}** à **{cible.display_name}** !")
        await cible.send(f"😱 Une de tes cartes a été volée mystérieusement... quelqu'un te surveille !")
    except:
        pass

@bot.command(name="voter")
async def voter_cmd(ctx, cible: discord.Member = None):
    """Voter pour éliminer quelqu'un — .voter @joueur"""
    gid = ctx.guild.id
    if gid not in parminous_game:
        return await ctx.send("❌ Pas de partie Parmi Nous active !", delete_after=5)
    if not cible:
        return await ctx.send("❌ Mentionne quelqu'un !", delete_after=5)
    uid = str(ctx.author.id)
    parminous_game[gid]["votes"][uid] = str(cible.id)
    await ctx.send(f"🗳️ **{ctx.author.display_name}** vote contre **{cible.display_name}** !", delete_after=10)

@bot.command(name="jedoute")
async def jedoute_cmd(ctx):
    """Signaler une fausse rumeur — .jedoute"""
    uid = str(ctx.author.id)
    gid = ctx.guild.id
    if gid in fausse_rumeur_active:
        fausse_rumeur_active[gid]["douteurs"][uid] = True
        economy_data[uid]['coins'] += 150
        await ctx.send(f"🧠 **{ctx.author.display_name}** doute de la rumeur !", delete_after=5)
        try: await ctx.message.delete()
        except: pass
    else:
        await ctx.send("❌ Aucune fausse rumeur en cours !", delete_after=5)

@bot.command(name="adopter")
async def adopter_cmd(ctx):
    """Adopter le corbeau — .adopter"""
    gid = ctx.guild.id
    if gid not in canard_actif:
        return await ctx.send("❌ Pas de canard à adopter !", delete_after=5)
    if canard_actif[gid].get("proprio"):
        ancien = ctx.guild.get_member(int(canard_actif[gid]["proprio"]))
        return await ctx.send(f"❌ Le corbeau appartient déjà à **{ancien.display_name if ancien else '???'}** !", delete_after=5)
    canard_actif[gid]["proprio"] = str(ctx.author.id)
    await ctx.send(f"🐦‍⬛ **{ctx.author.display_name}** adopte le corbeau ! Prends-en soin... ou pas 😄")

@bot.command(name="sort")
async def sort_cmd(ctx, type_sort: str = None, cible: discord.Member = None):
    """Lancer un sort (Magicien uniquement) — .sort <type> @joueur"""
    gid = ctx.guild.id
    if gid not in magicien_actif:
        return await ctx.send("❌ Pas de Magicien actif !", delete_after=5)
    data = magicien_actif[gid]
    if str(ctx.author.id) != data["magicien"]:
        return await ctx.send("❌ T'es pas le Magicien !", delete_after=5)
    if data["sorts_restants"] <= 0:
        return await ctx.send("❌ Plus de sorts disponibles !", delete_after=5)
    if not cible or not type_sort:
        return await ctx.send("❌ Usage : `.sort double/bloquer/troll @joueur`", delete_after=5)

    uid_cible = str(cible.id)
    type_sort = type_sort.lower()

    if type_sort == "double":
        economy_data[uid_cible]['coins'] *= 2
        effet = f"ses pièces ont été **doublées** !"
    elif type_sort == "bloquer":
        effet = f"ses commandes sont **bloquées 30 min** !"
    elif type_sort == "troll":
        commune = [k for k in ANIME_CARDS_DB if ANIME_CARDS_DB[k]['rarete'] == 'Commun' and k not in claimed_cards]
        if commune:
            key = _r.choice(commune)
            claimed_cards[key] = uid_cible
            gacha_collections[uid_cible][key] = {"fusion": 0}
        effet = f"a reçu une carte **Commune nulle** 😂"
    else:
        return await ctx.send("❌ Sort invalide ! `double`, `bloquer` ou `troll`", delete_after=5)

    data["sorts_restants"] -= 1
    data["sorts_lances"].append({"type": type_sort, "cible": cible.display_name})

    try:
        await ctx.message.delete()
        await cible.send(f"✨ Un sort anonyme a été lancé sur toi — **{effet}**")
    except:
        pass
    await ctx.author.send(f"✅ Sort `{type_sort}` lancé sur **{cible.display_name}** ! Sorts restants : **{data['sorts_restants']}**")

@bot.command(name="ecrire")
async def ecrire_cmd(ctx, cible: discord.Member = None):
    """Écrire un nom dans le Death Note — .ecrire @joueur"""
    gid = ctx.guild.id
    if gid not in death_note:
        return await ctx.send("❌ Pas de Death Note actif !", delete_after=5)
    data = death_note[gid]
    if str(ctx.author.id) != data["porteur"]:
        return await ctx.send("❌ T'as pas le Death Note !", delete_after=5)
    if data["utilisations"] >= 2:
        return await ctx.send("❌ Le Death Note est épuisé !", delete_after=5)
    if not cible:
        return await ctx.send("❌ Mentionne quelqu'un !", delete_after=5)

    uid_cible = str(cible.id)
    effets = ["pieces", "carte", "blocage"]
    effet = _r.choice(effets)

    montant = 0
    if effet == "pieces":
        montant = min(500, economy_data[uid_cible]['coins'])
        economy_data[uid_cible]['coins'] = max(0, economy_data[uid_cible]['coins'] - montant)
        desc_effet = f"💸 Perd **{montant} pièces**"
    elif effet == "carte":
        cartes = [k for k, v in claimed_cards.items() if v == uid_cible]
        if cartes:
            pire = min(cartes, key=lambda k: ["Commun","Rare","Épique","Légendaire","Mythique"].index(ANIME_CARDS_DB.get(k,{}).get("rarete","Commun")))
            del claimed_cards[pire]
            if pire in gacha_collections.get(uid_cible, {}):
                del gacha_collections[uid_cible][pire]
            desc_effet = f"🃏 Perd la carte **{ANIME_CARDS_DB.get(pire,{}).get('nom','???')}**"
        else:
            desc_effet = "❌ Aucune carte à perdre"
    else:
        desc_effet = f"🔒 Commandes bloquées **2h**"

    data["utilisations"] += 1
    data["victimes"].append({"uid": uid_cible, "effet": effet, "montant": montant})

    try:
        await ctx.message.delete()
        await cible.send(f"💀 Ton nom a été écrit dans le Death Note... {desc_effet}")
        await ctx.author.send(f"✅ **{cible.display_name}** a été ciblé ! {desc_effet}\nUtilisations restantes : **{2 - data['utilisations']}**")
    except:
        pass

# ── Handler clown dans on_message ─────────────────────────────
async def process_clown(message):
    if message.author.bot: return
    gid = message.guild.id if message.guild else None
    if not gid: return

    clown_uid = clown_actif.get(gid)
    if not clown_uid or str(message.author.id) != clown_uid: return

    # Répéter en version ridicule
    clown_versions = [
        f"🤡 *HONK HONK* {message.content} 🤡",
        f"🤡 {message.content.upper()} 🎪🤡🎪",
        f"🤡 Traduction : {message.content} (mais en version clown) 🎈",
        f"🎭 Le Grand Clown proclame : «{message.content}» 🤡",
    ]
    try:
        await message.channel.send(_r.choice(clown_versions))
    except:
        pass

    # Libération si quelqu'un réagit 😂 aux messages du clown
    for reaction in message.reactions:
        if str(reaction.emoji) == "😂" and reaction.count >= 1:
            if gid in clown_actif:
                del clown_actif[gid]
                role_clown = discord.utils.get(message.guild.roles, name="🤡 Clown du QG")
                clown_member = message.guild.get_member(int(clown_uid))
                if role_clown and clown_member:
                    try: await clown_member.remove_roles(role_clown)
                    except: pass
                await message.channel.send(f"😂 {clown_member.mention if clown_member else '???'} a fait rire quelqu'un et est **libéré** du sort de Clown !")
            return

# ── Handler conquête dans on_message ──────────────────────────
async def process_conquete(message):
    if message.author.bot or not message.guild: return
    gid = message.guild.id
    if gid not in conquete_zones: return

    data = conquete_zones[gid]
    uid = str(message.author.id)
    fid = faction_data.get(uid)
    if not fid: return

    channel_id = str(message.channel.id)
    if channel_id not in data["messages"]:
        return

    if fid not in data["messages"][channel_id]:
        data["messages"][channel_id][fid] = 0
    data["messages"][channel_id][fid] += 1

# ── Handler voleur de minuit dans on_message ──────────────────
async def process_voleur(message):
    if message.author.bot or not message.guild: return
    gid = message.guild.id
    data = wanted_actif.get(gid, {})
    if not data.get("voleur"): return
    if str(message.author.id) != data["voleur"]: return

    # Vol silencieux
    membres_actifs = [
        m for m in message.guild.members
        if not m.bot and str(m.id) != data["voleur"] and economy_data[str(m.id)]['coins'] > 10
    ]
    if not membres_actifs: return

    victime = _r.choice(membres_actifs)
    vol = _r.randint(5, 20)
    economy_data[str(victime.id)]['coins'] = max(0, economy_data[str(victime.id)]['coins'] - vol)
    economy_data[data["voleur"]]['coins'] += vol
    data["total_vole"] = data.get("total_vole", 0) + vol

    try:
        await victime.send("🌙 *Des pièces ont mystérieusement disparu de ton coffre cette nuit...*")
    except:
        pass


@bot.command(name="leavefaction", aliases=["quitfaction","leavefac"])
async def leavefaction_cmd(ctx):
    """Quitter sa faction — .leavefaction"""
    uid = str(ctx.author.id)
    if uid not in faction_data:
        return await ctx.send("❌ T'es dans aucune faction ! `.faction rejoindre <id>` pour en rejoindre une.")
    old_fid = faction_data[uid]
    old_fd = FACTIONS.get(old_fid, {})
    del faction_data[uid]
    embed = discord.Embed(
        title="👋 Faction quittée",
        description=f"{ctx.author.mention} a quitté **{old_fd.get('emoji','')} {old_fd.get('nom', old_fid)}** !\n\n*Tu peux rejoindre une autre faction avec `.faction rejoindre <id>`*",
        color=0x95a5a6
    )
    await ctx.send(embed=embed)


@bot.command(name="addcard", aliases=["createcard","carteperso"])
@commands.has_permissions(administrator=True)
async def addcard_cmd(ctx, *, args: str = None):
    """Crée une carte custom — .addcard <nom> | <serie> | <rarete> | <emoji> | <url_image>
    Raretés : Commun, Rare, Épique, Légendaire, Mythique
    Ex: .addcard Sensei | QG Kdrama | Mythique | 👑 | https://i.imgur.com/xxx.jpg"""

    if not args:
        return await ctx.send(
            "❌ Usage : `.addcard <nom> | <serie> | <rarete> | <emoji> | <url_image>`\n"
            "Ex : `.addcard Sensei | QG Kdrama | Mythique | 👑 | https://i.imgur.com/xxx.jpg`"
        )

    parts = [p.strip() for p in args.split("|")]
    if len(parts) < 4:
        return await ctx.send(
            "❌ Il manque des infos ! Format : `nom | serie | rarete | emoji | url_image(optionnel)`\n"
            "Raretés valides : `Commun` `Rare` `Épique` `Légendaire` `Mythique`"
        )

    nom = parts[0]
    serie = parts[1]
    rarete = parts[2]
    emoji = parts[3]
    url = parts[4] if len(parts) >= 5 else "https://i.imgur.com/JzbTwwD.jpg"

    rarete_valides = ["Commun", "Rare", "Épique", "Légendaire", "Mythique"]
    if rarete not in rarete_valides:
        return await ctx.send(f"❌ Rareté invalide ! Valides : {' • '.join(rarete_valides)}")

    if url and not url.startswith("https://i.imgur.com/"):
        return await ctx.send("❌ Image : utilise uniquement des liens imgur (https://i.imgur.com/...)")

    # Stats automatiques selon rareté
    stats = {
        "Commun":    {"pv": 100, "attaque": 25, "defense": 20},
        "Rare":      {"pv": 150, "attaque": 55, "defense": 50},
        "Épique":    {"pv": 200, "attaque": 80, "defense": 70},
        "Légendaire":{"pv": 230, "attaque": 100, "defense": 85},
        "Mythique":  {"pv": 260, "attaque": 120, "defense": 100},
    }[rarete]

    # Générer une clé unique
    import re as _re
    key = _re.sub(r"[^a-z0-9]", "", nom.lower().replace(" ", "_"))[:20]
    if not key:
        key = f"custom_{len(ANIME_CARDS_DB)}"
    # Éviter les doublons de clé
    base_key = key
    i = 1
    while key in ANIME_CARDS_DB:
        key = f"{base_key}{i}"
        i += 1

    ANIME_CARDS_DB[key] = {
        "nom": nom,
        "serie": serie,
        "rarete": rarete,
        "emoji": emoji,
        "pv": stats["pv"],
        "attaque": stats["attaque"],
        "defense": stats["defense"],
        "image": url,
        "attaques": [
            {"nom": "Attaque", "emoji": emoji, "degats": stats["attaque"]//2, "desc": "Frappe"},
            {"nom": "Combo", "emoji": "💥", "degats": int(stats["attaque"]*0.7), "desc": "Enchaînement"},
            {"nom": "Ultime", "emoji": "⚡", "degats": stats["attaque"], "desc": "Technique ultime"},
        ],
        "faiblesse": "💀",
        "resistance": emoji,
    }

    r_emoji = RARETE_EMOJI.get(rarete, "⭐")
    couleur = RARETE_COULEURS.get(rarete, 0x9b59b6)

    embed = discord.Embed(
        title=f"✅ Carte créée — {emoji} {nom}",
        description=(
            f"{r_emoji} **{rarete}** • *{serie}*\n\n"
            f"❤️ **{stats['pv']} PV** | ⚔️ **{stats['attaque']} ATK** | 🛡️ **{stats['defense']} DEF**\n\n"
            f"Clé interne : `{key}`\n\n"
            f"La carte est maintenant disponible dans le gacha !\n"
            f"Tu peux la donner avec `.givecard @joueur {key}`\n"
            f"Tu peux changer son image avec `.setimage {nom} <url>`"
        ),
        color=couleur
    )
    if url:
        embed.set_thumbnail(url=url)
    await ctx.send(embed=embed)


@bot.command(name="stopervent", aliases=["stopevent", "arreterevent", "endevent"])
@commands.has_permissions(administrator=True)
async def stopervent_cmd(ctx):
    """Arrête l'event en cours immédiatement — .stopervent"""
    global event_en_cours, encheres_actives, parminous_game, mine_actif
    global wanted_actif, clown_actif, canard_actif, magicien_actif
    global death_note, conquete_zones, oracle_prophecies, pacte_actif
    global puzzle_actif, vague_actif, double_xp_event_actif

    if not event_en_cours:
        return await ctx.send("❌ Aucun event en cours !", delete_after=5)

    # Reset toutes les variables d'events
    event_en_cours = False
    double_xp_event_actif = False

    # Nettoyer les données des events actifs
    for gid in list(encheres_actives.keys()):
        encheres_actives[gid]["actif"] = False
        del encheres_actives[gid]
    for gid in list(invasion_active.keys()):
        invasion_active[gid]["actif"] = False
        del invasion_active[gid]
    for gid in list(parminous_game.keys()):
        parminous_game[gid]["actif"] = False
        del parminous_game[gid]
    for gid in list(mine_actif.keys()):
        if isinstance(mine_actif[gid], dict):
            mine_actif[gid]["finie"] = [True]
        del mine_actif[gid]
    for gid in list(wanted_actif.keys()):
        del wanted_actif[gid]
    for gid in list(clown_actif.keys()):
        # Retirer le rôle clown
        guild = bot.get_guild(gid)
        if guild:
            role = discord.utils.get(guild.roles, name="🤡 Clown du QG")
            member = guild.get_member(int(clown_actif[gid]))
            if role and member:
                try:
                    await member.remove_roles(role)
                except:
                    pass
        del clown_actif[gid]
    for gid in list(canard_actif.keys()):
        del canard_actif[gid]
    for gid in list(magicien_actif.keys()):
        del magicien_actif[gid]
    for gid in list(death_note.keys()):
        del death_note[gid]
    for gid in list(conquete_zones.keys()):
        del conquete_zones[gid]
    for gid in list(pacte_actif.keys()):
        del pacte_actif[gid]
    for gid in list(puzzle_actif.keys()):
        del puzzle_actif[gid]
    oracle_prophecies.clear()

    # Annonce dans le salon event
    # Annonce dans salon event
    if SALON_EVENT_ID:
        ch_event = ctx.guild.get_channel(SALON_EVENT_ID)
    else:
        ch_event = ctx.channel
    if ch_event:
        embed = discord.Embed(
            title="🛑 Event Arrêté",
            description="L'event en cours a été arrêté par un administrateur.",
            color=0xe74c3c
        )
        await ch_event.send(embed=embed)
    await ctx.send(embed=discord.Embed(
        description="✅ Event arrêté ! Le serveur est de nouveau libre.",
        color=0x2ecc71
    ), delete_after=10)


@bot.command(name="setconquete", aliases=["conquetezones"])
@commands.has_permissions(administrator=True)
async def setconquete_cmd(ctx, *channels: discord.TextChannel):
    """Configure les salons de la Conquête — .setconquete #general #gaming #anime"""
    global CONQUETE_ZONE_IDS
    if not channels:
        if CONQUETE_ZONE_IDS:
            zones = [ctx.guild.get_channel(cid) for cid in CONQUETE_ZONE_IDS]
            desc = "\n".join([f"• {z.mention}" for z in zones if z])
            return await ctx.send(embed=discord.Embed(
                title="🌍 Zones de Conquête configurées",
                description=desc,
                color=0xe74c3c
            ))
        return await ctx.send("❌ Usage : `.setconquete #salon1 #salon2 #salon3`")
    CONQUETE_ZONE_IDS = [ch.id for ch in channels]
    sauvegarder_salons()
    desc = "\n".join([f"• {ch.mention}" for ch in channels])
    await ctx.send(embed=discord.Embed(
        title="✅ Zones de Conquête configurées !",
        description=desc,
        color=0x2ecc71
    ))


@bot.command(name="ouvrir", aliases=["open","coffre"])
async def ouvrir_cmd(ctx):
    """Ouvrir un coffre actif — .ouvrir"""
    import time as _t
    uid = str(ctx.author.id)
    channel_id = ctx.channel.id

    # Chercher un coffre actif dans ce salon ou le salon event
    coffre = coffre_actif.get(channel_id)
    if not coffre:
        # Chercher dans tous les salons actifs
        for cid, c in list(coffre_actif.items()):
            if c.get("expires", 0) > _t.time():
                coffre = c
                channel_id = cid
                break

    if not coffre:
        return await ctx.send("❌ Pas de coffre actif en ce moment !", delete_after=5)

    if coffre.get("expires", 0) < _t.time():
        del coffre_actif[channel_id]
        return await ctx.send("❌ Ce coffre a expiré !", delete_after=5)

    if uid in coffre.get("ouvert_par", []):
        return await ctx.send("❌ Tu as déjà ouvert ce coffre !", delete_after=5)

    if "ouvert_par" not in coffre:
        coffre["ouvert_par"] = []
    coffre["ouvert_par"].append(uid)

    gain = coffre["contenu"]
    economy_data[uid]['coins'] += gain

    embed = discord.Embed(
        title="📦 Coffre Ouvert !",
        description=f"{ctx.author.mention} ouvre le coffre et trouve **{gain} pièces** ! 💰",
        color=0xf1c40f
    )
    await ctx.send(embed=embed)

    # Supprimer le coffre après première ouverture
    if channel_id in coffre_actif:
        del coffre_actif[channel_id]
    event_en_cours = False


@bot.command(name="miser", aliases=["bid","enchere"])
async def miser_cmd(ctx, montant: int = None):
    """Miser dans les enchères — .miser <montant>"""
    gid = ctx.guild.id
    if gid not in encheres_actives or not encheres_actives[gid].get("actif"):
        return await ctx.send("❌ Pas d'enchères actives !", delete_after=5)
    if not montant or montant <= 0:
        return await ctx.send("❌ Montant invalide !", delete_after=5)
    uid = str(ctx.author.id)
    if economy_data[uid]['coins'] < montant:
        return await ctx.send(f"❌ Tu n'as pas assez de pièces ! Solde : **{economy_data[uid]['coins']:,}p**", delete_after=5)
    encheres_actives[gid]["mises"][uid] = montant
    await ctx.send(f"✅ Mise de **{montant:,} pièces** enregistrée !", delete_after=5)
    try: await ctx.message.delete()
    except: pass


async def lancer_classement_hebdo(ctx=None):
    for guild in bot.guilds:
        try:
            channel = get_event_channel(guild, ctx)
            if not channel: continue

            # Score = messages + xp + heures vocal
            scores = {}
            for uid in xp_data:
                m = guild.get_member(int(uid))
                if not m: continue
                score_msg = message_count.get(uid, 0) * 2
                score_xp = xp_data[uid]["xp"]
                score_level = xp_data[uid].get("level", 1) * 50
                scores[uid] = score_msg + score_xp + score_level

            if not scores:
                await channel.send(embed=discord.Embed(description="❌ Pas assez de données pour le classement !", color=0x95a5a6))
                return

            top5 = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:5]
            recompenses = [300, 200, 150, 100, 50]
            medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]

            desc = "**Basé sur : messages + XP + niveau**\n\n"
            mentions = []
            for i, (uid, score) in enumerate(top5):
                member = guild.get_member(int(uid))
                if member:
                    economy_data[uid]["coins"] += recompenses[i]
                    desc += f"{medals[i]} {member.mention} — **{score} pts** → **+{recompenses[i]} pièces** !\n"
                    mentions.append(member.mention)
                    # Reset message_count pour la semaine suivante
                    message_count[uid] = 0

            embed = discord.Embed(
                title="🏆 CLASSEMENT HEBDOMADAIRE — TOP 5",
                description=desc,
                color=0xf1c40f
            )
            await channel.send("@everyone", embed=embed)

        except Exception as e:
            print(f"Classement hebdo error: {e}")


async def lancer_colis_mystere(ctx=None):
    global event_en_cours
    event_en_cours = True
    for guild in bot.guilds:
        try:
            channel = get_event_channel(guild, ctx)
            if not channel: continue

            # Contenu aléatoire — bon ou mauvais
            contenus = [
                {"type": "carte_legendaire", "desc": "une carte **Légendaire** 🟠", "positif": True},
                {"type": "pieces_5000", "desc": "**5000 pièces** 💰", "positif": True},
                {"type": "pieces_2000", "desc": "**2000 pièces** 💰", "positif": True},
                {"type": "rolls_10", "desc": "**+10 rolls** bonus 🎰", "positif": True},
                {"type": "malediction", "desc": "une **malédiction** — perd 50% de ses pièces 💀", "positif": False},
                {"type": "vol_carte", "desc": "un **piège** — perd sa meilleure carte 😈", "positif": False},
                {"type": "rien", "desc": "**rien du tout**... le colis était vide 📭", "positif": False},
            ]
            contenu = _r.choices(
                contenus,
                weights=[10, 20, 15, 10, 20, 15, 10],
                k=1
            )[0]

            embed = discord.Embed(
                title="🎁 UN COLIS MYSTÉRIEUX EST ARRIVÉ !",
                description=(
                    "```\n"
                    "╔═══════════════════════════════╗\n"
                    "║   📦  C O L I S   📦          ║\n"
                    "║  ─────────────────────────  ║\n"
                    "║   Contenu : ???               ║\n"
                    "║   Expéditeur : Inconnu 👀     ║\n"
                    "╚═══════════════════════════════╝\n"
                    "```\n"
                    "💡 Tape `.ouvrir` dans **n'importe quel salon** !\n"
                    "⚡ **Un seul membre peut l\'ouvrir — premier arrivé !**\n"
                    "⚠️ Bon ou mauvais... personne sait avant d\'ouvrir !\n"
                    "⏰ **2 minutes** avant qu\'il disparaisse !"
                ),
                color=0x9b59b6
            )
            msg = await channel.send("@here", embed=embed)

            # Attendre que quelqu'un ouvre
            def check_ouvrir(m):
                return m.content.lower() in [".ouvrir", ".open"] and m.channel == channel and not m.author.bot

            try:
                rep = await bot.wait_for("message", timeout=120.0, check=check_ouvrir)
                uid = str(rep.author.id)
                member = rep.author

                # Appliquer le contenu
                if contenu["type"] == "carte_legendaire":
                    legendaires = [k for k in ANIME_CARDS_DB if k not in claimed_cards and ANIME_CARDS_DB[k]["rarete"] == "Légendaire"]
                    if legendaires:
                        carte_key = _r.choice(legendaires)
                        claimed_cards[carte_key] = uid
                        gacha_collections[uid][carte_key] = {"fusion": 0}
                        c = ANIME_CARDS_DB[carte_key]
                        contenu["desc"] = f"la carte Légendaire **{c['emoji']} {c['nom']}** 🟠"

                elif contenu["type"] == "pieces_5000":
                    economy_data[uid]["coins"] += 5000

                elif contenu["type"] == "pieces_2000":
                    economy_data[uid]["coins"] += 2000

                elif contenu["type"] == "rolls_10":
                    gacha_cooldowns[uid] = max(0, gacha_cooldowns.get(uid, 0) - 10)

                elif contenu["type"] == "malediction":
                    economy_data[uid]["coins"] = int(economy_data[uid]["coins"] * 0.5)

                elif contenu["type"] == "vol_carte":
                    cartes = [k for k, v in claimed_cards.items() if v == uid]
                    if cartes:
                        pire = max(cartes, key=lambda k: ["Commun","Rare","Épique","Légendaire","Mythique"].index(ANIME_CARDS_DB.get(k,{}).get("rarete","Commun")))
                        del claimed_cards[pire]
                        if pire in gacha_collections.get(uid, {}):
                            del gacha_collections[uid][pire]
                        c = ANIME_CARDS_DB.get(pire, {})
                        contenu["desc"] = f"un **piège** — **{c.get('nom','???')}** disparaît 😈"

                couleur = 0x2ecc71 if contenu["positif"] else 0xe74c3c
                emoji_result = "🎉" if contenu["positif"] else "💀"

                embed_result = discord.Embed(
                    title=f"{emoji_result} {member.display_name} ouvre le colis !",
                    description=(
                        "```\n"
                        "╔═══════════════════════════════╗\n"
                        f"║  {'🎁 BONNE SURPRISE !' if contenu['positif'] else '☠️ MAUVAISE SURPRISE !':^29}  ║\n"
                        "╚═══════════════════════════════╝\n"
                        "```\n"
                        f"{member.mention} trouve {contenu['desc']} !"
                    ),
                    color=couleur
                )
                embed_result.set_thumbnail(url=member.display_avatar.url)
                await msg.delete()
                await channel.send(embed=embed_result)

            except asyncio.TimeoutError:
                await msg.delete()
                await channel.send(embed=discord.Embed(
                    description="📭 Le colis mystérieux repart sans avoir été ouvert... dommage !",
                    color=0x95a5a6
                ))

        except Exception as e:
            print(f"Colis mystère error: {e}")
    for guild in bot.guilds:
            try:
                ch = guild.get_channel(SALON_EVENT_ID) if SALON_EVENT_ID else guild.system_channel
                if ch:
                    await ch.send(embed=discord.Embed(
                        description="✅ **Colis Mystère** — la livraison est terminée ! Merci d\'avoir participé 🎉",
                        color=0x2ecc71
                    ))
            except: pass
    event_en_cours = False


async def lancer_invasion_boss(ctx=None):
    """Lance une invasion de boss"""
    import random as _rand
    for guild in bot.guilds:
        try:
            channel = get_event_channel(guild, ctx)
            if not channel: continue
            if guild.id in invasion_active and invasion_active[guild.id].get("actif"):
                return
            boss = _rand.choice(BOSS_INVASIONS).copy()
            invasion_active[guild.id] = {**boss, "attaquants": {}, "actif": True, "max_pv": boss["pv"]}
            embed = discord.Embed(
                title=f"⚠️ INVASION — {boss['emoji']} {boss['nom']}",
                description=(
                    f"**{boss['nom']}** de *{boss['serie']}* envahit le QG !\n\n"
                    f"❤️ **{boss['pv']:,} PV**\n"
                    "`.attaquerboss` pour le combattre !\n"
                    "⏰ **2 heures** pour le vaincre !"
                ),
                color=0x8b0000
            )
            if boss.get("image"):
                embed.set_thumbnail(url=boss["image"])
            await channel.send("@everyone", embed=embed)
        except Exception as e:
            print(f"Invasion boss error: {e}")


async def lancer_prophetie_hebdo(ctx=None):
    """Prophétie hebdo — annonce la série bénie du lundi"""
    global serie_benie
    import random as _rand
    series = ["Naruto", "One Piece", "Demon Slayer", "Bleach", "Attack on Titan",
              "My Hero Academia", "Jujutsu Kaisen", "Hunter x Hunter", "Dragon Ball",
              "Black Clover", "Fairy Tail", "Solo Leveling", "Chainsaw Man"]
    serie_benie = _rand.choice(series)
    for guild in bot.guilds:
        try:
            channel = get_event_channel(guild, ctx)
            if not channel: continue
            embed = discord.Embed(
                title="🔮 PROPHÉTIE DE LA SEMAINE",
                description=(
                    f"L\'Oracle a parlé...\n\n"
                    f"✨ **Série bénie cette semaine : {serie_benie}**\n\n"
                    f"Toutes les cartes **{serie_benie}** ont **+10% de stats** en arène !\n"
                    f"Concentrez vos rolls sur cette série cette semaine !"
                ),
                color=0x9b59b6
            )
            await channel.send("<@&1484584133513580605>", embed=embed)
        except Exception as e:
            print(f"Prophétie hebdo error: {e}")


@bot.command(name="nourrir")
async def nourrir_cmd(ctx):
    gid = ctx.guild.id
    if gid not in canard_actif or not canard_actif[gid].get("proprio"):
        return await ctx.send("❌ T\'as pas de corbeau !", delete_after=5)
    if str(ctx.author.id) != canard_actif[gid]["proprio"]:
        return await ctx.send("❌ C\'est pas ton corbeau !", delete_after=5)
    data = canard_actif[gid]
    if data.get("nourri"):
        return await ctx.send(embed=discord.Embed(description="🐦\u200d⬛ Le corbeau tourne la tête — il a déjà mangé !", color=0x95a5a6), delete_after=5)
    data["nourri"] = True
    msg = await ctx.send(embed=discord.Embed(description="🐦\u200d⬛ *Tu sors quelques graines...*", color=0x2c2f33))
    await asyncio.sleep(1)
    await msg.edit(embed=discord.Embed(description="🐦\u200d⬛ *Le corbeau s\'approche prudemment...*", color=0x2c2f33))
    await asyncio.sleep(1)
    await msg.edit(embed=discord.Embed(description="🐦\u200d⬛ *Il picore dans ta main...*", color=0x2c2f33))
    await asyncio.sleep(1)
    if data["humeur"] == "grognon":
        data["humeur"] = "généreux"
        await msg.edit(embed=discord.Embed(title="🐦\u200d⬛ Le corbeau est apaisé !", description=f"{ctx.author.mention} son humeur change... il devient **généreux** 💰", color=0x2ecc71))
    else:
        data["reserve"] = data.get("reserve", 0) + 50
        await msg.edit(embed=discord.Embed(title="🐦\u200d⬛ Le corbeau est nourri !", description=f"{ctx.author.mention} il penche la tête avec satisfaction...\n**+50 pièces** en réserve ! `.recup` pour les récupérer", color=0x2ecc71))

@bot.command(name="caresser")
async def caresser_cmd(ctx):
    gid = ctx.guild.id
    if gid not in canard_actif or not canard_actif[gid].get("proprio"):
        return await ctx.send("❌ T\'as pas de corbeau !", delete_after=5)
    if str(ctx.author.id) != canard_actif[gid]["proprio"]:
        return await ctx.send("❌ C\'est pas ton corbeau !", delete_after=5)
    data = canard_actif[gid]
    if data.get("caresse"):
        return await ctx.send(embed=discord.Embed(description="🐦\u200d⬛ Le corbeau s\'éloigne — assez de caresses pour aujourd\'hui.", color=0x95a5a6), delete_after=5)
    data["caresse"] = True
    msg = await ctx.send(embed=discord.Embed(description="🐦\u200d⬛ *Tu tends la main doucement...*", color=0x2c2f33))
    await asyncio.sleep(1)
    await msg.edit(embed=discord.Embed(description="🐦\u200d⬛ *Il ferme les yeux...*", color=0x2c2f33))
    await asyncio.sleep(1)
    await msg.edit(embed=discord.Embed(description="🐦\u200d⬛ *Un lien se forme entre vous...*", color=0x9b59b6))
    await asyncio.sleep(1)
    xp_gain = _r.randint(30, 80)
    data["reserve_xp"] = data.get("reserve_xp", 0) + xp_gain
    await msg.edit(embed=discord.Embed(title="🐦\u200d⬛ Le corbeau te fait confiance !", description=f"{ctx.author.mention} il se blottit contre toi...\n**+{xp_gain} XP** en réserve ! `.recup` pour les récupérer", color=0x9b59b6))

@bot.command(name="recup", aliases=["recuperer"])
async def recup_cmd(ctx):
    gid = ctx.guild.id
    if gid not in canard_actif or not canard_actif[gid].get("proprio"):
        return await ctx.send("❌ T\'as pas de corbeau actif !", delete_after=5)
    if str(ctx.author.id) != canard_actif[gid]["proprio"]:
        return await ctx.send("❌ C\'est pas ton corbeau !", delete_after=5)
    data = canard_actif[gid]
    uid = str(ctx.author.id)
    if not data.get("reserve") and not data.get("reserve_xp") and not data.get("reserve_amelio"):
        return await ctx.send(embed=discord.Embed(description="🐦\u200d⬛ *Le corbeau secoue la tête — rien à récupérer pour l\'instant...*", color=0x95a5a6), delete_after=5)
    msg = await ctx.send(embed=discord.Embed(description="🐦\u200d⬛ *Le corbeau dépose ses trouvailles à tes pieds...*", color=0x2c2f33))
    await asyncio.sleep(1.5)
    desc = ""
    if data.get("reserve", 0) > 0:
        gain_pieces = data["reserve"]
        economy_data[uid]["coins"] += gain_pieces
        desc += f"💰 **+{gain_pieces} pièces**\n"
        data["reserve"] = 0
    if data.get("reserve_xp", 0) > 0:
        gain_xp = data["reserve_xp"]
        xp_data[uid]["xp"] += gain_xp
        desc += f"⭐ **+{gain_xp} XP**\n"
        data["reserve_xp"] = 0
    if data.get("reserve_amelio", 0) > 0:
        points_amelio[uid] = points_amelio.get(uid, 0) + 1
        desc += "💎 **+1 point d\'amélioration** !\n"
        data["reserve_amelio"] = 0
    await msg.edit(embed=discord.Embed(title="🐦\u200d⬛ Récolte du Corbeau !", description=f"{ctx.author.mention} récupère :\n\n{desc}\n*Le corbeau incline la tête fièrement.*", color=0xf1c40f))



@bot.event
async def on_raw_reaction_add(payload):
    """Gère les réactions — règlement, autoroles, panels"""
    if payload.user_id == bot.user.id:
        return
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    member = guild.get_member(payload.user_id)
    if not member or member.bot:
        return
    emoji = str(payload.emoji)
    msg_id = payload.message_id

    # ── Règlement ──────────────────────────────────────────
    if REGLEMENT_MSG_ID and msg_id == int(REGLEMENT_MSG_ID):
        if emoji == "✅" and REGLEMENT_ROLE_ID:
            role = guild.get_role(int(REGLEMENT_ROLE_ID))
            if role:
                try:
                    await member.add_roles(role)
                except:
                    pass
        return

    # ── Autorole panels ────────────────────────────────────
    gid = str(guild.id)
    panels = autorole_panels.get(guild.id, autorole_panels.get(gid, []))
    for panel in panels:
        if panel.get("message_id") == msg_id:
            for role_data in panel.get("roles", []):
                if str(role_data.get("emoji")) == emoji:
                    role = guild.get_role(int(role_data["role_id"]))
                    if role:
                        try:
                            await member.add_roles(role)
                            ch = guild.get_channel(payload.channel_id)
                            if ch:
                                await ch.send(f"✅ Rôle **{role.name}** attribué à {member.mention} !", delete_after=4)
                        except:
                            pass
                    return

    # ── Reaction roles ─────────────────────────────────────
    if msg_id in reaction_roles:
        data = reaction_roles[msg_id]
        role_id = data.get(emoji)
        if role_id:
            role = guild.get_role(int(role_id))
            if role:
                try:
                    await member.add_roles(role)
                except:
                    pass

@bot.event
async def on_raw_reaction_remove(payload):
    """Retire les rôles quand la réaction est supprimée"""
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    member = guild.get_member(payload.user_id)
    if not member or member.bot:
        return
    emoji = str(payload.emoji)
    msg_id = payload.message_id

    # ── Règlement ──────────────────────────────────────────
    if REGLEMENT_MSG_ID and msg_id == int(REGLEMENT_MSG_ID):
        if emoji == "✅" and REGLEMENT_ROLE_ID:
            role = guild.get_role(int(REGLEMENT_ROLE_ID))
            if role:
                try:
                    await member.remove_roles(role)
                except:
                    pass
        return

    # ── Autorole panels ────────────────────────────────────
    gid = str(guild.id)
    panels = autorole_panels.get(guild.id, autorole_panels.get(gid, []))
    for panel in panels:
        if panel.get("message_id") == msg_id:
            for role_data in panel.get("roles", []):
                if str(role_data.get("emoji")) == emoji:
                    role = guild.get_role(int(role_data["role_id"]))
                    if role:
                        try:
                            await member.remove_roles(role)
                            ch = guild.get_channel(payload.channel_id)
                            if ch:
                                await ch.send(f"❌ Rôle **{role.name}** retiré à {member.mention}", delete_after=4)
                        except:
                            pass
                    return

    # ── Reaction roles ─────────────────────────────────────
    if msg_id in reaction_roles:
        data = reaction_roles[msg_id]
        role_id = data.get(emoji)
        if role_id:
            role = guild.get_role(int(role_id))
            if role:
                try:
                    await member.remove_roles(role)
                except:
                    pass

@bot.event
async def on_member_join(member):
    """Accueille les nouveaux membres"""
    guild = member.guild
    # Message de bienvenue
    if SALON_BIENVENUE_ID:
        channel = guild.get_channel(SALON_BIENVENUE_ID)
        if channel:
            embed = discord.Embed(
                title=f"🌸 Bienvenue {member.display_name} !",
                description=(
                    f"{member.mention} vient de rejoindre **{guild.name}** !\n\n"
                    f"📖 Lis le règlement pour obtenir accès au serveur\n"
                    f"🎰 Tape `.help` pour voir toutes les commandes\n"
                    f"🎴 Tape `.ga` pour ton premier roll gacha !"
                ),
                color=0xff6b9d
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await channel.send(embed=embed)
    # Rôle automatique si configuré
    if ROLE_MEMBRE_NAME:
        role = discord.utils.get(guild.roles, name=ROLE_MEMBRE_NAME)
        if role:
            try:
                await member.add_roles(role)
            except:
                pass

@bot.event
async def on_member_remove(member):
    """Message d'au revoir"""
    guild = member.guild
    if SALON_AUREVOIR_ID:
        channel = guild.get_channel(SALON_AUREVOIR_ID)
        if channel:
            embed = discord.Embed(
                description=f"👋 **{member.display_name}** a quitté le serveur...",
                color=0x95a5a6
            )
            await channel.send(embed=embed)


@bot.command(name="planning", aliases=["agenda","events","calendrier"])
async def planning_cmd(ctx):
    """Voir le planning des events — .planning"""
    import datetime as _dt
    now = _dt.datetime.now()
    weekday = now.weekday()
    semaine = now.isocalendar()[1]

    ROTATION_WEEKEND = [
        ("⚔️ Tournoi du QG",        "tournoi"),
        ("💀 Death Note",            "deathnote"),
        ("🌍 Conquête du QG",        "conquete"),
        ("⚡ Enchères Interdites",   "encheres"),
        ("🕵️ Parmi Nous",            "parminous"),
        ("🧩 Puzzle Collectif",      "puzzle"),
    ]
    idx_ven = semaine % len(ROTATION_WEEKEND)
    idx_sam = (semaine + 2) % len(ROTATION_WEEKEND)
    idx_dim = (semaine + 4) % len(ROTATION_WEEKEND)
    if idx_sam == idx_ven: idx_sam = (idx_sam + 1) % len(ROTATION_WEEKEND)
    if idx_dim == idx_ven or idx_dim == idx_sam: idx_dim = (idx_dim + 2) % len(ROTATION_WEEKEND)

    ev_ven = ROTATION_WEEKEND[idx_ven][0]
    ev_sam = ROTATION_WEEKEND[idx_sam][0]
    ev_dim = ROTATION_WEEKEND[idx_dim][0]

    jours = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]

    hebdo = (
        f"**Lundi** → 🔮 Prophétie • 📦 Coffre 18h • 🎲 Event léger 20h\n"
        f"**Mardi** → 🌙 Nuit de Chasse OU 🕶️ Marché Noir 20h\n"
        f"**Mercredi** → 🌙 Heure Maudite 2h • 📦 Coffre 20h\n"
        f"**Jeudi** → 🎲 Event léger 20h • 🎰 Nuit Casino 21h\n"
        f"**Vendredi** → 🎴 Carte Mystère 18h • **{ev_ven}** 20h 🔥\n"
        f"**Samedi** → 🎭 Imposteur 15h • **{ev_sam}** 20h 🔥 • ⚠️ Invasion Boss 23h\n"
        f"**Dimanche** → 📦 Coffre 16h • **{ev_dim}** 17h 🔥 • 🎁 Colis 19h • 🏆 Classement 20h"
    )

    mensuel = (
        f"**1er** → 💸 Jackpot 5000p\n"
        f"**8** → 🃏 Draft de Cartes\n"
        f"**15** → 🏴\u200d☠️ Guerre des Factions + 👾 Boss Final\n"
        f"**22** → 🎪 Event Surprise + 👾 Boss Final\n"
        f"**Dernier vendredi** → 🌊 Vague de Légendes"
    )

    jour_actuel = jours[weekday]
    embed = discord.Embed(
        title="📅 PLANNING DES EVENTS",
        color=0x3498db
    )
    embed.add_field(name=f"📆 Cette semaine *(aujourd\'hui : {jour_actuel})*", value=hebdo, inline=False)
    embed.add_field(name="📆 Ce mois-ci", value=mensuel, inline=False)
    embed.set_footer(text="Les gros events du weekend changent chaque semaine 🔄")
    await ctx.send(embed=embed)


@bot.command(name="setimages", aliases=["massimages","bulkimages"])
@commands.has_permissions(administrator=True)
async def setimages_cmd(ctx, *, data: str = None):
    """Ajouter des images en masse — .setimages Nom1 URL1\nNom2 URL2"""
    if not data:
        return await ctx.send(
            "❌ Usage : `.setimages Nom1 URL1\nNom2 URL2`\n"
            "Exemple :\n```\n.setimages\nGoku https://i.imgur.com/xxx.jpg\nVegeta https://i.imgur.com/yyy.jpg\n```"
        )
    lines = [l.strip() for l in data.strip().split("\n") if l.strip()]
    updated = 0
    not_found = []
    for line in lines:
        parts = line.rsplit(" ", 1)
        if len(parts) != 2:
            continue
        nom, url = parts
        nom = nom.strip()
        url = url.strip()
        if not url.startswith("http"):
            continue
        # Chercher dans ANIME_CARDS_DB (insensible à la casse)
        found = False
        for key, card in ANIME_CARDS_DB.items():
            if card["nom"].lower() == nom.lower():
                ANIME_CARDS_DB[key]["image"] = url
                updated += 1
                found = True
                break
        if not found:
            not_found.append(nom)
    msg = f"✅ **{updated}** image(s) mise(s) à jour !"
    if not_found:
        msg += f"\n⚠️ Introuvables : {", ".join(not_found[:10])}"
        if len(not_found) > 10:
            msg += f" *(+{len(not_found)-10} autres)*"
    await ctx.send(msg)


@bot.command(name="shop", aliases=["boutique","magasin","store"])
async def shop_cmd(ctx):
    """Afficher la boutique — .shop"""
    cats = {
        "role":    ("🏷️ Rôles Exclusifs",   []),
        "boost":   ("🚀 Boosts Gacha",       []),
        "pvp":     ("⚔️ Items PvP",           []),
        "protect": ("🛡️ Protection",          []),
        "special": ("✨ Spéciaux",            []),
    }
    for item in SHOP_ITEMS:
        cat = item.get("cat", "special")
        if cat in cats:
            cats[cat][1].append(item)

    uid = str(ctx.author.id)
    solde = economy_data[uid]["coins"]

    embed = discord.Embed(
        title="🛒 BOUTIQUE DU QG",
        description=f"Ton solde : **{solde:,} pièces** 💰\n\n`.acheter <id>` pour acheter !",
        color=0x9b59b6
    )
    for cat_key, (cat_nom, items) in cats.items():
        if not items: continue
        lines = []
        for item in items:
            daily_tag = " *(1x/jour)*" if item.get("daily") else ""
            lines.append(f"`{item['id']}` — **{item['nom']}** {item['prix']:,}p{daily_tag}\n*{item['desc']}*")
        embed.add_field(name=cat_nom, value="\n".join(lines), inline=False)
    embed.set_footer(text="Prix en pièces | Items 1x/jour = se renouvellent chaque jour")
    await ctx.send(embed=embed)


@bot.command(name="cardlist", aliases=["cartelist","allcards","listecarte"])
@commands.has_permissions(administrator=True)
async def cardlist_cmd(ctx, rarete: str = None, *, serie: str = None):
    """Voir toutes les cartes du DB — .cardlist [rarete] [serie]"""
    cards = list(ANIME_CARDS_DB.items())
    if rarete:
        r_map = {"m": "Mythique", "l": "Légendaire", "e": "Épique", "r": "Rare", "c": "Commun",
                 "mythique":"Mythique","legendaire":"Légendaire","epique":"Épique","rare":"Rare","commun":"Commun"}
        r_filter = r_map.get(rarete.lower(), rarete.title())
        cards = [(k,v) for k,v in cards if v.get("rarete") == r_filter]
    if serie:
        cards = [(k,v) for k,v in cards if serie.lower() in v.get("serie","").lower()]

    if not cards:
        return await ctx.send("❌ Aucune carte trouvée avec ces critères !")

    # Paginer par 20
    per_page = 20
    pages = [cards[i:i+per_page] for i in range(0, len(cards), per_page)]
    page_num = 0

    def make_embed(page_cards, page_idx):
        desc = ""
        for key, c in page_cards:
            img_status = "🖼️" if c.get("image") else "📭"
            r_emoji = RARETE_EMOJI.get(c.get("rarete",""), "⚪")
            desc += f"{img_status} `{key}` — **{c['nom']}** {r_emoji} *{c.get('serie','')}*\n"
        embed = discord.Embed(
            title=f"📋 Cartes du DB ({len(cards)} total)",
            description=desc,
            color=0x9b59b6
        )
        embed.set_footer(text=f"Page {page_idx+1}/{len(pages)} | 🖼️ = image | 📭 = pas d\'image")
        return embed

    msg = await ctx.send(embed=make_embed(pages[0], 0))
    if len(pages) > 1:
        await msg.add_reaction("⬅️")
        await msg.add_reaction("➡️")

        def check(r, u):
            return u == ctx.author and str(r.emoji) in ["⬅️","➡️"] and r.message.id == msg.id

        import asyncio
        while True:
            try:
                reaction, user = await bot.wait_for("reaction_add", timeout=60.0, check=check)
                if str(reaction.emoji) == "➡️" and page_num < len(pages)-1:
                    page_num += 1
                elif str(reaction.emoji) == "⬅️" and page_num > 0:
                    page_num -= 1
                await msg.edit(embed=make_embed(pages[page_num], page_num))
                try: await msg.remove_reaction(reaction.emoji, user)
                except: pass
            except asyncio.TimeoutError:
                break


print("🚀 Démarrage du bot...")
import traceback, time
while True:
    try:
        bot.run(TOKEN)
    except Exception as e:
        print(f"❌ CRASH BOT: {e}")
        traceback.print_exc()
        print("🔄 Redémarrage dans 5 secondes...")
        time.sleep(5) 
