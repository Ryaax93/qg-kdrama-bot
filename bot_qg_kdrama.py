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
AI_API_KEY = "METS_TA_CLE_OPENAI_ICI"  # optionnel pour l'IA
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
    {"title": "Crash Landing on You", "genre": "Romance", "note": "⭐ 9.2/10", "emoji": "🪂"},
    {"title": "Goblin", "genre": "Fantasy/Romance", "note": "⭐ 9.5/10", "emoji": "🕯️"},
    {"title": "My Love from the Star", "genre": "Romance/SF", "note": "⭐ 8.9/10", "emoji": "⭐"},
    {"title": "Descendants of the Sun", "genre": "Romance/Action", "note": "⭐ 8.8/10", "emoji": "☀️"},
    {"title": "Reply 1988", "genre": "Slice of Life", "note": "⭐ 9.7/10", "emoji": "📼"},
    {"title": "Vincenzo", "genre": "Thriller/Comédie", "note": "⭐ 9.0/10", "emoji": "🦅"},
    {"title": "Itaewon Class", "genre": "Drama/Romance", "note": "⭐ 8.7/10", "emoji": "🍺"},
    {"title": "Kingdom", "genre": "Historique/Horreur", "note": "⭐ 9.1/10", "emoji": "👑"},
    {"title": "Squid Game", "genre": "Thriller", "note": "⭐ 8.0/10", "emoji": "🦑"},
    {"title": "Signal", "genre": "Policier/Thriller", "note": "⭐ 9.3/10", "emoji": "📻"},
    {"title": "Hospital Playlist", "genre": "Médical/Slice of Life", "note": "⭐ 9.4/10", "emoji": "🩺"},
    {"title": "Weightlifting Fairy Kim Bok-joo", "genre": "Romance/Sport", "note": "⭐ 8.9/10", "emoji": "🏋️"},
]

ANIMES = [
    {"title": "Attack on Titan", "genre": "Action/Drame", "note": "⭐ 9.1/10", "emoji": "⚔️"},
    {"title": "Demon Slayer", "genre": "Action/Aventure", "note": "⭐ 8.7/10", "emoji": "🗡️"},
    {"title": "One Piece", "genre": "Aventure", "note": "⭐ 9.0/10", "emoji": "🏴‍☠️"},
    {"title": "Death Note", "genre": "Psychologique/Thriller", "note": "⭐ 9.0/10", "emoji": "📓"},
    {"title": "Fullmetal Alchemist: Brotherhood", "genre": "Action/Fantasy", "note": "⭐ 9.5/10", "emoji": "⚗️"},
    {"title": "Haikyuu!!", "genre": "Sport/Drame", "note": "⭐ 9.1/10", "emoji": "🏐"},
    {"title": "Jujutsu Kaisen", "genre": "Action/Dark Fantasy", "note": "⭐ 8.8/10", "emoji": "💥"},
    {"title": "Vinland Saga", "genre": "Historique/Action", "note": "⭐ 9.0/10", "emoji": "🪓"},
    {"title": "Your Lie in April", "genre": "Romance/Musique", "note": "⭐ 9.3/10", "emoji": "🎹"},
    {"title": "Naruto Shippuden", "genre": "Action/Aventure", "note": "⭐ 8.7/10", "emoji": "🍥"},
]

GAMES = [
    {"title": "Genshin Impact", "genre": "RPG/Gacha", "emoji": "🌸"},
    {"title": "Valorant", "genre": "FPS Tactique", "emoji": "🎯"},
    {"title": "League of Legends", "genre": "MOBA", "emoji": "⚔️"},
    {"title": "Elden Ring", "genre": "Action RPG", "emoji": "💀"},
    {"title": "Stardew Valley", "genre": "Simulation", "emoji": "🌾"},
    {"title": "Minecraft", "genre": "Sandbox", "emoji": "⛏️"},
    {"title": "Overwatch 2", "genre": "FPS", "emoji": "🦸"},
    {"title": "Hollow Knight", "genre": "Metroidvania", "emoji": "🦋"},
]

