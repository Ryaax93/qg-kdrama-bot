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
        "SALON_BOUTIQUE_ID":  SALON_BOUTIQUE_ID,
        "SALON_COMBAT_ID":    SALON_COMBAT_ID,
        "SALON_DUEL_ID":      SALON_DUEL_ID,
        "SALON_BIENVENUE_ID": SALON_BIENVENUE_ID,
        "SALON_AUREVOIR_ID":  SALON_AUREVOIR_ID,
        "SALON_BOOST_ID":     SALON_BOOST_ID,
        "SALON_HOF_ID":       SALON_HOF_ID,
        "SALON_REGLEMENT_ID": SALON_REGLEMENT_ID,
        "ROLE_MEMBRE_NAME":   ROLE_MEMBRE_NAME,
        "REGLEMENT_ROLE_ID":   REGLEMENT_ROLE_ID,
        "REGLEMENT_MSG_ID":   REGLEMENT_MSG_ID,
    }
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"[Config] Erreur sauvegarde : {e}")

def charger_salons():
    """Charge les IDs de salons depuis le fichier JSON au démarrage"""
    global SALON_LEVELUP_ID, SALON_CASINO_ID, SALON_GACHA_ID, SALON_BOUTIQUE_ID
    global SALON_COMBAT_ID, SALON_DUEL_ID, SALON_BIENVENUE_ID, SALON_AUREVOIR_ID
    global SALON_BOOST_ID, SALON_HOF_ID, SALON_REGLEMENT_ID, ROLE_MEMBRE_NAME, REGLEMENT_ROLE_ID, REGLEMENT_MSG_ID
    if not os.path.exists(CONFIG_FILE):
        return
    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
        SALON_LEVELUP_ID   = data.get("SALON_LEVELUP_ID")
        SALON_CASINO_ID    = data.get("SALON_CASINO_ID")
        SALON_GACHA_ID     = data.get("SALON_GACHA_ID")
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
        REGLEMENT_ROLE_ID  = data.get("REGLEMENT_ROLE_ID")
        REGLEMENT_MSG_ID   = data.get("REGLEMENT_MSG_ID")
        print("[Config] Salons chargés depuis salons_config.json ✅")
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
    xp_data[uid]["xp"] += random.randint(2, 5)
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

    # ── Définition des pages ──────────────────────────────────────
    pages = []

    # Page 0 — Accueil
    p0 = discord.Embed(
        title="🌸 Akari — Bot du QG Kdrama",
        description=(
            "Bienvenue ! Utilise les boutons ◀️ ▶️ pour naviguer entre les catégories.\n\n"
            "**Préfixe : `.`**\n\n"
            "📌 **Catégories disponibles :**\n"
            "🎬 Contenu • 🎮 Gacha • ⚔️ Combats & Jeux\n"
            "💰 Économie • 📊 Progression • 💬 Social\n"
            "😄 Fun • 🛡️ Modération • 🔧 Utilitaires"
        ),
        color=0xff6b9d
    )
    p0.set_footer(text="Page 1/9 • QG Kdrama 🌸")
    pages.append(p0)

    # Page 1 — Contenu
    p1 = discord.Embed(title="🎬 Contenu — Dramas & Animés", color=0xff6b9d)
    p1.add_field(name="🎬 Dramas", value=(
        "`.drama <titre>` — Infos sur un drama\n"
        "`.dramarec` — Recommandation drama aléatoire\n"
        "`.quote` — Citation aléatoire animé ou kdrama"
    ), inline=False)
    p1.add_field(name="✨ Animés", value=(
        "`.anime <titre>` — Infos sur un animé\n"
        "`.animerec` — Recommandation animé aléatoire\n"
        "`.animequote` — Citation animé aléatoire"
    ), inline=False)
    p1.add_field(name="⭐ Notes & Avis", value=(
        "`.noter 9 Goblin` — Note un drama/animé /10\n"
        "`.avis Goblin` — Voir la moyenne du serveur"
    ), inline=False)
    p1.add_field(name="📋 Watchlist", value=(
        "`.watch ajouter <titre>` — Ajouter\n"
        "`.watch liste` — Voir ta liste\n"
        "`.watch vu <titre>` — Marquer comme vu ✅\n"
        "`.watch supprimer <titre>` — Retirer"
    ), inline=False)
    p1.add_field(name="📅 Sorties & Sondages", value=(
        "`.sorties` — Prochaines sorties kdramas & animés\n"
        "`.sondage <question>` — Créer un sondage rapide"
    ), inline=False)
    p1.set_footer(text="Page 2/9 • QG Kdrama 🌸")
    pages.append(p1)

    # Page 2 — Gacha
    p2 = discord.Embed(title="🎰 Gacha — Style Mudae", color=0x9b59b6)
    p2.add_field(name="🎲 Tirer & Claimer", value=(
        "`.ga` `.g` `.roll` `.r` — Tire une carte (10 rolls/6h)\n"
        "`.rolls` `.ro` — Voir tes rolls & cooldowns\n"
        "`.daily` — 150-300 pièces + 1 roll bonus (24h)"
    ), inline=False)
    p2.add_field(name="📦 Collection", value=(
        "`.gachastock` `.gs` `.coll` [@joueur] — Ta collection ◀️ ▶️\n"
        "`.gacha <perso>` `.gc <perso>` — Voir qui possède la carte\n"
        "`.gacha recent` — Dernières cartes claimées\n"
        "`.gacha ordre naruto 1 luffy 2` — Réorganiser ta collection"
    ), inline=False)
    p2.add_field(name="⭐ Fusion & Boost", value=(
        "`.fusionner <perso>` `.fus` `.fusion` — Booste une carte avec des tokens\n"
        "🔮 Mythique 0.01% • 👑 Légendaire 0.5% • 💜 Épique 3%\n"
        "⭐ Rare 20% • 🔵 Commun 76.49%"
    ), inline=False)
    p2.add_field(name="💫 Wishlist", value=(
        "`.wishlist add <perso>` `.wl add` — Ajouter à ta wishlist\n"
        "`.wishlist remove <perso>` — Retirer\n"
        "`.wishlist` `.wl` — Voir ta liste (max 10)\n"
        "🔔 Tu seras pingé dès que le perso drop !"
    ), inline=False)
    p2.add_field(name="🖼️ Image", value=(
        "`.setimage <perso> <url>` — Change l'image de ta carte\n"
        "*Uniquement si tu possèdes la carte !*"
    ), inline=False)
    p2.set_footer(text="Page 3/8 • QG Kdrama 🌸")
    pages.append(p2)

    # Page 3 — Combats & Jeux
    p3 = discord.Embed(title="⚔️ Combats & Jeux", color=0xe74c3c)
    p3.add_field(name="🃏 Combat Cartes", value=(
        "`.pokebattle @joueur` — Combat 3v3 avec tes cartes claimées !"
    ), inline=False)
    p3.add_field(name="⚔️ Duels & Boss", value=(
        "`.duel @joueur` — Défi rapide\n"
        "`.arene @joueur` — Combat PvP tour par tour\n"
        "`.boss` — Faire apparaître un boss (admin)\n"
        "`.attaque` — Frapper le boss ! (cooldown 13s)"
    ), inline=False)
    p3.add_field(name="🎯 Quiz", value=(
        "`.quiz [thème]` — Quiz solo qui s'enchaîne auto !\n"
        "`.quizduel [thème] @joueur` — Duel 5 questions\n"
        "`.quizstop` — Arrêter le quiz\n"
        "*Thèmes : kdrama • anime • gaming • culture • mix*"
    ), inline=False)
    p3.add_field(name="🎬 Bracket Tournoi", value=(
        "`.bracket kdrama` — Tournoi Kdramas\n"
        "`.bracket anime` — Tournoi Animés\n"
        "`.bracketskip` — Passer (admin) • `.bracketstop` — Annuler"
    ), inline=False)
    p3.add_field(name="🐺 Loup Garou", value=(
        "`.lgcreate` `.lgjoin` `.lgstart` `.lgstop`\n"
        "`.lg` — Aide complète • `.lgroles` — Voir les rôles"
    ), inline=False)
    p3.add_field(name="🎭 Mini-Jeux", value=(
        "`.devine` — Devine le personnage\n"
        "`.pendu` — Pendu animé/drama\n"
        "`.rps <choix>` — Pierre Feuille Ciseaux\n"
        "`.dice [faces]` — Lancer un dé"
    ), inline=False)
    p3.set_footer(text="Page 4/8 • QG Kdrama 🌸")
    pages.append(p3)

    # Page 4 — Économie
    p4 = discord.Embed(title="💰 Économie & Récompenses", color=0xf39c12)
    p4.add_field(name="💵 Pièces", value=(
        "`.daily` — 150-300 pièces + 1 roll gacha ⏳ 24h\n"
        "`.balance [@joueur]` — Voir ton solde\n"
        "`.pay @joueur <montant>` — Envoyer des pièces\n"
        "`.steal @joueur` — Vol (45% réussite, cooldown 1h)"
    ), inline=False)
    p4.add_field(name="🏦 Banque", value=(
        "`.banque depot <montant>` — Déposer\n"
        "`.banque retrait` — Retirer + intérêts\n"
        "`.banque solde` — Voir le solde\n"
        "📈 Intérêts : +5% toutes les 24h !"
    ), inline=False)
    p4.add_field(name="🎰 Casino", value=(
        "`.slot [mise]` — Slot machine\n"
        "Min 10p • Max 500p • Salon casino uniquement !"
    ), inline=False)
    p4.add_field(name="🛒 Boutique", value=(
        "`.shop` — Voir tous les items\n"
        "`.acheter <id>` — Acheter un item\n"
        "`.utiliser freeze @joueur` — Sceau des Ombres 🧊\n"
        "`.utiliser curse @joueur` — Malédiction ⏳"
    ), inline=False)
    p4.add_field(name="💡 Sources de pièces", value=(
        "`.daily` • Quiz • Arène • Duel • Boss"
    ), inline=False)
    p4.set_footer(text="Page 5/8 • QG Kdrama 🌸")
    pages.append(p4)

    # Page 5 — Progression
    p5 = discord.Embed(title="📊 Progression — XP & Niveaux", color=0xf1c40f)
    p5.add_field(name="Commandes", value=(
        "`.rank [@joueur]` — Ton niveau, XP et titre\n"
        "`.leaderboard` — Top 10 membres les plus actifs"
    ), inline=False)
    p5.add_field(name="📈 Gagner de l'XP", value=(
        "• Chatter → 2-5 XP/message\n"
        "• Gagner un quiz → +30 XP\n"
        "• Gagner une arène → +40 XP\n"
        "• Tuer un boss → +50 XP\n"
        "• Claimer une carte → +20 XP"
    ), inline=False)
    p5.add_field(name="🏆 Titres", value=(
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
    p5.set_footer(text="Page 6/8 • QG Kdrama 🌸")
    pages.append(p5)

    # Page 6 — Social & Fun
    p6 = discord.Embed(title="💬 Social & Fun", color=0xff6b9d)
    p6.add_field(name="💍 Mariage", value=(
        "`.marier @joueur` — Demande en mariage\n"
        "`.accepter` / `.refuser` — Répondre\n"
        "`.divorcer` — Divorce 💔"
    ), inline=False)
    p6.add_field(name="🎂 Anniversaires", value=(
        "`.anniversaire JJ/MM` — Enregistrer ton anniv\n"
        "`.anniversaire` — Voir tous les anniversaires"
    ), inline=False)
    p6.add_field(name="📊 Communauté", value=(
        "`.sondage \"Question?\" choix1 choix2` — Sondage\n"
        "`.giveaway <durée> <prix>` — Giveaway (admin)\n"
        "`.stats` — Statistiques du serveur"
    ), inline=False)
    p6.add_field(name="😄 Fun", value=(
        "`.roast [@joueur]` — Vanne façon Kdrama\n"
        "`.compliment [@joueur]` — Compliment stylé\n"
        "`.8ball <question>` — Boule magique !\n"
        "`.meme` — Meme aléatoire 😂"
    ), inline=False)
    p6.add_field(name="🎫 Support", value=(
        "`.ticket` — Ouvrir un ticket d'aide\n"
        "`.close` — Fermer un ticket (staff)"
    ), inline=False)
    p6.set_footer(text="Page 7/8 • QG Kdrama 🌸")
    pages.append(p6)

    # Page 7 — Modération
    p7 = discord.Embed(
        title="🛡️ Modération & Configuration",
        description="⚠️ Réservé aux **administrateurs**",
        color=0xe74c3c
    )
    p7.add_field(name="⚔️ Sanctions", value=(
        "`.ban @joueur [raison]` — Bannir\n"
        "`.kick @joueur [raison]` — Expulser + MP au membre\n"
        "`.warn @joueur [raison]` — Avertir + MP au membre\n"
        "`.mute @joueur [minutes]` — Rendre muet\n"
        "`.unmute @joueur` — Retirer le mute"
    ), inline=False)
    p7.add_field(name="🔧 Gestion Salon", value=(
        "`.clear [nombre]` `.clear all` — Supprimer X messages ou tous\n"
        "`.slowmode [secondes]` — Activer le slowmode\n"
        "`.lock [#salon]` — Verrouiller un salon\n"
        "`.unlock [#salon]` — Déverrouiller un salon"
    ), inline=False)
    p7.add_field(name="🎁 Cartes", value=(
        "`.givecard @joueur <perso>` — Donner une carte\n"
        "`.removecard @joueur <perso>` — Retirer une carte"
    ), inline=False)
    p7.add_field(name="📌 Salons — `.setsalon <type>`", value=(
        "`bienvenue` 🎌 • `aurevoir` 💔 • `boost` 💎\n"
        "`gacha` 🎰 • `boutique` 🛒 • `casino` 🎲\n"
        "`combat` ⚔️ • `duel` ⚔️ • `levelup` 📊\n"
        "`halloffame` 🏆 • `reglement @Role` 📜"
    ), inline=False)
    p7.add_field(name="🛡️ Anti-Raid", value=(
        "`.raidstop` — Désactiver le mode anti-raid\n"
        "*Détection auto : 5+ joins en 10 secondes*"
    ), inline=False)
    p7.set_footer(text="Page 8/9 • QG Kdrama 🌸")
    pages.append(p7)

    # Page 8 — Utilitaires
    p8 = discord.Embed(title="🔧 Utilitaires", color=0x3498db)
    p8.add_field(name="🖼️ Profil & Info", value=(
        "`.avatar [@membre]` — Affiche l'avatar d'un membre\n"
        "`.snipe` — Dernier message supprimé du salon\n"
        "`.invitations [@membre]` — Voir le nombre d'invitations\n"
        "`.topinvitations` — Classement des meilleurs inviteurs\n"
        "`.setinvitation` — Salon logs invitations (admin)"
    ), inline=False)
    p8.add_field(name="🎲 Outils", value=(
        "`.choisir <ID message>` — Gagnant aléatoire parmi les réactions\n"
        "`.sondage <question>` — Créer un sondage rapide\n"
        "`.8ball <question>` — Boule magique\n"
        "`.dice [faces]` — Lancer un dé"
    ), inline=False)
    p8.add_field(name="💑 Social", value=(
        "`.marier @membre` — Demande en mariage\n"
        "`.divorcer` — Divorce\n"
        "`.anniversaire <JJ/MM>` — Enregistre ton anniversaire\n"
        "`.giveaway <durée> <prix>` — Lancer un giveaway"
    ), inline=False)
    p8.add_field(name="🎭 Autorole (Admin)", value=(
        "`.autorole create <titre> | <desc>` — Crée un panel\n"
        "`.autorole add <msg_id> <emoji> @role <label>` — Ajoute un rôle\n"
        "`.autorole image <msg_id> <url>` — Ajoute une image/gif\n"
        "`.autorole delete <msg_id>` — Supprime un panel\n"
        "`.autorole list` — Voir les panels actifs"
    ), inline=False)
    p8.add_field(name="🎲 Outils", value=(
        "`.choisir <ID message>` — Choisit un gagnant parmi les réactions\n"
        "`.sondage <question>` — Crée un sondage rapide\n"
        "`.8ball <question>` — Boule magique\n"
        "`.dice [faces]` — Lancer un dé"
    ), inline=False)
    p8.add_field(name="💑 Social", value=(
        "`.marier @membre` — Demande en mariage\n"
        "`.divorcer` — Divorce\n"
        "`.anniversaire <JJ/MM>` — Enregistre ton anniversaire\n"
        "`.giveaway <durée> <prix>` — Lancer un giveaway"
    ), inline=False)
    p8.set_footer(text="Page 9/9 • QG Kdrama 🌸")
    pages.append(p8)

    # ── Navigation ────────────────────────────────────────────────
    index = [0]
    msg = await ctx.send(embed=pages[0])
    await msg.add_reaction("◀️")
    await msg.add_reaction("▶️")

    def check(reaction, user):
        return (
            user == ctx.author
            and reaction.message.id == msg.id
            and str(reaction.emoji) in ["◀️", "▶️"]
        )

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

# ── setimage ──────────────────────────────────────────────────────
@bot.command(name="setimage")
async def setimage_cmd(ctx, perso: str = None, url: str = None):
    """Change l'image d'une carte que tu possèdes — .setimage naruto https://i.imgur.com/xxx.jpg"""
    if SALON_GACHA_ID and ctx.channel.id != SALON_GACHA_ID:
        salon = ctx.guild.get_channel(SALON_GACHA_ID)
        mention = salon.mention if salon else "le salon gacha"
        return await ctx.send(f"🎰 Cette commande c'est dans {mention} !", delete_after=5)

    if not perso or not url:
        return await ctx.send("❌ Usage : `.setimage <perso> <url imgur>`\nEx: `.setimage naruto https://i.imgur.com/xxx.jpg`")

    # Nettoyer l'URL des caractères parasites Discord (__, **, <>, espaces)
    url = url.strip().strip("_").strip("*").strip("<").strip(">").strip()
    if not url.startswith("https://i.imgur.com/"):
        return await ctx.send("❌ Utilise uniquement des liens **imgur** ! (https://i.imgur.com/...)")

    uid = str(ctx.author.id)
    key = perso.lower().strip()

    if key not in ANIME_CARDS_DB:
        matches = [k for k in ANIME_CARDS_DB if perso.lower() in ANIME_CARDS_DB[k]["nom"].lower()]
        if not matches:
            return await ctx.send(f"❌ Personnage `{perso}` introuvable !")
        key = matches[0]

    # Vérifier que le joueur possède la carte
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


@bot.command()
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
@bot.command()
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



@bot.command()
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
#  ÉCONOMIE
# ============================================================
@bot.command()
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

@bot.command()
async def balance(ctx, member: discord.Member = None):
    member = member or ctx.author
    coins = economy_data[str(member.id)]["coins"]
    await ctx.send(embed=discord.Embed(
        description=f"💳 **{member.display_name}** possède **{coins} pièces**.",
        color=0xf39c12
    ))

@bot.command()
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
@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="Aucune raison fournie"):
    await member.ban(reason=reason)
    await ctx.send(embed=discord.Embed(description=f"🔨 **{member}** banni. Raison : {reason}", color=0xe74c3c))

@bot.command()
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

@bot.command()
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

@bot.command()
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
@bot.command()
async def roast(ctx, member: discord.Member = None):
    target = member or ctx.author
    await ctx.send(embed=discord.Embed(
        description=f"🔥 {target.mention} : {random.choice(ROASTS_QG)}",
        color=0xe74c3c
    ))

@bot.command()
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

@bot.command()
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

@bot.command()
async def dice(ctx, faces: int = 6):
    await ctx.send(embed=discord.Embed(
        description=f"🎲 Tu lances un dé à {faces} faces... **{random.randint(1, faces)}** !",
        color=0xe67e22
    ))

@bot.command()
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
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Permission refusée.")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Membre introuvable.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Argument manquant. Tape `.help` pour voir les commandes.")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        await ctx.send(f"❌ Erreur : `{error}`")

