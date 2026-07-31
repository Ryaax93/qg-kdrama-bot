import discord
from discord.ext import commands, tasks
import asyncio
import random
import json
import os
import datetime
from collections import defaultdict
from discord import ui
import io
try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    PIL_OK = True
except ImportError:
    PIL_OK = False
    print("[Profil] ⚠️ Pillow non installé — .profil utilisera un embed classique. Ajoute 'Pillow' au requirements.txt !")

# ============================================================
#  PERSISTANCE — Volume Railway (survit aux redéploiements)
#  Si un volume est monté sur /data, tous les fichiers y vont.
#  Sinon, comportement normal (dossier courant).
# ============================================================
DATA_DIR = "/data" if os.path.isdir("/data") else "."
def data_path(fname):
    return os.path.join(DATA_DIR, fname)

# ============================================================
#  UI MODERNE — Views avec boutons Discord
# ============================================================
class ConfirmView(ui.View):
    """Boutons Confirmer/Annuler — réservés à un utilisateur précis"""
    def __init__(self, author, timeout=30):
        super().__init__(timeout=timeout)
        self.author = author
        self.value = None

    async def interaction_check(self, interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ Ce n'est pas ton bouton !", ephemeral=True)
            return False
        return True

    @ui.button(label="Confirmer", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm(self, interaction, button):
        self.value = True
        for c in self.children: c.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

    @ui.button(label="Annuler", style=discord.ButtonStyle.danger, emoji="✖️")
    async def cancel(self, interaction, button):
        self.value = False
        for c in self.children: c.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

class AcceptView(ui.View):
    """Boutons Accepter/Refuser — réservés à la cible (trades, demandes)"""
    def __init__(self, target, timeout=60):
        super().__init__(timeout=timeout)
        self.target = target
        self.value = None

    async def interaction_check(self, interaction):
        if interaction.user.id != self.target.id:
            await interaction.response.send_message("❌ Cette demande ne t'est pas adressée !", ephemeral=True)
            return False
        return True

    @ui.button(label="Accepter", style=discord.ButtonStyle.success, emoji="🤝")
    async def accept(self, interaction, button):
        self.value = True
        for c in self.children: c.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

    @ui.button(label="Refuser", style=discord.ButtonStyle.danger, emoji="✖️")
    async def refuse(self, interaction, button):
        self.value = False
        for c in self.children: c.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

class PageView(ui.View):
    """Navigation paginée avec boutons ◀ ▶ — pour help, shop, listes"""
    def __init__(self, pages, author, timeout=120):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.author = author
        self.index = 0

    async def interaction_check(self, interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ Utilise ta propre commande !", ephemeral=True)
            return False
        return True

    def update_footer(self, embed):
        embed.set_footer(text=f"Page {self.index+1}/{len(self.pages)}")
        return embed

    @ui.button(emoji="◀️", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction, button):
        self.index = (self.index - 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.update_footer(self.pages[self.index]), view=self)

    @ui.button(emoji="▶️", style=discord.ButtonStyle.secondary)
    async def next(self, interaction, button):
        self.index = (self.index + 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.update_footer(self.pages[self.index]), view=self)

# ============================================================
#  CONFIG — remplace TOKEN par ton vrai token
# ============================================================
TOKEN = os.getenv("TOKEN")
PREFIX = "."

# ── Loup Garou : durées des phases (utilisées comme valeurs par défaut des vues) ──
LG_DUREE_NUIT = 180   # secondes avant résolution automatique de la nuit
LG_DUREE_JOUR = 300   # secondes de débat avant dépouillement automatique
# ============================================================

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

# ---------- Stockage en mémoire ----------
xp_data = defaultdict(lambda: {"xp": 0, "level": 1})
economy_data = defaultdict(lambda: {"coins": 0, "tier": "Spectateur Débutant"})
# ── Variables manquantes ─────────────────────────────────────
message_count = defaultdict(int)
planning_last_run = {}  # {(weekday, hour): timestamp} anti-doublon
planning_actif = True  # True = events automatiques activés
anniversaire_data = {}               # {uid: "JJ/MM"}

duels = {}
tickets = {}
cooldowns = {}
voice_clients = {}
queues = defaultdict(list)
double_xp_event_actif = False
casino_boost_actif = False
active_pokebattles = {}      # {channel_id: game_data}
active_boss = {}             # {guild_id: {boss, hp, participants, channel, msg}}
jackpot_cagnotte = 0         # cagnotte de l'event Jackpot
inventaire = defaultdict(lambda: defaultdict(int))  # {uid: {item_id: quantité}}
amulette_active = {}         # {uid: timestamp de fin}
oracle_actif = defaultdict(int)      # {uid: rolls restants avec bonus Oracle}
malediction_active = {}      # {uid: timestamp de fin}
ghost_cards = {}             # {f"{uid}_{key}": timestamp de fin}
active_brackets = {}         # {guild_id: {theme, matchs, tour, gagnants, votes_en_cours, channel}}
bank_data = defaultdict(lambda: {"depot": 0, "depot_time": 0})
CONQUETE_ZONE_IDS = []
ROLE_GACHA_ID = None
ROLE_GIRLS_ID = None
ROLE_ANIME_ID = None
SALON_GIRLS_ID = None
SALON_ANNONCES_ID = None

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
SALON_BOUTIQUE_ID = None
SALON_DASHBOARD_ID = None  # salon tableau de bord admin  # Met l'ID du salon boutique ici
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

CONFIG_FILE = data_path("salons_config.json")

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
        "SALON_GIRLS_ID":     SALON_GIRLS_ID,
        "SALON_ANNONCES_ID":  SALON_ANNONCES_ID,
        "SALON_INVITATION_ID": SALON_INVITATION_ID,
        "ROLE_GACHA_ID":      ROLE_GACHA_ID,
        "ROLE_GIRLS_ID":      ROLE_GIRLS_ID,
        "ROLE_ANIME_ID":      ROLE_ANIME_ID,
    }
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        print(f"[Config] Erreur sauvegarde : {e}")

def charger_salons():
    """Charge les IDs de salons depuis le fichier JSON au démarrage"""
    global SALON_LEVELUP_ID, SALON_CASINO_ID, SALON_GACHA_ID, SALON_BOUTIQUE_ID, SALON_EVENT_ID, SALON_GUIDE_ID, ROLE_GACHA_ID, ROLE_GIRLS_ID, ROLE_ANIME_ID
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
        global SALON_GIRLS_ID, SALON_ANNONCES_ID
        SALON_GIRLS_ID   = data.get("SALON_GIRLS_ID")
        SALON_ANNONCES_ID = data.get("SALON_ANNONCES_ID")
        SALON_INVITATION_ID = data.get("SALON_INVITATION_ID")
        ROLE_GACHA_ID = data.get("ROLE_GACHA_ID") or ROLE_GACHA_ID
        ROLE_GIRLS_ID = data.get("ROLE_GIRLS_ID") or ROLE_GIRLS_ID
        ROLE_ANIME_ID = data.get("ROLE_ANIME_ID") or ROLE_ANIME_ID
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
    _pbxp = pet_bonus(uid, "xp")
    if _pbxp:
        xp_gain = int(xp_gain * (1 + _pbxp / 100)) or xp_gain
    xp_data[uid]["xp"] += xp_gain
    give_pet_xp(uid, 1)
    track_stat(uid, "messages")
    needed = xp_data[uid]["level"] * 100
    if xp_data[uid]["xp"] >= needed:
        xp_data[uid]["level"] += 1
        track_stat(uid, "level", amount=0)
        user_stats[uid]["level"] = xp_data[uid]["level"]
        track_stat(uid, "level", amount=0)
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

    # Tracking missions — messages
    try:
        missions_progress[uid]["messages"] += 1
    except: pass
    # Tracking Girls Only
    if SALON_GIRLS_ID and message.channel.id == SALON_GIRLS_ID and ROLE_GIRLS_ID:
        role_girls = message.guild.get_role(ROLE_GIRLS_ID) if message.guild else None
        if role_girls and role_girls in message.author.roles:
            girls_message_count[message.guild.id][str(message.author.id)] += 1
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
#  HELP — 6 pages membres + 4 pages admin (masquées aux membres)
#  Navigation : menu déroulant + boutons
# ============================================================
def _help_footer(embed, i, total):
    dots = "".join("●" if k == i else "○" for k in range(total))
    embed.set_footer(text=f"Page {i+1}/{total}  •  {dots}  •  QG Kdrama 🌸")
    return embed

def build_help_pages(guild, is_admin=False):
    """Construit les pages d'aide. Les pages admin ne sont ajoutées que si is_admin."""
    pages = []

    # ══════════════ 1 — KDRAMA & ANIME ══════════════
    e = discord.Embed(
        title="🎬  Kdrama & Anime",
        description="*Le cœur du serveur — trouver quoi regarder et partager tes avis.*",
        color=0xff6b9d)
    e.add_field(name="🍿 Trouver quoi regarder", value=(
        "`.dramarec` — Un kdrama au hasard\n"
        "`.animerec` — Un animé au hasard\n"
        "`.sorties` — Les prochaines sorties"
    ), inline=False)
    e.add_field(name="🔎 Se renseigner", value=(
        "`.drama <titre>` — Fiche d'un kdrama\n"
        "`.anime <titre>` — Fiche d'un animé\n"
        "`.avis <titre>` — Les notes et avis du serveur"
    ), inline=False)
    e.add_field(name="⭐ Donner son avis", value=(
        "`.noter <1-10> <titre>` — Noter un drama/animé\n"
        "*Ex : `.noter 9 Goblin`*"
    ), inline=False)
    e.add_field(name="📝 Ta watchlist", value=(
        "`.watch ajouter <titre>` — Ajouter à ta liste\n"
        "`.watch liste` — Voir ta liste\n"
        "`.watch retirer <titre>` — Retirer un titre"
    ), inline=False)
    e.add_field(name="🧠 Quiz & Tournois", value=(
        "`.quiz kdrama` / `.quiz anime` — Quiz solo\n"
        "`.quizduel <thème> @joueur` — Quiz en duel\n"
        "`.quizstop` — Arrêter le quiz en cours\n"
        "`.bracket kdrama` — Tournoi des meilleurs kdramas\n"
        "`.quote` / `.animequote` — Une citation au hasard"
    ), inline=False)
    pages.append(("🎬", "Kdrama & Anime", e))

    # ══════════════ 2 — PROFIL & PROGRESSION ══════════════
    e = discord.Embed(
        title="🪪  Profil & Progression",
        description="*Tu progresses juste en discutant — aucune commande obligatoire.*",
        color=0x9b59b6)
    e.add_field(name="👤 Ton profil", value=(
        "`.profil [@membre]` — Ta carte de membre en image\n"
        "`.rank [@membre]` — Niveau et XP en texte\n"
        "`.stats` — Tes statistiques complètes\n"
        "`.leaderboard` — Top 10 du serveur"
    ), inline=False)
    e.add_field(name="🏆 Objectifs", value=(
        "`.succes [@membre]` — Tes 30 succès à débloquer\n"
        "`.missions` — Tes missions du jour"
    ), inline=False)
    e.add_field(name="🐾 Ton compagnon", value=(
        "`.adopter <rareté>` — Adopter un compagnon\n"
        "`.pet` — Le voir • `.pet liste` — Tous les tiens\n"
        "`.pet equiper <nom>` • `.pet nourrir` — +25 XP"
    ), inline=False)
    e.add_field(name="💪 Stats de combat", value=(
        "`.ameliorer <pv|atk|def|endurance>` — Dépenser tes points"
    ), inline=False)
    e.add_field(name="🎂 Divers", value=(
        "`.anniversaire <JJ/MM>` — Enregistrer ta date"
    ), inline=False)
    pages.append(("🪪", "Profil & Progression", e))

    # ══════════════ 3 — ÉCONOMIE ══════════════
    e = discord.Embed(
        title="💰  Économie",
        description="*Les pièces s'utilisent partout : boutique, gacha, compagnons, loterie.*",
        color=0x2ecc71)
    e.add_field(name="💵 Gagner des pièces", value=(
        "`.daily` — Ta récompense du jour (1×/24 h)\n"
        "`.travailler` — Un petit boulot\n"
        "`.balance [@membre]` — Voir son solde"
    ), inline=False)
    e.add_field(name="🏦 Banque & transferts", value=(
        "`.banque` — Déposer / retirer\n"
        "`.pay @membre <montant>` — Envoyer des pièces"
    ), inline=False)
    e.add_field(name="🛒 Dépenser", value=(
        "`.shop` — La boutique\n"
        "`.acheter <id>` — Acheter un article\n"
        "`.utiliser <item> @joueur` — Utiliser un item de sabotage"
    ), inline=False)
    e.add_field(name="🎲 Tenter sa chance", value=(
        "`.slot` — Machine à sous\n"
        "`.jackpot` — La cagnotte en cours\n"
        "`.loto` — Ticket de loterie (100 pièces)\n"
        "`.braquage` — Braquer la banque *(risqué)*\n"
        "`.steal @membre` — Voler un membre *(risqué)*"
    ), inline=False)
    pages.append(("💰", "Économie", e))

    # ══════════════ 4 — GACHA ══════════════
    e = discord.Embed(
        title="🎰  Gacha — collection de cartes",
        description="*Jeu de collection optionnel : ~500 cartes, une carte = un seul propriétaire.*",
        color=0xf1c40f)
    e.add_field(name="🎲 Tirer & réclamer", value=(
        "`.ga` — Tirer une carte au hasard\n"
        "*Puis clique sur le **cœur ❤️** sous la carte pour la garder*\n"
        "`.rolls` — Tirages restants\n"
        "`.invoke` — Invocation Légendaire+ garantie (10 000p)"
    ), inline=False)
    e.add_field(name="📦 Ta collection", value=(
        "`.gachastock [@membre]` — Voir une collection\n"
        "`.cardinfo <perso>` — Détails d'une carte\n"
        "`.serie <nom>` — Progression sur une série\n"
        "`.cartefav add/remove/voir <perso>` — Favoris\n"
        "`.wishlist` — Ta liste de souhaits\n"
        "`.gacha ordre <série> <n°>` — Ranger ta collection"
    ), inline=False)
    e.add_field(name="🔧 Faire évoluer", value=(
        "`.fusionner <perso>` — Fusionner des doublons (⭐)\n"
        "`.burn <perso>` — Recycler une carte contre des pièces\n"
        "`.setimage <perso> <url imgur>` — Changer l'image *(tes cartes)*"
    ), inline=False)
    e.add_field(name="🔄 Échanger", value=(
        "`.gachatrade @membre <ta carte> <sa carte>` — Échange\n"
        "`.gachagive @membre <perso>` — Offrir une carte\n"
        "`.marcheacheter <perso>` — Marché Noir *(event)*\n"
        "`.tradeshistory` — Historique des échanges"
    ), inline=False)
    e.add_field(name="📊 Infos", value=(
        "`.gachastats` — Stats du gacha du serveur\n"
        "`.ouvrir` — Ouvrir un coffre apparu dans le salon"
    ), inline=False)
    pages.append(("🎰", "Gacha", e))

    # ══════════════ 5 — JEUX & COMBATS ══════════════
    e = discord.Embed(
        title="🎮  Jeux & Combats",
        description="*De quoi s'occuper seul ou à plusieurs.*",
        color=0xe74c3c)
    e.add_field(name="🐺 Loup Garou", value=(
        "`.lg` — L'aide complète du jeu\n"
        "`.lgroles` — Les rôles existants\n"
        "`.lgcreate` — Créer une partie • `.lgjoin` — Rejoindre\n"
        "`.lgstart` — Lancer *(hôte)* • `.lgstatus` — État"
    ), inline=False)
    e.add_field(name="🌙 Loup Garou — pendant la partie", value=(
        "`.lgvote @joueur` — Voter au village\n"
        "`.lgkill @cible` — Loups : dévorer\n"
        "`.lgvoir @cible` — Voyante : sonder\n"
        "`.lgsave @cible` / `.lgpoison @cible` — Sorcière\n"
        "`.lglove @a @b` — Cupidon • `.lgkillchasseur @cible` — Chasseur\n"
        "`.lgpass` / `.lgskip` — Passer son tour • `.lgnext` — Suite"
    ), inline=False)
    e.add_field(name="⚔️ Combats", value=(
        "`.arene @membre` — Duel d'arène\n"
        "`.pokebattle @membre` — Combat de cartes\n"
        "`.pokestop` — Annuler le combat en cours\n"
        "`.attaque` — Frapper le boss du serveur *(alias `.attaquerboss`)*"
    ), inline=False)
    e.add_field(name="🎯 Mini-jeux", value=(
        "`.devine` — Devine le personnage\n"
        "`.pendu` — Le pendu (dramas & animés)\n"
        "`.rps <choix>` — Pierre / feuille / ciseaux\n"
        "`.dice` — Lancer un dé"
    ), inline=False)
    pages.append(("🎮", "Jeux & Combats", e))

    # ══════════════ 6 — EVENTS, SOCIAL & DIVERS ══════════════
    e = discord.Embed(
        title="🎪  Events, Social & Divers",
        description="*Le reste : events, vie du serveur, petites commandes pratiques.*",
        color=0x3498db)
    e.add_field(name="📅 Events", value=(
        "`.planning` — Le planning de la semaine\n"
        "`.planningauto` — Les events programmés\n"
        "`.eventstatus` — Quels events sont actifs\n"
        "🎩 **Banquier** et 🏛️ **Enchères** se jouent dans un salon dédié\n"
        "`.faction` — Les factions • `.leavefaction` — Quitter\n"
        "`.liga` — Classement Elo mensuel"
    ), inline=False)
    e.add_field(name="💍 Social", value=(
        "`.marier @membre` — Demander en mariage\n"
        "`.accepter` / `.refuser` — Répondre à une demande\n"
        "`.divorcer` — Divorcer\n"
        "`.invitations` — Tes invitations\n"
        "`.topinvitations` — Le classement des inviteurs"
    ), inline=False)
    e.add_field(name="😄 Fun", value=(
        "`.roast @membre` — Petite vanne\n"
        "`.compliment @membre` — Un compliment\n"
        "`.8ball <question>` — La boule magique\n"
        "`.meme` — Un meme au hasard\n"
        "`.choisir a | b | c` — Le bot choisit pour toi"
    ), inline=False)
    e.add_field(name="🔧 Utilitaires", value=(
        "`.snipe` — Voir le dernier message supprimé\n"
        "`.avatar [@membre]` — L'avatar en grand\n"
        "`.sondage <question>` — Lancer un sondage\n"
        "`.giveaway <durée> <lot>` — Lancer un giveaway\n"
        "`.help` — Cette aide"
    ), inline=False)
    pages.append(("🎪", "Events & Divers", e))

    if not is_admin:
        for i, (_, _, emb) in enumerate(pages):
            _help_footer(emb, i, len(pages))
            if guild and guild.icon:
                emb.set_thumbnail(url=guild.icon.url)
        return pages

    # ══════════════ 7 — ADMIN : MODÉRATION ══════════════
    e = discord.Embed(
        title="🛡️  Admin — Modération",
        description="*Réservé au staff.*",
        color=0x95a5a6)
    e.add_field(name="⚔️ Sanctions", value=(
        "`.ban @membre [raison]` — Bannir\n"
        "`.kick @membre [raison]` — Expulser\n"
        "`.mute @membre [durée]` — Rendre muet\n"
        "`.unmute @membre` — Rendre la parole\n"
        "`.warn @membre <raison>` — Avertir"
    ), inline=False)
    e.add_field(name="🧹 Salon", value=(
        "`.clear <nombre>` — Supprimer des messages\n"
        "`.slowmode <secondes>` — Mode lent\n"
        "`.lock` / `.unlock` — Verrouiller un salon"
    ), inline=False)
    e.add_field(name="📢 Communication", value=(
        "`.announce <message>` — Annonce officielle"
    ), inline=False)
    pages.append(("🛡️", "Admin — Modération", e))

    # ══════════════ 8 — ADMIN : GACHA & CARTES ══════════════
    e = discord.Embed(
        title="🔧  Admin — Gacha & Cartes",
        description="*Gestion des cartes et du système gacha.*",
        color=0x95a5a6)
    e.add_field(name="🎁 Donner / retirer", value=(
        "`.givecard @membre <perso>` — Donner une carte\n"
        "`.removecard @membre <perso>` — Retirer une carte"
    ), inline=False)
    e.add_field(name="✨ Créer", value=(
        "`.addcard <nom> | <série> | <rareté>` — Nouvelle carte\n"
        "*Raretés : Commun • Rare • Épique • Légendaire • Mythique*"
    ), inline=False)
    e.add_field(name="⚙️ Réglages", value=(
        "`.setrollreset <heures>` — Recharge des tirages\n"
        "`.gacharesetall` — ⚠️ Remettre tout le gacha à zéro"
    ), inline=False)
    pages.append(("🔧", "Admin — Gacha", e))

    # ══════════════ 9 — ADMIN : SALONS & CONFIG ══════════════
    e = discord.Embed(
        title="⚙️  Admin — Salons & Configuration",
        description="*À faire une fois, puis c'est mémorisé.*",
        color=0x95a5a6)
    e.add_field(name="📍 Salons — `.setsalon <type>`", value=(
        "*Tape la commande **dans** le salon voulu.*\n"
        "`gacha` `boutique` `casino` `event` `levelup` `guide`\n"
        "`combat` `duel` `dashboard` `bienvenue` `aurevoir`\n"
        "`halloffame` `girlsonly` `annonces` `invitation` `boost` `reglement`"
    ), inline=False)
    e.add_field(name="📖 Publication automatique", value=(
        "`.setsalon guide` — configure **et publie** le guide des nouveaux\n"
        "`.setsalon boutique` — configure **et publie** la boutique\n"
        "`.setsalon girlsonly` — configure **et publie** les commandes filles\n"
        "*Refais la commande pour republier après une mise à jour.*"
    ), inline=False)
    e.add_field(name="🌸 Girls Only", value=(
        "`.setgirlsrole @role` — Définir le rôle filles\n"
        "`.setsalon girlsonly` — Définir le salon *(publie aussi les commandes dedans)*\n"
        "`.setsalon annonces` — Salon des annonces\n"
        "💫 Star of the Week — lundi 10 h  •  💎 Diamond Girl — le 1er du mois"
    ), inline=False)
    e.add_field(name="🔔 Rôles de notification", value=(
        "`.setgacharole @role` — Rôle pingé pour les events gacha\n"
        "`.setanimerole @role` — Rôle pingé pour les events animé"
    ), inline=False)
    e.add_field(name="🎭 Rôles par réaction", value=(
        "`.autorole help` — Créer un panel\n"
        "`.rolecreate @role <emoji> <desc>` — Ajouter un rôle\n"
        "`.roledelete @role` — Retirer • `.rolelist` — Lister"
    ), inline=False)
    e.add_field(name="📊 Suivi", value=(
        "`.dashboard` — Vue d'ensemble du serveur"
    ), inline=False)
    pages.append(("⚙️", "Admin — Config", e))

    # ══════════════ 10 — ADMIN : EVENTS & ÉCONOMIE ══════════════
    e = discord.Embed(
        title="🎪  Admin — Events & Économie",
        description="*Lancer, programmer et régler.*",
        color=0x95a5a6)
    e.add_field(name="▶️ Lancer maintenant", value=(
        "`.lancerevent <nom>` — Démarrer un event\n"
        "`.stopervent` — Arrêter l'event en cours\n"
        "`.boss` — Faire apparaître un boss\n"
        "`.raidstop` — Arrêter le boss/raid en cours"
    ), inline=False)
    e.add_field(name="🗓️ Programmer", value=(
        "`.addevent <event> <jour> <heure>` — Programmer\n"
        "`.delevent <numéro>` — Supprimer *(voir `.planningauto`)*\n"
        "`.eventon` / `.eventoff` — Activer / mettre en pause"
    ), inline=False)
    e.add_field(name="🏆 Tournoi", value=(
        "`.bracketskip` — Résoudre le match en cours\n"
        "`.bracketstop` — Annuler le tournoi"
    ), inline=False)
    e.add_field(name="🐺 Loup Garou", value=(
        "`.lgstop` — Arrêter la partie en cours"
    ), inline=False)
    e.add_field(name="💰 Économie", value=(
        "`.givepieces @membre <montant>` — Donner des pièces\n"
        "`.givexp @membre <montant>` — Donner de l'XP"
    ), inline=False)
    pages.append(("🎪", "Admin — Events", e))

    for i, (_, _, emb) in enumerate(pages):
        _help_footer(emb, i, len(pages))
        if guild and guild.icon:
            emb.set_thumbnail(url=guild.icon.url)
    return pages

class HelpSelect(ui.Select):
    """Menu déroulant pour sauter directement à une catégorie"""
    def __init__(self, pages):
        options = [
            discord.SelectOption(label=label, emoji=emoji, value=str(i),
                                 description=(emb.description or "").strip("*")[:95])
            for i, (emoji, label, emb) in enumerate(pages)
        ]
        super().__init__(placeholder="📚 Choisir une catégorie…", options=options, row=0)

    async def callback(self, interaction):
        self.view.index = int(self.values[0])
        await self.view.refresh(interaction)

class HelpView(ui.View):
    """Navigation du help : menu déroulant + boutons ◀ ▶"""
    def __init__(self, pages, author, timeout=180):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.author = author
        self.index = 0
        self.add_item(HelpSelect(pages))

    async def interaction_check(self, interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ Tape `.help` pour avoir ta propre aide !", ephemeral=True)
            return False
        return True

    async def refresh(self, interaction):
        await interaction.response.edit_message(embed=self.pages[self.index][2], view=self)

    @ui.button(emoji="◀️", style=discord.ButtonStyle.secondary, row=1)
    async def prev(self, interaction, button):
        self.index = (self.index - 1) % len(self.pages)
        await self.refresh(interaction)

    @ui.button(emoji="▶️", style=discord.ButtonStyle.secondary, row=1)
    async def next(self, interaction, button):
        self.index = (self.index + 1) % len(self.pages)
        await self.refresh(interaction)

@bot.command(name="help", aliases=["aide", "commandes"])
async def help_cmd(ctx):
    """Affiche l'aide — .help"""
    is_admin = ctx.author.guild_permissions.administrator if ctx.guild else False
    pages = build_help_pages(ctx.guild, is_admin)
    view = HelpView(pages, ctx.author, timeout=180)
    await ctx.send(embed=pages[0][2], view=view)

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
                    track_stat(str(msg.author.id) if isinstance(str(msg.author.id), str) else str(str(msg.author.id)), "quiz_ok", channel=ctx.channel)
                    xp_data[str(msg.author.id)]["xp"] += 30
                    try: missions_progress[str(msg.author.id)]["quiz"] += 1
                    except: pass
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
@bot.command(name="rank", aliases=["niveau","xp"])
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
#  🎭 RÔLES BOUTIQUE — nom + couleur (créés automatiquement)
# ============================================================
ROLES_BOUTIQUE = {
    # ── Prestige ──
    "shadow":     ("🌑 Monarque des Ombres", 0x2c2f33),
    "pillier":    ("🔥 Pillier du Soleil",   0xe67e22),
    "drama_king": ("👑 Roi des Malédictions", 0x8e44ad),
    "gamer_pro":  ("⚔️ Chasseur National",   0x2980b9),
    "otaku":      ("🌀 Œil de Dieu",         0x1abc9c),
    "vip":        ("💎 Rang S — VIP",        0xf1c40f),
    # ── Girly — chacune sa couleur ──
    "strawberry": ("🍓 Strawberry",  0xe8506e),  # rouge fraise
    "coquette":   ("🎀 Coquette",    0xf7a8c4),  # rose poudré
    "butterfly":  ("🦋 Butterfly",   0xa78bfa),  # lavande
    "snowbunny":  ("❄️ Snow Bunny",  0xeaf2ff),  # blanc neige
    "peachy":     ("🍑 Peachy",      0xffb37a),  # pêche
    "bubblegum":  ("🫧 Bubblegum",   0xff6fd8),  # rose bonbon
    "matcha":     ("🍵 Matcha",      0x9ccc65),  # vert pastel
    "mermaid":    ("🌊 Mermaid",     0x4dd0e1),  # turquoise
    "moongirl":   ("🌙 Moon Girl",   0x8ba3d9),  # bleu argenté
    "maidsenpai": ("🕯️ Maid Senpai", 0xfff3d6),  # crème
    "darkdoll":   ("🖤 Dark Doll",   0x5b4a6b),  # violet sombre
    "slayqueen":  ("👑 Slay Queen",  0xffd166),  # or
}

# ============================================================
#  BOUTIQUE — ITEMS
# ============================================================
# ============================================================
SHOP_ITEMS = [
    # ═══ 🎭 RÔLES PRESTIGE ═══
    {"id": "shadow",     "nom": "🌑 Monarque des Ombres",  "prix": 25000, "cat": "role",  "description": "Le rôle le plus rare du serveur — noir absolu"},
    {"id": "pillier",    "nom": "🔥 Pillier du Soleil",    "prix": 15000, "cat": "role",  "description": "Orange flamboyant, pour les plus actifs"},
    {"id": "drama_king", "nom": "👑 Roi des Malédictions", "prix": 12000, "cat": "role",  "description": "Violet profond façon Jujutsu Kaisen"},
    {"id": "gamer_pro",  "nom": "⚔️ Chasseur National",   "prix": 9000,  "cat": "role",  "description": "Bleu roi — le rang des chasseurs d'élite"},
    {"id": "otaku",      "nom": "🌀 Œil de Dieu",          "prix": 8000,  "cat": "role",  "description": "Turquoise, pour les vrais connaisseurs"},
    {"id": "vip",        "nom": "💎 Rang S — VIP",         "prix": 5000,  "cat": "role",  "description": "Doré — le rang des élus"},

    # ═══ 💗 RÔLES GIRLY — une couleur différente pour chacun ═══
    {"id": "slayqueen",  "nom": "👑 Slay Queen",  "prix": 7000, "cat": "girly", "description": "Doré éclatant — tu ne passes jamais inaperçue"},
    {"id": "darkdoll",   "nom": "🖤 Dark Doll",   "prix": 5500, "cat": "girly", "description": "Violet sombre — poupée gothique"},
    {"id": "mermaid",    "nom": "🌊 Mermaid",     "prix": 5000, "cat": "girly", "description": "Turquoise océan"},
    {"id": "maidsenpai", "nom": "🕯️ Maid Senpai", "prix": 4800, "cat": "girly", "description": "Crème délicat — okaerinasai goshujin-sama"},
    {"id": "snowbunny",  "nom": "❄️ Snow Bunny",  "prix": 4500, "cat": "girly", "description": "Blanc neige immaculé"},
    {"id": "bubblegum",  "nom": "🫧 Bubblegum",   "prix": 4200, "cat": "girly", "description": "Rose bonbon pétillant"},
    {"id": "moongirl",   "nom": "🌙 Moon Girl",   "prix": 4000, "cat": "girly", "description": "Bleu argenté clair de lune"},
    {"id": "butterfly",  "nom": "🦋 Butterfly",   "prix": 3800, "cat": "girly", "description": "Lavande légère"},
    {"id": "matcha",     "nom": "🍵 Matcha",      "prix": 3500, "cat": "girly", "description": "Vert pastel tout doux"},
    {"id": "peachy",     "nom": "🍑 Peachy",      "prix": 3500, "cat": "girly", "description": "Pêche corail"},
    {"id": "strawberry", "nom": "🍓 Strawberry",  "prix": 3000, "cat": "girly", "description": "Rouge fraise acidulé"},
    {"id": "coquette",   "nom": "🎀 Coquette",    "prix": 3000, "cat": "girly", "description": "Rose poudré, nœuds et rubans"},

    # ═══ 🎰 GACHA — BOOSTS ═══
    {"id": "fav_slot_10",  "nom": "🔓 Slots Favoris (10)", "prix": 8000, "cat": "gacha_boost", "description": "Passe ta limite de cartes favorites à 10 (nécessite le slot 5)"},
    {"id": "claim_10",     "nom": "⚡ Claim 10 min",        "prix": 3000, "cat": "gacha_boost", "description": "Réduit ton cooldown de claim à 10 min — permanent"},
    {"id": "fav_slot_5",   "nom": "🔓 Slots Favoris (5)",   "prix": 3000, "cat": "gacha_boost", "description": "Passe ta limite de cartes favorites de 3 à 5"},
    {"id": "boost_rarete", "nom": "🎯 Boost Rareté",        "prix": 1500, "cat": "gacha_boost", "description": "Chances Épique+ fortement augmentées pour 5 rolls", "daily": True},
    {"id": "claim_15",     "nom": "⚡ Claim 15 min",        "prix": 1500, "cat": "gacha_boost", "description": "Réduit ton cooldown de claim à 15 min — permanent"},
    {"id": "cadeau",       "nom": "🎁 Cadeau Mystère",      "prix": 900,  "cat": "gacha_boost", "description": "Une carte aléatoire Rare ou supérieure, offerte"},
    {"id": "claim_20",     "nom": "⚡ Claim 20 min",        "prix": 800,  "cat": "gacha_boost", "description": "Réduit ton cooldown de claim à 20 min — permanent"},
    {"id": "rolls_5",      "nom": "🎰 +5 Rolls",            "prix": 700,  "cat": "gacha_boost", "description": "Cinq tirages supplémentaires immédiatement"},
    {"id": "oracle",       "nom": "🔮 Oracle",              "prix": 499,  "cat": "gacha_boost", "description": "Tes 3 prochains rolls ont 1 chance sur 5 de faire tomber une carte bonus"},
    {"id": "double_rien",  "nom": "🎰 Double ou Rien",      "prix": 200,  "cat": "gacha_boost", "description": "Double tes rolls… ou les perd tous (4 rolls max)"},

    # ═══ ⚔️ GACHA — SABOTAGE ═══
    {"id": "bombe_gacha", "nom": "💣 Bombe Gacha",       "prix": 8000, "cat": "gacha_pvp", "description": "Fait perdre à un joueur sa dernière carte claimée"},
    {"id": "cadenas",     "nom": "🔒 Cadenas",           "prix": 4000, "cat": "gacha_pvp", "description": "Empêche un joueur de claim pendant 30 min"},
    {"id": "fantome",     "nom": "👻 Fantôme",           "prix": 800,  "cat": "gacha_pvp", "description": "Rend une carte d'un joueur invisible 30 min"},
    {"id": "malediction", "nom": "🎭 Malédiction Rare",  "prix": 700,  "cat": "gacha_pvp", "description": "Force le prochain tirage d'un joueur à être Commun", "daily": True},
    {"id": "vol_roll",    "nom": "🎯 Vol de Roll",       "prix": 500,  "cat": "gacha_pvp", "description": "Vole 1 roll à un joueur (3 fois maximum par cible)"},
    {"id": "freeze",      "nom": "🧊 Sceau des Ombres",  "prix": 500,  "cat": "gacha_pvp", "description": "Bloque le claim d'un joueur 10 secondes", "daily": True},
    {"id": "curse",       "nom": "⏳ Malédiction Claim", "prix": 400,  "cat": "gacha_pvp", "description": "Ajoute 5 min au cooldown de claim d'un joueur", "daily": True},

    # ═══ 🛡️ GACHA — PROTECTION ═══
    {"id": "protection", "nom": "🌟 Protection Divine", "prix": 5000, "cat": "gacha_def", "description": "Immunité totale contre tout sabotage pendant 2 h"},
    {"id": "amulette",   "nom": "🪬 Amulette",          "prix": 2500, "cat": "gacha_def", "description": "Renvoie tout sabotage sur l'attaquant pendant 20 min"},
    {"id": "shield",     "nom": "🛡️ Bouclier",         "prix": 600,  "cat": "gacha_def", "description": "Protège du Sceau et des Malédictions pendant 30 min"},

    # ═══ ✨ DIVERS ═══
    {"id": "double_xp", "nom": "⚡ Double XP (1 h)", "prix": 300, "cat": "divers", "description": "Ton XP de messages est doublée pendant une heure"},
]

# Les compagnons sont générés depuis PETS_DB (voir build_shop_pages)

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

    gain = random.randint(80, 150)
    _pb = pet_bonus(uid, "coins")
    if _pb:
        gain = int(gain * (1 + _pb / 100))
    economy_data[uid]["coins"] += gain
    track_stat(uid, "dailies", channel=ctx.channel)
    check_coins_achievements(uid, ctx.channel)
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

    # Tracking missions
    try: missions_progress[uid]["daily"] = 1
    except: pass
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

# ============================================================
#  GACHA — SYSTÈME COMPLET
# ============================================================
import time as _time_module

gacha_wishlist = defaultdict(set)
claim_freeze = {}
claim_curse = {}

RARETE_POIDS = {
    "Mythique":   5,
    "Légendaire": 70,
    "Épique":     500,
    "Rare":       2200,
    "Commun":     7215,
}

def gacha_tirer(uid=None):
    """Tire une carte aléatoire selon les probabilités"""
    pool = list(ANIME_CARDS_DB.keys())
    # Malédiction Rare : forcé en Commun
    if uid and malediction_active.get(uid, 0) > _time_module.time():
        malediction_active.pop(uid, None)
        communs = [k for k in pool if ANIME_CARDS_DB[k]["rarete"] == "Commun"]
        if communs:
            return random.choice(communs)
    # Si boost rareté actif
    if uid and rarity_boost.get(uid, 0) > 0:
        rare_pool = [k for k in pool if ANIME_CARDS_DB[k]["rarete"] in ("Rare","Épique","Légendaire","Mythique")]
        if rare_pool and random.random() < 0.4:
            rarity_boost[uid] -= 1
            return random.choice(rare_pool)
    poids_total = sum(RARETE_POIDS[ANIME_CARDS_DB[k]["rarete"]] for k in pool)
    r = random.randint(1, poids_total)
    cumul = 0
    for key in pool:
        cumul += RARETE_POIDS[ANIME_CARDS_DB[key]["rarete"]]
        if r <= cumul:
            return key
    return random.choice(pool)

def build_card_embed(key, uid_claimer=None, claimed=False):
    c = ANIME_CARDS_DB[key]
    rarete    = c["rarete"]
    r_emoji   = RARETE_EMOJI.get(rarete, "▫️")
    couleur   = RARETE_COULEURS.get(rarete, 0x95a5a6)
    owner_uid = claimed_cards.get(key)

    # Bonus de fusion et de niveau (uniquement si la carte a un propriétaire)
    fus = fusion_levels.get(owner_uid, {}).get(key, 0) if owner_uid else 0
    lvl = card_level.get(owner_uid, {}).get(key, 1) if owner_uid else 1
    b_pv  = fus * 20 + (lvl - 1) * 5
    b_atk = fus * 15 + (lvl - 1) * 3
    b_def = fus * 10 + (lvl - 1) * 2
    etoiles = " " + "⭐" * fus if fus else ""

    embed = discord.Embed(
        title=f"{c.get('emoji','🎴')} {c['nom']}{etoiles}",
        description=f"*{c.get('serie','?')}*  {r_emoji} **{rarete}**",
        color=couleur)

    if c.get("image"):
        embed.set_image(url=c["image"])

    embed.add_field(
        name="📊 Stats",
        value=(f"❤️ **{c.get('pv',100) + b_pv}** PV  |  "
               f"⚔️ **{c.get('attaque',50) + b_atk}** ATK  |  "
               f"🛡️ **{c.get('defense',50) + b_def}** DEF"),
        inline=False)

    if c.get("attaques"):
        embed.add_field(
            name="⚔️ Attaques",
            value="\n".join(f"{a['emoji']} **{a['nom']}** — `{a['degats']} dégâts`"
                            for a in c["attaques"])[:1024],
            inline=False)

    if c.get("faiblesse") or c.get("resistance"):
        embed.add_field(
            name="🧩 Affinités",
            value=f"Faiblesse {c.get('faiblesse','—')}   •   Résistance {c.get('resistance','—')}",
            inline=False)

    if lvl > 1:
        embed.add_field(name="📈 Niveau", value=f"**{lvl}** / 10", inline=False)

    if owner_uid:
        embed.set_footer(text="✅ Carte déjà possédée")
    elif claimed:
        embed.set_footer(text="✅ Claimée !")
    else:
        embed.set_footer(text="❤️ Clique sur le cœur pour la réclamer — 30 secondes")
    return embed

# ============================================================
#  ❤️ CLAIM — bouton cœur sous la carte
# ============================================================
def try_claim(uid, key, guild_id):
    """Tente de claim une carte. Retourne (succès: bool, message: str)."""
    if key not in ANIME_CARDS_DB:
        return False, "❌ Carte introuvable !"
    if key in claimed_cards:
        return False, "❌ Trop tard — cette carte appartient déjà à quelqu'un !"
    now = _time_module.time()
    # Sceau des Ombres / Cadenas — le claim est bloqué
    if claim_freeze.get(uid, 0) > now:
        reste = int(claim_freeze[uid] - now)
        return False, f"🧊 Tu es **bloqué** — encore **{reste}s** avant de pouvoir claim !"
    cooldown_mins = CLAIM_COOLDOWN_MINUTES - claim_reduction.get(uid, 0)
    # Malédiction Claim — +5 min de cooldown
    if claim_curse.get(uid, 0) > now:
        cooldown_mins += 5
    last = claim_cooldown[uid]
    if last and now - last < cooldown_mins * 60:
        reste = int((cooldown_mins * 60 - (now - last)) / 60) + 1
        return False, f"⏳ Ton claim est en recharge — encore **{reste} min**."
    claimed_cards[key] = uid
    gacha_collections[uid][key] = {"fusion": 0}
    claim_cooldown[uid] = now
    economy_data[uid]["coins"] += 10
    return True, "ok"

class ClaimView(ui.View):
    """Bouton ❤️ sous la carte — premier arrivé, premier servi"""
    def __init__(self, key, timeout=30):
        super().__init__(timeout=timeout)
        self.key = key
        self.message = None

    @ui.button(emoji="❤️", style=discord.ButtonStyle.danger)
    async def claim_btn(self, interaction, button):
        uid = str(interaction.user.id)
        ok, msg = try_claim(uid, self.key, interaction.guild.id)
        if not ok:
            return await interaction.response.send_message(msg, ephemeral=True)
        c = ANIME_CARDS_DB[self.key]
        button.disabled = True
        embed = build_card_embed(self.key, uid, claimed=True)
        embed.set_author(name=f"✅  {interaction.user.display_name} a réclamé cette carte !")
        await interaction.response.edit_message(embed=embed, view=self)
        if c["rarete"] == "Mythique":
            unlock_achievement(uid, "mythique_1", interaction.channel)
        check_collection_achievements(uid, interaction.channel)
        self.stop()

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message and self.key not in claimed_cards:
            try:
                embed = build_card_embed(self.key)
                embed.set_footer(text="⏰ Claim expiré — personne n'a réclamé cette carte")
                await self.message.edit(embed=embed, view=self)
            except Exception:
                pass

# ============================================================
#  D. NIVEAU DE CARTE — Helpers
# ============================================================
def card_total_bonus(uid, key):
    """Retourne les bonus totaux d'une carte (fusion + niveau de combat)"""
    fus = fusion_levels[uid].get(key, 0)
    lvl = card_level[uid].get(key, 1)
    # Fusion : +20 PV, +15 ATK, +10 DEF par étoile
    # Niveau combat : +5 PV, +3 ATK, +2 DEF par niveau au-dessus de 1
    bonus_pv  = fus * 20 + (lvl - 1) * 5
    bonus_atk = fus * 15 + (lvl - 1) * 3
    bonus_def = fus * 10 + (lvl - 1) * 2
    return bonus_pv, bonus_atk, bonus_def

def give_card_xp(uid, key, won=True):
    """Donne de l'XP à une carte et gère la montée de niveau. Retourne (level_up, new_level)"""
    if key not in ANIME_CARDS_DB:
        return False, card_level[uid].get(key, 1)
    gain = CARD_XP_WIN if won else CARD_XP_LOSE
    card_xp[uid][key] += gain
    lvl = card_level[uid].get(key, 1)
    leveled = False
    while lvl < CARD_LEVEL_MAX and card_xp[uid][key] >= CARD_XP_PER_LEVEL:
        card_xp[uid][key] -= CARD_XP_PER_LEVEL
        lvl += 1
        leveled = True
    card_level[uid][key] = lvl
    return leveled, lvl

def card_xp_team(uid, equipe, won=True):
    """Donne de l'XP à toute une équipe de cartes, retourne la liste des level-ups"""
    levelups = []
    for carte in equipe:
        key = carte.get("key")
        if key:
            leveled, new_lvl = give_card_xp(uid, key, won)
            if leveled:
                levelups.append((ANIME_CARDS_DB.get(key, {}).get("nom", key), new_lvl))
    return levelups

# ============================================================
#  F. COLLECTION PAR SÉRIE — Helpers
# ============================================================
def get_serie_cards(serie):
    """Retourne toutes les clés de cartes d'une série"""
    return [k for k, c in ANIME_CARDS_DB.items() if c["serie"].lower() == serie.lower()]

def check_serie_complete(uid, serie):
    """Vérifie si un joueur a complété une série. Retourne (complete, owned, total)"""
    serie_keys = get_serie_cards(serie)
    if not serie_keys:
        return False, 0, 0
    owned = sum(1 for k in serie_keys if k in gacha_collections[uid])
    return owned == len(serie_keys), owned, len(serie_keys)

# Récompenses de complétion par taille de série
def serie_reward(total):
    """Récompense en pièces selon la taille de la série complétée"""
    return total * 500   # 500 pièces par carte de la série

@bot.command(name="ga", aliases=["roll"])
async def ga_cmd(ctx):
    """Tire une carte gacha — .ga"""
    if SALON_GACHA_ID and ctx.channel.id != SALON_GACHA_ID:
        salon = ctx.guild.get_channel(SALON_GACHA_ID)
        mention = salon.mention if salon else "le salon gacha"
        return await ctx.send(f"🎰 Le gacha c'est dans {mention} !", delete_after=5)
    uid = str(ctx.author.id)
    now = _time_module.time()
    data = roll_data[uid]
    # Reset rolls toutes les 6h
    if now - data["last_reset"] >= 21600:
        data["rolls"] = ROLLS_MAX
        data["last_reset"] = now
    if data["rolls"] <= 0:
        reset_in = int((21600 - (now - data["last_reset"])) / 60)
        return await ctx.send(f"❌ Plus de rolls ! Recharge dans **{reset_in} min** ou utilise `.daily` pour +1 roll.")
    _proll = pet_bonus(uid, "roll")
    if _proll and random.randint(1, 100) <= _proll:
        pid_r, pdb_r, _ = get_active_pet(uid)
        await ctx.send(f"{pdb_r['emoji']} **{pdb_r['nom']}** te protège — roll gratuit ! 🎁", delete_after=6)
    else:
        data["rolls"] -= 1
    # Tracking missions
    track_stat(uid, "rolls", channel=ctx.channel)
    try: missions_progress[uid]["rolls"] += 1
    except: pass
    key = gacha_tirer(uid)
    c = ANIME_CARDS_DB[key]
    already_owned = key in claimed_cards
    embed = build_card_embed(key)
    embed.set_author(name=f"🎰  Roll de {ctx.author.display_name}  •  {data['rolls']} rolls restants")
    if key in claimed_cards:
        await ctx.send(embed=embed)
    else:
        view = ClaimView(key, timeout=30)
        view.message = await ctx.send(embed=embed, view=view)
    # Notif wishlist
    for wuid, wset in gacha_wishlist.items():
        if key in wset and wuid != uid:
            try:
                m = ctx.guild.get_member(int(wuid))
                if m:
                    await m.send(f"🌟 **{c['nom']}** de ta wishlist vient de drop dans {ctx.channel.mention} !")
            except: pass

@bot.command(name="rolls")
async def rolls_cmd(ctx):
    """Voir tes rolls restants — .rolls"""
    uid = str(ctx.author.id)
    now = _time_module.time()
    data = roll_data[uid]
    if now - data["last_reset"] >= 21600:
        data["rolls"] = ROLLS_MAX
        data["last_reset"] = now
    reset_in = max(0, int((21600 - (now - data["last_reset"])) / 60))
    await ctx.send(embed=discord.Embed(
        description=f"🎰 **{ctx.author.display_name}** — **{data['rolls']}/{ROLLS_MAX} rolls** disponibles\n⏳ Recharge dans **{reset_in} min**",
        color=0x9b59b6
    ))

@bot.command(name="gachastock", aliases=["collection","col"])
async def gachastock_cmd(ctx, member: discord.Member = None):
    """Voir ta collection — .gachastock [@joueur]"""
    target = member or ctx.author
    uid = str(target.id)
    col = gacha_collections[uid]
    if not col:
        return await ctx.send(f"❌ **{target.display_name}** n'a aucune carte !")
    # Trier par rareté
    order = ["Mythique","Légendaire","Épique","Rare","Commun"]
    sorted_cards = sorted(col.keys(), key=lambda k: (order.index(ANIME_CARDS_DB[k]["rarete"]) if k in ANIME_CARDS_DB else 99))
    pages = []
    per_page = 10
    for i in range(0, len(sorted_cards), per_page):
        chunk = sorted_cards[i:i+per_page]
        lines = []
        for k in chunk:
            if k not in ANIME_CARDS_DB: continue
            c = ANIME_CARDS_DB[k]
            r_emoji = RARETE_EMOJI.get(c["rarete"], "⚪")
            lv = fusion_levels[uid].get(k, 0)
            stars = "⭐"*lv if lv else ""
            clvl = card_level[uid].get(k, 1)
            niv = f" `Niv.{clvl}`" if clvl > 1 else ""
            lines.append(f"{r_emoji} **{c['nom']}** {stars}{niv} — *{c['serie']}*")
        embed = discord.Embed(
            title=f"📦 Collection de {target.display_name} ({len(col)} cartes)",
            description="\n".join(lines),
            color=0x9b59b6
        )
        embed.set_footer(text=f"Page {i//per_page+1}/{(len(sorted_cards)-1)//per_page+1}")
        pages.append(embed)
    if len(pages) == 1:
        return await ctx.send(embed=pages[0])
    msg = await ctx.send(embed=pages[0])
    if len(pages) > 1:
        await msg.add_reaction("◀️")
        await msg.add_reaction("▶️")
        idx = [0]
        def check(r, u): return u == ctx.author and r.message.id == msg.id and str(r.emoji) in ["◀️","▶️"]
        while True:
            try:
                r, u = await bot.wait_for("reaction_add", timeout=60, check=check)
                idx[0] = (idx[0]+1) % len(pages) if str(r.emoji)=="▶️" else (idx[0]-1) % len(pages)
                await msg.edit(embed=pages[idx[0]])
                try: await msg.remove_reaction(r.emoji, u)
                except: pass
            except asyncio.TimeoutError:
                try: await msg.clear_reactions()
                except: pass
                break

@bot.command(name="fusionner", aliases=["fusion"])
async def fusionner_cmd(ctx, *, perso: str = None):
    """Fusionner des doublons pour améliorer une carte — .fusionner <perso>"""
    if not perso:
        return await ctx.send("❌ Usage : `.fusionner <nom du perso>`")
    uid = str(ctx.author.id)
    key = perso.lower().strip().replace(" ", "")
    if key not in ANIME_CARDS_DB:
        matches = [k for k in ANIME_CARDS_DB if perso.lower() in ANIME_CARDS_DB[k]["nom"].lower()]
        if not matches: return await ctx.send(f"❌ `{perso}` introuvable !")
        key = matches[0]
    if claimed_cards.get(key) != uid:
        return await ctx.send("❌ Tu ne possèdes pas cette carte !")
    lv = fusion_levels[uid].get(key, 0)
    if lv >= 3:
        return await ctx.send("❌ Fusion max atteinte (⭐⭐⭐) !")
    # Coût : 2 cartes de même rareté
    c = ANIME_CARDS_DB[key]
    meme_rarete = [k2 for k2 in gacha_collections[uid] if k2 != key and ANIME_CARDS_DB.get(k2,{}).get("rarete") == c["rarete"]]
    if len(meme_rarete) < 2:
        return await ctx.send(f"❌ Il te faut 2 autres cartes **{c['rarete']}** pour fusionner !")
    # Retirer 2 cartes
    for k2 in meme_rarete[:2]:
        del gacha_collections[uid][k2]
        if k2 in claimed_cards and claimed_cards[k2] == uid:
            del claimed_cards[k2]
    fusion_levels[uid][key] += 1
    if fusion_levels[uid].get(key, 0) >= 3:
        unlock_achievement(uid, "fusion_max", ctx.channel)
    new_lv = fusion_levels[uid][key]
    await ctx.send(embed=discord.Embed(
        description=f"✨ **{c['nom']}** fusionné ! Niveau {'⭐'*new_lv} !",
        color=RARETE_COULEURS.get(c["rarete"], 0x9b59b6)
    ))

@bot.command(name="gachagive")
async def gachagive_cmd(ctx, target: discord.Member = None, *, perso: str = None):
    """Donner une carte à quelqu'un — .gachagive @joueur <perso>"""
    if not target or not perso:
        return await ctx.send("❌ `.gachagive @joueur <perso>`")
    uid = str(ctx.author.id)
    key = perso.lower().strip().replace(" ","")
    if key not in ANIME_CARDS_DB:
        matches = [k for k in ANIME_CARDS_DB if perso.lower() in ANIME_CARDS_DB[k]["nom"].lower()]
        if not matches: return await ctx.send(f"❌ `{perso}` introuvable !")
        key = matches[0]
    if claimed_cards.get(key) != uid:
        return await ctx.send("❌ Tu ne possèdes pas cette carte !")
    c = ANIME_CARDS_DB[key]
    claimed_cards[key] = str(target.id)
    gacha_collections[str(target.id)][key] = gacha_collections[uid].pop(key, {"fusion": 0})
    await ctx.send(embed=discord.Embed(
        description=f"🎁 **{c['nom']}** donnée à {target.mention} !",
        color=0x2ecc71
    ))

@bot.command(name="wishlist")
async def wishlist_cmd(ctx, action: str = None, *, perso: str = None):
    """Gérer ta wishlist — .wishlist add/remove/voir <perso>"""
    uid = str(ctx.author.id)
    if not action or action == "voir":
        wl = gacha_wishlist[uid]
        if not wl: return await ctx.send("📋 Ta wishlist est vide !")
        names = [ANIME_CARDS_DB[k]["nom"] for k in wl if k in ANIME_CARDS_DB]
        await ctx.send(embed=discord.Embed(title="🌟 Ta Wishlist", description="\n".join(names), color=0xf1c40f))
        return
    if not perso: return await ctx.send("❌ Précise un personnage !")
    key = perso.lower().strip().replace(" ","")
    if key not in ANIME_CARDS_DB:
        matches = [k for k in ANIME_CARDS_DB if perso.lower() in ANIME_CARDS_DB[k]["nom"].lower()]
        if not matches: return await ctx.send(f"❌ `{perso}` introuvable !")
        key = matches[0]
    c = ANIME_CARDS_DB[key]
    if action == "add":
        gacha_wishlist[uid].add(key)
        await ctx.send(f"🌟 **{c['nom']}** ajouté à ta wishlist !")
    elif action == "remove":
        gacha_wishlist[uid].discard(key)
        await ctx.send(f"❌ **{c['nom']}** retiré de ta wishlist !")

# ============================================================
#  ÉCONOMIE — COMMANDES COMPLÈTES
# ============================================================

travailler_cooldowns = {}
braquage_cooldowns = {}

@bot.command(name="travailler", aliases=["work", "boulot"])
async def travailler_cmd(ctx):
    """Travailler pour gagner des pièces — .travailler"""
    uid = str(ctx.author.id)
    now = datetime.datetime.utcnow()
    last = travailler_cooldowns.get(uid)
    if last and (now - last).total_seconds() < 14400:
        reste = 14400 - (now - last).total_seconds()
        h, m = divmod(int(reste)//60, 60)
        return await ctx.send(f"⏳ Tu es fatigué ! Reviens dans **{h}h {m}m**")
    jobs = [
        ("🎬 Doubleur de Kdrama", 80, 160),
        ("🍜 Chef cuisinier coréen", 70, 140),
        ("📸 Photographe de stars", 90, 180),
        ("🎮 Streamer Gaming", 60, 120),
        ("🌸 Traducteur de manhwa", 75, 150),
        ("🎤 Backup dancer K-pop", 100, 200),
        ("📱 Influenceur Kdrama", 85, 170),
        ("🏪 Vendeur de ramyeon", 50, 100),
    ]
    job, mini, maxi = random.choice(jobs)
    gain = random.randint(mini, maxi)
    _pb = pet_bonus(uid, "coins")
    if _pb:
        gain = int(gain * (1 + _pb / 100))
    economy_data[uid]["coins"] += gain
    travailler_cooldowns[uid] = now
    await ctx.send(embed=discord.Embed(
        description=f"{job}\n💰 **{ctx.author.display_name}** a gagné **{gain} pièces** ! Total : {economy_data[uid]['coins']}",
        color=0x2ecc71
    ))

@bot.command(name="braquage", aliases=["voler", "steal", "steal_bank"])
async def braquage_cmd(ctx, target: discord.Member = None):
    """Tenter de braquer quelqu'un — .braquage @joueur"""
    if not target:
        return await ctx.send("❌ `.braquage @joueur`")
    if target.id == ctx.author.id:
        return await ctx.send("❌ Tu peux pas te braquer toi-même !")
    uid = str(ctx.author.id)
    tid = str(target.id)
    now = datetime.datetime.utcnow()
    last = braquage_cooldowns.get(uid)
    if last and (now - last).total_seconds() < 21600:
        reste = 21600 - (now - last).total_seconds()
        h, m = divmod(int(reste)//60, 60)
        return await ctx.send(f"⏳ Cooldown ! Reviens dans **{h}h {m}m**")
    braquage_cooldowns[uid] = now
    if shield_active.get(tid, 0) > _time_module.time():
        return await ctx.send(f"🛡️ **{target.display_name}** est protégé par un bouclier !")
    cible_coins = economy_data[tid]["coins"]
    if cible_coins < 100:
        return await ctx.send(f"💸 **{target.display_name}** est trop pauvre !")
    if random.random() < 0.35:
        montant = random.randint(50, min(300, cible_coins))
        economy_data[uid]["coins"] += montant
        track_stat(uid, "braquages", channel=ctx.channel)
        economy_data[tid]["coins"] -= montant
        await ctx.send(embed=discord.Embed(
            description=f"🦹 **{ctx.author.mention}** a volé **{montant} pièces** à {target.mention} ! 💰",
            color=0x2ecc71
        ))
    else:
        amende = min(random.randint(100, 200), economy_data[uid]["coins"])
        economy_data[uid]["coins"] -= amende
        economy_data[tid]["coins"] += amende
        await ctx.send(embed=discord.Embed(
            description=f"🚨 **{ctx.author.mention}** s'est fait attraper ! Amende : **{amende} pièces** 😂",
            color=0xe74c3c
        ))

@bot.command(name="slot")
async def slot_cmd(ctx, mise: int = 50):
    """Slot machine — .slot [mise]"""
    if SALON_CASINO_ID and ctx.channel.id != SALON_CASINO_ID:
        salon = ctx.guild.get_channel(SALON_CASINO_ID)
        mention = salon.mention if salon else "le salon casino"
        return await ctx.send(f"🎰 Casino dans {mention} !", delete_after=5)
    uid = str(ctx.author.id)
    mise = max(10, min(500, mise))
    if economy_data[uid]["coins"] < mise:
        return await ctx.send(f"❌ Tu n'as que **{economy_data[uid]['coins']} pièces** !")
    economy_data[uid]["coins"] -= mise
    SYMBOLES = ["🌸", "🗡️", "🦊", "👑", "🐉", "💎", "🎭", "⚡"]
    msg = await ctx.send("🎰 | ⏳ | ⏳ | ⏳ |")
    await asyncio.sleep(0.7)
    r1 = random.choice(SYMBOLES)
    await msg.edit(content=f"🎰 | {r1} | ⏳ | ⏳ |")
    await asyncio.sleep(0.7)
    r2 = random.choice(SYMBOLES)
    await msg.edit(content=f"🎰 | {r1} | {r2} | ⏳ |")
    await asyncio.sleep(0.7)
    r3 = random.choice(SYMBOLES)
    await msg.edit(content=f"🎰 | {r1} | {r2} | {r3} |")
    if r1 == r2 == r3:
        gain = mise * (20 if casino_boost_actif else 10)
        economy_data[uid]["coins"] += gain
        embed = discord.Embed(title="🎰 JACKPOT !!!", description=f"**{r1} {r2} {r3}**\n\n🎉 **+{gain} pièces !**", color=0xf1c40f)
    elif r1==r2 or r2==r3 or r1==r3:
        gain = mise * (4 if casino_boost_actif else 2)
        economy_data[uid]["coins"] += gain
        embed = discord.Embed(title="🎰 Paire !", description=f"**{r1} {r2} {r3}**\n\n✅ **+{gain} pièces !**", color=0x2ecc71)
    else:
        embed = discord.Embed(title="🎰 Raté...", description=f"**{r1} {r2} {r3}**\n\n💸 Perdu **{mise} pièces**", color=0xe74c3c)
    embed.set_footer(text=f"💰 Solde : {economy_data[uid]['coins']} pièces")
    await ctx.send(embed=embed)

@bot.command(name="banque")
async def banque_cmd(ctx, action: str = None, montant: int = None):
    """.banque depot/retrait/solde"""
    uid = str(ctx.author.id)
    now = _time_module.time()
    if not action:
        return await ctx.send("🏦 Usage: `.banque depot <montant>` | `.banque retrait` | `.banque solde`")
    action = action.lower()
    if action == "depot":
        if not montant or montant <= 0: return await ctx.send("❌ Précise un montant !")
        if economy_data[uid]["coins"] < montant: return await ctx.send(f"❌ Tu n'as que **{economy_data[uid]['coins']} pièces** !")
        economy_data[uid]["coins"] -= montant
        bank_data[uid]["depot"] += montant
        bank_data[uid]["depot_time"] = now
        await ctx.send(embed=discord.Embed(description=f"🏦 **{montant} pièces** déposées ! +5% intérêts/24h 📈", color=0x2ecc71))
    elif action == "retrait":
        depot = bank_data[uid]["depot"]
        if depot == 0: return await ctx.send("❌ Rien en banque !")
        elapsed = (now - bank_data[uid]["depot_time"]) / 86400
        interets = int(depot * 0.05 * elapsed)
        total = depot + interets
        economy_data[uid]["coins"] += total
        bank_data[uid] = {"depot": 0, "depot_time": 0}
        await ctx.send(embed=discord.Embed(description=f"🏦 Retrait **{total} pièces** (dépôt: {depot} + intérêts: {interets}) 💰", color=0x2ecc71))
    elif action == "solde":
        depot = bank_data[uid]["depot"]
        if depot == 0: return await ctx.send("🏦 Rien en banque !")
        elapsed = (now - bank_data[uid]["depot_time"]) / 86400
        interets = int(depot * 0.05 * elapsed)
        await ctx.send(embed=discord.Embed(title="🏦 Compte bancaire", description=f"💰 Dépôt : **{depot}**\n📈 Intérêts : **+{interets}**\n💎 Total : **{depot+interets}**", color=0xf1c40f))

@bot.command(name="jackpot")
async def jackpot_cmd(ctx):
    """Voir la cagnotte jackpot — .jackpot"""
    await ctx.send(embed=discord.Embed(
        description=f"🎰 **Cagnotte Jackpot** : **{jackpot_cagnotte} pièces** accumulées !\n*Gagnez-la en étant le premier à poster exactement `!jackpot` dans le bon event !*",
        color=0xf1c40f
    ))

def build_shop_pages():
    """Construit les pages de la boutique — utilisé par .shop et .setsalon boutique"""
    cats = {
        "role":        ("🎭 Rôles Prestige",      0xf1c40f),
        "girly":       ("💗 Rôles Girly",          0xff6fd8),
        "pets":        ("🐾 Compagnons",           0xe91e63),
        "gacha_boost": ("🎰 Gacha — Boosts",       0x9b59b6),
        "gacha_pvp":   ("⚔️ Gacha — Sabotage",     0xe74c3c),
        "gacha_def":   ("🛡️ Gacha — Protection",   0x3498db),
        "divers":      ("✨ Divers",                0x2ecc71),
    }
    pages = []
    for cat_id, (cat_name, color) in cats.items():
        if cat_id == "pets":
            # Page générée depuis PETS_DB, groupée par rareté
            ordre = ["Commun", "Rare", "Épique", "Légendaire"]
            embed = discord.Embed(
                title="🛒 Boutique — 🐾 Compagnons",
                description=(
                    "*Un compagnon te donne un **bonus permanent** et monte de niveau quand tu discutes.*\n"
                    "Achète-le avec `.acheter <id>` pour choisir exactement lequel,\n"
                    "ou tente ta chance moins cher avec `.adopter <rareté>` *(aléatoire)*."),
                color=color)
            for rar in ordre:
                lignes = []
                for pid, p in PETS_DB.items():
                    if p["rarete"] != rar:
                        continue
                    t = {"coins": "💰", "xp": "⭐", "roll": "🎰"}[p["type"]]
                    lignes.append(f"{p['emoji']} **{p['nom']}** — `{pid}` · {t} +{p['base']}%")
                if lignes:
                    embed.add_field(
                        name=f"{RARETE_EMOJI.get(rar, '▫️')} {rar} — {PETS_PRIX[rar]:,} pièces",
                        value="\n".join(lignes), inline=False)
            embed.set_footer(text=f"{len(PETS_DB)} compagnons • QG Kdrama 🌸")
            pages.append(embed)
            continue

        items = [i for i in SHOP_ITEMS if i["cat"] == cat_id]
        if not items:
            continue
        embed = discord.Embed(
            title=f"🛒 Boutique — {cat_name}",
            description="*Achète avec* `.acheter <id>`",
            color=color)
        for item in items:
            daily_tag = " *(1×/jour)*" if item.get("daily") else ""
            embed.add_field(
                name=f"{item['nom']} — **{item['prix']:,} pièces**{daily_tag}",
                value=f"`{item['id']}` — {item.get('description', '')}",
                inline=False)
        embed.set_footer(text=f"{len(items)} article(s) • QG Kdrama 🌸")
        pages.append(embed)
    return pages

@bot.command(name="shop", aliases=["boutique", "magasin"])
async def shop_cmd(ctx):
    """Boutique — .shop"""
    if SALON_BOUTIQUE_ID and ctx.channel.id != SALON_BOUTIQUE_ID:
        salon = ctx.guild.get_channel(SALON_BOUTIQUE_ID)
        mention = salon.mention if salon else "le salon boutique"
        return await ctx.send(f"🛒 Boutique dans {mention} !", delete_after=5)
    pages = build_shop_pages()
    if not pages:
        return await ctx.send("❌ Boutique vide !")
    view = PageView(pages, ctx.author, timeout=120) if len(pages) > 1 else None
    await ctx.send(embed=pages[0], view=view)

@bot.command(name="acheter")
async def acheter_cmd(ctx, item_id: str = None):
    """Acheter un item — .acheter <id>"""
    if not item_id: return await ctx.send("❌ `.acheter <id>` — Consulte `.shop`")
    uid = str(ctx.author.id)
    iid_low = item_id.lower()
    item = next((i for i in SHOP_ITEMS if i["id"] == iid_low), None)
    if not item and iid_low in PETS_DB:
        p = PETS_DB[iid_low]
        item = {"id": iid_low, "nom": f"{p['emoji']} {p['nom']}",
                "prix": PETS_PRIX[p["rarete"]], "cat": "pets", "description": p["desc"]}
    if not item: return await ctx.send(f"❌ Item `{item_id}` introuvable ! Consulte `.shop`")
    if economy_data[uid]["coins"] < item["prix"]:
        return await ctx.send(f"❌ Il te manque **{item['prix']-economy_data[uid]['coins']} pièces** !")
    now = _time_module.time()
    if item.get("daily"):
        last = daily_item_usage[uid].get(item["id"], 0)
        if now - last < 86400:
            h = int((86400-(now-last))//3600)
            return await ctx.send(f"⏳ Limité 1x/jour ! Disponible dans **{h}h**")
        daily_item_usage[uid][item["id"]] = now
    economy_data[uid]["coins"] -= item["prix"]
    iid = item["id"]
    if iid in ROLES_BOUTIQUE:
        nom_role, couleur_role = ROLES_BOUTIQUE[iid]
        role = discord.utils.get(ctx.guild.roles, name=nom_role)
        if not role:
            try:
                role = await ctx.guild.create_role(name=nom_role, colour=discord.Colour(couleur_role),
                                                   reason="Rôle boutique")
            except discord.Forbidden:
                economy_data[uid]["coins"] += item["prix"]
                return await ctx.send("❌ Je n'ai pas la permission de créer des rôles !")
        if role in ctx.author.roles:
            economy_data[uid]["coins"] += item["prix"]
            return await ctx.send("❌ Tu possèdes déjà ce rôle !")
        try:
            await ctx.author.add_roles(role, reason="Achat boutique")
        except discord.Forbidden:
            economy_data[uid]["coins"] += item["prix"]
            return await ctx.send("❌ Je ne peux pas t'attribuer ce rôle — mon rôle est trop bas dans la liste.")
        return await ctx.send(embed=discord.Embed(
            title="🎉 Nouveau rôle !",
            description=f"**{nom_role}** est à toi — regarde ta couleur dans la liste des membres.",
            color=couleur_role))

    # ── Achat direct d'un compagnon ──
    if iid in PETS_DB:
        p = PETS_DB[iid]
        prix_pet = PETS_PRIX[p["rarete"]]
        if uid not in pets_data:
            pets_data[uid] = {"owned": {}, "active": None}
        if iid in pets_data[uid]["owned"]:
            economy_data[uid]["coins"] += item["prix"]
            return await ctx.send(f"❌ Tu possèdes déjà **{p['nom']}** ! Utilise `.pet equiper {p['nom']}`.")
        pets_data[uid]["owned"][iid] = {"level": 1, "xp": 0}
        if not pets_data[uid]["active"]:
            pets_data[uid]["active"] = iid
        unlock_achievement(uid, "pet_1", ctx.channel)
        t = {"coins": "💰 pièces", "xp": "⭐ XP", "roll": "🎰 rolls gratuits"}[p["type"]]
        couleurs = {"Commun": 0x95a5a6, "Rare": 0x3498db, "Épique": 0x9b59b6, "Légendaire": 0xf1c40f}
        return await ctx.send(embed=discord.Embed(
            title=f"🐾 {p['emoji']} {p['nom']} rejoint ton équipe !",
            description=(f"**Rareté :** {p['rarete']}\n**Bonus :** +{p['base']}% {t}\n\n"
                         + ("🌟 Équipé automatiquement !" if pets_data[uid]["active"] == iid
                            else f"Utilise `.pet equiper {p['nom']}` pour l'activer.")),
            color=couleurs.get(p["rarete"], 0x95a5a6)))
    if iid == "rolls_5":
        roll_data[uid]["rolls"] = min(roll_data[uid]["rolls"]+5, ROLLS_MAX+5)
        return await ctx.send(embed=discord.Embed(description=f"🎰 **+5 rolls** ! ({roll_data[uid]['rolls']} restants)", color=0x2ecc71))
    if iid == "boost_rarete":
        rarity_boost[uid] = 5
        return await ctx.send(embed=discord.Embed(description=f"🎯 **Boost Rareté** actif pour 5 rolls !", color=0x9b59b6))
    if iid == "double_xp":
        double_xp_users[str(ctx.author.id)] = now + 3600
        return await ctx.send(embed=discord.Embed(description=f"⚡ **Double XP** actif pendant 1h !", color=0x2ecc71))
    if iid == "protection":
        shield_active[uid] = now + 7200
        return await ctx.send(embed=discord.Embed(description=f"🌟 **Protection Divine** active 2h !", color=0xf1c40f))
    if iid == "shield":
        shield_active[uid] = now + 1800
        return await ctx.send(embed=discord.Embed(description=f"🛡️ **Bouclier** actif 30min !", color=0x3498db))
    if iid == "fav_slot_5":
        if fav_slots[uid] >= 5:
            economy_data[uid]["coins"] += item["prix"]
            return await ctx.send("❌ Tu as déjà 5 slots favoris ou plus !")
        fav_slots[uid] = 5
        return await ctx.send(embed=discord.Embed(description="🔓 **Slots favoris augmentés à 5 !** Utilise `.cartefav add` 🌟", color=0x2ecc71))
    if iid == "fav_slot_10":
        if fav_slots[uid] < 5:
            economy_data[uid]["coins"] += item["prix"]
            return await ctx.send("❌ Tu dois d'abord acheter le **Slot Favoris (5)** !")
        if fav_slots[uid] >= 10:
            economy_data[uid]["coins"] += item["prix"]
            return await ctx.send("❌ Tu as déjà 10 slots favoris !")
        fav_slots[uid] = 10
        return await ctx.send(embed=discord.Embed(description="🔓 **Slots favoris augmentés à 10 !** 🌟🌟", color=0x2ecc71))
    # ── Réductions de claim permanentes ──
    if iid in ("claim_10", "claim_15", "claim_20"):
        cible = {"claim_10": 20, "claim_15": 15, "claim_20": 10}[iid]
        if claim_reduction[uid] >= cible:
            economy_data[uid]["coins"] += item["prix"]
            return await ctx.send("❌ Tu as déjà une réduction égale ou meilleure !")
        claim_reduction[uid] = cible
        restant = CLAIM_COOLDOWN_MINUTES - cible
        return await ctx.send(embed=discord.Embed(
            description=f"⚡ Ton cooldown de claim passe à **{restant} minutes** ! *(permanent)*",
            color=0x2ecc71))

    # ── Cadeau Mystère : une carte Rare ou mieux ──
    if iid == "cadeau":
        dispo = [k for k, cc in ANIME_CARDS_DB.items()
                 if cc["rarete"] in ("Rare", "Épique", "Légendaire", "Mythique") and k not in claimed_cards]
        if not dispo:
            economy_data[uid]["coins"] += item["prix"]
            return await ctx.send("❌ Aucune carte disponible pour le moment !")
        key = random.choice(dispo)
        claimed_cards[key] = uid
        gacha_collections[uid][key] = {"fusion": 0}
        check_collection_achievements(uid, ctx.channel)
        cc = ANIME_CARDS_DB[key]
        if cc["rarete"] == "Mythique":
            unlock_achievement(uid, "mythique_1", ctx.channel)
        embed = build_card_embed(key, uid, claimed=True)
        embed.set_author(name="🎁  Cadeau Mystère ouvert !")
        return await ctx.send(embed=embed)

    # ── Double ou Rien : mise sur tes rolls ──
    if iid == "double_rien":
        r = roll_data[uid]["rolls"]
        if r > 4:
            economy_data[uid]["coins"] += item["prix"]
            return await ctx.send("❌ Utilisable seulement avec **4 rolls ou moins** !")
        if random.random() < 0.5:
            roll_data[uid]["rolls"] = min(r * 2, ROLLS_MAX + 5)
            return await ctx.send(embed=discord.Embed(
                description=f"🎰 **DOUBLÉ !** Tu passes de {r} à **{roll_data[uid]['rolls']} rolls** ! 🎉",
                color=0x2ecc71))
        roll_data[uid]["rolls"] = 0
        return await ctx.send(embed=discord.Embed(
            description=f"💀 **Perdu !** Tes {r} rolls sont partis en fumée...", color=0xe74c3c))

    # ── Oracle : chance de carte mystère sur les 3 prochains rolls ──
    if iid == "oracle":
        oracle_actif[uid] = 3
        return await ctx.send(embed=discord.Embed(
            description="🔮 **Oracle activé !** Tes **3 prochains rolls** ont 1 chance sur 5 de faire tomber une carte rare bonus.",
            color=0x9b59b6))

    # ── Amulette : renvoie les sabotages ──
    if iid == "amulette":
        amulette_active[uid] = now + 1200
        return await ctx.send(embed=discord.Embed(
            description="🪬 **Amulette active 20 min** — tout sabotage se retournera contre son auteur.",
            color=0x9b59b6))

    # ── Items offensifs : rangés dans l'inventaire ──
    if iid in ("freeze", "curse", "cadenas", "bombe_gacha", "fantome", "malediction", "vol_roll"):
        inventaire[uid][iid] += 1
        return await ctx.send(embed=discord.Embed(
            title="🛒 Achat réussi !",
            description=(f"✅ **{item['nom']}** ajouté à ton inventaire *(x{inventaire[uid][iid]})*\n"
                         f"Utilise-le avec `.utiliser {iid} @joueur`"),
            color=0x2ecc71))

    await ctx.send(embed=discord.Embed(title="🛒 Achat réussi !", description=f"✅ **{item['nom']}** acheté !", color=0x2ecc71))

# ============================================================
#  SOCIAL — MARIAGE, ANNIVERSAIRE, AVATAR, SNIPE
# ============================================================

mariages = {}
demandes_mariage = {}
reaction_roles = {}            # {message_id: {role_id, emoji, guild_id}}
autorole_panels = {}           # {guild_id: [{message_id, channel_id, roles, image}]}
watchlist_data = defaultdict(list)  # {uid: [{title, status}]}

@bot.command(name="marier")
async def marier_cmd(ctx, cible: discord.Member = None):
    if not cible or cible.bot or cible.id == ctx.author.id:
        return await ctx.send("❌ Mentionne quelqu'un de valide !")
    if str(ctx.author.id) in mariages:
        return await ctx.send("❌ Tu es déjà marié(e) ! `.divorcer` d'abord.")
    demandes_mariage[ctx.author.id] = cible.id
    await ctx.send(embed=discord.Embed(
        title="💍 Demande en Mariage !",
        description=f"💜 **{ctx.author.mention}** demande en mariage **{cible.mention}** !\n\n{cible.mention}, tape `.accepter` pour dire **Oui** 💍 ou `.refuser` pour Non 💔",
        color=0xff6b9d
    ))

@bot.command(name="accepter")
async def accepter_mariage(ctx):
    demandeur_id = next((k for k, v in demandes_mariage.items() if v == ctx.author.id), None)
    if not demandeur_id: return await ctx.send("❌ Aucune demande en attente !")
    demandeur = ctx.guild.get_member(demandeur_id)
    demandes_mariage.pop(demandeur_id, None)
    mariages[str(demandeur_id)] = ctx.author.id
    mariages[str(ctx.author.id)] = demandeur_id
    unlock_achievement(str(ctx.author.id), "mariage", ctx.channel)
    unlock_achievement(str(demandeur_id), "mariage", ctx.channel)
    await ctx.send(embed=discord.Embed(title="💍 Mariage du QG Kdrama ! 🎊", description=f"🎉 **{demandeur.mention}** et **{ctx.author.mention}** sont maintenant mariés ! 💜", color=0xff6b9d))

@bot.command(name="refuser")
async def refuser_mariage(ctx):
    demandeur_id = next((k for k, v in demandes_mariage.items() if v == ctx.author.id), None)
    if not demandeur_id: return await ctx.send("❌ Aucune demande en attente !")
    demandeur = ctx.guild.get_member(demandeur_id)
    demandes_mariage.pop(demandeur_id, None)
    await ctx.send(embed=discord.Embed(description=f"💔 **{ctx.author.mention}** a refusé la demande de **{demandeur.mention}**...", color=0xe74c3c))

@bot.command(name="divorcer")
async def divorcer_cmd(ctx):
    uid = str(ctx.author.id)
    if uid not in mariages: return await ctx.send("❌ Tu n'es pas marié(e) !")
    partner_id = str(mariages[uid])
    mariages.pop(uid, None); mariages.pop(partner_id, None)
    await ctx.send(embed=discord.Embed(description=f"💔 **{ctx.author.mention}** a divorcé... 😢", color=0xe74c3c))

@bot.command(name="anniversaire")
async def anniversaire_cmd(ctx, date: str = None):
    uid = str(ctx.author.id)
    if not date:
        if not anniversaire_data: return await ctx.send("🎂 Aucun anniversaire enregistré !")
        embed = discord.Embed(title="🎂 Anniversaires du QG", color=0xff6b9d)
        for user_id, d in anniversaire_data.items():
            m = ctx.guild.get_member(int(user_id))
            if m: embed.add_field(name=m.display_name, value=f"🎂 {d}", inline=True)
        return await ctx.send(embed=embed)
    try:
        j, mo = date.split("/")
        assert 1<=int(j)<=31 and 1<=int(mo)<=12
    except:
        return await ctx.send("❌ Format `JJ/MM` — Ex: `.anniversaire 25/03`")
    anniversaire_data[uid] = date
    await ctx.send(embed=discord.Embed(description=f"🎂 Anniversaire enregistré le **{date}** ! 🎉", color=0xff6b9d))

snipe_data = {}

@bot.event
async def on_message_delete(message):
    if not message.author.bot:
        snipe_data[message.channel.id] = {"content": message.content, "author": message.author}

@bot.command(name="snipe")
async def snipe_cmd(ctx):
    data = snipe_data.get(ctx.channel.id)
    if not data: return await ctx.send("❌ Rien à snipe !")
    await ctx.send(embed=discord.Embed(
        description=f"👻 **{data['author'].display_name}** avait écrit :\n> {data['content']}",
        color=0x95a5a6
    ))

@bot.command(name="avatar")
async def avatar_cmd(ctx, member: discord.Member = None):
    m = member or ctx.author
    embed = discord.Embed(title=f"🖼️ Avatar de {m.display_name}", color=0x3498db)
    embed.set_image(url=m.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name="stats")
async def stats_cmd(ctx):
    guild = ctx.guild
    embed = discord.Embed(title=f"📊 Stats — {guild.name}", color=0x5865F2)
    embed.add_field(name="👥 Membres", value=f"Total: {guild.member_count}", inline=True)
    embed.add_field(name="💬 Salons", value=f"Texte: {len(guild.text_channels)} | Vocal: {len(guild.voice_channels)}", inline=True)
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    await ctx.send(embed=embed)

@bot.command(name="sondage")
async def sondage_cmd(ctx, *, question: str = None):
    if not question: return await ctx.send("❌ `.sondage <question>`")
    embed = discord.Embed(title="📊 Sondage", description=question, color=0x3498db)
    embed.set_footer(text=f"Par {ctx.author.display_name}")
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("✅"); await msg.add_reaction("❌")

@bot.command(name="giveaway")
async def giveaway_cmd(ctx, duree: str = None, *, prix: str = None):
    if not duree or not prix: return await ctx.send("❌ `.giveaway <durée> <prix>` Ex: `.giveaway 1h Rôle VIP`")
    seconds = 0
    if "h" in duree:
        try: seconds = int(duree.replace("h","")) * 3600
        except: pass
    elif "m" in duree:
        try: seconds = int(duree.replace("m","")) * 60
        except: pass
    if seconds == 0: return await ctx.send("❌ Durée invalide ! Ex: `1h` `30m`")
    embed = discord.Embed(title="🎉 GIVEAWAY !", description=f"**Prix : {prix}**\n\nRéagis avec 🎉 !\n⏳ Fin dans : **{duree}**", color=0xf1c40f)
    embed.set_footer(text=f"Par {ctx.author.display_name}")
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("🎉")
    await asyncio.sleep(seconds)
    try:
        msg = await ctx.channel.fetch_message(msg.id)
        r = discord.utils.get(msg.reactions, emoji="🎉")
        users = [u async for u in r.users() if not u.bot] if r else []
        if users:
            gagnant = random.choice(users)
            await ctx.send(embed=discord.Embed(title="🎉 Fin du Giveaway !", description=f"🏆 **{gagnant.mention}** remporte **{prix}** ! 🎊", color=0x2ecc71))
        else:
            await ctx.send("😔 Personne n'a participé...")
    except: pass

@bot.command(name="choisir")
async def choisir_cmd(ctx, *, args: str = None):
    if not args or " ou " not in args: return await ctx.send("❌ `.choisir <option1> ou <option2>`")
    options = [o.strip() for o in args.split(" ou ")]
    choix = random.choice(options)
    await ctx.send(embed=discord.Embed(description=f"🎲 Je choisis : **{choix}** !", color=0xf1c40f))

# ============================================================
#  DRAMA & ANIMÉ INFO
# ============================================================

@bot.command(name="drama")
async def drama_cmd(ctx, *, titre: str = None):
    if not titre: return await ctx.send("❌ `.drama <titre>`")
    match = next((d for d in KDRAMAS if titre.lower() in d["title"].lower()), None)
    if not match: return await ctx.send(f"❌ Drama `{titre}` non trouvé !")
    embed = discord.Embed(title=f"{match['emoji']} {match['title']}", color=0xff6b9d)
    embed.add_field(name="Genre", value=match["genre"])
    embed.add_field(name="Note", value=match["note"])
    if match.get("image"): embed.set_thumbnail(url=match["image"])
    await ctx.send(embed=embed)

@bot.command(name="dramarec")
async def dramarec_cmd(ctx):
    d = random.choice(KDRAMAS)
    embed = discord.Embed(title=f"🎬 Recommandation : {d['emoji']} {d['title']}", color=0xff6b9d)
    embed.add_field(name="Genre", value=d["genre"]); embed.add_field(name="Note", value=d["note"])
    if d.get("image"): embed.set_thumbnail(url=d["image"])
    await ctx.send(embed=embed)

@bot.command(name="anime")
async def anime_cmd(ctx, *, titre: str = None):
    if not titre: return await ctx.send("❌ `.anime <titre>`")
    match = next((a for a in ANIMES if titre.lower() in a["title"].lower()), None)
    if not match: return await ctx.send(f"❌ Animé `{titre}` non trouvé !")
    embed = discord.Embed(title=f"{match['emoji']} {match['title']}", color=0x9b59b6)
    embed.add_field(name="Genre", value=match["genre"]); embed.add_field(name="Note", value=match["note"])
    await ctx.send(embed=embed)

@bot.command(name="animerec")
async def animerec_cmd(ctx):
    a = random.choice(ANIMES)
    embed = discord.Embed(title=f"✨ Recommandation : {a['emoji']} {a['title']}", color=0x9b59b6)
    embed.add_field(name="Genre", value=a["genre"]); embed.add_field(name="Note", value=a["note"])
    await ctx.send(embed=embed)

@bot.command(name="quote")
async def quote_cmd(ctx):
    await ctx.send(embed=discord.Embed(description=random.choice(KDRAMA_QUOTES), color=0xff6b9d))

@bot.command(name="animequote")
async def animequote_cmd(ctx):
    await ctx.send(embed=discord.Embed(description=random.choice(ANIME_QUOTES), color=0x9b59b6))

# ============================================================
#  ADMIN ÉCONOMIE
# ============================================================

@bot.command(name="givepieces")
@commands.has_permissions(administrator=True)
async def givepieces_cmd(ctx, membre: discord.Member = None, montant: int = None):
    if not membre or not montant: return await ctx.send("❌ `.givepieces @joueur <montant>`")
    economy_data[str(membre.id)]["coins"] += montant
    await ctx.send(embed=discord.Embed(description=f"💰 **+{montant} pièces** données à {membre.mention} !", color=0x2ecc71))

@bot.command(name="givexp")
@commands.has_permissions(administrator=True)
async def givexp_cmd(ctx, membre: discord.Member = None, montant: int = None):
    if not membre or not montant: return await ctx.send("❌ `.givexp @joueur <montant>`")
    xp_data[str(membre.id)]["xp"] += montant
    await ctx.send(embed=discord.Embed(description=f"⭐ **+{montant} XP** donnés à {membre.mention} !", color=0x2ecc71))

@bot.command(name="eventon")
@commands.has_permissions(administrator=True)
async def eventon_cmd(ctx):
    global planning_actif
    planning_actif = True
    await ctx.send(embed=discord.Embed(description="✅ Planning automatique **activé** !", color=0x2ecc71))

@bot.command(name="eventoff")
@commands.has_permissions(administrator=True)
async def eventoff_cmd(ctx):
    global planning_actif
    planning_actif = False
    await ctx.send(embed=discord.Embed(description="🛑 Planning automatique **désactivé** !", color=0xe74c3c))

@bot.command(name="eventstatus")
async def eventstatus_cmd(ctx):
    status = "✅ Activé" if planning_actif else "🛑 Désactivé"
    await ctx.send(embed=discord.Embed(description=f"📊 Planning automatique : **{status}**", color=0x3498db))

@bot.command(name="planning")
async def planning_cmd(ctx):
    """Affiche le planning des events — .planning"""
    embed = discord.Embed(
        title="📅 Planning des Events — QG Kdrama",
        description="Voici comment fonctionnent les events du serveur :",
        color=0x3498db
    )
    embed.add_field(
        name="🎲 Events aléatoires (automatiques)",
        value=(
            "📦 **Coffre** — apparaît au hasard (~1x/h)\n"
            "🌙 **Nuit de Chasse** — taux Mythique ×2 (~toutes les 12h)\n"
            "🕶️ **Marché Noir** — cartes rares à acheter (~toutes les 48h)"
        ),
        inline=False
    )
    embed.add_field(
        name="📆 Events programmés",
        value="Tape `.planningauto` pour voir les events programmés à heure fixe !",
        inline=False
    )
    embed.add_field(
        name="🎪 Events manuels (admin)",
        value=(
            "⚡ Question Éclair • 🎤 Débat • 👑 Roi de la Colline • 🍀 Loterie\n"
            "⚔️ Invasion • 🎰 Nuit Casino • et plus...\n"
            "*Lancés par les admins avec `.lancerevent <nom>`*"
        ),
        inline=False
    )
    statut = "✅ Actifs" if planning_actif else "🛑 En pause"
    embed.set_footer(text=f"Events automatiques : {statut}")
    await ctx.send(embed=embed)

# ============================================================
#  EVENTS À EFFET RÉEL — partagés entre le lancement auto et manuel
# ============================================================
async def run_invasion(channel, guild):
    """⚠️ Invasion — boss dans un salon dédié (les .attaque en rafale polluent sinon)"""
    if guild.id in active_boss:
        return await channel.send("⚔️ Un boss est déjà en cours sur le serveur !")
    salon = await create_event_channel(guild, "🐉・invasion-boss")
    cible = salon or channel
    ping = get_event_ping(guild, "everyone") if cible is channel else ""
    if not await spawn_boss(cible, guild, ping):
        return
    if salon:
        active_boss[guild.id]["salon_temp"] = salon.id
        b = active_boss[guild.id]["boss"]
        await annoncer_event(guild, channel, "everyone", discord.Embed(
            title=f"⚠️ INVASION ! {b['emoji']} {b['nom']} attaque le QG !",
            description=(f"**{b['hp_max']:,} PV** — tout le monde peut frapper avec `.attaque` !\n"
                         f"*Celui qui porte le coup fatal reçoit un bonus.*"),
            color=0xe74c3c), salon)

async def run_coffre(channel, gain=None):
    """📦 Coffre — premier à .ouvrir gagne les pièces"""
    import time as _t
    gain = gain or random.randint(100, 500)
    coffre_actif[channel.id] = {"contenu": gain, "expires": _t.time() + 300}
    await channel.send(embed=discord.Embed(
        title="📦 Un coffre mystérieux est apparu !",
        description=(f"Tape `.ouvrir` rapidement pour récupérer les **{gain} pièces** à l'intérieur !\n"
                     f"⏰ Disponible pendant **5 minutes** — un seul gagnant !"),
        color=0xf1c40f))

async def run_colis(channel, guild):
    """🎁 Colis Mystère — un coffre plus généreux"""
    import time as _t
    gain = random.randint(600, 1500)
    coffre_actif[channel.id] = {"contenu": gain, "expires": _t.time() + 300}
    ping = get_event_ping(guild, "everyone")
    await channel.send(ping, embed=discord.Embed(
        title="🎁 COLIS MYSTÈRE !",
        description=(f"Un colis vient d'arriver au QG — il contient **{gain} pièces** !\n"
                     f"Tape `.ouvrir` pour le récupérer.\n⏰ **5 minutes** — un seul gagnant !"),
        color=0x27ae60))

async def run_nuit_chasse(channel, guild, duree=7200):
    """🌙 Nuit de Chasse — taux Mythique doublés"""
    global nuit_chasse_active
    if nuit_chasse_active:
        return await channel.send("🌙 La Nuit de Chasse est **déjà en cours** !")
    nuit_chasse_active = True
    ping = get_event_ping(guild, "gacha")
    await channel.send(ping, embed=discord.Embed(
        title="🌙 NUIT DE CHASSE !",
        description=(f"🔴 Les taux **Mythique** sont **DOUBLÉS** pendant **{duree//3600} heures** !\n"
                     f"C'est le moment de roll avec `.ga` ! 🎰"),
        color=0x9b59b6))
    await asyncio.sleep(duree)
    nuit_chasse_active = False
    await channel.send(embed=discord.Embed(
        description="🌅 La **Nuit de Chasse** est terminée — les taux reviennent à la normale.",
        color=0x95a5a6))

async def run_double_xp(channel, guild, duree=3600):
    """⚡ Double XP — l'XP des messages est doublée"""
    global double_xp_event_actif
    if double_xp_event_actif:
        return await channel.send("⚡ Le Double XP est **déjà actif** !")
    double_xp_event_actif = True
    ping = get_event_ping(guild, "everyone")
    await channel.send(ping, embed=discord.Embed(
        title="⚡ DOUBLE XP !",
        description=(f"Chaque message rapporte **deux fois plus d'XP** pendant **{duree//60} minutes** !\n"
                     f"Discutez, ça compte double. 💬"),
        color=0x3498db))
    await asyncio.sleep(duree)
    double_xp_event_actif = False
    await channel.send(embed=discord.Embed(
        description="⏰ Le **Double XP** est terminé.", color=0x95a5a6))

async def run_nuit_casino(channel, guild, duree=3600):
    """🎰 Nuit Casino — gains du .slot doublés"""
    global casino_boost_actif
    if casino_boost_actif:
        return await channel.send("🎰 La Nuit Casino est **déjà en cours** !")
    casino_boost_actif = True
    ping = get_event_ping(guild, "everyone")
    await channel.send(ping, embed=discord.Embed(
        title="🎰 NUIT CASINO !",
        description=(f"Les gains de `.slot` sont **doublés** pendant **{duree//60} minutes** !\n"
                     f"Tentez votre chance. 🍀"),
        color=0xf1c40f))
    await asyncio.sleep(duree)
    casino_boost_actif = False
    await channel.send(embed=discord.Embed(
        description="🌅 La **Nuit Casino** est terminée.", color=0x95a5a6))

async def run_marche_noir(channel, guild):
    """🕶️ Marché Noir — 3 cartes rares à acheter pendant 24h"""
    import time as _t
    candidates = [k for k in ANIME_CARDS_DB
                  if ANIME_CARDS_DB[k]["rarete"] in ("Légendaire", "Mythique", "Épique")
                  and k not in claimed_cards]
    if len(candidates) < 3:
        return await channel.send("❌ Pas assez de cartes rares disponibles pour ouvrir le Marché Noir.")
    marche_noir_actif.clear()
    prix_map = {"Mythique": 8000, "Légendaire": 5000, "Épique": 3000}
    desc = "🕶️ **Le Marché Noir ouvre ses portes pour 24h !**\n*Prix gonflés, mais cartes rares garanties...*\n\n"
    for k in random.sample(candidates, 3):
        cc = ANIME_CARDS_DB[k]
        prix = prix_map.get(cc["rarete"], 3000) + random.randint(500, 2000)
        marche_noir_actif[k] = {"prix": prix, "expires": _t.time() + 86400}
        desc += f"{RARETE_EMOJI.get(cc['rarete'],'▫️')} **{cc['nom']}** — **{prix:,} pièces** → `.marcheacheter {k}`\n"
    ping = get_event_ping(guild, "gacha")
    await channel.send(ping, embed=discord.Embed(title="🕶️ MARCHÉ NOIR", description=desc, color=0x2c3e50))

async def run_carte_mystere(channel, guild):
    """🎴 Carte Mystère — une carte rare tombe, premier au cœur la garde"""
    dispo = [k for k in ANIME_CARDS_DB
             if ANIME_CARDS_DB[k]["rarete"] in ("Épique", "Légendaire", "Mythique")
             and k not in claimed_cards]
    if not dispo:
        return await channel.send("❌ Aucune carte rare disponible pour le moment.")
    key = random.choice(dispo)
    ping = get_event_ping(guild, "gacha")
    embed = build_card_embed(key)
    embed.set_author(name="🎴  CARTE MYSTÈRE — première personne au cœur !")
    view = ClaimView(key, timeout=60)
    view.message = await channel.send(ping, embed=embed, view=view)

async def run_jackpot(channel, guild, montant=None):
    """💰 Jackpot — cagnotte au premier qui tape !jackpot"""
    global jackpot_cagnotte
    jackpot_cagnotte = montant or random.randint(1500, 5000)
    ping = get_event_ping(guild, "everyone")
    await channel.send(ping, embed=discord.Embed(
        title="💰 EVENT JACKPOT !",
        description=(f"Une cagnotte de **{jackpot_cagnotte:,} pièces** est en jeu !\n\n"
                     f"Le **premier** à écrire exactement `!jackpot` remporte tout. 🏃"),
        color=0xf1c40f))

async def run_classement(channel, guild):
    """🏆 Classement — le top 5 du serveur, affiché directement"""
    tops = sorted(xp_data.items(), key=lambda x: (x[1].get("level", 1), x[1].get("xp", 0)), reverse=True)[:5]
    lignes = []
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    for i, (uid, d) in enumerate(tops):
        m = guild.get_member(int(uid))
        if m:
            lignes.append(f"{medals[i]} **{m.display_name}** — niveau {d.get('level',1)}")
    ping = get_event_ping(guild, "everyone")
    await channel.send(ping, embed=discord.Embed(
        title="🏆 CLASSEMENT DU MOMENT",
        description="\n".join(lignes) if lignes else "Personne au classement pour l'instant !",
        color=0xf1c40f))

async def run_heure_maudite(channel, guild):
    """😈 Heure Maudite — déclenche un event surprise au hasard"""
    ping = get_event_ping(guild, "everyone")
    await channel.send(ping, embed=discord.Embed(
        title="😈 HEURE MAUDITE",
        description="Quelque chose se prépare au QG... personne ne sait quoi. 🌑",
        color=0xe74c3c))
    await asyncio.sleep(5)
    await random.choice([run_question_eclair, run_roi_colline, run_debat])(channel, guild)


# ============================================================
#  🎪 SALONS TEMPORAIRES D'EVENT — évitent de polluer les discussions
# ============================================================
EVENT_CATEGORY_NAME = "🎪 Events du QG"

async def create_event_channel(guild, nom):
    """Crée un salon temporaire pour un event. Retourne le salon ou None."""
    cat = discord.utils.get(guild.categories, name=EVENT_CATEGORY_NAME)
    if not cat:
        try:
            cat = await guild.create_category(EVENT_CATEGORY_NAME)
        except Exception:
            cat = None
    try:
        return await guild.create_text_channel(nom, category=cat,
                                               topic="Salon temporaire — supprimé à la fin de l'event")
    except Exception as e:
        print(f"[Event] Salon '{nom}' non créé : {e}")
        return None

async def close_event_channel(channel, delai=120):
    """Prévient puis supprime le salon d'event"""
    if not channel:
        return
    try:
        await channel.send(embed=discord.Embed(
            description=f"🚪 Ce salon sera supprimé dans **{delai//60} minute(s)**.",
            color=0x95a5a6))
        await asyncio.sleep(delai)
        await channel.delete(reason="Fin de l'event")
    except Exception:
        pass

async def annoncer_event(guild, salon_event, ping_type, embed, salon_temp=None):
    """Annonce l'event dans le salon events avec le bon ping + lien vers le salon dédié"""
    ping = get_event_ping(guild, ping_type)
    if salon_temp:
        embed.add_field(name="📍 Ça se passe ici",
                        value=f"➡️ {salon_temp.mention}", inline=False)
    try:
        await salon_event.send(ping, embed=embed)
    except Exception as e:
        print(f"[Event] Annonce impossible : {e}")

# ============================================================
#  🎩 LE BANQUIER — Deal or No Deal
# ============================================================
BANQUIER_MONTANTS = [1, 5, 25, 50, 100, 250, 500, 1000, 2000, 3500, 6000, 9000]
BANQUIER_MANCHES = [4, 3, 2, 1, 1]          # valises à ouvrir par manche
BANQUIER_FACTEURS = [0.40, 0.55, 0.70, 0.85, 0.95]   # radin au début, généreux à la fin

class BanquierCandidatView(ui.View):
    """Bouton d'inscription — premier arrivé devient le candidat"""
    def __init__(self, timeout=60):
        super().__init__(timeout=timeout)
        self.candidat = None

    @ui.button(label="Je joue !", emoji="🎩", style=discord.ButtonStyle.success)
    async def jouer(self, interaction, button):
        self.candidat = interaction.user
        button.disabled = True
        button.label = f"{interaction.user.display_name} est en jeu"
        await interaction.response.edit_message(view=self)
        self.stop()

class ValisesView(ui.View):
    """Grille des valises encore fermées"""
    def __init__(self, joueur, restantes, timeout=90):
        super().__init__(timeout=timeout)
        self.joueur = joueur
        self.choix = None
        for i, num in enumerate(sorted(restantes)):
            btn = ui.Button(label=str(num), style=discord.ButtonStyle.secondary, row=i // 4)
            async def cb(interaction, n=num):
                if interaction.user.id != self.joueur.id:
                    return await interaction.response.send_message("❌ Ce n'est pas toi le candidat !", ephemeral=True)
                self.choix = n
                for it in self.children:
                    it.disabled = True
                await interaction.response.edit_message(view=self)
                self.stop()
            btn.callback = cb
            self.add_item(btn)

class DealView(ui.View):
    """DEAL / NO DEAL"""
    def __init__(self, joueur, timeout=60):
        super().__init__(timeout=timeout)
        self.joueur = joueur
        self.deal = None

    async def interaction_check(self, interaction):
        if interaction.user.id != self.joueur.id:
            await interaction.response.send_message("❌ Seul le candidat décide !", ephemeral=True)
            return False
        return True

    @ui.button(label="DEAL", emoji="💰", style=discord.ButtonStyle.success)
    async def deal_btn(self, interaction, button):
        self.deal = True
        for it in self.children: it.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

    @ui.button(label="NO DEAL", emoji="🚫", style=discord.ButtonStyle.danger)
    async def nodeal_btn(self, interaction, button):
        self.deal = False
        for it in self.children: it.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

def _banquier_tableau(montants_restants):
    """Affiche les montants encore en jeu"""
    lignes, ligne = [], []
    for m in BANQUIER_MONTANTS:
        txt = f"**{m:,}**" if m in montants_restants else f"~~{m:,}~~"
        ligne.append(txt)
        if len(ligne) == 4:
            lignes.append(" · ".join(ligne)); ligne = []
    if ligne:
        lignes.append(" · ".join(ligne))
    return "\n".join(lignes)

async def run_banquier(channel, guild):
    """🎩 Le Banquier — Deal or No Deal, dans un salon dédié"""
    salon = await create_event_channel(guild, "🎩・le-banquier")
    if not salon:
        salon = channel

    annonce = discord.Embed(
        title="🎩 LE BANQUIER OUVRE SON BUREAU",
        description=(
            "**12 valises. Une seule sera la vôtre.**\n\n"
            "Un candidat affronte le banquier. Il peut repartir avec "
            "**9 000 pièces**… ou avec **1**.\n\n"
            "*Premier à cliquer sur le bouton entre en jeu.*"),
        color=0x1abc9c)
    if salon is not channel:
        await annoncer_event(guild, channel, "everyone", annonce, salon)

    # ── Recrutement du candidat ──
    view = BanquierCandidatView(timeout=60)
    embed_inscr = discord.Embed(
        title="🎩 LE BANQUIER",
        description="**12 valises. Une seule sera la vôtre.**\n\nQui ose affronter le banquier ?",
        color=0x1abc9c)
    embed_inscr.set_footer(text="⏰ 60 secondes — premier arrivé")
    await salon.send(get_event_ping(guild, "everyone") if salon is channel else "", embed=embed_inscr, view=view)
    await view.wait()

    if not view.candidat:
        await salon.send(embed=discord.Embed(
            description="😴 Personne ne s'est présenté — le banquier referme son bureau.",
            color=0x95a5a6))
        if salon is not channel:
            await close_event_channel(salon, 60)
        return

    joueur = view.candidat
    uid = str(joueur.id)

    # ── Distribution secrète des montants ──
    montants = BANQUIER_MONTANTS[:]
    random.shuffle(montants)
    valises = {i + 1: montants[i] for i in range(12)}
    fermees = set(valises)

    # ── Le candidat choisit SA valise ──
    v = ValisesView(joueur, fermees, timeout=90)
    await salon.send(
        f"{joueur.mention}",
        embed=discord.Embed(
            title=f"🎩 {joueur.display_name} entre en jeu !",
            description="**Choisis TA valise.**\nElle restera fermée jusqu'à la toute fin.",
            color=0x1abc9c),
        view=v)
    await v.wait()
    ma_valise = v.choix or random.choice(list(fermees))
    fermees.discard(ma_valise)

    await salon.send(embed=discord.Embed(
        description=f"🧳 **{joueur.display_name}** garde la valise **n°{ma_valise}**.\n\nQue le jeu commence…",
        color=0x1abc9c))
    await asyncio.sleep(2)

    # ── Les manches ──
    restants = set(valises.values())
    offre_finale = None
    for idx_manche, nb in enumerate(BANQUIER_MANCHES):
        for _ in range(nb):
            if not fermees:
                break
            vw = ValisesView(joueur, fermees, timeout=90)
            e = discord.Embed(
                title=f"🎩 MANCHE {idx_manche + 1} — ouvre une valise",
                description=f"💰 **Montants encore en jeu**\n{_banquier_tableau(restants)}\n\n🧳 Ta valise : **n°{ma_valise}**",
                color=0x3498db)
            msg = await salon.send(f"{joueur.mention} à toi !", embed=e, view=vw)
            await vw.wait()
            num = vw.choix or random.choice(list(fermees))
            fermees.discard(num)
            montant = valises[num]
            restants.discard(montant)
            gros = montant >= 2000
            await salon.send(embed=discord.Embed(
                description=(f"Valise **n°{num}**…\n\n"
                             f"# {'💀' if gros else '😌'}  {montant:,} pièces\n\n"
                             + ("*Aïe. Un gros montant part en fumée.*" if gros
                                else "*Ouf — un petit montant éliminé.*")),
                color=0xe74c3c if gros else 0x2ecc71))
            await asyncio.sleep(1.5)

        if not fermees:
            break

        # ── L'appel du banquier ──
        moyenne = sum(restants) / max(len(restants), 1)
        offre = max(1, int(moyenne * BANQUIER_FACTEURS[min(idx_manche, len(BANQUIER_FACTEURS) - 1)]))
        offre_finale = offre
        dv = DealView(joueur, timeout=60)
        e = discord.Embed(
            title="☎️ LE BANQUIER APPELLE",
            description=(f"Il propose à **{joueur.display_name}** :\n\n"
                         f"# 💰 {offre:,} pièces\n\n"
                         f"**Montants restants**\n{_banquier_tableau(restants)}"),
            color=0xf1c40f)
        e.set_footer(text="⏰ 60 secondes pour décider")
        await salon.send(f"{joueur.mention}", embed=e, view=dv)
        await dv.wait()

        if dv.deal:
            contenu = valises[ma_valise]
            economy_data[uid]["coins"] += offre
            check_coins_achievements(uid, salon)
            ecart = contenu - offre
            await salon.send(embed=discord.Embed(
                title="💰 DEAL !",
                description=(
                    f"**{joueur.display_name}** accepte les **{offre:,} pièces**.\n\n"
                    f"… mais ouvrons sa valise **n°{ma_valise}** :\n\n"
                    f"# {contenu:,} pièces\n\n"
                    + (f"😱 Il laisse **{ecart:,} pièces** sur la table." if ecart > 0
                       else f"😎 Bien joué — il gagne **{abs(ecart):,} pièces** de plus que sa valise !")),
                color=0xf1c40f))
            if salon is not channel:
                await close_event_channel(salon, 180)
            return
        await salon.send(embed=discord.Embed(
            description=f"🚫 **NO DEAL !** {joueur.display_name} continue… 😤", color=0xe74c3c))
        await asyncio.sleep(1.5)

    # ── Il est allé au bout ──
    contenu = valises[ma_valise]
    economy_data[uid]["coins"] += contenu
    check_coins_achievements(uid, salon)
    await salon.send(embed=discord.Embed(
        title="🧳 LA VALISE FINALE",
        description=(
            f"**{joueur.display_name}** a refusé toutes les offres.\n"
            f"*(la dernière était de {offre_finale:,} pièces)*\n\n"
            f"Sa valise **n°{ma_valise}** contient…\n\n"
            f"# 💰 {contenu:,} pièces\n\n"
            + ("🏆 **Quel sang-froid !**" if offre_finale and contenu >= offre_finale
               else "💔 **Il aurait mieux fait d'accepter…**")),
        color=0xf1c40f if (offre_finale and contenu >= offre_finale) else 0xe74c3c))
    if salon is not channel:
        await close_event_channel(salon, 180)


# ============================================================
#  🏛️ LES ENCHÈRES — lot en rotation, compte à rebours relancé
# ============================================================
LOTS_ROTATION = ["carte", "role", "item"]
enchere_rotation = {"index": 0}

ROLES_ENCHERE = ["shadow", "pillier", "drama_king", "vip", "slayqueen", "darkdoll"]

class EnchereModal(ui.Modal, title="Miser un montant"):
    montant = ui.TextInput(label="Ton offre (en pièces)", placeholder="Ex : 3500", max_length=8)

    def __init__(self, etat):
        super().__init__()
        self.etat = etat

    async def on_submit(self, interaction):
        try:
            val = int(str(self.montant.value).replace(" ", ""))
        except ValueError:
            return await interaction.response.send_message("❌ Entre un nombre.", ephemeral=True)
        ok, msg = _placer_enchere(self.etat, interaction.user, val)
        await interaction.response.send_message(msg, ephemeral=True)

def _placer_enchere(etat, membre, montant):
    """Valide et enregistre une enchère. Retourne (succès, message)."""
    import time as _t
    uid = str(membre.id)
    mini = etat["offre"] + etat["increment"] if etat["gagnant"] else etat["offre"]
    if etat["gagnant"] and etat["gagnant"].id == membre.id:
        return False, "❌ Tu détiens déjà la meilleure offre !"
    if montant < mini:
        return False, f"❌ Il faut miser au moins **{mini:,} pièces**."
    if economy_data[uid]["coins"] < montant:
        return False, f"❌ Tu n'as que **{economy_data[uid]['coins']:,} pièces**."
    etat["offre"] = montant
    etat["gagnant"] = membre
    etat["nb"] += 1
    etat["participants"].add(uid)
    etat["deadline"] = _t.time() + etat["duree_relance"]
    return True, f"✅ Offre de **{montant:,} pièces** enregistrée !"

class EnchereView(ui.View):
    def __init__(self, etat, timeout=900):
        super().__init__(timeout=timeout)
        self.etat = etat

    @ui.button(label="Enchérir", emoji="💰", style=discord.ButtonStyle.success)
    async def encherir(self, interaction, button):
        mini = self.etat["offre"] + self.etat["increment"] if self.etat["gagnant"] else self.etat["offre"]
        ok, msg = _placer_enchere(self.etat, interaction.user, mini)
        await interaction.response.send_message(msg, ephemeral=True)

    @ui.button(label="Miser un montant", emoji="✍️", style=discord.ButtonStyle.secondary)
    async def miser(self, interaction, button):
        await interaction.response.send_modal(EnchereModal(self.etat))

async def run_encheres(channel, guild):
    """🏛️ Vente aux enchères — carte, rôle ou item selon la rotation"""
    import time as _t
    type_lot = LOTS_ROTATION[enchere_rotation["index"] % len(LOTS_ROTATION)]
    enchere_rotation["index"] += 1

    lot_nom = lot_desc = None
    lot_image = None
    lot_key = lot_role = lot_item = None
    couleur = 0xf1c40f
    ping_type = "everyone"

    if type_lot == "carte":
        dispo = [k for k, cc in ANIME_CARDS_DB.items()
                 if cc["rarete"] in ("Légendaire", "Mythique") and k not in claimed_cards]
        if not dispo:
            type_lot = "item"
        else:
            lot_key = random.choice(dispo)
            cc = ANIME_CARDS_DB[lot_key]
            lot_nom = f"{RARETE_EMOJI.get(cc['rarete'],'')} {cc['nom']}"
            lot_desc = f"*{cc['serie']}* — **{cc['rarete']}**\n❤️ {cc['pv']} PV · ⚔️ {cc['attaque']} ATK · 🛡️ {cc['defense']} DEF"
            lot_image = cc.get("image")
            couleur = RARETE_COULEURS.get(cc["rarete"], 0xf1c40f)
            ping_type = "gacha"

    if type_lot == "role":
        lot_role, couleur = ROLES_BOUTIQUE[random.choice(ROLES_ENCHERE)]
        lot_nom = lot_role
        lot_desc = "Un rôle exclusif, attribué immédiatement au gagnant."

    if type_lot == "item":
        candidats = [i for i in SHOP_ITEMS if i["cat"] in ("boost", "pvp") and i["prix"] >= 1000]
        lot_item = random.choice(candidats)
        lot_nom = lot_item["nom"]
        lot_desc = f"{lot_item.get('description','')}\n*Valeur boutique : {lot_item['prix']:,} pièces*"
        couleur = 0x9b59b6

    depart = {"carte": 500, "role": 2000, "item": 400}[type_lot]
    increment = max(50, depart // 10)

    salon = await create_event_channel(guild, "🏛️・encheres")
    if not salon:
        salon = channel

    annonce = discord.Embed(
        title="🏛️ VENTE AUX ENCHÈRES",
        description=f"**Lot du jour :** {lot_nom}\n\nMise de départ : **{depart:,} pièces**",
        color=couleur)
    if salon is not channel:
        await annoncer_event(guild, channel, ping_type, annonce, salon)

    etat = {"offre": depart, "gagnant": None, "increment": increment, "nb": 0,
            "participants": set(), "deadline": _t.time() + 60, "duree_relance": 60}
    view = EnchereView(etat)

    def build():
        e = discord.Embed(title="🏛️ ENCHÈRE EN COURS", color=couleur)
        e.add_field(name=f"📦 {lot_nom}", value=lot_desc or "\u200b", inline=False)
        if etat["gagnant"]:
            e.add_field(name="💰 Meilleure offre",
                        value=f"**{etat['offre']:,} pièces**\n🙋 {etat['gagnant'].mention}", inline=True)
        else:
            e.add_field(name="💰 Mise de départ", value=f"**{depart:,} pièces**", inline=True)
        e.add_field(name="📊 Activité",
                    value=f"{etat['nb']} enchère(s)\n{len(etat['participants'])} participant(s)", inline=True)
        reste = max(0, int(etat["deadline"] - _t.time()))
        e.add_field(name="⏰ Temps restant", value=f"**{reste}s**\n*(relancé à chaque offre)*", inline=False)
        if lot_image:
            e.set_image(url=lot_image)
        e.set_footer(text=f"Enchère minimum : +{increment:,} pièces • QG Kdrama")
        return e

    msg = await salon.send(get_event_ping(guild, ping_type) if salon is channel else "",
                           embed=build(), view=view)

    fin_max = _t.time() + 900   # 15 min maximum
    while _t.time() < etat["deadline"] and _t.time() < fin_max:
        await asyncio.sleep(5)
        try:
            await msg.edit(embed=build(), view=view)
        except Exception:
            break

    view.stop()
    try:
        await msg.edit(embed=build(), view=None)
    except Exception:
        pass

    # ── Adjugé ──
    if not etat["gagnant"]:
        await salon.send(embed=discord.Embed(
            description="🔨 **Aucune offre** — le lot retourne dans les réserves.", color=0x95a5a6))
        if salon is not channel:
            await close_event_channel(salon, 60)
        return

    gagnant = etat["gagnant"]
    uid = str(gagnant.id)
    prix = etat["offre"]
    if economy_data[uid]["coins"] < prix:
        await salon.send(embed=discord.Embed(
            description=f"❌ {gagnant.mention} n'a plus les fonds — la vente est annulée.", color=0xe74c3c))
        if salon is not channel:
            await close_event_channel(salon, 60)
        return

    economy_data[uid]["coins"] -= prix
    detail = ""
    if lot_key:
        claimed_cards[lot_key] = uid
        gacha_collections[uid][lot_key] = {"fusion": 0}
        check_collection_achievements(uid, salon)
        if ANIME_CARDS_DB[lot_key]["rarete"] == "Mythique":
            unlock_achievement(uid, "mythique_1", salon)
        detail = "La carte rejoint sa collection."
    elif lot_role:
        role = discord.utils.get(guild.roles, name=lot_role)
        if not role:
            try:
                role = await guild.create_role(name=lot_role, colour=discord.Colour(couleur),
                                               reason="Enchère remportée")
            except Exception:
                role = None
        if role:
            try:
                await gagnant.add_roles(role, reason="Enchère remportée")
                detail = "Le rôle vient de lui être attribué."
            except Exception:
                detail = "⚠️ Rôle non attribué — permissions insuffisantes."
    elif lot_item:
        iid = lot_item["id"]
        if iid in ("freeze", "curse", "cadenas", "bombe_gacha", "fantome", "malediction", "vol_roll"):
            inventaire[uid][iid] += 1
            detail = f"L'objet est dans son inventaire — `.utiliser {iid} @joueur`"
        elif iid == "rolls_5":
            roll_data[uid]["rolls"] = min(roll_data[uid]["rolls"] + 5, ROLLS_MAX + 5)
            detail = "+5 rolls crédités."
        elif iid == "boost_rarete":
            rarity_boost[uid] = 5
            detail = "Boost Rareté actif pour 5 rolls."
        else:
            inventaire[uid][iid] += 1
            detail = "L'objet est dans son inventaire."

    await salon.send(embed=discord.Embed(
        title="🔨 ADJUGÉ !",
        description=(f"**{lot_nom}** revient à {gagnant.mention}\n"
                     f"pour **{prix:,} pièces** !\n\n{detail}\n\n"
                     f"*{etat['nb']} enchères · {len(etat['participants'])} participants*"),
        color=couleur))
    if salon is not channel:
        await close_event_channel(salon, 180)

# ============================================================
#  NOUVEAUX EVENTS — Fonctions réutilisables (auto + manuel)
# ============================================================
async def run_question_eclair(channel, guild):
    """⚡ Question Éclair — 3 premiers à répondre gagnent, dans un salon dédié"""
    q = random.choice(QUESTIONS_ECLAIR)
    salon_principal = channel
    salon = await create_event_channel(guild, "⚡・question-eclair")
    if salon:
        await annoncer_event(guild, salon_principal, q["theme"], discord.Embed(
            title="⚡ QUESTION ÉCLAIR !",
            description="Une question arrive — les **3 premiers** à répondre gagnent des pièces !",
            color=0xf1c40f), salon)
        channel = salon
    ping = get_event_ping(guild, q["theme"]) if channel is salon_principal else ""
    embed = discord.Embed(
        title="⚡ QUESTION ÉCLAIR !",
        description=f"**{q['q']}**\n\n🥇 1er : **200 pièces** • 🥈 2e : **120p** • 🥉 3e : **80p**\n*Réponds vite dans le chat !*",
        color=0xf1c40f
    )
    embed.set_footer(text="⏰ 60 secondes pour répondre !")
    await channel.send(ping, embed=embed)
    gagnants = []
    rewards = [200, 120, 80]
    def check(m):
        return m.channel == channel and not m.author.bot and m.author.id not in [g.id for g in gagnants]
    end = asyncio.get_event_loop().time() + 60
    while len(gagnants) < 3:
        remaining = end - asyncio.get_event_loop().time()
        if remaining <= 0:
            break
        try:
            msg = await bot.wait_for("message", check=check, timeout=remaining)
            if any(check_answer(msg.content, rep) for rep in q["r"]):
                place = len(gagnants)
                gain = rewards[place]
                economy_data[str(msg.author.id)]["coins"] += gain
                gagnants.append(msg.author)
                unlock_achievement(str(msg.author.id), "eclair_win", channel)
                medal = ["🥇", "🥈", "🥉"][place]
                await channel.send(f"{medal} **{msg.author.display_name}** +{gain} pièces !")
        except asyncio.TimeoutError:
            break
    if gagnants:
        await channel.send(embed=discord.Embed(
            description=f"✅ Question terminée ! Bravo aux {len(gagnants)} gagnant(s) ! La réponse était : **{q['r'][0]}**",
            color=0x2ecc71))
    else:
        await channel.send(embed=discord.Embed(
            description=f"⏰ Personne n'a trouvé ! La réponse était : **{q['r'][0]}**",
            color=0xe74c3c))
    if channel is not salon_principal:
        await close_event_channel(channel, 120)

async def run_debat(channel, guild, duree=3600):
    """🎤 Débat du Jour — vote dans un salon dédié, résultat annoncé à la fin"""
    d = random.choice(DEBATS)
    salon = await create_event_channel(guild, "🎤・debat-du-jour")
    if not salon:
        salon = channel
    embed = discord.Embed(
        title="🎤 DÉBAT DU JOUR !",
        description=(f"## {d['sujet']}\n\n🅰️ **{d['a']}**\n🆚\n🅱️ **{d['b']}**\n\n"
                     f"*Votez avec les réactions — résultat dans {duree//60} minutes.*"),
        color=0x9b59b6)
    if salon is not channel:
        annonce = discord.Embed(
            title="🎤 DÉBAT DU JOUR !",
            description=f"## {d['sujet']}\n🅰️ {d['a']}  🆚  🅱️ {d['b']}",
            color=0x9b59b6)
        await annoncer_event(guild, channel, d["theme"], annonce, salon)
        msg = await salon.send(embed=embed)
    else:
        msg = await salon.send(get_event_ping(guild, d["theme"]), embed=embed)
    await msg.add_reaction("🅰️")
    await msg.add_reaction("🅱️")

    await asyncio.sleep(duree)

    # ── Dépouillement ──
    try:
        msg = await salon.fetch_message(msg.id)
    except Exception:
        return
    va = vb = 0
    for r in msg.reactions:
        if str(r.emoji) == "🅰️": va = max(0, r.count - 1)
        elif str(r.emoji) == "🅱️": vb = max(0, r.count - 1)
    total = va + vb
    if total == 0:
        gagnant, detail = "Personne n'a voté", ""
    elif va > vb:
        gagnant, detail = f"🅰️ **{d['a']}**", f"{va} voix contre {vb} ({va*100//total}%)"
    elif vb > va:
        gagnant, detail = f"🅱️ **{d['b']}**", f"{vb} voix contre {va} ({vb*100//total}%)"
    else:
        gagnant, detail = "🤝 **Égalité parfaite !**", f"{va} voix partout"
    await salon.send(embed=discord.Embed(
        title="🎤 RÉSULTAT DU DÉBAT",
        description=f"### {d['sujet']}\n\nLe QG a tranché :\n\n# {gagnant}\n{detail}",
        color=0x9b59b6))
    if salon is not channel:
        await close_event_channel(salon, 300)


async def run_roi_colline(channel, guild):
    """👑 Roi de la Colline — défis en arène"""
    ping = get_event_ping(guild, "everyone")
    embed = discord.Embed(
        title="👑 ROI DE LA COLLINE !",
        description=(
            "Le trône est ouvert ! 👑\n\n"
            "Défiez-vous en `.arene @joueur` pendant **30 minutes** !\n"
            "Le **dernier vainqueur** de la période est couronné **Roi de la Colline** "
            "et remporte **500 pièces bonus** ! 🏆\n\n"
            "*Que le meilleur gagne !*"
        ),
        color=0xf1c40f
    )
    embed.set_footer(text="⚔️ Affrontez-vous en arène pour le trône !")
    await channel.send(ping, embed=embed)

async def run_loterie(channel, guild):
    """🍀 Loterie du QG — tickets puis tirage, dans un salon dédié"""
    salon_principal = channel
    salon = await create_event_channel(guild, "🍀・loterie")
    if salon:
        await annoncer_event(guild, salon_principal, "everyone", discord.Embed(
            title="🍀 LOTERIE DU QG !",
            description="Achète tes tickets — **un seul gagnant rafle toute la cagnotte !**",
            color=0xf1c40f), salon)
        channel = salon
    ping = get_event_ping(guild, "everyone") if channel is salon_principal else ""
    gid = guild.id
    loterie_data[gid] = {"participants": {}, "cagnotte": 0, "active": True}
    embed = discord.Embed(
        title="🍀 LOTERIE DU QG !",
        description=(
            "La loterie est ouverte ! 🎰\n\n"
            "Tape `.loto` pour acheter un ticket (**100 pièces**)\n"
            "Tu peux acheter plusieurs tickets pour augmenter tes chances !\n\n"
            "💰 **Un seul gagnant rafle TOUTE la cagnotte !**\n"
            "⏰ Tirage dans **5 minutes** !"
        ),
        color=0xf1c40f
    )
    await channel.send(ping, embed=embed)
    await asyncio.sleep(300)  # 5 min
    data = loterie_data.get(gid)
    if not data or not data["participants"]:
        loterie_data.pop(gid, None)
        await channel.send(embed=discord.Embed(
            description="🍀 Loterie annulée — aucun participant !", color=0x95a5a6))
        if channel is not salon_principal:
            await close_event_channel(channel, 60)
        return
    # Tirage pondéré par nombre de tickets
    tickets_pool = []
    for uid, nb in data["participants"].items():
        tickets_pool.extend([uid] * nb)
    gagnant_uid = random.choice(tickets_pool)
    cagnotte = data["cagnotte"]
    economy_data[gagnant_uid]["coins"] += cagnotte
    unlock_achievement(gagnant_uid, "loterie_win", channel)
    loterie_data.pop(gid, None)
    member = guild.get_member(int(gagnant_uid))
    nom = member.mention if member else "quelqu'un"
    await channel.send(embed=discord.Embed(
        title="🍀 TIRAGE DE LA LOTERIE !",
        description=f"🎉 Félicitations {nom} !\n💰 Tu remportes la cagnotte de **{cagnotte:,} pièces** !\n\n*{len(tickets_pool)} tickets vendus à {len(data['participants'])} joueurs*",
        color=0xf1c40f))
    if channel is not salon_principal:
        await close_event_channel(channel, 180)

@bot.command(name="loto", aliases=["loterie", "ticket_loto"])
async def loto_cmd(ctx):
    """Acheter un ticket de loterie — .loto (100 pièces)"""
    gid = ctx.guild.id
    if gid not in loterie_data or not loterie_data[gid].get("active"):
        return await ctx.send("❌ Aucune loterie en cours ! Attends qu'un admin en lance une avec `.lancerevent loterie`", delete_after=5)
    uid = str(ctx.author.id)
    PRIX_TICKET = 100
    if economy_data[uid]["coins"] < PRIX_TICKET:
        return await ctx.send(f"❌ Il te faut **{PRIX_TICKET} pièces** pour un ticket !", delete_after=5)
    economy_data[uid]["coins"] -= PRIX_TICKET
    loterie_data[gid]["participants"][uid] = loterie_data[gid]["participants"].get(uid, 0) + 1
    loterie_data[gid]["cagnotte"] += PRIX_TICKET
    nb = loterie_data[gid]["participants"][uid]
    cagnotte = loterie_data[gid]["cagnotte"]
    await ctx.send(embed=discord.Embed(
        description=f"🎟️ **{ctx.author.display_name}** achète un ticket ! *(tu en as {nb})*\n💰 Cagnotte actuelle : **{cagnotte:,} pièces**",
        color=0x2ecc71))

# ============================================================
#  PING INTELLIGENT + DONNÉES DES EVENTS
# ============================================================
def get_event_ping(guild, ping_type):
    """Retourne la mention du rôle à ping selon le type d'event.
    ping_type: 'anime', 'gacha', 'girls', 'everyone', 'none'"""
    if ping_type == "everyone":
        return "@everyone"
    elif ping_type == "anime" and ROLE_ANIME_ID:
        role = guild.get_role(ROLE_ANIME_ID)
        return role.mention if role else ""
    elif ping_type == "gacha" and ROLE_GACHA_ID:
        role = guild.get_role(ROLE_GACHA_ID)
        return role.mention if role else ""
    elif ping_type == "girls" and ROLE_GIRLS_ID:
        role = guild.get_role(ROLE_GIRLS_ID)
        return role.mention if role else ""
    return ""

# Questions pour Question Éclair (avec thème pour ping ciblé)
QUESTIONS_ECLAIR = [
    {"q": "Quel est le nom du renard à 9 queues dans Naruto ?", "r": ["kurama", "kyubi", "kyuubi"], "theme": "anime"},
    {"q": "Comment s'appelle l'épée de Tanjiro dans Demon Slayer ?", "r": ["nichirin", "lame nichirin"], "theme": "anime"},
    {"q": "Quel est le fruit du démon de Luffy ?", "r": ["gomu gomu", "gum gum", "gomu gomu no mi"], "theme": "anime"},
    {"q": "Combien de Titans primordiaux y a-t-il dans Attack on Titan ?", "r": ["9", "neuf"], "theme": "anime"},
    {"q": "Quel est le vrai nom de Light dans Death Note ?", "r": ["light yagami", "yagami"], "theme": "anime"},
    {"q": "Quelle technique signature utilise Gojo dans JJK ?", "r": ["infini", "infinity", "limitless", "illimité"], "theme": "anime"},
    {"q": "Quel personnage dit 'Plus Ultra' dans My Hero Academia ?", "r": ["all might", "allmight"], "theme": "anime"},
    {"q": "Comment s'appelle le carnet dans Death Note ?", "r": ["death note", "cahier de la mort"], "theme": "anime"},
    {"q": "Quelle est la rareté la plus haute du gacha QG ?", "r": ["mythique"], "theme": "gacha"},
    {"q": "Quelle commande permet de tirer une carte ?", "r": [".ga", "ga", ".roll", "roll"], "theme": "gacha"},
    {"q": "Combien de rolls as-tu au maximum dans le gacha ?", "r": ["10", "dix"], "theme": "gacha"},
    {"q": "Quelle est la capitale de la Corée du Sud ?", "r": ["seoul", "séoul"], "theme": "culture"},
    {"q": "Dans quel pays se déroulent les K-dramas ?", "r": ["corée", "corée du sud", "coree"], "theme": "culture"},
    {"q": "Quel drama Netflix coréen a explosé en 2021 avec un jeu mortel ?", "r": ["squid game"], "theme": "culture"},
    {"q": "Combien font 7 × 8 ?", "r": ["56"], "theme": "culture"},
]

# Sujets de débat (avec 2 options + thème)
DEBATS = [
    {"sujet": "Meilleur protagoniste shonen ?", "a": "Luffy 🏴‍☠️", "b": "Naruto 🍥", "theme": "anime"},
    {"sujet": "Le meilleur anime de combat ?", "a": "Demon Slayer 🗡️", "b": "Jujutsu Kaisen 💥", "theme": "anime"},
    {"sujet": "Qui gagnerait ?", "a": "Goku 🐉", "b": "Saitama 👊", "theme": "anime"},
    {"sujet": "Le meilleur Hokage ?", "a": "Minato ⚡", "b": "Itachi 🔴", "theme": "anime"},
    {"sujet": "Meilleur studio d'animation ?", "a": "MAPPA", "b": "Ufotable", "theme": "anime"},
    {"sujet": "Sub ou Dub ?", "a": "VOSTFR 🇯🇵", "b": "VF 🇫🇷", "theme": "anime"},
    {"sujet": "Le meilleur genre de K-drama ?", "a": "Romance 💜", "b": "Thriller 🔪", "theme": "culture"},
    {"sujet": "Team ?", "a": "Chat 🐱", "b": "Chien 🐶", "theme": "everyone"},
    {"sujet": "Le meilleur repas ?", "a": "Pizza 🍕", "b": "Burger 🍔", "theme": "everyone"},
    {"sujet": "Plutôt ?", "a": "Été ☀️", "b": "Hiver ❄️", "theme": "everyone"},
]

@bot.command(name="lancerevent")
@commands.has_permissions(manage_guild=True)
async def lancerevent_cmd(ctx, nom: str = None):
    if not nom:
        await ctx.send(embed=discord.Embed(
            title="🎪 Events Disponibles",
            description=(
                "**👥 Ouverts à tout le monde :**\n"
                "`questioneclair` `debatdujour` `roicolline` `loterie`\n"
                "`invasion` `coffre` `colis` `jackpot` `classement`\n"
                "`banquier` `encheres`\n"
                "`doublexp` `nuitcasino` `heuremaudite`\n\n"
                "**🎰 Orientés gacha :**\n"
                "`nuitchasse` `marchenoir` `cartemystere`\n\n"
                "*Usage : `.lancerevent <nom>` — tous ont un effet réel.*"
            ),
            color=0x3498db
        ))
        return
    nom = nom.lower()
    channel = ctx.guild.get_channel(SALON_EVENT_ID) if SALON_EVENT_ID else ctx.channel
    if not channel:
        channel = ctx.channel

    # ── Nouveaux events interactifs ──
    if nom in ("questioneclair", "question", "eclair"):
        return await run_question_eclair(channel, ctx.guild)
    if nom in ("debatdujour", "debat"):
        return await run_debat(channel, ctx.guild)
    if nom in ("roicolline", "roi", "colline"):
        return await run_roi_colline(channel, ctx.guild)
    if nom in ("loterie", "loto"):
        return await run_loterie(channel, ctx.guild)

    if nom in ("invasion", "boss", "invasiondemons"):
        return await run_invasion(channel, ctx.guild)

    # ── Events à effet réel ──
    if nom in ("coffre",):
        return await run_coffre(channel)
    if nom in ("colis",):
        return await run_colis(channel, ctx.guild)
    if nom in ("nuitchasse", "chasse"):
        return await run_nuit_chasse(channel, ctx.guild)
    if nom in ("doublexp", "xp2"):
        return await run_double_xp(channel, ctx.guild)
    if nom in ("nuitcasino", "casino"):
        return await run_nuit_casino(channel, ctx.guild)
    if nom in ("marchenoir", "marche"):
        return await run_marche_noir(channel, ctx.guild)
    if nom in ("cartemystere", "carte"):
        return await run_carte_mystere(channel, ctx.guild)
    if nom in ("jackpot",):
        return await run_jackpot(channel, ctx.guild)
    if nom in ("classement", "top"):
        return await run_classement(channel, ctx.guild)
    if nom in ("heuremaudite", "maudite"):
        return await run_heure_maudite(channel, ctx.guild)
    if nom in ("banquier", "banque", "deal"):
        return await run_banquier(channel, ctx.guild)
    if nom in ("encheres", "enchere", "vente"):
        return await run_encheres(channel, ctx.guild)
    await ctx.send(f"❌ Event `{nom}` inconnu — utilise `.lancerevent` sans argument pour la liste !")

@bot.command(name="stopervent", aliases=["stopevent"])
@commands.has_permissions(manage_guild=True)
async def stopervent_cmd(ctx):
    """Arrête tous les events en cours — .stopervent"""
    global nuit_chasse_active, double_xp_event_actif, casino_boost_actif, jackpot_cagnotte
    arretes = []
    if nuit_chasse_active:
        nuit_chasse_active = False; arretes.append("🌙 Nuit de Chasse")
    if double_xp_event_actif:
        double_xp_event_actif = False; arretes.append("⚡ Double XP")
    if casino_boost_actif:
        casino_boost_actif = False; arretes.append("🎰 Nuit Casino")
    if jackpot_cagnotte:
        jackpot_cagnotte = 0; arretes.append("💰 Jackpot")
    if marche_noir_actif:
        marche_noir_actif.clear(); arretes.append("🕶️ Marché Noir")
    if coffre_actif:
        coffre_actif.clear(); arretes.append("📦 Coffres")
    if ctx.guild.id in active_boss:
        _st = active_boss[ctx.guild.id].get("salon_temp")
        del active_boss[ctx.guild.id]; arretes.append("⚔️ Boss")
        if _st:
            _ch = ctx.guild.get_channel(_st)
            if _ch:
                asyncio.create_task(close_event_channel(_ch, 30))
    if ctx.guild.id in loterie_data:
        del loterie_data[ctx.guild.id]; arretes.append("🍀 Loterie")
    if ctx.guild.id in active_brackets:
        del active_brackets[ctx.guild.id]; arretes.append("🏆 Tournoi")
    if not arretes:
        return await ctx.send("✅ Aucun event n'était en cours.")
    await ctx.send(embed=discord.Embed(
        title="🛑 Events arrêtés",
        description="\n".join(f"• {a}" for a in arretes),
        color=0xe74c3c))


@bot.command(name="setsalon")
@commands.has_permissions(administrator=True)
async def setsalon_cmd(ctx, type_salon: str = None):
    global SALON_GACHA_ID, SALON_BOUTIQUE_ID, SALON_CASINO_ID, SALON_EVENT_ID
    global SALON_LEVELUP_ID, SALON_COMBAT_ID, SALON_DUEL_ID, SALON_DASHBOARD_ID
    global SALON_BIENVENUE_ID, SALON_AUREVOIR_ID, SALON_HOF_ID, SALON_GUIDE_ID, SALON_INVITATION_ID
    global SALON_BOOST_ID, SALON_REGLEMENT_ID
    if not type_salon:
        return await ctx.send("❌ Types : `gacha` `boutique` `casino` `event` `levelup` `guide` `combat` `duel` `dashboard` `bienvenue` `aurevoir` `halloffame` `girlsonly` `annonces` `invitation` `boost` `reglement`")
    mapping = {
        "gacha": "SALON_GACHA_ID", "boutique": "SALON_BOUTIQUE_ID",
        "casino": "SALON_CASINO_ID", "event": "SALON_EVENT_ID",
        "levelup": "SALON_LEVELUP_ID", "guide": "SALON_GUIDE_ID",
        "combat": "SALON_COMBAT_ID",
        "duel": "SALON_DUEL_ID", "dashboard": "SALON_DASHBOARD_ID",
        "bienvenue": "SALON_BIENVENUE_ID", "aurevoir": "SALON_AUREVOIR_ID",
        "halloffame": "SALON_HOF_ID", "girlsonly": "SALON_GIRLS_ID",
        "annonces": "SALON_ANNONCES_ID", "invitation": "SALON_INVITATION_ID",
        "boost": "SALON_BOOST_ID", "reglement": "SALON_REGLEMENT_ID",
    }
    t = type_salon.lower()
    if t not in mapping:
        return await ctx.send(f"❌ Type inconnu ! Types valides : {', '.join(mapping.keys())}")
    var = mapping[t]
    if var == "SALON_GACHA_ID": SALON_GACHA_ID = ctx.channel.id
    elif var == "SALON_BOUTIQUE_ID": SALON_BOUTIQUE_ID = ctx.channel.id
    elif var == "SALON_CASINO_ID": SALON_CASINO_ID = ctx.channel.id
    elif var == "SALON_EVENT_ID": SALON_EVENT_ID = ctx.channel.id
    elif var == "SALON_LEVELUP_ID": SALON_LEVELUP_ID = ctx.channel.id
    elif var == "SALON_GUIDE_ID": SALON_GUIDE_ID = ctx.channel.id
    elif var == "SALON_INVITATION_ID": SALON_INVITATION_ID = ctx.channel.id
    elif var == "SALON_BOOST_ID": SALON_BOOST_ID = ctx.channel.id
    elif var == "SALON_REGLEMENT_ID": SALON_REGLEMENT_ID = ctx.channel.id
    elif var == "SALON_COMBAT_ID": SALON_COMBAT_ID = ctx.channel.id
    elif var == "SALON_DUEL_ID": SALON_DUEL_ID = ctx.channel.id
    elif var == "SALON_DASHBOARD_ID": SALON_DASHBOARD_ID = ctx.channel.id
    elif var == "SALON_BIENVENUE_ID": SALON_BIENVENUE_ID = ctx.channel.id
    elif var == "SALON_AUREVOIR_ID": SALON_AUREVOIR_ID = ctx.channel.id
    elif var == "SALON_HOF_ID": SALON_HOF_ID = ctx.channel.id
    elif var == "SALON_GIRLS_ID":
        global SALON_GIRLS_ID
        SALON_GIRLS_ID = ctx.channel.id
    elif var == "SALON_ANNONCES_ID":
        global SALON_ANNONCES_ID
        SALON_ANNONCES_ID = ctx.channel.id
    sauvegarder_salons()
    await ctx.send(embed=discord.Embed(
        description=f"✅ Salon **{type_salon}** configuré sur {ctx.channel.mention} !", color=0x2ecc71))

    # Le salon guide reçoit directement le guide
    if t == "guide":
        try:
            for e in build_guide_embeds(ctx.guild):
                await ctx.channel.send(embed=e)
                await asyncio.sleep(0.4)
        except Exception as e:
            print(f"[Guide] Erreur publication : {e}")

    # Le salon boutique reçoit directement la boutique
    if t == "boutique":
        try:
            for e in build_shop_pages():
                await ctx.channel.send(embed=e)
                await asyncio.sleep(0.3)
        except Exception as e:
            print(f"[Boutique] Erreur publication : {e}")

    # Le salon Girls Only reçoit directement ses commandes — les filles les voient sur place
    if t == "girlsonly":
        presentation = discord.Embed(
            title="🌸  Bienvenue dans le Girls Only",
            description="*Cet espace est réservé aux filles du serveur. Voilà tout ce qui s'y passe.*",
            color=0xff9ec7)
        presentation.add_field(name="👗 Fit Check", value=(
            "`.fit <description de ta tenue>`\n"
            "Partage ton look du jour, les autres réagissent 💕"
        ), inline=False)
        presentation.add_field(name="🌙 Ritual du Soir", value=(
            "Chaque soir à **21 h**, une question drama est postée ici.\n"
            "Rien à taper : réponds simplement dans le salon."
        ), inline=False)
        presentation.add_field(name="💫 Star of the Week", value=(
            "Chaque **lundi à 10 h**, la fille la plus active de la semaine est mise à l'honneur."
        ), inline=False)
        presentation.add_field(name="💎 Diamond Girl", value=(
            "Le **1er de chaque mois**, la fille la plus active du mois reçoit le titre."
        ), inline=False)
        presentation.set_footer(text="QG Kdrama • Girls Only 🌸")
        try:
            await ctx.channel.send(embed=presentation)
        except Exception:
            pass

@bot.command(name="setgirlsrole")
@commands.has_permissions(administrator=True)
async def setgirlsrole_cmd(ctx, role: discord.Role = None):
    global ROLE_GIRLS_ID
    if not role:
        return await ctx.send("❌ `.setgirlsrole @role`")
    ROLE_GIRLS_ID = role.id
    sauvegarder_salons()
    await ctx.send(embed=discord.Embed(description=f"✅ Rôle Girls Only configuré : **{role.name}**", color=0xff69b4))

@bot.command(name="setanimerole")
@commands.has_permissions(administrator=True)
async def setanimerole_cmd(ctx, role: discord.Role = None):
    """Configure le rôle Anime (pour les pings d'events anime) — .setanimerole @role"""
    global ROLE_ANIME_ID
    if not role:
        return await ctx.send("❌ `.setanimerole @role`")
    ROLE_ANIME_ID = role.id
    sauvegarder_salons()
    await ctx.send(embed=discord.Embed(description=f"✅ Rôle Anime configuré : **{role.name}**\nIl sera pingé pour les events anime/manga.", color=0x9b59b6))

@bot.command(name="setgacharole")
@commands.has_permissions(administrator=True)
async def setgacharole_cmd(ctx, role: discord.Role = None):
    """Configure le rôle Gacha (pour les pings d'events gacha) — .setgacharole @role"""
    global ROLE_GACHA_ID
    if not role:
        return await ctx.send("❌ `.setgacharole @role`")
    ROLE_GACHA_ID = role.id
    sauvegarder_salons()
    await ctx.send(embed=discord.Embed(description=f"✅ Rôle Gacha configuré : **{role.name}**\nIl sera pingé pour les events gacha.", color=0xf1c40f))

    ROLE_GIRLS_ID = role.id
    sauvegarder_salons()
    await ctx.send(embed=discord.Embed(description=f"✅ Rôle Girls configuré : **{role.name}**", color=0xff6b9d))

@bot.command(name="announce")
@commands.has_permissions(manage_guild=True)
async def announce_cmd(ctx, *, texte: str = None):
    if not texte: return await ctx.send("❌ `.announce <texte>`")
    channel = ctx.guild.get_channel(SALON_ANNONCES_ID) if SALON_ANNONCES_ID else ctx.channel
    embed = discord.Embed(
        title="📢 Annonce Officielle — QG Kdrama",
        description=texte,
        color=0xff6b9d
    )
    embed.set_footer(text=f"Par {ctx.author.display_name} • {datetime.datetime.now().strftime('%d/%m/%Y')}")
    await (channel or ctx.channel).send(embed=embed)

@bot.command(name="fit")
async def fit_cmd(ctx, *, description: str = None):
    """Poster une tenue dans le salon Girls Only — .fit <description>"""
    if ROLE_GIRLS_ID:
        role = discord.utils.get(ctx.guild.roles, id=ROLE_GIRLS_ID)
        if role and role not in ctx.author.roles:
            return await ctx.send("❌ Réservé aux filles du serveur ! 🌸")
    if not description: return await ctx.send("❌ `.fit <description de ta tenue>`")
    channel = ctx.guild.get_channel(SALON_GIRLS_ID) if SALON_GIRLS_ID else ctx.channel
    embed = discord.Embed(
        title="👗 Fit Check du QG !",
        description=f"**{ctx.author.display_name}** partage son look :\n\n*{description}*",
        color=0xff6b9d
    )
    embed.set_thumbnail(url=ctx.author.display_avatar.url)
    msg = await (channel or ctx.channel).send(embed=embed)
    for emoji in ["🔥","💜","✨","👑","🌸"]:
        await msg.add_reaction(emoji)

@bot.command(name="warn")
@commands.has_permissions(manage_messages=True)
async def warn_cmd(ctx, member: discord.Member = None, *, reason: str = "Aucune raison"):
    if not member: return await ctx.send("❌ `.warn @joueur [raison]`")
    try:
        await member.send(embed=discord.Embed(
            title=f"⚠️ Avertissement — {ctx.guild.name}",
            description=f"**Raison :** {reason}",
            color=0xf39c12
        ))
    except: pass
    await ctx.send(embed=discord.Embed(description=f"⚠️ **{member.display_name}** averti. Raison : {reason}", color=0xf39c12))

@bot.command(name="slowmode")
@commands.has_permissions(manage_channels=True)
async def slowmode_cmd(ctx, secondes: int = 0):
    await ctx.channel.edit(slowmode_delay=secondes)
    await ctx.send(f"🐢 Slowmode : **{secondes}s**" if secondes > 0 else "⚡ Slowmode désactivé !")

@bot.command(name="lock")
@commands.has_permissions(manage_channels=True)
async def lock_cmd(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send("🔒 Salon verrouillé !")

@bot.command(name="unlock")
@commands.has_permissions(manage_channels=True)
async def unlock_cmd(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=None)
    await ctx.send("🔓 Salon déverrouillé !")

@bot.command(name="addcard")
@commands.has_permissions(administrator=True)
async def addcard_cmd(ctx, *, args: str = None):
    """Ajouter une carte custom — .addcard <nom> | <serie> | <rarete> | <emoji> | <url>"""
    if not args or "|" not in args:
        return await ctx.send("❌ `.addcard <nom> | <serie> | <rarete> | <emoji> | <url>`\nRaretés : Commun Rare Épique Légendaire Mythique")
    parts = [p.strip() for p in args.split("|")]
    if len(parts) < 4: return await ctx.send("❌ Format invalide !")
    nom, serie, rarete = parts[0], parts[1], parts[2]
    emoji = parts[3] if len(parts) > 3 else "⭐"
    url = parts[4] if len(parts) > 4 else ""
    rarete_valid = ["Commun","Rare","Épique","Légendaire","Mythique"]
    if rarete not in rarete_valid: return await ctx.send(f"❌ Rareté invalide ! Choisis : {', '.join(rarete_valid)}")
    key = nom.lower().replace(" ","")
    stats = {"Commun":(160,65,60),"Rare":(185,75,70),"Épique":(210,90,80),"Légendaire":(225,100,85),"Mythique":(250,115,95)}
    pv, atk, defe = stats[rarete]
    ANIME_CARDS_DB[key] = {
        "nom": nom, "serie": serie, "rarete": rarete, "emoji": emoji,
        "pv": pv, "attaque": atk, "defense": defe,
        "image": url,
        "attaques": [{"nom":"Attaque","emoji":"⚔️","degats":40,"desc":"Frappe"},{"nom":"Spéciale","emoji":"💥","degats":55,"desc":"Puissant"}],
        "faiblesse":"⚡","resistance":"🌟"
    }
    embed = discord.Embed(
        title="✅ Carte ajoutée !",
        description=f"**{emoji} {nom}** — *{serie}* — {RARETE_EMOJI.get(rarete,'⚪')} **{rarete}**",
        color=RARETE_COULEURS.get(rarete, 0x95a5a6)
    )
    if url: embed.set_thumbnail(url=url)
    await ctx.send(embed=embed)

@bot.command(name="dashboard")
@commands.has_permissions(administrator=True)
async def dashboard_cmd(ctx):
    guild = ctx.guild
    total_coins = sum(v["coins"] for v in economy_data.values())
    total_cards = len(claimed_cards)
    top_level = sorted(xp_data.items(), key=lambda x: x[1]["level"], reverse=True)[:3]
    top_str = "\n".join([f"• <@{uid}> Niv.{d['level']}" for uid,d in top_level]) or "Aucune donnée"
    embed = discord.Embed(title="📊 Dashboard Admin — QG Kdrama", color=0xff6b9d)
    embed.add_field(name="👥 Membres", value=str(guild.member_count), inline=True)
    embed.add_field(name="💰 Pièces en circulation", value=f"{total_coins:,}", inline=True)
    embed.add_field(name="🎴 Cartes claimées", value=f"{total_cards}/{len(ANIME_CARDS_DB)}", inline=True)
    embed.add_field(name="🏆 Top Niveaux", value=top_str, inline=False)
    embed.add_field(name="📅 Planning", value="✅ Actif" if planning_actif else "🛑 Désactivé", inline=True)
    embed.set_footer(text=f"Dashboard — {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}")
    await ctx.send(embed=embed)

# ============================================================
#  TASKS PLANIFIÉES
# ============================================================

# ============================================================
#  SCHEDULER — Programmation d'events auto (jour + heure)
# ============================================================
SCHEDULED_EVENTS_FILE = data_path("scheduled_events.json")
scheduled_events = []   # [{"event": "loterie", "jour": "samedi", "heure": 20, "minute": 0}]

JOURS_MAP = {
    "lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3,
    "vendredi": 4, "samedi": 5, "dimanche": 6,
    "lun": 0, "mar": 1, "mer": 2, "jeu": 3, "ven": 4, "sam": 5, "dim": 6,
}
JOURS_NOMS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]

# Liste de TOUS les events programmables (validation)
EVENTS_VALIDES = [
    "questioneclair", "debatdujour", "roicolline", "loterie",
    "coffre", "cartemystere", "nuitcasino", "nuitchasse", "marchenoir",
    "doublexp", "jackpot", "colis", "invasion", "heuremaudite", "classement",
    "banquier", "encheres",
]

def save_scheduled_events():
    try:
        with open(SCHEDULED_EVENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(scheduled_events, f, ensure_ascii=False)
    except Exception as e:
        print(f"[Scheduler] Erreur sauvegarde : {e}")

def load_scheduled_events():
    global scheduled_events
    if not os.path.exists(SCHEDULED_EVENTS_FILE):
        return
    try:
        with open(SCHEDULED_EVENTS_FILE, "r", encoding="utf-8") as f:
            scheduled_events = json.load(f)
        print(f"[Scheduler] ✅ {len(scheduled_events)} event(s) programmé(s)")
    except Exception as e:
        print(f"[Scheduler] Erreur chargement : {e}")

async def trigger_scheduled_event(guild, event_name):
    """Déclenche un event programmé dans le salon events"""
    channel = (guild.get_channel(SALON_EVENT_ID) if SALON_EVENT_ID else None) or guild.system_channel
    if not channel:
        return
    dispatch = {
        "questioneclair": run_question_eclair,
        "debatdujour":    run_debat,
        "roicolline":     run_roi_colline,
        "loterie":        run_loterie,
        "invasion":       run_invasion,
        "colis":          run_colis,
        "nuitchasse":     run_nuit_chasse,
        "doublexp":       run_double_xp,
        "nuitcasino":     run_nuit_casino,
        "marchenoir":     run_marche_noir,
        "cartemystere":   run_carte_mystere,
        "jackpot":        run_jackpot,
        "classement":     run_classement,
        "heuremaudite":   run_heure_maudite,
        "banquier":       run_banquier,
        "encheres":       run_encheres,
    }
    try:
        if event_name == "coffre":
            await run_coffre(channel)
        elif event_name in dispatch:
            await dispatch[event_name](channel, guild)
        else:
            print(f"[Scheduler] Event inconnu : {event_name}")
    except Exception as e:
        print(f"[Scheduler] Erreur déclenchement {event_name}: {e}")

@tasks.loop(minutes=1)
async def scheduler_task():
    """Vérifie chaque minute si un event programmé doit se déclencher"""
    if not planning_actif:
        return
    now = datetime.datetime.now()
    jour_actuel = now.weekday()
    for ev in scheduled_events:
        if ev["jour_num"] == jour_actuel and ev["heure"] == now.hour and ev.get("minute", 0) == now.minute:
            key = f"sched_{ev['event']}_{ev['jour_num']}_{ev['heure']}_{ev.get('minute',0)}_{now.date()}"
            if key not in planning_last_run:
                planning_last_run[key] = True
                for guild in bot.guilds:
                    await trigger_scheduled_event(guild, ev["event"])

@bot.command(name="addevent", aliases=["ajouterevent", "programmerevent"])
@commands.has_permissions(administrator=True)
async def addevent_cmd(ctx, event: str = None, jour: str = None, heure: str = None):
    """Programme un event auto — .addevent <event> <jour> <heure>
    Ex: .addevent loterie samedi 20h"""
    if not event or not jour or not heure:
        return await ctx.send(
            "❌ Usage : `.addevent <event> <jour> <heure>`\n"
            "Ex : `.addevent loterie samedi 20h`\n\n"
            "📋 Events : `questioneclair` `debatdujour` `roicolline` `loterie` `coffre` `cartemystere` `nuitcasino` `nuitchasse` `marchenoir` `doublexp` `jackpot` `colis` `invasion` `heuremaudite` `classement` `banquier` `encheres`\n"
            "📅 Jours : lundi → dimanche\n"
            "🕐 Heure : `20h`, `20h30`, `9h`..."
        )
    event = event.lower()
    if event not in EVENTS_VALIDES:
        return await ctx.send(f"❌ Event `{event}` invalide ! Tape `.addevent` pour voir la liste.")
    jour = jour.lower()
    if jour not in JOURS_MAP:
        return await ctx.send("❌ Jour invalide ! (lundi, mardi, mercredi, jeudi, vendredi, samedi, dimanche)")
    jour_num = JOURS_MAP[jour]
    # Parser l'heure (20h, 20h30, 9h)
    heure_clean = heure.lower().replace("h", ":").rstrip(":")
    try:
        if ":" in heure_clean:
            parts = heure_clean.split(":")
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 and parts[1] else 0
        else:
            h = int(heure_clean)
            m = 0
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError
    except ValueError:
        return await ctx.send("❌ Heure invalide ! Ex : `20h`, `20h30`, `9h`")
    # Vérifier doublon
    for ev in scheduled_events:
        if ev["event"] == event and ev["jour_num"] == jour_num and ev["heure"] == h and ev.get("minute", 0) == m:
            return await ctx.send("❌ Cet event est déjà programmé à cet horaire !")
    scheduled_events.append({
        "event": event, "jour": jour, "jour_num": jour_num,
        "heure": h, "minute": m
    })
    save_scheduled_events()
    await ctx.send(embed=discord.Embed(
        title="✅ Event programmé !",
        description=f"**{event}** se déclenchera chaque **{JOURS_NOMS[jour_num]} à {h}h{m:02d}**\n\n*Voir tous les events avec `.planningauto`*",
        color=0x2ecc71))

@bot.command(name="delevent", aliases=["supprimerevent", "retirerevent"])
@commands.has_permissions(administrator=True)
async def delevent_cmd(ctx, numero: int = None):
    """Supprime un event programmé — .delevent <numéro> (voir .planningauto)"""
    if numero is None:
        return await ctx.send("❌ Usage : `.delevent <numéro>`\nVoir les numéros avec `.planningauto`")
    if numero < 1 or numero > len(scheduled_events):
        return await ctx.send(f"❌ Numéro invalide ! (entre 1 et {len(scheduled_events)})")
    ev = scheduled_events.pop(numero - 1)
    save_scheduled_events()
    await ctx.send(embed=discord.Embed(
        description=f"🗑️ Event **{ev['event']}** du **{JOURS_NOMS[ev['jour_num']]} {ev['heure']}h{ev.get('minute',0):02d}** supprimé !",
        color=0xe74c3c))

@bot.command(name="planningauto", aliases=["listevents", "planningevents"])
async def planningauto_cmd(ctx):
    """Affiche le planning des events auto programmés — .planningauto"""
    if not scheduled_events:
        return await ctx.send(embed=discord.Embed(
            title="📅 Planning des Events Auto",
            description="*Aucun event programmé pour l'instant.*\n\nUn admin peut en ajouter avec `.addevent <event> <jour> <heure>`",
            color=0x3498db))
    # Trier par jour puis heure
    sorted_events = sorted(scheduled_events, key=lambda e: (e["jour_num"], e["heure"], e.get("minute", 0)))
    # Grouper par jour
    embed = discord.Embed(
        title="📅 Planning des Events Auto — QG Kdrama",
        description="Events programmés de la semaine :",
        color=0x3498db)
    par_jour = {}
    for i, ev in enumerate(sorted_events):
        # Retrouver le numéro original
        num = scheduled_events.index(ev) + 1
        jour_nom = JOURS_NOMS[ev["jour_num"]]
        par_jour.setdefault(jour_nom, []).append(
            f"`#{num}` **{ev['heure']}h{ev.get('minute',0):02d}** — {ev['event']}"
        )
    for jour in JOURS_NOMS:
        if jour in par_jour:
            embed.add_field(name=f"📆 {jour}", value="\n".join(par_jour[jour]), inline=False)
    statut = "✅ Actifs" if planning_actif else "🛑 En pause (.eventon pour activer)"
    embed.set_footer(text=f"Events auto : {statut} • .delevent <#> pour supprimer")
    await ctx.send(embed=embed)

@tasks.loop(minutes=1)
async def check_anniversaires():
    today = datetime.datetime.now().strftime("%d/%m")
    for guild in bot.guilds:
        channel = discord.utils.get(guild.text_channels, name="général") or guild.system_channel
        if not channel: continue
        for user_id, date in anniversaire_data.items():
            if date == today:
                m = guild.get_member(int(user_id))
                if m:
                    await channel.send(embed=discord.Embed(
                        title="🎂 Joyeux Anniversaire !",
                        description=f"Toute la communauté souhaite un joyeux anniversaire à **{m.mention}** ! 🎉🥳",
                        color=0xff6b9d
                    ))

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
            track_stat(str(winner["membre"].id), "arene_wins", channel=ctx.channel)
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

@bot.command(name="attaque", aliases=["attaquerboss", "boss_attack"])
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

        salon_temp = game.get("salon_temp")
        del active_boss[gid]
        if salon_temp:
            ch = ctx.guild.get_channel(salon_temp)
            if ch:
                asyncio.create_task(close_event_channel(ch, 180))

    else:
        # ── Mise à jour de l'embed boss ──────────────────────
        derniere = f"**{ctx.author.display_name}** inflige **{degats:,} dégâts** !"
        try:
            await game["msg"].edit(embed=build_boss_embed(gid, derniere))
        except:
            game["msg"] = await ctx.send(embed=build_boss_embed(gid, derniere))

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

# ============================================================
#  📖 GUIDE DU SERVEUR — Explications pour les nouveaux
#  Posté en embeds fixes (lisibles par tous, en permanence)
# ============================================================
def build_guide_embeds(guild):
    """Construit les pages du guide du serveur — pensé pour les novices de Discord"""
    pages = []

    # ── 1. Bienvenue & comment parler au bot ──
    e = discord.Embed(
        title="👋 Bienvenue au QG Kdrama !",
        description=(
            "Ici on parle **kdramas** et **animés** : on partage ses coups de cœur, "
            "on se recommande des séries, et on discute de ce qu'on regarde.\n\n"
            "**Akari**, c'est le robot du serveur. Il peut te recommander un drama, "
            "retenir ta liste « à regarder », lancer des jeux… mais il ne devine rien : "
            "il faut lui demander."
        ),
        color=0xff6b9d)
    e.add_field(
        name="✏️ Comment on lui parle ?",
        value=(
            "Tu écris un message qui **commence par un point**, et tu envoies. C'est tout.\n\n"
            "Essaie tout de suite : écris `.dramarec` dans un salon → Akari te propose un drama.\n\n"
            "⚠️ Le point compte : `.dramarec` fonctionne, `dramarec` tout seul ne fait rien."
        ), inline=False)
    e.add_field(
        name="🧘 Tu n'es obligé à rien",
        value=(
            "Tu peux très bien rester juste pour discuter kdrama et ignorer tout le reste. "
            "Les jeux du serveur sont là pour ceux que ça amuse, pas comme un devoir."
        ), inline=False)
    e.set_footer(text="Page 1/5 • Guide du QG Kdrama")
    if guild and guild.icon:
        e.set_thumbnail(url=guild.icon.url)
    pages.append(e)

    # ── 2. Kdrama & Anime ──
    e = discord.Embed(
        title="🎬 Kdrama & Anime — le cœur du serveur",
        description="À quoi ça sert : **savoir quoi regarder ce soir**, et faire découvrir tes coups de cœur aux autres.",
        color=0xff6b9d)
    e.add_field(
        name="🍿 Je ne sais pas quoi regarder",
        value=(
            "`.dramarec` — un drama au hasard, proposé par Akari\n"
            "`.animerec` — pareil pour les animés\n"
            "`.sorties` — les prochaines sorties à ne pas manquer"
        ), inline=False)
    e.add_field(
        name="🔎 Je veux des infos sur un titre",
        value=(
            "`.drama Goblin` — la fiche du drama (genre, note)\n"
            "`.anime One Piece` — la fiche de l'animé\n"
            "`.avis Goblin` — ce que **les membres du serveur** en ont pensé"
        ), inline=False)
    e.add_field(
        name="⭐ Je donne mon avis",
        value=(
            "`.noter 9 Goblin` — ta note sur 10\n"
            "*C'est ce qui construit les notes du serveur : plus on note, plus les avis sont utiles.*"
        ), inline=False)
    e.add_field(
        name="📝 Ma liste « à regarder »",
        value=(
            "`.watch ajouter Vincenzo` — ajoute un titre à ta liste\n"
            "`.watch liste` — revoir ta liste quand tu cherches quoi lancer"
        ), inline=False)
    e.add_field(
        name="🧠 Tester mes connaissances",
        value="`.quiz kdrama` — un quiz sur les kdramas (bonnes réponses = pièces)\n`.quizduel kdrama @ami` — en duel contre quelqu'un",
        inline=False)
    e.set_footer(text="Page 2/5 • Guide du QG Kdrama")
    pages.append(e)

    # ── 3. Progression ──
    e = discord.Embed(
        title="💬 Ta progression — ça marche tout seul",
        description=(
            "Rien à faire de spécial : **chaque message que tu écris te fait progresser**. "
            "Tu gagnes de l'expérience, tu montes de niveau, et tu débloques des choses en cours de route."
        ),
        color=0x9b59b6)
    e.add_field(
        name="🪪 Voir où j'en suis",
        value=(
            "`.profil` — ta carte de membre **en image** (niveau, pièces, succès, compagnon)\n"
            "`.rank` — la version rapide en texte\n"
            "`.leaderboard` — le classement des niveaux du serveur"
        ), inline=False)
    e.add_field(
        name="🏆 Les succès",
        value=(
            "`.succes` — **30 défis** à débloquer : discuter, noter des dramas, gagner des quiz, "
            "collectionner… Chacun te rapporte des pièces automatiquement."
        ), inline=False)
    e.add_field(
        name="💰 Gagner des pièces",
        value=(
            "`.daily` — ta récompense du jour, **une fois par 24 h** (le réflexe à prendre)\n"
            "`.travailler` — un petit boulot pour quelques pièces\n"
            "`.balance` — combien tu as\n"
            "`.shop` — ce que tu peux acheter avec"
        ), inline=False)
    e.add_field(
        name="🐾 Un compagnon",
        value=(
            "`.adopter commun` — adopte un animal de compagnie (1 000 pièces)\n"
            "Il te donne un **bonus permanent** (plus de pièces, ou plus d'expérience) et "
            "monte de niveau quand tu discutes. `.pet` pour le voir."
        ), inline=False)
    e.set_footer(text="Page 3/5 • Guide du QG Kdrama")
    pages.append(e)

    # ── 4. Le Gacha expliqué ──
    e = discord.Embed(
        title="🎰 Le Gacha, c'est quoi ?",
        description=(
            "**En une phrase :** c'est un jeu de **collection de cartes**. Akari possède près de "
            "**500 cartes** de personnages d'animés, et tu essaies de constituer ta collection.\n\n"
            "Le principe : tu tires une carte au hasard, et si elle te plaît, tu la gardes. "
            "Petite subtilité qui rend ça intéressant — **une carte n'appartient qu'à une seule personne "
            "sur tout le serveur**. Si quelqu'un a déjà pris Luffy, il est à lui."
        ),
        color=0xf1c40f)
    e.add_field(
        name="▶️ Pour essayer, dans l'ordre",
        value=(
            "**1.** `.ga` — tire une carte au hasard\n"
            "**2.** Elle te plaît ? Clique sur le **cœur ❤️** sous la carte — elle est à toi\n"
            "**3.** `.rolls` — voir combien de tirages il te reste *(c'est limité, ça se recharge)*"
        ), inline=False)
    e.add_field(
        name="🔧 Ensuite, si ça t'accroche",
        value=(
            "`.serie Naruto` — ta progression sur une série + récompense si tu la complètes\n"
            "`.burn <perso>` — détruire une carte qui ne t'intéresse pas contre des pièces\n"
            "`.gachatrade @membre <ta carte> <sa carte>` — échanger avec quelqu'un\n"
            "`.cardinfo <perso>` — les stats détaillées d'une de tes cartes"
        ), inline=False)
    e.add_field(
        name="🚫 Et si ça ne me tente pas du tout ?",
        value=(
            "**Aucun problème, et c'est important :** tu peux ignorer complètement le gacha. "
            "Tu ne rates rien du serveur, tu ne bloques personne, tu progresses quand même en discutant, "
            "et tout le reste fonctionne pareil.\n"
            "*Le gacha se joue dans son salon dédié — si le sujet ne t'intéresse pas, ne va pas dedans.*"
        ), inline=False)
    e.set_footer(text="Page 4/5 • Guide du QG Kdrama")
    pages.append(e)

    # ── 5. Jeux, events & FAQ ──
    e = discord.Embed(
        title="🎪 Jeux, events & questions fréquentes",
        color=0x3498db)
    e.add_field(
        name="🎮 Jouer à plusieurs",
        value=(
            "`.lg` — le **Loup Garou** sur Discord, avec les vrais rôles (le gros jeu du serveur)\n"
            "`.pendu` — le pendu avec des titres de dramas et d'animés\n"
            "`.devine` — devine le personnage\n"
            "`.arene @membre` — un duel rapide contre quelqu'un\n"
            "`.loto` — un ticket de loterie (100 pièces)"
        ), inline=False)
    e.add_field(
        name="🎉 Les events automatiques",
        value=(
            "De temps en temps, Akari lance un event tout seul : question éclair, débat, "
            "loterie, coffre à ouvrir… Le premier à répondre gagne.\n"
            "*Rien à installer : il suffit d'être là et de réagir vite.*"
        ), inline=False)
    e.add_field(
        name="❓ C'est quoi les pièces ?",
        value=(
            "La monnaie du serveur. Tu en gagnes en discutant, avec `.daily`, les quiz, les succès et les events. "
            "Tu les dépenses dans `.shop`, le gacha, ou pour un compagnon. **Ça ne coûte pas d'argent réel.**"
        ), inline=False)
    e.add_field(
        name="❓ Pourquoi je suis notifié ?",
        value=(
            "Akari ne prévient que les personnes concernées : un event gacha ne notifie que ceux qui ont "
            "le rôle Gacha, un event animé que le rôle Anime. Si tu reçois trop (ou pas assez) de notifications, "
            "demande à un admin de changer tes rôles."
        ), inline=False)
    e.add_field(
        name="❓ J'ai tapé une commande et rien ne se passe",
        value=(
            "Trois choses à vérifier :\n"
            "• le **point** au début (`.profil`, pas `profil`)\n"
            "• l'**orthographe** exacte\n"
            "• le **salon** : certaines commandes ne marchent que dans leur salon dédié (le gacha, par exemple)"
        ), inline=False)
    e.add_field(
        name="📚 Voir absolument tout",
        value="`.help` — la liste complète des commandes, page par page. À garder pour plus tard : commence par ce guide.",
        inline=False)
    e.set_footer(text="Page 5/5 • Guide du QG Kdrama 🌸")
    pages.append(e)

    return pages


# ============================================================
#  🖼️ CARTE DE PROFIL — Image générée (style néon futuriste)
# ============================================================
def _pf_font(size, bold=True):
    """Charge une police avec fallback"""
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()

async def generate_profile_card(member):
    """Génère la carte de profil en image. Retourne un BytesIO PNG."""
    uid = str(member.id)
    W, H = 900, 380
    img = Image.new("RGB", (W, H), (12, 10, 28))
    draw = ImageDraw.Draw(img)

    # ── Fond dégradé violet → rose (style néon kdrama) ──
    for y in range(H):
        t = y / H
        r = int(18 + t * 40)
        g = int(10 + t * 8)
        b = int(38 + t * 42)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Déco : cercles néon flous
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([W-260, -120, W+80, 220], fill=(120, 40, 160))
    gd.ellipse([-140, H-160, 180, H+140], fill=(40, 60, 180))
    glow = glow.filter(ImageFilter.GaussianBlur(80))
    img = Image.blend(img, glow, 0.45)
    draw = ImageDraw.Draw(img)

    # ── Avatar circulaire avec anneau néon ──
    try:
        avatar_bytes = await member.display_avatar.replace(size=256, static_format="png").read()
        av = Image.open(io.BytesIO(avatar_bytes)).convert("RGB").resize((170, 170))
        mask = Image.new("L", (170, 170), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, 170, 170], fill=255)
        # Anneau
        draw.ellipse([32, 32, 214, 214], outline=(255, 80, 200), width=5)
        draw.ellipse([36, 36, 210, 210], outline=(120, 200, 255), width=2)
        img.paste(av, (40, 40), mask)
    except Exception:
        draw.ellipse([40, 40, 210, 210], fill=(60, 40, 100), outline=(255, 80, 200), width=5)

    # ── Infos texte ──
    f_big   = _pf_font(42)
    f_med   = _pf_font(26)
    f_small = _pf_font(20)
    f_tiny  = _pf_font(16, bold=False)

    pseudo = member.display_name[:20]
    draw.text((250, 42), pseudo, font=f_big, fill=(255, 255, 255))

    lvl = xp_data[uid]["level"]
    xp  = xp_data[uid]["xp"]
    needed = lvl * 100
    coins = economy_data[uid]["coins"]
    nb_cartes = len(gacha_collections.get(uid, {}))
    nb_succes = len(achievements_data.get(uid, set()))
    nb_badges = len(serie_badges.get(uid, set()))

    # Ligne stats
    draw.text((252, 100), f"Niveau {lvl}", font=f_med, fill=(255, 200, 80))
    draw.text((420, 100), f"💰 {coins:,}", font=f_med, fill=(150, 255, 170))

    # ── Barre d'XP néon ──
    bx, by, bw, bh = 250, 145, 610, 26
    draw.rounded_rectangle([bx, by, bx+bw, by+bh], radius=13, fill=(30, 22, 55))
    ratio = min(1.0, xp / max(1, needed))
    if ratio > 0.02:
        draw.rounded_rectangle([bx, by, bx+int(bw*ratio), by+bh], radius=13, fill=(255, 80, 200))
    draw.text((bx+8, by+3), f"{xp}/{needed} XP", font=f_tiny, fill=(255, 255, 255))

    # ── Ligne badges/statistiques ──
    yb = 200
    stats_line = [
        ("🏆", f"{nb_succes}/{len(ACHIEVEMENTS)} succès"),
        ("🎴", f"{nb_cartes} cartes"),
        ("🏅", f"{nb_badges} badges série"),
    ]
    x = 252
    for emoji_txt, txt in stats_line:
        draw.text((x, yb), txt, font=f_small, fill=(220, 220, 255))
        x += len(txt) * 12 + 60

    # ── Compagnon actif ──
    pid, pdb, pstate = get_active_pet(uid)
    if pid:
        pet_txt = f"Compagnon : {pdb['nom']}  (Niv.{pstate['level']} • +{pdb['base'] + pstate['level'] - 1}% {pdb['type']})"
    else:
        pet_txt = "Aucun compagnon — .adopter pour en obtenir un !"
    draw.rounded_rectangle([250, 245, 860, 292], radius=12, outline=(120, 200, 255), width=2)
    draw.text((266, 256), pet_txt[:60], font=f_small, fill=(180, 230, 255))

    # ── Footer : drama points ou titre serveur ──
    draw.text((250, 315), "QG KDRAMA", font=f_med, fill=(255, 80, 200))
    draw.text((440, 322), "• Profil de membre •", font=f_tiny, fill=(160, 150, 200))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

@bot.command(name="profil", aliases=["profile", "carte_profil"])
async def profil_cmd(ctx, membre: discord.Member = None):
    """Ta carte de profil visuelle — .profil [@membre]"""
    target = membre or ctx.author
    uid = str(target.id)
    if PIL_OK:
        async with ctx.typing():
            try:
                buf = await generate_profile_card(target)
                return await ctx.send(file=discord.File(buf, filename=f"profil_{target.name}.png"))
            except Exception as e:
                print(f"[Profil] Erreur génération image : {e}")
    # Fallback embed si Pillow absent ou erreur
    lvl = xp_data[uid]["level"]
    coins = economy_data[uid]["coins"]
    nb_cartes = len(gacha_collections.get(uid, {}))
    nb_succes = len(achievements_data.get(uid, set()))
    pid, pdb, pstate = get_active_pet(uid)
    pet_txt = f"{pdb['emoji']} {pdb['nom']} Niv.{pstate['level']}" if pid else "Aucun"
    embed = discord.Embed(title=f"🪪 Profil de {target.display_name}", color=0xe91e63)
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="⭐ Niveau", value=str(lvl), inline=True)
    embed.add_field(name="💰 Pièces", value=f"{coins:,}", inline=True)
    embed.add_field(name="🎴 Cartes", value=str(nb_cartes), inline=True)
    embed.add_field(name="🏆 Succès", value=f"{nb_succes}/{len(ACHIEVEMENTS)}", inline=True)
    embed.add_field(name="🐾 Compagnon", value=pet_txt, inline=True)
    await ctx.send(embed=embed)

# ============================================================
#  🖼️ CARTES BIENVENUE / AUREVOIR — Images générées
# ============================================================
async def _card_avatar(member, size=200, grayscale=False):
    """Récupère l'avatar en cercle avec masque. Retourne (image, masque) ou (None, None)"""
    try:
        raw = await member.display_avatar.replace(size=256, static_format="png").read()
        av = Image.open(io.BytesIO(raw)).convert("RGB").resize((size, size))
        if grayscale:
            av = av.convert("L").convert("RGB")
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, size, size], fill=255)
        return av, mask
    except Exception:
        return None, None

async def generate_welcome_card(member):
    """Carte de bienvenue — format compact, texte lisible sans zoomer."""
    W, H = 760, 250
    img = Image.new("RGB", (W, H), (16, 8, 30))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        draw.line([(0, y), (W, y)], fill=(int(26 + t*72), int(9 + t*15), int(52 + t*58)))
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([-130, -150, 250, 230], fill=(235, 60, 155))
    gd.ellipse([W-250, H-140, W+140, H+170], fill=(95, 50, 225))
    glow = glow.filter(ImageFilter.GaussianBlur(80))
    img = Image.blend(img, glow, 0.5)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([10, 10, W-10, H-10], radius=18, outline=(255, 150, 210), width=2)

    # Avatar bien visible à gauche
    AV, ax, ay = 176, 28, 37
    av, mask = await _card_avatar(member, AV)
    draw.ellipse([ax-9, ay-9, ax+AV+9, ay+AV+9], outline=(255, 90, 190), width=6)
    draw.ellipse([ax-3, ay-3, ax+AV+3, ay+AV+3], outline=(150, 220, 255), width=2)
    if av:
        img.paste(av, (ax, ay), mask)
    else:
        draw.ellipse([ax, ay, ax+AV, ay+AV], fill=(70, 40, 110))

    X = ax + AV + 34
    f_hero = _pf_font(72)
    f_name = _pf_font(46)
    f_badge = _pf_font(28)
    f_tag  = _pf_font(19)

    draw.text((X+4, 32), "BIENVENUE", font=f_hero, fill=(150, 40, 110))
    draw.text((X, 28),   "BIENVENUE", font=f_hero, fill=(255, 255, 255))

    pseudo = member.display_name
    if len(pseudo) > 15:
        pseudo = pseudo[:14] + "…"
    draw.text((X, 112), pseudo, font=f_name, fill=(255, 210, 240))

    n = member.guild.member_count
    txt = f"MEMBRE N°{n:03d}"
    bw = int(draw.textlength(txt, font=f_badge)) + 40
    draw.rounded_rectangle([X, 172, X+bw, 222], radius=14, fill=(255, 75, 180))
    draw.text((X+20, 181), txt, font=f_badge, fill=(255, 255, 255))

    draw.text((W-138, H-34), "QG KDRAMA", font=f_tag, fill=(255, 130, 205))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


async def generate_goodbye_card(member):
    """Carte d'aurevoir — même format compact, palette froide."""
    W, H = 760, 250
    img = Image.new("RGB", (W, H), (10, 12, 22))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        draw.line([(0, y), (W, y)], fill=(int(15 + t*36), int(19 + t*42), int(34 + t*56)))
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([W-290, -130, W+130, 240], fill=(42, 84, 155))
    gd.ellipse([-160, H-140, 190, H+160], fill=(62, 62, 95))
    glow = glow.filter(ImageFilter.GaussianBlur(85))
    img = Image.blend(img, glow, 0.44)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([10, 10, W-10, H-10], radius=18, outline=(120, 142, 178), width=2)

    AV, ax, ay = 176, 28, 37
    av, mask = await _card_avatar(member, AV, grayscale=True)
    draw.ellipse([ax-8, ay-8, ax+AV+8, ay+AV+8], outline=(140, 162, 202), width=5)
    if av:
        img.paste(av, (ax, ay), mask)
    else:
        draw.ellipse([ax, ay, ax+AV, ay+AV], fill=(45, 50, 65))

    X = ax + AV + 34
    f_hero = _pf_font(68)
    f_name = _pf_font(45)
    f_badge = _pf_font(25)
    f_tag  = _pf_font(19)

    draw.text((X, 30), "AU REVOIR", font=f_hero, fill=(228, 235, 248))

    pseudo = member.display_name
    if len(pseudo) > 15:
        pseudo = pseudo[:14] + "…"
    draw.text((X, 112), pseudo, font=f_name, fill=(158, 175, 208))

    n = member.guild.member_count
    txt = f"IL RESTE {n} MEMBRES"
    bw = int(draw.textlength(txt, font=f_badge)) + 40
    draw.rounded_rectangle([X, 172, X+bw, 220], radius=14, outline=(120, 145, 185), width=2)
    draw.text((X+20, 181), txt, font=f_badge, fill=(180, 200, 232))

    draw.text((W-138, H-34), "QG KDRAMA", font=f_tag, fill=(120, 150, 195))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


# ============================================================
#  🏆 SUCCÈS / ACHIEVEMENTS — 30 succès pour tout le serveur
# ============================================================
user_stats = defaultdict(lambda: defaultdict(int))   # {uid: {stat: count}}
achievements_data = defaultdict(set)                  # {uid: {achievement_ids}}

# Succès à seuil : condition sur une stat trackée
# Succès événementiels : débloqués directement par unlock_achievement()
ACHIEVEMENTS = {
    # 💬 CHAT & COMMUNAUTÉ
    "bavard_1":     {"nom": "Premier Pas",        "emoji": "💬", "desc": "Envoyer 10 messages",            "stat": "messages",    "seuil": 10,    "reward": 100,  "cat": "💬 Communauté"},
    "bavard_2":     {"nom": "Pipelette",          "emoji": "🗣️", "desc": "Envoyer 500 messages",           "stat": "messages",    "seuil": 500,   "reward": 500,  "cat": "💬 Communauté"},
    "bavard_3":     {"nom": "Légende du Chat",    "emoji": "📢", "desc": "Envoyer 5000 messages",          "stat": "messages",    "seuil": 5000,  "reward": 2000, "cat": "💬 Communauté"},
    "niveau_5":     {"nom": "Novice",             "emoji": "⭐", "desc": "Atteindre le niveau 5",          "stat": "level",       "seuil": 5,     "reward": 200,  "cat": "💬 Communauté"},
    "niveau_20":    {"nom": "Confirmé",           "emoji": "🌟", "desc": "Atteindre le niveau 20",         "stat": "level",       "seuil": 20,    "reward": 1000, "cat": "💬 Communauté"},
    "niveau_50":    {"nom": "Vétéran du QG",      "emoji": "💫", "desc": "Atteindre le niveau 50",         "stat": "level",       "seuil": 50,    "reward": 5000, "cat": "💬 Communauté"},
    # 🎬 KDRAMA & ANIME
    "drama_1":      {"nom": "Critique Débutant",  "emoji": "🎬", "desc": "Noter 1 drama/animé",            "stat": "notes",       "seuil": 1,     "reward": 100,  "cat": "🎬 Kdrama & Anime"},
    "drama_10":     {"nom": "Cinéphile",          "emoji": "🍿", "desc": "Noter 10 dramas/animés",         "stat": "notes",       "seuil": 10,    "reward": 800,  "cat": "🎬 Kdrama & Anime"},
    "quiz_10":      {"nom": "Cerveau",            "emoji": "🧠", "desc": "10 bonnes réponses au quiz",     "stat": "quiz_ok",     "seuil": 10,    "reward": 500,  "cat": "🎬 Kdrama & Anime"},
    "quiz_100":     {"nom": "Encyclopédie",       "emoji": "🎓", "desc": "100 bonnes réponses au quiz",    "stat": "quiz_ok",     "seuil": 100,   "reward": 3000, "cat": "🎬 Kdrama & Anime"},
    "eclair_win":   {"nom": "Réflexes d'Acier",   "emoji": "⚡", "desc": "Gagner une Question Éclair",     "stat": None,          "seuil": None,  "reward": 300,  "cat": "🎬 Kdrama & Anime"},
    # 🎰 GACHA
    "roll_1":       {"nom": "Premier Tirage",     "emoji": "🎰", "desc": "Faire son premier roll",         "stat": "rolls",       "seuil": 1,     "reward": 50,   "cat": "🎰 Gacha"},
    "roll_100":     {"nom": "Accro du Gacha",     "emoji": "🎲", "desc": "Faire 100 rolls",                "stat": "rolls",       "seuil": 100,   "reward": 1000, "cat": "🎰 Gacha"},
    "roll_1000":    {"nom": "Machine à Roll",     "emoji": "🌀", "desc": "Faire 1000 rolls",               "stat": "rolls",       "seuil": 1000,  "reward": 5000, "cat": "🎰 Gacha"},
    "mythique_1":   {"nom": "Toucher les Étoiles","emoji": "🔴", "desc": "Claim une carte Mythique",       "stat": None,          "seuil": None,  "reward": 1000, "cat": "🎰 Gacha"},
    "collec_25":    {"nom": "Collectionneur",     "emoji": "📦", "desc": "Posséder 25 cartes",             "stat": None,          "seuil": None,  "reward": 500,  "cat": "🎰 Gacha"},
    "collec_100":   {"nom": "Musée Vivant",       "emoji": "🏛️", "desc": "Posséder 100 cartes",            "stat": None,          "seuil": None,  "reward": 3000, "cat": "🎰 Gacha"},
    "serie_1":      {"nom": "Perfectionniste",    "emoji": "🏅", "desc": "Compléter une série entière",    "stat": None,          "seuil": None,  "reward": 1000, "cat": "🎰 Gacha"},
    "fusion_max":   {"nom": "Étoile Suprême",     "emoji": "✨", "desc": "Fusionner une carte au max (3⭐)","stat": None,          "seuil": None,  "reward": 1500, "cat": "🎰 Gacha"},
    "burn_10":      {"nom": "Pyromane",           "emoji": "🔥", "desc": "Recycler 10 cartes",             "stat": "burns",       "seuil": 10,    "reward": 500,  "cat": "🎰 Gacha"},
    # ⚔️ COMBAT
    "arene_1":      {"nom": "Premier Sang",       "emoji": "⚔️", "desc": "Gagner un duel d'arène",         "stat": "arene_wins",  "seuil": 1,     "reward": 200,  "cat": "⚔️ Combat"},
    "arene_25":     {"nom": "Gladiateur",         "emoji": "🗡️", "desc": "Gagner 25 duels d'arène",        "stat": "arene_wins",  "seuil": 25,    "reward": 1500, "cat": "⚔️ Combat"},
    "pb_10":        {"nom": "Maître Dresseur",    "emoji": "🎴", "desc": "Gagner 10 pokebattles",          "stat": "pb_wins",     "seuil": 10,    "reward": 1000, "cat": "⚔️ Combat"},
    "boss_kill":    {"nom": "Tueur de Boss",      "emoji": "👹", "desc": "Porter le coup final à un boss", "stat": None,          "seuil": None,  "reward": 1000, "cat": "⚔️ Combat"},
    # 💰 ÉCONOMIE
    "riche_10k":    {"nom": "Petit Épargnant",    "emoji": "💰", "desc": "Posséder 10 000 pièces",         "stat": None,          "seuil": None,  "reward": 500,  "cat": "💰 Économie"},
    "riche_100k":   {"nom": "Millionnaire du QG", "emoji": "💎", "desc": "Posséder 100 000 pièces",        "stat": None,          "seuil": None,  "reward": 3000, "cat": "💰 Économie"},
    "daily_7":      {"nom": "Fidèle au Poste",    "emoji": "📅", "desc": "Récupérer 7 daily",              "stat": "dailies",     "seuil": 7,     "reward": 500,  "cat": "💰 Économie"},
    "braquage_1":   {"nom": "Bandit du QG",       "emoji": "🦹", "desc": "Réussir un braquage",            "stat": "braquages",   "seuil": 1,     "reward": 300,  "cat": "💰 Économie"},
    # 💖 SOCIAL & EVENTS
    "mariage":      {"nom": "Cœur Pris",          "emoji": "💍", "desc": "Se marier",                      "stat": None,          "seuil": None,  "reward": 500,  "cat": "💖 Social"},
    "loterie_win":  {"nom": "Chanceux",           "emoji": "🍀", "desc": "Gagner une loterie",             "stat": None,          "seuil": None,  "reward": 1000, "cat": "💖 Social"},
    "pet_1":        {"nom": "Ami des Bêtes",      "emoji": "🐾", "desc": "Adopter un compagnon",           "stat": None,          "seuil": None,  "reward": 200,  "cat": "💖 Social"},
}

def unlock_achievement(uid, ach_id, channel=None):
    """Débloque un succès (si pas déjà fait) + annonce + récompense"""
    if ach_id not in ACHIEVEMENTS or ach_id in achievements_data[uid]:
        return False
    achievements_data[uid].add(ach_id)
    a = ACHIEVEMENTS[ach_id]
    economy_data[uid]["coins"] += a["reward"]
    if channel:
        try:
            asyncio.create_task(channel.send(embed=discord.Embed(
                description=f"🏆 **SUCCÈS DÉBLOQUÉ !** {a['emoji']} **{a['nom']}**\n*{a['desc']}* — <@{uid}> gagne **+{a['reward']} pièces** !",
                color=0xf1c40f)))
        except Exception:
            pass
    return True

def track_stat(uid, stat, amount=1, channel=None):
    """Incrémente une stat + vérifie les succès à seuil liés"""
    user_stats[uid][stat] += amount
    val = user_stats[uid][stat]
    for ach_id, a in ACHIEVEMENTS.items():
        if a["stat"] == stat and a["seuil"] and val >= a["seuil"] and ach_id not in achievements_data[uid]:
            unlock_achievement(uid, ach_id, channel)

def check_coins_achievements(uid, channel=None):
    """Vérifie les succès de richesse"""
    coins = economy_data[uid]["coins"]
    if coins >= 10000:
        unlock_achievement(uid, "riche_10k", channel)
    if coins >= 100000:
        unlock_achievement(uid, "riche_100k", channel)

def check_collection_achievements(uid, channel=None):
    """Vérifie les succès de taille de collection"""
    n = len(gacha_collections.get(uid, {}))
    if n >= 25:
        unlock_achievement(uid, "collec_25", channel)
    if n >= 100:
        unlock_achievement(uid, "collec_100", channel)

@bot.command(name="succes", aliases=["achievements", "succès", "trophees"])
async def succes_cmd(ctx, membre: discord.Member = None):
    """Voir tes succès débloqués — .succes [@membre]"""
    target = membre or ctx.author
    uid = str(target.id)
    unlocked = achievements_data[uid]
    # Grouper par catégorie
    cats = {}
    for ach_id, a in ACHIEVEMENTS.items():
        cats.setdefault(a["cat"], []).append((ach_id, a))
    pages = []
    total = len(ACHIEVEMENTS)
    nb_ok = len(unlocked)
    for cat, achs in cats.items():
        embed = discord.Embed(
            title=f"🏆 Succès de {target.display_name} — {nb_ok}/{total}",
            description=f"## {cat}",
            color=0xf1c40f)
        lignes = []
        for ach_id, a in achs:
            if ach_id in unlocked:
                lignes.append(f"{a['emoji']} **{a['nom']}** ✅\n*{a['desc']}* — {a['reward']}p")
            else:
                lignes.append(f"⬜ **{a['nom']}**\n*{a['desc']}* — {a['reward']}p")
        embed.add_field(name="\u200b", value="\n\n".join(lignes), inline=False)
        pages.append(embed)
    view = PageView(pages, ctx.author, timeout=120)
    await ctx.send(embed=pages[0], view=view)

# ============================================================
#  🐾 COMPAGNONS (PETS) — Bonus passifs pour tous
# ============================================================
PETS_DB = {
    # Communs (œuf 1000p)
    "nyang":    {"nom": "Nyang le Chat Noir",   "emoji": "🐱", "rarete": "Commun",     "type": "coins", "base": 5,  "desc": "+% pièces sur daily/travail"},
    "mochi":    {"nom": "Mochi le Hamster",     "emoji": "🐹", "rarete": "Commun",     "type": "xp",    "base": 5,  "desc": "+% XP sur les messages"},
    "kkobuk":   {"nom": "Kkobuk la Tortue",     "emoji": "🐢", "rarete": "Commun",     "type": "roll",  "base": 3,  "desc": "% chance de roll gratuit"},
    # Rares (œuf 3000p)
    "kitsu":    {"nom": "Kitsu le Renard",      "emoji": "🦊", "rarete": "Rare",       "type": "coins", "base": 10, "desc": "+% pièces sur daily/travail"},
    "bao":      {"nom": "Bao le Panda",         "emoji": "🐼", "rarete": "Rare",       "type": "xp",    "base": 10, "desc": "+% XP sur les messages"},
    "hibou":    {"nom": "Hibou Sage",           "emoji": "🦉", "rarete": "Rare",       "type": "roll",  "base": 5,  "desc": "% chance de roll gratuit"},
    # Épiques (œuf 8000p)
    "loup":     {"nom": "Loup de Lune",         "emoji": "🐺", "rarete": "Épique",     "type": "coins", "base": 15, "desc": "+% pièces sur daily/travail"},
    "ryu":      {"nom": "Ryu le Mini-Dragon",   "emoji": "🐉", "rarete": "Épique",     "type": "xp",    "base": 15, "desc": "+% XP sur les messages"},
    "corbeau":  {"nom": "Corbeau du Destin",    "emoji": "🐦‍⬛", "rarete": "Épique",   "type": "roll",  "base": 8,  "desc": "% chance de roll gratuit"},
    # Légendaires (œuf 20000p)
    "licorne":  {"nom": "Licorne Céleste",      "emoji": "🦄", "rarete": "Légendaire", "type": "coins", "base": 25, "desc": "+% pièces sur daily/travail"},
    "phenix":   {"nom": "Phénix Immortel",      "emoji": "🔥", "rarete": "Légendaire", "type": "xp",    "base": 25, "desc": "+% XP sur les messages"},
    "gumiho":   {"nom": "Gumiho aux Neuf Queues","emoji": "🌙", "rarete": "Légendaire", "type": "roll", "base": 12, "desc": "% chance de roll gratuit"},
    # ── Nouveaux : animaux réels ──
    "shiba":    {"nom": "Shiba Inu",             "emoji": "🐕", "rarete": "Commun",     "type": "coins", "base": 5,  "desc": "+% pièces sur daily/travail"},
    "herisson": {"nom": "Hérisson Grognon",      "emoji": "🦔", "rarete": "Commun",     "type": "xp",    "base": 5,  "desc": "+% XP sur les messages"},
    "mochivi":  {"nom": "Mochi Vivant",          "emoji": "🍡", "rarete": "Commun",     "type": "roll",  "base": 3,  "desc": "% chance de roll gratuit"},
    "manchot":  {"nom": "Manchot Empereur",      "emoji": "🐧", "rarete": "Rare",       "type": "coins", "base": 10, "desc": "+% pièces sur daily/travail"},
    "loutre":   {"nom": "Loutre Farceuse",       "emoji": "🦦", "rarete": "Rare",       "type": "xp",    "base": 10, "desc": "+% XP sur les messages"},
    "panthere": {"nom": "Panthère des Neiges",   "emoji": "🐆", "rarete": "Épique",     "type": "coins", "base": 15, "desc": "+% pièces sur daily/travail"},
    # ── Nouveaux : créatures d'anime & mythologie ──
    "kodama":   {"nom": "Esprit de la Forêt",    "emoji": "🌸", "rarete": "Rare",       "type": "roll",  "base": 5,  "desc": "% chance de roll gratuit"},
    "nuage":    {"nom": "Nuage Doré",            "emoji": "☁️", "rarete": "Épique",     "type": "xp",    "base": 15, "desc": "+% XP sur les messages"},
    "komainu":  {"nom": "Lion Gardien",          "emoji": "🦁", "rarete": "Épique",     "type": "roll",  "base": 8,  "desc": "% chance de roll gratuit"},
    "haku":     {"nom": "Dragon de Rivière",     "emoji": "🐲", "rarete": "Légendaire", "type": "coins", "base": 25, "desc": "+% pièces sur daily/travail"},
    "cerf":     {"nom": "Cerf Sacré",            "emoji": "🦌", "rarete": "Légendaire", "type": "xp",    "base": 25, "desc": "+% XP sur les messages"},
    "fenrir":   {"nom": "Fenrir",                "emoji": "🐺", "rarete": "Légendaire", "type": "roll",  "base": 12, "desc": "% chance de roll gratuit"},
}
PETS_PRIX = {"Commun": 2000, "Rare": 6000, "Épique": 14000, "Légendaire": 35000}
PET_XP_PER_LEVEL = 100
PET_LEVEL_MAX = 10
pets_data = {}  # {uid: {"owned": {pet_id: {"level": 1, "xp": 0}}, "active": pet_id}}

def get_active_pet(uid):
    """Retourne (pet_id, pet_db, pet_state) du pet actif, ou (None, None, None)"""
    d = pets_data.get(uid)
    if not d or not d.get("active"):
        return None, None, None
    pid = d["active"]
    if pid not in d.get("owned", {}) or pid not in PETS_DB:
        return None, None, None
    return pid, PETS_DB[pid], d["owned"][pid]

def pet_bonus(uid, bonus_type):
    """Retourne le bonus % du pet actif pour un type donné (coins/xp/roll)"""
    pid, pdb, pstate = get_active_pet(uid)
    if not pid or pdb["type"] != bonus_type:
        return 0
    return pdb["base"] + (pstate["level"] - 1)  # +1% par niveau

def give_pet_xp(uid, amount=1):
    """Donne de l'XP au pet actif. Retourne (levelup, new_level) ou (False, 0)"""
    pid, pdb, pstate = get_active_pet(uid)
    if not pid:
        return False, 0
    if pstate["level"] >= PET_LEVEL_MAX:
        return False, pstate["level"]
    pstate["xp"] += amount
    leveled = False
    while pstate["level"] < PET_LEVEL_MAX and pstate["xp"] >= PET_XP_PER_LEVEL:
        pstate["xp"] -= PET_XP_PER_LEVEL
        pstate["level"] += 1
        leveled = True
    return leveled, pstate["level"]

@bot.command(name="adopter", aliases=["adopt"])
async def adopter_cmd(ctx, rarete: str = None):
    """Adopter un compagnon — .adopter <commun|rare|epique|legendaire>"""
    prix_map = {"commun": 1000, "rare": 3000, "epique": 8000, "legendaire": 20000}
    if not rarete or rarete.lower() not in prix_map:
        return await ctx.send(embed=discord.Embed(
            title="🐾 Adoption de Compagnon",
            description=(
                "Adopte un compagnon qui te donne des **bonus passifs** !\n\n"
                "🥚 `.adopter commun` — **1 000p** (bonus +5%/+3%)\n"
                "🥚 `.adopter rare` — **3 000p** (bonus +10%/+5%)\n"
                "🥚 `.adopter epique` — **8 000p** (bonus +15%/+8%)\n"
                "🥚 `.adopter legendaire` — **20 000p** (bonus +25%/+12%)\n\n"
                "Le pet obtenu est **aléatoire** parmi 3 de la rareté choisie !\n"
                "Types de bonus : 💰 pièces • ⭐ XP • 🎰 rolls gratuits\n"
                "*Ton pet gagne de l'XP quand tu chattes et monte de niveau (+1% bonus/niveau) !*"
            ),
            color=0xe91e63))
    rarete = rarete.lower()
    rarete_label = {"commun": "Commun", "rare": "Rare", "epique": "Épique", "legendaire": "Légendaire"}[rarete]
    prix = prix_map[rarete]
    uid = str(ctx.author.id)
    if economy_data[uid]["coins"] < prix:
        return await ctx.send(f"❌ Il te faut **{prix:,} pièces** pour cet œuf !")
    economy_data[uid]["coins"] -= prix
    pool = [pid for pid, p in PETS_DB.items() if p["rarete"] == rarete_label]
    pid = random.choice(pool)
    p = PETS_DB[pid]
    if uid not in pets_data:
        pets_data[uid] = {"owned": {}, "active": None}
    if pid in pets_data[uid]["owned"]:
        # Doublon → +50 XP au pet existant
        pets_data[uid]["owned"][pid]["xp"] += 50
        give_pet_xp(uid, 0)  # recalcul niveau si actif
        return await ctx.send(embed=discord.Embed(
            title="🥚 L'œuf éclot...",
            description=f"{p['emoji']} **{p['nom']}** — tu l'as déjà !\nIl gagne **+50 XP** à la place. 💫",
            color=0x9b59b6))
    pets_data[uid]["owned"][pid] = {"level": 1, "xp": 0}
    if not pets_data[uid]["active"]:
        pets_data[uid]["active"] = pid
    unlock_achievement(uid, "pet_1", ctx.channel)
    couleurs = {"Commun": 0x95a5a6, "Rare": 0x3498db, "Épique": 0x9b59b6, "Légendaire": 0xf1c40f}
    await ctx.send(embed=discord.Embed(
        title="🥚 L'œuf éclot... ✨",
        description=(
            f"# {p['emoji']} {p['nom']}\n"
            f"**Rareté :** {p['rarete']}\n"
            f"**Bonus :** {p['desc']} ({p['base']}%)\n\n"
            f"{'🌟 Équipé automatiquement !' if pets_data[uid]['active'] == pid else 'Utilise `.pet equiper` pour l’équiper !'}"
        ),
        color=couleurs.get(p["rarete"], 0x95a5a6)))

@bot.command(name="pet", aliases=["compagnon"])
async def pet_cmd(ctx, action: str = None, *, pet_name: str = None):
    """Voir/gérer ton compagnon — .pet | .pet liste | .pet equiper <nom> | .pet nourrir"""
    uid = str(ctx.author.id)
    if action is None:
        # Afficher le pet actif
        pid, pdb, pstate = get_active_pet(uid)
        if not pid:
            return await ctx.send("🐾 Tu n'as pas de compagnon actif ! `.adopter` pour en obtenir un.")
        bonus = pdb["base"] + (pstate["level"] - 1)
        if pstate["level"] < PET_LEVEL_MAX:
            filled = int((pstate["xp"] / PET_XP_PER_LEVEL) * 10)
            bar = "█"*filled + "░"*(10-filled)
            xp_txt = f"`{bar}` {pstate['xp']}/{PET_XP_PER_LEVEL} XP"
        else:
            xp_txt = "🌟 **NIVEAU MAX !**"
        type_emoji = {"coins": "💰", "xp": "⭐", "roll": "🎰"}[pdb["type"]]
        embed = discord.Embed(
            title=f"{pdb['emoji']} {pdb['nom']}",
            description=(
                f"**Rareté :** {pdb['rarete']}\n"
                f"**Niveau :** {pstate['level']}/{PET_LEVEL_MAX}\n"
                f"{xp_txt}\n\n"
                f"{type_emoji} **Bonus actuel :** {bonus}% ({pdb['desc']})"
            ),
            color=0xe91e63)
        embed.set_footer(text="Ton pet gagne de l'XP quand tu chattes ! • .pet nourrir pour booster")
        return await ctx.send(embed=embed)
    action = action.lower()
    if action in ("liste", "list", "collection"):
        d = pets_data.get(uid)
        if not d or not d.get("owned"):
            return await ctx.send("🐾 Tu n'as aucun compagnon ! `.adopter` pour commencer.")
        lignes = []
        for pid, st in d["owned"].items():
            p = PETS_DB.get(pid)
            if p:
                actif = " 🌟" if d.get("active") == pid else ""
                lignes.append(f"{p['emoji']} **{p['nom']}** — Niv.{st['level']} ({p['rarete']}){actif}")
        return await ctx.send(embed=discord.Embed(
            title=f"🐾 Compagnons de {ctx.author.display_name}",
            description="\n".join(lignes), color=0xe91e63))
    if action in ("equiper", "équiper", "equip"):
        if not pet_name:
            return await ctx.send("❌ `.pet equiper <nom>`")
        d = pets_data.get(uid, {})
        match = next((pid for pid in d.get("owned", {}) if pet_name.lower() in PETS_DB.get(pid, {}).get("nom", "").lower()), None)
        if not match:
            return await ctx.send("❌ Tu ne possèdes pas ce compagnon !")
        pets_data[uid]["active"] = match
        p = PETS_DB[match]
        return await ctx.send(embed=discord.Embed(
            description=f"🌟 **{p['emoji']} {p['nom']}** est maintenant ton compagnon actif !", color=0x2ecc71))
    if action in ("nourrir", "feed"):
        pid, pdb, pstate = get_active_pet(uid)
        if not pid:
            return await ctx.send("🐾 Aucun compagnon actif à nourrir !")
        PRIX_REPAS = 200
        if economy_data[uid]["coins"] < PRIX_REPAS:
            return await ctx.send(f"❌ Il te faut **{PRIX_REPAS} pièces** pour un repas !")
        if pstate["level"] >= PET_LEVEL_MAX:
            return await ctx.send(f"🌟 **{pdb['nom']}** est déjà au niveau max !")
        economy_data[uid]["coins"] -= PRIX_REPAS
        leveled, lvl = give_pet_xp(uid, 25)
        msg = f"🍖 **{pdb['emoji']} {pdb['nom']}** a bien mangé ! **+25 XP**"
        if leveled:
            msg += f"\n🆙 **NIVEAU {lvl} !** Son bonus augmente !"
        return await ctx.send(embed=discord.Embed(description=msg, color=0x2ecc71))
    await ctx.send("❌ Actions : `.pet` • `.pet liste` • `.pet equiper <nom>` • `.pet nourrir`")

# ============================================================
#  AUTOROLE — Persistance
# ============================================================
AUTOROLE_FILE = data_path("autorole_config.json")
def save_autorole():
    """Sauvegarde les panels autorole dans un fichier JSON"""
    try:
        with open(AUTOROLE_FILE, "w", encoding="utf-8") as f:
            json.dump(autorole_panels, f, ensure_ascii=False)
    except Exception as e:
        print(f"[Autorole] Erreur sauvegarde : {e}")

def load_autorole():
    """Charge les panels autorole au démarrage"""
    if not os.path.exists(AUTOROLE_FILE):
        return
    try:
        with open(AUTOROLE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        autorole_panels.update(data)
        print(f"[Autorole] ✅ {len(data)} serveur(s) chargé(s)")
    except Exception as e:
        print(f"[Autorole] Erreur chargement : {e}")

# ============================================================
#  BOSS LIST — pour la commande .boss (event manuel admin)
# ============================================================
BOSS_LIST = [
    {"nom": "Muzan Kibutsuji", "emoji": "🌙", "anime": "Demon Slayer", "hp_max": 5000, "recompense": 300, "image": "https://i.imgur.com/amD1hXZ.jpg"},
    {"nom": "Sosuke Aizen",    "emoji": "🦋", "anime": "Bleach",       "hp_max": 4500, "recompense": 280, "image": "https://i.imgur.com/rtSGfrn.jpg"},
    {"nom": "Madara Uchiha",   "emoji": "👁️", "anime": "Naruto",      "hp_max": 6000, "recompense": 350, "image": "https://i.imgur.com/FYEJwwH.jpg"},
    {"nom": "All For One",     "emoji": "☠️", "anime": "MHA",          "hp_max": 4000, "recompense": 250, "image": "https://i.imgur.com/4926kae.jpg"},
    {"nom": "Yhwach",          "emoji": "👑", "anime": "Bleach",       "hp_max": 5500, "recompense": 320, "image": "https://i.imgur.com/UR1i6Tb.jpg"},
    {"nom": "Meruem",          "emoji": "♟️", "anime": "HxH",          "hp_max": 4800, "recompense": 290, "image": "https://i.imgur.com/ajOXRt1.jpg"},
    {"nom": "Kaido",           "emoji": "🐲", "anime": "One Piece",    "hp_max": 6500, "recompense": 380, "image": "https://i.imgur.com/Q76UJEX.jpg"},
    {"nom": "Sukuna",          "emoji": "☠️", "anime": "JJK",          "hp_max": 5800, "recompense": 340, "image": "https://i.imgur.com/UbB1tmt.jpg"},
]

# ============================================================
#  BRACKET — Données tournois Kdrama & Anime
# ============================================================
BRACKET_KDRAMA = [
    {"nom": "Goblin", "emoji": "🕯️"},
    {"nom": "Crash Landing on You", "emoji": "🪂"},
    {"nom": "Squid Game", "emoji": "🦑"},
    {"nom": "Vincenzo", "emoji": "🦅"},
    {"nom": "Reply 1988", "emoji": "📼"},
    {"nom": "Itaewon Class", "emoji": "🍺"},
    {"nom": "Kingdom", "emoji": "👑"},
    {"nom": "Signal", "emoji": "📻"},
    {"nom": "Hospital Playlist", "emoji": "🩺"},
    {"nom": "My Love from the Star", "emoji": "⭐"},
    {"nom": "Descendants of the Sun", "emoji": "☀️"},
    {"nom": "The Glory", "emoji": "🔥"},
    {"nom": "Queen of Tears", "emoji": "💧"},
    {"nom": "Extraordinary Attorney Woo", "emoji": "🐋"},
    {"nom": "Sweet Home", "emoji": "👹"},
    {"nom": "All of Us Are Dead", "emoji": "🧟"},
]
BRACKET_ANIME = [
    {"nom": "Attack on Titan", "emoji": "⚔️"},
    {"nom": "Demon Slayer", "emoji": "🗡️"},
    {"nom": "One Piece", "emoji": "🏴‍☠️"},
    {"nom": "Naruto", "emoji": "🍥"},
    {"nom": "Death Note", "emoji": "📓"},
    {"nom": "Jujutsu Kaisen", "emoji": "💥"},
    {"nom": "FMA Brotherhood", "emoji": "⚗️"},
    {"nom": "Hunter x Hunter", "emoji": "🎯"},
    {"nom": "Bleach", "emoji": "🌙"},
    {"nom": "Dragon Ball Z", "emoji": "🐉"},
    {"nom": "One Punch Man", "emoji": "👊"},
    {"nom": "Solo Leveling", "emoji": "🗡️"},
    {"nom": "Vinland Saga", "emoji": "🪓"},
    {"nom": "Haikyuu!!", "emoji": "🏐"},
    {"nom": "Mob Psycho 100", "emoji": "🔮"},
    {"nom": "Chainsaw Man", "emoji": "⛓️"},
]

async def bracket_lancer_match(ctx, gid, match_idx):
    """Lance le vote pour un match du bracket"""
    if gid not in active_brackets:
        return
    game = active_brackets[gid]
    matchs = game["matchs"]
    if match_idx >= len(matchs):
        return
    a, b = matchs[match_idx]
    emoji_theme = "🎬" if game["theme"] == "kdrama" else "✨"
    embed = discord.Embed(
        title=f"{emoji_theme} MATCH {match_idx+1}/{len(matchs)} — Tour {game['tour']}",
        description=(
            f"# {a['emoji']} {a['nom']}\n"
            f"## ⚔️ VS ⚔️\n"
            f"# {b['emoji']} {b['nom']}\n\n"
            f"Votez avec les réactions ! Fin du vote : 1ère majorité ou `.bracketskip` (admin)"
        ),
        color=0xf1c40f
    )
    channel = ctx.guild.get_channel(game["channel"]) if hasattr(ctx, 'guild') else ctx.channel
    if not channel:
        channel = ctx.channel
    msg = await channel.send(embed=embed)
    await msg.add_reaction("🅰️")
    await msg.add_reaction("🅱️")
    game["votes_en_cours"] = {match_idx: msg.id}

async def bracket_resoudre_match(guild, gid, match_idx):
    """Compte les votes et déclare le vainqueur du match"""
    if gid not in active_brackets:
        return
    game = active_brackets[gid]
    if match_idx not in game.get("votes_en_cours", {}):
        return
    msg_id = game["votes_en_cours"][match_idx]
    channel = guild.get_channel(game["channel"])
    if not channel:
        return
    try:
        msg = await channel.fetch_message(msg_id)
    except:
        return
    votes_a = votes_b = 0
    for r in msg.reactions:
        if str(r.emoji) == "🅰️":
            votes_a = r.count - 1
        elif str(r.emoji) == "🅱️":
            votes_b = r.count - 1
    a, b = game["matchs"][match_idx]
    if votes_a >= votes_b:
        winner = a
    else:
        winner = b
    game["gagnants"].append(winner)
    game["votes_en_cours"].pop(match_idx, None)
    await channel.send(embed=discord.Embed(
        description=f"🏆 **{winner['emoji']} {winner['nom']}** remporte le match ! ({votes_a} vs {votes_b})",
        color=0x2ecc71
    ))
    # Match suivant du même tour ?
    next_idx = match_idx + 1
    if next_idx < len(game["matchs"]):
        await asyncio.sleep(2)
        # Recréer un faux ctx avec le channel
        class FakeCtx:
            def __init__(self, ch, g):
                self.channel = ch
                self.guild = g
        await bracket_lancer_match(FakeCtx(channel, guild), gid, next_idx)
    else:
        # Tour terminé → tour suivant ou victoire finale
        gagnants = game["gagnants"]
        if len(gagnants) == 1:
            champion = gagnants[0]
            await channel.send(embed=discord.Embed(
                title="👑 CHAMPION DU TOURNOI !",
                description=f"# {champion['emoji']} {champion['nom']}\n\nÉlu meilleur {'drama' if game['theme']=='kdrama' else 'animé'} du QG ! 🎉",
                color=0xf1c40f
            ))
            del active_brackets[gid]
        else:
            # Nouveau tour
            game["tour"] += 1
            game["matchs"] = [(gagnants[i], gagnants[i+1]) for i in range(0, len(gagnants), 2)]
            game["gagnants"] = []
            await channel.send(embed=discord.Embed(
                description=f"🎖️ **TOUR {game['tour']}** — {len(game['matchs'])} match(s) restant(s) !",
                color=0x3498db
            ))
            await asyncio.sleep(2)
            class FakeCtx:
                def __init__(self, ch, g):
                    self.channel = ch
                    self.guild = g
            await bracket_lancer_match(FakeCtx(channel, guild), gid, 0)

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

def boss_barre(hp, hp_max):
    """Barre de vie colorée du boss"""
    ratio = hp / max(hp_max, 1)
    filled = int(ratio * 14)
    couleur = "🟩" if ratio > 0.6 else ("🟨" if ratio > 0.3 else "🟥")
    return couleur * filled + "⬛" * (14 - filled)

def build_boss_embed(gid, derniere_attaque=None):
    """Embed du boss en cours — partagé par .boss, .attaque et l'event invasion"""
    game = active_boss[gid]
    boss = game["boss"]
    hp, hp_max = game["hp"], boss["hp_max"]
    ratio = hp / max(hp_max, 1)
    color = 0xe74c3c if ratio < 0.3 else (0xf39c12 if ratio < 0.6 else 0x2ecc71)
    desc = (
        f"## {boss['emoji']} {boss['nom']}\n"
        f"*{boss['anime']}*\n\n"
        f"❤️ **{hp:,} / {hp_max:,} PV** — {int(ratio*100)}%\n"
        f"{boss_barre(hp, hp_max)}\n\n"
    )
    if derniere_attaque:
        desc += f"⚔️ {derniere_attaque}\n\n"
    desc += (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🗡️ Tape `.attaque` pour frapper ! *(cooldown 13s)*\n"
        f"🏆 **{boss['recompense']} pièces** pour tous les participants "
        "+ **250 bonus** au coup fatal !"
    )
    embed = discord.Embed(description=desc, color=color)
    if boss.get("image"):
        embed.set_image(url=boss["image"])
    embed.set_footer(text="QG Kdrama — Boss Event ⚔️")
    return embed

async def spawn_boss(channel, guild, ping=""):
    """Fait apparaître un boss. Retourne False si un boss est déjà en cours."""
    gid = guild.id
    if gid in active_boss:
        return False
    boss = random.choice(BOSS_LIST).copy()
    active_boss[gid] = {
        "boss": boss,
        "hp": boss["hp_max"],
        "participants": {},
        "channel": channel.id,
        "msg": None,
    }
    msg = await channel.send(ping, embed=build_boss_embed(gid))
    active_boss[gid]["msg"] = msg
    return True

@bot.command(name="boss")
@commands.has_permissions(manage_guild=True)
async def boss_cmd(ctx):
    """Fait apparaître un boss de serveur (admin) — .boss"""
    if not await spawn_boss(ctx.channel, ctx.guild):
        await ctx.send("⚔️ Un boss est déjà en cours ! Tape `.attaque` pour combattre.", delete_after=5)

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
            "Clique sur **Confirmer** pour valider."
        ),
        color=0xe74c3c
    )
    view = ConfirmView(ctx.author, timeout=30)
    msg = await ctx.send(embed=embed, view=view)
    await view.wait()
    if view.value:
        claimed_cards.clear()
        gacha_collections.clear()
        fusion_levels.clear()
        card_xp.clear()
        card_level.clear()
        serie_badges.clear()
        fav_slots.clear()
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
        await msg.edit(embed=embed_ok, view=None)
    elif view.value is False:
        await msg.edit(embed=discord.Embed(description="❌ Reset annulé.", color=0x95a5a6), view=None)
    else:
        await msg.edit(embed=discord.Embed(description="⏰ Reset annulé — timeout.", color=0x95a5a6), view=None)

# ============================================================

# ── Fonctions process_ ──────────────────────────────────────
async def process_jackpot(message):
    global jackpot_cagnotte
    if message.content.strip() == "!jackpot" and jackpot_cagnotte > 0:
        uid = str(message.author.id)
        economy_data[uid]["coins"] += jackpot_cagnotte
        await message.channel.send(embed=discord.Embed(
            title="💰 JACKPOT !",
            description=f"🎉 {message.author.mention} remporte **{jackpot_cagnotte} pièces** !",
            color=0xf1c40f
        ))
        jackpot_cagnotte = 0
loterie_data = {}  # {guild_id: {participants, cagnotte, active}}

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
    view = AcceptView(membre, timeout=60)
    msg = await ctx.send(embed=embed, view=view)
    await view.wait()
    if view.value:
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
    elif view.value is False:
            embed_no = discord.Embed(
                description=f"❌ **{membre.display_name}** a refusé l'échange.",
                color=0xe74c3c
            )
            await msg.edit(embed=embed_no)
    else:
        embed_to = discord.Embed(
            description="⏰ Échange expiré — pas de réponse dans les 60 secondes.",
            color=0x95a5a6
        )
        await msg.edit(embed=embed_to)

# ── gacharesetall ──────────────────────────────────────────────────

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
    track_stat(str(ctx.author.id), "notes", channel=ctx.channel)
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

double_xp_users = {}  # {user_id: end_timestamp}
voice_time = defaultdict(int)  # {user_id: minutes}
voice_join_time = {}  # {user_id: join_timestamp}

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
                    b_pv, b_atk, b_def = card_total_bonus(uid, k)
                    new_card = card.copy()
                    new_card["key"] = k
                    new_card["pv"]       = new_card["pv"]      + b_pv
                    new_card["attaque"]  = new_card["attaque"] + b_atk
                    new_card["defense"]  = new_card["defense"] + b_def
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
            lvlups_win = card_xp_team(str(j2_g["membre"].id), j2_g["equipe"], won=True)
            track_stat(str(j2_g["membre"].id), "pb_wins", channel=ctx.channel)
            card_xp_team(str(j1_g["membre"].id), j1_g["equipe"], won=False)
            await combat_msg.edit(embed=build_embed_pb(), view=None, content=None)
            desc_fin = f"🎉 **{j2_g['membre'].mention}** remporte le combat 3v3 !\n💰 **+300 pièces** • ⭐ **+60 XP**"
            if lvlups_win:
                desc_fin += "\n\n📈 **Cartes qui montent de niveau :**\n" + "\n".join([f"⬆️ **{nom}** → Niv. {lvl}" for nom, lvl in lvlups_win])
            await ctx.send(embed=discord.Embed(title="🏆 FIN DU COMBAT !", description=desc_fin, color=0xf1c40f))
            return
        if all(c["ko"] for c in j2_g["equipe"]):
            del active_pokebattles[ctx.channel.id]
            economy_data[str(j1_g["membre"].id)]["coins"] += 300
            xp_data[str(j1_g["membre"].id)]["xp"] += 60
            lvlups_win = card_xp_team(str(j1_g["membre"].id), j1_g["equipe"], won=True)
            track_stat(str(j1_g["membre"].id), "pb_wins", channel=ctx.channel)
            card_xp_team(str(j2_g["membre"].id), j2_g["equipe"], won=False)
            await combat_msg.edit(embed=build_embed_pb(), view=None, content=None)
            desc_fin = f"🎉 **{j1_g['membre'].mention}** remporte le combat 3v3 !\n💰 **+300 pièces** • ⭐ **+60 XP**"
            if lvlups_win:
                desc_fin += "\n\n📈 **Cartes qui montent de niveau :**\n" + "\n".join([f"⬆️ **{nom}** → Niv. {lvl}" for nom, lvl in lvlups_win])
            await ctx.send(embed=discord.Embed(title="🏆 FIN DU COMBAT !", description=desc_fin, color=0xf1c40f))
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
    "naruto":    {"nom":"Naruto Uzumaki",  "serie":"Naruto",          "rarete":"Légendaire", "emoji":"🍥", "pv":220,"attaque":90,"defense":70,"image":"https://i.imgur.com/sDvyV8G.jpg","attaques":[{"nom":"Rasengan","emoji":"🌀","degats":79,"desc":"Frappe spirale"},{"nom":"Kage Bunshin","emoji":"👥","degats":72,"desc":"Clones"},{"nom":"Neuf Queues","emoji":"🦊","degats":90,"desc":"Puissance ultime"}],"faiblesse":"⚡","resistance":"🔥"},
    "sasuke":    {"nom":"Sasuke Uchiha",   "serie":"Naruto",          "rarete":"Légendaire", "emoji":"⚡", "pv":200,"attaque":95,"defense":75,"image":"https://i.imgur.com/4dx82Ou.jpg","attaques":[{"nom":"Chidori","emoji":"⚡","degats":82,"desc":"Foudre"},{"nom":"Sharingan","emoji":"👁️","degats":72,"desc":"Copie"},{"nom":"Amaterasu","emoji":"🔥","degats":90,"desc":"Flammes noires"}],"faiblesse":"💧","resistance":"⚡"},
    "sakura":    {"nom":"Sakura Haruno",   "serie":"Naruto",          "rarete":"Rare",       "emoji":"🌸", "pv":180,"attaque":75,"defense":85,"image":"https://i.imgur.com/OlSv1D1.jpg","attaques":[{"nom":"Frappe","emoji":"👊","degats":52,"desc":"Coup de poing"},{"nom":"Soin","emoji":"💚","degats":40,"desc":"Guérison"},{"nom":"Cent Frappe","emoji":"💥","degats":56,"desc":"Destruction"}],"faiblesse":"⚡","resistance":"🌸"},
    "kurapika":  {"nom":"Kurapika",        "serie":"HunterxHunter",   "rarete":"Légendaire",     "emoji":"🔗", "pv":195,"attaque":88,"defense":72,"image":"https://i.imgur.com/HNfrNAo.jpg","attaques":[{"nom":"Chaînes","emoji":"🔗","degats":72,"desc":"Emprisonne"},{"nom":"Jugement","emoji":"⚖️","degats":79,"desc":"Exécution"},{"nom":"Vol Cœur","emoji":"❤️","degats":90,"desc":"Fatal sur araignée"}],"faiblesse":"🔥","resistance":"🔗"},
    "shikamaru": {"nom":"Shikamaru Nara",  "serie":"Naruto",          "rarete":"Rare",       "emoji":"🦌", "pv":175,"attaque":70,"defense":80,"image":"https://i.imgur.com/P8VrZXS.jpg","attaques":[{"nom":"Kagemane","emoji":"🌑","degats":35,"desc": "Immobilise"},{"nom":"Ombre","emoji":"🌒","degats":45,"desc": "Contrôle"},{"nom":"Ombre Étreinte","emoji":"💀","degats":55,"desc": "Fatal"}],"faiblesse":"🔥","resistance":"🌑"},
    "obito":     {"nom":"Obito Uchiha",    "serie":"Naruto",          "rarete":"Légendaire",   "emoji":"👁️", "pv":230,"attaque":100,"defense":90,"image":"https://i.imgur.com/9DMerh1.jpg","attaques":[{"nom":"Kamui","emoji":"🌀","degats":80,"desc":"Intangibilité"},{"nom":"Sharingan","emoji":"👁️","degats":72,"desc":"Illusion"},{"nom":"Dix Queues","emoji":"🐉","degats":90,"desc":"Dévastateur"}],"faiblesse":"💧","resistance":"👁️"},
    # ── DEMON SLAYER ────────────────────────────────────────
    "inosuke":   {"nom":"Inosuke Hashibira","serie":"Demon Slayer",   "rarete":"Épique",       "emoji":"🐗", "pv":215,"attaque":90,"defense":65,"image":"https://i.imgur.com/At5236C.jpg","attaques":[{"nom":"Bête","emoji":"🐗","degats":50,"desc": "Respiration bête"},{"nom":"Poignard","emoji":"🗡️","degats":40,"desc": "Double lame"},{"nom":"Frenésie","emoji":"💢","degats":60,"desc": "Attaque sauvage"}],"faiblesse":"⚡","resistance":"🐗"},
    "nobara":    {"nom":"Nobara Kugisaki", "serie":"Jujutsu Kaisen",  "rarete":"Épique",       "emoji":"🔨", "pv":185,"attaque":82,"defense":68,"image":"https://i.imgur.com/UAfmEnA.jpg","attaques":[{"nom":"Clou Résonance","emoji":"🔨","degats":45,"desc": "Cloue l'ennemi"},{"nom":"Paille Poupée","emoji":"🪆","degats":55,"desc": "Vaudou"},{"nom":"Explosion","emoji":"💥","degats":65,"desc": "Détonation"}],"faiblesse":"🌊","resistance":"🔨"},
    # ── JUJUTSU KAISEN ──────────────────────────────────────
    # ── ONE PIECE ────────────────────────────────────────────
    "usopp":     {"nom":"Usopp",           "serie":"One Piece",       "rarete":"Commun",     "emoji":"🎯", "pv":170,"attaque":72,"defense":60,"image":"https://i.imgur.com/0kobHRe.jpg","attaques":[{"nom":"Sarbacane","emoji":"🎯","degats":35,"desc": "Précision"},{"nom":"Pop Green","emoji":"🌿","degats":40,"desc": "Plante explosive"},{"nom":"Sogeking","emoji":"⭐","degats":50,"desc": "Sniper légendaire"}],"faiblesse":"🔥","resistance":"🎯"},
    # ── SWORD ART ONLINE ─────────────────────────────────────
    "asuna":     {"nom":"Asuna Yuuki",     "serie":"SAO",             "rarete":"Légendaire", "emoji":"⚡", "pv":200,"attaque":93,"defense":76,"image":"https://i.imgur.com/qAWf8kO.jpg","attaques":[{"nom":"Linear","emoji":"⚡","degats":55,"desc": "Frappe éclair"},{"nom":"Lambent Light","emoji":"💛","degats":65,"desc": "Épée lumineuse"},{"nom":"Mother's Rosario","emoji":"🌹","degats":80,"desc": "Combo ultime"}],"faiblesse":"🔥","resistance":"⚡"},
    # ── DARLING IN THE FRANXX ────────────────────────────────
    "zerotwo":   {"nom":"Zero Two",        "serie":"Darling in the FranXX","rarete":"Mythique","emoji":"💗","pv":235,"attaque":102,"defense":80,"image":"https://i.imgur.com/z8RKZDk.jpg","attaques":[{"nom":"Strelizia","emoji":"🌺","degats":99,"desc":"Frappe pilote"},{"nom":"Griffes","emoji":"💅","degats":88,"desc":"Lacère"},{"nom":"Apus","emoji":"💗","degats":110,"desc":"Forme ultime"}],"faiblesse":"💧","resistance":"💗"},
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
    "faye":      {"nom":"Faye Valentine",  "serie":"Cowboy Bebop",    "rarete":"Épique",       "emoji":"💜", "pv":185,"attaque":82,"defense":70,"image":"https://i.imgur.com/1i8e1kK.jpg","attaques":[{"nom":"Pistolet","emoji":"🔫","degats":64,"desc":"Tir précis"},{"nom":"Séduction","emoji":"💜","degats":56,"desc":"Déstabilise"},{"nom":"Tir Rapide","emoji":"⚡","degats":72,"desc":"Rafale"}],"faiblesse":"🚀","resistance":"💜"},
    # ── VIOLET EVERGARDEN ────────────────────────────────────
    "violet":    {"nom":"Violet Evergarden","serie":"Violet Evergarden","rarete":"Épique",   "emoji":"💌", "pv":190,"attaque":86,"defense":80,"image":"https://i.imgur.com/q3rwJ3M.jpg","attaques":[{"nom":"Lames","emoji":"⚔️","degats":55,"desc": "Combat militaire"},{"nom":"Lettre","emoji":"💌","degats":40,"desc": "Émotion intense"},{"nom":"Soldat","emoji":"🪖","degats":70,"desc": "Instinct guerrier"}],"faiblesse":"💔","resistance":"💌"},
    # ── OVERLORD ─────────────────────────────────────────────
    "ainz":      {"nom":"Ainz Ooal Gown",  "serie":"Overlord",        "rarete":"Mythique",   "emoji":"💀", "pv":250,"attaque":112,"defense":98,"image":"https://i.imgur.com/fgV5T6r.jpg","attaques":[{"nom":"Grasp Heart","emoji":"💀","degats":90,"desc":"Stop cardiaque"},{"nom":"Fallen Down","emoji":"☠️","degats":100,"desc":"Annihilation"},{"nom":"True Death","emoji":"💀","degats":110,"desc":"Mort absolue"}],"faiblesse":"✨","resistance":"💀"},
    "albedo":    {"nom":"Albedo",           "serie":"Overlord",        "rarete":"Épique", "emoji":"🖤", "pv":220,"attaque":95,"defense":95,"image":"https://i.imgur.com/XBoMVup.jpg","attaques":[{"nom":"Bouclier","emoji":"🛡️","degats":50,"desc": "Défense ultime"},{"nom":"Frappe","emoji":"💥","degats":65,"desc": "Force démoniaque"},{"nom":"Valkyrie","emoji":"🖤","degats":80,"desc": "Mode combat"}],"faiblesse":"✨","resistance":"🖤"},
    # ── RE:ZERO ───────────────────────────────────────────────
    "subaru":    {"nom":"Subaru Natsuki",   "serie":"Re:Zero",         "rarete":"Épique",       "emoji":"💙", "pv":185,"attaque":72,"defense":70,"image":"https://i.imgur.com/hq5JhSO.jpg","attaques":[{"nom":"Retour","emoji":"⏪","degats":40,"desc": "Recommence"},{"nom":"Ombre","emoji":"🌑","degats":50,"desc": "Pouvoirs noirs"},{"nom":"Dévotion","emoji":"💙","degats":60,"desc": "Volonté pure"}],"faiblesse":"💔","resistance":"💙"},
    "emilia":    {"nom":"Emilia",           "serie":"Re:Zero",         "rarete":"Épique",     "emoji":"❄️", "pv":195,"attaque":85,"defense":78,"image":"https://i.imgur.com/gTrkjMj.jpg","attaques":[{"nom":"Glace","emoji":"❄️","degats":55,"desc": "Magie de glace"},{"nom":"Gel","emoji":"🧊","degats":65,"desc": "Congèle tout"},{"nom":"Barrière","emoji":"🛡️","degats":45,"desc": "Protection glacée"}],"faiblesse":"🔥","resistance":"❄️"},
    # ── BERSERK ──────────────────────────────────────────────
    "guts":      {"nom":"Guts",            "serie":"Berserk",         "rarete":"Légendaire",   "emoji":"⚫", "pv":245,"attaque":108,"defense":85,"image":"https://i.imgur.com/PgjWnwG.jpg","attaques":[{"nom":"Dragonslayer","emoji":"⚫","degats":85,"desc": "Épée géante"},{"nom":"Berserker","emoji":"🐺","degats":100,"desc": "Armure berserker"},{"nom":"Canonnade","emoji":"💥","degats":75,"desc": "Bras canon"}],"faiblesse":"💀","resistance":"⚫"},
    "griffith":  {"nom":"Griffith",        "serie":"Berserk",         "rarete":"Mythique",   "emoji":"🦅", "pv":240,"attaque":106,"defense":92,"image":"https://i.imgur.com/2pJDLG5.jpg","attaques":[{"nom":"Femto","emoji":"🦅","degats":90,"desc": "Apôtre divin"},{"nom":"Causalité","emoji":"🌑","degats":80,"desc": "Destin inévitable"},{"nom":"Godhand","emoji":"☠️","degats":105,"desc": "Dieu de la chair"}],"faiblesse":"⚫","resistance":"🦅"},
    # ── SPY X FAMILY / MOB PSYCHO / AUTRES ───────────────────
    "mob":       {"nom":"Shigeo Kageyama", "serie":"Mob Psycho 100",  "rarete":"Mythique",   "emoji":"🔮", "pv":235,"attaque":107,"defense":88,"image":"https://i.imgur.com/twihMkj.jpg","attaques":[{"nom":"100%","emoji":"🔮","degats":95,"desc":"Débordement psychique"},{"nom":"Télékinésie","emoji":"🌀","degats":65,"desc":"Manipulation objet"},{"nom":"???%","emoji":"💥","degats":110,"desc":"Au-delà de tout"}],"faiblesse":"💔","resistance":"🔮"},
    "reigen":    {"nom":"Reigen Arataka",  "serie":"Mob Psycho 100",  "rarete":"Rare",       "emoji":"👔", "pv":170,"attaque":68,"defense":85,"image":"https://i.imgur.com/8E78wJD.jpg","attaques":[{"nom":"Salt Splash","emoji":"🧂","degats":48,"desc":"Exorcise à sel"},{"nom":"Massage","emoji":"✋","degats":40,"desc":"Décontracte"},{"nom":"Arnaque","emoji":"👔","degats":56,"desc":"Trompe l'adversaire"}],"faiblesse":"🔮","resistance":"👔"},
    # ── MELIODAS / SEVEN DEADLY SINS ─────────────────────────
    "meliodas":  {"nom":"Meliodas",        "serie":"Seven Deadly Sins","rarete":"Mythique",  "emoji":"🐉", "pv":245,"attaque":110,"defense":90,"image":"https://i.imgur.com/zkxcN5n.jpg","attaques":[{"nom":"Full Counter","emoji":"🔄","degats":80,"desc": "Renvoie les attaques"},{"nom":"Revenge Counter","emoji":"💥","degats":95,"desc": "Accumulé x10"},{"nom":"Demon King","emoji":"🐉","degats":110,"desc": "Mode roi démon"}],"faiblesse":"✨","resistance":"🐉"},
    "escanor":   {"nom":"Escanor",         "serie":"Seven Deadly Sins","rarete":"Mythique",  "emoji":"☀️", "pv":240,"attaque":115,"defense":80,"image":"https://i.imgur.com/ob5Fqky.jpg","attaques":[{"nom":"Pride","emoji":"☀️","degats":95,"desc":"Orgueil solaire"},{"nom":"The One","emoji":"👑","degats":110,"desc":"Forme ultime"},{"nom":"Sunshine","emoji":"🌞","degats":85,"desc":"Chaleur divine"}],"faiblesse":"🌙","resistance":"☀️"},
    "ban":       {"nom":"Ban",             "serie":"Seven Deadly Sins","rarete":"Légendaire","emoji":"🍺", "pv":245,"attaque":88,"defense":105,"image":"https://i.imgur.com/37tOayw.jpg","attaques":[{"nom":"Vol","emoji":"🤏","degats":72,"desc":"Vole les stats"},{"nom":"Fox Hunt","emoji":"🦊","degats":83,"desc":"Frappe multiple"},{"nom":"Zero Sign","emoji":"∞","degats":90,"desc":"Immortalité parfaite"}],"faiblesse":"💔","resistance":"⚔️"},
    "arthur_ks": {"nom":"Arthur Pendragon","serie":"Seven Deadly Sins","rarete":"Légendaire","emoji":"🗡️", "pv":215,"attaque":98,"defense":85,"image":"https://i.imgur.com/drRQ5hX.jpg","attaques":[{"nom":"Excalibur","emoji":"🗡️","degats":70,"desc": "Épée sacrée"},{"nom":"Chaos","emoji":"🌀","degats":85,"desc": "Pouvoir du chaos"},{"nom":"Roi Chaos","emoji":"👑","degats":95,"desc": "Maître du chaos"}],"faiblesse":"💀","resistance":"🗡️"},
    # ── TOWER OF GOD ─────────────────────────────────────────
    "bam":       {"nom":"Twenty-Fifth Bam","serie":"Tower of God",    "rarete":"Légendaire",   "emoji":"🕯️", "pv":240,"attaque":104,"defense":86,"image":"https://i.imgur.com/43t3sLi.jpg","attaques":[{"nom":"Shinsu","emoji":"🕯️","degats":70,"desc": "Contrôle shinsu"},{"nom":"Baam","emoji":"⚡","degats":85,"desc": "Pouvoir irrégulier"},{"nom":"Thorn","emoji":"🌑","degats":100,"desc": "Fragment d'épine"}],"faiblesse":"🌊","resistance":"🕯️"},
    "white":     {"nom":"White (Arlen)",   "serie":"Tower of God",    "rarete":"Épique",     "emoji":"🤍", "pv":205,"attaque":95,"defense":80,"image":"https://i.imgur.com/oxHxTsI.jpg","attaques":[{"nom":"Fantôme","emoji":"🤍","degats":60,"desc": "Attaque spectrale"},{"nom":"Âme","emoji":"👻","degats":70,"desc": "Dévore l'âme"},{"nom":"Blade","emoji":"🗡️","degats":80,"desc": "Lame blanche"}],"faiblesse":"🕯️","resistance":"🤍"},
    # ── VINLAND SAGA ─────────────────────────────────────────
    "thorkell":  {"nom":"Thorkell",        "serie":"Vinland Saga",    "rarete":"Légendaire", "emoji":"🪓", "pv":235,"attaque":102,"defense":78,"image":"https://i.imgur.com/NPh93gb.jpg","attaques":[{"nom":"Hache","emoji":"🪓","degats":70,"desc": "Frappe titanesque"},{"nom":"Lancer","emoji":"🎯","degats":60,"desc": "Javeline précise"},{"nom":"Berserker","emoji":"💢","degats":85,"desc": "Rage viking"}],"faiblesse":"🏹","resistance":"🪓"},
    "thorfinn":  {"nom":"Thorfinn",        "serie":"Vinland Saga",    "rarete":"Légendaire",     "emoji":"🗡️", "pv":200,"attaque":92,"defense":74,"image":"https://i.imgur.com/SjwyGc4.jpg","attaques":[{"nom":"Dague","emoji":"🗡️","degats":72,"desc":"Double dague"},{"nom":"Fantôme","emoji":"💨","degats":83,"desc":"Vitesse fantôme"},{"nom":"Askeladd","emoji":"⚔️","degats":90,"desc":"Héritage"}],"faiblesse":"🪓","resistance":"🗡️"},
    # ── FULLMETAL ALCHEMIST ──────────────────────────────────
    "edward":    {"nom":"Edward Elric",    "serie":"FMA Brotherhood", "rarete":"Épique", "emoji":"⚗️", "pv":205,"attaque":90,"defense":80,"image":"https://i.imgur.com/5xTiio2.jpg","attaques":[{"nom":"Alchimie","emoji":"⚗️","degats":55,"desc": "Transmutation"},{"nom":"Lance","emoji":"🗡️","degats":65,"desc": "Bras alchimique"},{"nom":"Frappe","emoji":"💪","degats":75,"desc": "Poing automail"}],"faiblesse":"💧","resistance":"⚗️"},
    "alphonse":  {"nom":"Alphonse Elric",  "serie":"FMA Brotherhood", "rarete":"Épique",     "emoji":"🛡️", "pv":220,"attaque":85,"defense":95,"image":"https://i.imgur.com/Ge8EMLN.jpg","attaques":[{"nom":"Armure","emoji":"🛡️","degats":50,"desc": "Frappe d'armure"},{"nom":"Alchimie","emoji":"⚗️","degats":60,"desc": "Transmutation"},{"nom":"Flamme","emoji":"🔥","degats":70,"desc": "Alchimie de feu"}],"faiblesse":"⚡","resistance":"🛡️"},
    "roy":       {"nom":"Roy Mustang",     "serie":"FMA Brotherhood", "rarete":"Épique", "emoji":"🔥", "pv":195,"attaque":97,"defense":78,"image":"https://i.imgur.com/sCqq6aL.jpg","attaques":[{"nom":"Inferno","emoji":"🔥","degats":70,"desc": "Alchimie de feu"},{"nom":"Flamme","emoji":"🔥","degats":55,"desc": "Claquement de doigts"},{"nom":"Soleil","emoji":"☀️","degats":80,"desc": "Chaleur infernale"}],"faiblesse":"💧","resistance":"🔥"},
    # ── BAKI ─────────────────────────────────────────────────
    "baki":      {"nom":"Baki Hanma",      "serie":"Baki",            "rarete":"Légendaire", "emoji":"💪", "pv":220,"attaque":98,"defense":80,"image":"https://i.imgur.com/6kAHdw4.jpg","attaques":[{"nom":"Coordinatrice","emoji":"💪","degats":65,"desc": "Force brute"},{"nom":"Imitateur","emoji":"🦈","degats":75,"desc": "Copie n'importe quoi"},{"nom":"Tremblement","emoji":"💥","degats":85,"desc": "Frappe vibratoire"}],"faiblesse":"🔮","resistance":"💪"},
    "yujiro":    {"nom":"Yujiro Hanma",    "serie":"Baki",            "rarete":"Mythique",   "emoji":"👹", "pv":255,"attaque":120,"defense":95,"image":"https://i.imgur.com/q7nhyXN.jpg","attaques":[{"nom":"Démon","emoji":"👹","degats":100,"desc":"Dos démoniaque"},{"nom":"Coordinatrice","emoji":"💪","degats":85,"desc":"Force absolue"},{"nom":"Ogre","emoji":"☠️","degats":110,"desc":"L'être le plus fort"}],"faiblesse":"💔","resistance":"👹"},
    # ── HUNTER X HUNTER (AUTRES) ─────────────────────────────
    "meruem":    {"nom":"Meruem",          "serie":"HunterxHunter",   "rarete":"Mythique",   "emoji":"♟️", "pv":250,"attaque":118,"defense":100,"image":"https://i.imgur.com/ajOXRt1.jpg","attaques":[{"nom":"Hakai","emoji":"♟️","degats":95,"desc": "Destruction pure"},{"nom":"Absorption","emoji":"🍽️","degats":80,"desc": "Vole les pouvoirs"},{"nom":"Rose","emoji":"☠️","degats":110,"desc": "Après Rose"}],"faiblesse":"🌹","resistance":"♟️"},
    # ── HELLSING ─────────────────────────────────────────────
    "alucard":   {"nom":"Alucard",         "serie":"Hellsing",        "rarete":"Mythique",   "emoji":"🧛", "pv":275,"attaque":116,"defense":125,"image":"https://i.imgur.com/EoRtG4W.jpg","attaques":[{"nom":"Restriction 0","emoji":"🧛","degats":99,"desc":"Légion d'âmes"},{"nom":"Hell","emoji":"🩸","degats":88,"desc":"Régénération"},{"nom":"Alucard Mode","emoji":"☠️","degats":110,"desc":"Vrai vampire"}],"faiblesse":"✝️","resistance":"🩸"},
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
    "kakashi":   {"nom":"Kakashi Hatake",  "serie":"Naruto",          "rarete":"Légendaire", "emoji":"⚡", "pv":205,"attaque":96,"defense":85,"image":"https://i.imgur.com/XcHGLHb.jpg","attaques":[{"nom":"Chidori","emoji":"⚡","degats":81,"desc":"Mille oiseaux"},{"nom":"Sharingan","emoji":"👁️","degats":72,"desc":"Œil copieur"},{"nom":"Kamui","emoji":"🌀","degats":90,"desc":"Dimension autre"}],"faiblesse":"💧","resistance":"⚡"},
    "madara":    {"nom":"Madara Uchiha",   "serie":"Naruto",          "rarete":"Légendaire",   "emoji":"👁️", "pv":250,"attaque":115,"defense":95,"image":"https://i.imgur.com/FYEJwwH.jpg","attaques":[{"nom":"Meteore","emoji":"☄️","degats":100,"desc": "Fait tomber des meteores"},{"nom":"Susanoo","emoji":"⚔️","degats":90,"desc": "Guerrier colossal"},{"nom":"Edo Tensei","emoji":"💀","degats":110,"desc": "Immortel"}],"faiblesse":"💧","resistance":"👁️"},
    "kaguya":    {"nom":"Kaguya Otsutsuki","serie":"Naruto",          "rarete":"Mythique",   "emoji":"🌸", "pv":255,"attaque":118,"defense":100,"image":"https://i.imgur.com/6E9Q66v.jpg","attaques":[{"nom":"Ash Bones","emoji":"🦴","degats":100,"desc":"Os qui tuent"},{"nom":"Portail","emoji":"🌀","degats":90,"desc":"Dimension de cendres"},{"nom":"Omnipotence","emoji":"🌸","degats":110,"desc":"Chakra originel"}],"faiblesse":"⚡","resistance":"🌸"},
    # ── BLEACH (nouveaux) ────────────────────────────────────
    "ichigo":    {"nom":"Ichigo Kurosaki", "serie":"Bleach",          "rarete":"Légendaire",   "emoji":"🌙", "pv":235,"attaque":103,"defense":85,"image":"https://i.imgur.com/tGmGlBB.jpg","attaques":[{"nom":"Getsuga Tensho","emoji":"🌙","degats":70,"desc": "Lune tranchante"},{"nom":"Bankai","emoji":"💀","degats":85,"desc": "Tensa Zangetsu"},{"nom":"Final Getsuga","emoji":"☠️","degats":100,"desc": "Forme finale"}],"faiblesse":"🔥","resistance":"🌙"},
    # ── ATTACK ON TITAN (nouveaux) ────────────────────────────
    "levi":      {"nom":"Levi Ackerman",   "serie":"Attack on Titan", "rarete":"Légendaire",   "emoji":"⚔️", "pv":205,"attaque":105,"defense":80,"image":"https://i.imgur.com/cvXCIWl.jpg","attaques":[{"nom":"Tourbillon","emoji":"🌪️","degats":80,"desc": "Spin légendaire"},{"nom":"Lame","emoji":"⚔️","degats":60,"desc": "Précision absolue"},{"nom":"Ackerman","emoji":"💢","degats":95,"desc": "Pouvoir du clan"}],"faiblesse":"💥","resistance":"⚔️"},
    "eren":      {"nom":"Eren Yeager",     "serie":"Attack on Titan", "rarete":"Légendaire", "emoji":"🔑", "pv":225,"attaque":97,"defense":78,"image":"https://i.imgur.com/BE73Bud.jpg","attaques":[{"nom":"Titan","emoji":"👣","degats":65,"desc": "Transformation"},{"nom":"Rumbling","emoji":"🌍","degats":90,"desc": "Grondement"},{"nom":"Fondateur","emoji":"🔑","degats":100,"desc": "Titan fondateur"}],"faiblesse":"⚡","resistance":"🔑"},
    "erwin":     {"nom":"Erwin Smith",     "serie":"Attack on Titan", "rarete":"Épique",     "emoji":"🦅", "pv":190,"attaque":80,"defense":82,"image":"https://i.imgur.com/jV3h5SB.jpg","attaques":[{"nom":"Charge","emoji":"🦅","degats":55,"desc": "Charge héroïque"},{"nom":"Tactique","emoji":"♟️","degats":65,"desc": "Stratège brillant"},{"nom":"Sacrifice","emoji":"💀","degats":75,"desc": "Tout pour l'humanité"}],"faiblesse":"💥","resistance":"🦅"},
    "mikasa":    {"nom":"Mikasa Ackerman", "serie":"Attack on Titan", "rarete":"Légendaire", "emoji":"❤️", "pv":210,"attaque":100,"defense":82,"image":"https://i.imgur.com/vwLKjUw.jpg","attaques":[{"nom":"Lame","emoji":"⚔️","degats":65,"desc": "Précision"},{"nom":"Ackerman","emoji":"💢","degats":80,"desc": "Pouvoir clan"},{"nom":"Protection","emoji":"❤️","degats":70,"desc": "Protège Eren"}],"faiblesse":"💥","resistance":"❤️"},
    # ── DEMON SLAYER (nouveaux) ──────────────────────────────
    "tanjiro":   {"nom":"Tanjiro Kamado",  "serie":"Demon Slayer",    "rarete":"Légendaire",     "emoji":"🔥", "pv":205,"attaque":88,"defense":75,"image":"https://i.imgur.com/RmLMZaP.jpg","attaques":[{"nom":"Soleil Hinokami","emoji":"☀️","degats":90,"desc":"Respiration solaire"},{"nom":"Eau","emoji":"💧","degats":72,"desc":"Respiration eau"},{"nom":"Danse Flamme","emoji":"🔥","degats":86,"desc":"Danse ignée"}],"faiblesse":"🌊","resistance":"🔥"},
    "zenitsu":   {"nom":"Zenitsu Agatsuma","serie":"Demon Slayer",    "rarete":"Épique",       "emoji":"⚡", "pv":185,"attaque":86,"defense":65,"image":"https://i.imgur.com/xBnRNSv.jpg","attaques":[{"nom":"Tonnerre","emoji":"⚡","degats":60,"desc": "Respiration foudre"},{"nom":"Godspeed","emoji":"💨","degats":75,"desc": "Vitesse éclair"},{"nom":"Thunderclap","emoji":"🌩️","degats":85,"desc": "Coup unique"}],"faiblesse":"🌊","resistance":"⚡"},
    "nezuko":    {"nom":"Nezuko Kamado",   "serie":"Demon Slayer",    "rarete":"Épique",     "emoji":"🩷", "pv":200,"attaque":85,"defense":78,"image":"https://i.imgur.com/n9kTXuX.jpg","attaques":[{"nom":"Sang Explosion","emoji":"🩸","degats":65,"desc": "Flammes roses"},{"nom":"Démon","emoji":"👹","degats":55,"desc": "Transformation"},{"nom":"Soleil","emoji":"☀️","degats":75,"desc": "Résiste au soleil"}],"faiblesse":"🌊","resistance":"🩷"},
    "tengen":    {"nom":"Tengen Uzui",     "serie":"Demon Slayer",    "rarete":"Légendaire",     "emoji":"💥", "pv":210,"attaque":93,"defense":77,"image":"https://i.imgur.com/Mv099qN.jpg","attaques":[{"nom":"Son","emoji":"🎵","degats":60,"desc": "Respiration son"},{"nom":"Explosion","emoji":"💥","degats":75,"desc": "Détonation"},{"nom":"Flamboyant","emoji":"✨","degats":80,"desc": "Spectaculaire"}],"faiblesse":"🌊","resistance":"💥"},
    "muichiro":  {"nom":"Muichiro Tokito", "serie":"Demon Slayer",    "rarete":"Légendaire",     "emoji":"🌫️", "pv":195,"attaque":91,"defense":76,"image":"https://i.imgur.com/C9Q0GcG.jpg","attaques":[{"nom":"Brume","emoji":"🌫️","degats":60,"desc": "Respiration brume"},{"nom":"Brume 7","emoji":"🌊","degats":70,"desc": "7ème forme"},{"nom":"Démon","emoji":"💀","degats":80,"desc": "Marque du démon"}],"faiblesse":"🔥","resistance":"🌫️"},
    "giyu":      {"nom":"Giyu Tomioka",    "serie":"Demon Slayer",    "rarete":"Légendaire", "emoji":"💧", "pv":215,"attaque":97,"defense":83,"image":"https://i.imgur.com/oWIcMrV.jpg","attaques":[{"nom":"Eau 11","emoji":"💧","degats":70,"desc": "Onzième forme"},{"nom":"Calme","emoji":"🌊","degats":60,"desc": "Eau tranquille"},{"nom":"Pilier","emoji":"⚔️","degats":85,"desc": "Force de pilier"}],"faiblesse":"⚡","resistance":"💧"},
    "rengoku":   {"nom":"Kyojuro Rengoku", "serie":"Demon Slayer",    "rarete":"Légendaire", "emoji":"🔥", "pv":218,"attaque":99,"defense":80,"image":"https://i.imgur.com/utlCuQn.jpg","attaques":[{"nom":"Flamme 9","emoji":"🔥","degats":75,"desc": "Neuvième forme"},{"nom":"Pillier Feu","emoji":"🔥","degats":85,"desc": "Force du pilier feu"},{"nom":"Ardeur","emoji":"💪","degats":70,"desc": "Cœur enflammé"}],"faiblesse":"💧","resistance":"🔥"},
    "sanemi":    {"nom":"Sanemi Shinazugawa","serie":"Demon Slayer",  "rarete":"Légendaire", "emoji":"🌬️", "pv":212,"attaque":98,"defense":79,"image":"https://i.imgur.com/fHuqIaF.jpg","attaques":[{"nom":"Vent","emoji":"🌬️","degats":70,"desc": "Respiration vent"},{"nom":"Cyclone","emoji":"🌪️","degats":80,"desc": "Rafale"},{"nom":"Sang Rare","emoji":"🩸","degats":85,"desc": "Sang qui attire"}],"faiblesse":"🔥","resistance":"🌬️"},
    "akaza":     {"nom":"Akaza",           "serie":"Demon Slayer",    "rarete":"Légendaire",     "emoji":"🩸", "pv":220,"attaque":102,"defense":85,"image":"https://i.imgur.com/s3SbBSM.jpg","attaques":[{"nom":"Destruction","emoji":"💥","degats":83,"desc":"Style de combat"},{"nom":"Régén","emoji":"💚","degats":72,"desc":"Se régénère"},{"nom":"Lune 3","emoji":"🌙","degats":90,"desc":"Lune supérieure 3"}],"faiblesse":"☀️","resistance":"🩸"},
    # ── JJK (nouveaux) ──────────────────────────────────────
    "gojo":      {"nom":"Satoru Gojo",     "serie":"Jujutsu Kaisen",  "rarete":"Mythique",   "emoji":"♾️", "pv":250,"attaque":110,"defense":100,"image":"https://i.imgur.com/7n8Gmn3.jpg","attaques":[{"nom":"Infini","emoji":"♾️","degats":70,"desc": "Barrière infinie"},{"nom":"Hollow Purple","emoji":"💜","degats":90,"desc": "Destructeur"},{"nom":"Domaine","emoji":"🌐","degats":100,"desc": "Sure Hit"}],"faiblesse":"💀","resistance":"♾️"},
    "sukuna":    {"nom":"Ryomen Sukuna",   "serie":"Jujutsu Kaisen",  "rarete":"Mythique",   "emoji":"☠️", "pv":255,"attaque":118,"defense":95,"image":"https://i.imgur.com/UbB1tmt.jpg","attaques":[{"nom":"Dismantle","emoji":"✂️","degats":90,"desc":"Coupe tout"},{"nom":"Malédiction","emoji":"☠️","degats":100,"desc":"Énergie maudite"},{"nom":"Domaine","emoji":"🌑","degats":110,"desc":"Boucherie"}],"faiblesse":"♾️","resistance":"☠️"},
    "yuji":      {"nom":"Yuji Itadori",    "serie":"Jujutsu Kaisen",  "rarete":"Épique",     "emoji":"👊", "pv":220,"attaque":92,"defense":80,"image":"https://i.imgur.com/wxIT2y4.jpg","attaques":[{"nom":"Divergent Fist","emoji":"👊","degats":55,"desc": "Double impact"},{"nom":"Black Flash","emoji":"⚫","degats":70,"desc": "Distorsion maudite"},{"nom":"Sukuna","emoji":"☠️","degats":85,"desc": "Roi des malédictions"}],"faiblesse":"♾️","resistance":"👊"},
    "megumi":    {"nom":"Megumi Fushiguro","serie":"Jujutsu Kaisen",  "rarete":"Épique",     "emoji":"🐕", "pv":200,"attaque":88,"defense":82,"image":"https://i.imgur.com/VRQStsA.jpg","attaques":[{"nom":"Shikigami","emoji":"🐕","degats":60,"desc": "Invoque des bêtes"},{"nom":"Mahoraga","emoji":"☯️","degats":90,"desc": "Shikigami ultime"},{"nom":"Dix Ombres","emoji":"🌑","degats":75,"desc": "Technique des ombres"}],"faiblesse":"🔥","resistance":"🌑"},
    # ── ONE PIECE (nouveaux) ─────────────────────────────────
    "luffy":     {"nom":"Monkey D. Luffy", "serie":"One Piece",       "rarete":"Légendaire",   "emoji":"👒", "pv":240,"attaque":105,"defense":85,"image":"https://i.imgur.com/WaXKIPM.jpg","attaques":[{"nom":"Gear 5","emoji":"☁️","degats":90,"desc":"Nika libéré"},{"nom":"Gomu Gomu","emoji":"👊","degats":72,"desc":"Poing élastique"},{"nom":"Red Roc","emoji":"🔥","degats":84,"desc":"Frappe embrasée"}],"faiblesse":"⚡","resistance":"👊"},
    "zoro":      {"nom":"Roronoa Zoro",    "serie":"One Piece",       "rarete":"Légendaire", "emoji":"⚔️", "pv":215,"attaque":98,"defense":82,"image":"https://i.imgur.com/Nr66sRV.jpg","attaques":[{"nom":"Asura","emoji":"👹","degats":75,"desc": "Neuf lames"},{"nom":"Hiryu Kaen","emoji":"🔥","degats":60,"desc": "Dragon de feu"},{"nom":"Enma","emoji":"⚔️","degats":85,"desc": "Lame du roi"}],"faiblesse":"💧","resistance":"⚔️"},
    "mihawk":    {"nom":"Dracule Mihawk",  "serie":"One Piece",       "rarete":"Légendaire",   "emoji":"🗡️", "pv":225,"attaque":110,"defense":88,"image":"https://i.imgur.com/pB4lYTn.jpg","attaques":[{"nom":"Slash","emoji":"🗡️","degats":80,"desc": "Coupe l'air"},{"nom":"Yoru","emoji":"🌑","degats":95,"desc": "Épée noire"},{"nom":"Croix","emoji":"✝️","degats":100,"desc": "Croix du jugement"}],"faiblesse":"💥","resistance":"🗡️"},
    "kaido":     {"nom":"Kaido",           "serie":"One Piece",       "rarete":"Mythique",   "emoji":"🐲", "pv":260,"attaque":116,"defense":100,"image":"https://i.imgur.com/Q76UJEX.jpg","attaques":[{"nom":"Thunder Bagua","emoji":"🌩️","degats":100,"desc":"Frappe de masse"},{"nom":"Dragon","emoji":"🐲","degats":110,"desc":"Transformation dragon"},{"nom":"Haoshoku","emoji":"👑","degats":110,"desc":"Haki des rois"}],"faiblesse":"⚡","resistance":"🐲"},
    "shanks":    {"nom":"Shanks",          "serie":"One Piece",       "rarete":"Mythique",   "emoji":"🍶", "pv":245,"attaque":114,"defense":95,"image":"https://i.imgur.com/BkCK51H.jpg","attaques":[{"nom":"Haki","emoji":"👑","degats":90,"desc": "Haki des rois"},{"nom":"Griffe","emoji":"⚔️","degats":80,"desc": "Cicatrice de Shanks"},{"nom":"Ittoryu","emoji":"🗡️","degats":100,"desc": "Style une lame"}],"faiblesse":"💀","resistance":"🍶"},
    # ── DRAGON BALL (nouveaux) ───────────────────────────────
    "goku":      {"nom":"Son Goku",        "serie":"Dragon Ball",     "rarete":"Mythique",   "emoji":"🟡", "pv":250,"attaque":110,"defense":90,"image":"https://i.imgur.com/YbSpxzS.jpg","attaques":[{"nom":"Kamehameha","emoji":"🌊","degats":75,"desc": "Vague d'énergie"},{"nom":"Ultra Instinct","emoji":"🟡","degats":95,"desc": "Instinct supérieur"},{"nom":"Spirit Bomb","emoji":"☀️","degats":110,"desc": "Bombe du Génie"}],"faiblesse":"💀","resistance":"🟡"},
    "vegeta":    {"nom":"Vegeta",          "serie":"Dragon Ball",     "rarete":"Mythique", "emoji":"👑", "pv":230,"attaque":100,"defense":88,"image":"https://i.imgur.com/ld1LPss.jpg","attaques":[{"nom":"Big Bang","emoji":"💥","degats":95,"desc":"Explosion ultime"},{"nom":"Galick Gun","emoji":"💜","degats":88,"desc":"Rayon violet"},{"nom":"Ultra Ego","emoji":"👑","degats":110,"desc":"Ego transcendé"}],"faiblesse":"🟡","resistance":"👑"},
    "frieza":    {"nom":"Frieza",          "serie":"Dragon Ball",     "rarete":"Mythique",   "emoji":"❄️", "pv":240,"attaque":108,"defense":92,"image":"https://i.imgur.com/qIelqUS.jpg","attaques":[{"nom":"Death Beam","emoji":"❄️","degats":80,"desc": "Rayon mortel"},{"nom":"Black Frieza","emoji":"🖤","degats":110,"desc": "Forme ultime"},{"nom":"Supernova","emoji":"💫","degats":95,"desc": "Étoile de mort"}],"faiblesse":"🟡","resistance":"❄️"},
    "beerus":    {"nom":"Beerus",          "serie":"Dragon Ball Super","rarete":"Mythique",  "emoji":"🌌", "pv":255,"attaque":120,"defense":100,"image":"https://i.imgur.com/NDn5qKx.jpg","attaques":[{"nom":"Hakai","emoji":"💥","degats":100,"desc":"Destruction pure"},{"nom":"Sphere","emoji":"🌌","degats":110,"desc":"Sphère de destruction"},{"nom":"Dieu","emoji":"✨","degats":110,"desc":"Dieu de la destruction"}],"faiblesse":"💀","resistance":"🌌"},
    # ── MHA (nouveaux) ──────────────────────────────────────
    "allmight":  {"nom":"All Might",       "serie":"My Hero Academia","rarete":"Mythique",   "emoji":"💪", "pv":240,"attaque":112,"defense":88,"image":"https://i.imgur.com/5YVOpkT.jpg","attaques":[{"nom":"Detroit Smash","emoji":"💪","degats":90,"desc": "Frappe dévastatrice"},{"nom":"Carolina Smash","emoji":"💥","degats":80,"desc": "Croisée"},{"nom":"United States Smash","emoji":"🌍","degats":110,"desc": "Ultime"}],"faiblesse":"💀","resistance":"💪"},
    "deku":      {"nom":"Izuku Midoriya",  "serie":"My Hero Academia","rarete":"Légendaire",     "emoji":"💚", "pv":210,"attaque":90,"defense":75,"image":"https://i.imgur.com/aKjpPQs.jpg","attaques":[{"nom":"Detroit Smash","emoji":"💚","degats":81,"desc":"100% One for All"},{"nom":"Shoot Style","emoji":"🦵","degats":72,"desc":"Frappe de pied"},{"nom":"Float","emoji":"🌊","degats":90,"desc":"Full Cowl"}],"faiblesse":"🔥","resistance":"💚"},
    "bakugo":    {"nom":"Katsuki Bakugo",  "serie":"My Hero Academia","rarete":"Légendaire", "emoji":"💥", "pv":215,"attaque":100,"defense":76,"image":"https://i.imgur.com/jlLDh3h.jpg","attaques":[{"nom":"Explosion","emoji":"💥","degats":70,"desc": "Nitroglycérine"},{"nom":"Howitzer","emoji":"🌀","degats":85,"desc": "Tornado explosive"},{"nom":"AP Shot","emoji":"🔫","degats":75,"desc": "Tir ciblé"}],"faiblesse":"💧","resistance":"💥"},
    "shigaraki": {"nom":"Shigaraki Tomura","serie":"My Hero Academia","rarete":"Légendaire",   "emoji":"🖐️", "pv":235,"attaque":106,"defense":82,"image":"https://i.imgur.com/464ERG7.jpg","attaques":[{"nom":"Désintégration","emoji":"🖐️","degats":90,"desc": "Touche = mort"},{"nom":"AFO","emoji":"☠️","degats":105,"desc": "Pouvoir volé"},{"nom":"Decay","emoji":"💀","degats":95,"desc": "Tout se désagrège"}],"faiblesse":"💧","resistance":"🖐️"},
    # ── CODE GEASS ───────────────────────────────────────────
    "lelouch":   {"nom":"Lelouch vi Britannia","serie":"Code Geass",  "rarete":"Mythique", "emoji":"♟️", "pv":180,"attaque":115,"defense":82,"image":"https://i.imgur.com/T0AqdVz.jpg","attaques":[{"nom":"Geass","emoji":"👁️","degats":104,"desc":"Ordre absolu"},{"nom":"Tactique","emoji":"♟️","degats":88,"desc":"Génie militaire"},{"nom":"Zéro","emoji":"🃏","degats":110,"desc":"Masque de Zéro"}],"faiblesse":"💀","resistance":"♟️"},
    "suzaku":    {"nom":"Suzaku Kururugi",  "serie":"Code Geass",    "rarete":"Épique",     "emoji":"🌸", "pv":205,"attaque":93,"defense":80,"image":"https://i.imgur.com/b5cVGjx.jpg","attaques":[{"nom":"Lancelot","emoji":"🤖","degats":65,"desc": "Knightmare Frame"},{"nom":"Hadron","emoji":"💛","degats":75,"desc": "Canon hadron"},{"nom":"Geas","emoji":"🌸","degats":80,"desc": "Vivre pour ordonner"}],"faiblesse":"♟️","resistance":"🌸"},
    # ── SOLO LEVELING ────────────────────────────────────────
    "jinwoo":    {"nom":"Sung Jin-Woo",    "serie":"Solo Leveling",   "rarete":"Mythique",   "emoji":"🗡️", "pv":248,"attaque":115,"defense":95,"image":"https://i.imgur.com/cytYnaz.jpg","attaques":[{"nom":"Ombre","emoji":"🌑","degats":90,"desc": "Armée des ombres"},{"nom":"Dague","emoji":"🗡️","degats":80,"desc": "Lame d'ombre"},{"nom":"Monarque","emoji":"👑","degats":110,"desc": "Monarque des ombres"}],"faiblesse":"✨","resistance":"🗡️"},
    # ── BLACK CLOVER ─────────────────────────────────────────
    "asta":      {"nom":"Asta",            "serie":"Black Clover",    "rarete":"Épique", "emoji":"⚫", "pv":220,"attaque":97,"defense":80,"image":"https://i.imgur.com/zxT2yys.jpg","attaques":[{"nom":"Anti-Magie","emoji":"⚫","degats":56,"desc":"Annule la magie"},{"nom":"Black Divider","emoji":"🗡️","degats":64,"desc":"Coupe tout"},{"nom":"Démon","emoji":"👹","degats":72,"desc":"Fusion démoniaque"}],"faiblesse":"🔥","resistance":"⚫"},
    "yuno":      {"nom":"Yuno",            "serie":"Black Clover",    "rarete":"Épique",     "emoji":"🍀", "pv":210,"attaque":94,"defense":80,"image":"https://i.imgur.com/R9lnjWa.jpg","attaques":[{"nom":"Vent","emoji":"🍀","degats":65,"desc": "Magie du vent"},{"nom":"Spirit Dive","emoji":"🌪️","degats":80,"desc": "Fusion avec Sylph"},{"nom":"Étoile","emoji":"⭐","degats":85,"desc": "Magie d'étoile"}],"faiblesse":"🔥","resistance":"🍀"},
    "yami":      {"nom":"Yami Sukehiro",   "serie":"Black Clover",    "rarete":"Épique", "emoji":"🌑", "pv":218,"attaque":102,"defense":83,"image":"https://i.imgur.com/H5UTEEg.jpg","attaques":[{"nom":"Dark Magic","emoji":"🌑","degats":75,"desc": "Magie des ténèbres"},{"nom":"Kata","emoji":"⚔️","degats":65,"desc": "Style sabre"},{"nom":"Dimension Slash","emoji":"💀","degats":90,"desc": "Coupe la dimension"}],"faiblesse":"✨","resistance":"🌑"},
    # ── HXH (nouveaux) ──────────────────────────────────────
    "gon":       {"nom":"Gon Freecss",     "serie":"HunterxHunter",   "rarete":"Légendaire",     "emoji":"🌿", "pv":210,"attaque":85,"defense":70,"image":"https://i.imgur.com/JEAkcm9.jpg","attaques":[{"nom":"Jajanken","emoji":"✊","degats":72,"desc":"Papier/Pierre/Ciseaux"},{"nom":"Adult Gon","emoji":"💥","degats":90,"desc":"Forme adulte"},{"nom":"Jan Ken","emoji":"💪","degats":77,"desc":"Combo"}],"faiblesse":"⚡","resistance":"🌿"},
    "killua":    {"nom":"Killua Zoldyck",  "serie":"HunterxHunter",   "rarete":"Légendaire", "emoji":"⚡", "pv":205,"attaque":92,"defense":78,"image":"https://i.imgur.com/T0BJceE.jpg","attaques":[{"nom":"Godspeed","emoji":"⚡","degats":83,"desc":"Vitesse ultime"},{"nom":"Griffes","emoji":"🗡️","degats":72,"desc":"Lacère"},{"nom":"Éclair","emoji":"🌩️","degats":90,"desc":"Décharge"}],"faiblesse":"🌊","resistance":"⚡"},
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
    "konohamaru":{"nom":"Konohamaru Sarutobi","serie":"Naruto",       "rarete":"Rare",       "emoji":"🎭", "pv":175,"attaque":72,"defense":65,"image":"https://i.imgur.com/3VJ5ob5.jpg","attaques":[{"nom":"Rasengan","emoji":"🌀","degats":56,"desc":"Imite son sensei"},{"nom":"Sexy no Jutsu","emoji":"😏","degats":40,"desc":"Déstabilise"},{"nom":"Shuriken","emoji":"🌟","degats":52,"desc":"Précision"}],"faiblesse":"🔥","resistance":"🎭"},
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
    "saitama":    {"nom":"Saitama",           "serie":"One Punch Man",    "rarete":"Mythique",   "emoji":"👊", "pv":275,"attaque":140,"defense":125,"image":"https://i.imgur.com/iMeJqxN.jpg","attaques":[{"nom":"Un seul coup","emoji":"👊","degats":110,"desc":"Instakill absolu"},{"nom":"Serious Punch","emoji":"💥","degats":110,"desc":"Détruit tout"},{"nom":"Consecutive Punches","emoji":"🌪️","degats":88,"desc":"Rafale infinie"}],"faiblesse":"💔","resistance":"👊"},
    "whis":       {"nom":"Whis",              "serie":"Dragon Ball Super", "rarete":"Mythique",   "emoji":"🪄", "pv":275,"attaque":140,"defense":125,"image":"https://i.imgur.com/SCSWxDk.jpg","attaques":[{"nom":"Temps inversé","emoji":"⏪","degats":88,"desc":"Annule toute action"},{"nom":"Bâton","emoji":"🪄","degats":110,"desc":"Frappe divine"},{"nom":"Réveil","emoji":"✨","degats":95,"desc":"Révèle la puissance"}],"faiblesse":"💀","resistance":"🪄"},
    "anos":       {"nom":"Anos Voldigoad",     "serie":"Misfit of Demon King","rarete":"Mythique", "emoji":"🩸","pv":275,"attaque":140,"defense":125,"image":"https://i.imgur.com/Sky6bPd.jpg","attaques":[{"nom":"Vendettas","emoji":"🩸","degats":110,"desc":"Anéantissement absolu"},{"nom":"Jeux Mort","emoji":"💀","degats":88,"desc":"Tue 1000 fois"},{"nom":"Démesure","emoji":"👑","degats":99,"desc":"Pouvoir infini"}],"faiblesse":"💔","resistance":"🩸"},
    "muzan":      {"nom":"Muzan Kibutsuji",    "serie":"Demon Slayer",    "rarete":"Mythique",   "emoji":"🌙", "pv":275,"attaque":120,"defense":110,"image":"https://i.imgur.com/amD1hXZ.jpg","attaques":[{"nom":"Sang Noir","emoji":"🌙","degats":104,"desc":"Sang démoniaque"},{"nom":"Régénération","emoji":"💚","degats":88,"desc":"Se régénère"},{"nom":"Roi Démons","emoji":"🌑","degats":110,"desc":"Puissance absolue"}],"faiblesse":"☀️","resistance":"🌙"},
    "garou":      {"nom":"Garou",              "serie":"One Punch Man",   "rarete":"Mythique",   "emoji":"🐺", "pv":275,"attaque":118,"defense":95,"image":"https://i.imgur.com/TQXoa3i.jpg","attaques":[{"nom":"Fist of Flowing Water","emoji":"🌊","degats":90,"desc":"Style martial"},{"nom":"Monstre","emoji":"🐺","degats":110,"desc":"Transformation"},{"nom":"God Garou","emoji":"💥","degats":110,"desc":"Forme divine"}],"faiblesse":"👊","resistance":"🐺"},
    "hashirama":  {"nom":"Hashirama Senju",    "serie":"Naruto",          "rarete":"Mythique",   "emoji":"🌿", "pv":275,"attaque":115,"defense":105,"image":"https://i.imgur.com/l3i058Z.jpg","attaques":[{"nom":"Mokuton","emoji":"🌿","degats":90,"desc":"Magie du bois"},{"nom":"Sage Mode","emoji":"🍃","degats":105,"desc":"Mode sage"},{"nom":"Bouddha Bois","emoji":"🗿","degats":110,"desc":"Colosse de bois"}],"faiblesse":"🔥","resistance":"🌿"},
    "pain":       {"nom":"Nagato/Pain",        "serie":"Naruto",          "rarete":"Mythique",   "emoji":"🔱", "pv":260,"attaque":112,"defense":95,"image":"https://i.imgur.com/uA77dW6.jpg","attaques":[{"nom":"Shinra Tensei","emoji":"🔱","degats":100,"desc":"Répulsion divine"},{"nom":"Chibaku Tensei","emoji":"🌑","degats":110,"desc":"Sphère de gravité"},{"nom":"Six Voies","emoji":"⚡","degats":90,"desc":"Six corps"}],"faiblesse":"💧","resistance":"🔱"},
    "toji":       {"nom":"Toji Fushiguro",     "serie":"Jujutsu Kaisen",  "rarete":"Mythique",   "emoji":"🗡️", "pv":250,"attaque":114,"defense":88,"image":"https://i.imgur.com/NzgqTBl.jpg","attaques":[{"nom":"Inventaire","emoji":"🗡️","degats":95,"desc":"Armes spectrales"},{"nom":"Zéro Energie","emoji":"⬛","degats":85,"desc":"Aucune énergie maudite"},{"nom":"Tueur","emoji":"💀","degats":110,"desc":"Assassin parfait"}],"faiblesse":"♾️","resistance":"🗡️"},
    "blackbeard": {"nom":"Barbe Noire",        "serie":"One Piece",       "rarete":"Mythique",   "emoji":"⚫", "pv":275,"attaque":116,"defense":98,"image":"https://i.imgur.com/DA6CfBP.jpg","attaques":[{"nom":"Tremblement","emoji":"🌍","degats":105,"desc":"Deux fruits"},{"nom":"Ténèbres","emoji":"⚫","degats":95,"desc":"Avale tout"},{"nom":"Yami Yami","emoji":"🌑","degats":110,"desc":"Gravité noire"}],"faiblesse":"⚡","resistance":"⚫"},
    "roger":      {"nom":"Gol D. Roger",       "serie":"One Piece",       "rarete":"Mythique",   "emoji":"🏴‍☠️","pv":275,"attaque":115,"defense":95,"image":"https://i.imgur.com/MHNBUvj.jpg","attaques":[{"nom":"Haki Roi","emoji":"👑","degats":105,"desc":"Conquête divine"},{"nom":"Épée","emoji":"⚔️","degats":90,"desc":"Maître épéiste"},{"nom":"Voix Monde","emoji":"🌊","degats":95,"desc":"Entend tout"}],"faiblesse":"💀","resistance":"🏴‍☠️"},

    # ── CARTES RÉCUPÉRÉES (cartes_sans_image.md) ────────────

    "nagumo_r": {"nom":"Nagumo Hajime", "serie":"Arifureta", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/cjNpGvC.jpg", "attaques":[{"nom":"Donner","emoji":"🔫","degats":44,"desc":"Revolver artisanal"},{"nom":"Transmutation","emoji":"⚗️","degats":50,"desc":"Modifie la matière"},{"nom":"Éclair Noir","emoji":"⚡","degats":55,"desc":"Magie du néant"}], "faiblesse":"⚡", "resistance":"🌟"},
    "nagumo": {"nom":"Nagumo Hajime (debut)", "serie":"Arifureta", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/cjNpGvC.jpg", "attaques":[{"nom":"Transmutation Faible","emoji":"⚗️","degats":26,"desc":"Magie de base"},{"nom":"Fuite","emoji":"🏃","degats":31,"desc":"Survivre d'abord"},{"nom":"Détermination","emoji":"💢","degats":36,"desc":"L'abîme le change"}], "faiblesse":"⚡", "resistance":"🌟"},
    "sasha": {"nom":"Sasha Blouse", "serie":"Attack on Titan", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/5JwHT7z.jpg", "attaques":[{"nom":"Tir de Précision","emoji":"🏹","degats":42,"desc":"Ne rate jamais"},{"nom":"Manœuvre Tridimensionnelle","emoji":"🪝","degats":48,"desc":"Vol acrobatique"},{"nom":"Instinct de Chasseuse","emoji":"🥔","degats":54,"desc":"Réflexes du village"}], "faiblesse":"⚡", "resistance":"🌟"},
    "jean": {"nom":"Jean Kirstein", "serie":"Attack on Titan", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/cldsnpV.jpg", "attaques":[{"nom":"Lames Doubles","emoji":"⚔️","degats":42,"desc":"Tranche la nuque"},{"nom":"Commandement","emoji":"📢","degats":48,"desc":"Dirige l'escouade"},{"nom":"Manœuvre Précise","emoji":"🪝","degats":54,"desc":"Meilleur pilote de sa promo"}], "faiblesse":"⚡", "resistance":"🌟"},
    "historia": {"nom":"Historia Reiss", "serie":"Attack on Titan", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"", "attaques":[{"nom":"Lame Royale","emoji":"👑","degats":41,"desc":"Sang de la famille royale"},{"nom":"Charge Décidée","emoji":"💨","degats":47,"desc":"Plus forte qu'elle en a l'air"},{"nom":"Volonté de Reine","emoji":"✨","degats":53,"desc":"Inspire les troupes"}], "faiblesse":"⚡", "resistance":"🌟"},
    "ymir": {"nom":"Ymir", "serie":"Attack on Titan", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"", "attaques":[{"nom":"Titan Mâchoire","emoji":"🦷","degats":44,"desc":"Morsure perforante"},{"nom":"Griffes","emoji":"🐾","degats":50,"desc":"Lacère à pleine vitesse"},{"nom":"Agilité Titanesque","emoji":"💨","degats":55,"desc":"Petit et rapide"}], "faiblesse":"⚡", "resistance":"🌟"},
    "petra": {"nom":"Petra Ral", "serie":"Attack on Titan", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"", "attaques":[{"nom":"Lames Jumelles","emoji":"⚔️","degats":41,"desc":"Escouade d'élite"},{"nom":"Vol Tournoyant","emoji":"🌀","degats":47,"desc":"Rotation tranchante"},{"nom":"Coordination","emoji":"🤝","degats":53,"desc":"Attaque en groupe"}], "faiblesse":"⚡", "resistance":"🌟"},
    "floch": {"nom":"Floch Forster", "serie":"Attack on Titan", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"", "attaques":[{"nom":"Tir Fanatique","emoji":"🔫","degats":41,"desc":"Sans hésitation"},{"nom":"Discours Enflammé","emoji":"📢","degats":47,"desc":"Rallie les Jägers"},{"nom":"Lame Vengeresse","emoji":"⚔️","degats":53,"desc":"Frappe par conviction"}], "faiblesse":"⚡", "resistance":"🌟"},
    "thomas": {"nom":"Thomas", "serie":"Attack on Titan", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/ahh7Com.jpg", "attaques":[{"nom":"Lames de Recrue","emoji":"⚔️","degats":26,"desc":"Formation de base"},{"nom":"Manœuvre Hésitante","emoji":"🪝","degats":31,"desc":"Encore peu sûr"},{"nom":"Courage Fragile","emoji":"😨","degats":36,"desc":"Tient malgré la peur"}], "faiblesse":"⚡", "resistance":"🌟"},
    "daz": {"nom":"Daz", "serie":"Attack on Titan", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"", "attaques":[{"nom":"Frappe Tremblante","emoji":"😰","degats":24,"desc":"Peu confiant"},{"nom":"Survie","emoji":"🏃","degats":29,"desc":"Fuit pour vivre"},{"nom":"Lame Désespérée","emoji":"⚔️","degats":34,"desc":"Dernier recours"}], "faiblesse":"⚡", "resistance":"🌟"},
    "samuel": {"nom":"Samuel", "serie":"Attack on Titan", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"", "attaques":[{"nom":"Lame de Recrue","emoji":"⚔️","degats":25,"desc":"Bases du corps"},{"nom":"Chute Contrôlée","emoji":"🪂","degats":30,"desc":"Récupère en vol"},{"nom":"Effort Sincère","emoji":"💪","degats":35,"desc":"Donne tout"}], "faiblesse":"⚡", "resistance":"🌟"},
    "connie": {"nom":"Connie Springer", "serie":"Attack on Titan", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/UP38Q1k.jpg", "attaques":[{"nom":"Lames Rapides","emoji":"⚔️","degats":28,"desc":"Vif malgré tout"},{"nom":"Manœuvre Agile","emoji":"🪝","degats":33,"desc":"Petit et souple"},{"nom":"Cri de Guerre","emoji":"📢","degats":38,"desc":"Motive l'escouade"}], "faiblesse":"⚡", "resistance":"🌟"},
    "griffithgod": {"nom":"Griffith (Femto)", "serie":"Berserk", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"https://i.imgur.com/2pJDLG5.jpg", "attaques":[{"nom":"Aile de Lumière","emoji":"🕊️","degats":90,"desc":"Ange déchu"},{"nom":"Appel des Apôtres","emoji":"👹","degats":99,"desc":"Armée démoniaque"},{"nom":"Éclipse","emoji":"🌑","degats":108,"desc":"Sacrifice de la Main de Dieu"}], "faiblesse":"⚡", "resistance":"🌟"},
    "gutsbk": {"nom":"Guts (Berserker)", "serie":"Berserk", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"https://i.imgur.com/PgjWnwG.jpg", "attaques":[{"nom":"Dragon Slayer","emoji":"🗡️","degats":90,"desc":"Épée trop lourde pour un homme"},{"nom":"Bras Canon","emoji":"💥","degats":99,"desc":"Tir à bout portant"},{"nom":"Armure du Berserk","emoji":"🐺","degats":108,"desc":"Ignore la douleur, brise son corps"}], "faiblesse":"⚡", "resistance":"🌟"},
    "judeau": {"nom":"Judeau", "serie":"Berserk", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/HPPvOXA.jpg", "attaques":[{"nom":"Couteaux de Lancer","emoji":"🔪","degats":42,"desc":"Précision mortelle"},{"nom":"Volée Rapide","emoji":"🎯","degats":48,"desc":"Six lames d'un geste"},{"nom":"Soutien Fidèle","emoji":"🤝","degats":54,"desc":"Toujours pour la Bande du Faucon"}], "faiblesse":"⚡", "resistance":"🌟"},
    "corkus": {"nom":"Corkus", "serie":"Berserk", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/4sywNUP.jpg", "attaques":[{"nom":"Rapière","emoji":"🤺","degats":25,"desc":"Escrime rapide"},{"nom":"Orgueil Blessé","emoji":"😤","degats":30,"desc":"Frappe de dépit"},{"nom":"Estoc Vif","emoji":"⚔️","degats":35,"desc":"Attaque nerveuse"}], "faiblesse":"⚡", "resistance":"🌟"},
    "luciusfull": {"nom":"Lucius Zogratis", "serie":"Black Clover", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"https://i.imgur.com/P5NrsCF.jpg", "attaques":[{"nom":"Magie du Temps","emoji":"⏳","degats":90,"desc":"Accélère et fige"},{"nom":"Âmes Réincarnées","emoji":"👼","degats":99,"desc":"Armée de paladins"},{"nom":"Jugement Final","emoji":"⚖️","degats":108,"desc":"Refait le monde"}], "faiblesse":"⚡", "resistance":"🌟"},
    "astafull": {"nom":"Asta (Anti-Magic)", "serie":"Black Clover", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/zxT2yys.jpg", "attaques":[{"nom":"Épée Anti-Magie","emoji":"🗡️","degats":72,"desc":"Annule les sorts"},{"nom":"Black Divider","emoji":"⚫","degats":80,"desc":"Tranche le mana"},{"nom":"Black Meteorite","emoji":"☄️","degats":88,"desc":"Charge dévastatrice"}], "faiblesse":"⚡", "resistance":"🌟"},
    "yunofull": {"nom":"Yuno (Spirit)", "serie":"Black Clover", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/R9lnjWa.jpg", "attaques":[{"nom":"Spirit Dive","emoji":"🌪️","degats":72,"desc":"Fusion avec Sylph"},{"nom":"Spirit Storm","emoji":"🌀","degats":80,"desc":"Tempête de vent"},{"nom":"Spirit of Boreas","emoji":"❄️","degats":88,"desc":"Lance glaciale"}], "faiblesse":"⚡", "resistance":"🌟"},
    "spade": {"nom":"Dante Zogratis", "serie":"Black Clover", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/Bp0jw1D.jpg", "attaques":[{"nom":"Magie du Corps","emoji":"🩸","degats":72,"desc":"Membres déformables"},{"nom":"Gravity Singularity","emoji":"🕳️","degats":80,"desc":"Écrase par la gravité"},{"nom":"Force du Démon","emoji":"👹","degats":88,"desc":"Puissance de l'Arcane"}], "faiblesse":"⚡", "resistance":"🌟"},
    "lichtbc": {"nom":"Licht", "serie":"Black Clover", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/17Bjofy.jpg", "attaques":[{"nom":"Épée de Lumière","emoji":"✨","degats":58,"desc":"Lame étincelante"},{"nom":"Sword Creation","emoji":"⚔️","degats":65,"desc":"Armes multiples"},{"nom":"Elf Reincarnation","emoji":"🧝","degats":72,"desc":"Forme originelle"}], "faiblesse":"⚡", "resistance":"🌟"},
    "mereoleona": {"nom":"Mereoleona Vermillion", "serie":"Black Clover", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/JMhLymg.jpg", "attaques":[{"nom":"Poing du Lion Ardent","emoji":"🦁","degats":58,"desc":"Frappe incandescente"},{"nom":"Calidos Brachium","emoji":"🔥","degats":65,"desc":"Bras de flammes"},{"nom":"Mana Zone","emoji":"🌋","degats":72,"desc":"Domine la zone"}], "faiblesse":"⚡", "resistance":"🌟"},
    "julius": {"nom":"Julius Novachrono", "serie":"Black Clover", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/wEc5g2E.jpg", "attaques":[{"nom":"Chrono Anastasis","emoji":"⏱️","degats":59,"desc":"Stocke le temps"},{"nom":"Vol de Temps","emoji":"⌛","degats":65,"desc":"Prend les années"},{"nom":"Accélération","emoji":"⚡","degats":72,"desc":"Se meut hors du temps"}], "faiblesse":"⚡", "resistance":"🌟"},
    "zenon": {"nom":"Zenon Zogratis", "serie":"Black Clover", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/N8kGT5u.jpg", "attaques":[{"nom":"Magie d'Os","emoji":"🦴","degats":58,"desc":"Lances osseuses"},{"nom":"Bone Prison","emoji":"⛓️","degats":65,"desc":"Cage de côtes"},{"nom":"Spirit of Boreas","emoji":"👹","degats":72,"desc":"Pouvoir du démon"}], "faiblesse":"⚡", "resistance":"🌟"},
    "magna": {"nom":"Magna Swing", "serie":"Black Clover", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/qH2W7pZ.jpg", "attaques":[{"nom":"Exploding Fireball","emoji":"🔥","degats":42,"desc":"Balle enflammée"},{"nom":"Flame Magic Ball","emoji":"⚾","degats":48,"desc":"Frappe de batteur"},{"nom":"Soul Chain","emoji":"⛓️","degats":54,"desc":"Lien avec son ami"}], "faiblesse":"⚡", "resistance":"🌟"},
    "gauche": {"nom":"Gauche Adlai", "serie":"Black Clover", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/hMWHQ4G.jpg", "attaques":[{"nom":"Mirror Magic","emoji":"🪞","degats":42,"desc":"Réfléchit les sorts"},{"nom":"Reflect Ray","emoji":"💫","degats":48,"desc":"Rayon renvoyé"},{"nom":"Real Double","emoji":"👥","degats":54,"desc":"Clone miroir"}], "faiblesse":"⚡", "resistance":"🌟"},
    "noelle_r": {"nom":"Noelle Silva (debut)", "serie":"Black Clover", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/IE0nG9f.jpg", "attaques":[{"nom":"Water Ball","emoji":"💧","degats":41,"desc":"Sphère d'eau"},{"nom":"Sea Dragon's Roar","emoji":"🐉","degats":47,"desc":"Rugissement aquatique"},{"nom":"Valkyrie Dress","emoji":"👗","degats":53,"desc":"Armure d'eau"}], "faiblesse":"⚡", "resistance":"🌟"},
    "sekke": {"nom":"Sekke Bronzazza", "serie":"Black Clover", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/qEHztQO.jpg", "attaques":[{"nom":"Sekke Magnum","emoji":"🐝","degats":24,"desc":"Boule de bronze"},{"nom":"Fuite Élégante","emoji":"💨","degats":29,"desc":"Se retire poliment"},{"nom":"Flatterie","emoji":"😁","degats":34,"desc":"Se fait bien voir"}], "faiblesse":"⚡", "resistance":"🌟"},
    "aizenhogy": {"nom":"Aizen (Hogyoku)", "serie":"Bleach", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"", "attaques":[{"nom":"Kyoka Suigetsu","emoji":"🌙","degats":90,"desc":"Hypnose totale"},{"nom":"Fusion Hogyoku","emoji":"💠","degats":99,"desc":"Évolution perpétuelle"},{"nom":"Kurohitsugi","emoji":"⬛","degats":108,"desc":"Cercueil noir"}], "faiblesse":"⚡", "resistance":"🌟"},
    "yhwachalmighty": {"nom":"Yhwach (Almighty)", "serie":"Bleach", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"https://i.imgur.com/UR1i6Tb.jpg", "attaques":[{"nom":"The Almighty","emoji":"👁️","degats":92,"desc":"Voit et réécrit l'avenir"},{"nom":"Sankt Altar","emoji":"⚔️","degats":100,"desc":"Lame sacrée"},{"nom":"Auswählen","emoji":"✨","degats":110,"desc":"Sélection divine"}], "faiblesse":"⚡", "resistance":"🌟"},
    "ichigofull": {"nom":"Ichigo (Full Hollow)", "serie":"Bleach", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"https://i.imgur.com/tGmGlBB.jpg", "attaques":[{"nom":"Getsuga Tensho","emoji":"🌑","degats":89,"desc":"Lame noire"},{"nom":"Masque de Hollow","emoji":"👺","degats":98,"desc":"Puissance déchaînée"},{"nom":"Rugissement Vasto","emoji":"🔊","degats":107,"desc":"Instinct pur"}], "faiblesse":"⚡", "resistance":"🌟"},
    "ichigofinal": {"nom":"Ichigo (Final Getsuga)", "serie":"Bleach", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/tGmGlBB.jpg", "attaques":[{"nom":"Mugetsu","emoji":"🌑","degats":73,"desc":"Lame de ténèbres"},{"nom":"Final Getsuga","emoji":"⚫","degats":81,"desc":"Devient l'attaque"},{"nom":"Sacrifice","emoji":"💔","degats":88,"desc":"Au prix de ses pouvoirs"}], "faiblesse":"⚡", "resistance":"🌟"},
    "stark": {"nom":"Coyote Starrk", "serie":"Bleach", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"", "attaques":[{"nom":"Los Lobos","emoji":"🐺","degats":72,"desc":"Meute d'énergie"},{"nom":"Cero Metralleta","emoji":"💥","degats":80,"desc":"Rafale de ceros"},{"nom":"Colmillo","emoji":"🗡️","degats":87,"desc":"Croc du loup solitaire"}], "faiblesse":"⚡", "resistance":"🌟"},
    "barragan": {"nom":"Barragan", "serie":"Bleach", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/jbuhrOW.jpg", "attaques":[{"nom":"Respira","emoji":"💀","degats":72,"desc":"Le souffle du vieillissement"},{"nom":"Arrogante","emoji":"👑","degats":80,"desc":"Roi squelette"},{"nom":"Gran Caida","emoji":"🪓","degats":88,"desc":"Hache du monarque"}], "faiblesse":"⚡", "resistance":"🌟"},
    "shunsui": {"nom":"Shunsui Kyoraku", "serie":"Bleach", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"", "attaques":[{"nom":"Katen Kyokotsu","emoji":"🎭","degats":72,"desc":"Jeux mortels"},{"nom":"Bushogoma","emoji":"🌪️","degats":80,"desc":"Tourbillon jumeau"},{"nom":"Kageoni","emoji":"👥","degats":87,"desc":"Le jeu de l'ombre"}], "faiblesse":"⚡", "resistance":"🌟"},
    "unohana": {"nom":"Retsu Unohana", "serie":"Bleach", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"", "attaques":[{"nom":"Minazuki","emoji":"🩸","degats":72,"desc":"Lame carmin"},{"nom":"Kaido Sanjuurokku","emoji":"💚","degats":80,"desc":"Soin instantané"},{"nom":"Première Kenpachi","emoji":"⚔️","degats":88,"desc":"Instinct de tueuse"}], "faiblesse":"⚡", "resistance":"🌟"},
    "halibel": {"nom":"Tier Harribel", "serie":"Bleach", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"", "attaques":[{"nom":"Cascada","emoji":"🌊","degats":72,"desc":"Vague écrasante"},{"nom":"La Gota","emoji":"💧","degats":80,"desc":"Goutte tranchante"},{"nom":"Tiburon","emoji":"🦈","degats":88,"desc":"Forme de requin"}], "faiblesse":"⚡", "resistance":"🌟"},
    "renji": {"nom":"Renji Abarai", "serie":"Bleach", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"", "attaques":[{"nom":"Zabimaru","emoji":"🐍","degats":42,"desc":"Lame segmentée"},{"nom":"Hihio Zabimaru","emoji":"🦴","degats":48,"desc":"Serpent d'os"},{"nom":"Bankai Rugissant","emoji":"💢","degats":54,"desc":"Puissance libérée"}], "faiblesse":"⚡", "resistance":"🌟"},
    "ikkaku": {"nom":"Ikkaku Madarame", "serie":"Bleach", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"", "attaques":[{"nom":"Hozukimaru","emoji":"🔱","degats":42,"desc":"Lance à trois sections"},{"nom":"Ryumon Hozukimaru","emoji":"🐉","degats":48,"desc":"Bankai du dragon"},{"nom":"Danse de Combat","emoji":"💃","degats":54,"desc":"Plus il saigne, plus il frappe"}], "faiblesse":"⚡", "resistance":"🌟"},
    "rangiku": {"nom":"Rangiku Matsumoto", "serie":"Bleach", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"", "attaques":[{"nom":"Haineko","emoji":"🐱","degats":41,"desc":"Cendres tranchantes"},{"nom":"Nuage de Cendres","emoji":"☁️","degats":47,"desc":"Enveloppe l'ennemi"},{"nom":"Lame Dispersée","emoji":"✨","degats":53,"desc":"Mille éclats"}], "faiblesse":"⚡", "resistance":"🌟"},
    "izuru": {"nom":"Izuru Kira", "serie":"Bleach", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"", "attaques":[{"nom":"Wabisuke","emoji":"⚖️","degats":41,"desc":"Double le poids à chaque coup"},{"nom":"Frappe Alourdie","emoji":"🪨","degats":47,"desc":"Cloue au sol"},{"nom":"Lame Crochue","emoji":"🪝","degats":53,"desc":"Désarme"}], "faiblesse":"⚡", "resistance":"🌟"},
    "chad": {"nom":"Yasutora Chad", "serie":"Bleach", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"", "attaques":[{"nom":"Brazo Derecha","emoji":"🦾","degats":43,"desc":"Bras du géant"},{"nom":"La Muerte","emoji":"💀","degats":49,"desc":"Poing dévastateur"},{"nom":"Brazo Izquierda","emoji":"🛡️","degats":55,"desc":"Bras du diable"}], "faiblesse":"⚡", "resistance":"🌟"},
    "uryu": {"nom":"Uryu Ishida", "serie":"Bleach", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/eg1x8Zi.jpg", "attaques":[{"nom":"Licht Regen","emoji":"🏹","degats":42,"desc":"Pluie de flèches"},{"nom":"Seele Schneider","emoji":"⚔️","degats":48,"desc":"Lame de reishi"},{"nom":"Letzt Stil","emoji":"✨","degats":54,"desc":"Puissance ultime"}], "faiblesse":"⚡", "resistance":"🌟"},
    "hanataro": {"nom":"Hanataro Yamada", "serie":"Bleach", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/pHxnJ3G.jpg", "attaques":[{"nom":"Hisagomaru","emoji":"💊","degats":25,"desc":"Lame de soin"},{"nom":"Akeiro Hisagomaru","emoji":"🩹","degats":30,"desc":"Libère l'énergie soignée"},{"nom":"Soutien Discret","emoji":"🧹","degats":35,"desc":"Toujours là pour aider"}], "faiblesse":"⚡", "resistance":"🌟"},
    "donkanonji": {"nom":"Don Kanonji", "serie":"Bleach", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/0mrQRon.jpg", "attaques":[{"nom":"Bohahaha","emoji":"📢","degats":26,"desc":"Rire tonitruant"},{"nom":"Canne Spirituelle","emoji":"🦯","degats":31,"desc":"Frappe bénie"},{"nom":"Pose de Star","emoji":"⭐","degats":36,"desc":"Impressionne le public"}], "faiblesse":"⚡", "resistance":"🌟"},
    "keigo": {"nom":"Keigo Asano", "serie":"Bleach", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/KxrABAv.jpg", "attaques":[{"nom":"Fuite Paniquée","emoji":"😱","degats":24,"desc":"Détale en hurlant"},{"nom":"Coup Désespéré","emoji":"👊","degats":29,"desc":"Frappe maladroite"},{"nom":"Cri d'Alerte","emoji":"📢","degats":34,"desc":"Prévient ses amis"}], "faiblesse":"⚡", "resistance":"🌟"},
    "mizuiro": {"nom":"Mizuiro Kojima", "serie":"Bleach", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/VHWPYMs.jpg", "attaques":[{"nom":"Coup Calculé","emoji":"📱","degats":25,"desc":"Frappe réfléchie"},{"nom":"Charme Discret","emoji":"😌","degats":30,"desc":"Déconcentre"},{"nom":"Esquive Souple","emoji":"💨","degats":35,"desc":"Évite sans effort"}], "faiblesse":"⚡", "resistance":"🌟"},
    "okamome": {"nom":"Momo Ayase", "serie":"Dandadan", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/TEJ6KZr.jpg", "attaques":[{"nom":"Pouvoir Psychique","emoji":"🔮","degats":58,"desc":"Télékinésie brute"},{"nom":"Coup de Pied Spirituel","emoji":"🦵","degats":65,"desc":"Frappe surnaturelle"},{"nom":"Cri de Turbo Mamie","emoji":"👵","degats":72,"desc":"Invoque l'esprit"}], "faiblesse":"⚡", "resistance":"🌟"},
    "akkum": {"nom":"Aira Shiratori", "serie":"Dandadan", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/xqs2Gev.jpg", "attaques":[{"nom":"Idol Aura","emoji":"🌟","degats":27,"desc":"Charme surnaturel"},{"nom":"Coup d'Ongles","emoji":"💅","degats":32,"desc":"Griffure vive"},{"nom":"Popularité","emoji":"📣","degats":37,"desc":"Le public la porte"}], "faiblesse":"⚡", "resistance":"🌟"},
    "narumigen": {"nom":"Gen Narumi (debut)", "serie":"Dandadan", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"", "attaques":[{"nom":"Coup Rapide","emoji":"👊","degats":26,"desc":"Frappe nerveuse"},{"nom":"Esquive","emoji":"💨","degats":31,"desc":"Réflexes affûtés"},{"nom":"Bluff","emoji":"😎","degats":36,"desc":"Fait le fanfaron"}], "faiblesse":"⚡", "resistance":"🌟"},
    "yoriichi": {"nom":"Yoriichi Tsugikuni", "serie":"Demon Slayer", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"https://i.imgur.com/blBxnnO.jpg", "attaques":[{"nom":"Danse du Dieu du Feu","emoji":"🔥","degats":91,"desc":"Souffle originel"},{"nom":"Cercle de Flammes","emoji":"🌀","degats":100,"desc":"Rotation parfaite"},{"nom":"Œil de la Transparence","emoji":"👁️","degats":109,"desc":"Voit chaque muscle"}], "faiblesse":"⚡", "resistance":"🌟"},
    "muzanfinal": {"nom":"Muzan (Forme Finale)", "serie":"Demon Slayer", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"https://i.imgur.com/amD1hXZ.jpg", "attaques":[{"nom":"Fouets Charnels","emoji":"🩸","degats":90,"desc":"Tentacules tranchants"},{"nom":"Régénération Absolue","emoji":"♾️","degats":99,"desc":"Se reforme sans cesse"},{"nom":"Sang Démoniaque","emoji":"☠️","degats":108,"desc":"Poison instantané"}], "faiblesse":"⚡", "resistance":"🌟"},
    "gyomei": {"nom":"Gyomei Himejima", "serie":"Demon Slayer", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/YtrUnvL.jpg", "attaques":[{"nom":"Souffle de la Roche","emoji":"🪨","degats":73,"desc":"Force colossale"},{"nom":"Hache et Fléau","emoji":"⛓️","degats":81,"desc":"Chaîne dévastatrice"},{"nom":"Marque du Pourfendeur","emoji":"💠","degats":88,"desc":"Puissance décuplée"}], "faiblesse":"⚡", "resistance":"🌟"},
    "mitsuri": {"nom":"Mitsuri Kanroji", "serie":"Demon Slayer", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/jtoItwO.jpg", "attaques":[{"nom":"Souffle de l'Amour","emoji":"💕","degats":72,"desc":"Lame souple"},{"nom":"Frisson d'Amour","emoji":"💗","degats":80,"desc":"Six coups enchaînés"},{"nom":"Fouet Écarlate","emoji":"🎀","degats":88,"desc":"Katana flexible"}], "faiblesse":"⚡", "resistance":"🌟"},
    "obanai": {"nom":"Obanai Iguro", "serie":"Demon Slayer", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/yNIPY2y.jpg", "attaques":[{"nom":"Souffle du Serpent","emoji":"🐍","degats":72,"desc":"Trajectoire sinueuse"},{"nom":"Serpent Jumeau","emoji":"🐉","degats":80,"desc":"Double morsure"},{"nom":"Reptation Mortelle","emoji":"💀","degats":88,"desc":"Frappe imprévisible"}], "faiblesse":"⚡", "resistance":"🌟"},
    "doma": {"nom":"Doma", "serie":"Demon Slayer", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/IBoGpOh.jpg", "attaques":[{"nom":"Souffle de Glace","emoji":"❄️","degats":72,"desc":"Cristaux mortels"},{"nom":"Lotus Givré","emoji":"🪷","degats":80,"desc":"Fleur de glace"},{"nom":"Brume Empoisonnée","emoji":"🌫️","degats":88,"desc":"Gèle les poumons"}], "faiblesse":"⚡", "resistance":"🌟"},
    "kokushibo": {"nom":"Kokushibo", "serie":"Demon Slayer", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/3jSkSj0.jpg", "attaques":[{"nom":"Souffle de la Lune","emoji":"🌙","degats":73,"desc":"Lames lunaires"},{"nom":"Lunes Multiples","emoji":"🌑","degats":81,"desc":"Croissants imprévisibles"},{"nom":"Œil Transparent","emoji":"👁️","degats":88,"desc":"Six yeux, aucune faille"}], "faiblesse":"⚡", "resistance":"🌟"},
    "tengen_l": {"nom":"Tengen Uzui (Full)", "serie":"Demon Slayer", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/Mv099qN.jpg", "attaques":[{"nom":"Souffle du Son","emoji":"🔊","degats":72,"desc":"Partition musicale"},{"nom":"Musique Meurtrière","emoji":"🎶","degats":80,"desc":"Rythme de la mort"},{"nom":"Explosion Flamboyante","emoji":"💥","degats":88,"desc":"Bombes et cimeterres"}], "faiblesse":"⚡", "resistance":"🌟"},
    "kanaep": {"nom":"Kanao Tsuyuri (Full)", "serie":"Demon Slayer", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/wDD0iSX.jpg", "attaques":[{"nom":"Souffle de la Fleur","emoji":"🌸","degats":58,"desc":"Danse gracieuse"},{"nom":"Œil du Dieu Fleur","emoji":"👁️","degats":65,"desc":"Ralentit sa perception"},{"nom":"Équinoxe Vermillon","emoji":"🌺","degats":72,"desc":"Coupe finale"}], "faiblesse":"⚡", "resistance":"🌟"},
    "genyaep": {"nom":"Genya Shinazugawa (Full)", "serie":"Demon Slayer", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/AaQT1PZ.jpg", "attaques":[{"nom":"Fusil à Pompe","emoji":"🔫","degats":58,"desc":"Balles bénies"},{"nom":"Consommation Démoniaque","emoji":"🩸","degats":65,"desc":"Mange pour se renforcer"},{"nom":"Cheveux Perforants","emoji":"💇","degats":72,"desc":"Lances organiques"}], "faiblesse":"⚡", "resistance":"🌟"},
    "zenitsur": {"nom":"Zenitsu (Endormi)", "serie":"Demon Slayer", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/xBnRNSv.jpg", "attaques":[{"nom":"Éclair Foudroyant","emoji":"⚡","degats":44,"desc":"Une seule attaque, parfaite"},{"nom":"Six Fois","emoji":"6️⃣","degats":50,"desc":"Six éclairs successifs"},{"nom":"Sommeil du Guerrier","emoji":"😴","degats":55,"desc":"Endormi, donc invincible"}], "faiblesse":"⚡", "resistance":"🌟"},
    "inozukur": {"nom":"Inosuke (Fort)", "serie":"Demon Slayer", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/At5236C.jpg", "attaques":[{"nom":"Souffle de la Bête","emoji":"🐗","degats":44,"desc":"Deux lames dentelées"},{"nom":"Croc Tranchant","emoji":"🦷","degats":50,"desc":"Découpe sauvage"},{"nom":"Perception Spatiale","emoji":"🌐","degats":55,"desc":"Sent tout autour de lui"}], "faiblesse":"⚡", "resistance":"🌟"},
    "kanaocom": {"nom":"Kanao Tsuyuri (debut)", "serie":"Demon Slayer", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/wDD0iSX.jpg", "attaques":[{"nom":"Souffle de la Fleur","emoji":"🌸","degats":28,"desc":"Encore en apprentissage"},{"nom":"Pile ou Face","emoji":"🪙","degats":33,"desc":"Laisse le hasard décider"},{"nom":"Danse Légère","emoji":"💃","degats":38,"desc":"Mouvements fluides"}], "faiblesse":"⚡", "resistance":"🌟"},
    "genyacom": {"nom":"Genya Shinazugawa (debut)", "serie":"Demon Slayer", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/AaQT1PZ.jpg", "attaques":[{"nom":"Coup de Fusil","emoji":"🔫","degats":29,"desc":"Tir rapproché"},{"nom":"Rage Fraternelle","emoji":"💢","degats":34,"desc":"Se bat pour son frère"},{"nom":"Morsure Démoniaque","emoji":"🦷","degats":39,"desc":"Absorbe un fragment"}], "faiblesse":"⚡", "resistance":"🌟"},
    "vegitossj4": {"nom":"Vegito (SSJ4)", "serie":"Dragon Ball GT", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"https://i.imgur.com/COP7cnj.jpg", "attaques":[{"nom":"Kamehameha x100","emoji":"🌊","degats":90,"desc":"Puissance centuplée"},{"nom":"Épée Spirituelle","emoji":"⚔️","degats":99,"desc":"Lame d'énergie pure"},{"nom":"Fusion Ultime","emoji":"💥","degats":108,"desc":"Apogée de la fusion"}], "faiblesse":"⚡", "resistance":"🌟"},
    "goguissj4": {"nom":"Gogeta (SSJ4)", "serie":"Dragon Ball GT", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"https://i.imgur.com/7rZvNsk.jpg", "attaques":[{"nom":"Big Bang Kamehameha","emoji":"🌊","degats":90,"desc":"Vague colossale"},{"nom":"Dragon du Chaos","emoji":"🐉","degats":99,"desc":"Dragon d'énergie"},{"nom":"Frappe SSJ4","emoji":"👊","degats":107,"desc":"Poing écarlate"}], "faiblesse":"⚡", "resistance":"🌟"},
    "gokugt": {"nom":"Goku (GT SSJ4)", "serie":"Dragon Ball GT", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"", "attaques":[{"nom":"Kamehameha x10","emoji":"🌊","degats":74,"desc":"Version décuplée"},{"nom":"Dragon Fist","emoji":"🐉","degats":82,"desc":"Poing du dragon"},{"nom":"Queue de Singe","emoji":"🐒","degats":88,"desc":"Retour aux origines"}], "faiblesse":"⚡", "resistance":"🌟"},
    "vegtassj4": {"nom":"Vegeta (SSJ4)", "serie":"Dragon Ball GT", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/ld1LPss.jpg", "attaques":[{"nom":"Final Flash","emoji":"✨","degats":74,"desc":"Charge dorée"},{"nom":"Big Bang Attack","emoji":"💥","degats":81,"desc":"Sphère explosive"},{"nom":"Rage du Prince","emoji":"👑","degats":88,"desc":"Fierté saiyan"}], "faiblesse":"⚡", "resistance":"🌟"},
    "gokuui": {"nom":"Goku (Ultra Instinct)", "serie":"Dragon Ball Super", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"", "attaques":[{"nom":"Esquive Autonome","emoji":"💠","degats":88,"desc":"Le corps réagit seul"},{"nom":"Kamehameha Ultra","emoji":"🌊","degats":98,"desc":"Vague argentée"},{"nom":"Poing de l'Instinct","emoji":"👊","degats":108,"desc":"Frappe parfaite"}], "faiblesse":"⚡", "resistance":"🌟"},
    "vegetaue": {"nom":"Vegeta (Ultra Ego)", "serie":"Dragon Ball Super", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"https://i.imgur.com/ld1LPss.jpg", "attaques":[{"nom":"Hakai","emoji":"💜","degats":88,"desc":"Destruction pure"},{"nom":"Poing de l'Orgueil","emoji":"👊","degats":97,"desc":"Plus il souffre, plus il frappe"},{"nom":"Ultra Ego Final","emoji":"💥","degats":106,"desc":"Apogée du guerrier"}], "faiblesse":"⚡", "resistance":"🌟"},
    "zenousama": {"nom":"Zeno-Sama", "serie":"Dragon Ball Super", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"https://i.imgur.com/QyPDWvD.jpg", "attaques":[{"nom":"Effacement","emoji":"⚪","degats":92,"desc":"Efface de l'existence"},{"nom":"Volonté du Roi","emoji":"👑","degats":100,"desc":"Décret absolu"},{"nom":"Néant","emoji":"🌌","degats":110,"desc":"Plus rien ne subsiste"}], "faiblesse":"⚡", "resistance":"🌟"},
    "grandpretre": {"nom":"Grand Prêtre", "serie":"Dragon Ball Super", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"", "attaques":[{"nom":"Garde Divine","emoji":"🕊️","degats":90,"desc":"Protection angélique"},{"nom":"Frappe Angélique","emoji":"✨","degats":99,"desc":"Coup imparable"},{"nom":"Jugement Suprême","emoji":"⚖️","degats":108,"desc":"Sentence divine"}], "faiblesse":"⚡", "resistance":"🌟"},
    "brolybersk": {"nom":"Broly (Berserk)", "serie":"Dragon Ball Super", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"https://i.imgur.com/c0oACBA.jpg", "attaques":[{"nom":"Rage Incontrôlable","emoji":"😡","degats":88,"desc":"Puissance qui monte"},{"nom":"Gigantic Roar","emoji":"🔊","degats":97,"desc":"Rugissement destructeur"},{"nom":"Omega Blaster","emoji":"☄️","degats":107,"desc":"Sphère colossale"}], "faiblesse":"⚡", "resistance":"🌟"},
    "toppohakai": {"nom":"Toppo (Hakai)", "serie":"Dragon Ball Super", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"https://i.imgur.com/fSf1u96.jpg", "attaques":[{"nom":"Justice Flash","emoji":"⚡","degats":87,"desc":"Charge du justicier"},{"nom":"Hakai","emoji":"💜","degats":96,"desc":"Pouvoir de destruction"},{"nom":"Poing du Dieu","emoji":"👊","degats":105,"desc":"Frappe divine"}], "faiblesse":"⚡", "resistance":"🌟"},
    "jirenfull": {"nom":"Jiren (Full Power)", "serie":"Dragon Ball Super", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"https://i.imgur.com/z1ZKU2Y.jpg", "attaques":[{"nom":"Regard Perforant","emoji":"👁️","degats":89,"desc":"Fige d'un seul œil"},{"nom":"Onde de Choc","emoji":"💢","degats":98,"desc":"Repousse tout"},{"nom":"Puissance Absolue","emoji":"💥","degats":108,"desc":"Sans limite"}], "faiblesse":"⚡", "resistance":"🌟"},
    "jiren": {"nom":"Jiren", "serie":"Dragon Ball Super", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/z1ZKU2Y.jpg", "attaques":[{"nom":"Poing Silencieux","emoji":"👊","degats":72,"desc":"Frappe sans élan"},{"nom":"Barrière de Volonté","emoji":"🛡️","degats":80,"desc":"Mur invisible"},{"nom":"Rafale Éclair","emoji":"⚡","degats":87,"desc":"Salve fulgurante"}], "faiblesse":"⚡", "resistance":"🌟"},
    "broly": {"nom":"Broly (DBS)", "serie":"Dragon Ball Super", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/c0oACBA.jpg", "attaques":[{"nom":"Charge Berserk","emoji":"😤","degats":72,"desc":"Ruée incontrôlée"},{"nom":"Blaster Meteor","emoji":"☄️","degats":80,"desc":"Pluie d'énergie"},{"nom":"Rugissement","emoji":"🔊","degats":87,"desc":"Cri de guerre"}], "faiblesse":"⚡", "resistance":"🌟"},
    "gogeta": {"nom":"Gogeta (SSJ Blue)", "serie":"Dragon Ball Super", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/7rZvNsk.jpg", "attaques":[{"nom":"Stardust Breaker","emoji":"✨","degats":74,"desc":"Sphère purificatrice"},{"nom":"Big Bang Kamehameha","emoji":"🌊","degats":82,"desc":"Fusion des deux"},{"nom":"Impact Ultime","emoji":"💥","degats":88,"desc":"Coup final"}], "faiblesse":"⚡", "resistance":"🌟"},
    "vegito": {"nom":"Vegito (SSJ Blue)", "serie":"Dragon Ball Super", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/COP7cnj.jpg", "attaques":[{"nom":"Final Kamehameha","emoji":"🌊","degats":74,"desc":"Vague fusionnée"},{"nom":"Spirit Sword","emoji":"⚔️","degats":82,"desc":"Lame d'énergie"},{"nom":"Banshee Blast","emoji":"💫","degats":88,"desc":"Rafale guidée"}], "faiblesse":"⚡", "resistance":"🌟"},
    "vegetassj": {"nom":"Vegeta (SSJ)", "serie":"Dragon Ball Z", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/ld1LPss.jpg", "attaques":[{"nom":"Galick Gun","emoji":"💜","degats":70,"desc":"Rayon violet"},{"nom":"Big Bang Attack","emoji":"💥","degats":78,"desc":"Sphère explosive"},{"nom":"Final Flash","emoji":"✨","degats":88,"desc":"Charge dorée"}], "faiblesse":"⚡", "resistance":"🌟"},
    "gohanssj2": {"nom":"Gohan (SSJ2 vs Cell)", "serie":"Dragon Ball Z", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/FW9Uddq.jpg", "attaques":[{"nom":"Masenko","emoji":"💛","degats":70,"desc":"Rayon frontal"},{"nom":"Kamehameha Père-Fils","emoji":"🌊","degats":80,"desc":"Vague héritée"},{"nom":"Fureur du SSJ2","emoji":"⚡","degats":88,"desc":"Rage libérée"}], "faiblesse":"⚡", "resistance":"🌟"},
    "android21": {"nom":"Android 21", "serie":"Dragon Ball Z", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"", "attaques":[{"nom":"Rayon Absorbant","emoji":"🍬","degats":70,"desc":"Transforme en bonbon"},{"nom":"Forme Majin","emoji":"🍭","degats":78,"desc":"Éveil monstrueux"},{"nom":"Vague Destructrice","emoji":"💥","degats":86,"desc":"Souffle total"}], "faiblesse":"⚡", "resistance":"🌟"},
    "android17": {"nom":"Android 17", "serie":"Dragon Ball Z", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"", "attaques":[{"nom":"Barrière d'Énergie","emoji":"🛡️","degats":55,"desc":"Bouclier infini"},{"nom":"Rafale de Photons","emoji":"⚡","degats":63,"desc":"Tirs rapides"},{"nom":"Super Éclair","emoji":"💥","degats":70,"desc":"Décharge totale"}], "faiblesse":"⚡", "resistance":"🌟"},
    "android18": {"nom":"Android 18", "serie":"Dragon Ball Z", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"", "attaques":[{"nom":"Coup de Pied Éclair","emoji":"🦵","degats":55,"desc":"Frappe nette"},{"nom":"Rafale d'Énergie","emoji":"⚡","degats":62,"desc":"Salve continue"},{"nom":"Explosion Infinie","emoji":"💥","degats":70,"desc":"Énergie sans limite"}], "faiblesse":"⚡", "resistance":"🌟"},
    "cellparfait": {"nom":"Cell (Parfait)", "serie":"Dragon Ball Z", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/C0yiDwl.jpg", "attaques":[{"nom":"Kamehameha","emoji":"🌊","degats":58,"desc":"Copié de Goku"},{"nom":"Solar Kamehameha","emoji":"☀️","degats":65,"desc":"Version aveuglante"},{"nom":"Absorption","emoji":"🪱","degats":72,"desc":"Aspire sa cible"}], "faiblesse":"⚡", "resistance":"🌟"},
    "gohanadulte": {"nom":"Gohan (Adulte)", "serie":"Dragon Ball Z", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/FW9Uddq.jpg", "attaques":[{"nom":"Masenko","emoji":"💛","degats":55,"desc":"Rayon frontal"},{"nom":"Kamehameha","emoji":"🌊","degats":63,"desc":"Vague déferlante"},{"nom":"Potentiel Libéré","emoji":"✨","degats":70,"desc":"Éveil ultime"}], "faiblesse":"⚡", "resistance":"🌟"},
    "gotenks": {"nom":"Gotenks", "serie":"Dragon Ball Z", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/sENwCrn.jpg", "attaques":[{"nom":"Fantômes Kamikaze","emoji":"👻","degats":58,"desc":"Explosifs vivants"},{"nom":"Bouclier Galactique","emoji":"🌀","degats":64,"desc":"Sphère protectrice"},{"nom":"Volley-ball Céleste","emoji":"🏐","degats":71,"desc":"Smash cosmique"}], "faiblesse":"⚡", "resistance":"🌟"},
    "piccolomax": {"nom":"Piccolo (Grand Forme)", "serie":"Dragon Ball Z", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/V5eQN61.jpg", "attaques":[{"nom":"Makankosappo","emoji":"🌀","degats":58,"desc":"Rayon perforant"},{"nom":"Bras Extensibles","emoji":"💪","degats":63,"desc":"Allonge namek"},{"nom":"Explosion Démoniaque","emoji":"💥","degats":70,"desc":"Onde de choc"}], "faiblesse":"⚡", "resistance":"🌟"},
    "cooler": {"nom":"Cooler", "serie":"Dragon Ball Z", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/kTiv7z4.jpg", "attaques":[{"nom":"Supernova","emoji":"☄️","degats":60,"desc":"Boule solaire"},{"nom":"Rafale Mortelle","emoji":"💫","degats":66,"desc":"Salve glaciale"},{"nom":"Metal Cooler","emoji":"🤖","degats":72,"desc":"Forme mécanique"}], "faiblesse":"⚡", "resistance":"🌟"},
    "tenshinhan": {"nom":"Tenshinhan", "serie":"Dragon Ball Z", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/3YDRHe9.jpg", "attaques":[{"nom":"Dodonpa","emoji":"☝️","degats":42,"desc":"Rayon du doigt"},{"nom":"Kikoho","emoji":"🔺","degats":48,"desc":"Triangle mortel"},{"nom":"Multi-Formes","emoji":"👥","degats":54,"desc":"Quatre clones"}], "faiblesse":"⚡", "resistance":"🌟"},
    "piccolo": {"nom":"Piccolo", "serie":"Dragon Ball Z", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/V5eQN61.jpg", "attaques":[{"nom":"Makankosappo","emoji":"🌀","degats":44,"desc":"Rayon perforant"},{"nom":"Bras Extensibles","emoji":"💪","degats":48,"desc":"Allonge namek"},{"nom":"Explosion Démoniaque","emoji":"💥","degats":54,"desc":"Onde de choc"}], "faiblesse":"⚡", "resistance":"🌟"},
    "goten": {"nom":"Goten", "serie":"Dragon Ball Z", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/ChVkoHe.jpg", "attaques":[{"nom":"Kamehameha","emoji":"🌊","degats":40,"desc":"Vague enfantine"},{"nom":"Poing Super Saiyan","emoji":"👊","degats":46,"desc":"Frappe dorée"},{"nom":"Assaut Espiègle","emoji":"⚡","degats":52,"desc":"Rafale rapide"}], "faiblesse":"⚡", "resistance":"🌟"},
    "trunksenfant": {"nom":"Trunks (enfant)", "serie":"Dragon Ball Z", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/y49vSMv.jpg", "attaques":[{"nom":"Burning Attack","emoji":"🔥","degats":42,"desc":"Sphère brûlante"},{"nom":"Coup d'Épée","emoji":"⚔️","degats":48,"desc":"Lame du futur"},{"nom":"Rafale Dorée","emoji":"✨","degats":53,"desc":"Salve saiyan"}], "faiblesse":"⚡", "resistance":"🌟"},
    "masterroshi": {"nom":"Master Roshi", "serie":"Dragon Ball Z", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/M6bRwMB.jpg", "attaques":[{"nom":"Kamehameha","emoji":"🌊","degats":45,"desc":"L'originel"},{"nom":"Mafuba","emoji":"🏺","degats":50,"desc":"Scelle dans une urne"},{"nom":"Pleine Puissance","emoji":"💪","degats":55,"desc":"Muscles gonflés"}], "faiblesse":"⚡", "resistance":"🌟"},
    "zarbon": {"nom":"Zarbon", "serie":"Dragon Ball Z", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/iAiojTr.jpg", "attaques":[{"nom":"Coup Élégant","emoji":"💅","degats":40,"desc":"Frappe raffinée"},{"nom":"Forme Monstrueuse","emoji":"👹","degats":47,"desc":"Métamorphose"},{"nom":"Étreinte Brutale","emoji":"🤜","degats":53,"desc":"Broie l'adversaire"}], "faiblesse":"⚡", "resistance":"🌟"},
    "dodoria": {"nom":"Dodoria", "serie":"Dragon Ball Z", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/ZQBlxBN.jpg", "attaques":[{"nom":"Rayon Buccal","emoji":"😮","degats":40,"desc":"Tir à bout portant"},{"nom":"Charge Massive","emoji":"🐗","degats":46,"desc":"Bélier de chair"},{"nom":"Explosion Rose","emoji":"💗","degats":52,"desc":"Souffle corrosif"}], "faiblesse":"⚡", "resistance":"🌟"},
    "captainginyu": {"nom":"Captain Ginyu", "serie":"Dragon Ball Z", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/gHswpfY.jpg", "attaques":[{"nom":"Change Now!","emoji":"🔄","degats":44,"desc":"Échange de corps"},{"nom":"Milky Cannon","emoji":"🥛","degats":49,"desc":"Rayon laiteux"},{"nom":"Pose du Ginyu","emoji":"💃","degats":54,"desc":"Chorégraphie fatale"}], "faiblesse":"⚡", "resistance":"🌟"},
    "chiaotzu": {"nom":"Chiaotzu", "serie":"Dragon Ball Z", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/Ls6ZoNh.jpg", "attaques":[{"nom":"Dodonpa","emoji":"☝️","degats":26,"desc":"Rayon du doigt"},{"nom":"Télékinésie","emoji":"🧠","degats":32,"desc":"Immobilise"},{"nom":"Auto-Destruction","emoji":"💥","degats":38,"desc":"Sacrifice ultime"}], "faiblesse":"⚡", "resistance":"🌟"},
    "oolong": {"nom":"Oolong", "serie":"Dragon Ball Z", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/WQdxlJV.jpg", "attaques":[{"nom":"Transformation","emoji":"🐷","degats":24,"desc":"Change de forme"},{"nom":"Fuite Rapide","emoji":"💨","degats":30,"desc":"Détale en couinant"},{"nom":"Coup Bas","emoji":"👊","degats":35,"desc":"Frappe déloyale"}], "faiblesse":"⚡", "resistance":"🌟"},
    "celljr": {"nom":"Cell Jr", "serie":"Dragon Ball Z", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/rQZyE9r.jpg", "attaques":[{"nom":"Mini Kamehameha","emoji":"🌊","degats":28,"desc":"Version réduite"},{"nom":"Griffes Vives","emoji":"✂️","degats":33,"desc":"Lacère"},{"nom":"Rire Cruel","emoji":"😈","degats":38,"desc":"Déstabilise"}], "faiblesse":"⚡", "resistance":"🌟"},
    "pilaf": {"nom":"Pilaf", "serie":"Dragon Ball Z", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/ljm3Pcx.jpg", "attaques":[{"nom":"Robot Pilaf","emoji":"🤖","degats":25,"desc":"Machine de combat"},{"nom":"Plan Machiavélique","emoji":"📜","degats":30,"desc":"Piège tordu"},{"nom":"Rayon Laser","emoji":"🔦","degats":36,"desc":"Tir mécanique"}], "faiblesse":"⚡", "resistance":"🌟"},
    "guldo": {"nom":"Guldo", "serie":"Dragon Ball Z", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/AyyXKRH.jpg", "attaques":[{"nom":"Arrêt du Temps","emoji":"⏱️","degats":28,"desc":"Fige l'instant"},{"nom":"Télékinésie","emoji":"🧠","degats":33,"desc":"Soulève et projette"},{"nom":"Rocher Psychique","emoji":"🪨","degats":38,"desc":"Projectile mental"}], "faiblesse":"⚡", "resistance":"🌟"},
    "jeice": {"nom":"Jeice", "serie":"Dragon Ball Z", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/HXvx4HN.jpg", "attaques":[{"nom":"Crusher Ball","emoji":"🔴","degats":28,"desc":"Sphère écarlate"},{"nom":"Rafale Rouge","emoji":"💢","degats":33,"desc":"Tirs enchaînés"},{"nom":"Purple Comet","emoji":"☄️","degats":38,"desc":"Attaque en duo"}], "faiblesse":"⚡", "resistance":"🌟"},
    "burter": {"nom":"Burter", "serie":"Dragon Ball Z", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/PJCchbh.jpg", "attaques":[{"nom":"Vitesse Éclair","emoji":"⚡","degats":27,"desc":"Plus rapide que l'œil"},{"nom":"Blue Hurricane","emoji":"🌪️","degats":33,"desc":"Tornade bleue"},{"nom":"Coup Fulgurant","emoji":"💨","degats":38,"desc":"Frappe invisible"}], "faiblesse":"⚡", "resistance":"🌟"},
    "recoome": {"nom":"Recoome", "serie":"Dragon Ball Z", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/UIpkFSp.jpg", "attaques":[{"nom":"Recoome Boom","emoji":"💣","degats":29,"desc":"Coup de boule"},{"nom":"Recoome Kick","emoji":"🦵","degats":34,"desc":"Talon écrasant"},{"nom":"Eraser Gun","emoji":"🔫","degats":39,"desc":"Rayon buccal"}], "faiblesse":"⚡", "resistance":"🌟"},
    "raditz": {"nom":"Raditz", "serie":"Dragon Ball Z", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/6C1qiWd.jpg", "attaques":[{"nom":"Double Sunday","emoji":"✌️","degats":30,"desc":"Double rayon"},{"nom":"Saturday Crush","emoji":"💥","degats":35,"desc":"Sphère perforante"},{"nom":"Charge Saiyan","emoji":"🐒","degats":40,"desc":"Assaut brutal"}], "faiblesse":"⚡", "resistance":"🌟"},
    "nappa": {"nom":"Nappa", "serie":"Dragon Ball Z", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/4TBKP7u.jpg", "attaques":[{"nom":"Break Cannon","emoji":"💥","degats":30,"desc":"Explosion de zone"},{"nom":"Bomber DX","emoji":"💣","degats":35,"desc":"Frappe dévastatrice"},{"nom":"Colère Volcanique","emoji":"🌋","degats":40,"desc":"Rage saiyan"}], "faiblesse":"⚡", "resistance":"🌟"},
    "buumaigre": {"nom":"Buu Maigre", "serie":"Dragon Ball Z", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/klfd0MP.jpg", "attaques":[{"nom":"Rayon Transformateur","emoji":"🍬","degats":30,"desc":"Change en friandise"},{"nom":"Vapeur Mortelle","emoji":"☁️","degats":35,"desc":"Nuage toxique"},{"nom":"Régénération","emoji":"🩹","degats":40,"desc":"Se reforme"}], "faiblesse":"⚡", "resistance":"🌟"},
    "puar": {"nom":"Puar", "serie":"Dragon Ball Z", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/xoEbJHh.jpg", "attaques":[{"nom":"Transformation","emoji":"🐱","degats":24,"desc":"Prend une forme"},{"nom":"Diversion","emoji":"💨","degats":29,"desc":"Détourne l'attention"},{"nom":"Piqûre Surprise","emoji":"📌","degats":34,"desc":"Attaque en aiguille"}], "faiblesse":"⚡", "resistance":"🌟"},
    "babidi": {"nom":"Babidi", "serie":"Dragon Ball Z", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/TbVFfwD.jpg", "attaques":[{"nom":"Contrôle Mental","emoji":"🧠","degats":27,"desc":"Asservit sa cible"},{"nom":"Papapapa","emoji":"✨","degats":32,"desc":"Incantation"},{"nom":"Magie Noire","emoji":"🔮","degats":37,"desc":"Sort obscur"}], "faiblesse":"⚡", "resistance":"🌟"},
    "spopovitch": {"nom":"Spopovitch", "serie":"Dragon Ball Z", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/498OBCg.jpg", "attaques":[{"nom":"Prise Brutale","emoji":"🤼","degats":28,"desc":"Étranglement"},{"nom":"Coup de Tête","emoji":"💢","degats":33,"desc":"Choc frontal"},{"nom":"Régénération Majin","emoji":"🩸","degats":38,"desc":"Se relève toujours"}], "faiblesse":"⚡", "resistance":"🌟"},
    "mrpopo": {"nom":"Mr Popo", "serie":"Dragon Ball Z", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/rzPjawD.jpg", "attaques":[{"nom":"Magie de Kami","emoji":"🔮","degats":26,"desc":"Sort du gardien"},{"nom":"Tapis Volant","emoji":"🪄","degats":31,"desc":"Charge aérienne"},{"nom":"Entraînement Divin","emoji":"🧘","degats":36,"desc":"Technique ancestrale"}], "faiblesse":"⚡", "resistance":"🌟"},
    "yamu": {"nom":"Yamu", "serie":"Dragon Ball Z", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/lgxeTO7.jpg", "attaques":[{"nom":"Absorption d'Énergie","emoji":"🔋","degats":27,"desc":"Vide sa cible"},{"nom":"Lance Aspirante","emoji":"🔱","degats":32,"desc":"Perce et draine"},{"nom":"Frappe Majin","emoji":"💢","degats":37,"desc":"Coup possédé"}], "faiblesse":"⚡", "resistance":"🌟"},
    "videl": {"nom":"Videl", "serie":"Dragon Ball Z", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/TlSc4jR.jpg", "attaques":[{"nom":"Arts Martiaux","emoji":"🥋","degats":26,"desc":"Enchaînement précis"},{"nom":"Coup de Pied Sauté","emoji":"🦵","degats":31,"desc":"Frappe aérienne"},{"nom":"Vol","emoji":"🕊️","degats":36,"desc":"Assaut plongeant"}], "faiblesse":"⚡", "resistance":"🌟"},
    "chichi": {"nom":"Chi-Chi", "serie":"Dragon Ball Z", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/V49V1AJ.jpg", "attaques":[{"nom":"Poêle à Frire","emoji":"🍳","degats":25,"desc":"Arme de cuisine"},{"nom":"Cri Perçant","emoji":"📢","degats":30,"desc":"Assourdit"},{"nom":"Colère Maternelle","emoji":"💢","degats":36,"desc":"Fureur incontrôlable"}], "faiblesse":"⚡", "resistance":"🌟"},
    "bulma": {"nom":"Bulma", "serie":"Dragon Ball Z", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/CuRdkfj.jpg", "attaques":[{"nom":"Capsule Hoi-Poi","emoji":"💊","degats":24,"desc":"Déploie une machine"},{"nom":"Radar Dragon","emoji":"📡","degats":29,"desc":"Localise la faille"},{"nom":"Invention Géniale","emoji":"🔧","degats":34,"desc":"Gadget improvisé"}], "faiblesse":"⚡", "resistance":"🌟"},
    "mrSatan": {"nom":"Mr Satan", "serie":"Dragon Ball Z", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/gMzLZve.jpg", "attaques":[{"nom":"Dynamite Kick","emoji":"🦵","degats":26,"desc":"Coup de pied signature"},{"nom":"Satan Punch","emoji":"🥊","degats":31,"desc":"Direct du champion"},{"nom":"Bluff Héroïque","emoji":"🎤","degats":36,"desc":"Impressionne la foule"}], "faiblesse":"⚡", "resistance":"🌟"},
    "gildarts": {"nom":"Gildarts Clive", "serie":"Fairy Tail", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/U8so0Qd.jpg", "attaques":[{"nom":"Crash","emoji":"💥","degats":72,"desc":"Désintègre la matière"},{"nom":"Poing du Crash","emoji":"👊","degats":80,"desc":"Réduit en morceaux"},{"nom":"Disassembly","emoji":"🧩","degats":88,"desc":"Découpe tout"}], "faiblesse":"⚡", "resistance":"🌟"},
    "jellal": {"nom":"Jellal Fernandes", "serie":"Fairy Tail", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/dVR705B.jpg", "attaques":[{"nom":"Meteor","emoji":"☄️","degats":72,"desc":"Vitesse céleste"},{"nom":"Grand Chariot","emoji":"✨","degats":80,"desc":"Sept étoiles"},{"nom":"Sema","emoji":"🌠","degats":88,"desc":"Météore vengeur"}], "faiblesse":"⚡", "resistance":"🌟"},
    "juvia": {"nom":"Juvia Lockser", "serie":"Fairy Tail", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/6jjacAq.jpg", "attaques":[{"nom":"Water Slicer","emoji":"💧","degats":42,"desc":"Lames liquides"},{"nom":"Water Nebula","emoji":"🌊","degats":48,"desc":"Double torrent"},{"nom":"Water Lock","emoji":"🫧","degats":54,"desc":"Prison aquatique"}], "faiblesse":"⚡", "resistance":"🌟"},
    "gajeel": {"nom":"Gajeel Redfox", "serie":"Fairy Tail", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/Bij0me3.jpg", "attaques":[{"nom":"Iron Dragon's Roar","emoji":"🐉","degats":43,"desc":"Rugissement de fer"},{"nom":"Iron Dragon's Club","emoji":"🔩","degats":49,"desc":"Poing allongé"},{"nom":"Iron Shadow","emoji":"⚫","degats":55,"desc":"Fer et ombre mêlés"}], "faiblesse":"⚡", "resistance":"🌟"},
    "wendy": {"nom":"Wendy Marvell", "serie":"Fairy Tail", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/lCguz5s.jpg", "attaques":[{"nom":"Sky Dragon's Roar","emoji":"🌪️","degats":41,"desc":"Rugissement du ciel"},{"nom":"Vernier","emoji":"💨","degats":47,"desc":"Accélère les alliés"},{"nom":"Soin du Ciel","emoji":"💚","degats":53,"desc":"Guérit les blessures"}], "faiblesse":"⚡", "resistance":"🌟"},
    "elfman": {"nom":"Elfman Strauss", "serie":"Fairy Tail", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/9ZPNM8f.jpg", "attaques":[{"nom":"Beast Arm","emoji":"💪","degats":28,"desc":"Bras de bête"},{"nom":"Beast Soul","emoji":"🐗","degats":33,"desc":"Transformation totale"},{"nom":"Fierté de l'Homme","emoji":"♂️","degats":38,"desc":"Un vrai homme protège"}], "faiblesse":"⚡", "resistance":"🌟"},
    "jet": {"nom":"Jet", "serie":"Fairy Tail", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"", "attaques":[{"nom":"High Speed","emoji":"💨","degats":26,"desc":"Course fulgurante"},{"nom":"Falcon Rush","emoji":"🦅","degats":31,"desc":"Charge en piqué"},{"nom":"Esquive Éclair","emoji":"⚡","degats":36,"desc":"Insaisissable"}], "faiblesse":"⚡", "resistance":"🌟"},
    "droy": {"nom":"Droy", "serie":"Fairy Tail", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/RCiD6JL.jpg", "attaques":[{"nom":"Plant Magic","emoji":"🌱","degats":25,"desc":"Graines vivantes"},{"nom":"Knuckle Plant","emoji":"🌿","degats":30,"desc":"Poing végétal"},{"nom":"Vigne Étrangleuse","emoji":"🍃","degats":35,"desc":"Immobilise"}], "faiblesse":"⚡", "resistance":"🌟"},
    "loke": {"nom":"Loke", "serie":"Fairy Tail", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"", "attaques":[{"nom":"Regulus Impact","emoji":"🦁","degats":28,"desc":"Poing de lumière"},{"nom":"Lion Brilliance","emoji":"☀️","degats":33,"desc":"Éclat aveuglant"},{"nom":"Esprit du Lion","emoji":"✨","degats":38,"desc":"Porte de Leo"}], "faiblesse":"⚡", "resistance":"🌟"},
    "shinfull": {"nom":"Shinra (Adolla Burst)", "serie":"Fire Force", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"https://i.imgur.com/EHSOtr3.jpg", "attaques":[{"nom":"Adolla Burst","emoji":"🔥","degats":90,"desc":"Flamme originelle"},{"nom":"Rapid Blast","emoji":"💨","degats":99,"desc":"Vitesse de la lumière"},{"nom":"Coup de Pied du Diable","emoji":"😈","degats":108,"desc":"Empreintes ardentes"}], "faiblesse":"⚡", "resistance":"🌟"},
    "shinra": {"nom":"Shinra Kusakabe", "serie":"Fire Force", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/EHSOtr3.jpg", "attaques":[{"nom":"Coup de Pied du Diable","emoji":"😈","degats":58,"desc":"Sa signature"},{"nom":"Rapid Blast","emoji":"💨","degats":65,"desc":"Propulsion des pieds"},{"nom":"Sourire du Démon","emoji":"😁","degats":72,"desc":"Terrifie malgré lui"}], "faiblesse":"⚡", "resistance":"🌟"},
    "burns": {"nom":"Leonard Burns", "serie":"Fire Force", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"", "attaques":[{"nom":"Poing Solaire","emoji":"☀️","degats":58,"desc":"Frappe incandescente"},{"nom":"Bouclier de Flammes","emoji":"🛡️","degats":65,"desc":"Mur ardent"},{"nom":"Œil de Feu","emoji":"👁️","degats":72,"desc":"Regard du capitaine"}], "faiblesse":"⚡", "resistance":"🌟"},
    "benimaru": {"nom":"Benimaru Shinmon", "serie":"Fire Force", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/WQdhN22.jpg", "attaques":[{"nom":"Matsukaze","emoji":"🌪️","degats":59,"desc":"Vitesse foudroyante"},{"nom":"Flamme et Chaleur","emoji":"🔥","degats":66,"desc":"Deux pouvoirs mêlés"},{"nom":"Poing d'Asakusa","emoji":"👊","degats":72,"desc":"Frappe du roi"}], "faiblesse":"⚡", "resistance":"🌟"},
    "arthurf": {"nom":"Arthur Boyle", "serie":"Fire Force", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/zJikG6Q.jpg", "attaques":[{"nom":"Excalibur","emoji":"⚔️","degats":43,"desc":"Lame de plasma"},{"nom":"Chevalier Roi","emoji":"👑","degats":49,"desc":"Plus il y croit, plus il frappe"},{"nom":"Charge du Roi","emoji":"🐎","degats":55,"desc":"Assaut héroïque"}], "faiblesse":"⚡", "resistance":"🌟"},
    "tamaki": {"nom":"Tamaki Kotatsu", "serie":"Fire Force", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/RHyuh47.jpg", "attaques":[{"nom":"Nekomata","emoji":"🐱","degats":27,"desc":"Flammes félines"},{"nom":"Griffes Ardentes","emoji":"🔥","degats":32,"desc":"Lacération brûlante"},{"nom":"Lucky Lecher","emoji":"💫","degats":37,"desc":"Malchance chronique"}], "faiblesse":"⚡", "resistance":"🌟"},
    "iris": {"nom":"Iris", "serie":"Fire Force", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/Q0YdrNY.jpg", "attaques":[{"nom":"Prière","emoji":"🙏","degats":25,"desc":"Soutient les alliés"},{"nom":"Lumière Sacrée","emoji":"✨","degats":30,"desc":"Repousse les flammes"},{"nom":"Rosaire","emoji":"📿","degats":35,"desc":"Bénédiction protectrice"}], "faiblesse":"⚡", "resistance":"🌟"},
    "soma_r": {"nom":"Soma Yukihira", "serie":"Food Wars", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/OWRs0x0.jpg", "attaques":[{"nom":"Plat Improvisé","emoji":"🍳","degats":43,"desc":"Recette de comptoir"},{"nom":"Assaisonnement Choc","emoji":"🌶️","degats":49,"desc":"Réveille les papilles"},{"nom":"Sourire Provocateur","emoji":"😏","degats":55,"desc":"Déstabilise l'adversaire"}], "faiblesse":"⚡", "resistance":"🌟"},
    "alice_r": {"nom":"Alice Nakiri", "serie":"Food Wars", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/mUnqSa3.jpg", "attaques":[{"nom":"Cuisine Moléculaire","emoji":"🧪","degats":42,"desc":"Science culinaire"},{"nom":"Azote Liquide","emoji":"❄️","degats":48,"desc":"Choc thermique"},{"nom":"Présentation Parfaite","emoji":"✨","degats":54,"desc":"Séduit le jury"}], "faiblesse":"⚡", "resistance":"🌟"},
    "sen_r": {"nom":"Erina Nakiri", "serie":"Food Wars", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/wZ8mpoH.jpg", "attaques":[{"nom":"Palais de Dieu","emoji":"👅","degats":44,"desc":"Goût absolu"},{"nom":"Critique Impitoyable","emoji":"📝","degats":50,"desc":"Détruit moralement"},{"nom":"Élégance Nakiri","emoji":"👑","degats":55,"desc":"Perfection technique"}], "faiblesse":"⚡", "resistance":"🌟"},
    "mimasaka": {"nom":"Subaru Mimasaka", "serie":"Food Wars", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/KsiSZog.jpg", "attaques":[{"nom":"Traçage","emoji":"🔍","degats":42,"desc":"Copie parfaitement"},{"nom":"Plat Volé","emoji":"🍽️","degats":48,"desc":"Reproduit en mieux"},{"nom":"Analyse Totale","emoji":"📊","degats":54,"desc":"Connaît chaque geste"}], "faiblesse":"⚡", "resistance":"🌟"},
    "soma_com": {"nom":"Soma Yukihira (debut)", "serie":"Food Wars", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/OWRs0x0.jpg", "attaques":[{"nom":"Plat du Jour","emoji":"🍜","degats":26,"desc":"Cuisine familiale"},{"nom":"Ingrédient Surprise","emoji":"🐙","degats":31,"desc":"Recette douteuse"},{"nom":"Persévérance","emoji":"💪","degats":36,"desc":"N'abandonne jamais"}], "faiblesse":"⚡", "resistance":"🌟"},
    "ryou_com": {"nom":"Ryou Kurokiba", "serie":"Food Wars", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/cu3sS8W.jpg", "attaques":[{"nom":"Mode Berserk","emoji":"🩸","degats":29,"desc":"Change de personnalité"},{"nom":"Couteau de Mer","emoji":"🔪","degats":34,"desc":"Spécialiste des fruits de mer"},{"nom":"Bandana Retiré","emoji":"😤","degats":39,"desc":"Libère sa rage"}], "faiblesse":"⚡", "resistance":"🌟"},
    "gachiaka": {"nom":"Rudo", "serie":"Gachiakuta", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/OD9tpq7.jpg", "attaques":[{"nom":"Gant Vital","emoji":"🧤","degats":43,"desc":"Objet chargé d'affection"},{"nom":"Ordure Vivante","emoji":"🗑️","degats":49,"desc":"Arme improvisée"},{"nom":"Rage des Bas-Fonds","emoji":"💢","degats":55,"desc":"Colère des exclus"}], "faiblesse":"⚡", "resistance":"🌟"},
    "tadashi": {"nom":"Tadashi Kariya", "serie":"Gachiakuta", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"", "attaques":[{"nom":"Objet Sentimental","emoji":"🎒","degats":42,"desc":"Puissance liée aux souvenirs"},{"nom":"Coup Nettoyeur","emoji":"🧹","degats":48,"desc":"Frappe des égouts"},{"nom":"Solidarité","emoji":"🤝","degats":54,"desc":"Se bat pour les siens"}], "faiblesse":"⚡", "resistance":"🌟"},
    "hinata_hq": {"nom":"Shoyo Hinata", "serie":"Haikyuu", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"", "attaques":[{"nom":"Attaque Éclair","emoji":"⚡","degats":43,"desc":"Frappe invisible"},{"nom":"Saut Prodigieux","emoji":"🦘","degats":49,"desc":"Détente surhumaine"},{"nom":"Le Petit Géant","emoji":"🏐","degats":55,"desc":"Domine malgré sa taille"}], "faiblesse":"⚡", "resistance":"🌟"},
    "kageyama": {"nom":"Tobio Kageyama", "serie":"Haikyuu", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"", "attaques":[{"nom":"Passe de Génie","emoji":"🎯","degats":43,"desc":"Précision millimétrée"},{"nom":"Service Sauté","emoji":"🏐","degats":49,"desc":"Ace redoutable"},{"nom":"Roi du Terrain","emoji":"👑","degats":55,"desc":"Dirige toute l'équipe"}], "faiblesse":"⚡", "resistance":"🌟"},
    "gabuep": {"nom":"Gabimaru (Ninja)", "serie":"Hell's Paradise", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/n2oz8Dn.jpg", "attaques":[{"nom":"Ninpo Flamme","emoji":"🔥","degats":58,"desc":"Art ninja du feu"},{"nom":"Vitesse d'Iwagakure","emoji":"💨","degats":65,"desc":"Le plus fort du village"},{"nom":"Amour pour sa Femme","emoji":"💗","degats":72,"desc":"Sa vraie force"}], "faiblesse":"⚡", "resistance":"🌟"},
    "nanatsu": {"nom":"Nanatsu Tokushima", "serie":"Hell's Paradise", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"", "attaques":[{"nom":"Sabre Yamada Asaemon","emoji":"⚔️","degats":43,"desc":"École du bourreau"},{"nom":"Décapitation","emoji":"🗡️","degats":49,"desc":"Coupe nette"},{"nom":"Tan","emoji":"🌿","degats":55,"desc":"Maîtrise le flux"}], "faiblesse":"⚡", "resistance":"🌟"},
    "gabimaru": {"nom":"Gabimaru", "serie":"Hell's Paradise", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/n2oz8Dn.jpg", "attaques":[{"nom":"Ninpo Flamme","emoji":"🔥","degats":43,"desc":"Souffle enflammé"},{"nom":"Poing Ninja","emoji":"👊","degats":49,"desc":"Frappe silencieuse"},{"nom":"Régénération","emoji":"🩹","degats":55,"desc":"Corps entraîné à survivre"}], "faiblesse":"⚡", "resistance":"🌟"},
    "sagiri": {"nom":"Sagiri Yamada", "serie":"Hell's Paradise", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/hnOh7ju.jpg", "attaques":[{"nom":"Sabre du Bourreau","emoji":"⚔️","degats":43,"desc":"Lame d'exécution"},{"nom":"Kekka","emoji":"💠","degats":49,"desc":"Perception du flux"},{"nom":"Détermination","emoji":"🎀","degats":55,"desc":"Ne détourne jamais le regard"}], "faiblesse":"⚡", "resistance":"🌟"},
    "aluepic": {"nom":"Alucard (Young)", "serie":"Hellsing", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/EoRtG4W.jpg", "attaques":[{"nom":"Jackal","emoji":"🔫","degats":58,"desc":"Pistolet anti-démon"},{"nom":"Chiens des Ténèbres","emoji":"🐕","degats":65,"desc":"Meute d'ombres"},{"nom":"Régénération Vampirique","emoji":"🩸","degats":72,"desc":"Impossible à tuer"}], "faiblesse":"⚡", "resistance":"🌟"},
    "gonadult": {"nom":"Gon (Adulte)", "serie":"HunterxHunter", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"https://i.imgur.com/JEAkcm9.jpg", "attaques":[{"nom":"Jajanken Pierre","emoji":"✊","degats":90,"desc":"Toute sa vie en un coup"},{"nom":"Rage Absolue","emoji":"😡","degats":99,"desc":"Sacrifie son avenir"},{"nom":"Poing du Serment","emoji":"💥","degats":108,"desc":"Frappe irréversible"}], "faiblesse":"⚡", "resistance":"🌟"},
    "meruemfull": {"nom":"Meruem (Full Power)", "serie":"HunterxHunter", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"https://i.imgur.com/ajOXRt1.jpg", "attaques":[{"nom":"Aura Royale","emoji":"👑","degats":91,"desc":"Écrase par la présence"},{"nom":"Queue Perforante","emoji":"🐜","degats":100,"desc":"Transperce tout"},{"nom":"Rose Empoisonnée","emoji":"☠️","degats":109,"desc":"Contamination fatale"}], "faiblesse":"⚡", "resistance":"🌟"},
    "chrollo": {"nom":"Chrollo Lucilfer", "serie":"HunterxHunter", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/oSuczS8.jpg", "attaques":[{"nom":"Skill Hunter","emoji":"📖","degats":72,"desc":"Vole les capacités"},{"nom":"Bandit's Secret","emoji":"🖐️","degats":80,"desc":"Livre des pouvoirs"},{"nom":"Black Voice","emoji":"📿","degats":88,"desc":"Contrôle par l'antenne"}], "faiblesse":"⚡", "resistance":"🌟"},
    "neferpitou": {"nom":"Neferpitou", "serie":"HunterxHunter", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/X9f9pyY.jpg", "attaques":[{"nom":"Terpsichora","emoji":"🎎","degats":72,"desc":"Marionnette de guerre"},{"nom":"Griffes du Chat","emoji":"🐾","degats":80,"desc":"Lacération fulgurante"},{"nom":"Doctor Blythe","emoji":"💉","degats":88,"desc":"Soin d'urgence"}], "faiblesse":"⚡", "resistance":"🌟"},
    "silva": {"nom":"Silva Zoldyck", "serie":"HunterxHunter", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/1HUdAyr.jpg", "attaques":[{"nom":"Poing du Zoldyck","emoji":"👊","degats":72,"desc":"Frappe d'assassin"},{"nom":"Sphère de Rage","emoji":"🔮","degats":80,"desc":"Boule d'aura"},{"nom":"Arrachage de Cœur","emoji":"🫀","degats":88,"desc":"Technique familiale"}], "faiblesse":"⚡", "resistance":"🌟"},
    "zeno_z": {"nom":"Zeno Zoldyck", "serie":"HunterxHunter", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/OOnUGGv.jpg", "attaques":[{"nom":"Dragon Dive","emoji":"🐉","degats":72,"desc":"Pluie de dragons"},{"nom":"Dragon Head","emoji":"🐲","degats":80,"desc":"Tête d'aura"},{"nom":"Sagesse du Patriarche","emoji":"👴","degats":88,"desc":"Des décennies d'expérience"}], "faiblesse":"⚡", "resistance":"🌟"},
    "leorio": {"nom":"Leorio Paradinight", "serie":"HunterxHunter", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/ZeRU0Pg.jpg", "attaques":[{"nom":"Poing Médical","emoji":"👊","degats":42,"desc":"Frappe à distance"},{"nom":"Mallette","emoji":"💼","degats":48,"desc":"Coup surprise"},{"nom":"Serment du Médecin","emoji":"🩺","degats":54,"desc":"Se bat pour soigner"}], "faiblesse":"⚡", "resistance":"🌟"},
    "illumi": {"nom":"Illumi Zoldyck", "serie":"HunterxHunter", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/NeFo0aX.jpg", "attaques":[{"nom":"Aiguilles","emoji":"📍","degats":44,"desc":"Contrôle par le crâne"},{"nom":"Needle People","emoji":"🎎","degats":50,"desc":"Marionnettes humaines"},{"nom":"Regard Vide","emoji":"👁️","degats":55,"desc":"Terrifie sans effort"}], "faiblesse":"⚡", "resistance":"🌟"},
    "tonpa": {"nom":"Tonpa", "serie":"HunterxHunter", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/P3fsw0E.jpg", "attaques":[{"nom":"Jus Piégé","emoji":"🥤","degats":24,"desc":"Boisson laxative"},{"nom":"Sabotage","emoji":"😈","degats":29,"desc":"Piège les novices"},{"nom":"Vétéran du 35e","emoji":"📋","degats":34,"desc":"Connaît tous les tours"}], "faiblesse":"⚡", "resistance":"🌟"},
    "pokkle": {"nom":"Pokkle", "serie":"HunterxHunter", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/e6jBMaX.jpg", "attaques":[{"nom":"Tir de Nen","emoji":"🏹","degats":26,"desc":"Flèche d'aura"},{"nom":"Volée Rapide","emoji":"🎯","degats":31,"desc":"Trois flèches"},{"nom":"Concentration","emoji":"🧘","degats":36,"desc":"Vise le point faible"}], "faiblesse":"⚡", "resistance":"🌟"},
    "dioworld": {"nom":"DIO (The World)", "serie":"JoJo", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"", "attaques":[{"nom":"Za Warudo","emoji":"⏱️","degats":90,"desc":"Arrête le temps"},{"nom":"Muda Muda Muda","emoji":"👊","degats":99,"desc":"Déluge de poings"},{"nom":"Rouleau Compresseur","emoji":"🚜","degats":108,"desc":"Écrase dans le temps figé"}], "faiblesse":"⚡", "resistance":"🌟"},
    "giotagold": {"nom":"Giorno (Gold Experience Requiem)", "serie":"JoJo", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"", "attaques":[{"nom":"Retour à Zéro","emoji":"🐞","degats":92,"desc":"Annule les actions"},{"nom":"Muda Rush","emoji":"✨","degats":100,"desc":"Poings de la vérité"},{"nom":"Vie Éternelle","emoji":"🌱","degats":110,"desc":"Nul ne peut l'atteindre"}], "faiblesse":"⚡", "resistance":"🌟"},
    "diavolo": {"nom":"Diavolo (King Crimson)", "serie":"JoJo", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"https://i.imgur.com/FNa1SzP.jpg", "attaques":[{"nom":"Effacement du Temps","emoji":"🩸","degats":90,"desc":"Supprime dix secondes"},{"nom":"Épilogue","emoji":"🔮","degats":99,"desc":"Voit le futur proche"},{"nom":"Poing Imparable","emoji":"👊","degats":107,"desc":"Frappe déjà arrivée"}], "faiblesse":"⚡", "resistance":"🌟"},
    "pucci": {"nom":"Enrico Pucci (Made in Heaven)", "serie":"JoJo", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"https://i.imgur.com/owvBCPl.jpg", "attaques":[{"nom":"Made in Heaven","emoji":"🕰️","degats":91,"desc":"Accélère le temps"},{"nom":"Gravité Nouvelle","emoji":"🌍","degats":99,"desc":"Le monde recommence"},{"nom":"C-Moon","emoji":"🌙","degats":108,"desc":"Inverse la matière"}], "faiblesse":"⚡", "resistance":"🌟"},
    "dio_ep": {"nom":"DIO (debut)", "serie":"JoJo", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"", "attaques":[{"nom":"Vampirisme","emoji":"🧛","degats":58,"desc":"Draine le sang"},{"nom":"Space Ripper","emoji":"👁️","degats":65,"desc":"Rayon oculaire"},{"nom":"Souffle Glacial","emoji":"❄️","degats":72,"desc":"Gèle au contact"}], "faiblesse":"⚡", "resistance":"🌟"},
    "josefep": {"nom":"Joseph Joestar (mature)", "serie":"JoJo", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/8PlNFLr.jpg", "attaques":[{"nom":"Hermit Purple","emoji":"🍇","degats":58,"desc":"Vignes spirituelles"},{"nom":"Ondes du Hamon","emoji":"💛","degats":65,"desc":"Énergie solaire"},{"nom":"Stratagème","emoji":"🧠","degats":72,"desc":"Toujours un coup d'avance"}], "faiblesse":"⚡", "resistance":"🌟"},
    "joseph": {"nom":"Joseph Joestar", "serie":"JoJo", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/8PlNFLr.jpg", "attaques":[{"nom":"Ondes de Hamon","emoji":"💛","degats":42,"desc":"Énergie du soleil"},{"nom":"Clacker Volley","emoji":"🪀","degats":48,"desc":"Boules enchaînées"},{"nom":"Bluff Légendaire","emoji":"🎭","degats":54,"desc":"Ta prochaine réplique sera…"}], "faiblesse":"⚡", "resistance":"🌟"},
    "caesar": {"nom":"Caesar Zeppeli", "serie":"JoJo", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/72ILubC.jpg", "attaques":[{"nom":"Bulles de Hamon","emoji":"🫧","degats":42,"desc":"Sphères tranchantes"},{"nom":"Bubble Cutter","emoji":"✂️","degats":48,"desc":"Lames flottantes"},{"nom":"Barrière de Bulles","emoji":"🛡️","degats":54,"desc":"Protection dorée"}], "faiblesse":"⚡", "resistance":"🌟"},
    "okuyasu": {"nom":"Okuyasu Nijimura", "serie":"JoJo", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"", "attaques":[{"nom":"The Hand","emoji":"✋","degats":42,"desc":"Efface l'espace"},{"nom":"Aspiration","emoji":"🌀","degats":48,"desc":"Attire l'ennemi"},{"nom":"Griffure du Vide","emoji":"💢","degats":54,"desc":"Supprime la matière"}], "faiblesse":"⚡", "resistance":"🌟"},
    "joske": {"nom":"Josuke Higashikata", "serie":"JoJo", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/EPb3V6Q.jpg", "attaques":[{"nom":"Crazy Diamond","emoji":"💎","degats":44,"desc":"Répare toute chose"},{"nom":"Dora Rush","emoji":"👊","degats":50,"desc":"Rafale de poings"},{"nom":"Restauration","emoji":"🩹","degats":55,"desc":"Soigne instantanément"}], "faiblesse":"⚡", "resistance":"🌟"},
    "roji": {"nom":"Rohan Kishibe", "serie":"JoJo", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/i5KeD6y.jpg", "attaques":[{"nom":"Heaven's Door","emoji":"📖","degats":42,"desc":"Transforme en livre"},{"nom":"Ordre Écrit","emoji":"✍️","degats":48,"desc":"Impose un comportement"},{"nom":"Lecture d'Âme","emoji":"👁️","degats":54,"desc":"Connaît tout de sa cible"}], "faiblesse":"⚡", "resistance":"🌟"},
    "gyro": {"nom":"Gyro Zeppeli", "serie":"JoJo", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/8uaa3YP.jpg", "attaques":[{"nom":"Spin","emoji":"🌀","degats":44,"desc":"Rotation infinie"},{"nom":"Ball Breaker","emoji":"⚪","degats":50,"desc":"Sphère tournoyante"},{"nom":"Golden Rectangle","emoji":"📐","degats":55,"desc":"Trajectoire parfaite"}], "faiblesse":"⚡", "resistance":"🌟"},
    "speedwagon": {"nom":"Speedwagon", "serie":"JoJo", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/MNQUd3I.jpg", "attaques":[{"nom":"Coup de Chapeau","emoji":"🎩","degats":25,"desc":"Lames dissimulées"},{"nom":"Loyauté","emoji":"🤝","degats":30,"desc":"Défend ses amis"},{"nom":"Fondation","emoji":"🏛️","degats":35,"desc":"Ressources illimitées"}], "faiblesse":"⚡", "resistance":"🌟"},
    "polnareff": {"nom":"Polnareff", "serie":"JoJo", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/KD7QyWH.jpg", "attaques":[{"nom":"Silver Chariot","emoji":"⚔️","degats":29,"desc":"Escrime fulgurante"},{"nom":"Estoc Multiple","emoji":"🗡️","degats":34,"desc":"Mille coups d'épée"},{"nom":"Armure Retirée","emoji":"💨","degats":39,"desc":"Vitesse maximale"}], "faiblesse":"⚡", "resistance":"🌟"},
    "avdol": {"nom":"Muhammad Avdol", "serie":"JoJo", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/DfX89ry.jpg", "attaques":[{"nom":"Magician's Red","emoji":"🔥","degats":29,"desc":"Flammes vivantes"},{"nom":"Crossfire Hurricane","emoji":"🦅","degats":34,"desc":"Ankh enflammé"},{"nom":"Mur de Feu","emoji":"🧱","degats":39,"desc":"Barrière ardente"}], "faiblesse":"⚡", "resistance":"🌟"},
    "koichi": {"nom":"Koichi Hirose", "serie":"JoJo", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/D8Aadew.jpg", "attaques":[{"nom":"Echoes Act 1","emoji":"🥚","degats":26,"desc":"Sons matérialisés"},{"nom":"Echoes Act 2","emoji":"🔊","degats":31,"desc":"Les mots deviennent réels"},{"nom":"Act 3 Freeze","emoji":"⬇️","degats":37,"desc":"Alourdit sa cible"}], "faiblesse":"⚡", "resistance":"🌟"},
    "giorno_com": {"nom":"Giorno (debut)", "serie":"JoJo", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"", "attaques":[{"nom":"Gold Experience","emoji":"🐞","degats":27,"desc":"Donne la vie"},{"nom":"Coup de Poing Vital","emoji":"👊","degats":32,"desc":"Amplifie les sens"},{"nom":"Plante Guérisseuse","emoji":"🌱","degats":37,"desc":"Régénère les blessures"}], "faiblesse":"⚡", "resistance":"🌟"},
    "jonathan": {"nom":"Jonathan Joestar", "serie":"JoJo", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/Tkv1a3e.jpg", "attaques":[{"nom":"Overdrive","emoji":"💛","degats":28,"desc":"Hamon du soleil"},{"nom":"Scarlet Overdrive","emoji":"🔥","degats":33,"desc":"Hamon enflammé"},{"nom":"Noblesse","emoji":"🎩","degats":38,"desc":"Force du gentleman"}], "faiblesse":"⚡", "resistance":"🌟"},
    "sukunafull": {"nom":"Sukuna (Full Power)", "serie":"Jujutsu Kaisen", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"", "attaques":[{"nom":"Dismantle","emoji":"🔪","degats":90,"desc":"Découpe à distance"},{"nom":"Cleave","emoji":"⚔️","degats":99,"desc":"Tranche selon la résistance"},{"nom":"Malevolent Shrine","emoji":"⛩️","degats":108,"desc":"Sanctuaire de mort"}], "faiblesse":"⚡", "resistance":"🌟"},
    "gojolimitless": {"nom":"Gojo (Six Eyes + Limitless)", "serie":"Jujutsu Kaisen", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"", "attaques":[{"nom":"Bleu","emoji":"🔵","degats":90,"desc":"Attire par le vide"},{"nom":"Rouge","emoji":"🔴","degats":99,"desc":"Repousse violemment"},{"nom":"Violet","emoji":"🟣","degats":108,"desc":"Fusion des deux"}], "faiblesse":"⚡", "resistance":"🌟"},
    "satoru_m": {"nom":"Gojo Satoru (Prison Realm Freed)", "serie":"Jujutsu Kaisen", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"", "attaques":[{"nom":"Infinity","emoji":"♾️","degats":91,"desc":"Rien ne l'atteint"},{"nom":"Unlimited Void","emoji":"🌌","degats":100,"desc":"Submerge d'informations"},{"nom":"Six Eyes","emoji":"👁️","degats":109,"desc":"Voit tout, sans effort"}], "faiblesse":"⚡", "resistance":"🌟"},
    "yuta": {"nom":"Yuta Okkotsu", "serie":"Jujutsu Kaisen", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/iVcKXD4.jpg", "attaques":[{"nom":"Rika","emoji":"👻","degats":72,"desc":"Reine des malédictions"},{"nom":"Copie","emoji":"📋","degats":80,"desc":"Reproduit les techniques"},{"nom":"Pure Love","emoji":"💕","degats":88,"desc":"Amour devenu malédiction"}], "faiblesse":"⚡", "resistance":"🌟"},
    "kashimo": {"nom":"Hajime Kashimo", "serie":"Jujutsu Kaisen", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"", "attaques":[{"nom":"Mythical Beast Amber","emoji":"⚡","degats":72,"desc":"Foudre incarnée"},{"nom":"Décharge Céleste","emoji":"🌩️","degats":80,"desc":"Éclair perforant"},{"nom":"Genju Kohaku","emoji":"🐉","degats":88,"desc":"Bête mythique"}], "faiblesse":"⚡", "resistance":"🌟"},
    "choso": {"nom":"Choso", "serie":"Jujutsu Kaisen", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/HBNSQtw.jpg", "attaques":[{"nom":"Blood Manipulation","emoji":"🩸","degats":72,"desc":"Contrôle son sang"},{"nom":"Piercing Blood","emoji":"🎯","degats":80,"desc":"Jet perforant"},{"nom":"Flowing Red Scale","emoji":"♨️","degats":88,"desc":"Amplifie le flux"}], "faiblesse":"⚡", "resistance":"🌟"},
    "yusufep": {"nom":"Yuji Itadori (Black Flash)", "serie":"Jujutsu Kaisen", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/wxIT2y4.jpg", "attaques":[{"nom":"Black Flash","emoji":"⚫","degats":58,"desc":"Impact parfait"},{"nom":"Divergent Fist","emoji":"👊","degats":65,"desc":"Double impact"},{"nom":"Manji Kick","emoji":"🦵","degats":72,"desc":"Coup de pied ascendant"}], "faiblesse":"⚡", "resistance":"🌟"},
    "hakari": {"nom":"Kinji Hakari", "serie":"Jujutsu Kaisen", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/EWUa6kE.jpg", "attaques":[{"nom":"Jackpot","emoji":"🎰","degats":44,"desc":"Machine à sous mortelle"},{"nom":"Private Pure Love Train","emoji":"🚃","degats":50,"desc":"Extension du territoire"},{"nom":"Régénération Infinie","emoji":"♾️","degats":55,"desc":"Ne meurt plus pendant le jackpot"}], "faiblesse":"⚡", "resistance":"🌟"},
    "higuruma": {"nom":"Hiromi Higuruma", "serie":"Jujutsu Kaisen", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/bzmXdQf.jpg", "attaques":[{"nom":"Judgeman","emoji":"⚖️","degats":43,"desc":"Tribunal spirituel"},{"nom":"Marteau du Juge","emoji":"🔨","degats":49,"desc":"Sentence exécutoire"},{"nom":"Peine de Mort","emoji":"💀","degats":55,"desc":"Verdict sans appel"}], "faiblesse":"⚡", "resistance":"🌟"},
    "kazuma": {"nom":"Kazuma Sato", "serie":"Konosuba", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/enjMPoo.jpg", "attaques":[{"nom":"Steal","emoji":"🖐️","degats":28,"desc":"Vole un objet au hasard"},{"nom":"Embuscade","emoji":"🌿","degats":33,"desc":"Attaque par surprise"},{"nom":"Chance Maximale","emoji":"🍀","degats":38,"desc":"Sa seule vraie stat"}], "faiblesse":"⚡", "resistance":"🌟"},
    "aqua": {"nom":"Aqua", "serie":"Konosuba", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/8rNReMB.jpg", "attaques":[{"nom":"Sacred Turn Undead","emoji":"✨","degats":29,"desc":"Pulvérise les morts-vivants"},{"nom":"God Blow","emoji":"👊","degats":34,"desc":"Poing divin"},{"nom":"Pleurnicherie","emoji":"😭","degats":39,"desc":"Agace l'ennemi"}], "faiblesse":"⚡", "resistance":"🌟"},
    "megumin": {"nom":"Megumin", "serie":"Konosuba", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/tyeydlp.jpg", "attaques":[{"nom":"Explosion","emoji":"💥","degats":34,"desc":"La seule magie qu'elle connaît"},{"nom":"Incantation Interminable","emoji":"📜","degats":30,"desc":"Deux minutes de chuunibyou"},{"nom":"Effondrement","emoji":"😵","degats":25,"desc":"Ne peut plus bouger après"}], "faiblesse":"⚡", "resistance":"🌟"},
    "darkness": {"nom":"Darkness", "serie":"Konosuba", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"", "attaques":[{"nom":"Provocation","emoji":"🛡️","degats":26,"desc":"Attire tous les coups"},{"nom":"Encaissement","emoji":"💪","degats":31,"desc":"Défense monstrueuse"},{"nom":"Attaque Aléatoire","emoji":"🎲","degats":36,"desc":"Ne touche jamais sa cible"}], "faiblesse":"⚡", "resistance":"🌟"},
    "narumisho": {"nom":"Narumi Sho", "serie":"MHA Vigilante", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/Uopntmk.jpg", "attaques":[{"nom":"Vitesse Aveuglante","emoji":"💨","degats":29,"desc":"Trop rapide pour l'œil"},{"nom":"Coup Décisif","emoji":"👊","degats":34,"desc":"Frappe unique"},{"nom":"Confiance Absolue","emoji":"😎","degats":39,"desc":"Ne doute jamais"}], "faiblesse":"⚡", "resistance":"🌟"},
    "kouichi": {"nom":"Kouichi Haimawari", "serie":"MHA Vigilante", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/xXCITQ8.jpg", "attaques":[{"nom":"Slide and Glide","emoji":"🛼","degats":26,"desc":"Glisse sur les surfaces"},{"nom":"Coup de Pied Aérien","emoji":"🦵","degats":31,"desc":"Frappe en mouvement"},{"nom":"Aide Discrète","emoji":"🤝","degats":36,"desc":"Le héros de l'ombre"}], "faiblesse":"⚡", "resistance":"🌟"},
    "kazuho": {"nom":"Kazuho Haneyama", "serie":"MHA Vigilante", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/4OzcWm0.jpg", "attaques":[{"nom":"Onde Sonore","emoji":"🎤","degats":27,"desc":"Chant amplifié"},{"nom":"Sonic Wave","emoji":"🔊","degats":32,"desc":"Vibration destructrice"},{"nom":"Pop Step","emoji":"🦘","degats":37,"desc":"Bond musical"}], "faiblesse":"⚡", "resistance":"🌟"},
    "mash": {"nom":"Mash Burnedead", "serie":"Mashle", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/ETOIMgo.jpg", "attaques":[{"nom":"Poing Musculaire","emoji":"💪","degats":58,"desc":"Zéro magie, cent muscles"},{"nom":"Iron Fist","emoji":"🤜","degats":65,"desc":"Frappe démolisseuse"},{"nom":"Rotation Brutale","emoji":"🌀","degats":72,"desc":"Vrille dévastatrice"}], "faiblesse":"⚡", "resistance":"🌟"},
    "lanceep": {"nom":"Lance Crown", "serie":"Mashle", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/TOpeVUp.jpg", "attaques":[{"nom":"Magie de Fer","emoji":"⚙️","degats":58,"desc":"Lames métalliques"},{"nom":"Iron Grave","emoji":"⚰️","degats":65,"desc":"Cercueil de fer"},{"nom":"Amour Fraternel","emoji":"💗","degats":72,"desc":"Se surpasse pour sa sœur"}], "faiblesse":"⚡", "resistance":"🌟"},
    "finn": {"nom":"Finn Ames", "serie":"Mashle", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"", "attaques":[{"nom":"Magie Défensive","emoji":"🛡️","degats":41,"desc":"Barrière fiable"},{"nom":"Coup Nerveux","emoji":"😰","degats":47,"desc":"Frappe hésitante"},{"nom":"Amitié","emoji":"🤝","degats":53,"desc":"Se dépasse pour Mash"}], "faiblesse":"⚡", "resistance":"🌟"},
    "dotmashle": {"nom":"Dot Barrett", "serie":"Mashle", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"", "attaques":[{"nom":"Magie de Feu","emoji":"🔥","degats":42,"desc":"Flammes ardentes"},{"nom":"Boule Incandescente","emoji":"☄️","degats":48,"desc":"Projectile explosif"},{"nom":"Coiffure Parfaite","emoji":"💇","degats":54,"desc":"Ne touchez pas aux cheveux"}], "faiblesse":"⚡", "resistance":"🌟"},
    "mash_com": {"nom":"Mash Burnedead (debut)", "serie":"Mashle", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/ETOIMgo.jpg", "attaques":[{"nom":"Poing Simple","emoji":"👊","degats":29,"desc":"Force brute"},{"nom":"Cream Puff","emoji":"🧁","degats":34,"desc":"Motivé par les choux"},{"nom":"Entraînement Matinal","emoji":"🏋️","degats":39,"desc":"Mille pompes par jour"}], "faiblesse":"⚡", "resistance":"🌟"},
    "laplace": {"nom":"Laplace", "serie":"Mushoku Tensei", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"", "attaques":[{"nom":"Magie des Démons","emoji":"👹","degats":90,"desc":"Sorts interdits"},{"nom":"Prescience","emoji":"👁️","degats":99,"desc":"Voit les futurs possibles"},{"nom":"Plan Millénaire","emoji":"♟️","degats":108,"desc":"Tout était prévu"}], "faiblesse":"⚡", "resistance":"🌟"},
    "ruijerd": {"nom":"Ruijerd Superdia", "serie":"Mushoku Tensei", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/NpLm3dY.jpg", "attaques":[{"nom":"Lance Superd","emoji":"🔱","degats":73,"desc":"Arme du peuple maudit"},{"nom":"Œil Perceptif","emoji":"👁️","degats":81,"desc":"Détecte les présences"},{"nom":"Fierté du Superd","emoji":"💚","degats":88,"desc":"Protège les enfants"}], "faiblesse":"⚡", "resistance":"🌟"},
    "rudeus": {"nom":"Rudeus Greyrat", "serie":"Mushoku Tensei", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/3Ih34qF.jpg", "attaques":[{"nom":"Magie Sans Incantation","emoji":"🔮","degats":58,"desc":"Sorts instantanés"},{"nom":"Stone Cannon","emoji":"🪨","degats":65,"desc":"Projectile perforant"},{"nom":"Œil Divin","emoji":"👁️","degats":72,"desc":"Voit une seconde d'avance"}], "faiblesse":"⚡", "resistance":"🌟"},
    "allmightl": {"nom":"All Might (Prime)", "serie":"My Hero Academia", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/5YVOpkT.jpg", "attaques":[{"nom":"Detroit Smash","emoji":"💥","degats":73,"desc":"Poing du symbole"},{"nom":"Texas Smash","emoji":"🌪️","degats":81,"desc":"Souffle de vent"},{"nom":"United States of Smash","emoji":"🇺🇸","degats":88,"desc":"Toute la puissance restante"}], "faiblesse":"⚡", "resistance":"🌟"},
    "deku100": {"nom":"Deku (100%)", "serie":"My Hero Academia", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"", "attaques":[{"nom":"Delaware Smash","emoji":"💨","degats":72,"desc":"Chiquenaude d'air"},{"nom":"100% Full Cowl","emoji":"⚡","degats":80,"desc":"Corps entier"},{"nom":"Detroit Smash","emoji":"💥","degats":88,"desc":"Héritage du One For All"}], "faiblesse":"⚡", "resistance":"🌟"},
    "afo": {"nom":"All For One", "serie":"My Hero Academia", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/4926kae.jpg", "attaques":[{"nom":"Vol d'Alter","emoji":"🖐️","degats":73,"desc":"Prend le pouvoir"},{"nom":"Air Cannon","emoji":"💨","degats":81,"desc":"Souffle destructeur"},{"nom":"Alters Multiples","emoji":"🌑","degats":88,"desc":"Combine ses vols"}], "faiblesse":"⚡", "resistance":"🌟"},
    "toga": {"nom":"Toga Himiko", "serie":"My Hero Academia", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/KfQa8Rz.jpg", "attaques":[{"nom":"Transformation","emoji":"🩸","degats":58,"desc":"Prend l'apparence bue"},{"nom":"Couteaux","emoji":"🔪","degats":64,"desc":"Lames dissimulées"},{"nom":"Amour Dévorant","emoji":"💕","degats":72,"desc":"Devient celle qu'elle aime"}], "faiblesse":"⚡", "resistance":"🌟"},
    "overhaul": {"nom":"Overhaul", "serie":"My Hero Academia", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/1YJZ1rg.jpg", "attaques":[{"nom":"Désassemblage","emoji":"🖐️","degats":58,"desc":"Décompose au toucher"},{"nom":"Réassemblage","emoji":"🧩","degats":65,"desc":"Reforme la matière"},{"nom":"Fusion","emoji":"👹","degats":72,"desc":"Absorbe ses alliés"}], "faiblesse":"⚡", "resistance":"🌟"},
    "muscular": {"nom":"Muscular", "serie":"My Hero Academia", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/s9SpLak.jpg", "attaques":[{"nom":"Fibres Musculaires","emoji":"💪","degats":58,"desc":"Muscles apparents"},{"nom":"Charge Brutale","emoji":"🐗","degats":65,"desc":"Bélier humain"},{"nom":"Empilement","emoji":"🏋️","degats":72,"desc":"Superpose ses fibres"}], "faiblesse":"⚡", "resistance":"🌟"},
    "hantaep": {"nom":"Hanta Sero (Full)", "serie":"My Hero Academia", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"", "attaques":[{"nom":"Ruban Adhésif","emoji":"🎀","degats":56,"desc":"Piège l'adversaire"},{"nom":"Fouet Collant","emoji":"🪢","degats":63,"desc":"Frappe à distance"},{"nom":"Cocon","emoji":"🕸️","degats":70,"desc":"Immobilise totalement"}], "faiblesse":"⚡", "resistance":"🌟"},
    "tokoyami": {"nom":"Tokoyami Fumikage", "serie":"My Hero Academia", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/XGQO6Ao.jpg", "attaques":[{"nom":"Dark Shadow","emoji":"🐦‍⬛","degats":42,"desc":"Ombre vivante"},{"nom":"Black Ankh","emoji":"🌑","degats":48,"desc":"Armure d'ombre"},{"nom":"Abyssal Body","emoji":"👤","degats":54,"desc":"Plus il fait noir, plus il est fort"}], "faiblesse":"⚡", "resistance":"🌟"},
    "uraraka": {"nom":"Uraraka Ochaco", "serie":"My Hero Academia", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/ih0tKWb.jpg", "attaques":[{"nom":"Zéro Gravité","emoji":"🎈","degats":41,"desc":"Annule le poids"},{"nom":"Home Run Comet","emoji":"☄️","degats":47,"desc":"Projette des débris"},{"nom":"Meteor Storm","emoji":"🌠","degats":53,"desc":"Pluie de gravats"}], "faiblesse":"⚡", "resistance":"🌟"},
    "iida": {"nom":"Iida Tenya", "serie":"My Hero Academia", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/KHUHYgm.jpg", "attaques":[{"nom":"Recipro Burst","emoji":"🦿","degats":42,"desc":"Accélération extrême"},{"nom":"Torque Over","emoji":"⚙️","degats":48,"desc":"Régime maximal"},{"nom":"Coup de Pied Moteur","emoji":"🦵","degats":54,"desc":"Frappe fulgurante"}], "faiblesse":"⚡", "resistance":"🌟"},
    "yaoyorozu": {"nom":"Yaoyorozu Momo", "serie":"My Hero Academia", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/79pubHU.jpg", "attaques":[{"nom":"Création","emoji":"🧪","degats":42,"desc":"Fabrique n'importe quoi"},{"nom":"Canon Improvisé","emoji":"🔫","degats":48,"desc":"Arme sur mesure"},{"nom":"Bouclier Matriciel","emoji":"🛡️","degats":54,"desc":"Défense créée"}], "faiblesse":"⚡", "resistance":"🌟"},
    "kaminari": {"nom":"Kaminari Denki", "serie":"My Hero Academia", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/uRwc6Xb.jpg", "attaques":[{"nom":"Décharge","emoji":"⚡","degats":41,"desc":"Électricité brute"},{"nom":"Indiscriminate Shock","emoji":"🌩️","degats":47,"desc":"Frappe en zone"},{"nom":"Sharpshooting","emoji":"🎯","degats":53,"desc":"Tir précis via pointe"}], "faiblesse":"⚡", "resistance":"🌟"},
    "vlad": {"nom":"Vlad King", "serie":"My Hero Academia", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/u7oL7Z8.jpg", "attaques":[{"nom":"Blood Control","emoji":"🩸","degats":43,"desc":"Manipule son sang"},{"nom":"Étreinte Écarlate","emoji":"🔴","degats":49,"desc":"Immobilise"},{"nom":"Lance de Sang","emoji":"🗡️","degats":55,"desc":"Perforation"}], "faiblesse":"⚡", "resistance":"🌟"},
    "mineta": {"nom":"Mineta", "serie":"My Hero Academia", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/DV0c9Sa.jpg", "attaques":[{"nom":"Boules Collantes","emoji":"🟣","degats":24,"desc":"Arrache ses cheveux"},{"nom":"Piège Adhésif","emoji":"🕸️","degats":29,"desc":"Bloque au sol"},{"nom":"Fuite Éhontée","emoji":"😰","degats":34,"desc":"Détale en criant"}], "faiblesse":"⚡", "resistance":"🌟"},
    "sero": {"nom":"Sero Hanta", "serie":"My Hero Academia", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/bFBAIFm.jpg", "attaques":[{"nom":"Ruban Adhésif","emoji":"🎀","degats":26,"desc":"Sort de ses coudes"},{"nom":"Balancier","emoji":"🤸","degats":31,"desc":"Se déplace en ville"},{"nom":"Immobilisation","emoji":"🪢","degats":36,"desc":"Ligote sa cible"}], "faiblesse":"⚡", "resistance":"🌟"},
    "aoyama": {"nom":"Aoyama Yuga", "serie":"My Hero Academia", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/BxGZJIL.jpg", "attaques":[{"nom":"Naval Laser","emoji":"✨","degats":27,"desc":"Rayon du nombril"},{"nom":"Laser Prolongé","emoji":"💫","degats":32,"desc":"Tir soutenu"},{"nom":"Style Scintillant","emoji":"💅","degats":37,"desc":"Éblouit l'adversaire"}], "faiblesse":"⚡", "resistance":"🌟"},
    "hagakure": {"nom":"Hagakure Toru", "serie":"My Hero Academia", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/mHsMwlA.jpg", "attaques":[{"nom":"Invisibilité","emoji":"👻","degats":25,"desc":"Totalement indétectable"},{"nom":"Réfraction Lumineuse","emoji":"🔦","degats":30,"desc":"Concentre la lumière"},{"nom":"Attaque Surprise","emoji":"❔","degats":35,"desc":"Personne ne la voit venir"}], "faiblesse":"⚡", "resistance":"🌟"},
    "ojiro": {"nom":"Ojiro Mashirao", "serie":"My Hero Academia", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/XwG9qOE.jpg", "attaques":[{"nom":"Queue Puissante","emoji":"🦎","degats":28,"desc":"Frappe balayante"},{"nom":"Arts Martiaux","emoji":"🥋","degats":33,"desc":"Technique impeccable"},{"nom":"Balayage","emoji":"🌀","degats":38,"desc":"Déséquilibre"}], "faiblesse":"⚡", "resistance":"🌟"},
    "narutosp": {"nom":"Naruto (Six Paths)", "serie":"Naruto", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"https://i.imgur.com/sDvyV8G.jpg", "attaques":[{"nom":"Rasenshuriken","emoji":"🌀","degats":90,"desc":"Shuriken de vent"},{"nom":"Bouddha aux Mille Mains","emoji":"🙏","degats":99,"desc":"Puissance des Six Chemins"},{"nom":"Mode Ermite Six Chemins","emoji":"☀️","degats":108,"desc":"Chakra des Sages"}], "faiblesse":"⚡", "resistance":"🌟"},
    "sasukerinn": {"nom":"Sasuke (Rinnegan)", "serie":"Naruto", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"https://i.imgur.com/4dx82Ou.jpg", "attaques":[{"nom":"Amaterasu","emoji":"🔥","degats":90,"desc":"Flammes noires éternelles"},{"nom":"Susanoo Parfait","emoji":"🗡️","degats":99,"desc":"Colosse spectral"},{"nom":"Chibaku Tensei","emoji":"🌑","degats":107,"desc":"Sphère céleste"}], "faiblesse":"⚡", "resistance":"🌟"},
    "isshiki": {"nom":"Isshiki Otsutsuki", "serie":"Naruto", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"https://i.imgur.com/agAerjl.jpg", "attaques":[{"nom":"Sukunahikona","emoji":"🔻","degats":91,"desc":"Réduit la matière"},{"nom":"Daikokuten","emoji":"⬛","degats":99,"desc":"Invoque ses bâtons"},{"nom":"Karma","emoji":"💠","degats":109,"desc":"Marque des Otsutsuki"}], "faiblesse":"⚡", "resistance":"🌟"},
    "baryonnaruto": {"nom":"Naruto (Baryon Mode)", "serie":"Naruto", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"https://i.imgur.com/sDvyV8G.jpg", "attaques":[{"nom":"Mode Baryon","emoji":"🔴","degats":90,"desc":"Fusion de chakra"},{"nom":"Poing du Renard","emoji":"🦊","degats":99,"desc":"Frappe qui vole la vie"},{"nom":"Rasengan Baryon","emoji":"🌀","degats":108,"desc":"Consume l'adversaire"}], "faiblesse":"⚡", "resistance":"🌟"},
    "momoshiki": {"nom":"Momoshiki Otsutsuki", "serie":"Naruto", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"https://i.imgur.com/SPBKQIg.jpg", "attaques":[{"nom":"Absorption de Ninjutsu","emoji":"🔮","degats":89,"desc":"Avale les techniques"},{"nom":"Rinnegan Rouge","emoji":"👁️","degats":97,"desc":"Renvoie l'attaque"},{"nom":"Flèche de Chakra","emoji":"🏹","degats":106,"desc":"Tir amplifié"}], "faiblesse":"⚡", "resistance":"🌟"},
    "kaguya_m": {"nom":"Kaguya Otsutsuki (Full)", "serie":"Naruto", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"https://i.imgur.com/6E9Q66v.jpg", "attaques":[{"nom":"Tout-Puissant Élément","emoji":"🌋","degats":92,"desc":"Change de dimension"},{"nom":"Cendres Fondantes","emoji":"☄️","degats":100,"desc":"Os de cendre"},{"nom":"Tsukuyomi Infini","emoji":"🌕","degats":110,"desc":"Piège le monde"}], "faiblesse":"⚡", "resistance":"🌟"},
    "mightguy": {"nom":"Might Guy (8 Portes)", "serie":"Naruto", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/RRUkedp.jpg", "attaques":[{"nom":"Sixième Porte","emoji":"🌀","degats":72,"desc":"Vitesse extrême"},{"nom":"Hirudora","emoji":"🐯","degats":81,"desc":"Tigre de nuit"},{"nom":"Huitième Porte","emoji":"💀","degats":88,"desc":"Dragon du soir, au prix de sa vie"}], "faiblesse":"⚡", "resistance":"🌟"},
    "tobirama": {"nom":"Tobirama Senju", "serie":"Naruto", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/6qXLw0N.jpg", "attaques":[{"nom":"Suiton Vague Explosive","emoji":"🌊","degats":72,"desc":"Raz-de-marée"},{"nom":"Hiraishin","emoji":"⚡","degats":80,"desc":"Téléportation instantanée"},{"nom":"Edo Tensei","emoji":"💀","degats":88,"desc":"Réanime les morts"}], "faiblesse":"⚡", "resistance":"🌟"},
    "orochimaru": {"nom":"Orochimaru", "serie":"Naruto", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/912UszF.jpg", "attaques":[{"nom":"Serpents Cachés","emoji":"🐍","degats":58,"desc":"Sort des manches"},{"nom":"Kusanagi","emoji":"🗡️","degats":65,"desc":"Lame sacrée"},{"nom":"Immortalité","emoji":"♾️","degats":72,"desc":"Change de corps"}], "faiblesse":"⚡", "resistance":"🌟"},
    "konan": {"nom":"Konan", "serie":"Naruto", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/HzC900u.jpg", "attaques":[{"nom":"Danse du Shikigami","emoji":"📄","degats":58,"desc":"Ailes de papier"},{"nom":"Pluie d'Origami","emoji":"🌧️","degats":64,"desc":"Papillons explosifs"},{"nom":"Océan de Parchemins","emoji":"📜","degats":72,"desc":"Six cent milliards de talismans"}], "faiblesse":"⚡", "resistance":"🌟"},
    "temari": {"nom":"Temari", "serie":"Naruto", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/0k8xkUw.jpg", "attaques":[{"nom":"Éventail de Vent","emoji":"🌬️","degats":42,"desc":"Bourrasque tranchante"},{"nom":"Faucille du Vent","emoji":"🌪️","degats":48,"desc":"Lames invisibles"},{"nom":"Kamatari","emoji":"🦡","degats":54,"desc":"Invoque la belette"}], "faiblesse":"⚡", "resistance":"🌟"},
    "asuma": {"nom":"Asuma Sarutobi", "serie":"Naruto", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/ETWXGX5.jpg", "attaques":[{"nom":"Lames de Chakra","emoji":"✂️","degats":43,"desc":"Poings américains"},{"nom":"Cendres Ardentes","emoji":"🔥","degats":48,"desc":"Nuage explosif"},{"nom":"Hien","emoji":"💨","degats":54,"desc":"Lame allongée"}], "faiblesse":"⚡", "resistance":"🌟"},
    "kurenai": {"nom":"Kurenai Yuhi", "serie":"Naruto", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/Ff8hnaz.jpg", "attaques":[{"nom":"Genjutsu Illusoire","emoji":"🌸","degats":41,"desc":"Piège mental"},{"nom":"Arbre Enveloppant","emoji":"🌳","degats":47,"desc":"Immobilise"},{"nom":"Illusion Florale","emoji":"🌺","degats":53,"desc":"Perd toute notion"}], "faiblesse":"⚡", "resistance":"🌟"},
    "yamato": {"nom":"Yamato", "serie":"Naruto", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/Cv9YpcR.jpg", "attaques":[{"nom":"Mokuton","emoji":"🌲","degats":44,"desc":"Élément bois"},{"nom":"Prison de Bois","emoji":"🪵","degats":49,"desc":"Cage vivante"},{"nom":"Quatre Piliers","emoji":"🏛️","degats":55,"desc":"Structure défensive"}], "faiblesse":"⚡", "resistance":"🌟"},
    "deidara": {"nom":"Deidara", "serie":"Naruto", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/KpYxLSW.jpg", "attaques":[{"nom":"Argile Explosive","emoji":"🧨","degats":43,"desc":"Sculptures vivantes"},{"nom":"C2 Dragon","emoji":"🐉","degats":49,"desc":"Dragon d'argile"},{"nom":"C4 Karura","emoji":"💀","degats":55,"desc":"Explosion microscopique"}], "faiblesse":"⚡", "resistance":"🌟"},
    "sasori": {"nom":"Sasori", "serie":"Naruto", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/PZxzyLv.jpg", "attaques":[{"nom":"Marionnettes","emoji":"🎎","degats":43,"desc":"Cent pantins"},{"nom":"Lames Empoisonnées","emoji":"☠️","degats":49,"desc":"Poison foudroyant"},{"nom":"Hiruko","emoji":"🦂","degats":55,"desc":"Carapace de combat"}], "faiblesse":"⚡", "resistance":"🌟"},
    "kabuto": {"nom":"Kabuto Yakushi", "serie":"Naruto", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/LaVdS18.jpg", "attaques":[{"nom":"Scalpel de Chakra","emoji":"🔪","degats":42,"desc":"Tranche les muscles"},{"nom":"Mode Ermite","emoji":"🐍","degats":48,"desc":"Chakra du serpent"},{"nom":"Régénération","emoji":"🩹","degats":54,"desc":"Se reconstitue"}], "faiblesse":"⚡", "resistance":"🌟"},
    "ebisu": {"nom":"Ebisu", "serie":"Naruto", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/E7tlhOH.jpg", "attaques":[{"nom":"Taijutsu de Base","emoji":"👊","degats":25,"desc":"Technique académique"},{"nom":"Clone Élite","emoji":"👥","degats":30,"desc":"Double d'entraînement"},{"nom":"Fierté du Tuteur","emoji":"🤓","degats":35,"desc":"Discours interminable"}], "faiblesse":"⚡", "resistance":"🌟"},
    "iruka": {"nom":"Iruka Umino", "serie":"Naruto", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/jJg9gWq.jpg", "attaques":[{"nom":"Shuriken","emoji":"⭐","degats":27,"desc":"Lancer précis"},{"nom":"Clone d'Ombre","emoji":"👥","degats":32,"desc":"Diversion"},{"nom":"Protection du Maître","emoji":"🛡️","degats":37,"desc":"Se sacrifie pour ses élèves"}], "faiblesse":"⚡", "resistance":"🌟"},
    "ino": {"nom":"Ino Yamanaka", "serie":"Naruto", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/6pcNDvB.jpg", "attaques":[{"nom":"Transfert d'Esprit","emoji":"🧠","degats":28,"desc":"Prend le contrôle"},{"nom":"Fleur Explosive","emoji":"🌸","degats":33,"desc":"Piège floral"},{"nom":"Perception Mentale","emoji":"💭","degats":38,"desc":"Lit les pensées"}], "faiblesse":"⚡", "resistance":"🌟"},
    "choji": {"nom":"Choji Akimichi", "serie":"Naruto", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/0haGoIw.jpg", "attaques":[{"nom":"Décuplement","emoji":"🍖","degats":30,"desc":"Corps géant"},{"nom":"Boulet Humain","emoji":"⚪","degats":35,"desc":"Roule sur l'ennemi"},{"nom":"Papillon","emoji":"🦋","degats":40,"desc":"Pilule rouge"}], "faiblesse":"⚡", "resistance":"🌟"},
    "kankuro": {"nom":"Kankuro", "serie":"Naruto", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/bdRuDAU.jpg", "attaques":[{"nom":"Corbeau","emoji":"🎎","degats":28,"desc":"Marionnette à lames"},{"nom":"Poison Noir","emoji":"☠️","degats":33,"desc":"Aiguilles empoisonnées"},{"nom":"Salamandre","emoji":"🦎","degats":38,"desc":"Bouclier vivant"}], "faiblesse":"⚡", "resistance":"🌟"},
    "anko": {"nom":"Anko Mitarashi", "serie":"Naruto", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/9ioyert.jpg", "attaques":[{"nom":"Serpents Ombres","emoji":"🐍","degats":29,"desc":"Sortent des manches"},{"nom":"Aiguilles Senbon","emoji":"📍","degats":34,"desc":"Volée précise"},{"nom":"Marque Maudite","emoji":"🔯","degats":39,"desc":"Puissance instable"}], "faiblesse":"⚡", "resistance":"🌟"},
    "izumo": {"nom":"Izumo Kamizuki", "serie":"Naruto", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/JOu1umT.jpg", "attaques":[{"nom":"Lame Cornue","emoji":"🗡️","degats":26,"desc":"Arme à double crochet"},{"nom":"Duo Parfait","emoji":"🤝","degats":31,"desc":"Attaque coordonnée"},{"nom":"Garde de Konoha","emoji":"🛡️","degats":36,"desc":"Défend la porte"}], "faiblesse":"⚡", "resistance":"🌟"},
    "kotetsu": {"nom":"Kotetsu Hagane", "serie":"Naruto", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/DlRzvyY.jpg", "attaques":[{"nom":"Masse Hérissée","emoji":"🔨","degats":26,"desc":"Arme contondante"},{"nom":"Duo Parfait","emoji":"🤝","degats":31,"desc":"Attaque coordonnée"},{"nom":"Garde de Konoha","emoji":"🛡️","degats":36,"desc":"Défend la porte"}], "faiblesse":"⚡", "resistance":"🌟"},
    "moegi": {"nom":"Moegi", "serie":"Naruto", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/WeWmVwc.jpg", "attaques":[{"nom":"Mokuton Naissant","emoji":"🌱","degats":25,"desc":"Élément bois débutant"},{"nom":"Clone d'Ombre","emoji":"👥","degats":30,"desc":"Technique de base"},{"nom":"Volonté du Feu","emoji":"🔥","degats":35,"desc":"Détermination"}], "faiblesse":"⚡", "resistance":"🌟"},
    "hanabi": {"nom":"Hanabi Hyuga", "serie":"Naruto", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/t29BUBj.jpg", "attaques":[{"nom":"Poing Souple","emoji":"👋","degats":29,"desc":"Frappe les points de chakra"},{"nom":"Byakugan","emoji":"👁️","degats":34,"desc":"Vision à 360 degrés"},{"nom":"Paume du Vide","emoji":"💨","degats":39,"desc":"Repousse à distance"}], "faiblesse":"⚡", "resistance":"🌟"},
    "hidan": {"nom":"Hidan", "serie":"Naruto", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/G7pZkhI.jpg", "attaques":[{"nom":"Faux à Trois Lames","emoji":"☠️","degats":30,"desc":"Récolte le sang"},{"nom":"Rituel Maudit","emoji":"🩸","degats":35,"desc":"Partage la douleur"},{"nom":"Immortalité","emoji":"♾️","degats":40,"desc":"Ne peut pas mourir"}], "faiblesse":"⚡", "resistance":"🌟"},
    "kakuzu": {"nom":"Kakuzu", "serie":"Naruto", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/a1qKNly.jpg", "attaques":[{"nom":"Masques Élémentaires","emoji":"🎭","degats":30,"desc":"Cinq cœurs, cinq éléments"},{"nom":"Fils d'Acier","emoji":"🧵","degats":35,"desc":"Membres détachables"},{"nom":"Cœur Volé","emoji":"🫀","degats":40,"desc":"Absorbe une vie"}], "faiblesse":"⚡", "resistance":"🌟"},
    "imsama": {"nom":"Im-Sama", "serie":"One Piece", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"https://i.imgur.com/4FkukvY.jpg", "attaques":[{"nom":"Volonté du Trône","emoji":"👑","degats":90,"desc":"Ordre absolu"},{"nom":"Effacement d'Histoire","emoji":"📜","degats":99,"desc":"Rature le passé"},{"nom":"Décret Suprême","emoji":"⚡","degats":108,"desc":"Nul n'y échappe"}], "faiblesse":"⚡", "resistance":"🌟"},
    "luffygear5": {"nom":"Luffy (Gear 5)", "serie":"One Piece", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"", "attaques":[{"nom":"Bajrang Gun","emoji":"☀️","degats":90,"desc":"Poing géant"},{"nom":"Liberté du Toon","emoji":"🎈","degats":99,"desc":"Réalité déformée"},{"nom":"Rire du Nika","emoji":"😂","degats":108,"desc":"Le tambour de la libération"}], "faiblesse":"⚡", "resistance":"🌟"},
    "kaidodragon": {"nom":"Kaido (Dragon)", "serie":"One Piece", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"https://i.imgur.com/Q76UJEX.jpg", "attaques":[{"nom":"Bolo Breath","emoji":"🔥","degats":90,"desc":"Souffle incandescent"},{"nom":"Boro Blast","emoji":"⚡","degats":98,"desc":"Éclair du ciel"},{"nom":"Raimei Hakke","emoji":"🌩️","degats":107,"desc":"Huit trigrammes du tonnerre"}], "faiblesse":"⚡", "resistance":"🌟"},
    "bigmom": {"nom":"Big Mom", "serie":"One Piece", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/jP0GMXL.jpg", "attaques":[{"nom":"Ikoku","emoji":"☁️","degats":72,"desc":"Nuage tranchant"},{"nom":"Prometheus","emoji":"☀️","degats":80,"desc":"Soleil vivant"},{"nom":"Vol d'Âme","emoji":"👻","degats":88,"desc":"Prend des années de vie"}], "faiblesse":"⚡", "resistance":"🌟"},
    "admiralkizaru": {"nom":"Kizaru", "serie":"One Piece", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/bxRummG.jpg", "attaques":[{"nom":"Yasakani no Magatama","emoji":"💫","degats":72,"desc":"Pluie de lumière"},{"nom":"Ama no Murakumo","emoji":"⚔️","degats":80,"desc":"Lame lumineuse"},{"nom":"Vitesse Lumière","emoji":"⚡","degats":88,"desc":"Insaisissable"}], "faiblesse":"⚡", "resistance":"🌟"},
    "admiralaokiji": {"nom":"Aokiji", "serie":"One Piece", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/Z2KRYQd.jpg", "attaques":[{"nom":"Ice Age","emoji":"❄️","degats":72,"desc":"Gèle la mer"},{"nom":"Ice Saber","emoji":"🗡️","degats":80,"desc":"Lame de glace"},{"nom":"Pheasant Beak","emoji":"🦅","degats":88,"desc":"Oiseau de givre"}], "faiblesse":"⚡", "resistance":"🌟"},
    "admiralakainu": {"nom":"Akainu", "serie":"One Piece", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/WUQYoFP.jpg", "attaques":[{"nom":"Meigo","emoji":"👊","degats":73,"desc":"Poing de magma"},{"nom":"Dai Funka","emoji":"🌋","degats":81,"desc":"Éruption majeure"},{"nom":"Ryusei Kazan","emoji":"☄️","degats":88,"desc":"Pluie volcanique"}], "faiblesse":"⚡", "resistance":"🌟"},
    "katakuri": {"nom":"Katakuri", "serie":"One Piece", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/vfzIr7R.jpg", "attaques":[{"nom":"Mochi Tsuki","emoji":"🍡","degats":58,"desc":"Pilonnage de mochi"},{"nom":"Buzz Cut Mochi","emoji":"✂️","degats":65,"desc":"Lances gluantes"},{"nom":"Kenbunshoku Futur","emoji":"👁️","degats":72,"desc":"Voit les coups d'avance"}], "faiblesse":"⚡", "resistance":"🌟"},
    "roblucci": {"nom":"Rob Lucci", "serie":"One Piece", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/OqBlCGc.jpg", "attaques":[{"nom":"Rokuogan","emoji":"💥","degats":58,"desc":"Onde de choc interne"},{"nom":"Shigan","emoji":"☝️","degats":64,"desc":"Doigt perforant"},{"nom":"Léopard","emoji":"🐆","degats":72,"desc":"Forme hybride"}], "faiblesse":"⚡", "resistance":"🌟"},
    "enel": {"nom":"Enel", "serie":"One Piece", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/yMIM8D5.jpg", "attaques":[{"nom":"El Thor","emoji":"⚡","degats":58,"desc":"Foudre du ciel"},{"nom":"Kiten","emoji":"🐍","degats":65,"desc":"Serpent électrique"},{"nom":"Raigo","emoji":"☁️","degats":72,"desc":"Jugement divin"}], "faiblesse":"⚡", "resistance":"🌟"},
    "doflamingo": {"nom":"Doflamingo", "serie":"One Piece", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/PPFbKzA.jpg", "attaques":[{"nom":"Parasite","emoji":"🧵","degats":58,"desc":"Contrôle les corps"},{"nom":"Overheat","emoji":"🔥","degats":65,"desc":"Fil incandescent"},{"nom":"God Thread","emoji":"🕸️","degats":72,"desc":"Lances de fil"}], "faiblesse":"⚡", "resistance":"🌟"},
    "marco": {"nom":"Marco le Phénix", "serie":"One Piece", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/41zNRCO.jpg", "attaques":[{"nom":"Flammes Bleues","emoji":"💙","degats":58,"desc":"Régénération"},{"nom":"Serres du Phénix","emoji":"🦅","degats":65,"desc":"Griffes ardentes"},{"nom":"Renaissance","emoji":"🔥","degats":72,"desc":"Renaît de ses cendres"}], "faiblesse":"⚡", "resistance":"🌟"},
    "sabo": {"nom":"Sabo", "serie":"One Piece", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/MX8frrO.jpg", "attaques":[{"nom":"Griffe de Dragon","emoji":"🐉","degats":58,"desc":"Poing enflammé"},{"nom":"Hiken","emoji":"🔥","degats":66,"desc":"L'héritage d'Ace"},{"nom":"Ryusoken","emoji":"💢","degats":72,"desc":"Poing du dragon"}], "faiblesse":"⚡", "resistance":"🌟"},
    "smoker": {"nom":"Smoker", "serie":"One Piece", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/7i5i7h3.jpg", "attaques":[{"nom":"White Blow","emoji":"💨","degats":42,"desc":"Poing de fumée"},{"nom":"White Snake","emoji":"🐍","degats":48,"desc":"Serpent brumeux"},{"nom":"Matraque Kairoseki","emoji":"🔱","degats":54,"desc":"Annule les pouvoirs"}], "faiblesse":"⚡", "resistance":"🌟"},
    "bellamy": {"nom":"Bellamy", "serie":"One Piece", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/TADQZSS.jpg", "attaques":[{"nom":"Spring Hopper","emoji":"🌀","degats":41,"desc":"Rebond fulgurant"},{"nom":"Spring Snipe","emoji":"🎯","degats":47,"desc":"Frappe propulsée"},{"nom":"Bane Bane no Mi","emoji":"💥","degats":53,"desc":"Élasticité brutale"}], "faiblesse":"⚡", "resistance":"🌟"},
    "missvalentine": {"nom":"Miss Valentine", "serie":"One Piece", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/x2evVSX.jpg", "attaques":[{"nom":"Kilo Press","emoji":"⚖️","degats":40,"desc":"Écrase de tout son poids"},{"nom":"Ombrelle Tournoyante","emoji":"☂️","degats":46,"desc":"Frappe aérienne"},{"nom":"Dix Mille Kilos","emoji":"💢","degats":52,"desc":"Poids maximal"}], "faiblesse":"⚡", "resistance":"🌟"},
    "mr5": {"nom":"Mr 5", "serie":"One Piece", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/rzPjawD.jpg", "attaques":[{"nom":"Nose Fancy Cannon","emoji":"👃","degats":40,"desc":"Projectile explosif"},{"nom":"Doigt Explosif","emoji":"💥","degats":46,"desc":"Chaque partie explose"},{"nom":"Souffle Détonant","emoji":"💣","degats":52,"desc":"Explosion rapprochée"}], "faiblesse":"⚡", "resistance":"🌟"},
    "tashigi": {"nom":"Tashigi", "serie":"One Piece", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/iZLo8au.jpg", "attaques":[{"nom":"Coup Précis","emoji":"⚔️","degats":41,"desc":"Lame exacte"},{"nom":"Iaido","emoji":"🗡️","degats":47,"desc":"Dégainé foudroyant"},{"nom":"Shigure","emoji":"🌧️","degats":53,"desc":"Épée légendaire"}], "faiblesse":"⚡", "resistance":"🌟"},
    "crocobase": {"nom":"Crocodile", "serie":"One Piece", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/lQsrDPU.jpg", "attaques":[{"nom":"Sables Mouvants","emoji":"🏜️","degats":44,"desc":"Aspire au sol"},{"nom":"Desert Spada","emoji":"🗡️","degats":50,"desc":"Lame de sable"},{"nom":"Ground Death","emoji":"💀","degats":55,"desc":"Assèche tout"}], "faiblesse":"⚡", "resistance":"🌟"},
    "coby": {"nom":"Coby", "serie":"One Piece", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/D6I5q8r.jpg", "attaques":[{"nom":"Rokushiki","emoji":"👊","degats":28,"desc":"Bases de la Marine"},{"nom":"Soru","emoji":"💨","degats":33,"desc":"Déplacement éclair"},{"nom":"Détermination","emoji":"💪","degats":38,"desc":"Ne renonce jamais"}], "faiblesse":"⚡", "resistance":"🌟"},
    "helmeppo": {"nom":"Helmeppo", "serie":"One Piece", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/75dmyw6.jpg", "attaques":[{"nom":"Kukri","emoji":"🔪","degats":26,"desc":"Double lame"},{"nom":"Coup Fourbe","emoji":"😼","degats":31,"desc":"Frappe déloyale"},{"nom":"Entraînement","emoji":"🏋️","degats":36,"desc":"Progrès récents"}], "faiblesse":"⚡", "resistance":"🌟"},
    "richie": {"nom":"Richie", "serie":"One Piece", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"", "attaques":[{"nom":"Griffes de Lion","emoji":"🦁","degats":27,"desc":"Lacération"},{"nom":"Rugissement","emoji":"🔊","degats":32,"desc":"Terrifie"},{"nom":"Charge Féline","emoji":"🐾","degats":37,"desc":"Bond puissant"}], "faiblesse":"⚡", "resistance":"🌟"},
    "alvida": {"nom":"Alvida", "serie":"One Piece", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/6DoLNt8.jpg", "attaques":[{"nom":"Massue de Fer","emoji":"🔨","degats":28,"desc":"Coup assommant"},{"nom":"Sube Sube","emoji":"💧","degats":33,"desc":"Tout glisse sur elle"},{"nom":"Charge Lisse","emoji":"✨","degats":38,"desc":"Insaisissable"}], "faiblesse":"⚡", "resistance":"🌟"},
    "wapol": {"nom":"Wapol", "serie":"One Piece", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/ME6sNT9.jpg", "attaques":[{"nom":"Baku Baku","emoji":"😋","degats":28,"desc":"Dévore et fusionne"},{"nom":"Canon Munch","emoji":"🔫","degats":33,"desc":"Crache ce qu'il mange"},{"nom":"Wapol House","emoji":"🏠","degats":38,"desc":"Forme blindée"}], "faiblesse":"⚡", "resistance":"🌟"},
    "buggy": {"nom":"Buggy le Clown", "serie":"One Piece", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/zaPTd4C.jpg", "attaques":[{"nom":"Bara Bara","emoji":"✂️","degats":30,"desc":"Corps en morceaux"},{"nom":"Muggy Ball","emoji":"💣","degats":35,"desc":"Boule explosive"},{"nom":"Chop Chop Cannon","emoji":"🔪","degats":40,"desc":"Volée de couteaux"}], "faiblesse":"⚡", "resistance":"🌟"},
    "mohji": {"nom":"Mohji", "serie":"One Piece", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/yO9O84d.jpg", "attaques":[{"nom":"Fouet du Dompteur","emoji":"🎪","degats":26,"desc":"Claquement sec"},{"nom":"Richie Attaque","emoji":"🦁","degats":31,"desc":"Envoie son lion"},{"nom":"Cirque Sauvage","emoji":"🎭","degats":36,"desc":"Numéro brutal"}], "faiblesse":"⚡", "resistance":"🌟"},
    "cabaji": {"nom":"Cabaji", "serie":"One Piece", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/MoaRmJd.jpg", "attaques":[{"nom":"Kyokugei Kenpo","emoji":"🎪","degats":27,"desc":"Escrime acrobatique"},{"nom":"Roue Tranchante","emoji":"🚲","degats":32,"desc":"Charge à vélo"},{"nom":"Toupie Mortelle","emoji":"🌀","degats":37,"desc":"Tourbillon de lames"}], "faiblesse":"⚡", "resistance":"🌟"},
    "jango": {"nom":"Jango", "serie":"One Piece", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/A6fISXf.jpg", "attaques":[{"nom":"Chakram","emoji":"💿","degats":27,"desc":"Disque tranchant"},{"nom":"Hypnose","emoji":"😵","degats":32,"desc":"Endort sa cible"},{"nom":"Un, Deux, Jango","emoji":"🕺","degats":37,"desc":"Danse hypnotique"}], "faiblesse":"⚡", "resistance":"🌟"},
    "bonclay": {"nom":"Bon Clay", "serie":"One Piece", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/LoOhxYu.jpg", "attaques":[{"nom":"Mane Mane","emoji":"🎭","degats":29,"desc":"Copie un visage"},{"nom":"Ballet Kenpo","emoji":"🩰","degats":34,"desc":"Coups de pied gracieux"},{"nom":"Cygne Blanc","emoji":"🦢","degats":39,"desc":"Danse mortelle"}], "faiblesse":"⚡", "resistance":"🌟"},
    "foxy": {"nom":"Foxy", "serie":"One Piece", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/MKVeZsg.jpg", "attaques":[{"nom":"Noro Noro Beam","emoji":"🐌","degats":28,"desc":"Ralentit trente secondes"},{"nom":"Coup Sournois","emoji":"😈","degats":33,"desc":"Frappe pendant l'arrêt"},{"nom":"Afro Boost","emoji":"💇","degats":38,"desc":"Puissance capillaire"}], "faiblesse":"⚡", "resistance":"🌟"},
    "mikaela": {"nom":"Mikaela Hyakuya", "serie":"Owari no Seraph", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/lrnezr7.jpg", "attaques":[{"nom":"Soif de Sang","emoji":"🩸","degats":43,"desc":"Force vampirique"},{"nom":"Épée Maudite","emoji":"⚔️","degats":49,"desc":"Lame de noble"},{"nom":"Lien Fraternel","emoji":"🤝","degats":55,"desc":"Se bat pour Yuichiro"}], "faiblesse":"⚡", "resistance":"🌟"},
    "yuichiro": {"nom":"Yuichiro Hyakuya", "serie":"Owari no Seraph", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/CrHTsmJ.jpg", "attaques":[{"nom":"Asuramaru","emoji":"😈","degats":44,"desc":"Épée démoniaque"},{"nom":"Contrat Démoniaque","emoji":"📜","degats":50,"desc":"Puissance au prix de son âme"},{"nom":"Rage Séraphique","emoji":"👼","degats":55,"desc":"Éveil du séraphin"}], "faiblesse":"⚡", "resistance":"🌟"},
    "lindwurm": {"nom":"Lindwurm", "serie":"Ragna Crimson", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"", "attaques":[{"nom":"Souffle Draconique","emoji":"🐉","degats":90,"desc":"Flammes du roi dragon"},{"nom":"Écailles Absolues","emoji":"🛡️","degats":99,"desc":"Défense parfaite"},{"nom":"Griffe Céleste","emoji":"🐾","degats":108,"desc":"Fend le ciel"}], "faiblesse":"⚡", "resistance":"🌟"},
    "crimson": {"nom":"Crimson", "serie":"Ragna Crimson", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"", "attaques":[{"nom":"Lame Écarlate","emoji":"⚔️","degats":73,"desc":"Épée du futur"},{"nom":"Vitesse Absolue","emoji":"💨","degats":81,"desc":"Plus rapide que la vue"},{"nom":"Tueur de Dragons","emoji":"🐲","degats":88,"desc":"Conçu pour ça"}], "faiblesse":"⚡", "resistance":"🌟"},
    "ragnaep": {"nom":"Ragna", "serie":"Ragna Crimson", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/ShjRIz1.jpg", "attaques":[{"nom":"Épée Grossière","emoji":"🗡️","degats":58,"desc":"Technique brute"},{"nom":"Volonté de Vengeance","emoji":"💢","degats":65,"desc":"Refuse de mourir"},{"nom":"Coup Désespéré","emoji":"💥","degats":72,"desc":"Tout ou rien"}], "faiblesse":"⚡", "resistance":"🌟"},
    "reinmyth": {"nom":"Reinhard van Astrea (Divine)", "serie":"Re:Zero", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"https://i.imgur.com/DDdI6qL.jpg", "attaques":[{"nom":"Bénédiction du Sabre","emoji":"⚔️","degats":91,"desc":"Divine protection"},{"nom":"Épée du Dragon","emoji":"🐉","degats":100,"desc":"Lame légendaire"},{"nom":"Bénédictions Infinies","emoji":"✨","degats":109,"desc":"Une bénédiction pour chaque situation"}], "faiblesse":"⚡", "resistance":"🌟"},
    "reinhard": {"nom":"Reinhard van Astrea", "serie":"Re:Zero", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/DDdI6qL.jpg", "attaques":[{"nom":"Épée Sacrée","emoji":"⚔️","degats":73,"desc":"Lame de l'Astrea"},{"nom":"Bénédiction du Vent","emoji":"🌪️","degats":81,"desc":"Vitesse divine"},{"nom":"Œil du Dragon","emoji":"👁️","degats":88,"desc":"Voit toute faiblesse"}], "faiblesse":"⚡", "resistance":"🌟"},
    "volcanica": {"nom":"Volcanica", "serie":"Re:Zero", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"", "attaques":[{"nom":"Souffle du Dragon","emoji":"🐉","degats":73,"desc":"Flammes ancestrales"},{"nom":"Brume Protectrice","emoji":"🌫️","degats":81,"desc":"Scelle la sorcière"},{"nom":"Rugissement Millénaire","emoji":"🔊","degats":88,"desc":"Ébranle le monde"}], "faiblesse":"⚡", "resistance":"🌟"},
    "emilia_r": {"nom":"Emilia (debut)", "serie":"Re:Zero", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/gTrkjMj.jpg", "attaques":[{"nom":"Magie de Glace","emoji":"❄️","degats":42,"desc":"Cristaux tranchants"},{"nom":"Mur de Givre","emoji":"🧊","degats":48,"desc":"Barrière glaciale"},{"nom":"Esprit Puck","emoji":"🐈","degats":54,"desc":"Contrat avec l'esprit"}], "faiblesse":"⚡", "resistance":"🌟"},
    "otto": {"nom":"Otto Suwen", "serie":"Re:Zero", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/yj239Dw.jpg", "attaques":[{"nom":"Dialogue Animal","emoji":"🐾","degats":25,"desc":"Parle aux bêtes"},{"nom":"Négociation","emoji":"💰","degats":30,"desc":"Marchand rusé"},{"nom":"Loyauté Discrète","emoji":"🤝","degats":35,"desc":"Toujours présent"}], "faiblesse":"⚡", "resistance":"🌟"},
    "sakamotoe": {"nom":"Taro Sakamoto", "serie":"Sakamoto Days", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"", "attaques":[{"nom":"Tir Impossible","emoji":"🔫","degats":58,"desc":"Balle qui ricoche"},{"nom":"Objets du Quotidien","emoji":"🛒","degats":65,"desc":"Tout devient une arme"},{"nom":"Mode Sérieux","emoji":"😐","degats":72,"desc":"Retrouve sa silhouette"}], "faiblesse":"⚡", "resistance":"🌟"},
    "shinae": {"nom":"Shin Asakura", "serie":"Sakamoto Days", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"", "attaques":[{"nom":"Télépathie","emoji":"🧠","degats":58,"desc":"Lit les pensées"},{"nom":"Esquive Anticipée","emoji":"💨","degats":64,"desc":"Connaît le coup d'avance"},{"nom":"Coup de Poing Mental","emoji":"👊","degats":71,"desc":"Frappe où ça fait mal"}], "faiblesse":"⚡", "resistance":"🌟"},
    "jiroep": {"nom":"Jiro Yamada", "serie":"Sakamoto Days", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"", "attaques":[{"nom":"Double Pistolet","emoji":"🔫","degats":57,"desc":"Tir croisé"},{"nom":"Rechargement Rapide","emoji":"⚡","degats":64,"desc":"Vitesse d'exécution"},{"nom":"Style du Tueur","emoji":"🕶️","degats":71,"desc":"Élégance létale"}], "faiblesse":"⚡", "resistance":"🌟"},
    "yukimichi": {"nom":"Yukimichi Tsurumi", "serie":"Sakamoto Days", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"", "attaques":[{"nom":"Course Rapide","emoji":"🏃","degats":26,"desc":"Vitesse de sprinteur"},{"nom":"Frappe Éclair","emoji":"👊","degats":31,"desc":"Coup avant la garde"},{"nom":"Fuite Tactique","emoji":"💨","degats":36,"desc":"Sait quand décrocher"}], "faiblesse":"⚡", "resistance":"🌟"},
    "jinwoofull": {"nom":"Sung Jin-Woo (Monarch)", "serie":"Solo Leveling", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"https://i.imgur.com/cytYnaz.jpg", "attaques":[{"nom":"Armée des Ombres","emoji":"🌑","degats":91,"desc":"Légion de soldats"},{"nom":"Bellion","emoji":"⚔️","degats":100,"desc":"Le commandant des ombres"},{"nom":"Domination du Monarque","emoji":"👑","degats":109,"desc":"Autorité absolue"}], "faiblesse":"⚡", "resistance":"🌟"},
    "antares": {"nom":"Antares", "serie":"Solo Leveling", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"https://i.imgur.com/CEsQ9Kn.jpg", "attaques":[{"nom":"Souffle du Roi Dragon","emoji":"🐉","degats":91,"desc":"Flammes destructrices"},{"nom":"Griffe Monarque","emoji":"🐾","degats":100,"desc":"Lacère les dimensions"},{"nom":"Règne du Destructeur","emoji":"💥","degats":109,"desc":"Roi des Monarques"}], "faiblesse":"⚡", "resistance":"🌟"},
    "chahae": {"nom":"Cha Hae-In", "serie":"Solo Leveling", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/PVzfmpD.jpg", "attaques":[{"nom":"Danse de l'Épée","emoji":"⚔️","degats":58,"desc":"Enchaînement fluide"},{"nom":"Perception Olfactive","emoji":"👃","degats":65,"desc":"Sent le mana"},{"nom":"Épéiste de Rang S","emoji":"✨","degats":72,"desc":"La plus forte de Corée"}], "faiblesse":"⚡", "resistance":"🌟"},
    "thomasandre": {"nom":"Thomas Andre", "serie":"Solo Leveling", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/ahh7Com.jpg", "attaques":[{"nom":"Force Titanesque","emoji":"💪","degats":58,"desc":"Puissance brute"},{"nom":"Prise du Goliath","emoji":"🤼","degats":65,"desc":"Broie l'adversaire"},{"nom":"Rang National","emoji":"🇺🇸","degats":72,"desc":"Chasseur d'élite mondial"}], "faiblesse":"⚡", "resistance":"🌟"},
    "arthurl": {"nom":"Arthur Leywin (Dragon)", "serie":"The Beginning After the End", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/zJikG6Q.jpg", "attaques":[{"nom":"Volonté du Dragon","emoji":"🐉","degats":73,"desc":"Héritage ancestral"},{"nom":"Realmheart","emoji":"💠","degats":81,"desc":"Voit le mana"},{"nom":"Souffle Draconique","emoji":"🔥","degats":88,"desc":"Puissance de la lignée"}], "faiblesse":"⚡", "resistance":"🌟"},
    "arthurep": {"nom":"Arthur Leywin (Asura)", "serie":"The Beginning After the End", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/zJikG6Q.jpg", "attaques":[{"nom":"Burst Step","emoji":"💨","degats":58,"desc":"Déplacement fulgurant"},{"nom":"God Step","emoji":"✨","degats":65,"desc":"Vitesse asura"},{"nom":"Lame de Mana","emoji":"⚔️","degats":72,"desc":"Épée d'énergie"}], "faiblesse":"⚡", "resistance":"🌟"},
    "arthur_tb": {"nom":"Arthur Leywin", "serie":"The Beginning After the End", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/zJikG6Q.jpg", "attaques":[{"nom":"Lame de Vent","emoji":"🌪️","degats":42,"desc":"Mana élémentaire"},{"nom":"Bouclier de Terre","emoji":"🪨","degats":48,"desc":"Protection solide"},{"nom":"Double Élément","emoji":"💠","degats":54,"desc":"Combine les affinités"}], "faiblesse":"⚡", "resistance":"🌟"},
    "gideon": {"nom":"Gideon Crossvalid", "serie":"The Beginning After the End", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"", "attaques":[{"nom":"Enquête","emoji":"🔍","degats":25,"desc":"Trouve la vérité"},{"nom":"Sort de Détection","emoji":"🔮","degats":30,"desc":"Repère le mana"},{"nom":"Autorité","emoji":"📜","degats":35,"desc":"Parle au nom du conseil"}], "faiblesse":"⚡", "resistance":"🌟"},
    "shadowfull": {"nom":"Shadow (True Form)", "serie":"The Eminence in Shadow", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"https://i.imgur.com/cRhS3i4.jpg", "attaques":[{"nom":"I Am Atomic","emoji":"☢️","degats":91,"desc":"Explosion atomique"},{"nom":"Slaughter Wave","emoji":"🌊","degats":100,"desc":"Vague de mana"},{"nom":"Maîtrise de l'Ombre","emoji":"🌑","degats":109,"desc":"Le plus fort, discrètement"}], "faiblesse":"⚡", "resistance":"🌟"},
    "naofumil": {"nom":"Naofumi Iwatani", "serie":"The Rising of the Shield Hero", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/dsFYYLS.jpg", "attaques":[{"nom":"Bouclier de la Colère","emoji":"🛡️","degats":73,"desc":"Nourri par sa rage"},{"nom":"Prison de Ronces","emoji":"🌹","degats":81,"desc":"Épines vengeresses"},{"nom":"Blood Sacrifice","emoji":"🩸","degats":88,"desc":"Au prix de sa propre vie"}], "faiblesse":"⚡", "resistance":"🌟"},
    "filo": {"nom":"Filo", "serie":"The Rising of the Shield Hero", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/w6BThoA.jpg", "attaques":[{"nom":"Spiral Strike","emoji":"🌀","degats":72,"desc":"Vrille aérienne"},{"nom":"Coup de Pied Céleste","emoji":"🦵","degats":80,"desc":"Frappe de reine filolial"},{"nom":"Haikyuu Charge","emoji":"🪶","degats":88,"desc":"Charge à pleine vitesse"}], "faiblesse":"⚡", "resistance":"🌟"},
    "naofumie": {"nom":"Naofumi (Bouclier)", "serie":"The Rising of the Shield Hero", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"https://i.imgur.com/dsFYYLS.jpg", "attaques":[{"nom":"Bouclier de Ronces","emoji":"🌿","degats":58,"desc":"Contre-attaque épineuse"},{"nom":"Air Strike Shield","emoji":"🛡️","degats":65,"desc":"Bouclier flottant"},{"nom":"Shield Prison","emoji":"⛓️","degats":72,"desc":"Emprisonne la cible"}], "faiblesse":"⚡", "resistance":"🌟"},
    "raphtalia": {"nom":"Raphtalia", "serie":"The Rising of the Shield Hero", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/slo211S.jpg", "attaques":[{"nom":"Épée du Raccoon","emoji":"🗡️","degats":44,"desc":"Lame héritée"},{"nom":"Spiral Strike","emoji":"🌀","degats":50,"desc":"Attaque tourbillonnante"},{"nom":"Blood Screech","emoji":"🩸","degats":55,"desc":"Cri déchirant"}], "faiblesse":"⚡", "resistance":"🌟"},
    "malty": {"nom":"Malty Melromarc", "serie":"The Rising of the Shield Hero", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/1XTtPVw.jpg", "attaques":[{"nom":"Mensonge","emoji":"🗣️","degats":25,"desc":"Manipule l'entourage"},{"nom":"Coup Fourbe","emoji":"🔪","degats":30,"desc":"Poignarde dans le dos"},{"nom":"Fausses Larmes","emoji":"😢","degats":35,"desc":"Retourne la situation"}], "faiblesse":"⚡", "resistance":"🌟"},
    "takemichi_l": {"nom":"Takemichi (Futur)", "serie":"Tokyo Revengers", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"https://i.imgur.com/sbsK3sl.jpg", "attaques":[{"nom":"Résolution du Héros","emoji":"💪","degats":72,"desc":"Ne lâche jamais"},{"nom":"Contre-Attaque","emoji":"👊","degats":80,"desc":"Encaisse et rend"},{"nom":"Time Leap","emoji":"⏳","degats":88,"desc":"Change le passé"}], "faiblesse":"⚡", "resistance":"🌟"},
    "mikeye": {"nom":"Manjiro Sano (Mikey)", "serie":"Tokyo Revengers", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"", "attaques":[{"nom":"Coup de Pied Invincible","emoji":"🦵","degats":58,"desc":"Sa frappe légendaire"},{"nom":"Charge du Roi","emoji":"👑","degats":65,"desc":"Aucune hésitation"},{"nom":"Impulsion Noire","emoji":"🌑","degats":72,"desc":"Se laisse submerger"}], "faiblesse":"⚡", "resistance":"🌟"},
    "baji": {"nom":"Keisuke Baji", "serie":"Tokyo Revengers", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"", "attaques":[{"nom":"Poing de Fer","emoji":"👊","degats":57,"desc":"Frappe brute"},{"nom":"Loyauté Absolue","emoji":"🤝","degats":64,"desc":"Se bat pour les siens"},{"nom":"Charge Suicidaire","emoji":"💢","degats":71,"desc":"Sans aucun recul"}], "faiblesse":"⚡", "resistance":"🌟"},
    "izanaep": {"nom":"Izana Kurokawa (Pleine Puissance)", "serie":"Tokyo Revengers", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"", "attaques":[{"nom":"Frappe Impitoyable","emoji":"💢","degats":58,"desc":"Aucun scrupule"},{"nom":"Lecture de Combat","emoji":"👁️","degats":65,"desc":"Copie les mouvements"},{"nom":"Rage du Roi Noir","emoji":"🖤","degats":72,"desc":"Fureur du chef"}], "faiblesse":"⚡", "resistance":"🌟"},
    "chifuyu": {"nom":"Chifuyu Matsuno", "serie":"Tokyo Revengers", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"", "attaques":[{"nom":"Garde du Vice-Capitaine","emoji":"🛡️","degats":42,"desc":"Protège son capitaine"},{"nom":"Contre du Chat","emoji":"🐈","degats":48,"desc":"Riposte agile"},{"nom":"Poing Fidèle","emoji":"👊","degats":54,"desc":"Frappe déterminée"}], "faiblesse":"⚡", "resistance":"🌟"},
    "draken": {"nom":"Ken Ryuguji (Draken)", "serie":"Tokyo Revengers", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/PSZyDlw.jpg", "attaques":[{"nom":"Poing du Dragon","emoji":"🐉","degats":44,"desc":"Frappe massive"},{"nom":"Garde du Corps","emoji":"🛡️","degats":50,"desc":"Encaisse pour son ami"},{"nom":"Bagarre de Rue","emoji":"🔧","degats":55,"desc":"Sale et efficace"}], "faiblesse":"⚡", "resistance":"🌟"},
    "izana": {"nom":"Izana Kurokawa", "serie":"Tokyo Revengers", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"", "attaques":[{"nom":"Frappe Calculée","emoji":"🧠","degats":42,"desc":"Analyse puis frappe"},{"nom":"Charisme Noir","emoji":"🖤","degats":48,"desc":"Rallie ses hommes"},{"nom":"Coup de Pied Volé","emoji":"🦵","degats":54,"desc":"Imite Mikey"}], "faiblesse":"⚡", "resistance":"🌟"},
    "mucho": {"nom":"Mucho", "serie":"Tokyo Revengers", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"", "attaques":[{"nom":"Étranglement","emoji":"🤼","degats":42,"desc":"Prise brutale"},{"nom":"Poids Lourd","emoji":"🏋️","degats":48,"desc":"Écrase l'adversaire"},{"nom":"Sang-Froid","emoji":"🧊","degats":54,"desc":"Ne montre rien"}], "faiblesse":"⚡", "resistance":"🌟"},
    "kokonoi": {"nom":"Kokonoi Hajime", "serie":"Tokyo Revengers", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/T0L4mb4.jpg", "attaques":[{"nom":"Corruption","emoji":"💴","degats":42,"desc":"Achète la victoire"},{"nom":"Coup Fourbe","emoji":"😈","degats":48,"desc":"Frappe par surprise"},{"nom":"Plan Financier","emoji":"📊","degats":54,"desc":"Toujours un budget"}], "faiblesse":"⚡", "resistance":"🌟"},
    "akkun": {"nom":"Akkun", "serie":"Tokyo Revengers", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/PYv67d3.jpg", "attaques":[{"nom":"Poing Désespéré","emoji":"👊","degats":26,"desc":"Frappe de rage"},{"nom":"Loyauté","emoji":"🤝","degats":31,"desc":"Fidèle à Takemichi"},{"nom":"Charge Aveugle","emoji":"💨","degats":36,"desc":"Fonce sans réfléchir"}], "faiblesse":"⚡", "resistance":"🌟"},
    "yamagishi": {"nom":"Yamagishi", "serie":"Tokyo Revengers", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/34FzbI3.jpg", "attaques":[{"nom":"Analyse","emoji":"🤓","degats":24,"desc":"Repère les faiblesses"},{"nom":"Coup Maladroit","emoji":"👊","degats":29,"desc":"Fait ce qu'il peut"},{"nom":"Soutien Moral","emoji":"📣","degats":34,"desc":"Encourage l'équipe"}], "faiblesse":"⚡", "resistance":"🌟"},
    "sakurawb": {"nom":"Haruka Sakura", "serie":"Wind Breaker", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"", "attaques":[{"nom":"Poing de Solitaire","emoji":"👊","degats":58,"desc":"Frappe sèche"},{"nom":"Combo Rapide","emoji":"💥","degats":65,"desc":"Enchaînement brutal"},{"nom":"Fierté de Bofurin","emoji":"🌸","degats":72,"desc":"Protège la ville"}], "faiblesse":"⚡", "resistance":"🌟"},
    "suowb": {"nom":"Tomoya Suo", "serie":"Wind Breaker", "rarete":"Épique", "emoji":"🟣", "pv":210, "attaque":90, "defense":80, "image":"", "attaques":[{"nom":"Art Martial Souple","emoji":"🥋","degats":58,"desc":"Redirige la force"},{"nom":"Contre Parfait","emoji":"🔄","degats":65,"desc":"Retourne l'attaque"},{"nom":"Sourire Impassible","emoji":"😌","degats":72,"desc":"Ne montre jamais rien"}], "faiblesse":"⚡", "resistance":"🌟"},
    "angel": {"nom":"Rin Suzunome", "serie":"Wistoria", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"", "attaques":[{"nom":"Magie de Soutien","emoji":"✨","degats":42,"desc":"Renforce les alliés"},{"nom":"Bouclier Magique","emoji":"🛡️","degats":48,"desc":"Barrière solide"},{"nom":"Encouragement","emoji":"💗","degats":54,"desc":"Redonne courage"}], "faiblesse":"⚡", "resistance":"🌟"},
    "will": {"nom":"Will Serfort", "serie":"Wistoria", "rarete":"Rare", "emoji":"🔵", "pv":185, "attaque":75, "defense":70, "image":"https://i.imgur.com/CXSqYtO.jpg", "attaques":[{"nom":"Épée sans Magie","emoji":"⚔️","degats":43,"desc":"Le seul non-mage"},{"nom":"Danse de Lames","emoji":"🗡️","degats":49,"desc":"Enchaînement fulgurant"},{"nom":"Promesse","emoji":"🤝","degats":55,"desc":"Atteindra le sommet"}], "faiblesse":"⚡", "resistance":"🌟"},
    "fumiya": {"nom":"Fumiya Tomozaki (Bottom-tier Character)", "serie":"Divers", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/DWeuClR.jpg", "attaques":[{"nom":"Analyse Sociale","emoji":"🧠","degats":25,"desc":"Traite la vie comme un jeu"},{"nom":"Stratégie Optimale","emoji":"📊","degats":30,"desc":"Calcule chaque geste"},{"nom":"Progression","emoji":"📈","degats":35,"desc":"Monte lentement mais sûrement"}], "faiblesse":"⚡", "resistance":"🌟"},
    "reginald": {"nom":"Reginald Raizel (Noblesse)", "serie":"Divers", "rarete":"Commun", "emoji":"⚪", "pv":160, "attaque":65, "defense":60, "image":"https://i.imgur.com/1O2BkZE.jpg", "attaques":[{"nom":"Sang Noble","emoji":"🩸","degats":29,"desc":"Pouvoir héréditaire"},{"nom":"Regenerate","emoji":"🩹","degats":34,"desc":"Se reconstitue"},{"nom":"Autorité du Noblesse","emoji":"👑","degats":39,"desc":"Domine par la présence"}], "faiblesse":"⚡", "resistance":"🌟"},
    "rikiep": {"nom":"Riki Nura (Nurarihyon no Mago)", "serie":"Divers", "rarete":"Légendaire", "emoji":"🟠", "pv":225, "attaque":100, "defense":85, "image":"", "attaques":[{"nom":"Meikyo Shisui","emoji":"⚔️","degats":73,"desc":"Lame du Nurarihyon"},{"nom":"Peur","emoji":"👺","degats":81,"desc":"Manipule la terreur"},{"nom":"Chef des Yokai","emoji":"🏯","degats":88,"desc":"Commande cent démons"}], "faiblesse":"⚡", "resistance":"🌟"},
    "rubyroze": {"nom":"Anos Voldigoad Maou (Misfit of Demon King)", "serie":"Divers", "rarete":"Mythique", "emoji":"🔴", "pv":250, "attaque":115, "defense":95, "image":"https://i.imgur.com/Sky6bPd.jpg", "attaques":[{"nom":"Magie de Destruction","emoji":"💥","degats":91,"desc":"Anéantit d'un mot"},{"nom":"Résurrection","emoji":"♾️","degats":100,"desc":"Revient toujours"},{"nom":"Roi Démon Tyrannique","emoji":"👑","degats":109,"desc":"Deux mille ans de puissance"}], "faiblesse":"⚡", "resistance":"🌟"},
    "whitebeard": {"nom":"Barbe Blanche",      "serie":"One Piece",       "rarete":"Mythique",   "emoji":"🌊", "pv":275,"attaque":113,"defense":100,"image":"https://i.imgur.com/hD6V9QR.jpg","attaques":[{"nom":"Gura Gura","emoji":"🌊","degats":100,"desc":"Tremblement de mer"},{"nom":"Tsunami","emoji":"🌊","degats":110,"desc":"Vague géante"},{"nom":"Bisento","emoji":"🪓","degats":90,"desc":"Lance de guerre}"}],"faiblesse":"🔥","resistance":"🌊"},
    "dio":        {"nom":"Dio Brando",         "serie":"JoJo",            "rarete":"Mythique",   "emoji":"🧛", "pv":260,"attaque":111,"defense":92,"image":"https://i.imgur.com/sZdHO5z.jpg","attaques":[{"nom":"Za Warudo","emoji":"🕐","degats":95,"desc":"Stop time"},{"nom":"Knife","emoji":"🗡️","degats":75,"desc":"Couteaux gelés"},{"nom":"Road Roller","emoji":"🚗","degats":105,"desc":"écrase tout}"}],"faiblesse":"☀️","resistance":"🧛"},
    "giorno":     {"nom":"Giorno Giovanna",    "serie":"JoJo",            "rarete":"Mythique",   "emoji":"🌟", "pv":255,"attaque":110,"defense":90,"image":"https://i.imgur.com/sndc2al.jpg","attaques":[{"nom":"Gold Experience","emoji":"🌟","degats":85,"desc":"Donne la vie"},{"nom":"GER","emoji":"♾️","degats":110,"desc":"Retour à zéro"},{"nom":"Requin","emoji":"🦈","degats":90,"desc":"Transformation"}],"faiblesse":"💀","resistance":"🌟"},
    "makima":     {"nom":"Makima",             "serie":"Chainsaw Man",    "rarete":"Mythique",   "emoji":"👁️", "pv":260,"attaque":112,"defense":96,"image":"https://i.imgur.com/OxiYDGt.jpg","attaques":[{"nom":"Contrôle","emoji":"👁️","degats":95,"desc":"Contrôle tout"},{"nom":"Force","emoji":"💥","degats":100,"desc":"Accumule les morts"},{"nom":"Déesse","emoji":"🌸","degats":110,"desc":"Concept de contrôle}"}],"faiblesse":"💔","resistance":"👁️"},
    "netero":     {"nom":"Netero",             "serie":"HunterxHunter",   "rarete":"Mythique",   "emoji":"🙏", "pv":255,"attaque":113,"defense":90,"image":"https://i.imgur.com/hucISaO.jpg","attaques":[{"nom":"100 Type Guanyin","emoji":"🙏","degats":91,"desc":"Bouddha divin"},{"nom":"Poor Man's Rose","emoji":"☢️","degats":110,"desc":"Bombe nucléaire"},{"nom":"Vitesse","emoji":"⚡","degats":88,"desc":"Vitesse ultime}"}],"faiblesse":"♟️","resistance":"🙏"},
    "cid":        {"nom":"Cid Kagenou",        "serie":"The Eminence in Shadow","rarete":"Mythique","emoji":"🌑","pv":270,"attaque":112,"defense":92,"image":"https://i.imgur.com/d0emxwc.jpg","attaques":[{"nom":"I Am Atomic","emoji":"🌑","degats":110,"desc":"Destruction totale"},{"nom":"Shadow","emoji":"👤","degats":95,"desc":"Magie des ombres"},{"nom":"Flashy","emoji":"💥","degats":105,"desc":"Style spectaculaire}"}],"faiblesse":"✨","resistance":"🌑"},
    # ── LÉGENDAIRE ───────────────────────────────────────────
    "ace":        {"nom":"Portgas D. Ace",     "serie":"One Piece",       "rarete":"Légendaire", "emoji":"🔥", "pv":220,"attaque":98,"defense":78,"image":"https://i.imgur.com/MLPIlkk.jpg","attaques":[{"nom":"Mera Mera","emoji":"🔥","degats":70,"desc":"Feu absolu"},{"nom":"Hiken","emoji":"🔥","degats":80,"desc":"Poing de feu"},{"nom":"Entei","emoji":"☀️","degats":90,"desc":"Soleil de feu}"}],"faiblesse":"💧","resistance":"🔥"},
    "law":        {"nom":"Trafalgar Law",      "serie":"One Piece",       "rarete":"Légendaire", "emoji":"⚔️", "pv":210,"attaque":96,"defense":82,"image":"https://i.imgur.com/FIOCksy.jpg","attaques":[{"nom":"Room","emoji":"⚔️","degats":65,"desc":"Espace chirurgical"},{"nom":"Shambles","emoji":"🔄","degats":75,"desc":"Téléporte organes"},{"nom":"Gamma Knife","emoji":"💛","degats":85,"desc":"Détruit l'énergie}"}],"faiblesse":"🔥","resistance":"⚔️"},
    "sanji":      {"nom":"Sanji",              "serie":"One Piece",       "rarete":"Légendaire", "emoji":"🦵", "pv":215,"attaque":97,"defense":80,"image":"https://i.imgur.com/w4Xvi0m.jpg","attaques":[{"nom":"Ifrit Jambe","emoji":"🔥","degats":85,"desc":"Jambe de feu"},{"nom":"Diable Jambe","emoji":"🦵","degats":75,"desc":"Coup enflammé"},{"nom":"Germa","emoji":"⚡","degats":80,"desc":"Exosquelette}"}],"faiblesse":"💧","resistance":"🦵"},
    "robin":      {"nom":"Nico Robin",         "serie":"One Piece",       "rarete":"Légendaire", "emoji":"🌸", "pv":195,"attaque":88,"defense":78,"image":"https://i.imgur.com/HrbMy5H.jpg","attaques":[{"nom":"Cien Fleur","emoji":"🌸","degats":60,"desc":"Cent mains"},{"nom":"Gigante Fleur","emoji":"🌺","degats":80,"desc":"Forme géante"},{"nom":"Mil Fleur","emoji":"💐","degats":70,"desc":"Mille fleurs}"}],"faiblesse":"🔥","resistance":"🌸"},
    "jiraiya":    {"nom":"Jiraiya",            "serie":"Naruto",          "rarete":"Légendaire", "emoji":"🐸", "pv":220,"attaque":97,"defense":82,"image":"https://i.imgur.com/5oueuVT.jpg","attaques":[{"nom":"Rasengan","emoji":"🌀","degats":70,"desc":"Maître du Rasengan"},{"nom":"Crapaud Sage","emoji":"🐸","degats":85,"desc":"Mode sage"},{"nom":"Summoning","emoji":"🌊","degats":80,"desc":"Invocation crapaud}"}],"faiblesse":"⚡","resistance":"🐸"},
    "tsunade":    {"nom":"Tsunade",            "serie":"Naruto",          "rarete":"Légendaire", "emoji":"💚", "pv":230,"attaque":95,"defense":90,"image":"https://i.imgur.com/Q0HAKjM.jpg","attaques":[{"nom":"Frappe","emoji":"💚","degats":86,"desc":"Force surhumaine"},{"nom":"Byakugou","emoji":"💎","degats":90,"desc":"Sceau de force"},{"nom":"Soin","emoji":"✚","degats":72,"desc":"Guérison ultime}"}],"faiblesse":"⚡","resistance":"💚"},
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
# ── D. Niveau de carte (XP de combat) ──────────────────────
card_xp = defaultdict(lambda: defaultdict(int))      # {uid: {card_key: xp}}
card_level = defaultdict(lambda: defaultdict(lambda: 1))  # {uid: {card_key: level}}
CARD_XP_PER_LEVEL = 100        # XP nécessaire par niveau
CARD_LEVEL_MAX = 10            # Niveau max d'une carte
CARD_XP_WIN = 30               # XP gagné par la carte en cas de victoire
CARD_XP_LOSE = 10              # XP gagné même en défaite
# ── F. Collection par série (badges) ───────────────────────
serie_badges = defaultdict(set)   # {uid: {serie1, serie2}} — séries complétées
# ── Boutique 5 : limite de favoris ─────────────────────────
fav_slots = defaultdict(lambda: 3)  # {uid: nombre de slots favoris} — 3 par défaut

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
shield_active = {}     # {uid: shield_end_timestamp}
rarity_boost = {}      # {uid: rolls_restants_avec_boost}
daily_item_usage = defaultdict(lambda: defaultdict(float))  # {uid: {item_id: last_use_timestamp}}

# Probabilités gacha
RARETE_EMOJI = {
    "Mythique":   "💎",
    "Légendaire": "👑",
    "Épique":     "🔮",
    "Rare":       "💠",
    "Commun":     "▫️",
}

RARETE_COULEURS = {
    "Mythique":   0xe74c3c,
    "Légendaire": 0xe67e22,
    "Épique":     0x9b59b6,
    "Rare":       0x3498db,
    "Commun":     0x95a5a6,
}

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

@bot.command(name="setrollreset")
@commands.has_permissions(administrator=True)
async def setrollreset(ctx, heures: int = None):
    """Configure le temps de recharge des rolls — .setrollreset <heures>"""
    global ROLLS_RESET_HOURS
    if not heures or heures < 1 or heures > 24:
        return await ctx.send("❌ Précise un nombre d'heures entre 1 et 24 ! Ex: `.setrollreset 6`")
    ROLLS_RESET_HOURS = heures
    await ctx.send(f"✅ Rolls rechargés toutes les **{heures}h** maintenant !")

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

invite_counts   = defaultdict(int)   # {inviter_user_id: count}
guild_invites   = {}   # cache {guild_id: {code: uses}}
SALON_INVITATION_ID = None  # salon où afficher les invitations

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
    if inventaire[uid].get(itype, 0) <= 0:
        return await ctx.send(f"❌ Tu n'as pas l'item `{itype}` ! Achète-le avec `.acheter {itype}`")

    # Vérif amulette sur la cible
    if amulette_active.get(uid_cible, 0) > now_ts:
        inventaire[uid][itype] -= 1
        return await ctx.send(embed=discord.Embed(
            title="🪬 Amulette activée !",
            description=f"**{cible.display_name}** est protégé par une **Amulette** ! Le sabotage se retourne contre **{ctx.author.mention}** ! 😈",
            color=0x9b59b6
        ))

    # Vérif protection divine
    if shield_active.get(uid_cible, 0) > now_ts:
        inventaire[uid][itype] -= 1
        restant = int((shield_active[uid_cible] - now_ts) // 60)
        return await ctx.send(f"🌟 **{cible.display_name}** est sous **Protection Divine** ! ({restant} min restantes)")

    # Vérif bouclier basique
    if itype in ("freeze","curse") and uid_cible in shield_active and shield_active[uid_cible] > now_ts:
        return await ctx.send(f"🛡️ **{cible.display_name}** est protégé par un bouclier !")

    # Consommer l'item
    inventaire[uid][itype] -= 1

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
        ghost_cards[f"{uid_cible}_{ghost_key}"] = now_ts + 1800  # 30 min
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
        malediction_active[uid_cible] = now_ts + 3600  # 1h
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

# ============================================================
#  COMMANDES SUPPLÉMENTAIRES RÉCUPÉRÉES
# ============================================================

@bot.command(name="invoke")
async def invoke_cmd(ctx):
    """Invocation garantie Légendaire+ — .invoke (10 000 pièces)"""
    if SALON_GACHA_ID and ctx.channel.id != SALON_GACHA_ID:
        salon = ctx.guild.get_channel(SALON_GACHA_ID)
        mention = salon.mention if salon else "le salon gacha"
        return await ctx.send(f"🎰 Invocation dans {mention} !", delete_after=5)
    uid = str(ctx.author.id)
    if not ANIME_CARDS_DB:
        return await ctx.send("❌ Aucune carte disponible !")
    cout = 10000
    if economy_data[uid]["coins"] < cout:
        return await ctx.send(f"❌ Il te faut **{cout} pièces** ! Tu en as **{economy_data[uid]['coins']}**.")
    pool = [k for k, c in ANIME_CARDS_DB.items() if c["rarete"] in ("Légendaire", "Mythique")]
    if not pool:
        pool = list(ANIME_CARDS_DB.keys())
    economy_data[uid]["coins"] -= cout
    key = random.choice(pool)
    embed = build_card_embed(key)
    embed.set_author(name=f"✨  Invocation Garantie de {ctx.author.display_name}")
    if key in claimed_cards:
        await ctx.send(embed=embed)
    else:
        view = ClaimView(key, timeout=30)
        view.message = await ctx.send(embed=embed, view=view)

@bot.command(name="cartefav")
async def cartefav_cmd(ctx, action: str = None, *, perso: str = None):
    """Gérer tes cartes favorites — .cartefav add/remove/voir <perso>"""
    uid = str(ctx.author.id)
    if not hasattr(bot, 'cartes_fav'):
        bot.cartes_fav = {}
    if uid not in bot.cartes_fav:
        bot.cartes_fav[uid] = []
    favs = bot.cartes_fav[uid]
    if not action or action == "voir":
        if not favs:
            return await ctx.send(f"⭐ Tu n'as aucune carte favorite ! *(limite : {fav_slots[uid]} slots)*")
        lines = []
        for k in favs:
            if k in ANIME_CARDS_DB:
                c = ANIME_CARDS_DB[k]
                lines.append(f"{RARETE_EMOJI.get(c['rarete'],'⚪')} **{c['nom']}** — *{c['serie']}*")
        return await ctx.send(embed=discord.Embed(title="⭐ Tes Cartes Favorites", description="\n".join(lines), color=0xf1c40f))
    if not perso:
        return await ctx.send("❌ `.cartefav add/remove/voir <perso>`")
    key = perso.lower().strip().replace(" ","")
    if key not in ANIME_CARDS_DB:
        matches = [k for k in ANIME_CARDS_DB if perso.lower() in ANIME_CARDS_DB[k]["nom"].lower()]
        if not matches:
            return await ctx.send(f"❌ `{perso}` introuvable !")
        key = matches[0]
    c = ANIME_CARDS_DB[key]
    if action == "add":
        limite = fav_slots[uid]
        if len(favs) >= limite:
            return await ctx.send(f"❌ Maximum {limite} cartes favorites ! Achète des **Slots Favoris** en boutique pour augmenter la limite 🔓")
        if key in favs:
            return await ctx.send("❌ Déjà dans tes favoris !")
        favs.append(key)
        await ctx.send(f"⭐ **{c['nom']}** ajouté à tes favoris !")
    elif action == "remove":
        if key in favs:
            favs.remove(key)
            await ctx.send(f"❌ **{c['nom']}** retiré des favoris !")
        else:
            await ctx.send("❌ Cette carte n'est pas dans tes favoris !")

@bot.command(name="liga")
async def liga_cmd(ctx):
    """Classement Elo mensuel — .liga"""
    if not xp_data:
        return await ctx.send("❌ Aucune donnée disponible !")
    sorted_data = sorted(xp_data.items(), key=lambda x: x[1]["level"] * 100 + x[1]["xp"], reverse=True)[:10]
    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, (uid, data) in enumerate(sorted_data):
        medal = medals[i] if i < 3 else f"`{i+1}.`"
        m = ctx.guild.get_member(int(uid))
        name = m.display_name if m else f"<@{uid}>"
        lines.append(f"{medal} **{name}** — Niv.{data['level']} • {economy_data[uid]['coins']} pièces")
    embed = discord.Embed(title="🏆 Liga QG Kdrama — Classement Mensuel", description="\n".join(lines), color=0xf1c40f)
    await ctx.send(embed=embed)

@bot.command(name="faction")
async def faction_cmd(ctx, action: str = None, *, args: str = None):
    """Système de factions — .faction"""
    FACTIONS = {
        "kdrama": {"nom": "🎬 Clan Kdrama", "desc": "Pour les fans de dramas coréens"},
        "anime": {"nom": "⚔️ Clan Anime", "desc": "Pour les fans d'animés"},
        "gaming": {"nom": "🎮 Clan Gaming", "desc": "Pour les gamers du QG"},
    }
    if not hasattr(bot, 'factions_membres'):
        bot.factions_membres = {}
    uid = str(ctx.author.id)
    if not action:
        embed = discord.Embed(title="⚔️ Factions du QG", color=0xff6b9d)
        for fid, f in FACTIONS.items():
            membres = sum(1 for v in bot.factions_membres.values() if v == fid)
            embed.add_field(name=f"{f['nom']} (`{fid}`)", value=f"{f['desc']}\n👥 {membres} membres", inline=False)
        embed.set_footer(text=".faction rejoindre <id> pour rejoindre")
        return await ctx.send(embed=embed)
    if action == "rejoindre":
        fid = args.lower().strip() if args else ""
        if fid not in FACTIONS:
            return await ctx.send(f"❌ Faction invalide ! Choisis : {', '.join(FACTIONS.keys())}")
        bot.factions_membres[uid] = fid
        await ctx.send(embed=discord.Embed(description=f"✅ Tu as rejoint **{FACTIONS[fid]['nom']}** !", color=0x2ecc71))
    elif action == "info":
        fid = bot.factions_membres.get(uid)
        if not fid:
            return await ctx.send("❌ Tu n'es dans aucune faction !")
        f = FACTIONS[fid]
        membres = sum(1 for v in bot.factions_membres.values() if v == fid)
        await ctx.send(embed=discord.Embed(title=f"⚔️ {f['nom']}", description=f"{f['desc']}\n👥 {membres} membres", color=0xff6b9d))
    elif action == "classement":
        from collections import Counter
        counts = Counter(bot.factions_membres.values())
        lines = [f"**{FACTIONS[fid]['nom']}** — {n} membres" for fid, n in counts.most_common() if fid in FACTIONS]
        await ctx.send(embed=discord.Embed(title="🏆 Classement Factions", description="\n".join(lines) or "Aucune donnée", color=0xf1c40f))

@bot.command(name="leavefaction")
async def leavefaction_cmd(ctx):
    """Quitter sa faction"""
    if not hasattr(bot, 'factions_membres'):
        bot.factions_membres = {}
    uid = str(ctx.author.id)
    if uid in bot.factions_membres:
        del bot.factions_membres[uid]
        await ctx.send("✅ Tu as quitté ta faction !")
    else:
        await ctx.send("❌ Tu n'es dans aucune faction !")

# ============================================================
#  E. BURN / RECYCLAGE — Détruire une carte contre des pièces
# ============================================================
@bot.command(name="burn", aliases=["recycler", "bruler"])
async def burn_cmd(ctx, *, perso: str = None):
    """Détruit une carte que tu possèdes contre des pièces — .burn <perso>"""
    if SALON_GACHA_ID and ctx.channel.id != SALON_GACHA_ID:
        salon = ctx.guild.get_channel(SALON_GACHA_ID)
        mention = salon.mention if salon else "le salon gacha"
        return await ctx.send(f"🎰 Le recyclage c'est dans {mention} !", delete_after=5)
    if not perso:
        return await ctx.send("❌ Usage : `.burn <perso>`\n*Détruit une carte contre des pièces selon sa rareté.*")
    uid = str(ctx.author.id)
    key = perso.lower().strip().replace(" ", "")
    if key not in ANIME_CARDS_DB:
        matches = [k for k in ANIME_CARDS_DB if perso.lower() in ANIME_CARDS_DB[k]["nom"].lower()]
        if not matches:
            return await ctx.send(f"❌ Personnage `{perso}` introuvable !")
        key = matches[0]
    if claimed_cards.get(key) != uid:
        return await ctx.send("❌ Tu ne possèdes pas cette carte !")
    c = ANIME_CARDS_DB[key]
    # Valeur de burn selon rareté
    burn_values = {"Commun": 100, "Rare": 300, "Épique": 700, "Légendaire": 1500, "Mythique": 4000}
    gain = burn_values.get(c["rarete"], 100)
    # Bonus selon fusion et niveau
    fus = fusion_levels[uid].get(key, 0)
    lvl = card_level[uid].get(key, 1)
    bonus = fus * 200 + (lvl - 1) * 50
    total = gain + bonus
    r_emoji = RARETE_EMOJI.get(c["rarete"], "🔵")
    # Confirmation
    embed = discord.Embed(
        title="🔥 Recycler cette carte ?",
        description=(
            f"{r_emoji} **{c['nom']}** — *{c['serie']}*\n"
            f"{'⭐'*fus if fus else ''} {'`Niv.'+str(lvl)+'`' if lvl > 1 else ''}\n\n"
            f"💰 Tu recevras **{total:,} pièces**"
            + (f" *(base {gain} + bonus {bonus})*" if bonus else "")
            + "\n\n⚠️ **Action irréversible !** Clique sur **Confirmer**."
        ),
        color=0xe67e22
    )
    if c.get("image"):
        embed.set_thumbnail(url=c["image"])
    view = ConfirmView(ctx.author, timeout=30)
    msg = await ctx.send(embed=embed, view=view)
    await view.wait()
    if view.value:
        del claimed_cards[key]
        gacha_collections[uid].pop(key, None)
        fusion_levels[uid].pop(key, None)
        card_level[uid].pop(key, None)
        card_xp[uid].pop(key, None)
        economy_data[uid]["coins"] += total
        track_stat(uid, "burns", channel=ctx.channel)
        await msg.edit(embed=discord.Embed(
            title="🔥 Carte recyclée !",
            description=f"**{c['nom']}** a été détruite.\n💰 **+{total:,} pièces** ! (total : {economy_data[uid]['coins']:,})",
            color=0x2ecc71
        ), view=None)
    elif view.value is False:
        await msg.edit(embed=discord.Embed(description="❌ Recyclage annulé.", color=0x95a5a6), view=None)
    else:
        await msg.edit(embed=discord.Embed(description="⏰ Recyclage annulé (timeout).", color=0x95a5a6), view=None)

# ============================================================
#  F. COLLECTION PAR SÉRIE — Voir progression & récompenses
# ============================================================
@bot.command(name="serie", aliases=["series", "collectionserie"])
async def serie_cmd(ctx, *, nom_serie: str = None):
    """Voir ta progression sur une série et réclamer la récompense — .serie <nom>"""
    uid = str(ctx.author.id)
    # Liste toutes les séries
    toutes_series = sorted(set(c["serie"] for c in ANIME_CARDS_DB.values()))
    if not nom_serie:
        # Afficher la progression globale
        embed = discord.Embed(
            title="📚 Tes Collections par Série",
            description="Complète une série entière pour gagner un **badge** et des **pièces** !\n`.serie <nom>` pour les détails.",
            color=0x9b59b6
        )
        lignes = []
        for serie in toutes_series:
            complete, owned, total = check_serie_complete(uid, serie)
            if owned > 0:  # Ne montrer que les séries entamées
                badge = "🏅" if serie in serie_badges[uid] else ("✅" if complete else "")
                lignes.append(f"{badge} **{serie}** — {owned}/{total}")
        if lignes:
            # Paginer si trop long
            chunk = "\n".join(lignes[:25])
            embed.add_field(name="📊 Progression", value=chunk, inline=False)
        else:
            embed.add_field(name="📊 Progression", value="*Tu n'as encore aucune carte ! Fais `.ga` pour commencer.*", inline=False)
        embed.set_footer(text=f"{len(toutes_series)} séries au total dans le gacha")
        return await ctx.send(embed=embed)
    # Détails d'une série précise
    match_serie = next((s for s in toutes_series if nom_serie.lower() in s.lower()), None)
    if not match_serie:
        return await ctx.send(f"❌ Série `{nom_serie}` introuvable !\n*Exemples : Naruto, One Piece, Bleach...*")
    serie_keys = get_serie_cards(match_serie)
    owned_keys = [k for k in serie_keys if k in gacha_collections[uid]]
    complete = len(owned_keys) == len(serie_keys)
    # Liste des cartes possédées / manquantes
    order = ["Mythique", "Légendaire", "Épique", "Rare", "Commun"]
    serie_keys_sorted = sorted(serie_keys, key=lambda k: order.index(ANIME_CARDS_DB[k]["rarete"]))
    lignes = []
    for k in serie_keys_sorted:
        c = ANIME_CARDS_DB[k]
        r = RARETE_EMOJI.get(c["rarete"], "⚪")
        if k in owned_keys:
            lignes.append(f"✅ {r} {c['nom']}")
        else:
            lignes.append(f"⬜ {r} ||{c['nom']}||")
    embed = discord.Embed(
        title=f"📚 Collection — {match_serie}",
        description=f"**{len(owned_keys)}/{len(serie_keys)}** cartes possédées",
        color=0x2ecc71 if complete else 0x9b59b6
    )
    # Paginer la liste si trop longue
    txt = "\n".join(lignes)
    if len(txt) > 1000:
        txt = txt[:1000] + "\n*...(liste tronquée)*"
    embed.add_field(name="Cartes", value=txt, inline=False)
    # Récompense
    if complete:
        reward = serie_reward(len(serie_keys))
        if match_serie in serie_badges[uid]:
            embed.add_field(name="🏅 Badge obtenu", value=f"Tu as déjà réclamé la récompense de **{reward:,} pièces** !", inline=False)
        else:
            serie_badges[uid].add(match_serie)
            economy_data[uid]["coins"] += reward
            unlock_achievement(uid, "serie_1", ctx.channel)
            embed.add_field(
                name="🎉 SÉRIE COMPLÉTÉE !",
                value=f"🏅 Badge **{match_serie}** débloqué !\n💰 **+{reward:,} pièces** de récompense !",
                inline=False
            )
            embed.color = 0xf1c40f
    else:
        manquantes = len(serie_keys) - len(owned_keys)
        reward = serie_reward(len(serie_keys))
        embed.set_footer(text=f"Encore {manquantes} carte(s) pour le badge + {reward:,} pièces !")
    await ctx.send(embed=embed)

# ============================================================
#  D. CARDINFO — Voir les détails d'une carte (niveau, XP)
# ============================================================
@bot.command(name="cardinfo", aliases=["carte", "cardstats"])
async def cardinfo_cmd(ctx, *, perso: str = None):
    """Voir les stats détaillées d'une de tes cartes — .cardinfo <perso>"""
    if not perso:
        return await ctx.send("❌ Usage : `.cardinfo <perso>`")
    uid = str(ctx.author.id)
    key = perso.lower().strip().replace(" ", "")
    if key not in ANIME_CARDS_DB:
        matches = [k for k in ANIME_CARDS_DB if perso.lower() in ANIME_CARDS_DB[k]["nom"].lower()]
        if not matches:
            return await ctx.send(f"❌ Personnage `{perso}` introuvable !")
        key = matches[0]
    c = ANIME_CARDS_DB[key]
    r_emoji = RARETE_EMOJI.get(c["rarete"], "🔵")
    couleur = RARETE_COULEURS.get(c["rarete"], 0x95a5a6)
    owner = claimed_cards.get(key)
    is_owner = owner == uid
    # Stats avec bonus
    fus = fusion_levels[uid].get(key, 0) if is_owner else 0
    lvl = card_level[uid].get(key, 1) if is_owner else 1
    xp = card_xp[uid].get(key, 0) if is_owner else 0
    b_pv, b_atk, b_def = card_total_bonus(uid, key) if is_owner else (0, 0, 0)
    embed = discord.Embed(
        title=f"{r_emoji} {c['nom']} {'⭐'*fus}",
        description=f"*{c['serie']}* — **{c['rarete']}**",
        color=couleur
    )
    if c.get("image"):
        embed.set_image(url=c["image"])
    embed.add_field(
        name="📊 Stats actuelles",
        value=(
            f"❤️ **PV** : {c['pv'] + b_pv} *(+{b_pv})*\n"
            f"⚔️ **ATK** : {c['attaque'] + b_atk} *(+{b_atk})*\n"
            f"🛡️ **DEF** : {c['defense'] + b_def} *(+{b_def})*"
        ),
        inline=True
    )
    if is_owner:
        # Barre d'XP
        if lvl < CARD_LEVEL_MAX:
            bar_filled = int((xp / CARD_XP_PER_LEVEL) * 10)
            bar = "█"*bar_filled + "░"*(10-bar_filled)
            xp_txt = f"`{bar}` {xp}/{CARD_XP_PER_LEVEL}"
        else:
            xp_txt = "🌟 **NIVEAU MAX !**"
        embed.add_field(
            name=f"🆙 Niveau de combat : {lvl}/{CARD_LEVEL_MAX}",
            value=f"⭐ Fusion : {fus}/3\n{xp_txt}",
            inline=True
        )
        embed.set_footer(text="💡 Combats en pokebattle pour faire monter le niveau !")
    else:
        if owner:
            m = ctx.guild.get_member(int(owner))
            embed.set_footer(text=f"Possédée par {m.display_name if m else 'quelqu’un'}")
        else:
            embed.set_footer(text="Carte disponible — personne ne la possède !")
    await ctx.send(embed=embed)

@bot.command(name="gachastats")
async def gachastats_cmd(ctx):
    """Classement des collections — .gachastats"""
    if not gacha_collections:
        return await ctx.send("❌ Aucune collection existante !")
    sorted_col = sorted(gacha_collections.items(), key=lambda x: len(x[1]), reverse=True)[:10]
    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, (uid, col) in enumerate(sorted_col):
        medal = medals[i] if i < 3 else f"`{i+1}.`"
        m = ctx.guild.get_member(int(uid))
        name = m.display_name if m else f"<@{uid}>"
        lines.append(f"{medal} **{name}** — {len(col)} cartes")
    await ctx.send(embed=discord.Embed(title="🏆 Top Collectionneurs", description="\n".join(lines), color=0x9b59b6))

@bot.command(name="tradeshistory")
async def tradeshistory_cmd(ctx):
    """Historique des échanges — .tradeshistory"""
    if not hasattr(bot, 'trades_history'):
        bot.trades_history = []
    if not bot.trades_history:
        return await ctx.send("📋 Aucun échange enregistré !")
    recents = bot.trades_history[-10:]
    lines = [f"• {t}" for t in reversed(recents)]
    await ctx.send(embed=discord.Embed(title="🔄 Historique des Échanges", description="\n".join(lines), color=0x3498db))

@bot.command(name="raidstop")
@commands.has_permissions(manage_guild=True)
async def raidstop_cmd(ctx):
    """Arrêter le raid/boss en cours — .raidstop"""
    if not active_boss:
        return await ctx.send("❌ Aucun raid/boss en cours !")
    active_boss.clear()
    await ctx.send(embed=discord.Embed(description="🛑 Raid/Boss arrêté !", color=0xe74c3c))

@bot.command(name="marcheacheter")
async def marcheacheter_cmd(ctx, *, perso: str = None):
    """Acheter une carte au Marché Noir — .marcheacheter <perso>"""
    if not perso:
        return await ctx.send("❌ `.marcheacheter <perso>`")
    uid = str(ctx.author.id)
    key = perso.lower().strip().replace(" ","")
    if key not in ANIME_CARDS_DB:
        matches = [k for k in ANIME_CARDS_DB if perso.lower() in ANIME_CARDS_DB[k]["nom"].lower()]
        if not matches:
            return await ctx.send(f"❌ `{perso}` introuvable !")
        key = matches[0]
    c = ANIME_CARDS_DB[key]
    prix = {"Commun": 500, "Rare": 1200, "Épique": 2500, "Légendaire": 5000, "Mythique": 12000}
    cout = prix.get(c["rarete"], 1000)
    if key in claimed_cards:
        return await ctx.send(f"❌ **{c['nom']}** appartient déjà à quelqu'un !")
    if economy_data[uid]["coins"] < cout:
        return await ctx.send(f"❌ Il te faut **{cout} pièces** ! (Marché Noir 🕶️)")
    economy_data[uid]["coins"] -= cout
    claimed_cards[key] = uid
    gacha_collections[uid][key] = {"fusion": 0}
    embed = discord.Embed(
        title="🕶️ Marché Noir — Achat réussi !",
        description=f"{RARETE_EMOJI.get(c['rarete'],'⚪')} **{c['nom']}** acquis pour **{cout} pièces** !",
        color=0x2c3e50
    )
    if c.get("image"):
        embed.set_thumbnail(url=c["image"])
    await ctx.send(embed=embed)

# Tracking missions
missions_progress = defaultdict(lambda: {"messages": 0, "rolls": 0, "daily": 0, "wins": 0, "quiz": 0, "claimed": False})

@bot.command(name="missions", aliases=["mission","quetes"])
async def missions_cmd(ctx):
    """Missions journalières avec récompenses — .missions"""
    uid = str(ctx.author.id)
    import time as _t
    if not hasattr(bot, 'missions_data'):
        bot.missions_data = {}
    now = _t.time()
    last = bot.missions_data.get(uid, {}).get("reset", 0)
    
    # Reset journalier
    if now - last >= 86400:
        # Reset le progrès
        missions_progress[uid] = {"messages": 0, "rolls": 0, "daily": 0, "wins": 0, "quiz": 0, "claimed": False}
        bot.missions_data[uid] = {"reset": now, "claimed": False}
    
    prog = missions_progress[uid]
    
    # Définir les missions du jour avec leur progression actuelle
    missions = [
        {"id": "messages", "desc": "💬 Envoyer 20 messages",        "cible": 20, "prog": prog["messages"], "reward_coins": 100, "reward_xp": 20},
        {"id": "rolls",    "desc": "🎰 Faire 3 rolls gacha",         "cible": 3,  "prog": prog["rolls"],    "reward_coins": 150, "reward_xp": 30},
        {"id": "daily",    "desc": "💰 Utiliser .daily",             "cible": 1,  "prog": prog["daily"],    "reward_coins": 80,  "reward_xp": 15},
        {"id": "quiz",     "desc": "🎯 Répondre juste au quiz 2x",   "cible": 2,  "prog": prog["quiz"],     "reward_coins": 120, "reward_xp": 25},
        {"id": "wins",     "desc": "⚔️ Gagner 1 combat (arène/quiz)", "cible": 1, "prog": prog["wins"],     "reward_coins": 200, "reward_xp": 50},
    ]
    
    embed = discord.Embed(
        title="📋 Missions Journalières",
        description=f"**{ctx.author.display_name}** — Reset dans {int((86400 - (now - last)) / 3600)}h",
        color=0x3498db
    )
    
    total_coins_done = 0
    total_xp_done = 0
    nb_done = 0
    
    for m in missions:
        bar_filled = int((min(m["prog"], m["cible"]) / m["cible"]) * 10)
        bar = "█"*bar_filled + "░"*(10-bar_filled)
        done = m["prog"] >= m["cible"]
        status = "✅" if done else "⏳"
        embed.add_field(
            name=f"{status} {m['desc']}",
            value=f"`{bar}` **{min(m['prog'], m['cible'])}/{m['cible']}** — 🪙 +{m['reward_coins']} • ⭐ +{m['reward_xp']} XP",
            inline=False
        )
        if done:
            total_coins_done += m["reward_coins"]
            total_xp_done += m["reward_xp"]
            nb_done += 1
    
    # CRITIQUE: Distribuer les récompenses si pas déjà claimed
    claimed = bot.missions_data.get(uid, {}).get("claimed", False)
    if nb_done > 0 and not claimed:
        # Récompenses bonus si toutes les missions sont faites
        bonus_coins = 250 if nb_done == len(missions) else 0
        bonus_xp = 50 if nb_done == len(missions) else 0
        
        economy_data[uid]["coins"] += total_coins_done + bonus_coins
        xp_data[uid]["xp"] += total_xp_done + bonus_xp
        bot.missions_data[uid]["claimed"] = True
        
        msg = f"💰 **+{total_coins_done} pièces** & **+{total_xp_done} XP** récupérés !"
        if bonus_coins > 0:
            msg += f"\n🎉 **BONUS TOUTES MISSIONS** : +{bonus_coins} pièces & +{bonus_xp} XP !"
        embed.set_footer(text=msg)
    elif claimed:
        embed.set_footer(text=f"✅ Récompenses du jour déjà récupérées ({total_coins_done} pièces)")
    else:
        embed.set_footer(text="💡 Complète des missions pour gagner pièces et XP !")
    
    await ctx.send(embed=embed)

# ============================================================
#  LOUP GAROU — DONNÉES
# ============================================================
LG_ROLES = {
    "Loup Garou":   {"emoji": "🐺", "desc": "Élimine un villageois chaque nuit. Reste caché !", "team": "loups"},
    "Loup Blanc":   {"emoji": "🤍", "desc": "Loup solitaire — peut éliminer les autres loups la nuit.", "team": "loup_blanc"},
    "Villageois":   {"emoji": "👨‍🌾", "desc": "Trouve et élimine les loups le jour. Tu n'as pas de pouvoir spécial.", "team": "village"},
    "Voyante":      {"emoji": "🔮", "desc": "Chaque nuit, découvre le rôle d'un joueur.", "team": "village"},
    "Sorcière":     {"emoji": "🧙‍♀️", "desc": "Possède 2 potions : 1 pour sauver, 1 pour tuer. Usage unique chacune.", "team": "village"},
    "Chasseur":     {"emoji": "🏹", "desc": "Quand tu meurs, tu peux emporter quelqu'un avec toi.", "team": "village"},
    "Cupidon":      {"emoji": "💘", "desc": "Au début, lie 2 joueurs. S'ils sont séparés, ils meurent ensemble.", "team": "village"},
    "Petite Fille": {"emoji": "👧", "desc": "Peut espionner les loups la nuit — mais si tu te fais attraper, tu meurs !", "team": "village"},
}

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


# ============================================================
#  🐺 LOUP GAROU — Interfaces cliquables par rôle
# ============================================================
def _lg_options(game, guild, exclure=(), loups_visibles=False):
    """Construit la liste déroulante des joueurs vivants"""
    opts = []
    for uid, p in game["players"].items():
        if not p["alive"] or uid in exclure:
            continue
        emoji = "🐺" if (loups_visibles and p["role"] in ("Loup Garou", "Loup Blanc")) else "👤"
        opts.append(discord.SelectOption(label=p["name"][:100], value=str(uid), emoji=emoji))
    return opts[:25]

class LGCibleSelect(ui.Select):
    """Menu déroulant générique de désignation"""
    def __init__(self, options, placeholder):
        super().__init__(placeholder=placeholder, options=options, min_values=1, max_values=1)

    async def callback(self, interaction):
        await self.view.choisir(interaction, int(self.values[0]))

class LGLoupsView(ui.View):
    """🐺 Vote de la meute — majorité l'emporte"""
    def __init__(self, game, gid, ctx, timeout=LG_DUREE_NUIT):
        super().__init__(timeout=timeout)
        self.game, self.gid, self.ctx = game, gid, ctx
        self.message = None
        opts = _lg_options(game, ctx.guild,
                           exclure=[u for u, p in game["players"].items()
                                    if p["role"] in ("Loup Garou", "Loup Blanc")])
        self.add_item(LGCibleSelect(opts, "🎯 Désigner une victime…"))

    async def interaction_check(self, interaction):
        p = self.game["players"].get(interaction.user.id)
        if not p or not p["alive"] or p["role"] not in ("Loup Garou", "Loup Blanc"):
            await interaction.response.send_message("❌ Seuls les loups votent ici.", ephemeral=True)
            return False
        return True

    async def choisir(self, interaction, cible):
        uid = interaction.user.id
        self.game["kill_votes"][uid] = cible
        nom = self.game["players"][cible]["name"]
        loups = [u for u, p in self.game["players"].items() if p["alive"] and p["role"] == "Loup Garou"]
        votes = {k: v for k, v in self.game["kill_votes"].items()
                 if self.game["players"].get(k, {}).get("role") == "Loup Garou"}
        detail = "\n".join(f"• **{self.game['players'][k]['name']}** → {self.game['players'][v]['name']}"
                           for k, v in votes.items())
        await interaction.response.send_message(f"🎯 Tu désignes **{nom}**.", ephemeral=True)
        try:
            await interaction.message.edit(embed=discord.Embed(
                title="🐺 La meute délibère",
                description=(f"*Vos crocs se découvrent. Il faut choisir — et vite.*\n\n"
                             f"**Votes ({len(votes)}/{len(loups)})**\n{detail}"),
                color=0x2c3e50), view=self)
        except Exception:
            pass
        if len(votes) >= len(loups) and loups:
            from collections import Counter as _C
            victime = _C(votes.values()).most_common(1)[0][0]
            self.game["eliminated_tonight"] = victime
            for it in self.children: it.disabled = True
            try:
                await interaction.message.edit(view=self)
            except Exception:
                pass
            await interaction.channel.send(embed=discord.Embed(
                description=f"🐺 La meute a tranché : **{self.game['players'][victime]['name']}** ne verra pas l'aube.",
                color=0xe74c3c))
            await _lg_inform_sorciere(self.ctx.guild, self.game, victime)
            self.stop()

class LGLoupBlancView(ui.View):
    """🤍 Frappe solitaire — peut viser un loup"""
    def __init__(self, game, uid_lb, guild, timeout=LG_DUREE_NUIT):
        super().__init__(timeout=timeout)
        self.game, self.uid_lb = game, uid_lb
        self.add_item(LGCibleSelect(_lg_options(game, guild, exclure=[uid_lb], loups_visibles=True),
                                    "🤍 Ta cible secrète…"))

    async def interaction_check(self, interaction):
        if interaction.user.id != self.uid_lb:
            await interaction.response.send_message("❌ Ce n'est pas ton salon.", ephemeral=True)
            return False
        return True

    async def choisir(self, interaction, cible):
        self.game["loup_blanc_cible"] = cible
        for it in self.children: it.disabled = True
        await interaction.response.edit_message(embed=discord.Embed(
            title="🤍 Ton choix est scellé",
            description=(f"**{self.game['players'][cible]['name']}** mourra cette nuit.\n\n"
                         f"*Personne ne saura que c'était toi. Pas même la meute.*"),
            color=0x95a5a6), view=self)
        self.stop()

class LGVoyanteView(ui.View):
    """🔮 Une seule vision par nuit"""
    def __init__(self, game, uid_v, guild, timeout=LG_DUREE_NUIT):
        super().__init__(timeout=timeout)
        self.game, self.uid_v = game, uid_v
        self.add_item(LGCibleSelect(_lg_options(game, guild, exclure=[uid_v]), "🔮 Qui veux-tu sonder ?"))

    async def interaction_check(self, interaction):
        if interaction.user.id != self.uid_v:
            await interaction.response.send_message("❌ Ce n'est pas ton salon.", ephemeral=True)
            return False
        return True

    async def choisir(self, interaction, cible):
        p = self.game["players"][cible]
        rd = LG_ROLES.get(p["role"], {"emoji": "❓"})
        loup = p["role"] in ("Loup Garou", "Loup Blanc")
        for it in self.children: it.disabled = True
        await interaction.response.edit_message(embed=discord.Embed(
            title="🔮 La vision se dissipe…",
            description=(f"**{p['name']}** est {rd['emoji']} **{p['role']}**\n\n"
                         + ("🔴 *Un loup. Tu le sais maintenant — mais comment le dire sans te trahir ?*"
                            if loup else "✅ *Innocent. Une piste écartée.*")),
            color=0xe74c3c if loup else 0x2ecc71), view=self)
        self.stop()


class LGSorciereView(ui.View):
    """🧙 Désigne d'abord, puis choisis la fiole"""
    def __init__(self, game, uid_s, guild, timeout=LG_DUREE_NUIT):
        super().__init__(timeout=timeout)
        self.game, self.uid_s, self.cible = game, uid_s, None
        self.add_item(LGCibleSelect(_lg_options(game, guild), "🧪 Désigner quelqu'un…"))

    async def interaction_check(self, interaction):
        if interaction.user.id != self.uid_s:
            await interaction.response.send_message("❌ Ce n'est pas ton antre.", ephemeral=True)
            return False
        return True

    def _potions(self):
        return self.game["witch_potions"].get(self.uid_s, {"life": True, "death": True})

    async def choisir(self, interaction, cible):
        self.cible = cible
        nom = self.game["players"][cible]["name"]
        pot = self._potions()
        victime = self.game.get("eliminated_tonight")
        peut_soigner = pot.get("life") and victime == cible
        self.soigner.disabled = not peut_soigner
        self.empoisonner.disabled = not pot.get("death")
        aide = ("*Cette personne est la proie des loups — tu peux encore la sauver.*"
                if peut_soigner else
                "*Ta fiole de vie ne ramène que la victime des loups.*" if pot.get("life")
                else "*Ta fiole de vie est vide.*")
        await interaction.response.edit_message(embed=discord.Embed(
            title="🧙‍♀️ Ton chaudron frémit",
            description=f"Tu as désigné **{nom}**.\n\n{aide}\n\nQue fais-tu ?",
            color=0x27ae60), view=self)

    @ui.button(label="Sauver", emoji="🌿", style=discord.ButtonStyle.success, row=1, disabled=True)
    async def soigner(self, interaction, button):
        if self.cible is None:
            return await interaction.response.send_message("❌ Désigne d'abord quelqu'un.", ephemeral=True)
        self.game["witch_potions"][self.uid_s]["life"] = False
        if self.game.get("eliminated_tonight") == self.cible:
            self.game["eliminated_tonight"] = None
        nom = self.game["players"][self.cible]["name"]
        for it in self.children: it.disabled = True
        await interaction.response.edit_message(embed=discord.Embed(
            title="🌿 Fiole de vie brisée",
            description=f"**{nom}** respirera encore demain.\n\n*Il ne saura jamais qui l'a sauvé.*",
            color=0x2ecc71), view=self)
        await _lg_check_sorciere_potions(interaction.guild, self.game, self.uid_s)
        self.stop()

    @ui.button(label="Empoisonner", emoji="☠️", style=discord.ButtonStyle.danger, row=1, disabled=True)
    async def empoisonner(self, interaction, button):
        if self.cible is None:
            return await interaction.response.send_message("❌ Désigne d'abord quelqu'un.", ephemeral=True)
        self.game["witch_potions"][self.uid_s]["death"] = False
        self.game["players"][self.cible]["alive"] = False
        nom = self.game["players"][self.cible]["name"]
        for it in self.children: it.disabled = True
        await interaction.response.edit_message(embed=discord.Embed(
            title="☠️ Fiole de mort versée",
            description=f"**{nom}** ne se réveillera pas.\n\n*Le village croira que ce sont les loups.*",
            color=0xe74c3c), view=self)
        await _lg_check_sorciere_potions(interaction.guild, self.game, self.uid_s)
        self.stop()

    @ui.button(label="Ne rien faire", emoji="⏭️", style=discord.ButtonStyle.secondary, row=1)
    async def passer(self, interaction, button):
        for it in self.children: it.disabled = True
        await interaction.response.edit_message(embed=discord.Embed(
            description="⏭️ Tu ranges tes fioles. *Cette nuit, tu observes.*", color=0x95a5a6), view=self)
        self.stop()

class LGCupidonView(ui.View):
    """💘 Deux flèches, deux destins liés"""
    def __init__(self, game, uid_c, guild, timeout=LG_DUREE_NUIT):
        super().__init__(timeout=timeout)
        self.game, self.uid_c = game, uid_c
        self.a = self.b = None
        opts = _lg_options(game, guild)
        s1 = LGCibleSelect(opts, "💘 Premier amoureux…"); s1.row = 0
        s2 = LGCibleSelect(list(opts), "💘 Second amoureux…"); s2.row = 1
        s1.callback = self._mk(1, s1); s2.callback = self._mk(2, s2)
        self.add_item(s1); self.add_item(s2)

    def _mk(self, num, select):
        async def cb(interaction):
            if interaction.user.id != self.uid_c:
                return await interaction.response.send_message("❌ Ce n'est pas ton salon.", ephemeral=True)
            val = int(select.values[0])
            if num == 1: self.a = val
            else: self.b = val
            self.lier.disabled = not (self.a and self.b and self.a != self.b)
            txt = (f"❤️ **{self.game['players'][self.a]['name']}**" if self.a else "❤️ *(à choisir)*")
            txt += "  ✚  "
            txt += (f"**{self.game['players'][self.b]['name']}**" if self.b else "*(à choisir)*")
            if self.a and self.a == self.b:
                txt += "\n\n⚠️ *Choisis deux personnes différentes.*"
            await interaction.response.edit_message(embed=discord.Embed(
                title="💘 Tes flèches sont prêtes",
                description=f"*Tu ne tues pas — tu lies. Pour le meilleur et surtout pour le pire.*\n\n{txt}",
                color=0xff6b9d), view=self)
        return cb

    @ui.button(label="Lier ces deux âmes", emoji="💞", style=discord.ButtonStyle.success, row=2, disabled=True)
    async def lier(self, interaction, button):
        self.game["lovers"] = [self.a, self.b]
        self.game["cupidon_done"] = True
        for it in self.children: it.disabled = True
        na = self.game["players"][self.a]["name"]; nb = self.game["players"][self.b]["name"]
        await interaction.response.edit_message(embed=discord.Embed(
            title="💞 Les âmes sont liées",
            description=f"**{na}** et **{nb}** vivront et mourront ensemble.\n\n*Ils viennent d'être prévenus en privé.*",
            color=0xff6b9d), view=self)
        for uid in (self.a, self.b):
            m = interaction.guild.get_member(int(uid))
            autre = self.b if uid == self.a else self.a
            if m:
                try:
                    await m.send(embed=discord.Embed(
                        title="💘 Une flèche t'a touché",
                        description=(f"Tu es lié à **{self.game['players'][autre]['name']}**.\n\n"
                                     f"*Si l'un de vous meurt, l'autre le suivra de chagrin.*"),
                        color=0xff6b9d))
                except Exception:
                    pass
        salon_id = self.game.get("salons_temp", {}).pop("cupidon", None)
        if salon_id:
            ch = interaction.guild.get_channel(salon_id)
            if ch:
                asyncio.create_task(close_event_channel(ch, 30))
        self.stop()

class LGChasseurView(ui.View):
    """🏹 Le dernier geste"""
    def __init__(self, game, uid_ch, guild, timeout=120):
        super().__init__(timeout=timeout)
        self.game, self.uid_ch = game, uid_ch
        self.add_item(LGCibleSelect(_lg_options(game, guild, exclure=[uid_ch]), "🏹 Qui pars avec toi ?"))

    async def interaction_check(self, interaction):
        if interaction.user.id != self.uid_ch:
            await interaction.response.send_message("❌ Ce n'est pas ton arme.", ephemeral=True)
            return False
        return True

    async def choisir(self, interaction, cible):
        self.game["players"][cible]["alive"] = False
        nom = self.game["players"][cible]["name"]
        for it in self.children: it.disabled = True
        await interaction.response.edit_message(embed=discord.Embed(
            title="🏹 Le coup part",
            description=f"**{nom}** s'effondre à tes côtés.\n\n*Tu ne pars pas seul.*",
            color=0xe67e22), view=self)
        ch_pub = interaction.guild.get_channel(self.game["channel"])
        if ch_pub:
            await ch_pub.send(embed=discord.Embed(
                description=f"🏹 Dans un dernier souffle, le Chasseur emporte **{nom}** !",
                color=0xe67e22))
        salon_id = self.game.get("salons_temp", {}).pop("chasseur", None)
        if salon_id:
            c2 = interaction.guild.get_channel(salon_id)
            if c2:
                asyncio.create_task(close_event_channel(c2, 30))
        self.stop()


class LGVoteView(ui.View):
    """⚖️ Vote du village — menu déroulant, tout le monde vote"""
    def __init__(self, game, gid, ctx, timeout=LG_DUREE_JOUR):
        super().__init__(timeout=timeout)
        self.game, self.gid, self.ctx = game, gid, ctx
        self.add_item(LGCibleSelect(_lg_options(game, ctx.guild), "⚖️ Voter contre…"))

    async def interaction_check(self, interaction):
        p = self.game["players"].get(interaction.user.id)
        if not p:
            await interaction.response.send_message("❌ Tu ne participes pas à cette partie.", ephemeral=True)
            return False
        if not p["alive"]:
            await interaction.response.send_message("💀 Les morts ne votent pas.", ephemeral=True)
            return False
        return True

    async def choisir(self, interaction, cible):
        uid = interaction.user.id
        if cible == uid:
            return await interaction.response.send_message("❌ Tu ne peux pas voter contre toi-même.", ephemeral=True)
        self.game["votes"][uid] = cible
        vivants = [u for u, p in self.game["players"].items() if p["alive"]]
        from collections import Counter as _C
        tally = _C(self.game["votes"].values())
        detail = "\n".join(f"• **{self.game['players'][k]['name']}** — {v} voix"
                           for k, v in tally.most_common())
        await interaction.response.send_message(
            f"🗳️ Ton vote va contre **{self.game['players'][cible]['name']}**.", ephemeral=True)
        try:
            await interaction.message.edit(embed=discord.Embed(
                title="⚖️ Le village délibère",
                description=(f"*Les accusations fusent. Il faut trancher.*\n\n"
                             f"**Votes ({len(self.game['votes'])}/{len(vivants)})**\n{detail}"),
                color=0xe67e22), view=self)
        except Exception:
            pass
        if len(self.game["votes"]) >= len(vivants):
            for it in self.children: it.disabled = True
            try:
                await interaction.message.edit(view=self)
            except Exception:
                pass
            self.stop()
            await lg_resolve_vote(self.ctx, self.game, self.gid)

async def lg_narrer(ctx, cle: str):
    import random as _r
    textes = LG_NARRATIONS.get(cle, [])
    if not textes:
        return
    texte = _r.choice(textes)
    embed = discord.Embed(description=f"*{texte}*", color=0x2c2f33)
    embed.set_footer(text="🐺 Loup Garou — QG Kdrama")
    await ctx.send(embed=embed)

def lg_get_compo(n):
    if n <= 5:
        return ["Loup Garou", "Voyante", "Sorcière", "Villageois", "Villageois"]
    elif n <= 7:
        return ["Loup Garou", "Loup Garou", "Voyante", "Sorcière", "Chasseur", "Villageois", "Villageois"][:n]
    elif n <= 9:
        return ["Loup Garou", "Loup Garou", "Voyante", "Sorcière", "Chasseur", "Cupidon", "Villageois", "Villageois", "Villageois"][:n]
    elif n <= 11:
        return ["Loup Garou", "Loup Garou", "Loup Blanc", "Voyante", "Sorcière", "Chasseur", "Cupidon", "Petite Fille", "Villageois", "Villageois", "Villageois"][:n]
    else:
        return ["Loup Garou", "Loup Garou", "Loup Blanc", "Voyante", "Sorcière", "Chasseur", "Cupidon", "Petite Fille", "Villageois", "Villageois", "Villageois", "Villageois"][:n]

def lg_check_win(game):
    players = game["players"]
    alive = {uid: p for uid, p in players.items() if p["alive"]}
    wolves_alive = [uid for uid, p in alive.items() if p["role"] in ["Loup Garou", "Loup Blanc"]]
    villagers_alive = [uid for uid, p in alive.items() if p["role"] not in ["Loup Garou", "Loup Blanc"]]
    loup_blanc_alive = [uid for uid, p in alive.items() if p["role"] == "Loup Blanc"]
    if len(alive) == 1 and loup_blanc_alive:
        return True, "🤍 **Le Loup Blanc** gagne seul ! Mystérieux jusqu'au bout..."
    if len(villagers_alive) <= len(wolves_alive):
        return True, "🐺 **Les Loups Garous** ont gagné ! Le village est sous leur emprise..."
    if not wolves_alive:
        return True, "🏘️ **Le Village** a gagné ! Tous les loups sont éliminés !"
    return False, ""

async def lg_reveal_roles(channel, game):
    lines = []
    for uid, p in game["players"].items():
        role = p.get("role", "?")
        role_data = LG_ROLES.get(role, {"emoji": "❓"})
        status = "✅ Vivant" if p["alive"] else "💀 Éliminé"
        lines.append(f"{role_data['emoji']} **{p['name']}** — {role} ({status})")
    embed = discord.Embed(
        title="🎭 Révélation des Rôles",
        description="\n".join(lines),
        color=0x2c3e50
    )
    await channel.send(embed=embed)

async def lg_cleanup_salons(guild, game):
    """Supprime tous les salons temporaires LG"""
    salons = game.get("salons_temp", {})
    for key, channel_id in list(salons.items()):
        ch = guild.get_channel(channel_id)
        if ch:
            try:
                await ch.delete(reason="Fin de partie Loup Garou")
            except:
                pass
    game["salons_temp"] = {}

async def lg_create_salons(guild, game):
    """Crée les salons temporaires selon les rôles présents"""
    players = game["players"]
    salons = {}
    
    # Trouver ou créer une catégorie LG
    cat = discord.utils.get(guild.categories, name="🐺 Loup Garou")
    if not cat:
        try:
            cat = await guild.create_category("🐺 Loup Garou", overwrites={
                guild.default_role: discord.PermissionOverwrite(read_messages=False)
            })
        except:
            cat = None

    async def make_salon(name, allowed_uids, read_only_uids=None):
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True),
        }
        for uid in allowed_uids:
            m = guild.get_member(int(uid))
            if m:
                overwrites[m] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        if read_only_uids:
            for uid in read_only_uids:
                m = guild.get_member(int(uid))
                if m:
                    overwrites[m] = discord.PermissionOverwrite(read_messages=True, send_messages=False)
        try:
            ch = await guild.create_text_channel(name, overwrites=overwrites, category=cat)
            return ch
        except:
            return None

    # 🐺 Salon Loups (Loups Garous + Loup Blanc)
    loups = [uid for uid, p in players.items() if p["role"] in ["Loup Garou", "Loup Blanc"]]
    if loups:
        ch = await make_salon("🐺・loups-garous", loups)
        if ch:
            salons["loups"] = ch.id

    # 🤍 Salon Loup Blanc seul
    loup_blanc = [uid for uid, p in players.items() if p["role"] == "Loup Blanc"]
    if loup_blanc:
        ch = await make_salon("🤍・loup-blanc-secret", loup_blanc)
        if ch:
            salons["loup_blanc"] = ch.id

    # 🔮 Salon Voyante
    voyante = [uid for uid, p in players.items() if p["role"] == "Voyante"]
    if voyante:
        ch = await make_salon("🔮・voyante-secret", voyante)
        if ch:
            salons["voyante"] = ch.id

    # 🧙 Salon Sorcière
    sorciere = [uid for uid, p in players.items() if p["role"] == "Sorcière"]
    if sorciere:
        ch = await make_salon("🧙・sorciere-antre", sorciere)
        if ch:
            salons["sorciere"] = ch.id

    # 💘 Salon Cupidon (1ère nuit seulement)
    cupidon = [uid for uid, p in players.items() if p["role"] == "Cupidon"]
    if cupidon:
        ch = await make_salon("💘・cupidon-secret", cupidon)
        if ch:
            salons["cupidon"] = ch.id

    # 👧 Salon Petite Fille
    pg = [uid for uid, p in players.items() if p["role"] == "Petite Fille"]
    if pg:
        ch = await make_salon("👧・petite-fille-secret", pg)
        if ch:
            salons["petite_fille"] = ch.id

    game["salons_temp"] = salons
    return salons

async def lg_nuit_annonces(guild, game, ctx_channel):
    """Narration + interface cliquable dans chaque salon de rôle"""
    players = game["players"]
    salons = game.get("salons_temp", {})
    nuit = game.get("day", 1)

    class _Ctx:
        def __init__(s, g, ch): s.guild, s.channel = g, ch
    ctx = _Ctx(guild, ctx_channel)

    def ping(uids):
        return " ".join(m.mention for m in
                        (guild.get_member(int(u)) for u in uids) if m)

    # ── 🐺 La meute ──
    loups = [u for u, p in players.items() if p["alive"] and p["role"] in ("Loup Garou", "Loup Blanc")]
    if "loups" in salons and loups:
        ch = guild.get_channel(salons["loups"])
        if ch:
            v = LGLoupsView(game, guild.id, ctx)
            await ch.send(ping(loups), embed=discord.Embed(
                title=f"🐺 Nuit {nuit} — la meute s'éveille",
                description=("*Le village dort. Vos crocs se découvrent.*\n\n"
                             "**Ce que tu dois faire :** désigne une victime dans le menu. "
                             "Quand tous les loups auront choisi, la majorité l'emportera.\n"
                             "*Discutez ici — personne d'autre ne vous lit.*"),
                color=0x2c3e50), view=v)

    # ── 🤍 Le Loup Blanc ──
    lb = [u for u, p in players.items() if p["alive"] and p["role"] == "Loup Blanc"]
    if "loup_blanc" in salons and lb:
        ch = guild.get_channel(salons["loup_blanc"])
        if ch:
            await ch.send(ping(lb), embed=discord.Embed(
                title=f"🤍 Nuit {nuit} — tu chasses seul",
                description=("*Ni la meute ni le village ne sont tes alliés. Un seul survivra, et ce sera toi.*\n\n"
                             "**Ce que tu dois faire :** tu peux frapper **n'importe qui** — "
                             "même un loup. Ton choix reste secret.\n"
                             "*Tu peux aussi ne rien faire cette nuit.*"),
                color=0x95a5a6), view=LGLoupBlancView(game, lb[0], guild))

    # ── 🔮 La Voyante ──
    voy = [u for u, p in players.items() if p["alive"] and p["role"] == "Voyante"]
    if "voyante" in salons and voy:
        ch = guild.get_channel(salons["voyante"])
        if ch:
            await ch.send(ping(voy), embed=discord.Embed(
                title=f"🔮 Nuit {nuit} — une seule vision",
                description=("*La boule s'éclaircit. Tu n'auras qu'un regard cette nuit.*\n\n"
                             "**Ce que tu dois faire :** choisis un joueur, son rôle exact te sera révélé.\n"
                             "*Le plus dur viendra demain : le dire sans te faire dévorer.*"),
                color=0x9b59b6), view=LGVoyanteView(game, voy[0], guild))

    # ── 🧙 La Sorcière ──
    sorc = [u for u, p in players.items() if p["alive"] and p["role"] == "Sorcière"]
    if "sorciere" in salons and sorc:
        ch = guild.get_channel(salons["sorciere"])
        if ch:
            pot = game["witch_potions"].get(sorc[0], {"life": True, "death": True})
            await ch.send(ping(sorc), embed=discord.Embed(
                title=f"🧙‍♀️ Nuit {nuit} — deux fioles, deux destins",
                description=(f"*Ton antre sent le soufre et la menthe.*\n\n"
                             f"🌿 Fiole de vie : {'**disponible**' if pot.get('life') else '~~vide~~'}\n"
                             f"☠️ Fiole de mort : {'**disponible**' if pot.get('death') else '~~vide~~'}\n\n"
                             f"**Ce que tu dois faire :** désigne quelqu'un dans le menu, "
                             f"puis choisis ta fiole. Chacune ne sert **qu'une fois de toute la partie**.\n"
                             f"*Je te préviendrai dès que les loups auront frappé.*"),
                color=0x27ae60), view=LGSorciereView(game, sorc[0], guild))

    # ── 💘 Cupidon (nuit 1) ──
    cup = [u for u, p in players.items() if p["alive"] and p["role"] == "Cupidon"]
    if "cupidon" in salons and cup and nuit == 1 and not game.get("cupidon_done"):
        ch = guild.get_channel(salons["cupidon"])
        if ch:
            await ch.send(ping(cup), embed=discord.Embed(
                title="💘 Nuit 1 — tes flèches ne tuent pas",
                description=("*Elles lient. Pour le meilleur, et surtout pour le pire.*\n\n"
                             "**Ce que tu dois faire :** choisis **deux** joueurs dans les menus, "
                             "puis valide. Si l'un meurt, l'autre le suivra de chagrin.\n"
                             "*Tu peux te choisir toi-même — à tes risques.*"),
                color=0xff6b9d), view=LGCupidonView(game, cup[0], guild))

    # ── 👧 La Petite Fille ──
    pf = [u for u, p in players.items() if p["alive"] and p["role"] == "Petite Fille"]
    if "petite_fille" in salons and pf:
        ch = guild.get_channel(salons["petite_fille"])
        if ch:
            noms_loups = [p["name"] for u, p in players.items()
                          if p["alive"] and p["role"] in ("Loup Garou", "Loup Blanc")]
            if random.random() < 0.5 and noms_loups:
                indice = (f"*Tu entrouvres les volets. Dans l'obscurité, un nom revient en chuchotement :*\n\n"
                          f"# 🕯️ {random.choice(noms_loups)}\n\n"
                          f"*Vrai ? Piège ? Tu n'en sauras rien avant demain.*")
            else:
                indice = ("*Tu tends l'oreille longtemps… mais les voix restent indistinctes.*\n\n"
                          "# 🌫️ Rien cette nuit\n\n*Trop risqué d'insister.*")
            await ch.send(ping(pf), embed=discord.Embed(
                title=f"👧 Nuit {nuit} — tu espionnes",
                description=indice + "\n\n**Ce que tu dois faire :** rien à cliquer — "
                                     "garde l'info et choisis bien tes mots demain.",
                color=0xf39c12))


# ============================================================
#  COMMANDES LG
# ============================================================

lg_games = {}  # {guild_id: game_data}


async def _lg_timer_nuit(ctx, gid, jour):
    """Résout la nuit automatiquement si l'hôte ne le fait pas"""
    await asyncio.sleep(LG_DUREE_NUIT)
    game = lg_games.get(gid)
    if not game or game["state"] != "night" or game["day"] != jour:
        return
    try:
        await ctx.send(embed=discord.Embed(
            description="🌅 Le temps de la nuit est écoulé — l'aube se lève d'elle-même…",
            color=0x95a5a6))
        await lg_resoudre_nuit(ctx, game, gid)
    except Exception as e:
        print(f"[LG] Timer nuit : {e}")

async def _lg_timer_jour(ctx, gid, jour):
    """Dépouille le vote automatiquement si tout le monde n'a pas voté"""
    await asyncio.sleep(LG_DUREE_JOUR)
    game = lg_games.get(gid)
    if not game or game["state"] != "day" or game["day"] != jour:
        return
    try:
        await ctx.send(embed=discord.Embed(
            description="⏰ Le temps du débat est écoulé — dépouillement des votes !",
            color=0x95a5a6))
        await lg_resolve_vote(ctx, game, gid)
    except Exception as e:
        print(f"[LG] Timer jour : {e}")

async def _lg_chasseur(guild, game, uid, ctx_channel):
    """Ouvre le salon du Chasseur — appelé qu'il meure de jour ou de nuit"""
    if game["players"].get(uid, {}).get("role") != "Chasseur":
        return
    m = guild.get_member(int(uid))
    if not m:
        return
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True),
        m: discord.PermissionOverwrite(read_messages=True, send_messages=True),
    }
    try:
        cat = discord.utils.get(guild.categories, name="🐺 Loup Garou")
        ch = await guild.create_text_channel("🏹・chasseur-secret", overwrites=overwrites, category=cat)
    except Exception:
        return
    game["salons_temp"]["chasseur"] = ch.id
    await ch.send(m.mention, embed=discord.Embed(
        title="🏹 Ton dernier geste",
        description=("*Tu tombes. Ta main se crispe une dernière fois sur la détente.*\n\n"
                     "**Ce que tu dois faire :** choisis qui part avec toi dans le menu.\n"
                     "*Tu as 2 minutes — après quoi ton doigt se relâchera.*"),
        color=0xe67e22), view=LGChasseurView(game, uid, guild))



@bot.command(name="lg")
async def loup_garou_help(ctx):
    """Affiche l'aide du Loup Garou"""
    embed = discord.Embed(
        title="🐺 Loup Garou — QG Kdrama",
        description="Le célèbre jeu de déduction social, version Discord !",
        color=0x2c3e50
    )
    embed.add_field(name="📋 Commandes serveur", value=(
        "`.lgcreate` — Créer une partie\n"
        "`.lgjoin` — Rejoindre la partie\n"
        "`.lgstart` — Lancer (créateur uniquement)\n"
        "`.lgvote @joueur` — Voter *(ou utilise le menu du jour)*\n"
        "`.lgnext` — Terminer la nuit tout de suite (hôte)\n"
        "`.lgpass` — Terminer la phase en cours (hôte)\n"
        "`.lgstatus` — Voir les joueurs en vie\n"
        "`.lgstop` — Annuler la partie\n"
        "`.lgroles` — Voir tous les rôles"
    ), inline=False)
    embed.add_field(name="🖱️ Pendant la partie", value=(
        "**Tout se fait au clic !** Chaque rôle reçoit son menu déroulant "
        "dans son salon secret — aucune commande à taper, aucun pseudo à écrire.\n"
        "*Les commandes texte (`.lgkill`, `.lgvoir`…) restent dispo en secours.*"
    ), inline=False)
    embed.add_field(name="🗺️ Déroulement", value=(
        "**Nuit 1** → Salons secrets créés, actions de nuit *(3 min max)*\n"
        "**Jour** → Débat + vote d'élimination *(5 min max)*\n"
        "**Nuit suivante** → Actions de nuit dans les salons\n"
        "*Les salons secrets sont supprimés en fin de partie*"
    ), inline=False)
    embed.add_field(name="🎯 Min/Max", value="5 à 12 joueurs", inline=True)
    embed.add_field(name="⏱️ Durée", value="15–30 minutes", inline=True)
    await ctx.send(embed=embed)

@bot.command(name="lgroles")
async def lg_roles_list(ctx):
    embed = discord.Embed(title="🃏 Rôles du Loup Garou", color=0x8e44ad)
    for role, data in LG_ROLES.items():
        embed.add_field(name=f"{data['emoji']} {role}", value=data['desc'], inline=False)
    await ctx.send(embed=embed)

@bot.command(name="lgcreate")
async def lg_create(ctx):
    gid = ctx.guild.id
    if gid in lg_games:
        return await ctx.send("❌ Une partie est déjà en cours ! Tape `.lgstop` pour l'annuler.")
    lg_games[gid] = {
        "state": "waiting",
        "host": ctx.author.id,
        "players": {},
        "channel": ctx.channel.id,
        "day": 0,
        "votes": {},
        "night_actions": {},
        "lovers": [],
        "witch_potions": {},
        "eliminated_tonight": None,
        "loup_blanc_cible": None,
        "salons_temp": {},
        "cupidon_done": False,
        "kill_votes": {},  # votes des loups
    }
    lg_games[gid]["players"][int(ctx.author.id)] = {
        "name": ctx.author.display_name,
        "role": None,
        "alive": True,
        "power_used": False,
    }
    embed = discord.Embed(
        title="🐺 Partie de Loup Garou créée !",
        description=(
            f"**{ctx.author.display_name}** ouvre une partie !\n\n"
            "Tape `.lgjoin` pour rejoindre.\n"
            "Le créateur tape `.lgstart` quand tout le monde est prêt.\n\n"
            f"**Joueurs (1) :** {ctx.author.display_name}"
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
    if int(ctx.author.id) in game["players"]:
        return await ctx.send("❌ Tu es déjà inscrit !")
    if len(game["players"]) >= 12:
        return await ctx.send("❌ La partie est complète (12 joueurs max).")
    game["players"][int(ctx.author.id)] = {
        "name": ctx.author.display_name,
        "role": None,
        "alive": True,
        "power_used": False,
    }
    names = ", ".join(p["name"] for p in game["players"].values())
    embed = discord.Embed(
        description=f"✅ **{ctx.author.display_name}** a rejoint ! **({len(game['players'])}) :** {names}",
        color=0x27ae60
    )
    await ctx.send(embed=embed)

@bot.command(name="lgstart")
async def lg_start(ctx):
    try:
        await _lg_start_inner(ctx)
    except Exception as e:
        import traceback
        traceback.print_exc()
        await ctx.send(f"❌ Erreur LG: `{type(e).__name__}: {e}`")

async def _lg_start_inner(ctx):
    gid = ctx.guild.id
    if gid not in lg_games:
        return await ctx.send("❌ Aucune partie en attente.")
    game = lg_games[gid]
    if int(ctx.author.id) != game["host"]:
        return await ctx.send("❌ Seul le créateur peut lancer la partie.")
    if game["state"] != "waiting":
        return await ctx.send("❌ La partie a déjà commencé.")
    n = len(game["players"])
    if n < 5:
        return await ctx.send(f"❌ Il faut au moins 5 joueurs ! ({n}/5)")

    # Distribuer les rôles
    import random as _r
    compo = lg_get_compo(n)
    _r.shuffle(compo)
    player_ids = list(game["players"].keys())
    _r.shuffle(player_ids)
    for i, uid in enumerate(player_ids):
        game["players"][uid]["role"] = compo[i]

    # Potions sorcière
    for uid, p in game["players"].items():
        if p["role"] == "Sorcière":
            game["witch_potions"][uid] = {"life": True, "death": True}

    # Envoyer rôles en DM
    failed_dm = []
    for uid, p in game["players"].items():
        role = p["role"]
        role_data = LG_ROLES[role]
        embed = discord.Embed(
            title="🃏 Ton rôle secret — QG Kdrama",
            description=(
                f"**{role_data['emoji']} {role}**\n\n"
                f"_{role_data['desc']}_\n\n"
                f"**Équipe :** {'🐺 Loups' if role_data['team'] == 'loups' else ('🤍 Solitaire' if role_data['team'] == 'loup_blanc' else '👨‍🌾 Village')}"
            ),
            color=0x8e44ad
        )
        if role in ["Loup Garou", "Loup Blanc"]:
            wolves = [pp["name"] for pid, pp in game["players"].items() 
                     if pp["role"] in ["Loup Garou", "Loup Blanc"] and pid != uid]
            if wolves:
                embed.add_field(name="🐺 Tes coéquipiers loups", value=", ".join(wolves), inline=False)
        embed.add_field(name="📋 Ton action", value={
            "Loup Garou": "🐺 Chaque nuit, vote dans **#loups-garous** pour tuer un villageois",
            "Loup Blanc": "🤍 Dans **#loups-garous** avec les loups + **#loup-blanc-secret** pour trahir",
            "Voyante": "🔮 Chaque nuit, espionner quelqu'un dans **#voyante-secret**",
            "Sorcière": "🧙 Utilise tes potions dans **#sorciere-antre**",
            "Chasseur": "🏹 Si tu meurs, tu peux emporter quelqu'un",
            "Cupidon": "💘 Nuit 1 seulement : lier 2 amoureux dans **#cupidon-secret**",
            "Petite Fille": "👧 Tu recevras un indice chaque nuit dans **#petite-fille-secret**",
            "Villageois": "👨‍🌾 Débats et vote le jour pour trouver les loups !",
        }.get(role, "Participe aux débats !"), inline=False)
        embed.set_footer(text="🔒 Ne montre ce message à personne !")
        try:
            member = ctx.guild.get_member(int(uid))
            if member:
                await member.send(embed=embed)
            else:
                failed_dm.append(p["name"])
        except:
            failed_dm.append(p["name"])

    game["state"] = "night"
    game["day"] = 1

    # Créer les salons temporaires
    await ctx.send("⏳ Création des salons secrets...")
    salons = await lg_create_salons(ctx.guild, game)
    if not salons:
        await ctx.send(embed=discord.Embed(
            title="⚠️ Salons secrets non créés",
            description=("Je n'ai pas la permission **Gérer les salons**.\n"
                         "Les rôles spéciaux ne pourront pas agir — demande à un admin "
                         "de me donner la permission, puis relance la partie."),
            color=0xe67e22))

    # Annonce publique
    dm_status = "⚠️ DM fermés : " + ", ".join(failed_dm) if failed_dm else "✅ Rôles envoyés en DM !"
    names_list = "\n".join([f"❓ {p['name']}" for p in game["players"].values()])
    embed = discord.Embed(
        title="🐺 La partie commence !",
        description=(
            f"**{n} joueurs** ont reçu leur rôle en DM !\n"
            f"{dm_status}\n\n"
            "🌙 **La nuit tombe...**\n"
            "Des salons secrets ont été créés pour chaque rôle.\n"
            "Vérifiez vos salons — le bot vous a pingé !"
        ),
        color=0x2c3e50
    )
    embed.add_field(name=f"👥 Joueurs ({n})", value=names_list, inline=False)
    await ctx.send(embed=embed)
    await lg_narrer(ctx, "debut")

    # Envoyer les annonces de nuit dans les salons
    await lg_nuit_annonces(ctx.guild, game, ctx.channel)
    asyncio.create_task(_lg_timer_nuit(ctx, gid, game["day"]))

@bot.command(name="lgvote")
async def lg_vote(ctx, target: discord.Member = None):
    gid = ctx.guild.id
    if gid not in lg_games:
        return await ctx.send("❌ Aucune partie en cours.")
    game = lg_games[gid]
    if game["state"] != "day":
        return await ctx.send("❌ On ne vote que pendant le jour !")
    if int(ctx.author.id) not in game["players"]:
        return await ctx.send("❌ Tu ne participes pas à cette partie.")
    if not game["players"][int(ctx.author.id)]["alive"]:
        return await ctx.send("❌ Les morts ne votent pas... 💀")
    if target is None:
        return await ctx.send("❌ Mentionne un joueur : `.lgvote @joueur`")
    if int(target.id) not in game["players"] or not game["players"][int(target.id)]["alive"]:
        return await ctx.send("❌ Ce joueur n'est pas dans la partie ou est éliminé.")
    if int(target.id) == int(ctx.author.id):
        return await ctx.send("❌ Tu ne peux pas voter contre toi-même !")

    game["votes"][int(ctx.author.id)] = int(target.id)
    alive_voters = [uid for uid, p in game["players"].items() if p["alive"]]
    voted_count = len(game["votes"])

    embed = discord.Embed(
        description=f"🗳️ **{ctx.author.display_name}** vote contre **{target.display_name}** ({voted_count}/{len(alive_voters)})",
        color=0xe67e22
    )
    await ctx.send(embed=embed)

    if voted_count >= len(alive_voters):
        await lg_resolve_vote(ctx, game, gid)

@bot.command(name="lgkill")
async def lg_kill(ctx, target: discord.Member = None):
    """Vote des loups — dans le salon #loups-garous"""
    gid = ctx.guild.id
    if gid not in lg_games:
        return
    game = lg_games[gid]
    if game["state"] != "night":
        return await ctx.send("❌ C'est pas la nuit !", delete_after=5)
    uid = int(ctx.author.id)
    if uid not in game["players"] or game["players"][uid]["role"] not in ["Loup Garou", "Loup Blanc"]:
        return await ctx.send("❌ Réservé aux loups !", delete_after=5)
    if not game["players"][uid]["alive"]:
        return
    if target is None:
        return await ctx.send("❌ Mentionne une cible ! `.lgkill @joueur`", delete_after=5)
    target_uid = int(target.id)
    if target_uid not in game["players"] or not game["players"][target_uid]["alive"]:
        return await ctx.send("❌ Cible invalide !", delete_after=5)

    # Le Loup Blanc frappe seul depuis son salon secret
    if ctx.channel.id == game.get("salons_temp", {}).get("loup_blanc"):
        game["loup_blanc_cible"] = target_uid
        return await ctx.send(embed=discord.Embed(
            description=f"🤍 Ta cible secrète : **{game['players'][target_uid]['name']}**.\nLes autres loups n'en sauront rien.",
            color=0x95a5a6))

    game["kill_votes"][uid] = target_uid
    loups_vivants = [u for u, p in game["players"].items() if p["alive"] and p["role"] == "Loup Garou"]
    voted = len([v for v in game["kill_votes"] if game["players"].get(v, {}).get("role") == "Loup Garou"])
    await ctx.send(f"✅ **{ctx.author.display_name}** vote pour tuer **{target.display_name}** ({voted}/{len(loups_vivants)})")

    # Tous les loups ont voté ?
    if not loups_vivants:
        return
    if voted >= len(loups_vivants):
        from collections import Counter
        count = Counter(v for k, v in game["kill_votes"].items() if game["players"].get(k, {}).get("role") == "Loup Garou")
        if count:
            victime_id = count.most_common(1)[0][0]
            game["eliminated_tonight"] = victime_id
            victime_name = game["players"][victime_id]["name"]
            await ctx.send(embed=discord.Embed(
                description=f"🐺 Les loups ont décidé... **{victime_name}** sera leur cible cette nuit.",
                color=0x2c3e50
            ))
            # Informer la sorcière si elle existe
            await _lg_inform_sorciere(ctx.guild, game, victime_id)

@bot.command(name="lgvoir")
async def lg_voir(ctx, target: discord.Member = None):
    """Voyante — voir le rôle d'un joueur"""
    gid = ctx.guild.id
    if gid not in lg_games:
        return
    game = lg_games[gid]
    if game["state"] != "night":
        return await ctx.send("❌ C'est pas la nuit !", delete_after=5)
    uid = int(ctx.author.id)
    if uid not in game["players"] or game["players"][uid]["role"] != "Voyante":
        return await ctx.send("❌ Réservé à la Voyante !", delete_after=5)
    if target is None:
        return await ctx.send("❌ `.lgvoir @joueur`", delete_after=5)
    target_uid = int(target.id)
    if target_uid not in game["players"] or not game["players"][target_uid]["alive"]:
        return await ctx.send("❌ Cible invalide !", delete_after=5)

    cible_role = game["players"][target_uid]["role"]
    role_data = LG_ROLES.get(cible_role, {"emoji": "❓"})
    is_wolf = cible_role in ["Loup Garou", "Loup Blanc"]
    embed = discord.Embed(
        title="🔮 Révélation",
        description=(
            f"**{target.display_name}** est {role_data['emoji']} **{cible_role}**\n"
            f"{'🔴 **C\'est un LOUP !** Sois prudente...' if is_wolf else '✅ Innocent — ce n\'est pas un loup.'}"
        ),
        color=0xe74c3c if is_wolf else 0x2ecc71
    )
    await ctx.send(embed=embed)

@bot.command(name="lgsave")
async def lg_save(ctx, target: discord.Member = None):
    """Sorcière — potion de vie"""
    gid = ctx.guild.id
    if gid not in lg_games:
        return
    game = lg_games[gid]
    uid = int(ctx.author.id)
    if uid not in game["players"] or game["players"][uid]["role"] != "Sorcière":
        return await ctx.send("❌ Réservé à la Sorcière !", delete_after=5)
    potions = game["witch_potions"].get(uid, {})
    if not potions.get("life"):
        return await ctx.send("❌ Tu as déjà utilisé ta potion de vie !")
    if target is None:
        return await ctx.send("❌ `.lgsave @joueur`")
    target_uid = int(target.id)
    if target_uid not in game["players"]:
        return await ctx.send("❌ Joueur introuvable !")
    game["witch_potions"][uid]["life"] = False
    # Annuler la mort cette nuit
    if game["eliminated_tonight"] == target_uid:
        game["eliminated_tonight"] = None
    await ctx.send(embed=discord.Embed(
        description=f"🌿 **{target.display_name}** est sauvé cette nuit ! Potion de vie utilisée.",
        color=0x2ecc71
    ))
    await _lg_check_sorciere_potions(ctx.guild, game, uid)

@bot.command(name="lgpoison")
async def lg_poison(ctx, target: discord.Member = None):
    """Sorcière — potion de mort"""
    gid = ctx.guild.id
    if gid not in lg_games:
        return
    game = lg_games[gid]
    uid = int(ctx.author.id)
    if uid not in game["players"] or game["players"][uid]["role"] != "Sorcière":
        return await ctx.send("❌ Réservé à la Sorcière !", delete_after=5)
    potions = game["witch_potions"].get(uid, {})
    if not potions.get("death"):
        return await ctx.send("❌ Tu as déjà utilisé ta potion de mort !")
    if target is None:
        return await ctx.send("❌ `.lgpoison @joueur`")
    target_uid = int(target.id)
    if target_uid not in game["players"] or not game["players"][target_uid]["alive"]:
        return await ctx.send("❌ Cible invalide !")
    game["witch_potions"][uid]["death"] = False
    game["players"][target_uid]["alive"] = False
    await ctx.send(embed=discord.Embed(
        description=f"☠️ **{target.display_name}** a été empoisonné cette nuit...",
        color=0xe74c3c
    ))
    await _lg_check_sorciere_potions(ctx.guild, game, uid)

async def _lg_check_sorciere_potions(guild, game, uid):
    """Supprime le salon sorcière si elle n'a plus de potions"""
    potions = game["witch_potions"].get(uid, {})
    if not potions.get("life") and not potions.get("death"):
        salon_id = game.get("salons_temp", {}).get("sorciere")
        if salon_id:
            ch = guild.get_channel(salon_id)
            if ch:
                try:
                    await ch.send("🧙 Tu n'as plus de potions — ce salon va fermer.")
                    await asyncio.sleep(5)
                    await ch.delete()
                except:
                    pass
            game["salons_temp"].pop("sorciere", None)

async def _lg_inform_sorciere(guild, game, victime_id):
    """Prévient la sorcière de la victime des loups, avec le bouton de soin"""
    salon_id = game.get("salons_temp", {}).get("sorciere")
    if not salon_id:
        return
    ch = guild.get_channel(salon_id)
    if not ch:
        return
    sorc = [u for u, p in game["players"].items() if p["role"] == "Sorcière" and p["alive"]]
    if not sorc:
        return
    uid_s = sorc[0]
    pot = game["witch_potions"].get(uid_s, {})
    m = guild.get_member(int(uid_s))
    nom = game["players"].get(victime_id, {}).get("name", "?")
    v = LGSorciereView(game, uid_s, guild)
    v.cible = victime_id
    v.soigner.disabled = not pot.get("life")
    v.empoisonner.disabled = not pot.get("death")
    await ch.send(m.mention if m else "", embed=discord.Embed(
        title="☠️ Les crocs ont choisi",
        description=(f"*Une silhouette s'affaisse dans la nuit…*\n\n"
                     f"# {nom}\n\n"
                     f"**Ce que tu dois faire :** clique sur 🌿 **Sauver** pour le ramener, "
                     f"ou désigne quelqu'un d'autre et verse ☠️ ta fiole de mort.\n"
                     f"*Ou ne fais rien — c'est aussi un choix.*"),
        color=0xe74c3c), view=v)


@bot.command(name="lglove")
async def lg_love(ctx, j1: discord.Member = None, j2: discord.Member = None):
    """Cupidon — lier deux amoureux"""
    gid = ctx.guild.id
    if gid not in lg_games:
        return
    game = lg_games[gid]
    uid = int(ctx.author.id)
    if uid not in game["players"] or game["players"][uid]["role"] != "Cupidon":
        return await ctx.send("❌ Réservé à Cupidon !", delete_after=5)
    if game.get("cupidon_done"):
        return await ctx.send("❌ Tu as déjà lié les amoureux !")
    if not j1 or not j2:
        return await ctx.send("❌ `.lglove @joueur1 @joueur2`")
    if int(j1.id) not in game["players"] or int(j2.id) not in game["players"]:
        return await ctx.send("❌ Ces joueurs ne sont pas dans la partie !")
    game["lovers"] = [int(j1.id), int(j2.id)]
    game["cupidon_done"] = True
    # Notifier les amoureux en DM
    for amoureux in [j1, j2]:
        autre = j2 if amoureux == j1 else j1
        try:
            await amoureux.send(embed=discord.Embed(
                description=f"💘 Cupidon t'a lié à **{autre.display_name}** ! Si l'un de vous meurt, l'autre mourra de chagrin.",
                color=0xff6b9d
            ))
        except:
            pass
    await ctx.send(embed=discord.Embed(
        description=f"💘 Les amoureux sont liés ! Ils mourront ensemble s'il le faut...",
        color=0xff6b9d
    ))
    # Supprimer le salon cupidon
    salon_id = game.get("salons_temp", {}).get("cupidon")
    if salon_id:
        ch = ctx.guild.get_channel(salon_id)
        if ch:
            await asyncio.sleep(3)
            try:
                await ch.delete()
            except:
                pass
        game["salons_temp"].pop("cupidon", None)

@bot.command(name="lgskip")
async def lg_skip(ctx):
    """Passer son action de nuit"""
    await ctx.send("⏭️ Tu passes cette nuit.", delete_after=5)

@bot.command(name="lgpass")
async def lg_pass_vote(ctx):
    """Forcer la résolution du vote (hôte uniquement)"""
    gid = ctx.guild.id
    if gid not in lg_games:
        return
    game = lg_games[gid]
    if int(ctx.author.id) != game["host"]:
        return await ctx.send("❌ Réservé à l'hôte.")
    if game["state"] == "night":
        await lg_resoudre_nuit(ctx, game, gid)
    elif game["state"] == "day":
        await lg_resolve_vote(ctx, game, gid)

@bot.command(name="lgnext")
async def lg_next(ctx):
    """Passer à la résolution de nuit (hôte)"""
    gid = ctx.guild.id
    if gid not in lg_games:
        return
    game = lg_games[gid]
    if int(ctx.author.id) != game["host"]:
        return await ctx.send("❌ Réservé à l'hôte.")
    if game["state"] != "night":
        return await ctx.send("❌ C'est pas la nuit !")
    await lg_resoudre_nuit(ctx, game, gid)

async def lg_resoudre_nuit(ctx, game, gid):
    """Résout la nuit et passe au jour"""
    guild = ctx.guild
    players = game["players"]

    # Appliquer la mort des loups
    morts_nuit = []

    def _tuer(cible):
        if not cible or not players.get(cible, {}).get("alive"):
            return
        players[cible]["alive"] = False
        morts_nuit.append(cible)
        # Amoureux : l'autre meurt de chagrin
        if cible in game["lovers"]:
            autre = [l for l in game["lovers"] if l != cible]
            if autre and players.get(autre[0], {}).get("alive"):
                players[autre[0]]["alive"] = False
                morts_nuit.append(autre[0])

    _tuer(game.get("eliminated_tonight"))
    _tuer(game.get("loup_blanc_cible"))

    # Le Chasseur emporte quelqu'un même s'il meurt la nuit
    for mort_uid in morts_nuit:
        await _lg_chasseur(guild, game, mort_uid, ctx.channel)

    # Annonce du matin
    if morts_nuit:
        desc_morts = "\n".join([f"💀 **{players[uid]['name']}** ({players[uid]['role']})" for uid in morts_nuit])
        embed = discord.Embed(
            title="☀️ L'aube se lève...",
            description=f"Cette nuit, le village a perdu :\n{desc_morts}\n\n☀️ **Jour {game['day']} — Débat !**\nVotez avec `.lgvote @joueur` pour éliminer un suspect.",
            color=0xe74c3c
        )
        await lg_narrer(ctx, "jour_mort")
    else:
        embed = discord.Embed(
            title="☀️ L'aube se lève...",
            description="Cette nuit, personne n'est mort. Les loups ont raté leur cible !\n\n☀️ **Débat !** Votez avec `.lgvote @joueur`",
            color=0x2ecc71
        )
        await lg_narrer(ctx, "jour_rien")

    alive_list = "\n".join([f"• {p['name']}" for p in players.values() if p["alive"]])
    embed.add_field(name="👥 Joueurs en vie", value=alive_list or "Personne", inline=False)
    await ctx.send(embed=embed)

    # Check victoire
    won, msg = lg_check_win(game)
    if won:
        await ctx.send(embed=discord.Embed(title="🏆 FIN DE PARTIE", description=msg, color=0xf1c40f))
        chan = ctx.guild.get_channel(game["channel"])
        if chan:
            await lg_reveal_roles(chan, game)
        await lg_cleanup_salons(guild, game)
        del lg_games[gid]
        return

    # Passer au jour
    game["state"] = "day"
    game["votes"] = {}
    game["night_actions"] = {}
    game["kill_votes"] = {}
    game["eliminated_tonight"] = None
    game["loup_blanc_cible"] = None
    await ctx.send(embed=discord.Embed(
        title="⚖️ Le village délibère",
        description=("*Les accusations fusent. Il faut trancher avant la nuit.*\n\n"
                     "**Ce que vous devez faire :** votez dans le menu ci-dessous.\n"
                     f"*{LG_DUREE_JOUR//60} minutes — ou l'hôte peut couper court avec `.lgpass`.*"),
        color=0xe67e22), view=LGVoteView(game, gid, ctx))
    asyncio.create_task(_lg_timer_jour(ctx, gid, game["day"]))

async def lg_resolve_vote(ctx, game, gid):
    """Compte les votes et élimine"""
    from collections import Counter
    count = Counter(game["votes"].values())
    guild = ctx.guild
    players = game["players"]

    if not count:
        await ctx.send("🗳️ Aucun vote — personne n'est éliminé.")
    else:
        max_votes = max(count.values())
        top = [uid for uid, v in count.items() if v == max_votes]
        if len(top) > 1:
            eliminated_id = random.choice(top)
            await ctx.send("⚖️ Égalité ! Le destin tranche...")
        else:
            eliminated_id = top[0]

        p = players[eliminated_id]
        p["alive"] = False
        role = p["role"]
        role_data = LG_ROLES.get(role, {"emoji": "❓"})

        embed = discord.Embed(
            title="☀️ Fin du vote villageois",
            description=(
                f"**{p['name']}** est éliminé avec **{count[eliminated_id]} vote(s)** !\n"
                f"Son rôle était : **{role_data['emoji']} {role}**"
            ),
            color=0xe74c3c
        )
        await ctx.send(embed=embed)

        # Amoureux ?
        if eliminated_id in game["lovers"]:
            autre_id = [l for l in game["lovers"] if l != eliminated_id]
            if autre_id and players.get(autre_id[0], {}).get("alive"):
                players[autre_id[0]]["alive"] = False
                await ctx.send(embed=discord.Embed(
                    description=f"💔 **{players[autre_id[0]]['name']}** meurt de chagrin !",
                    color=0xff6b9d
                ))

        # Chasseur ?
        await _lg_chasseur(guild, game, eliminated_id, ctx.channel)

    # Check victoire
    won, msg = lg_check_win(game)
    if won:
        await ctx.send(embed=discord.Embed(title="🏆 FIN DE PARTIE", description=msg, color=0xf1c40f))
        chan = guild.get_channel(game["channel"])
        if chan:
            await lg_reveal_roles(chan, game)
        await lg_cleanup_salons(guild, game)
        del lg_games[gid]
        return

    # Passer à la nuit
    game["state"] = "night"
    game["votes"] = {}
    game["kill_votes"] = {}
    game["eliminated_tonight"] = None
    game["loup_blanc_cible"] = None
    game["day"] += 1

    alive_list = "\n".join([f"• {p['name']}" for p in players.values() if p["alive"]])
    embed = discord.Embed(
        title=f"🌙 Nuit {game['day']} — Le village s'endort...",
        description=(
            "Les rôles spéciaux agissent dans leurs salons secrets !\n\n"
            f"**Joueurs en vie :**\n{alive_list}"
        ),
        color=0x2c3e50
    )
    await ctx.send(embed=embed)
    await lg_narrer(ctx, "nuit")
    await lg_nuit_annonces(ctx.guild, game, ctx.channel)
    asyncio.create_task(_lg_timer_nuit(ctx, gid, game["day"]))

@bot.command(name="lgkillchasseur")
async def lg_kill_chasseur(ctx, target: discord.Member = None):
    """Chasseur — emporter quelqu'un"""
    gid = ctx.guild.id
    if gid not in lg_games:
        return
    game = lg_games[gid]
    uid = int(ctx.author.id)
    if game["players"].get(uid, {}).get("role") != "Chasseur":
        return
    if target is None:
        return await ctx.send("❌ `.lgkillchasseur @joueur`")
    target_uid = int(target.id)
    if target_uid not in game["players"] or not game["players"][target_uid]["alive"]:
        return await ctx.send("❌ Cible invalide !")
    game["players"][target_uid]["alive"] = False
    ch_pub = ctx.guild.get_channel(game["channel"])
    if ch_pub:
        await ch_pub.send(embed=discord.Embed(
            description=f"🏹 Le Chasseur emporte **{target.display_name}** dans sa chute !",
            color=0xe67e22
        ))
    # Supprimer salon chasseur
    salon_id = game.get("salons_temp", {}).get("chasseur")
    if salon_id:
        ch = ctx.guild.get_channel(salon_id)
        if ch:
            try:
                await ch.delete()
            except:
                pass
        game["salons_temp"].pop("chasseur", None)

@bot.command(name="lgstop")
@commands.has_permissions(manage_messages=True)
async def lg_stop(ctx):
    gid = ctx.guild.id
    if gid not in lg_games:
        return await ctx.send("❌ Aucune partie en cours !")
    await lg_cleanup_salons(ctx.guild, lg_games[gid])
    del lg_games[gid]
    await ctx.send(embed=discord.Embed(description="🛑 Partie annulée et salons supprimés !", color=0xe74c3c))

@bot.command(name="lgstatus")
async def lg_status(ctx):
    gid = ctx.guild.id
    if gid not in lg_games:
        return await ctx.send("❌ Aucune partie en cours !")
    game = lg_games[gid]
    players = game["players"]
    alive = [p["name"] for p in players.values() if p["alive"]]
    dead = [p["name"] for p in players.values() if not p["alive"]]
    embed = discord.Embed(title="🐺 Statut — Loup Garou", color=0x2c3e50)
    embed.add_field(name=f"✅ Vivants ({len(alive)})", value="\n".join(alive) or "Aucun", inline=True)
    if dead:
        embed.add_field(name=f"💀 Éliminés ({len(dead)})", value="\n".join(dead), inline=True)
    embed.add_field(name="📊 Phase", value=f"**{game.get('state','?').upper()}** — Jour {game.get('day',0)}", inline=False)
    await ctx.send(embed=embed)

# ============================================================
#  GIRLS ONLY — TASKS AUTOMATIQUES
# ============================================================

# Tracking activité filles dans le salon Girls Only
girls_message_count = defaultdict(lambda: defaultdict(int))  # {guild_id: {uid: count}}

# Questions Ritual du Soir (21h chaque soir dans le salon girls)
RITUAL_QUESTIONS = [
    "🌙 **Ritual du Soir** — Quel drama vous fait vibrer en ce moment ? 🎬",
    "🌙 **Ritual du Soir** — Si vous étiez l'héroïne d'un Kdrama, votre drama serait un romance ou un thriller ? 💜",
    "🌙 **Ritual du Soir** — Quel acteur coréen vous ferait tomber amoureuse en 5 secondes ? 😍",
    "🌙 **Ritual du Soir** — Drama de la semaine : coup de cœur ou déception ? Partagez vos avis ! ⭐",
    "🌙 **Ritual du Soir** — Si vous deviez recommander UN drama à quelqu'un qui n'en a jamais regardé, lequel ce serait ? 🌸",
    "🌙 **Ritual du Soir** — Scène de drama qui vous a fait pleurer comme une madeleine ? 😭",
    "🌙 **Ritual du Soir** — Votre OST de drama préféré en ce moment ? 🎵",
    "🌙 **Ritual du Soir** — Second lead syndrome : vous en souffrez en ce moment pour quel drama ? 💔",
    "🌙 **Ritual du Soir** — Un drama que vous avez abandonné mais que vous voulez reprendre ? 📺",
    "🌙 **Ritual du Soir** — Votre drama comfort — celui que vous regardez quand vous êtes triste ? 🤗",
]

# Tracking Girls Only — géré directement dans on_message

@tasks.loop(minutes=1)
async def girls_auto_tasks():
    """Tasks automatiques Girls Only — Star of the Week, Diamond Girl, Ritual du Soir"""
    import datetime as _dt
    now = _dt.datetime.now()

    for guild in bot.guilds:
        if not SALON_GIRLS_ID:
            continue
        channel_girls = guild.get_channel(SALON_GIRLS_ID)
        if not channel_girls:
            continue

        gid = guild.id

        # ── RITUAL DU SOIR — 21h chaque soir ─────────────────────────
        key_ritual = f"ritual_{gid}_{now.date()}"
        if now.hour == 21 and now.minute == 0 and key_ritual not in planning_last_run:
            planning_last_run[key_ritual] = True
            question = random.choice(RITUAL_QUESTIONS)
            if ROLE_GIRLS_ID:
                role = guild.get_role(ROLE_GIRLS_ID)
                ping = role.mention if role else ""
            else:
                ping = ""
            await channel_girls.send(
                f"{ping}\n" if ping else "",
                embed=discord.Embed(
                    description=question,
                    color=0xff6b9d
                ).set_footer(text="🌙 Ritual du Soir — QG Kdrama Girls 🌸")
            )

        # ── STAR OF THE WEEK — Lundi 10h ──────────────────────────────
        key_star = f"star_week_{gid}_{now.isocalendar()[1]}"  # numéro de semaine
        if now.weekday() == 0 and now.hour == 10 and now.minute == 0 and key_star not in planning_last_run:
            planning_last_run[key_star] = True
            counts = girls_message_count[gid]
            if counts:
                top_uid = max(counts, key=counts.get)
                top_count = counts[top_uid]
                top_member = guild.get_member(int(top_uid))
                if top_member and top_count > 0:
                    embed = discord.Embed(
                        title="💫 Star of the Week !",
                        description=(
                            f"Cette semaine, la fille la plus active du QG est...\n\n"
                            f"✨ **{top_member.mention}** ✨\n\n"
                            f"*{top_count} messages dans notre salon cette semaine !*\n\n"
                            f"Félicitations à notre Star 🌟💜"
                        ),
                        color=0xf1c40f
                    )
                    embed.set_thumbnail(url=top_member.display_avatar.url)
                    embed.set_footer(text="⭐ Star of the Week — QG Kdrama Girls 🌸")
                    chan_annonces = guild.get_channel(SALON_ANNONCES_ID) if SALON_ANNONCES_ID else channel_girls
                    await (chan_annonces or channel_girls).send(embed=embed)
                    # Reset compteur de la semaine
                    girls_message_count[gid] = defaultdict(int)

        # ── DIAMOND GIRL — 1er du mois 12h ────────────────────────────
        key_diamond = f"diamond_{gid}_{now.year}_{now.month}"
        if now.day == 1 and now.hour == 12 and now.minute == 0 and key_diamond not in planning_last_run:
            planning_last_run[key_diamond] = True
            counts = girls_message_count[gid]
            if counts:
                top_uid = max(counts, key=counts.get)
                top_count = counts[top_uid]
                top_member = guild.get_member(int(top_uid))
                if top_member and top_count > 0:
                    embed = discord.Embed(
                        title="💎 Diamond Girl du Mois !",
                        description=(
                            f"Ce mois-ci, la Diamond Girl du QG est...\n\n"
                            f"💎 **{top_member.mention}** 💎\n\n"
                            f"*La plus active, la plus brillante de toutes !*\n\n"
                            f"Félicitations à notre Diamond Girl 👑💜"
                        ),
                        color=0x3498db
                    )
                    embed.set_thumbnail(url=top_member.display_avatar.url)
                    embed.set_footer(text="💎 Diamond Girl — QG Kdrama Girls 🌸")
                    chan_annonces = guild.get_channel(SALON_ANNONCES_ID) if SALON_ANNONCES_ID else channel_girls
                    await (chan_annonces or channel_girls).send(embed=embed)

# ============================================================
#  PERSISTANCE JSON — Sauvegarde et chargement des données
# ============================================================

DATA_FILES = {
    "economy": data_path("data_economy.json"),
    "xp":      data_path("data_xp.json"),
    "gacha":   data_path("data_gacha.json"),
    "social":  data_path("data_social.json"),
    "bank":    data_path("data_bank.json"),
}

def save_all_data():
    """Sauvegarde toutes les données importantes dans des fichiers JSON"""
    import json as _json
    # Economy
    try:
        with open(DATA_FILES["economy"], "w", encoding="utf-8") as f:
            _json.dump(dict(economy_data), f, ensure_ascii=False)
    except Exception as e:
        print(f"[Save] Erreur economy: {e}")
    # XP
    try:
        with open(DATA_FILES["xp"], "w", encoding="utf-8") as f:
            _json.dump(dict(xp_data), f, ensure_ascii=False)
    except Exception as e:
        print(f"[Save] Erreur xp: {e}")
    # Gacha
    try:
        gacha_save = {
            "collections": {k: dict(v) for k, v in gacha_collections.items()},
            "claimed":     dict(claimed_cards),
            "fusion":      {k: dict(v) for k, v in fusion_levels.items()},
            "card_xp":     {k: dict(v) for k, v in card_xp.items()},
            "card_level":  {k: dict(v) for k, v in card_level.items()},
            "serie_badges": {k: list(v) for k, v in serie_badges.items()},
            "fav_slots":   dict(fav_slots),
        }
        with open(DATA_FILES["gacha"], "w", encoding="utf-8") as f:
            _json.dump(gacha_save, f, ensure_ascii=False)
    except Exception as e:
        print(f"[Save] Erreur gacha: {e}")
    # Social
    try:
        social_save = {
            "mariages":     dict(mariages) if 'mariages' in dir() else {},
            "anniversaires": dict(anniversaire_data),
            "pets": pets_data,
            "achievements": {k: list(v) for k, v in achievements_data.items()},
            "user_stats": {k: dict(v) for k, v in user_stats.items()},
            "invite_counts": dict(invite_counts),
            "inventaire": {k: dict(v) for k, v in inventaire.items()},
            "claim_reduction": dict(claim_reduction),
        }
        with open(DATA_FILES["social"], "w", encoding="utf-8") as f:
            _json.dump(social_save, f, ensure_ascii=False)
    except Exception as e:
        print(f"[Save] Erreur social: {e}")
    # Bank
    try:
        with open(DATA_FILES["bank"], "w", encoding="utf-8") as f:
            _json.dump(dict(bank_data), f, ensure_ascii=False)
    except Exception as e:
        print(f"[Save] Erreur bank: {e}")

def load_all_data():
    """Charge toutes les données depuis les fichiers JSON au démarrage"""
    import json as _json, os as _os
    # Economy
    if _os.path.exists(DATA_FILES["economy"]):
        try:
            with open(DATA_FILES["economy"], "r", encoding="utf-8") as f:
                data = _json.load(f)
            for uid, val in data.items():
                economy_data[uid].update(val)
            print(f"[Load] ✅ Economy: {len(data)} membres")
        except Exception as e:
            print(f"[Load] Erreur economy: {e}")
    # XP
    if _os.path.exists(DATA_FILES["xp"]):
        try:
            with open(DATA_FILES["xp"], "r", encoding="utf-8") as f:
                data = _json.load(f)
            for uid, val in data.items():
                xp_data[uid].update(val)
            print(f"[Load] ✅ XP: {len(data)} membres")
        except Exception as e:
            print(f"[Load] Erreur xp: {e}")
    # Gacha
    if _os.path.exists(DATA_FILES["gacha"]):
        try:
            with open(DATA_FILES["gacha"], "r", encoding="utf-8") as f:
                data = _json.load(f)
            for uid, col in data.get("collections", {}).items():
                gacha_collections[uid].update(col)
            claimed_cards.update(data.get("claimed", {}))
            for uid, fus in data.get("fusion", {}).items():
                fusion_levels[uid].update(fus)
            for uid, cx in data.get("card_xp", {}).items():
                card_xp[uid].update(cx)
            for uid, cl in data.get("card_level", {}).items():
                card_level[uid].update(cl)
            for uid, sb in data.get("serie_badges", {}).items():
                serie_badges[uid] = set(sb)
            for uid, fs in data.get("fav_slots", {}).items():
                fav_slots[uid] = fs
            print(f"[Load] ✅ Gacha: {len(claimed_cards)} cartes claimées")
        except Exception as e:
            print(f"[Load] Erreur gacha: {e}")
    # Social
    if _os.path.exists(DATA_FILES["social"]):
        try:
            with open(DATA_FILES["social"], "r", encoding="utf-8") as f:
                data = _json.load(f)
            anniversaire_data.update(data.get("anniversaires", {}))
            pets_data.update(data.get("pets", {}))
            for k, v in data.get("achievements", {}).items():
                achievements_data[k] = set(v)
            for k, v in data.get("user_stats", {}).items():
                user_stats[k].update(v)
            invite_counts.update(data.get("invite_counts", {}))
            for k, v in data.get("inventaire", {}).items():
                inventaire[k].update(v)
            claim_reduction.update(data.get("claim_reduction", {}))
            print(f"[Load] ✅ Social chargé")
        except Exception as e:
            print(f"[Load] Erreur social: {e}")
    # Bank
    if _os.path.exists(DATA_FILES["bank"]):
        try:
            with open(DATA_FILES["bank"], "r", encoding="utf-8") as f:
                data = _json.load(f)
            for uid, val in data.items():
                bank_data[uid].update(val)
            print(f"[Load] ✅ Bank: {len(data)} membres")
        except Exception as e:
            print(f"[Load] Erreur bank: {e}")

@tasks.loop(minutes=10)
async def autosave():
    """Sauvegarde automatique toutes les 10 minutes"""
    save_all_data()
    print("[AutoSave] ✅ Données sauvegardées")

# ============================================================
#  EVENTS AUTOMATIQUES — Récupérés de l'original
# ============================================================

# Variables d'état des events
coffre_actif = {}           # {channel_id: {contenu, expires}}
nuit_chasse_active = False  # Bool global
marche_noir_actif = {}      # {card_key: {prix, expires}}

# Liste des boss possibles pour les invasions

# ─────────────────────────────────────────────────────────────
#  📦 SPAWN COFFRE — toutes les 30-90 min, 1 gagnant, 100-500p
# ─────────────────────────────────────────────────────────────
@tasks.loop(minutes=60)
async def spawn_coffre():
    """Coffre aléatoire (~30% par heure). Premier à .ouvrir gagne."""
    if not planning_actif:
        return
    if random.random() > 0.30:
        return
    for guild in bot.guilds:
        try:
            channel = (guild.get_channel(SALON_GACHA_ID) if SALON_GACHA_ID else None) or guild.system_channel
            if channel:
                await run_coffre(channel)
        except Exception as e:
            print(f"[spawn_coffre] Erreur: {e}")

# ─────────────────────────────────────────────────────────────
#  🌙 NUIT DE CHASSE — boost Mythique x2 pendant 2h
# ─────────────────────────────────────────────────────────────
@tasks.loop(hours=12)
async def nuit_de_chasse():
    """Toutes les 12h, 15% de chance — taux Mythique ×2 pendant 2h"""
    if not planning_actif:
        return
    if random.random() > 0.15:
        return
    for guild in bot.guilds:
        try:
            channel = (guild.get_channel(SALON_GACHA_ID) if SALON_GACHA_ID else None) or guild.system_channel
            if channel:
                await run_nuit_chasse(channel, guild)
        except Exception as e:
            print(f"[nuit_de_chasse] Erreur: {e}")

# ─────────────────────────────────────────────────────────────
#  🕶️ MARCHÉ NOIR — toutes les 48h, 3 cartes rares à acheter
# ─────────────────────────────────────────────────────────────
@tasks.loop(hours=48)
async def marche_noir_task():
    """Toutes les 48h, 60% de chance — Marché Noir pendant 24h"""
    if not planning_actif:
        return
    if random.random() > 0.60:
        return
    for guild in bot.guilds:
        try:
            channel = (guild.get_channel(SALON_BOUTIQUE_ID or SALON_GACHA_ID)
                       if (SALON_BOUTIQUE_ID or SALON_GACHA_ID) else None) or guild.system_channel
            if channel:
                await run_marche_noir(channel, guild)
        except Exception as e:
            print(f"[marche_noir_task] Erreur: {e}")

@bot.command(name="ouvrir", aliases=["coffre", "open"])
async def ouvrir_cmd(ctx):
    """Ouvrir le coffre actif dans le salon — premier arrivé, premier servi"""
    import time as _t
    channel_id = ctx.channel.id
    now = _t.time()
    if channel_id not in coffre_actif or coffre_actif[channel_id].get("expires", 0) < now:
        return await ctx.send("❌ Aucun coffre disponible ici pour l'instant !", delete_after=5)
    coffre = coffre_actif.pop(channel_id)
    uid = str(ctx.author.id)
    gain = coffre.get("contenu", random.randint(100, 500))
    economy_data[uid]["coins"] += gain
    embed = discord.Embed(
        title="📦 Coffre ouvert !",
        description=f"🎉 **{ctx.author.mention}** a ouvert le coffre et gagné **{gain} pièces** ! 💰",
        color=0xf1c40f
    )
    await ctx.send(embed=embed)

# ============================================================
#  👋 ARRIVÉES & DÉPARTS — Bienvenue, aurevoir, invitations
# ============================================================
async def _refresh_invite_cache(guild):
    """Met à jour le cache des invitations d'un serveur"""
    try:
        guild_invites[guild.id] = {inv.code: (inv.uses or 0) for inv in await guild.invites()}
    except Exception:
        pass

async def _find_inviter(guild):
    """Compare le cache avant/après pour trouver qui a invité. Retourne le membre ou None"""
    try:
        avant = guild_invites.get(guild.id, {})
        invites = await guild.invites()
        inviter = None
        for inv in invites:
            if (inv.uses or 0) > avant.get(inv.code, 0):
                inviter = inv.inviter
                break
        guild_invites[guild.id] = {inv.code: (inv.uses or 0) for inv in invites}
        return inviter
    except Exception:
        return None

@bot.event
async def on_invite_create(invite):
    """Garde le cache d'invitations à jour quand un lien est créé"""
    if invite.guild:
        guild_invites.setdefault(invite.guild.id, {})[invite.code] = invite.uses or 0

@bot.event
async def on_member_join(member):
    """Message de bienvenue (image + texte) + suivi des invitations"""
    # ── Qui l'a invité ? ──
    inviter = await _find_inviter(member.guild)
    if inviter and not inviter.bot:
        invite_counts[str(inviter.id)] += 1
        if SALON_INVITATION_ID:
            salon_inv = member.guild.get_channel(SALON_INVITATION_ID)
            if salon_inv:
                try:
                    await salon_inv.send(embed=discord.Embed(
                        description=(
                            f"🔗 {member.mention} a rejoint grâce à {inviter.mention} !\n"
                            f"🎉 **{inviter.display_name}** en est à **{invite_counts[str(inviter.id)]} invitation(s)**."
                        ),
                        color=0x2ecc71))
                except Exception:
                    pass

    # ── Message de bienvenue ──
    channel = member.guild.get_channel(SALON_BIENVENUE_ID) if SALON_BIENVENUE_ID else None
    if not channel:
        channel = member.guild.system_channel
    if not channel:
        return

    n = member.guild.member_count
    prophecies = [
        "Celui qui arrive en {n}ème position vaincra par la ruse, jamais par la force.",
        "Le {n}ème membre du QG marquera l'histoire de son passage.",
        "Une âme errante depuis longtemps trouve enfin sa place au {n}ème rang.",
        "Quand le {n}ème entrera, les équilibres du QG changeront à jamais.",
        "Le {n}ème nom inscrit dans les annales résonnera longtemps après son départ.",
    ]
    prophetie = random.choice(prophecies).replace("{n}", str(n))

    salon_guide = member.guild.get_channel(SALON_GUIDE_ID) if SALON_GUIDE_ID else None
    lien_guide = (f"📖 Tout est expliqué dans {salon_guide.mention} — passe y jeter un œil.\n"
                  if salon_guide else "")

    texte = (
        f"🔮 **PROPHÉTIE N°{n:03d}**\n"
        f"> *{prophetie}*\n\n"
        f"{member.mention}, installe-toi !\n"
        f"{lien_guide}"
        f"🎬 Ou lance `.dramarec` tout de suite pour ta première recommandation."
    )

    if PIL_OK:
        try:
            buf = await generate_welcome_card(member)
            return await channel.send(content=texte,
                                      file=discord.File(buf, filename="bienvenue.png"))
        except Exception as e:
            print(f"[Bienvenue] Erreur image : {e}")

    embed = discord.Embed(description=texte, color=0xff6b9d)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text="QG Kdrama • Ta place t'attendait",
                     icon_url=member.guild.icon.url if member.guild.icon else None)
    try:
        await channel.send(embed=embed)
    except Exception as e:
        print(f"[Bienvenue] Erreur envoi : {e}")

@bot.event
async def on_member_remove(member):
    """Message d'aurevoir (image + texte)"""
    channel = member.guild.get_channel(SALON_AUREVOIR_ID) if SALON_AUREVOIR_ID else None
    if not channel:
        return

    citations = [
        ("Même si tu pars, tu resteras dans nos mémoires.", "esprit de Clannad"),
        ("Les adieux sont douloureux, peu importe combien de fois on les vit.", "esprit de Violet Evergarden"),
        ("Partir ne veut pas dire oublier.", "esprit de Your Lie in April"),
        ("On se retrouvera, même si ce n'est pas dans ce monde.", "esprit d'Angel Beats"),
        ("Les liens qu'on tisse ne disparaissent pas avec les adieux.", "esprit de Naruto"),
        ("Toute rencontre porte en elle sa séparation.", "esprit de Bleach"),
    ]
    citation, source = random.choice(citations)

    texte = (
        f"💔 **{member.display_name}** a quitté le QG.\n\n"
        f"> *« {citation} »*\n"
        f"— {source}\n\n"
        f"🏯 Il reste **{member.guild.member_count} membres**."
    )

    if PIL_OK:
        try:
            buf = await generate_goodbye_card(member)
            return await channel.send(content=texte,
                                      file=discord.File(buf, filename="aurevoir.png"))
        except Exception as e:
            print(f"[Aurevoir] Erreur image : {e}")

    embed = discord.Embed(description=texte, color=0x5d6d7e)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text="QG Kdrama • À bientôt, peut-être",
                     icon_url=member.guild.icon.url if member.guild.icon else None)
    try:
        await channel.send(embed=embed)
    except Exception as e:
        print(f"[Aurevoir] Erreur envoi : {e}")

@bot.event
async def on_member_update(before, after):
    """Annonce quand un membre boost le serveur"""
    if before.premium_since is not None or after.premium_since is None:
        return
    if not SALON_BOOST_ID:
        return
    channel = after.guild.get_channel(SALON_BOOST_ID)
    if not channel:
        return
    total = after.guild.premium_subscription_count or 0
    embed = discord.Embed(
        title="💎 NOUVEAU BOOST !",
        description=(
            f"### 🌟 {after.mention} vient de booster le QG Kdrama !\n\n"
            f"Le serveur compte maintenant **{total} boost(s)**.\n"
            f"Merci du fond du cœur 💜"
        ),
        color=0xff73fa)
    embed.set_thumbnail(url=after.display_avatar.url)
    embed.set_footer(
        text="QG Kdrama • Merci aux boosteurs 🚀",
        icon_url=after.guild.icon.url if after.guild.icon else None)
    try:
        await channel.send(embed=embed)
    except Exception as e:
        print(f"[Boost] Erreur envoi : {e}")

@bot.event
async def on_error(event, *args, **kwargs):
    """Attrape les erreurs d'événements au lieu de les perdre silencieusement"""
    import traceback
    print(f"❌ Erreur dans l'événement '{event}' :")
    traceback.print_exc()

@bot.event
async def on_command_error(ctx, error):
    """Messages d'erreur clairs au lieu d'un silence total"""
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingPermissions):
        return await ctx.send("❌ Tu n'as pas la permission d'utiliser cette commande.", delete_after=8)
    if isinstance(error, commands.MissingRequiredArgument):
        return await ctx.send(f"❌ Il manque un argument : `{error.param.name}`\nTape `.help` pour voir l'usage.", delete_after=10)
    if isinstance(error, commands.BadArgument):
        return await ctx.send("❌ Argument invalide — vérifie la commande avec `.help`.", delete_after=8)
    if isinstance(error, commands.CommandOnCooldown):
        return await ctx.send(f"⏳ Patiente encore **{int(error.retry_after)}s**.", delete_after=8)
    if isinstance(error, commands.NoPrivateMessage):
        return await ctx.send("❌ Cette commande ne marche que sur le serveur.")
    # Vraie erreur : on prévient et on log
    import traceback
    print(f"[Erreur] {ctx.command} → {type(error).__name__}: {error}")
    traceback.print_exception(type(error), error, error.__traceback__)
    try:
        await ctx.send("❌ Une erreur est survenue — un admin a été notifié dans les logs.", delete_after=10)
    except Exception:
        pass

# ============================================================
#  🎭 RÉACTIONS — Autorole, rôles par réaction, règlement, Hall of Fame
# ============================================================
@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    member = guild.get_member(payload.user_id)
    if not member or member.bot:
        return
    emoji = str(payload.emoji)

    # ── Règlement : ✅ donne le rôle Membre ──
    if SALON_REGLEMENT_ID and payload.channel_id == SALON_REGLEMENT_ID and emoji == "✅":
        role = guild.get_role(REGLEMENT_ROLE_ID) if REGLEMENT_ROLE_ID else None
        if not role:
            role = discord.utils.get(guild.roles, name=ROLE_MEMBRE_NAME)
        if role and role not in member.roles:
            try:
                await member.add_roles(role, reason="Règlement accepté")
            except discord.Forbidden:
                print("[Règlement] Permission refusée pour attribuer le rôle")
        elif not role:
            print(f"[Règlement] Rôle introuvable (ID={REGLEMENT_ROLE_ID}, nom={ROLE_MEMBRE_NAME})")

    # ── Rôles par réaction simples (.rolecreate) ──
    if payload.message_id in reaction_roles:
        data = reaction_roles[payload.message_id]
        if emoji == data["emoji"]:
            role = guild.get_role(data["role_id"])
            if role:
                try:
                    await member.add_roles(role, reason="Rôle par réaction")
                except discord.Forbidden:
                    pass

    # ── Panels autorole (.autorole) ──
    for panel in autorole_panels.get(str(guild.id), []):
        if str(payload.message_id) != panel["message_id"]:
            continue
        for r in panel["roles"]:
            if r["emoji"] == emoji:
                role = guild.get_role(int(r["role_id"]))
                if role:
                    try:
                        await member.add_roles(role, reason="Autorole")
                    except discord.Forbidden:
                        pass
                break

    # ── Hall of Fame : message très réagi ──
    if SALON_HOF_ID and emoji in HOF_EMOJIS and payload.message_id not in HOF_MESSAGES:
        channel = guild.get_channel(payload.channel_id)
        hof_channel = guild.get_channel(SALON_HOF_ID)
        if channel and hof_channel and channel.id != SALON_HOF_ID:
            try:
                msg = await channel.fetch_message(payload.message_id)
            except Exception:
                return
            total = sum(r.count for r in msg.reactions if str(r.emoji) in HOF_EMOJIS)
            if total >= HOF_SEUIL and not msg.author.bot:
                HOF_MESSAGES.add(msg.id)
                embed = discord.Embed(
                    description=msg.content[:2000] or "*(message sans texte)*",
                    color=0xf1c40f,
                    timestamp=msg.created_at)
                embed.set_author(name=msg.author.display_name, icon_url=msg.author.display_avatar.url)
                embed.add_field(name="\u200b", value=f"[↗️ Aller au message]({msg.jump_url})", inline=False)
                if msg.attachments and msg.attachments[0].content_type and "image" in msg.attachments[0].content_type:
                    embed.set_image(url=msg.attachments[0].url)
                embed.set_footer(text=f"🏆 Hall of Fame • {total} réactions • #{channel.name}")
                try:
                    await hof_channel.send(embed=embed)
                except Exception as e:
                    print(f"[HOF] Erreur envoi : {e}")

@bot.event
async def on_raw_reaction_remove(payload):
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    member = guild.get_member(payload.user_id)
    if not member or member.bot:
        return
    emoji = str(payload.emoji)

    # ── Rôles par réaction simples ──
    if payload.message_id in reaction_roles:
        data = reaction_roles[payload.message_id]
        if emoji == data["emoji"]:
            role = guild.get_role(data["role_id"])
            if role:
                try:
                    await member.remove_roles(role, reason="Réaction retirée")
                except discord.Forbidden:
                    pass

    # ── Panels autorole ──
    for panel in autorole_panels.get(str(guild.id), []):
        if str(payload.message_id) != panel["message_id"]:
            continue
        for r in panel["roles"]:
            if r["emoji"] == emoji:
                role = guild.get_role(int(r["role_id"]))
                if role:
                    try:
                        await member.remove_roles(role, reason="Autorole retiré")
                    except discord.Forbidden:
                        pass
                break

@bot.event
async def on_ready():
    load_all_data()
    load_autorole()
    load_scheduled_events()
    for g in bot.guilds:
        await _refresh_invite_cache(g)
    check_anniversaires.start()
    scheduler_task.start()
    girls_auto_tasks.start()
    autosave.start()
    spawn_coffre.start()
    nuit_de_chasse.start()
    marche_noir_task.start()
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name="🎬 Kdrama • .help")
    )
    print(f"✅ Bot QG Kdrama connecté : {bot.user}")
    print(f"✅ Serveurs : {len(bot.guilds)}")

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
