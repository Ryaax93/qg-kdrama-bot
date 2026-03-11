import discord
from discord.ext import commands, tasks
import asyncio
import random
import json
import os
import datetime
from collections import defaultdict

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

# ---------- Titres selon niveau ----------
TIERS = [
    (1,  "🎬 Spectateur Débutant"),
    (5,  "📺 Fan de Kdrama"),
    (10, "🎮 Gamer Kdrama"),
    (15, "✨ Otaku Confirmé"),
    (20, "👑 Légende du QG"),
    (30, "💫 Dieu du QG Kdrama"),
]

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
]

QUIZ_ANIME = [
    {"q": "Quel est le vrai nom de Light Yagami dans Death Note ?", "a": "light yagami"},
    {"q": "Dans Demon Slayer, quelle est la technique signature de Tanjiro ?", "a": "respiration de l'eau"},
    {"q": "Combien de membres compte l'équipe de volleyball de Karasuno dans Haikyuu ?", "a": "12"},
    {"q": "Dans FMA Brotherhood, quel est l'équivalent sacrifié par Ed pour ramener Alphonse ?", "a": "son bras"},
    {"q": "Quel animé se passe dans le monde des Titans derrière des murs ?", "a": "attack on titan"},
    {"q": "Comment s'appelle le démon que Tanjiro affronte dans Demon Slayer ?", "a": "muzan"},
    {"q": "Dans One Piece, quel est le fruit du diable de Luffy ?", "a": "gomu gomu"},
    {"q": "Quel est le prénom du personnage principal de Jujutsu Kaisen ?", "a": "yuji"},
    {"q": "Dans Your Lie in April, de quel instrument joue Kousei ?", "a": "piano"},
    {"q": "Combien de titans primordiaux existent dans Attack on Titan ?", "a": "9"},
]

QUIZ_GAMING = [
    {"q": "Dans Genshin Impact, quel est le nom de la région de départ ?", "a": "mondstadt"},
    {"q": "Dans Elden Ring, comment s'appelle le monde ouvert principal ?", "a": "entre-terre"},
    {"q": "Dans Valorant, combien de rounds faut-il gagner pour remporter une partie ?", "a": "13"},
    {"q": "Dans League of Legends, comment s'appelle la tour centrale à détruire ?", "a": "nexus"},
    {"q": "Dans Minecraft, quel matériau est le plus résistant ?", "a": "netherite"},
    {"q": "Quel est le nom du dragon final dans Skyrim ?", "a": "alduin"},
    {"q": "Dans Genshin Impact, quel élément représente Zhongli ?", "a": "géo"},
    {"q": "Dans Hollow Knight, comment s'appelle le royaume des insectes ?", "a": "hallownest"},
]