# ============================================================
#  🐺 LOUP GAROU — Système complet
# ============================================================

# Rôles disponibles et leurs descriptions
LG_ROLES = {
    "Loup Garou":     {"emoji": "🐺", "team": "loups",    "count": 0, "desc": "Chaque nuit, élimine un villageois avec les autres loups."},
    "Villageois":     {"emoji": "👨‍🌾", "team": "village",  "count": 0, "desc": "Pas de pouvoir spécial, mais ton vote compte !"},
    "Voyante":        {"emoji": "🔮", "team": "village",  "count": 0, "desc": "Chaque nuit, découvre le rôle d'un joueur."},
    "Sorcière":       {"emoji": "🧙‍♀️", "team": "village",  "count": 0, "desc": "Une potion de vie et une potion de mort à utiliser une fois chacune."},
    "Chasseur":       {"emoji": "🏹", "team": "village",  "count": 0, "desc": "Quand tu meurs, tu peux emporter quelqu'un avec toi."},
    "Cupidon":        {"emoji": "💘", "team": "village",  "count": 0, "desc": "La première nuit, lie deux joueurs en amoureux. Ils meurent ensemble."},
    "Petite Fille":   {"emoji": "👧", "team": "village",  "count": 0, "desc": "Peut espionner les loups la nuit, mais risque d'être tuée si repérée."},
    "Loup Blanc":     {"emoji": "🤍🐺", "team": "loup_blanc","count": 0, "desc": "Loup solitaire ! Une nuit sur deux, peut tuer un loup garou."},
}