QUIZ_QG = [
    # Kdrama
    {"q": "Dans quel drama joue Lee Min-ho dans le rôle de Gu Jun-pyo ?", "a": "boys over flowers"},
    {"q": "Comment s'appelle le goblin dans le drama 'Goblin' ?", "a": "kim shin"},
    {"q": "Dans 'Crash Landing on You', dans quel pays atterrit Yoon Se-ri ?", "a": "corée du nord"},
    {"q": "Quel drama coréen a été le premier à entrer dans le top 1 mondial Netflix ?", "a": "squid game"},
    {"q": "Dans 'Reply 1988', dans quel quartier de Séoul vivent les personnages ?", "a": "ssangmun-dong"},
    # Animé
    {"q": "Quel est le vrai nom de Light Yagami dans Death Note ?", "a": "light yagami"},
    {"q": "Dans Demon Slayer, quelle est la technique signature de Tanjiro ?", "a": "respiration de l'eau"},
    {"q": "Combien de membres compte l'équipe de volleyball de Karasuno dans Haikyuu ?", "a": "12"},
    {"q": "Dans FMA Brotherhood, quel est l'équivalent sacrifié par Ed pour ramener Alphonse ?", "a": "son bras"},
    {"q": "Quel animé se passe dans le monde des Titans derrière des murs ?", "a": "attack on titan"},
    # Gaming
    {"q": "Dans Genshin Impact, quel est le nom de la région de départ ?", "a": "mondstadt"},
    {"q": "Combien de joueurs survivent à la fin d'une partie normale de Valorant ?", "a": "5"},
    {"q": "Dans Elden Ring, comment s'appelle le monde ouvert principal ?", "a": "entre-terre"},
]

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
async def on_ready():
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name="🎬 Kdrama • .help")
    )
    print(f"✅ Bot QG Kdrama connecté : {bot.user}")

@bot.event
async def on_member_join(member):
    channel = discord.utils.get(member.guild.text_channels, name="général")
    if not channel:
        channel = member.guild.system_channel
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
async def help_cmd(ctx):
    embed = discord.Embed(
        title="📖 Commandes du Bot QG Kdrama",
        description="Préfixe : `.`   |   Le bot de la communauté 🎬🎮✨",
        color=0xff6b9d
    )
    embed.add_field(name="🎬 Kdrama", value="`drama` `dramarec` `quote` `oppachallenge`", inline=False)
    embed.add_field(name="✨ Animé", value="`anime` `animerec` `animequote`", inline=False)
    embed.add_field(name="🎮 Gaming", value="`gamerec` `lfg` `dice` `rps`", inline=False)
    embed.add_field(name="🎯 Quiz QG", value="`quiz` — Questions Kdrama/Animé/Gaming", inline=False)
    embed.add_field(name="⚔️ Duels", value="`duel @user` `accept` `decline`", inline=False)
    embed.add_field(name="📊 Niveaux", value="`rank` `leaderboard`", inline=False)
    embed.add_field(name="💰 Économie", value="`daily` `balance` `pay`", inline=False)
    embed.add_field(name="🎫 Support", value="`ticket` `close`", inline=False)
    embed.add_field(name="🛡️ Modération", value="`ban` `kick` `mute` `unmute` `clear`", inline=False)
    embed.add_field(name="🤖 IA", value="`ask <question>`", inline=False)
    embed.add_field(name="🐺 Loup Garou", value="`lg` `lgcreate` `lgjoin` `lgstart` `lgvote` `lgnuit` `lgsorciere` `lgnextday` `lgstatus` `lgstop` `lgroles`", inline=False)
    embed.add_field(name="😄 Fun", value="`roast` `compliment` `8ball` `meme`", inline=False)
    embed.set_footer(text="QG Kdrama 🎬 • Bon drama et bonnes parties !")
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
    embed.set_footer(text="💡 Tape .dramarec pour une recommandation personnalisée !")
    await ctx.send(embed=embed)