QUIZ_CULTURE = [
    {"q": "Quelle est la capitale de la Corée du Sud ?", "a": "séoul"},
    {"q": "En quelle année a eu lieu la Révolution française ?", "a": "1789"},
    {"q": "Qui a peint la Joconde ?", "a": "léonard de vinci"},
    {"q": "Quelle planète est la plus proche du Soleil ?", "a": "mercure"},
    {"q": "Combien de côtés a un hexagone ?", "a": "6"},
    {"q": "Quel est le plus grand océan du monde ?", "a": "pacifique"},
    {"q": "Dans quel pays se trouve la Tour de Pise ?", "a": "italie"},
    {"q": "Combien font 17 × 8 ?", "a": "136"},
    {"q": "Quelle est la langue la plus parlée au monde ?", "a": "mandarin"},
    {"q": "Qui a écrit Roméo et Juliette ?", "a": "shakespeare"},
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
    xp_data[uid]["xp"] += random.randint(3, 8)
    needed = xp_data[uid]["level"] * 100
    if xp_data[uid]["xp"] >= needed:
        xp_data[uid]["level"] += 1
        xp_data[uid]["xp"] = 0
        new_tier = get_tier(xp_data[uid]["level"])
        embed = discord.Embed(
            title="🎉 Level Up !",
            description=(
                f"{message.author.mention} est maintenant **niveau {xp_data[uid]['level']}** !\n"
                f"Nouveau titre : **{new_tier}**"
            ),
            color=0xff6b9d
        )
        await message.channel.send(embed=embed)

    # Réponses automatiques contextuelles
    content = message.content.lower()
    if any(w in content for w in ["goblin", "kdrama", "drama coréen"]):
        reactions = ["🕯️", "💜", "🎬", "😭"]
        await message.add_reaction(random.choice(reactions))
    elif any(w in content for w in ["anime", "animé", "manga"]):
        await message.add_reaction(random.choice(["⚔️", "✨", "💥", "🎌"]))
    elif any(w in content for w in ["gaming", "gamer", "jeux", "gg", "elden ring", "genshin"]):
        await message.add_reaction(random.choice(["🎮", "🏆", "💀", "⚡"]))

    await bot.process_commands(message)

# ============================================================
#  HELP
# ============================================================
@bot.command(name="help")
async def help_cmd(ctx, categorie: str = None):
    if categorie is None:
        # Menu principal
        embed = discord.Embed(
            title="📖 Aide — Bot QG Kdrama",
            description=(
                "Bienvenue ! Voici toutes les catégories de commandes.\n"
                "Tape `.help <catégorie>` pour voir les détails !\n\n"
                "**Exemple :** `.help kdrama` ou `.help loupgarou`"
            ),
            color=0xff6b9d
        )
        embed.add_field(name="🎬 `.help kdrama`", value="Dramas, recommandations, notes, watchlist", inline=True)
        embed.add_field(name="✨ `.help anime`", value="Animés, recommandations, citations", inline=True)
        embed.add_field(name="🎮 `.help gaming`", value="Jeux, LFG, mini-jeux", inline=True)
        embed.add_field(name="🃏 `.help gacha`", value="Cartes personnages à collectionner", inline=True)
        embed.add_field(name="🎬 `.help bracket`", value="Tournoi Kdrama & Animé", inline=True)
        embed.add_field(name="🎰 `.help casino`", value="Slot machine & jeux d'argent", inline=True)
        embed.add_field(name="🐉 `.help boss`", value="Boss de serveur & Arène PvP", inline=True)
        embed.add_field(name="🎯 `.help quiz`", value="Quiz solo et duel par thème", inline=True)
        embed.add_field(name="🎭 `.help minijeux`", value="Pendu, Devine le personnage", inline=True)
        embed.add_field(name="📊 `.help niveaux`", value="XP, rang, classement", inline=True)
        embed.add_field(name="💰 `.help economie`", value="Pièces, boutique, banque, vol", inline=True)
        embed.add_field(name="⚔️ `.help duels`", value="Défis entre membres", inline=True)
        embed.add_field(name="💍 `.help social`", value="Mariage, anniversaires, sondages", inline=True)
        embed.add_field(name="🐺 `.help loupgarou`", value="Jeu de rôle complet", inline=True)
        embed.add_field(name="🎫 `.help support`", value="Tickets d'aide", inline=True)
        embed.add_field(name="🛡️ `.help modo`", value="Outils de modération", inline=True)
        embed.add_field(name="😄 `.help fun`", value="Commandes fun et délire", inline=True)
        embed.set_footer(text="QG Kdrama 🎬 • Préfixe : .  •  Bon drama et bonnes parties !")
        await ctx.send(embed=embed)

    elif categorie.lower() == "anime":
        embed = discord.Embed(title="✨ Commandes Animé", color=0x5865F2)
        embed.add_field(name="`.anime`", value="Affiche un animé aléatoire avec sa note et son genre", inline=False)
        embed.add_field(name="`.animerec [genre]`", value="Recommande un animé selon le genre\nEx: `.animerec action` ou `.animerec romance`", inline=False)
        embed.add_field(name="`.animequote`", value="Affiche une citation culte d'un animé", inline=False)
        embed.set_footer(text="💡 Genres dispo : action, romance, sport, psychologique, fantasy...")
        await ctx.send(embed=embed)

    elif categorie.lower() == "gaming":
        embed = discord.Embed(title="🎮 Commandes Gaming", color=0x2ecc71)
        embed.add_field(name="`.gamerec [genre]`", value="Recommande un jeu vidéo selon le genre\nEx: `.gamerec rpg` ou `.gamerec fps`", inline=False)
        embed.add_field(name="`.lfg [jeu]`", value="Cherche des coéquipiers pour jouer ensemble\nEx: `.lfg Valorant` — les intéressés réagissent avec 🎮", inline=False)
        embed.add_field(name="`.rps <choix>`", value="Pierre Feuille Ciseaux contre le bot !\nEx: `.rps pierre` / `.rps feuille` / `.rps ciseaux`\n✅ Victoire = +20 pièces", inline=False)
        embed.add_field(name="`.dice [faces]`", value="Lance un dé ! Par défaut 6 faces\nEx: `.dice` ou `.dice 20` pour un dé à 20 faces", inline=False)
        await ctx.send(embed=embed)

    elif categorie.lower() == "niveaux":
        embed = discord.Embed(title="📊 Commandes Niveaux & XP", color=0xf1c40f)
        embed.add_field(name="`.rank [@joueur]`", value="Affiche ton niveau, XP et titre actuel\nEx: `.rank` ou `.rank @ami`", inline=False)
        embed.add_field(name="`.leaderboard`", value="Affiche le top 10 des membres les plus actifs du serveur", inline=False)
        embed.add_field(name="📈 Comment gagner de l'XP ?", value="Tu gagnes de l'XP automatiquement en **chattant** dans le serveur !\nChaque message = 3 à 8 XP aléatoires", inline=False)
        embed.add_field(name="🏆 Titres disponibles", value=(
            "Niv.1 → 🎬 Spectateur Débutant\n"
            "Niv.5 → 📺 Fan de Kdrama\n"
            "Niv.10 → 🎮 Gamer Kdrama\n"
            "Niv.15 → ✨ Otaku Confirmé\n"
            "Niv.20 → 👑 Légende du QG\n"
            "Niv.30 → 💫 Dieu du QG Kdrama"
        ), inline=False)
        await ctx.send(embed=embed)

    elif categorie.lower() == "duels":
        embed = discord.Embed(title="⚔️ Commandes Duels", color=0xe74c3c)
        embed.add_field(name="`.duel @joueur`", value="Lance un défi à un membre du serveur\nEx: `.duel @ami`", inline=False)
        embed.add_field(name="`.accept`", value="Accepte un défi qui t'a été lancé", inline=False)
        embed.add_field(name="`.decline`", value="Refuse un défi qui t'a été lancé", inline=False)
        embed.add_field(name="⚡ Comment ça marche ?", value=(
            "1. Tu lances `.duel @joueur`\n"
            "2. L'adversaire tape `.accept`\n"
            "3. Le bot tire au sort le gagnant\n"
            "4. Le gagnant remporte **50-200 pièces** au perdant !"
        ), inline=False)
        await ctx.send(embed=embed)

    elif categorie.lower() in ["loupgarou", "lg", "loup"]:
        embed = discord.Embed(title="🐺 Commandes Loup Garou", color=0x2c3e50)
        embed.add_field(name="🎙️ Narration vocale automatique !", value="Le bot rejoint le salon vocal et narre les phases avec une vraie voix française ! 🎭\n*(Rejoins un vocal avant de lancer la partie)*", inline=False)
        embed.add_field(name="`.lg`", value="Affiche l'aide complète du Loup Garou", inline=False)
        embed.add_field(name="`.lgroles`", value="Affiche tous les rôles disponibles et leurs pouvoirs", inline=False)
        embed.add_field(name="`.lgcreate`", value="Crée une nouvelle partie (tu deviens l'hôte)", inline=False)
        embed.add_field(name="`.lgjoin`", value="Rejoins la partie en attente", inline=False)
        embed.add_field(name="`.lgstart`", value="Lance la partie — envoie les rôles en DM + narration vocale de début 🎙️", inline=False)
        embed.add_field(name="`.lgvote @joueur`", value="Vote pour éliminer un suspect pendant le jour", inline=False)
        embed.add_field(name="`.lgnuit @joueur`", value="⚠️ En MP avec le bot — Action de nuit selon ton rôle\n• Loup : désigne ta victime\n• Voyante : découvre un rôle\n• Cupidon : lie deux amoureux", inline=False)
        embed.add_field(name="`.lgsorciere vie/mort @joueur`", value="⚠️ En MP — Utilise une potion\n• `vie` : sauve la victime de la nuit\n• `mort @joueur` : empoisonne quelqu'un", inline=False)
        embed.add_field(name="`.lgnextday`", value="Passe à la phase de jour — révèle les morts + narration vocale 🎙️ (hôte uniquement)", inline=False)
        embed.add_field(name="`.lgstatus`", value="Affiche les joueurs encore en vie et les éliminés", inline=False)
        embed.add_field(name="`.lgstop`", value="Annule la partie en cours (hôte ou admin)", inline=False)
        embed.set_footer(text="🐺 5 à 12 joueurs • Rôles en DM • Narration vocale automatique !")
        await ctx.send(embed=embed)

    elif categorie.lower() == "support":
        embed = discord.Embed(title="🎫 Commandes Support", color=0x5865F2)
        embed.add_field(name="`.ticket`", value="Ouvre un ticket de support privé\nUn salon secret est créé, visible uniquement par toi et le staff", inline=False)
        embed.add_field(name="`.close`", value="Ferme et supprime le ticket (dans le salon ticket uniquement)", inline=False)
        embed.set_footer(text="💡 Utilise le ticket pour contacter le staff en privé !")
        await ctx.send(embed=embed)

    elif categorie.lower() in ["modo", "moderation", "modération"]:
        embed = discord.Embed(title="🛡️ Commandes Modération", color=0x95a5a6)
        embed.add_field(name="`.ban @joueur [raison]`", value="Bannit définitivement un membre du serveur\nEx: `.ban @spam Publicité non autorisée`", inline=False)
        embed.add_field(name="`.kick @joueur [raison]`", value="Expulse un membre du serveur (il peut revenir)\nEx: `.kick @joueur Comportement inapproprié`", inline=False)
        embed.add_field(name="`.mute @joueur [minutes]`", value="Rend un membre muet pendant X minutes (10 par défaut)\nEx: `.mute @joueur 30`", inline=False)
        embed.add_field(name="`.unmute @joueur`", value="Retire le mute d'un membre avant la fin du timer", inline=False)
        embed.add_field(name="`.clear [nombre]`", value="Supprime X messages dans le salon (5 par défaut)\nEx: `.clear 10`", inline=False)
        embed.set_footer(text="⚠️ Réservé aux membres avec les permissions appropriées")
        await ctx.send(embed=embed)

    elif categorie.lower() == "gacha":
        embed = discord.Embed(title="🃏 Commandes Gacha", color=0xf1c40f)
        embed.add_field(name="`.gacha`", value="Tire une carte personnage aléatoire !\n💰 Coût : 50 pièces\nRaretés : 🔵 Commun | ⭐ Rare | 💎 Épique | 🌈 Légendaire", inline=False)
        embed.add_field(name="`.gacha10`", value="10 tirages d'un coup !\n💰 Coût : 400 pièces (économise 100 pièces !)", inline=False)
        embed.add_field(name="`.collection [@joueur]`", value="Voir ta collection de cartes complète\nEx: `.collection` ou `.collection @ami`", inline=False)
        embed.add_field(name="`.carte <nom>`", value="Voir une carte en détail avec son image\nEx: `.carte Naruto` ou `.carte Gojo`", inline=False)
        embed.set_footer(text="🌈 Légendaire = 3% | 💎 Épique = 15% | ⭐ Rare = 35% | 🔵 Commun = 47%")
        await ctx.send(embed=embed)

    elif categorie.lower() == "bracket":
        embed = discord.Embed(title="🎬 Commandes Bracket Tournoi", color=0xe74c3c)
        embed.add_field(name="`.bracket kdrama`", value="Lance le tournoi des meilleurs Kdramas !\n8 dramas s'affrontent en mode éliminatoire", inline=False)
        embed.add_field(name="`.bracket anime`", value="Lance le tournoi des meilleurs Animés !\n8 animés s'affrontent avec leurs affiches officielles", inline=False)
        embed.add_field(name="`.bracketskip`", value="Résout le match en cours immédiatement (admin)\nUtile si tu veux pas attendre 24h", inline=False)
        embed.add_field(name="`.bracketstop`", value="Annule le tournoi en cours (admin)", inline=False)
        embed.add_field(name="💡 Comment ça marche ?", value="1. Lance `.bracket kdrama` ou `.bracket anime`\n2. Vote 🅰️ ou 🅱️ sur chaque match\n3. Le bot gère les tours automatiquement\n4. Le champion est couronné à la fin ! 👑", inline=False)
        await ctx.send(embed=embed)

    elif categorie.lower() == "casino":
        embed = discord.Embed(title="🎰 Commandes Casino", color=0xf39c12)
        embed.add_field(name="`.slot [mise]`", value="Slot machine ! Tente ta chance !\nMise min: 10 pièces | max: 500 pièces\nEx: `.slot 100`", inline=False)
        embed.add_field(name="🎰 Symboles & Gains", value="3 identiques = JACKPOT 💰\n2 identiques = Paire (x2)\n👑 = x30 | 💎 = x75 | 🐉 = x50\n⚡ = x40 | 🦊 = x15 | 🗡️ = x10", inline=False)
        await ctx.send(embed=embed)

    elif categorie.lower() == "boss":
        embed = discord.Embed(title="🐉 Boss & Arène PvP", color=0xe74c3c)
        embed.add_field(name="`.boss`", value="Fait apparaître un boss de serveur ! (admin)\nTout le monde peut l'attaquer ensemble 🐉", inline=False)
        embed.add_field(name="`.attaque`", value="Attaque le boss en cours !\nCooldown : 30 secondes entre chaque attaque\n🏆 Récompenses pour tous les participants à la mort du boss !", inline=False)
        embed.add_field(name="`.arene @joueur`", value="Lance un combat PvP au tour par tour !\nChoisis parmi 6 attaques spéciales (Rasengan, Kamehameha...)\n🏆 Victoire = pièces + XP", inline=False)
        embed.set_footer(text="⚔️ Plus ton niveau est élevé, plus tes dégâts sont puissants !")
        await ctx.send(embed=embed)

    elif categorie.lower() == "fun":
        embed = discord.Embed(title="😄 Commandes Fun", color=0xff6b9d)
        embed.add_field(name="`.roast [@joueur]`", value="Se fait rôtir par le bot avec une vanne Kdrama/Gaming\nEx: `.roast` ou `.roast @ami`", inline=False)
        embed.add_field(name="`.compliment [@joueur]`", value="Reçois un compliment stylé façon Kdrama !\nEx: `.compliment` ou `.compliment @ami`", inline=False)
        embed.add_field(name="`.8ball <question>`", value="Pose une question à la boule magique du QG !\nEx: `.8ball Est-ce que je vais finir Goblin ce soir ?`", inline=False)
        embed.add_field(name="`.meme`", value="Affiche un meme aléatoire 😂", inline=False)
        embed.add_field(name="`.quiz`", value="Lance une question sur les Kdramas, animés ou jeux\n✅ Bonne réponse = pièces + XP bonus !", inline=False)
        await ctx.send(embed=embed)

    elif categorie.lower() in ["minijeux", "mini-jeux", "jeux"]:
        embed = discord.Embed(title="🎭 Mini-Jeux", color=0x9b59b6)
        embed.add_field(name="`.devine`", value="Devine le personnage d'un animé ou drama !\nIndices progressifs, tape 'indice' pour en avoir plus\n✅ Moins tu utilises d'indices = plus tu gagnes de pièces !", inline=False)
        embed.add_field(name="`.pendu`", value="Pendu avec des titres d'animés et de dramas !\nTape une lettre à la fois pour deviner le titre\n✅ Victoire = +100 pièces", inline=False)
        await ctx.send(embed=embed)

    elif categorie.lower() == "social":
        embed = discord.Embed(title="💍 Commandes Sociales", color=0xff6b9d)
        embed.add_field(name="`.marier @joueur`", value="Demande quelqu'un en mariage 💍\nL'autre personne doit accepter avec `.accepter`", inline=False)
        embed.add_field(name="`.accepter`", value="Accepte une demande en mariage 💜", inline=False)
        embed.add_field(name="`.refuser`", value="Refuse une demande en mariage 💔", inline=False)
        embed.add_field(name="`.divorcer`", value="Divorce de ton partenaire 😢", inline=False)
        embed.add_field(name="`.anniversaire JJ/MM`", value="Enregistre ton anniversaire\nEx: `.anniversaire 25/03`\nLe bot te souhaitera automatiquement !", inline=False)
        embed.add_field(name="`.anniversaire`", value="Voir tous les anniversaires du serveur 🎂", inline=False)
        embed.add_field(name="`.sondage \"Question?\" choix1 choix2`", value="Lance un sondage avec réactions\nEx: `.sondage \"Ce soir?\" Goblin Vincenzo Signal`", inline=False)
        embed.add_field(name="`.giveaway <durée> <prix>`", value="Lance un giveaway (admin uniquement)\nEx: `.giveaway 24h Rôle VIP` ou `.giveaway 1h 500 pièces`", inline=False)
        embed.add_field(name="`.stats`", value="Voir les statistiques du serveur 📊", inline=False)
        await ctx.send(embed=embed)

    elif categorie.lower() in ["economie", "économie"]:
        embed = discord.Embed(title="💰 Commandes Économie", color=0xf39c12)
        embed.add_field(name="`.daily`", value="Récupère tes pièces journalières (100-500 pièces)\n⏳ Disponible une fois toutes les 24h", inline=False)
        embed.add_field(name="`.balance [@joueur]`", value="Affiche ton solde de pièces", inline=False)
        embed.add_field(name="`.pay @joueur <montant>`", value="Envoie des pièces à quelqu'un\nEx: `.pay @ami 100`", inline=False)
        embed.add_field(name="`.steal @joueur`", value="Tente de voler des pièces ! (45% de réussite)\n⏳ Cooldown : 1h • Échec = tu paies une amende 😂", inline=False)
        embed.add_field(name="`.shop`", value="Voir la boutique du QG 🛒\nRôles exclusifs, Double XP et plus !", inline=False)
        embed.add_field(name="`.acheter <id>`", value="Acheter un item de la boutique\nIDs: `vip` `drama_king` `otaku` `gamer_pro` `double_xp`", inline=False)
        embed.add_field(name="`.banque depot <montant>`", value="Déposer des pièces à la banque\n📈 Intérêts : +5% toutes les 24h !", inline=False)
        embed.add_field(name="`.banque retrait`", value="Retirer tes pièces + intérêts accumulés", inline=False)
        embed.add_field(name="`.banque solde`", value="Voir ton solde bancaire et tes intérêts", inline=False)
        embed.add_field(name="💡 Comment gagner des pièces ?", value="`.daily` `.quiz` `.rps` `.duel` `.pendu` `.devine`", inline=False)
        await ctx.send(embed=embed)

    elif categorie.lower() == "kdrama":
        embed = discord.Embed(title="🎬 Commandes Kdrama", color=0xff6b9d)
        embed.add_field(name="`.drama`", value="Affiche un drama coréen aléatoire avec note et genre", inline=False)
        embed.add_field(name="`.dramarec [genre]`", value="Recommandation par genre\nEx: `.dramarec romance` ou `.dramarec thriller`", inline=False)
        embed.add_field(name="`.quote`", value="Citation inspirante d'un Kdrama", inline=False)
        embed.add_field(name="`.oppachallenge`", value="Défi fun lié aux Kdramas !", inline=False)
        embed.add_field(name="`.noter 9 Goblin`", value="Donne une note /10 à un drama\nLa moyenne du serveur est calculée automatiquement !", inline=False)
        embed.add_field(name="`.avis Goblin`", value="Voir la moyenne et les votes du serveur pour un drama", inline=False)
        embed.add_field(name="`.sorties`", value="Calendrier des prochaines sorties dramas/animés 📅", inline=False)
        embed.add_field(name="`.watch ajouter Goblin`", value="Ajouter un titre à ta watchlist perso 📋", inline=False)
        embed.add_field(name="`.watch liste`", value="Voir ta watchlist complète", inline=False)
        embed.add_field(name="`.watch vu Goblin`", value="Marquer un titre comme vu ✅", inline=False)
        embed.add_field(name="`.watch supprimer Goblin`", value="Supprimer un titre de ta watchlist", inline=False)
        embed.set_footer(text="💡 Genres dispo : romance, thriller, fantasy, historique, médical...")
        await ctx.send(embed=embed)



# ============================================================
#  KDRAMA COMMANDS
# ============================================================
@bot.command()
async def drama(ctx):
    """Affiche un drama aléatoire du top"""
    d = random.choice(KDRAMAS)
    embed = discord.Embed(
        title=f"{d['emoji']} {d['title']}",
        description=f"**Genre :** {d['genre']}\n**Note :** {d['note']}",
        color=0xff6b9d
    )
    embed.set_image(url=d['image'])
    embed.set_footer(text="💡 Tape .dramarec [genre] pour une recommandation personnalisée !")
    await ctx.send(embed=embed)

@bot.command()
async def dramarec(ctx, *, genre: str = None):
    if genre:
        filtered = [d for d in KDRAMAS if genre.lower() in d['genre'].lower()]
        if not filtered:
            filtered = KDRAMAS
    else:
        filtered = KDRAMAS
    d = random.choice(filtered)
    embed = discord.Embed(
        title=f"🎬 Recommandation Kdrama",
        description=f"**{d['emoji']} {d['title']}**\nGenre : {d['genre']} | {d['note']}",
        color=0xff6b9d
    )
    embed.set_image(url=d['image'])
    embed.set_footer(text="Good luck pour les feels 😭")
    await ctx.send(embed=embed)

@bot.command()
async def quote(ctx):
    embed = discord.Embed(title="💬 Quote Kdrama", description=random.choice(KDRAMA_QUOTES), color=0xc39bd3)
    await ctx.send(embed=embed)

@bot.command()
async def oppachallenge(ctx):
    challenges = [
        "Regarde un épisode de drama sans pleurer 😭 (impossible)",
        "Nomme 5 acteurs coréens en moins de 10 secondes !",
        "Décris un Kdrama en seulement 3 emojis dans ce chat !",
        "Ping quelqu'un qui doit absolument regarder Goblin !",
        "Dis nous : quel drama t'a le plus brisé le cœur ? 💔",
        "Recommande un drama à quelqu'un qui n'en a jamais vu !",
        "Qui est ton oppa/unnie de drama préféré(e) ? Justifie !",
    ]
    embed = discord.Embed(
        title="🎭 Oppa Challenge !",
        description=f"**{ctx.author.mention}, ton défi :**\n\n{random.choice(challenges)}",
        color=0xff6b9d
    )
    await ctx.send(embed=embed)

# ============================================================
#  ANIMÉ COMMANDS
# ============================================================
@bot.command()
async def anime(ctx):
    a = random.choice(ANIMES)
    embed = discord.Embed(
        title=f"{a['emoji']} {a['title']}",
        description=f"**Genre :** {a['genre']}\n**Note :** {a['note']}",
        color=0x5865F2
    )
    embed.set_image(url=a['image'])
    embed.set_footer(text="✨ Tape .animerec [genre] pour une recommandation !")
    await ctx.send(embed=embed)

@bot.command()
async def animerec(ctx, *, genre: str = None):
    if genre:
        filtered = [a for a in ANIMES if genre.lower() in a['genre'].lower()]
        if not filtered:
            filtered = ANIMES
    else:
        filtered = ANIMES
    a = random.choice(filtered)
    embed = discord.Embed(
        title="✨ Recommandation Animé",
        description=f"**{a['emoji']} {a['title']}**\nGenre : {a['genre']} | {a['note']}",
        color=0x5865F2
    )
    await ctx.send(embed=embed)

@bot.command()
async def animequote(ctx):
    embed = discord.Embed(
        title="💬 Quote Animé",
        description=random.choice(ANIME_QUOTES),
        color=0x5865F2
    )
    await ctx.send(embed=embed)

# ============================================================
#  GAMING COMMANDS
# ============================================================
@bot.command()
async def gamerec(ctx, *, genre: str = None):
    """Recommande un jeu"""
    if genre:
        filtered = [g for g in GAMES if genre.lower() in g['genre'].lower()]
        if not filtered:
            filtered = GAMES
    else:
        filtered = GAMES
    g = random.choice(filtered)
    embed = discord.Embed(
        title=f"🎮 Recommandation Gaming",
        description=f"**{g['emoji']} {g['title']}**\nGenre : {g['genre']}",
        color=0x2ecc71
    )
    await ctx.send(embed=embed)

@bot.command()
async def lfg(ctx, *, game: str = None):
    """LFG — Looking For Group"""
    game_name = game or "un jeu"
    embed = discord.Embed(
        title="🎮 LFG — Cherche des joueurs !",
        description=f"{ctx.author.mention} cherche des joueurs pour **{game_name}** !\nRéagis avec 🎮 si tu veux rejoindre !",
        color=0x2ecc71
    )
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("🎮")

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
    """Quiz solo — .quiz [kdrama/anime/gaming/culture/mix]"""
    theme = theme.lower()
    if theme not in QUIZ_THEMES:
        return await ctx.send(f"❌ Thème invalide ! Choisis parmi : `kdrama`, `anime`, `gaming`, `culture`, `mix`")
    if ctx.channel.id in active_quiz or ctx.channel.id in quiz_duels:
        return await ctx.send("❓ Un quiz est déjà en cours ici !")

    q = random.choice(QUIZ_THEMES[theme])
    active_quiz[ctx.channel.id] = {"answer": q["a"], "theme": theme}
    embed = discord.Embed(
        title=f"🎯 Quiz {THEME_LABELS[theme]}",
        description=f"**{q['q']}**",
        color=0xf1c40f
    )
    embed.set_footer(text="⏳ 30 secondes • Premier à répondre gagne !")
    await ctx.send(embed=embed)

    def check(m):
        return m.channel == ctx.channel and not m.author.bot

    try:
        msg = await bot.wait_for("message", check=check, timeout=30)
        data = active_quiz.pop(ctx.channel.id, None)
        if not data:
            return
        correct = data["answer"]
        if msg.content.lower().strip() == correct:
            prize = random.randint(50, 150)
            economy_data[str(msg.author.id)]["coins"] += prize
            xp_data[str(msg.author.id)]["xp"] += 30
            await ctx.send(embed=discord.Embed(
                description=f"✅ **{msg.author.display_name}** a trouvé ! +{prize} pièces & +30 XP 🎉",
                color=0x2ecc71
            ))
        else:
            await ctx.send(embed=discord.Embed(
                description=f"❌ Mauvaise réponse ! La bonne réponse était : **{correct}**",
                color=0xe74c3c
            ))
    except asyncio.TimeoutError:
        active_quiz.pop(ctx.channel.id, None)
        await ctx.send("⏰ Temps écoulé ! Personne n'a trouvé.")

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
        try:
            msg = await bot.wait_for("message", check=check_duel, timeout=20)
            if ctx.channel.id not in quiz_duels:
                break
            if msg.content.lower().strip() == q["a"]:
                quiz_duels[ctx.channel.id]["players"][msg.author.id]["score"] += 1
                score = quiz_duels[ctx.channel.id]["players"][msg.author.id]["score"]
                await ctx.send(embed=discord.Embed(
                    description=f"✅ **{msg.author.display_name}** a trouvé ! ({score} pt{'s' if score > 1 else ''})",
                    color=0x2ecc71
                ))
                answered = True
            else:
                await ctx.send(embed=discord.Embed(
                    description=f"❌ **{msg.author.display_name}** — Mauvaise réponse ! La réponse était : **{q['a']}**",
                    color=0xe74c3c
                ))
        except asyncio.TimeoutError:
            await ctx.send(embed=discord.Embed(
                description=f"⏰ Temps écoulé ! La réponse était : **{q['a']}**",
                color=0x95a5a6
            ))

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
        prize = random.randint(100, 300)
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
    embed = discord.Embed(title=f"📊 Fiche de {member.display_name}", color=0xff6b9d)
    embed.add_field(name="Titre", value=tier, inline=False)
    embed.add_field(name="Niveau", value=str(lvl))
    embed.add_field(name="XP", value=f"{xp}/{needed}")
    embed.add_field(name="Progression", value=f"`{bar}`", inline=False)
    embed.set_thumbnail(url=member.display_avatar.url)
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
    uid = str(ctx.author.id)
    now = datetime.datetime.utcnow()
    last = cooldowns.get(f"daily_{uid}")
    if last and (now - last).total_seconds() < 86400:
        reste = 86400 - (now - last).total_seconds()
        h, m = divmod(int(reste) // 60, 60)
        return await ctx.send(f"⏳ Reviens dans **{h}h {m}m** pour tes pièces journalières !")
    gain = random.randint(100, 500)
    economy_data[uid]["coins"] += gain
    cooldowns[f"daily_{uid}"] = now
    await ctx.send(embed=discord.Embed(
        description=f"💰 {ctx.author.mention} reçoit **{gain} pièces** ! Total : {economy_data[uid]['coins']} 🎬",
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
#  DUELS
# ============================================================
@bot.command()
async def duel(ctx, opponent: discord.Member):
    if opponent.bot or opponent == ctx.author:
        return await ctx.send("❌ Cible invalide !")
    duels[ctx.author.id] = opponent.id
    embed = discord.Embed(
        title="⚔️ Défi lancé !",
        description=f"{opponent.mention}, **{ctx.author.display_name}** te défie !\nTape `.accept` pour accepter ou `.decline` pour refuser.",
        color=0xe74c3c
    )
    await ctx.send(embed=embed)

@bot.command()
async def accept(ctx):
    challenger_id = next((k for k, v in duels.items() if v == ctx.author.id), None)
    if not challenger_id:
        return await ctx.send("❌ Aucun défi en attente.")
    challenger = ctx.guild.get_member(challenger_id)
    del duels[challenger_id]
    winner = random.choice([ctx.author, challenger])
    loser = challenger if winner == ctx.author else ctx.author
    prize = random.randint(50, 200)
    economy_data[str(winner.id)]["coins"] += prize
    economy_data[str(loser.id)]["coins"] = max(0, economy_data[str(loser.id)]["coins"] - prize)
    await ctx.send(embed=discord.Embed(
        title="⚔️ Résultat du duel !",
        description=f"🏆 **{winner.display_name}** bat **{loser.display_name}** et gagne **{prize} pièces** !",
        color=0xf1c40f
    ))

@bot.command()
async def decline(ctx):
    challenger_id = next((k for k, v in duels.items() if v == ctx.author.id), None)
    if challenger_id:
        del duels[challenger_id]
    await ctx.send(f"❌ {ctx.author.display_name} a refusé le duel.")

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

@bot.command()
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int = 5):
    await ctx.channel.purge(limit=amount + 1)
    msg = await ctx.send(embed=discord.Embed(description=f"🧹 {amount} message(s) supprimé(s).", color=0x3498db))
    await asyncio.sleep(3)
    await msg.delete()



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

    # Message de bienvenue normal (si pas de raid)
    if not raid_mode:
        channel = (
            discord.utils.get(member.guild.text_channels, name="général") or
            member.guild.system_channel
        )
        if channel:
            embed = discord.Embed(
                title="🎬 Bienvenue au QG Kdrama !",
                description=(
                    f"Salut {member.mention} ! 👋\n\n"
                    "Tu viens d'entrer dans le meilleur QG pour parler de :\n"
                    "🎬 **Kdramas** • 🎮 **Gaming** • ✨ **Animés**\n\n"
                    "Tape `.help` pour voir les commandes du bot !\n"
                    "_Bon visionnage et bonnes parties !_ 💫"
                ),
                color=0xff6b9d
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await channel.send(embed=embed)

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

@bot.command(name="sorties")
async def sorties_cmd(ctx):
    """Affiche le calendrier des prochaines sorties dramas/animés"""
    embed = discord.Embed(
        title="📅 Prochaines Sorties — Dramas & Animés",
        color=0xff6b9d
    )
    for s in SORTIES:
        embed.add_field(
            name=f"{s['type']} — {s['titre']}",
            value=f"📆 {s['date']} • 📺 {s['plateforme']}",
            inline=False
        )
    embed.set_footer(text="💡 Liste mise à jour manuellement — .help pour toutes les commandes")
    await ctx.send(embed=embed)

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
    active_pendu[ctx.channel.id] = {
        "mot": mot,
        "trouve": ["_" if c != " " else " " for c in mot],
        "lettres": [],
        "erreurs": 0,
        "max_erreurs": 6
    }

    await ctx.send(embed=_pendu_embed(active_pendu[ctx.channel.id]))

    def check(m):
        return m.channel == ctx.channel and not m.author.bot and len(m.content) == 1 and m.content.isalpha()

    while ctx.channel.id in active_pendu:
        game = active_pendu[ctx.channel.id]
        try:
            msg = await bot.wait_for("message", check=check, timeout=60)
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
    {"id": "vip", "nom": "🌟 Rôle VIP", "prix": 500, "description": "Rôle exclusif VIP du QG !"},
    {"id": "drama_king", "nom": "👑 Drama King/Queen", "prix": 800, "description": "Le titre ultime des fans de Kdrama !"},
    {"id": "otaku", "nom": "⚡ Otaku Elite", "prix": 800, "description": "Le titre des vrais fans d'animé !"},
    {"id": "gamer_pro", "nom": "🎮 Gamer Pro", "prix": 600, "description": "Pour les meilleurs gamers du QG !"},
    {"id": "double_xp", "nom": "⚡ Double XP (1h)", "prix": 300, "description": "Double ton XP pendant 1 heure !"},
]

shop_roles = {}  # {item_id: role_id}
double_xp_users = {}  # {user_id: end_timestamp}

@bot.command(name="shop")
async def shop_cmd(ctx):
    """Affiche la boutique du QG"""
    embed = discord.Embed(
        title="🛒 Boutique du QG Kdrama",
        description="Dépense tes pièces pour des rôles et bonus exclusifs !",
        color=0xf1c40f
    )
    uid = str(ctx.author.id)
    solde = economy_data[uid]["coins"]
    for item in SHOP_ITEMS:
        dispo = "✅" if solde >= item["prix"] else "❌"
        embed.add_field(
            name=f"{item['nom']} — {item['prix']} pièces {dispo}",
            value=f"{item['description']}\nAcheter : `.acheter {item['id']}`",
            inline=False
        )
    embed.set_footer(text=f"💰 Ton solde : {solde} pièces")
    await ctx.send(embed=embed)

@bot.command(name="acheter")
async def acheter_cmd(ctx, item_id: str = None):
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

    economy_data[uid]["coins"] -= item["prix"]

    # Double XP
    if item["id"] == "double_xp":
        import time
        double_xp_users[ctx.author.id] = time.time() + 3600
        return await ctx.send(embed=discord.Embed(
            description=f"⚡ {ctx.author.mention} a activé le **Double XP** pendant 1 heure ! Chatte pour en profiter 🎉",
            color=0x2ecc71
        ))

    # Rôles
    role_names = {
        "vip": "⭐ VIP",
        "drama_king": "👑 Drama King",
        "otaku": "⚡ Otaku Elite",
        "gamer_pro": "🎮 Gamer Pro",
    }
    role_name = role_names.get(item["id"])
    if role_name:
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        if not role:
            role = await ctx.guild.create_role(name=role_name, reason=f"Boutique QG — achat par {ctx.author.display_name}")
        await ctx.author.add_roles(role)

    await ctx.send(embed=discord.Embed(
        title="🛒 Achat réussi !",
        description=f"✅ {ctx.author.mention} a acheté **{item['nom']}** pour **{item['prix']} pièces** ! 🎉",
        color=0x2ecc71
    ))

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
@bot.command(name="sondage")
async def sondage_cmd(ctx, question: str = None, *choix):
    """
    .sondage "Question ?" Option1 Option2 Option3
    Ex: .sondage "Quel drama ce soir ?" Goblin Vincenzo Signal
    """
    if not question:
        return await ctx.send('❌ Usage: `.sondage "Question?" choix1 choix2 choix3`')
    if len(choix) < 2:
        return await ctx.send("❌ Donne au moins 2 choix !")
    if len(choix) > 9:
        return await ctx.send("❌ Maximum 9 choix !")

    numeros = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
    description = "\n".join([f"{numeros[i]} {c}" for i, c in enumerate(choix)])

    embed = discord.Embed(
        title=f"📊 {question}",
        description=description,
        color=0x5865F2
    )
    embed.set_footer(text=f"Sondage lancé par {ctx.author.display_name}")
    msg = await ctx.send(embed=embed)
    for i in range(len(choix)):
        await msg.add_reaction(numeros[i])

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

    embed = discord.Embed(title=f"📊 Statistiques — {guild.name}", color=0x5865F2)
    embed.add_field(name="👥 Membres", value=f"Total: {total_members}\nHumains: {humains}\nBots: {bots}\nEn ligne: {online}", inline=True)
    embed.add_field(name="💬 Salons", value=f"Texte: {len(guild.text_channels)}\nVocal: {len(guild.voice_channels)}", inline=True)
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
#  🃏 GACHA PERSONNAGES
# ============================================================
GACHA_PERSONNAGES = [
    # LÉGENDAIRES
    {"nom": "Naruto Uzumaki", "anime": "Naruto", "rarete": "Légendaire", "emoji": "🌈", "force": 95, "image": "https://upload.wikimedia.org/wikipedia/en/9/9a/NarutoUzumaki.png"},
    {"nom": "Son Goku", "anime": "Dragon Ball Z", "rarete": "Légendaire", "emoji": "🌈", "force": 98, "image": "https://upload.wikimedia.org/wikipedia/en/a/a7/Gokugteenaf.jpg"},
    {"nom": "Monkey D. Luffy", "anime": "One Piece", "rarete": "Légendaire", "emoji": "🌈", "force": 94, "image": "https://upload.wikimedia.org/wikipedia/en/e/e9/Monkey_D_Luffy.png"},
    {"nom": "Levi Ackerman", "anime": "Attack on Titan", "rarete": "Légendaire", "emoji": "🌈", "force": 97, "image": "https://upload.wikimedia.org/wikipedia/en/6/60/Levi_Ackerman_anime.png"},
    {"nom": "Itachi Uchiha", "anime": "Naruto", "rarete": "Légendaire", "emoji": "🌈", "force": 96, "image": "https://upload.wikimedia.org/wikipedia/en/thumb/2/27/Itachi_Uchiha.PNG/220px-Itachi_Uchiha.PNG"},
    # ÉPIQUES
    {"nom": "Tanjiro Kamado", "anime": "Demon Slayer", "rarete": "Épique", "emoji": "💎", "force": 82, "image": "https://upload.wikimedia.org/wikipedia/en/3/3c/Tanjiro_Kamado.png"},
    {"nom": "Satoru Gojo", "anime": "Jujutsu Kaisen", "rarete": "Épique", "emoji": "💎", "force": 90, "image": "https://upload.wikimedia.org/wikipedia/en/6/6a/Gojo_Satoru_anime.png"},
    {"nom": "Edward Elric", "anime": "FMA Brotherhood", "rarete": "Épique", "emoji": "💎", "force": 80, "image": "https://upload.wikimedia.org/wikipedia/en/thumb/6/6b/Edward_Elric.png/220px-Edward_Elric.png"},
    {"nom": "Light Yagami", "anime": "Death Note", "rarete": "Épique", "emoji": "💎", "force": 78, "image": "https://upload.wikimedia.org/wikipedia/en/thumb/7/7a/Light_yagami.jpg/220px-Light_yagami.jpg"},
    {"nom": "Eren Yeager", "anime": "Attack on Titan", "rarete": "Épique", "emoji": "💎", "force": 85, "image": "https://upload.wikimedia.org/wikipedia/en/thumb/e/e0/Eren_Yeager.PNG/220px-Eren_Yeager.PNG"},
    {"nom": "Hinata Shoyo", "anime": "Haikyuu", "rarete": "Épique", "emoji": "💎", "force": 75, "image": "https://upload.wikimedia.org/wikipedia/en/thumb/0/0e/Shoyo_Hinata.png/220px-Shoyo_Hinata.png"},
    # RARES
    {"nom": "Zenitsu Agatsuma", "anime": "Demon Slayer", "rarete": "Rare", "emoji": "⭐", "force": 65, "image": "https://upload.wikimedia.org/wikipedia/en/thumb/b/b9/Zenitsu_Agatsuma.png/220px-Zenitsu_Agatsuma.png"},
    {"nom": "Roronoa Zoro", "anime": "One Piece", "rarete": "Rare", "emoji": "⭐", "force": 70, "image": "https://upload.wikimedia.org/wikipedia/en/thumb/1/15/RoronoaZoro.png/220px-RoronoaZoro.png"},
    {"nom": "Vegeta", "anime": "Dragon Ball Z", "rarete": "Rare", "emoji": "⭐", "force": 72, "image": "https://upload.wikimedia.org/wikipedia/en/thumb/7/77/Vegeta.jpg/220px-Vegeta.jpg"},
    {"nom": "Sasuke Uchiha", "anime": "Naruto", "rarete": "Rare", "emoji": "⭐", "force": 68, "image": "https://upload.wikimedia.org/wikipedia/en/thumb/b/b7/Sasuke_Uchiha.png/220px-Sasuke_Uchiha.png"},
    {"nom": "Inosuke Hashibira", "anime": "Demon Slayer", "rarete": "Rare", "emoji": "⭐", "force": 63, "image": "https://upload.wikimedia.org/wikipedia/en/thumb/b/b3/Inosuke_Hashibira.png/220px-Inosuke_Hashibira.png"},
    # COMMUNS
    {"nom": "Krillin", "anime": "Dragon Ball Z", "rarete": "Commun", "emoji": "🔵", "force": 35, "image": "https://upload.wikimedia.org/wikipedia/en/thumb/9/9b/Krillin.jpg/220px-Krillin.jpg"},
    {"nom": "Rock Lee", "anime": "Naruto", "rarete": "Commun", "emoji": "🔵", "force": 42, "image": "https://upload.wikimedia.org/wikipedia/en/thumb/5/5d/Rock_Lee.png/220px-Rock_Lee.png"},
    {"nom": "Usopp", "anime": "One Piece", "rarete": "Commun", "emoji": "🔵", "force": 38, "image": "https://upload.wikimedia.org/wikipedia/en/thumb/e/e5/Usopp.png/220px-Usopp.png"},
    {"nom": "Mineta", "anime": "My Hero Academia", "rarete": "Commun", "emoji": "🔵", "force": 20, "image": "https://upload.wikimedia.org/wikipedia/en/thumb/d/d7/Minoru_Mineta.png/220px-Minoru_Mineta.png"},
]

GACHA_RARETE_POIDS = {
    "Légendaire": 3,
    "Épique": 15,
    "Rare": 35,
    "Commun": 47,
}

GACHA_COULEURS = {
    "Légendaire": 0xf1c40f,
    "Épique": 0x9b59b6,
    "Rare": 0x3498db,
    "Commun": 0x95a5a6,
}

gacha_collections = defaultdict(list)  # {user_id: [nom_perso, ...]}
gacha_cooldowns = {}

def gacha_tirer():
    pool = []
    for p in GACHA_PERSONNAGES:
        pool.extend([p] * GACHA_RARETE_POIDS[p["rarete"]])
    return random.choice(pool)

@bot.command(name="gacha")
async def gacha_cmd(ctx):
    """Tire une carte personnage ! — .gacha (coûte 50 pièces)"""
    uid = str(ctx.author.id)
    cout = 50
    if economy_data[uid]["coins"] < cout:
        return await ctx.send(f"❌ Il te faut **{cout} pièces** pour faire un tirage ! Tu en as {economy_data[uid]['coins']}.")

    economy_data[uid]["coins"] -= cout
    perso = gacha_tirer()
    gacha_collections[uid].append(perso["nom"])

    couleur = GACHA_COULEURS[perso["rarete"]]
    embed = discord.Embed(
        title=f"{perso['emoji']} {perso['rarete'].upper()} !",
        description=f"**{ctx.author.mention}** a obtenu :\n\n# {perso['nom']}\n🎌 *{perso['anime']}*\n⚔️ Force : **{perso['force']}/100**",
        color=couleur
    )
    embed.set_image(url=perso["image"])
    embed.set_footer(text=f"💰 -{cout} pièces | Total cartes : {len(gacha_collections[uid])} | .collection pour voir toutes tes cartes")
    await ctx.send(embed=embed)

@bot.command(name="gacha10")
async def gacha10_cmd(ctx):
    """Tire 10 cartes d'un coup ! — .gacha10 (coûte 400 pièces)"""
    uid = str(ctx.author.id)
    cout = 400
    if economy_data[uid]["coins"] < cout:
        return await ctx.send(f"❌ Il te faut **{cout} pièces** pour 10 tirages !")

    economy_data[uid]["coins"] -= cout
    tirages = [gacha_tirer() for _ in range(10)]
    for p in tirages:
        gacha_collections[uid].append(p["nom"])

    # Afficher le résumé
    embed = discord.Embed(
        title=f"🎰 10 Tirages Gacha — {ctx.author.display_name}",
        color=0xf1c40f
    )
    lines = ""
    meilleur = max(tirages, key=lambda x: x["force"])
    for p in tirages:
        lines += f"{p['emoji']} **{p['nom']}** — {p['rarete']} ({p['anime']})\n"
    embed.description = lines
    embed.set_image(url=meilleur["image"])
    embed.set_footer(text=f"⭐ Meilleur tirage : {meilleur['nom']} | 💰 -{cout} pièces")
    await ctx.send(embed=embed)

@bot.command(name="collection")
async def collection_cmd(ctx, member: discord.Member = None):
    """Voir ta collection de cartes — .collection [@joueur]"""
    target = member or ctx.author
    uid = str(target.id)
    cartes = gacha_collections[uid]
    if not cartes:
        return await ctx.send(f"📭 **{target.display_name}** n'a aucune carte ! Fais `.gacha` pour commencer !")

    # Compter par rareté
    compteur = defaultdict(list)
    for nom in cartes:
        perso = next((p for p in GACHA_PERSONNAGES if p["nom"] == nom), None)
        if perso:
            compteur[perso["rarete"]].append(nom)

    embed = discord.Embed(
        title=f"📚 Collection de {target.display_name}",
        description=f"**{len(cartes)} cartes** au total",
        color=0xf1c40f
    )
    for rarete in ["Légendaire", "Épique", "Rare", "Commun"]:
        if compteur[rarete]:
            emoji = {"Légendaire": "🌈", "Épique": "💎", "Rare": "⭐", "Commun": "🔵"}[rarete]
            noms = ", ".join(set(compteur[rarete]))
            embed.add_field(name=f"{emoji} {rarete} ({len(compteur[rarete])})", value=noms, inline=False)
    await ctx.send(embed=embed)

@bot.command(name="carte")
async def carte_cmd(ctx, *, nom: str = None):
    """Voir une carte en détail — .carte Naruto"""
    if not nom:
        return await ctx.send("❌ Précise un nom ! Ex: `.carte Naruto`")
    perso = next((p for p in GACHA_PERSONNAGES if nom.lower() in p["nom"].lower()), None)
    if not perso:
        return await ctx.send(f"❌ Personnage `{nom}` introuvable !")
    embed = discord.Embed(
        title=f"{perso['emoji']} {perso['nom']}",
        description=f"🎌 **{perso['anime']}**\n⭐ Rareté : **{perso['rarete']}**\n⚔️ Force : **{perso['force']}/100**",
        color=GACHA_COULEURS[perso["rarete"]]
    )
    embed.set_image(url=perso["image"])
    await ctx.send(embed=embed)

# ============================================================
#  🎬 BRACKET TOURNOI
# ============================================================
BRACKET_KDRAMA = [
    {"nom": "Goblin", "image": "https://upload.wikimedia.org/wikipedia/en/thumb/6/63/Goblin_poster.jpg/220px-Goblin_poster.jpg"},
    {"nom": "Vincenzo", "image": "https://upload.wikimedia.org/wikipedia/en/thumb/5/57/Vincenzo_poster.jpg/220px-Vincenzo_poster.jpg"},
    {"nom": "Squid Game", "image": "https://upload.wikimedia.org/wikipedia/en/thumb/3/39/Squid_Game_poster.jpg/220px-Squid_Game_poster.jpg"},
    {"nom": "Crash Landing on You", "image": "https://upload.wikimedia.org/wikipedia/en/thumb/5/5e/Crash_Landing_on_You.jpg/220px-Crash_Landing_on_You.jpg"},
    {"nom": "Itaewon Class", "image": "https://upload.wikimedia.org/wikipedia/en/thumb/0/09/Itaewon_Class.jpg/220px-Itaewon_Class.jpg"},
    {"nom": "Signal", "image": "https://upload.wikimedia.org/wikipedia/en/thumb/7/79/Signal_2016_TV_series.jpg/220px-Signal_2016_TV_series.jpg"},
    {"nom": "Reply 1988", "image": "https://upload.wikimedia.org/wikipedia/en/thumb/8/82/Reply_1988.jpg/220px-Reply_1988.jpg"},
    {"nom": "Kingdom", "image": "https://upload.wikimedia.org/wikipedia/en/thumb/1/16/Kingdom_Netflix.jpg/220px-Kingdom_Netflix.jpg"},
]

BRACKET_ANIME = [
    {"nom": "Naruto", "image": "https://upload.wikimedia.org/wikipedia/en/thumb/9/94/NarutoCoverTankobon1.jpg/220px-NarutoCoverTankobon1.jpg"},
    {"nom": "One Piece", "image": "https://upload.wikimedia.org/wikipedia/en/thumb/9/90/One_Piece%2C_Volume_61_Cover_%28Japanese%29.jpg/220px-One_Piece%2C_Volume_61_Cover_%28Japanese%29.jpg"},
    {"nom": "Attack on Titan", "image": "https://upload.wikimedia.org/wikipedia/en/thumb/d/d1/Shingeki_no_Kyojin_manga_volume_1.jpg/220px-Shingeki_no_Kyojin_manga_volume_1.jpg"},
    {"nom": "Demon Slayer", "image": "https://upload.wikimedia.org/wikipedia/en/thumb/9/9b/Kimetsu_no_Yaiba_-_Volume_1_Cover.png/220px-Kimetsu_no_Yaiba_-_Volume_1_Cover.png"},
    {"nom": "Death Note", "image": "https://upload.wikimedia.org/wikipedia/en/thumb/2/22/Death_Note_manga_volume_1.jpg/220px-Death_Note_manga_volume_1.jpg"},
    {"nom": "Jujutsu Kaisen", "image": "https://upload.wikimedia.org/wikipedia/en/thumb/7/7a/Jujutsu_Kaisen_manga_cover_volume_1.jpg/220px-Jujutsu_Kaisen_manga_cover_volume_1.jpg"},
    {"nom": "Dragon Ball Z", "image": "https://upload.wikimedia.org/wikipedia/en/thumb/f/f2/Dragon_Ball_Z_volume_1.jpg/220px-Dragon_Ball_Z_volume_1.jpg"},
    {"nom": "Fullmetal Alchemist", "image": "https://upload.wikimedia.org/wikipedia/en/thumb/0/0f/Fullmetal_Alchemist_manga_volume_1.png/220px-Fullmetal_Alchemist_manga_volume_1.png"},
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
    """Lance un match du bracket avec vote"""
    if gid not in active_brackets:
        return
    game = active_brackets[gid]
    matchs = game["matchs"]
    if match_idx >= len(matchs):
        await bracket_fin_tour(ctx, gid)
        return

    a, b = matchs[match_idx]
    channel = ctx.guild.get_channel(game["channel"])

    embed = discord.Embed(
        title=f"⚔️ DUEL — Tour {game['tour']} • Match {match_idx+1}/{len(matchs)}",
        description=(
            f"## 🅰️ {a['nom']}\nvs\n## 🅱️ {b['nom']}\n\n"
            f"**Vote 🅰️ ou 🅱️ ci-dessous !**\n⏳ Résultat dans **24h** (ou quand l'hôte tape `.bracketskip`)"
        ),
        color=0xe74c3c
    )
    embed.set_thumbnail(url=a["image"])
    embed.set_image(url=b["image"])
    embed.set_footer(text=f"🏆 Tournoi {'Kdrama' if game['theme'] == 'kdrama' else 'Animé'} — QG Kdrama")

    msg = await channel.send(embed=embed)
    await msg.add_reaction("🅰️")
    await msg.add_reaction("🅱️")

    game["votes_en_cours"][match_idx] = {
        "message_id": msg.id,
        "a": a,
        "b": b,
    }

    # Timer 24h → résoudre automatiquement
    await asyncio.sleep(86400)
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
    {"nom": "Le Titan Colossal", "anime": "Attack on Titan", "hp_max": 2000, "emoji": "👹", "image": "https://upload.wikimedia.org/wikipedia/en/thumb/8/85/Colossal_Titan_AoT.png/220px-Colossal_Titan_AoT.png", "recompense": 300},
    {"nom": "Muzan Kibutsuji", "anime": "Demon Slayer", "hp_max": 1500, "emoji": "🧛", "image": "https://upload.wikimedia.org/wikipedia/en/thumb/7/78/Muzan_Kibutsuji.png/220px-Muzan_Kibutsuji.png", "recompense": 250},
    {"nom": "Kaguya Otsutsuki", "anime": "Naruto", "hp_max": 1800, "emoji": "🌙", "image": "https://upload.wikimedia.org/wikipedia/en/thumb/4/4e/Kaguya_Otsutsuki.png/220px-Kaguya_Otsutsuki.png", "recompense": 280},
    {"nom": "Ryuk (Death Note)", "anime": "Death Note", "hp_max": 1200, "emoji": "💀", "image": "https://upload.wikimedia.org/wikipedia/en/thumb/1/13/Ryuk_Death_Note.png/220px-Ryuk_Death_Note.png", "recompense": 200},
    {"nom": "Gilgamesh", "anime": "Fate/Zero", "hp_max": 2500, "emoji": "⚔️", "image": "https://upload.wikimedia.org/wikipedia/en/thumb/4/44/Gilgamesh_Fate.png/220px-Gilgamesh_Fate.png", "recompense": 400},
]

active_boss = {}  # {guild_id: {boss, hp, participants, message_id}}

@bot.command(name="boss")
@commands.has_permissions(manage_guild=True)
async def boss_cmd(ctx):
    """Fait apparaître un boss de serveur ! (admin) — .boss"""
    gid = ctx.guild.id
    if gid in active_boss:
        return await ctx.send("⚔️ Un boss est déjà en cours ! Tape `.attaque` pour combattre !")

    boss = random.choice(BOSS_LIST)
    active_boss[gid] = {
        "boss": boss,
        "hp": boss["hp_max"],
        "participants": {},
        "channel": ctx.channel.id,
    }

    embed = discord.Embed(
        title=f"{boss['emoji']} BOSS APPARU — {boss['nom']} !",
        description=(
            f"*{boss['nom']}* de **{boss['anime']}** attaque le serveur !\n\n"
            f"❤️ HP : **{boss['hp_max']}/{boss['hp_max']}**\n"
            f"{'█' * 20} 100%\n\n"
            f"⚔️ Tape `.attaque` pour combattre !\n"
            f"🏆 Récompense finale : **{boss['recompense']} pièces** pour tous les participants !"
        ),
        color=0xe74c3c
    )
    embed.set_image(url=boss["image"])
    await ctx.send(embed=embed)

@bot.command(name="attaque")
async def attaque_cmd(ctx):
    """Attaque le boss en cours ! — .attaque"""
    gid = ctx.guild.id
    if gid not in active_boss:
        return await ctx.send("❌ Aucun boss en cours ! Attends qu'un admin lance `.boss`")

    game = active_boss[gid]
    if game["hp"] <= 0:
        return await ctx.send("💀 Le boss est déjà vaincu !")

    uid = str(ctx.author.id)
    now = datetime.datetime.utcnow().timestamp()

    # Cooldown 30sec par attaque
    last = game["participants"].get(uid, {}).get("last_attack", 0)
    if now - last < 30:
        restant = int(30 - (now - last))
        return await ctx.send(f"⏳ Tu dois attendre **{restant}s** avant d'attaquer à nouveau !", delete_after=5)

    # Calculer les dégâts selon le niveau du joueur
    niveau = xp_data[uid]["level"]
    degats = random.randint(10 + niveau * 2, 30 + niveau * 5)

    if uid not in game["participants"]:
        game["participants"][uid] = {"degats_total": 0, "last_attack": 0, "membre": ctx.author.display_name}

    game["participants"][uid]["degats_total"] += degats
    game["participants"][uid]["last_attack"] = now
    game["hp"] = max(0, game["hp"] - degats)

    boss = game["boss"]
    hp_pct = game["hp"] / boss["hp_max"]
    barres = int(hp_pct * 20)
    barre = "█" * barres + "░" * (20 - barres)

    if game["hp"] <= 0:
        # Boss vaincu !
        recompense = boss["recompense"]
        embed = discord.Embed(
            title=f"💀 {boss['nom']} est vaincu !",
            description=(
                f"⚔️ **{ctx.author.mention}** a porté le coup fatal ! **-{degats} dégâts**\n\n"
                f"🏆 Tous les participants reçoivent **{recompense} pièces** !\n\n"
                + "\n".join([f"• **{d['membre']}** — {d['degats_total']} dégâts" for d in sorted(game["participants"].values(), key=lambda x: x["degats_total"], reverse=True)])
            ),
            color=0xf1c40f
        )
        embed.set_thumbnail(url=boss["image"])
        for pid, data in game["participants"].items():
            economy_data[pid]["coins"] += recompense
            xp_data[pid]["xp"] += 50
        del active_boss[gid]
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title=f"{boss['emoji']} {boss['nom']}",
            description=(
                f"⚔️ **{ctx.author.mention}** inflige **{degats} dégâts** !\n\n"
                f"❤️ **{game['hp']}/{boss['hp_max']} HP**\n"
                f"`{barre}` {int(hp_pct*100)}%"
            ),
            color=0xe74c3c if hp_pct < 0.3 else 0xf39c12 if hp_pct < 0.6 else 0x2ecc71
        )
        await ctx.send(embed=embed, delete_after=15)

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

@bot.command(name="arene")
async def arene_cmd(ctx, adversaire: discord.Member = None):
    """⚔️ Combat PvP en arène ! — .arene @joueur"""
    if not adversaire:
        return await ctx.send("❌ Mentionne un adversaire ! Ex: `.arene @ami`")
    if adversaire.bot or adversaire.id == ctx.author.id:
        return await ctx.send("❌ Adversaire invalide !")
    if ctx.channel.id in active_arene:
        return await ctx.send("⚔️ Un combat est déjà en cours ici !")

    active_arene[ctx.channel.id] = {
        "joueur1": {"membre": ctx.author, "hp": 100},
        "joueur2": {"membre": adversaire, "hp": 100},
        "tour": ctx.author.id,
    }

    embed = discord.Embed(
        title="⚔️ ARÈNE PVP — QG Kdrama",
        description=(
            f"**{ctx.author.mention}** défie **{adversaire.mention}** !\n\n"
            f"❤️ {ctx.author.display_name} : 100 HP\n"
            f"❤️ {adversaire.display_name} : 100 HP\n\n"
            f"C'est à **{ctx.author.mention}** d'attaquer !\n"
            f"Choisis une attaque en tapant son numéro :"
        ),
        color=0xe74c3c
    )
    attaques_str = "\n".join([f"`{i+1}` {a['emoji']} **{a['nom']}** *(+{a['degats'][0]}-{a['degats'][1]} dégâts)*" if not a.get('esquive') and not a.get('soin') else f"`{i+1}` {a['emoji']} **{a['nom']}** *({'Esquive' if a.get('esquive') else 'Soin +20-30 HP'})*" for i, a in enumerate(ATTAQUES_PVP[:6])])
    embed.add_field(name="🗡️ Attaques disponibles", value=attaques_str, inline=False)
    await ctx.send(embed=embed)

    # Boucle de combat
    while ctx.channel.id in active_arene:
        game = active_arene[ctx.channel.id]
        j1 = game["joueur1"]
        j2 = game["joueur2"]
        current = j1 if game["tour"] == j1["membre"].id else j2
        other = j2 if game["tour"] == j1["membre"].id else j1

        def check(m):
            return m.channel == ctx.channel and m.author.id == current["membre"].id and m.content.isdigit() and 1 <= int(m.content) <= 6

        try:
            msg = await bot.wait_for("message", check=check, timeout=30)
            choix = int(msg.content) - 1
            attaque = ATTAQUES_PVP[choix]

            if attaque.get("esquive"):
                degats = 0
                texte = f"💨 **{current['membre'].display_name}** esquive la prochaine attaque !"
            elif attaque.get("soin"):
                soin = random.randint(20, 30)
                current["hp"] = min(100, current["hp"] + soin)
                degats = 0
                texte = f"🌸 **{current['membre'].display_name}** se soigne de **{soin} HP** !"
            else:
                degats = random.randint(*attaque["degats"])
                other["hp"] = max(0, other["hp"] - degats)
                texte = f"{attaque['emoji']} **{current['membre'].display_name}** utilise **{attaque['nom']}** → **-{degats} HP** à {other['membre'].display_name} !"

            # Vérif victoire
            if other["hp"] <= 0:
                prize = random.randint(100, 250)
                economy_data[str(current["membre"].id)]["coins"] += prize
                xp_data[str(current["membre"].id)]["xp"] += 40
                del active_arene[ctx.channel.id]
                embed = discord.Embed(
                    title="🏆 FIN DU COMBAT !",
                    description=f"{texte}\n\n🏆 **{current['membre'].mention}** remporte l'arène ! **+{prize} pièces & +40 XP** 🎉",
                    color=0xf1c40f
                )
                await ctx.send(embed=embed)
                return

            # Prochain tour
            game["tour"] = other["membre"].id
            embed = discord.Embed(
                title="⚔️ Arène PvP",
                description=(
                    f"{texte}\n\n"
                    f"❤️ {j1['membre'].display_name} : **{j1['hp']} HP**\n"
                    f"❤️ {j2['membre'].display_name} : **{j2['hp']} HP**\n\n"
                    f"C'est au tour de **{other['membre'].mention}** !\n{attaques_str}"
                ),
                color=0xe74c3c
            )
            embed.add_field(name="🗡️ Attaques", value=attaques_str, inline=False)
            await ctx.send(embed=embed)

        except asyncio.TimeoutError:
            del active_arene[ctx.channel.id]
            await ctx.send(f"⏰ **{current['membre'].mention}** n'a pas répondu — combat annulé !")
            return

# ============================================================
bot.run(TOKEN)