# Composition par nombre de joueurs
LG_COMPOS = {
    5:  ["Loup Garou", "Voyante", "Villageois", "Villageois", "Villageois"],
    6:  ["Loup Garou", "Voyante", "Sorcière", "Villageois", "Villageois", "Villageois"],
    7:  ["Loup Garou", "Loup Garou", "Voyante", "Sorcière", "Villageois", "Villageois", "Villageois"],
    8:  ["Loup Garou", "Loup Garou", "Voyante", "Sorcière", "Chasseur", "Villageois", "Villageois", "Villageois"],
    9:  ["Loup Garou", "Loup Garou", "Voyante", "Sorcière", "Chasseur", "Cupidon", "Villageois", "Villageois", "Villageois"],
    10: ["Loup Garou", "Loup Garou", "Loup Garou", "Voyante", "Sorcière", "Chasseur", "Cupidon", "Villageois", "Villageois", "Villageois"],
    12: ["Loup Garou", "Loup Garou", "Loup Garou", "Voyante", "Sorcière", "Chasseur", "Cupidon", "Petite Fille", "Loup Blanc", "Villageois", "Villageois", "Villageois"],
}

# Stockage des parties en cours  {guild_id: game_state}
lg_games = {}

def lg_get_compo(n):
    """Retourne la compo la plus proche pour n joueurs"""
    available = sorted(LG_COMPOS.keys())
    best = available[0]
    for k in available:
        if k <= n:
            best = k
    compo = LG_COMPOS[best].copy()
    # Compléter avec des Villageois si besoin
    while len(compo) < n:
        compo.append("Villageois")
    return compo[:n]

def lg_check_win(game):
    """Vérifie si une équipe a gagné. Retourne (True, message) ou (False, None)"""
    alive = [p for p in game["players"].values() if p["alive"]]
    wolves = [p for p in alive if p["role"] in ["Loup Garou", "Loup Blanc"]]
    villagers = [p for p in alive if p["role"] not in ["Loup Garou", "Loup Blanc"]]

    if len(wolves) == 0:
        return True, "🎉 **Le Village a gagné !** Tous les loups sont éliminés ! 👨‍🌾"
    if len(wolves) >= len(villagers):
        return True, "🐺 **Les Loups ont gagné !** Ils sont en supériorité ! Bonne nuit village..."
    # Loup Blanc seul ?
    if len(alive) == 1 and alive[0]["role"] == "Loup Blanc":
        return True, "🤍 **Le Loup Blanc a gagné !** Il est le dernier survivant !"
    return False, None

# ---- Commandes Loup Garou ----

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
        try:
            await member.send(embed=discord.Embed(
                title="🐺 Nuit — Choisis ta victime",
                description=f"Tape `.lgnuit @joueur` pour désigner votre cible.\n\n**Villageois en vie :**\n{names}",
                color=0x2c3e50
            ))
        except:
            pass

@bot.command(name="lgnuit")
async def lg_night_action(ctx, target: discord.Member = None):
    """Action de nuit — à utiliser EN MESSAGE PRIVÉ avec le bot"""
    # Trouver la partie du joueur
    game = None
    gid = None
    for g_id, g in lg_games.items():
        if ctx.author.id in g["players"]:
            game = g
            gid = g_id
            break

    if not game:
        return await ctx.send("❌ Tu ne participes à aucune partie en cours.")
    if game["state"] != "night":
        return await ctx.send("❌ Ce n'est pas la nuit !")
    if not game["players"][ctx.author.id]["alive"]:
        return await ctx.send("❌ Tu es mort(e), tu ne peux plus agir.")
    if target is None:
        return await ctx.send("❌ Mentionne une cible : `.lgnuit @joueur`")

    role = game["players"][ctx.author.id]["role"]
    p_target = game["players"].get(target.id)

    if not p_target or not p_target["alive"]:
        return await ctx.send("❌ Ce joueur n'est pas en vie dans la partie.")

    # Loup Garou — vote collectif
    if role in ["Loup Garou"]:
        game["night_actions"][ctx.author.id] = target.id
        wolves_alive = [uid for uid, p in game["players"].items() if p["role"] == "Loup Garou" and p["alive"]]
        voted_wolves = [uid for uid in wolves_alive if uid in game["night_actions"]]
        await ctx.send(f"✅ Tu as désigné **{target.display_name}** comme cible ({len(voted_wolves)}/{len(wolves_alive)} loups ont voté).")

        if len(voted_wolves) >= len(wolves_alive):
            # Majorité — cible la plus votée
            from collections import Counter
            wolf_votes = Counter([game["night_actions"][uid] for uid in voted_wolves])
            victim_id = wolf_votes.most_common(1)[0][0]
            game["eliminated_tonight"] = victim_id
            # Notifier tous les loups
            for wuid in wolves_alive:
                try:
                    m = ctx.guild.get_member(wuid)
                    await m.send(f"🐺 Cible choisie : **{game['players'][victim_id]['name']}**")
                except:
                    pass

    # Voyante
    elif role == "Voyante":
        role_target = p_target["role"]
        role_data = LG_ROLES[role_target]
        await ctx.send(embed=discord.Embed(
            title="🔮 Vision de la Voyante",
            description=f"**{target.display_name}** est... **{role_data['emoji']} {role_target}** !",
            color=0x9b59b6
        ))

    # Cupidon (première nuit)
    elif role == "Cupidon" and game["day"] == 1:
        if game["lovers"]:
            return await ctx.send("❌ Tu as déjà lié des amoureux !")
        # Cupidon se lie lui-même ou attend 2 cibles
        if ctx.author.id not in game["night_actions"]:
            game["night_actions"]["cupidon_1"] = target.id
            await ctx.send(f"💘 Premier amoureux : **{target.display_name}**. Maintenant tape `.lgnuit @joueur2`.")
        else:
            first = game["night_actions"].get("cupidon_1")
            game["lovers"] = [first, target.id]
            p1 = game["players"][first]
            await ctx.send(f"💘 **{p1['name']}** et **{target.display_name}** sont liés par l'amour !")
            # Prévenir les amoureux
            try:
                m1 = ctx.guild.get_member(first)
                await m1.send(f"💘 Tu es amoureux(se) de **{target.display_name}** ! Si l'un de vous meurt, l'autre aussi...")
                await target.send(f"💘 Tu es amoureux(se) de **{p1['name']}** ! Si l'un de vous meurt, l'autre aussi...")
            except:
                pass
    else:
        await ctx.send("❌ Tu n'as pas d'action de nuit disponible ou ce n'est pas le bon moment.")

@bot.command(name="lgsorciere")
async def lg_witch(ctx, action: str = None, target: discord.Member = None):
    """Sorcière : .lgsorciere vie/mort @cible — en MP"""
    game = None
    gid = None
    for g_id, g in lg_games.items():
        if ctx.author.id in g["players"]:
            game = g
            gid = g_id
            break

    if not game or game["state"] != "night":
        return await ctx.send("❌ Ce n'est pas la nuit ou tu n'es pas dans une partie.")
    if game["players"][ctx.author.id]["role"] != "Sorcière":
        return await ctx.send("❌ Tu n'es pas la Sorcière !")

    potions = game["witch_potions"].get(ctx.author.id, {"life": False, "death": False})

    if action == "vie":
        if not potions["life"]:
            return await ctx.send("❌ Tu as déjà utilisé ta potion de vie !")
        victim_id = game.get("eliminated_tonight")
        if not victim_id:
            return await ctx.send("❌ Personne n'a été ciblé cette nuit.")
        game["players"][victim_id]["alive"] = True
        game["eliminated_tonight"] = None
        game["witch_potions"][ctx.author.id]["life"] = False
        await ctx.send(f"🧪 Potion de vie utilisée ! **{game['players'][victim_id]['name']}** est sauvé(e) !")

    elif action == "mort":
        if not potions["death"]:
            return await ctx.send("❌ Tu as déjà utilisé ta potion de mort !")
        if not target or target.id not in game["players"] or not game["players"][target.id]["alive"]:
            return await ctx.send("❌ Cible invalide.")
        game["players"][target.id]["alive"] = False
        game["witch_potions"][ctx.author.id]["death"] = False
        await ctx.send(f"☠️ Potion de mort utilisée ! **{target.display_name}** sera éliminé(e) cette nuit.")
    else:
        await ctx.send("❌ Utilise `.lgsorciere vie` ou `.lgsorciere mort @cible`")

@bot.command(name="lgnextday")
async def lg_next_day(ctx):
    """Passer à la phase de jour — hôte uniquement"""
    gid = ctx.guild.id
    if gid not in lg_games:
        return
    game = lg_games[gid]
    if ctx.author.id != game["host"]:
        return await ctx.send("❌ Réservé à l'hôte.")
    if game["state"] != "night":
        return await ctx.send("❌ Ce n'est pas la nuit.")

    game["day"] += 1
    game["state"] = "day"

    deaths = []

    # Victime des loups
    victim_id = game.get("eliminated_tonight")
    if victim_id and game["players"][victim_id]["alive"]:
        game["players"][victim_id]["alive"] = False
        deaths.append(game["players"][victim_id]["name"])

        # Amoureux ?
        if victim_id in game["lovers"]:
            lover_id = [l for l in game["lovers"] if l != victim_id][0]
            if game["players"].get(lover_id, {}).get("alive"):
                game["players"][lover_id]["alive"] = False
                deaths.append(game["players"][lover_id]["name"] + " (💔 amoureux)")

    if deaths:
        desc = "🌅 **Le village se réveille...**\n\n☠️ **Cette nuit, il y a eu des victimes :**\n" + "\n".join([f"• {d}" for d in deaths])
        await lg_narrer_vocal(ctx, "jour_mort")
    else:
        desc = "🌅 **Le village se réveille... Personne n'est mort cette nuit !** 🍀"
        await lg_narrer_vocal(ctx, "jour_rien")

    # Révéler les rôles des morts
    for uid, p in game["players"].items():
        if not p["alive"] and p["name"] in deaths:
            desc += f"\n\n{p['name']} était : **{LG_ROLES[p['role']]['emoji']} {p['role']}**"

    alive_list = "\n".join([f"• {p['name']}" for p in game["players"].values() if p["alive"]])

    won, win_msg = lg_check_win(game)
    if won:
        await ctx.send(embed=discord.Embed(description=desc, color=0xe74c3c))
        cle_fin = "fin_village" if "village" in win_msg.lower() or "villageois" in win_msg.lower() else "fin_loups"
        await lg_narrer_vocal(ctx, cle_fin)
        await ctx.send(embed=discord.Embed(title="🏆 FIN DE PARTIE", description=win_msg, color=0xf1c40f))
        await lg_reveal_roles(ctx, game)
        del lg_games[gid]
        return

    embed = discord.Embed(
        title=f"☀️ Jour {game['day']}",
        description=desc + f"\n\n**Joueurs en vie :**\n{alive_list}\n\nDiscutez et utilisez `.lgvote @joueur` pour éliminer un suspect !",
        color=0xf39c12
    )
    await ctx.send(embed=embed)
    game["votes"] = {}
    game["night_actions"] = {}
    game["eliminated_tonight"] = None