@bot.command()
async def dramarec(ctx, *, genre: str = None):
    """Recommande un drama selon le genre (romance, thriller, fantasy...)"""
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
    embed.set_footer(text="Good luck pour les feels 😭")
    await ctx.send(embed=embed)

@bot.command()
async def quote(ctx):
    """Quote Kdrama inspirante"""
    embed = discord.Embed(
        title="💬 Quote Kdrama",
        description=random.choice(KDRAMA_QUOTES),
        color=0xc39bd3
    )
    await ctx.send(embed=embed)

@bot.command()
async def oppachallenge(ctx):
    """Un challenge drama fun"""
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
    embed.set_footer(text="✨ Tape .animerec pour une recommandation !")
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
#  QUIZ QG (Kdrama + Animé + Gaming)
# ============================================================
active_quiz = {}

@bot.command()
async def quiz(ctx):
    if ctx.channel.id in active_quiz:
        return await ctx.send("❓ Un quiz est déjà en cours ici !")
    q = random.choice(QUIZ_QG)
    active_quiz[ctx.channel.id] = q["a"]
    embed = discord.Embed(
        title="🎯 Quiz QG Kdrama !",
        description=f"**{q['q']}**",
        color=0xf1c40f
    )
    embed.set_footer(text="⏳ 30 secondes pour répondre !")
    await ctx.send(embed=embed)

    def check(m):
        return m.channel == ctx.channel and not m.author.bot

    try:
        msg = await bot.wait_for("message", check=check, timeout=30)
        correct = active_quiz.pop(ctx.channel.id, None)
        if msg.content.lower().strip() == correct:
            prize = random.randint(50, 150)
            economy_data[str(msg.author.id)]["coins"] += prize
            xp_data[str(msg.author.id)]["xp"] += 30
            await ctx.send(embed=discord.Embed(
                description=f"✅ **{msg.author.display_name}** a trouvé ! +{prize} pièces & +30 XP 🎉",
                color=0x2ecc71
            ))
        else:
            active_quiz.pop(ctx.channel.id, None)
            await ctx.send(embed=discord.Embed(
                description=f"❌ Perdu ! La bonne réponse était : **{correct}**",
                color=0xe74c3c
            ))
    except asyncio.TimeoutError:
        active_quiz.pop(ctx.channel.id, None)
        await ctx.send("⏰ Temps écoulé ! Personne n'a trouvé.")

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
#  IA
# ============================================================
@bot.command()
async def ask(ctx, *, question):
    try:
        import openai
        client = openai.AsyncOpenAI(api_key=AI_API_KEY)
        async with ctx.typing():
            response = await client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": (
                        "Tu es un assistant passionné de Kdramas, d'animés et de gaming. "
                        "Tu fais partie du serveur Discord 'QG Kdrama'. Tu réponds en français, "
                        "de façon sympa, précise et avec des emojis. "
                        "Si on te parle de Kdrama, d'animé ou de jeux vidéo, tu es très enthousiaste !"
                    )},
                    {"role": "user", "content": question}
                ],
                max_tokens=400
            )
        answer = response.choices[0].message.content
        embed = discord.Embed(title="🤖 IA du QG", description=answer, color=0x9b59b6)
        embed.set_footer(text=f"Question de {ctx.author.display_name}")
        await ctx.send(embed=embed)
    except ImportError:
        await ctx.send("⚠️ Installe openai : `pip install openai`")
    except Exception as e:
        await ctx.send(f"❌ Erreur IA : {e}")

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
    else:
        desc = "🌅 **Le village se réveille... Personne n'est mort cette nuit !** 🍀"

    # Révéler les rôles des morts
    for uid, p in game["players"].items():
        if not p["alive"] and p["name"] in deaths:
            desc += f"\n\n{p['name']} était : **{LG_ROLES[p['role']]['emoji']} {p['role']}**"

    alive_list = "\n".join([f"• {p['name']}" for p in game["players"].values() if p["alive"]])

    won, win_msg = lg_check_win(game)
    if won:
        await ctx.send(embed=discord.Embed(description=desc, color=0xe74c3c))
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
bot.run(TOKEN)