async def lg_reveal_roles(ctx, game):
    """Révèle tous les rôles en fin de partie"""
    desc = ""
    for uid, p in game["players"].items():
        status = "✅" if p["alive"] else "💀"
        desc += f"{status} **{p['name']}** — {LG_ROLES[p['role']]['emoji']} {p['role']}\n"
    await ctx.send(embed=discord.Embed(
        title="📋 Révélation finale des rôles",
        description=desc,
        color=0x8e44ad
    ))

@bot.command(name="lgstatus")
async def lg_status(ctx):
    gid = ctx.guild.id
    if gid not in lg_games:
        return await ctx.send("❌ Aucune partie en cours.")
    game = lg_games[gid]
    alive = [p for p in game["players"].values() if p["alive"]]
    dead = [p for p in game["players"].values() if not p["alive"]]

    embed = discord.Embed(title=f"📊 Status — Jour {game['day']}", color=0x3498db)
    embed.add_field(name=f"✅ En vie ({len(alive)})", value="\n".join([f"• {p['name']}" for p in alive]) or "Aucun", inline=True)
    if dead:
        embed.add_field(name=f"💀 Éliminés ({len(dead)})", value="\n".join([f"• {p['name']} ({LG_ROLES[p['role']]['emoji']})" for p in dead]), inline=True)
    embed.set_footer(text=f"Phase : {'🌙 Nuit' if game['state'] == 'night' else '☀️ Jour'}")
    await ctx.send(embed=embed)

@bot.command(name="lgstop")
async def lg_stop(ctx):
    gid = ctx.guild.id
    if gid not in lg_games:
        return await ctx.send("❌ Aucune partie en cours.")
    game = lg_games[gid]
    if ctx.author.id != game["host"] and not ctx.author.guild_permissions.administrator:
        return await ctx.send("❌ Seul l'hôte ou un admin peut annuler la partie.")
    del lg_games[gid]
    await ctx.send(embed=discord.Embed(description="🛑 La partie de Loup Garou a été annulée.", color=0xe74c3c))

# ============================================================
#  RÔLES PAR RÉACTION — Système dynamique
# ============================================================
reaction_roles = {}  # {message_id: {"role_id": int, "emoji": str, "guild_id": int}}

@bot.command(name="rolecreate")
@commands.has_permissions(manage_roles=True)
async def role_create(ctx, role: discord.Role, emoji: str, image_url: str = None):
    """
    Crée un embed de rôle par réaction
    Usage: .rolecreate @NomDuRôle 🎬 https://lien-image.jpg
    """
    embed = discord.Embed(
        title=f"{emoji} | {role.name.upper()}",
        description=f"Réagis avec {emoji} pour obtenir le rôle **{role.name}** !",
        color=role.color if role.color.value != 0 else 0xff6b9d
    )
    if image_url:
        embed.set_image(url=image_url)
    embed.set_footer(text="Clique sur la réaction ci-dessous !")

    msg = await ctx.send(embed=embed)
    await msg.add_reaction(emoji)

    reaction_roles[msg.id] = {
        "role_id": role.id,
        "emoji": emoji,
        "guild_id": ctx.guild.id
    }
    await ctx.message.delete()

@bot.command(name="rolelist")
@commands.has_permissions(manage_roles=True)
async def role_list(ctx):
    """Affiche tous les rôles par réaction actifs"""
    if not reaction_roles:
        return await ctx.send("❌ Aucun rôle par réaction configuré.")
    embed = discord.Embed(title="🎭 Rôles par réaction actifs", color=0xff6b9d)
    for msg_id, data in reaction_roles.items():
        role = ctx.guild.get_role(data["role_id"])
        if role:
            embed.add_field(
                name=f"{data['emoji']} {role.name}",
                value=f"Message ID: `{msg_id}`",
                inline=False
            )
    await ctx.send(embed=embed)

@bot.command(name="roledelete")
@commands.has_permissions(manage_roles=True)
async def role_delete(ctx, role: discord.Role):
    """Supprime un rôle par réaction — .roledelete @NomDuRôle"""
    to_delete = [mid for mid, data in reaction_roles.items() if data["role_id"] == role.id]
    if not to_delete:
        return await ctx.send(f"❌ Aucun rôle par réaction trouvé pour **{role.name}**.")
    for mid in to_delete:
        del reaction_roles[mid]
    await ctx.send(embed=discord.Embed(
        description=f"✅ Rôle par réaction **{role.name}** supprimé !",
        color=0x2ecc71
    ))

@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    member = guild.get_member(payload.user_id)
    if not member:
        return

    # ── Règlement : ✅ → donne le rôle Membre ───────────────
    if SALON_REGLEMENT_ID and payload.channel_id == SALON_REGLEMENT_ID and str(payload.emoji) == "✅":
        # Chercher le rôle par ID (fiable) puis par nom (fallback)
        role = guild.get_role(REGLEMENT_ROLE_ID) if REGLEMENT_ROLE_ID else None
        if not role:
            role = discord.utils.get(guild.roles, name=ROLE_MEMBRE_NAME)
        if role and role not in member.roles:
            try:
                await member.add_roles(role, reason="Règlement accepté ✅")
            except discord.Forbidden:
                pass
        elif not role:
            # Log si le rôle est introuvable
            print(f"⚠️ Règlement: rôle introuvable (ID={REGLEMENT_ROLE_ID}, nom={ROLE_MEMBRE_NAME})")

    # ── Reaction roles classiques ────────────────────────────
    if payload.message_id in reaction_roles:
        data = reaction_roles[payload.message_id]
        if str(payload.emoji) == data["emoji"]:
            role = guild.get_role(data["role_id"])
            if role:
                await member.add_roles(role)

@bot.event
async def on_raw_reaction_remove(payload):
    if payload.message_id not in reaction_roles:
        return
    data = reaction_roles[payload.message_id]
    if str(payload.emoji) != data["emoji"]:
        return
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    role = guild.get_role(data["role_id"])
    member = guild.get_member(payload.user_id)
    if role and member:
        await member.remove_roles(role)

# ============================================================
#  ANTI-SPAM INTELLIGENT
# ============================================================
spam_tracker = {}  # {user_id: {"messages": [timestamps], "contents": [str], "warned": bool}}
muted_users = {}   # {user_id: timestamp}

def is_staff(member):
    return (
        member.guild_permissions.administrator or
        member.guild_permissions.manage_messages or
        member.guild_permissions.manage_guild
    )

async def get_or_create_mute_role(guild):
    mute_role = discord.utils.get(guild.roles, name="Muted")
    if not mute_role:
        mute_role = await guild.create_role(name="Muted", reason="Anti-spam")
        for channel in guild.channels:
            try:
                await channel.set_permissions(mute_role, send_messages=False, speak=False)
            except:
                pass
    return mute_role

async def check_spam(message):
    """Détecte uniquement le vrai spam : flood massif ou messages identiques"""
    author = message.author
    uid = author.id
    now = datetime.datetime.utcnow().timestamp()

    if uid not in spam_tracker:
        spam_tracker[uid] = {"messages": [], "contents": [], "warned": False}

    tracker = spam_tracker[uid]

    # Nettoyer les messages de plus de 5 secondes
    tracker["messages"] = [t for t in tracker["messages"] if now - t < 5]
    tracker["contents"] = tracker["contents"][-10:]  # garder les 10 derniers

    tracker["messages"].append(now)
    tracker["contents"].append(message.content.lower().strip())

    msg_count = len(tracker["messages"])
    contents = tracker["contents"]

    # Critère 1 : +8 messages en 5 secondes (flood massif)
    is_flood = msg_count >= 8

    # Critère 2 : messages identiques répétés 4+ fois
    if len(contents) >= 4:
        last_4 = contents[-4:]
        is_duplicate = len(set(last_4)) == 1 and last_4[0] != ""
    else:
        is_duplicate = False

    # Critère 3 : +5 mentions dans un message
    is_mention_spam = len(message.mentions) >= 5

    if not (is_flood or is_duplicate or is_mention_spam):
        return  # Pas du spam

    # Avertissement d'abord
    if not tracker["warned"]:
        tracker["warned"] = True
        warn_embed = discord.Embed(
            description=f"⚠️ {author.mention} doucement sur les messages ! Continue et tu seras muté. 🔇",
            color=0xf39c12
        )
        await message.channel.send(embed=warn_embed, delete_after=8)
        return

    # Mute si déjà averti et ça continue
    try:
        mute_role = await get_or_create_mute_role(message.guild)
        await author.add_roles(mute_role, reason="Anti-spam : spam détecté")
        muted_users[uid] = now
        spam_tracker[uid] = {"messages": [], "contents": [], "warned": False}

        embed = discord.Embed(
            title="🔇 Mute Anti-Spam",
            description=f"{author.mention} a été muté **10 minutes** pour spam.",
            color=0xe74c3c
        )
        await message.channel.send(embed=embed)

        # Unmute après 10 minutes
        await asyncio.sleep(600)
        await author.remove_roles(mute_role, reason="Anti-spam : fin du mute")
    except Exception as e:
        print(f"Erreur anti-spam mute: {e}")

# ============================================================
#  ANTI-RAID
# ============================================================
join_tracker = []  # liste de timestamps des joins récents
raid_mode = False

@bot.event
async def on_member_join(member):
    global raid_mode
    now = datetime.datetime.utcnow().timestamp()

    # Nettoyer les joins de plus de 10 secondes
    join_tracker_clean = [t for t in join_tracker if now - t < 10]
    join_tracker_clean.append(now)
    join_tracker.clear()
    join_tracker.extend(join_tracker_clean)

    # Détection raid : 5+ membres en 10 secondes
    if len(join_tracker) >= 5 and not raid_mode:
        raid_mode = True
        try:
            await member.guild.edit(
                verification_level=discord.VerificationLevel.high,
                reason="Anti-raid activé automatiquement"
            )
        except:
            pass

        # Chercher le salon logs ou général
        log_channel = (
            discord.utils.get(member.guild.text_channels, name="logs") or
            discord.utils.get(member.guild.text_channels, name="mod-logs") or
            discord.utils.get(member.guild.text_channels, name="général") or
            member.guild.system_channel
        )
        if log_channel:
            embed = discord.Embed(
                title="🚨 RAID DÉTECTÉ !",
                description=(
                    f"**{len(join_tracker)} membres** ont rejoint en moins de 10 secondes !\n\n"
                    f"✅ Vérification du serveur passée en mode **élevé** automatiquement.\n"
                    f"Utilise `.raidstop` pour revenir en mode normal."
                ),
                color=0xe74c3c
            )
            embed.set_footer(text="Anti-Raid QG Kdrama 🛡️")
            await log_channel.send(embed=embed)

        # Réinitialiser après 30 secondes
        await asyncio.sleep(30)
        raid_mode = False
        return

    # Message de bienvenue — Prophétie B violet
    # ── Tracker invitations ──────────────────────────────────
    try:
        new_invites = {inv.code: inv.uses for inv in await member.guild.invites()}
        inviter = None
        for code, uses in new_invites.items():
            old_uses = guild_invites.get(member.guild.id, {}).get(code, 0)
            if uses > old_uses:
                # Trouver qui possède ce lien
                for inv in await member.guild.invites():
                    if inv.code == code and inv.inviter:
                        inviter = inv.inviter
                        break
                break
        guild_invites[member.guild.id] = new_invites
        if inviter:
            invite_counts[str(inviter.id)] += 1
            total = invite_counts[str(inviter.id)]
            if SALON_INVITATION_ID:
                inv_channel = member.guild.get_channel(SALON_INVITATION_ID)
                if inv_channel:
                    embed_inv = discord.Embed(
                        description=(
                            f"🔗 **{member.mention}** a été invité par **{inviter.mention}** !\n"
                            f"🎉 Merci pour ta contribution — tu es maintenant à **{total} invitation(s)** au total !"
                        ),
                        color=0x2ecc71
                    )
                    await inv_channel.send(embed=embed_inv)
    except:
        pass

    if not raid_mode:
        channel = None
        if SALON_BIENVENUE_ID:
            channel = member.guild.get_channel(SALON_BIENVENUE_ID)
        if not channel:
            channel = discord.utils.get(member.guild.text_channels, name="général") or member.guild.system_channel
        if channel:
            import random as _random
            member_count = member.guild.member_count

            # Prophéties aléatoires
            prophecies = [
                ("Celui qui arrive en {n}ème position\nvainquera par la ruse, jamais par la force.", "Le QG l'attendait depuis toujours."),
                ("Le {n}ème guerrier du QG\nmarquera l'histoire de son passage.", "Nul ne pouvait en douter."),
                ("Une âme errante depuis longtemps\ntrouve enfin sa place au {n}ème rang.", "Le destin ne ment jamais."),
                ("Quand le {n}ème entrera,\nles équilibres du QG changeront à jamais.", "La prophétie est accomplie."),
                ("Le {n}ème nom inscrit dans les annales\nrésonnera longtemps après son départ.", "Il est écrit depuis toujours."),
            ]
            texte, conclusion = _random.choice(prophecies)
            texte = texte.replace('{n}', str(member_count))
            conclusion = conclusion.replace('{n}', str(member_count))

            embed = discord.Embed(color=0x9B59B6)
            embed.set_author(
                name=f"{member.display_name}  •  Membre n°{member_count}",
                icon_url=member.display_avatar.url
            )
            embed.description = (
                f"🔮  **PROPHÉTIE N°{member_count:03d} — DÉCLASSIFIÉE**\n\n"
                f"{member.mention}\n\n"
                f"> *{texte}*\n\n"
                f"*— {conclusion}*\n\n"
                f"📖 Tape `.help` pour découvrir tes pouvoirs"
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(
                text="QG Kdrama  •  Prophétie inscrite bien avant ton arrivée",
                icon_url=member.guild.icon.url if member.guild.icon else None
            )
            await channel.send(embed=embed)

@bot.event
async def on_member_remove(member):
    """Message d'aurevoir quand un membre quitte"""
    channel = None
    if SALON_AUREVOIR_ID:
        channel = member.guild.get_channel(SALON_AUREVOIR_ID)
    if not channel:
        return
    member_count = member.guild.member_count

    citations_aurevoir = [
        ("*« Même si tu pars, tu resteras à jamais dans nos cœurs. »*", "— Inspiré de Clannad"),
        ("*« Les adieux sont toujours douloureux, peu importe les fois où on les vit. »*", "— Violet Evergarden"),
        ("*« Partir ne signifie pas oublier. »*", "— Inspiré de Your Lie in April"),
        ("*« On se retrouvera, même si ce n'est pas dans ce monde. »*", "— Inspiré de Angel Beats"),
        ("*« Les liens qu'on tisse ne disparaissent pas, même après les adieux. »*", "— Inspiré de Naruto"),
        ("*« Toutes les rencontres mènent à une séparation... c'est la loi de ce monde. »*", "— Inspiré de Bleach"),
    ]

    import random as _random
    citation, auteur = _random.choice(citations_aurevoir)

    embed = discord.Embed(
        title="💔 Un membre a quitté le QG...",
        description=(
            f"**{member.display_name}** vient de quitter le serveur.\n\n"
            f"{citation}\n"
            f"*{auteur}*\n\n"
            f"Il nous reste **{member_count} membres** dans le QG. 🏯"
        ),
        color=0x555555
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text="QG Kdrama — À bientôt... 👋", icon_url=member.guild.icon.url if member.guild.icon else None)
    await channel.send(embed=embed)

@bot.event
async def on_member_update(before, after):
    """Détecte quand un membre boost le serveur"""
    if before.premium_since is None and after.premium_since is not None:
        # Nouveau boost !
        channel = None
        if SALON_BOOST_ID:
            channel = after.guild.get_channel(SALON_BOOST_ID)
        if not channel:
            return
        boosters = [m for m in after.guild.members if m.premium_since]
        boost_count = len(boosters)
        suffix = "er" if boost_count == 1 else "ème"
        embed = discord.Embed(
            title="💎 BOOST ACTIVÉ !",
            description=(
                f"### 🌟 {after.mention} vient de booster le QG Kdrama !\n\n"
                f"✨ Tu es notre **{boost_count}{suffix} boosteur** du serveur !\n"
                f"🔥 Le QG gagne en puissance grâce à toi !\n"
                f"👑 Tu rejoins l'élite des soutiens du QG !\n\n"
                f"*« Sans les boosteurs, le QG ne serait rien »* 🎌\n\n"
                f"🎊 **Merci du fond du cœur !** 💜"
            ),
            color=0xff73fa
        )
        embed.set_thumbnail(url=after.display_avatar.url)
        embed.set_image(url="https://i.imgur.com/placeholder_boost.gif") if False else None
        embed.set_footer(
            text=f"QG Kdrama — {after.guild.premium_subscription_count} boost(s) au total 🚀",
            icon_url=after.guild.icon.url if after.guild.icon else None
        )
        await channel.send(embed=embed)

@bot.event
async def on_reaction_add(reaction, user):
    """Hall of Fame — message avec 4+ réactions drôles"""
    if user.bot:
        return
    if str(reaction.emoji) not in HOF_EMOJIS:
        return
    if not SALON_HOF_ID:
        return
    msg = reaction.message
    if msg.id in HOF_MESSAGES:
        return  # Déjà dans le Hall of Fame

    # Compter toutes les réactions HOF sur ce message
    total_hof = 0
    for r in msg.reactions:
        if str(r.emoji) in HOF_EMOJIS:
            total_hof += r.count

    if total_hof < HOF_SEUIL:
        return

    # Ajouter au Hall of Fame
    HOF_MESSAGES.add(msg.id)
    hof_channel = msg.guild.get_channel(SALON_HOF_ID)
    if not hof_channel:
        return

    # Construire l'emoji dominant
    top_emoji = str(reaction.emoji)
    top_count = reaction.count
    for r in msg.reactions:
        if str(r.emoji) in HOF_EMOJIS and r.count > top_count:
            top_emoji = str(r.emoji)
            top_count = r.count

    embed = discord.Embed(
        description=f"**{msg.content}**" if msg.content else "*[Media ou embed]*",
        color=0xf1c40f,
        timestamp=msg.created_at
    )
    embed.set_author(
        name=msg.author.display_name,
        icon_url=msg.author.display_avatar.url
    )
    # Image si présente
    if msg.attachments:
        embed.set_image(url=msg.attachments[0].url)

    embed.add_field(
        name="📍 Source",
        value=f"[Voir le message original]({msg.jump_url}) dans {msg.channel.mention}",
        inline=False
    )
    embed.set_footer(text=f"{top_emoji} {total_hof} réactions • #{msg.channel.name}")

    title_embed = discord.Embed(
        description=f"{top_emoji} **{total_hof} personnes ont explosé de rire !**",
        color=0xf1c40f
    )
    await hof_channel.send(embed=title_embed)
    await hof_channel.send(embed=embed)



@bot.command(name="raidstop")
@commands.has_permissions(administrator=True)
async def raid_stop(ctx):
    """Désactive le mode anti-raid et remet la vérification normale"""
    global raid_mode
    raid_mode = False
    try:
        await ctx.guild.edit(verification_level=discord.VerificationLevel.low)
    except:
        pass
    await ctx.send(embed=discord.Embed(
        description="✅ Mode raid désactivé ! Vérification revenue en mode normal.",
        color=0x2ecc71
    ))

# Intégrer le check spam dans on_message — patch
_original_on_message = bot.on_message if hasattr(bot, 'on_message') else None

@bot.listen("on_message")
async def spam_listener(message):
    if message.author.bot:
        return
    if not message.guild:
        return
    if is_staff(message.author):
        return
    # Salon gacha exempté de l'antispam
    if SALON_GACHA_ID and message.channel.id == SALON_GACHA_ID:
        return
    await check_spam(message)

# ============================================================
#  WATCHLIST
# ============================================================
watchlist_data = defaultdict(list)  # {user_id: [{"title": str, "type": str, "status": str}]}

@bot.command(name="watch")
async def watch_cmd(ctx, action: str = None, *, title: str = None):
    """
    .watch ajouter <titre> — Ajoute à ta watchlist
    .watch liste — Voir ta watchlist
    .watch vu <titre> — Marquer comme vu
    .watch supprimer <titre> — Supprimer de la liste
    """
    uid = str(ctx.author.id)
    if not action:
        return await ctx.send("📋 Usage: `.watch ajouter <titre>` | `.watch liste` | `.watch vu <titre>` | `.watch supprimer <titre>`")

    action = action.lower()

    if action == "ajouter":
        if not title:
            return await ctx.send("❌ Précise un titre ! Ex: `.watch ajouter Goblin`")
        for item in watchlist_data[uid]:
            if item["title"].lower() == title.lower():
                return await ctx.send(f"❌ **{title}** est déjà dans ta watchlist !")
        watchlist_data[uid].append({"title": title, "status": "À voir"})
        await ctx.send(embed=discord.Embed(
            description=f"✅ **{title}** ajouté à ta watchlist ! 🎬",
            color=0xff6b9d
        ))

    elif action == "liste":
        items = watchlist_data[uid]
        if not items:
            return await ctx.send("📋 Ta watchlist est vide ! Ajoute des titres avec `.watch ajouter <titre>`")
        embed = discord.Embed(title=f"📋 Watchlist de {ctx.author.display_name}", color=0xff6b9d)
        a_voir = [i["title"] for i in items if i["status"] == "À voir"]
        vus = [i["title"] for i in items if i["status"] == "Vu ✅"]
        if a_voir:
            embed.add_field(name="🎬 À voir", value="\n".join([f"• {t}" for t in a_voir]), inline=False)
        if vus:
            embed.add_field(name="✅ Vus", value="\n".join([f"• {t}" for t in vus]), inline=False)
        embed.set_footer(text=f"{len(items)} titre(s) au total")
        await ctx.send(embed=embed)

    elif action == "vu":
        if not title:
            return await ctx.send("❌ Précise un titre ! Ex: `.watch vu Goblin`")
        for item in watchlist_data[uid]:
            if item["title"].lower() == title.lower():
                item["status"] = "Vu ✅"
                return await ctx.send(embed=discord.Embed(
                    description=f"✅ **{item['title']}** marqué comme vu ! 🎉",
                    color=0x2ecc71
                ))
        await ctx.send(f"❌ **{title}** n'est pas dans ta watchlist.")

    elif action == "supprimer":
        if not title:
            return await ctx.send("❌ Précise un titre !")
        before = len(watchlist_data[uid])
        watchlist_data[uid] = [i for i in watchlist_data[uid] if i["title"].lower() != title.lower()]
        if len(watchlist_data[uid]) < before:
            await ctx.send(embed=discord.Embed(description=f"🗑️ **{title}** supprimé de ta watchlist.", color=0xe74c3c))
        else:
            await ctx.send(f"❌ **{title}** n'est pas dans ta watchlist.")

# ============================================================
#  AVIS & NOTES
# ============================================================
reviews_data = defaultdict(lambda: defaultdict(dict))  # {title_lower: {user_id: {"note": int, "avis": str}}}

@bot.command(name="noter")
async def noter_cmd(ctx, note: int, *, titre: str):
    """
    .noter <1-10> <titre> — Donne une note à un drama/animé
    Ex: .noter 9 Goblin
    """
    if not 1 <= note <= 10:
        return await ctx.send("❌ La note doit être entre 1 et 10 !")
    key = titre.lower().strip()
    reviews_data[key][str(ctx.author.id)] = {"note": note, "titre_original": titre}
    notes = [v["note"] for v in reviews_data[key].values()]
    moyenne = sum(notes) / len(notes)
    embed = discord.Embed(
        title=f"⭐ Note enregistrée — {titre}",
        description=(
            f"{ctx.author.mention} a noté **{titre}** : **{note}/10**\n\n"
            f"📊 Moyenne du serveur : **{moyenne:.1f}/10** ({len(notes)} vote{'s' if len(notes) > 1 else ''})"
        ),
        color=0xf1c40f
    )
    await ctx.send(embed=embed)

@bot.command(name="avis")
async def avis_cmd(ctx, *, titre: str):
    """Voir les notes et avis du serveur pour un titre"""
    key = titre.lower().strip()
    if key not in reviews_data or not reviews_data[key]:
        return await ctx.send(f"❌ Aucun avis pour **{titre}** pour l'instant.")
    notes = [v["note"] for v in reviews_data[key].values()]
    moyenne = sum(notes) / len(notes)
    titre_original = list(reviews_data[key].values())[0]["titre_original"]
    stars = "⭐" * round(moyenne / 2)
    embed = discord.Embed(
        title=f"📊 Avis du serveur — {titre_original}",
        description=f"{stars}\n**Moyenne : {moyenne:.1f}/10** — {len(notes)} vote{'s' if len(notes) > 1 else ''}",
        color=0xf1c40f
    )
    top = sorted(reviews_data[key].items(), key=lambda x: x[1]["note"], reverse=True)[:5]
    details = ""
    for uid, data in top:
        member = ctx.guild.get_member(int(uid))
        name = member.display_name if member else "Membre inconnu"
        details += f"• **{name}** : {data['note']}/10\n"
    if details:
        embed.add_field(name="🏆 Top votes", value=details, inline=False)
    await ctx.send(embed=embed)

# ============================================================
#  CALENDRIER DES SORTIES
# ============================================================
SORTIES = [
    {"titre": "When the Stars Gossip", "type": "🎬 Kdrama", "date": "Mars 2026", "plateforme": "Netflix"},
    {"titre": "Queen of Tears S2", "type": "🎬 Kdrama", "date": "Avril 2026", "plateforme": "Netflix"},
    {"titre": "Demon Slayer S5", "type": "✨ Animé", "date": "Printemps 2026", "plateforme": "Crunchyroll"},
    {"titre": "Solo Leveling S2", "type": "✨ Animé", "date": "Janvier 2026", "plateforme": "Crunchyroll"},
    {"titre": "My Mister S2", "type": "🎬 Kdrama", "date": "2026", "plateforme": "Netflix"},
    {"titre": "Jujutsu Kaisen S3", "type": "✨ Animé", "date": "2026", "plateforme": "Crunchyroll"},
]


# ============================================================
#  DEVINE LE PERSONNAGE
# ============================================================
PERSONNAGES = [
    {"nom": "Gong Woo Jin (Goblin)", "indices": ["Je suis immortel depuis 900 ans", "J'ai une épée plantée dans ma poitrine", "Je cherche ma fiancée pour mourir enfin", "Je suis un goblin coréen"], "univers": "🎬 Goblin"},
    {"nom": "Vincenzo Cassano", "indices": ["Je suis avocat de la mafia italienne", "Je suis d'origine coréenne adoptée en Italie", "Je combats une corporation corrompue", "Mon style est impeccable en costume"], "univers": "🎬 Vincenzo"},
    {"nom": "Park Saeroyi", "indices": ["Mon père a été tué par un riche héritier", "J'ai ouvert un bar dans Itaewon pour me venger", "Je suis passionné et têtu", "Mon bar s'appelle DanBam"], "univers": "🎬 Itaewon Class"},
    {"nom": "Eren Yeager", "indices": ["Je veux détruire tous mes ennemis", "J'ai perdu ma mère enfant", "Je peux me transformer en titan", "Je porte le titan fondateur"], "univers": "✨ Attack on Titan"},
    {"nom": "Tanjiro Kamado", "indices": ["Ma sœur a été transformée en démon", "J'utilise la respiration de l'eau", "Je suis très empathique même envers les démons", "Mes boucles d'oreilles sont caracteristiques"], "univers": "✨ Demon Slayer"},
    {"nom": "Light Yagami", "indices": ["Je suis un lycéen brillant", "J'ai trouvé un carnet qui tue", "Je veux créer un monde parfait sans criminels", "Mon alter ego s'appelle Kira"], "univers": "✨ Death Note"},
    {"nom": "Monkey D. Luffy", "indices": ["Mon corps est en caoutchouc", "Je veux devenir Roi des Pirates", "Mon chapeau de paille est précieux pour moi", "Mon équipage s'appelle les Chapeaux de Paille"], "univers": "✨ One Piece"},
    {"nom": "Edward Elric", "indices": ["J'ai perdu un bras et une jambe", "Je cherche la pierre philosophale", "Je suis le plus jeune alchimiste d'état de l'histoire", "Ne me dis pas que je suis petit"], "univers": "✨ FMA Brotherhood"},
    {"nom": "Shoyo Hinata", "indices": ["Je suis petit mais je saute très haut", "Je joue au volleyball", "Mon équipe s'appelle Karasuno", "Je suis un libéro sauteur"], "univers": "✨ Haikyuu!!"},
    {"nom": "Yuji Itadori", "indices": ["J'ai avalé un doigt maudit", "Je suis physiquement très fort", "Je partage mon corps avec un démon", "J'étudie dans un lycée d'exorcistes"], "univers": "✨ Jujutsu Kaisen"},
]

active_devine = {}

@bot.command(name="devine")
async def devine_cmd(ctx):
    """Lance un jeu Devine le Personnage"""
    if ctx.channel.id in active_devine:
        return await ctx.send("🎭 Un jeu est déjà en cours ici !")

    perso = random.choice(PERSONNAGES)
    active_devine[ctx.channel.id] = {"perso": perso, "indice_idx": 0, "tries": 0}

    embed = discord.Embed(
        title=f"🎭 Devine le Personnage ! {perso['univers']}",
        description=f"**Indice 1 :** {perso['indices'][0]}\n\n_Tape le nom du personnage !_",
        color=0x9b59b6
    )
    embed.set_footer(text="⏳ 60 secondes • Tu peux demander un indice en tapant 'indice' !")
    await ctx.send(embed=embed)

    def check(m):
        return m.channel == ctx.channel and not m.author.bot

    end_time = asyncio.get_event_loop().time() + 60
    while True:
        remaining = end_time - asyncio.get_event_loop().time()
        if remaining <= 0:
            break
        try:
            msg = await bot.wait_for("message", check=check, timeout=remaining)
            if ctx.channel.id not in active_devine:
                return
            game = active_devine[ctx.channel.id]

            if msg.content.lower().strip() == "indice":
                game["indice_idx"] = min(game["indice_idx"] + 1, len(perso["indices"]) - 1)
                idx = game["indice_idx"]
                await ctx.send(embed=discord.Embed(
                    description=f"💡 **Indice {idx+1} :** {perso['indices'][idx]}",
                    color=0xf39c12
                ))
                continue

            if perso["nom"].split(" ")[0].lower() in msg.content.lower() or msg.content.lower().strip() in perso["nom"].lower():
                active_devine.pop(ctx.channel.id, None)
                prize = max(50, 150 - game["indice_idx"] * 30)
                economy_data[str(msg.author.id)]["coins"] += prize
                xp_data[str(msg.author.id)]["xp"] += 20
                await ctx.send(embed=discord.Embed(
                    description=f"🎉 **{msg.author.mention}** a trouvé ! C'était **{perso['nom']}** ! +{prize} pièces 🎭",
                    color=0x2ecc71
                ))
                return
        except asyncio.TimeoutError:
            break

    active_devine.pop(ctx.channel.id, None)
    await ctx.send(embed=discord.Embed(
        description=f"⏰ Temps écoulé ! C'était **{perso['nom']}** ({perso['univers']}) !",
        color=0xe74c3c
    ))

# ============================================================
#  PENDU
# ============================================================
PENDU_MOTS = [
    "goblin", "vincenzo", "squid game", "kingdom", "signal", "itaewon class",
    "reply 1988", "hospital playlist", "crash landing on you",
    "attack on titan", "demon slayer", "death note", "one piece", "haikyuu",
    "jujutsu kaisen", "fullmetal alchemist", "your lie in april", "vinland saga",
    "naruto", "dragon ball", "pokemon", "one punch man",
]

PENDU_STAGES = ["😵", "😰", "😨", "😟", "😐", "🙂", "😄"]

active_pendu = {}

@bot.command(name="pendu")
async def pendu_cmd(ctx):
    """Lance une partie de Pendu avec des titres d'animés/dramas"""
    if ctx.channel.id in active_pendu:
        return await ctx.send("🎮 Une partie de pendu est déjà en cours !")

    mot = random.choice(PENDU_MOTS)
    # Révéler la première lettre
    trouve_init = ["_" if c != " " else " " for c in mot]
    premiere = mot[0]
    for i, c in enumerate(mot):
        if c == premiere:
            trouve_init[i] = c
    active_pendu[ctx.channel.id] = {
        "mot": mot,
        "trouve": trouve_init,
        "lettres": [premiere],
        "erreurs": 0,
        "max_erreurs": 6
    }

    await ctx.send(embed=_pendu_embed(active_pendu[ctx.channel.id]))

    def check(m):
        return (
            m.channel == ctx.channel and not m.author.bot and
            (len(m.content) == 1 and m.content.isalpha() or m.content.lower() == "skip")
        )

    while ctx.channel.id in active_pendu:
        game = active_pendu[ctx.channel.id]
        try:
            msg = await bot.wait_for("message", check=check, timeout=60)
            # Skip
            if msg.content.lower() == "skip":
                mot_cache = game["mot"]
                active_pendu.pop(ctx.channel.id, None)
                await ctx.send(embed=discord.Embed(
                    description=f"⏭️ Mot passé ! C'était **{mot_cache.upper()}**\nTape `.pendu` pour rejouer !",

                    color=0x95a5a6
                ))
                return
            lettre = msg.content.lower()
            if lettre in game["lettres"]:
                await ctx.send(f"⚠️ La lettre **{lettre}** a déjà été proposée !", delete_after=3)
                continue
            game["lettres"].append(lettre)
            if lettre in game["mot"]:
                for i, c in enumerate(game["mot"]):
                    if c == lettre:
                        game["trouve"][i] = lettre
                if "_" not in game["trouve"]:
                    active_pendu.pop(ctx.channel.id, None)
                    prize = 100
                    economy_data[str(msg.author.id)]["coins"] += prize
                    await ctx.send(embed=discord.Embed(
                        description=f"🎉 **{msg.author.mention}** a trouvé ! C'était **{game['mot'].upper()}** ! +{prize} pièces 🏆",
                        color=0x2ecc71
                    ))
                    return
                await ctx.send(embed=_pendu_embed(game))
            else:
                game["erreurs"] += 1
                if game["erreurs"] >= game["max_erreurs"]:
                    active_pendu.pop(ctx.channel.id, None)
                    await ctx.send(embed=discord.Embed(
                        description=f"💀 Perdu ! Le mot était **{game['mot'].upper()}** !",
                        color=0xe74c3c
                    ))
                    return
                await ctx.send(embed=_pendu_embed(game))
        except asyncio.TimeoutError:
            active_pendu.pop(ctx.channel.id, None)
            await ctx.send("⏰ Partie de pendu abandonnée !")
            return

def _pendu_embed(game):
    stage = PENDU_STAGES[max(0, len(PENDU_STAGES) - 1 - game["erreurs"])]
    embed = discord.Embed(
        title=f"🎮 Pendu {stage}",
        description=(
            f"**`{' '.join(game['trouve'])}`**\n\n"
            f"❌ Erreurs : **{game['erreurs']}/{game['max_erreurs']}**\n"
            f"📝 Lettres proposées : {', '.join(game['lettres']) if game['lettres'] else 'Aucune'}"
        ),
        color=0xe74c3c if game["erreurs"] >= 4 else 0xf39c12 if game["erreurs"] >= 2 else 0x2ecc71
    )
    embed.set_footer(text="Tape une lettre pour jouer !")
    return embed

# ============================================================
#  BOUTIQUE
# ============================================================
SHOP_ITEMS = [
    # ═══ RÔLES EXCLUSIFS (du plus cher au moins cher) ═══
    {"id": "shadow",       "nom": "🌑 Monarque des Ombres",  "prix": 3000, "cat": "role",  "description": "Le rôle le plus rare du serveur — prestige absolu"},
    {"id": "pillier",      "nom": "🔥 Pillier du Soleil",    "prix": 2000, "cat": "role",  "description": "Rôle légendaire des membres les plus actifs"},
    {"id": "drama_king",   "nom": "👑 Roi des Malédictions", "prix": 1500, "cat": "role",  "description": "Le titre ultime façon Jujutsu Kaisen"},
    {"id": "otaku",        "nom": "🌀 Oeil de Dieu",         "prix": 1200, "cat": "role",  "description": "Rôle exclusif des vrais connaisseurs d'animé"},
    {"id": "vip",          "nom": "💎 Rang S — VIP",         "prix": 1000, "cat": "role",  "description": "Le rang des élus — accès exclusif aux salons VIP"},
    {"id": "gamer_pro",    "nom": "⚔️ Chasseur National",   "prix": 800,  "cat": "role",  "description": "Le rang des meilleurs gamers du QG"},
    # ═══ BOOSTS & ROLLS (du plus cher au moins cher) ═══
    {"id": "claim_10",     "nom": "⚡ Claim 10 min",         "prix": 3000, "cat": "boost", "description": "Réduit le claim reset à 10 min (permanent)"},
    {"id": "boost_rarete", "nom": "🎯 Boost Rareté",         "prix": 1500, "cat": "boost", "description": "↑↑ chances Épique/Légendaire/Mythique pour 5 rolls (1x/jour)", "daily": True},
    {"id": "claim_15",     "nom": "⚡ Claim 15 min",         "prix": 1500, "cat": "boost", "description": "Réduit le claim reset à 15 min (permanent)"},
    {"id": "claim_20",     "nom": "⚡ Claim 20 min",         "prix": 800,  "cat": "boost", "description": "Réduit le claim reset à 20 min (permanent)"},
    {"id": "rolls_5",      "nom": "🎰 +5 Rolls Gacha",       "prix": 700,  "cat": "boost", "description": "+5 rolls gacha instantanément !"},
    {"id": "double_xp",    "nom": "⚡ Double XP (1h)",       "prix": 300,  "cat": "boost", "description": "Double ton XP pendant 1 heure !"},
    # ═══ ITEMS PVP — SABOTAGE & DÉFENSE (du plus cher au moins cher) ═══
    {"id": "bombe_gacha",  "nom": "💣 Bombe Gacha",          "prix": 8000, "cat": "pvp",   "description": "Force un joueur à perdre sa dernière carte claimée 💀"},
    {"id": "protection",   "nom": "🌟 Protection Divine",    "prix": 5000, "cat": "pvp",   "description": "Immunité totale contre tout sabotage pendant 2h"},
    {"id": "cadenas",      "nom": "🔒 Cadenas",              "prix": 4000, "cat": "pvp",   "description": "Empêche un joueur de claim pendant 30 min"},
    {"id": "amulette",     "nom": "🪬 Amulette",             "prix": 2500, "cat": "pvp",   "description": "Renvoie tout sabotage sur l'attaquant pendant 20 min"},
    {"id": "cadeau",       "nom": "🎁 Cadeau Mystère",       "prix": 900,  "cat": "pvp",   "description": "Reçois une carte aléatoire Rare ou supérieure 🎲"},
    {"id": "fantome",      "nom": "👻 Fantôme",              "prix": 800,  "cat": "pvp",   "description": "Rend une carte aléatoire d'un joueur invisible 30 min"},
    {"id": "malediction",  "nom": "🎭 Malédiction Rare",     "prix": 700,  "cat": "pvp",   "description": "Force le prochain tirage d'un joueur à être Commun (2x/jour, 1x/joueur)", "daily": True},
    {"id": "oracle",       "nom": "🔮 Oracle",               "prix": 499,  "cat": "pvp",   "description": "Une carte mystère a 1/5 chance de drop dans les 3 prochains tirages !"},
    {"id": "vol_roll",     "nom": "🎯 Vol de Roll",          "prix": 500,  "cat": "pvp",   "description": "Vole 1 roll à un joueur ciblé (max 3x sur le même joueur)"},
    {"id": "double_rien",  "nom": "🎰 Double ou Rien",       "prix": 200,  "cat": "pvp",   "description": "Double tes rolls ou les perds tous ! (max 4 rolls restants)"},
    {"id": "shield",       "nom": "🛡️ Bouclier",            "prix": 600,  "cat": "pvp",   "description": "Protège du Sceau et Malédiction pendant 30 min"},
    {"id": "freeze",       "nom": "🧊 Sceau des Ombres",     "prix": 500,  "cat": "pvp",   "description": "Bloque le claim d'un joueur 10 secondes (1x/jour)", "daily": True},
    {"id": "curse",        "nom": "⏳ Malédiction Claim",    "prix": 400,  "cat": "pvp",   "description": "+5 min sur le claim d'un joueur (1x/jour)", "daily": True},
]

shop_roles = {}  # {item_id: role_id}
double_xp_users = {}  # {user_id: end_timestamp}
message_count = defaultdict(int)  # {user_id: count}
voice_time = defaultdict(int)  # {user_id: minutes}
voice_join_time = {}  # {user_id: join_timestamp}

@bot.command(name="shop")
async def shop_cmd(ctx):
    """Affiche la boutique du QG"""
    if SALON_BOUTIQUE_ID and ctx.channel.id != SALON_BOUTIQUE_ID:
        salon = ctx.guild.get_channel(SALON_BOUTIQUE_ID)
        mention = salon.mention if salon else "le salon boutique"
        return await ctx.send(f"🛒 La boutique c'est dans {mention} !", delete_after=5)
    embed = discord.Embed(
        title="🛒 Boutique du QG Kdrama",
        description="Dépense tes pièces pour des rôles et bonus exclusifs !",
        color=0xf1c40f
    )
    uid = str(ctx.author.id)
    solde = economy_data[uid]["coins"]
    # Trier du plus cher au moins cher par catégorie
    roles_items  = sorted([i for i in SHOP_ITEMS if i.get("cat") == "role"],  key=lambda x: x["prix"], reverse=True)
    boosts_items = sorted([i for i in SHOP_ITEMS if i.get("cat") == "boost"], key=lambda x: x["prix"], reverse=True)
    gacha_items  = sorted([i for i in SHOP_ITEMS if i.get("cat") == "pvp"],   key=lambda x: x["prix"], reverse=True)

    embed.add_field(name="─── 🎭 RÔLES EXCLUSIFS ───", value="​", inline=False)
    for item in roles_items:
        dispo = "✅" if solde >= item["prix"] else "❌"
        embed.add_field(
            name=f"{item['nom']} — {item['prix']} pièces {dispo}",
            value=f"{item['description']}\n`.acheter {item['id']}`",
            inline=False
        )
    embed.add_field(name="─── ⚡ BOOSTS & ROLLS ───", value="​", inline=False)
    for item in boosts_items:
        dispo = "✅" if solde >= item["prix"] else "❌"
        embed.add_field(
            name=f"{item['nom']} — {item['prix']} pièces {dispo}",
            value=f"{item['description']}\n`.acheter {item['id']}`",
            inline=False
        )
    embed.add_field(name="─── 🎴 ITEMS GACHA (sabotage & défense) ───", value="​", inline=False)
    for item in gacha_items:
        dispo = "✅" if solde >= item["prix"] else "❌"
        embed.add_field(
            name=f"{item['nom']} — {item['prix']} pièces {dispo}",
            value=f"{item['description']}\n`.acheter {item['id']}`",
            inline=False
        )
    embed.set_footer(text=f"💰 Ton solde : {solde} pièces")
    await ctx.send(embed=embed)

@bot.command(name="acheter")
async def acheter_cmd(ctx, item_id: str = None):
    if SALON_BOUTIQUE_ID and ctx.channel.id != SALON_BOUTIQUE_ID:
        salon = ctx.guild.get_channel(SALON_BOUTIQUE_ID)
        mention = salon.mention if salon else "le salon boutique"
        return await ctx.send(f"🛒 La boutique c'est dans {mention} !", delete_after=5)
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
        economy_data[uid]["coins"] += gain
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
    "Mythique":   1,     # ~0.01%
    "Légendaire": 50,    # ~0.5%
    "Épique":     300,   # ~3%
    "Rare":       2000,  # ~20%
    "Commun":     7649,  # ~76.49%
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
            title="🛒 Items Boutique — Pouvoirs Gacha",
            description="Ces items s'achètent avec `.acheter <id>` en boutique et impactent directement le gacha !",
            color=0xf39c12
        )
        embed4.add_field(name="🚀 Boosts offensifs", value=(
            "🎰 **+10 Rolls** `rolls_10` — **600p**\n"
            "→ Ajoute instantanément 10 rolls à ton compteur\n\n"
            "🎯 **Boost Rareté** `boost_rarete` — **1500p** *(1x/jour)*\n"
            "→ Tes 5 prochains rolls ont des taux de rareté boostés !\n\n"
            "🔄 **Reset Claim** `reset_claim` — **1200p**\n"
            "→ Annule ton cooldown claim instantanément"
        ), inline=False)
        embed4.add_field(name="⚡ Réduction cooldown claim *(permanents)*", value=(
            "⚡ **Claim en 20 min** `claim_20` — **800p**\n"
            "⚡ **Claim en 15 min** `claim_15` — **1500p**\n"
            "⚡ **Claim en 10 min** `claim_10` — **3000p**\n"
            "→ Réduit définitivement ton temps d'attente entre chaque claim"
        ), inline=False)
        embed4.add_field(name="⚔️ Items PvP — Sabote tes adversaires !", value=(
            "🧊 **Sceau des Ombres** `freeze` — **500p** *(1x/jour)*\n"
            "→ `.utiliser freeze @joueur` — **bloque son claim pendant 10 secondes** après un tirage !\n\n"
            "⏳ **Malédiction** `curse` — **400p** *(1x/jour)*\n"
            "→ `.utiliser curse @joueur` — **ajoute 5 min** à son cooldown claim\n\n"
            "🛡️ **Bouclier** `shield` — **600p**\n"
            "→ Te protège du Sceau et de la Malédiction pendant **30 minutes**"
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
            description=(
                "Dépense tes pièces pour des avantages exclusifs !\n"
                "Rôles, boosts gacha, items offensifs... tout est là 💰"
            ),
            color=0xf39c12
        )
        embed1.add_field(name="💡 Comment acheter ?", value=(
            "`.shop` — Voir tous les items & prix\n"
            "`.acheter <id>` — Acheter un item *(ex: `.acheter vip`)*\n"
            "`.balance` — Voir ton solde de pièces"
        ), inline=False)
        embed1.add_field(name="👑 Rôles exclusifs", value=(
            "`vip` — 💎 **Rang S VIP** → **1000p**\n"
            "`drama_king` — 👑 **Roi des Malédictions** → **1500p**\n"
            "`oeil_dieu` — 🌀 **Oeil de Dieu** → **1200p**\n"
            "`chasseur` — ⚔️ **Chasseur National** → **800p**\n"
            "`monarque` — 🌑 **Monarque des Ombres** → **3000p**\n"
            "`pilier` — 🔥 **Pillier du Soleil** → **2000p**\n\n"
            "*Ces rôles sont visibles par tout le serveur — affiche ton statut !*"
        ), inline=False)
        embed1.add_field(name="🎰 Boosts Gacha", value=(
            "`rolls_10` — 🎲 **+10 Rolls instantanés** → **600p**\n"
            "→ Utilise immédiatement 10 rolls supplémentaires\n\n"
            "`boost_rarete` — 🎯 **Boost Rareté** *(1x/jour)* → **1500p**\n"
            "→ Tes 5 prochains rolls ont des taux boostés (Mythique passe à 1.5% !)\n\n"
            "`reset_claim` — 🔄 **Reset Claim instantané** → **1200p**\n"
            "→ Supprime ton cooldown de claim immédiatement"
        ), inline=False)
        embed1.add_field(name="⚡ Réduction cooldown claim *(permanents)*", value=(
            "`claim_20` — **Claim en 20 min** → **800p**\n"
            "`claim_15` — **Claim en 15 min** → **1500p**\n"
            "`claim_10` — **Claim en 10 min** → **3000p**\n\n"
            "*Une fois acheté, actif pour toujours sur ce serveur !*"
        ), inline=False)
        embed1.add_field(name="⚔️ Items PvP — Sabote tes adversaires !", value=(
            "`freeze` — 🧊 **Sceau des Ombres** *(1x/jour)* → **500p**\n"
            "→ `.utiliser freeze @joueur` — bloque son claim **10 secondes** après un drop\n\n"
            "`curse` — ⏳ **Malédiction** *(1x/jour)* → **400p**\n"
            "→ `.utiliser curse @joueur` — ajoute **+5 min** à son cooldown claim\n\n"
            "`shield` — 🛡️ **Bouclier** → **600p**\n"
            "→ Te protège du Sceau ET de la Malédiction pendant **30 minutes**"
        ), inline=False)
        embed1.add_field(name="🎯 XP", value=(
            "`double_xp` — ⚡ **Double XP** pendant 1h → **300p**\n"
            "→ Tous tes gains d'XP sont doublés pendant 1 heure !"
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
    global SALON_LEVELUP_ID, SALON_CASINO_ID, SALON_GACHA_ID, SALON_BOUTIQUE_ID
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
    }

    if not type_salon or type_salon.lower() not in TYPES:
        return await ctx.send(
            "❌ Usage : `.setsalon levelup` | `casino` | `gacha` | `boutique` | `combat` | "
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
    }
    current = vals.get(var_name)

    def set_var(vname, value):
        global SALON_LEVELUP_ID, SALON_CASINO_ID, SALON_GACHA_ID, SALON_BOUTIQUE_ID
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
    if itype not in ("freeze","curse") and (uid not in pending or itype not in pending.get(uid,{})):
        return await ctx.send(f"❌ Tu n'as pas l'item `{itype}` ! Achète-le en boutique avec `.acheter {itype}`")

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

autorole_panels = {}   # {guild_id: [{message_id, channel_id, roles: [{emoji, role_id, label}], image}]}
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

@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return
    guild_id = str(payload.guild_id)
    msg_id = str(payload.message_id)
    emoji = str(payload.emoji)
    for p in autorole_panels.get(guild_id, []):
        if p["message_id"] == msg_id:
            for r in p["roles"]:
                if r["emoji"] == emoji:
                    guild = bot.get_guild(payload.guild_id)
                    if not guild:
                        return
                    member = guild.get_member(payload.user_id)
                    role = guild.get_role(int(r["role_id"]))
                    if member and role:
                        try:
                            await member.add_roles(role)
                        except:
                            pass
                    return

@bot.event
async def on_raw_reaction_remove(payload):
    if payload.user_id == bot.user.id:
        return
    guild_id = str(payload.guild_id)
    msg_id = str(payload.message_id)
    emoji = str(payload.emoji)
    for p in autorole_panels.get(guild_id, []):
        if p["message_id"] == msg_id:
            for r in p["roles"]:
                if r["emoji"] == emoji:
                    guild = bot.get_guild(payload.guild_id)
                    if not guild:
                        return
                    member = guild.get_member(payload.user_id)
                    role = guild.get_role(int(r["role_id"]))
                    if member and role:
                        try:
                            await member.remove_roles(role)
                        except:
                            pass
                    return


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
