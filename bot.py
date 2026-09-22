import os
import asyncio
import sqlite3
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo
import unicodedata
import re
from io import BytesIO

import discord
import aiohttp
from discord import app_commands
from discord.ext import commands, tasks
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().with_name(".env")
load_dotenv(dotenv_path=ENV_PATH, override=False)
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN or TOKEN in {"WKLEJ_TUTAJ_TOKEN", "WKLEJ_TUTAJ_NOWY_TOKEN"}:
    raise RuntimeError(f"Brak tokenu. Bot szuka pliku tutaj: {ENV_PATH}")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
DATA_DIR = Path(os.getenv("DATA_DIR", ".")).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB = str(DATA_DIR / "bcso.db")

HIERARCHY_CHANNEL_ID = 1544730702459707485

ANNOUNCEMENT_CHANNELS = {
    "ogloszenia": 1544036673535484101,
    "zarzad": 1544036673380163756,
}
ANNOUNCEMENT_ROLE_ID = 1544036672876978291
MANAGEMENT_ANNOUNCEMENT_ROLE_IDS = [1544036672893886472, 1544036672893886468]
ACTIVITY_PING_ROLE_ID = 1544036672876978291
TRAINING_ROLE_IDS = [
    1544036672839090292,
    1544036672839090291,
    1544036672839090290,
    1544036672839090289,
    1544036672839090288,
    1544036672839090287,
    1544036672839090286,
    1544036672826642541,
]
SPECIAL_TRAINING_ROLE_ID = 1544036672839090289
SPECIAL_TRAINING_REQUIRED_ROLE_ID = 1544446761878167605
AUTO_DEGRAD_TRIGGER_ROLE_ID = 1544036672818127015
AUTO_AWANS_TRIGGER_ROLE_ID = 1544036672826642535
AUTO_DEGRAD_LOG_CHANNEL_ID = 1544036673963167829
AUTO_AWANS_LOG_CHANNEL_ID = 1544036673963167828
TRAINING_LOG_CHANNEL_ID = 1544036674399506511

ACTION_CHANNELS = {
    "awans": 1544036673963167828,
    "degrad": 1544036673963167829,
    "akta": 1544036673963167827,       # plus / minus / pochwala / nagana
    "lota": 1544036673963167831,
    "blacklista": 1544036673963167832,
}
URLOP_CHANNEL_ID = 1544036673963167834
URLOP_ROLE_ID = 1544036672902271050
BLACKLIST_ROLE_ID = 1544885220115742851

RESIGNATION_ROLE_ID = 1544036672818127010
BOT_SUCCESS_LOG_CHANNEL_ID = 1544888154006364172
BLACKLIST_PUBLIC_LOG_CHANNEL_ID = 1544888193437007922

RESIGNATION_CHANNEL_ID = 1544036673963167833
ACTIVITY_TEST_CHANNEL_ID = 1544891662025629707
SUSPENSION_ROLE_ID = 1544036672902271051
SUSPENSION_LOG_CHANNEL_ID = 1544036673963167830

CHANGELOG_CHANNEL_ID = 1544898484652744724
TICKET_TRANSCRIPT_CHANNEL_ID = 1544036673380163759
HIERARCHY_OWNER_ROLE_ID = 1544037780156583936
HIERARCHY_OWNER_USERNAME = "celdex.30"

BOT_VERSION = "v27-clean"

ANNOUNCEMENT_MASTER_ROLE_ID = 1544036672893886472

FIVEM_SERVER_ID = "3ygoz78"
FIVEM_CONNECT_URL = "https://cfx.re/join/3ygoz78"
FIVEM_STATUS_CHANNEL_ID = 1544036673380163764
FIVEM_STATUS_REFRESH_MINUTES = 5
FIVEM_STATUS_MESSAGE_META_KEY = "fivem_status_message_id"

DEPARTMENT_ANNOUNCEMENTS = {
    "iad": {
        "allowed_role_ids": [1544036672868458565, 1544036672868458564],
        "channel_id": 1544466248656752750,
        "ping_role_id": 1544446675056328704,
        "label": "IAD",
        "icon": "🕵️",
    },
    "sert": {
        "allowed_role_ids": [1544036672855998642, 1544036672855998641],
        "channel_id": 1544464861894021170,
        "ping_role_id": 1544446761878167605,
        "label": "SERT",
        "icon": "🚨",
    },
    "ddu": {
        "allowed_role_ids": [1544036672868458557, 1544036672868458556],
        "channel_id": 1544453247400542208,
        "ping_role_id": 1544446784858755102,
        "label": "DDU",
        "icon": "🛡️",
    },
    "ftd": {
        "allowed_role_ids": [1544036672868458561, 1544036672868458560],
        "channel_id": 1544449066123927723,
        "ping_role_id": 1544446778630471800,
        "label": "FTD",
        "icon": "🎓",
    },
}
BOT_CHANGES = [
    "Wyczyszczono cały stary system kompendiów i automatycznego publikowania materiałów.",
    "Usunięto cały stary system odznak oraz automatyczne przypisywanie odznak.",
    "Zachowano stabilne awanse, degrady, szkolenia, logi, ogłoszenia, tickety i status FiveM.",
    "Dodano czyszczenie starych wpisów kompendium/odznak z trwałej bazy SQLite przy starcie.",
    "Ulepszono obsługę błędów slash-komend i restart bota bez tracebacku.",
]


def db():
    return sqlite3.connect(DB)


def init_db():
    con = db()
    con.execute("""
        CREATE TABLE IF NOT EXISTS actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            moderator_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            points INTEGER NOT NULL DEFAULT 0,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS blacklist (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            moderator_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (guild_id, user_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS rank_roles (
            guild_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            position INTEGER NOT NULL,
            PRIMARY KEY (guild_id, role_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS suspensions (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role_ids TEXT NOT NULL,
            moderator_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (guild_id, user_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS bot_meta (
            guild_id INTEGER NOT NULL,
            meta_key TEXT NOT NULL,
            meta_value TEXT NOT NULL,
            PRIMARY KEY (guild_id, meta_key)
        )
    """)
    # v27-clean: jednorazowe czyszczenie starych danych po usunięciu
    # systemu kompendiów i odznak. Nie usuwa historii akcji ani ticketów.
    try:
        con.execute("DROP TABLE IF EXISTS badge_assignments")
        con.execute("DROP TABLE IF EXISTS badges")
        con.execute("DROP TABLE IF EXISTS training_compendium")
        con.execute("""
            DELETE FROM bot_meta
            WHERE lower(meta_key) LIKE '%badge%'
               OR lower(meta_key) LIKE '%odznak%'
               OR lower(meta_key) LIKE '%kompend%'
               OR lower(meta_key) LIKE '%training_guide%'
               OR lower(meta_key) LIKE '%training_resource%'
        """)
    except Exception as e:
        print(f"[DB CLEANUP] {type(e).__name__}: {e}")

    con.execute("""
        CREATE TABLE IF NOT EXISTS ticket_channels (
            guild_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            channel_name TEXT NOT NULL,
            opened_at TEXT NOT NULL,
            transcript_sent INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, channel_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS ticket_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            author_id INTEGER NOT NULL,
            author_name TEXT NOT NULL,
            content TEXT NOT NULL,
            attachments TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    con.commit()
    con.close()


def is_staff(interaction: discord.Interaction) -> bool:
    p = interaction.user.guild_permissions
    return p.administrator or p.manage_roles


async def require_staff(interaction: discord.Interaction) -> bool:
    if not is_staff(interaction):
        await interaction.response.send_message(
            "Nie masz uprawnien do tej komendy.", ephemeral=True
        )
        return False
    return True


def add_action(guild_id, user_id, moderator_id, action, points, reason):
    con = db()
    con.execute(
        "INSERT INTO actions(guild_id,user_id,moderator_id,action,points,reason,created_at) VALUES(?,?,?,?,?,?,?)",
        (guild_id, user_id, moderator_id, action, points, reason,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    con.commit()
    con.close()


def normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower()
    value = re.sub(r"[^a-z0-9/]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def find_role_contains(guild: discord.Guild, phrase: str):
    wanted = normalize_name(phrase)
    for role in guild.roles:
        if wanted in normalize_name(role.name):
            return role
    return None


async def set_progress_role(member: discord.Member, base_name: str, count: int, maximum: int):
    """Remove old progress roles for a category and add the correct one."""
    guild = member.guild
    prefix = normalize_name(base_name)
    to_remove = []
    for role in member.roles:
        n = normalize_name(role.name)
        if prefix in n and any(f"{i}/{maximum}" in n for i in range(1, maximum + 1)):
            to_remove.append(role)

    if to_remove:
        try:
            await member.remove_roles(*to_remove, reason=f"Aktualizacja licznika {base_name}")
        except discord.Forbidden:
            return False, "Bot nie moze usunac starej roli. Ustaw role bota wyzej."

    target_num = min(max(count, 1), maximum)
    target = find_role_contains(guild, f"{base_name} {target_num}/{maximum}")
    if target is None:
        return False, f"Nie znaleziono roli `{base_name} {target_num}/{maximum}`."

    try:
        await member.add_roles(target, reason=f"Aktualizacja licznika {base_name}")
    except discord.Forbidden:
        return False, "Bot nie moze nadac tej roli. Ustaw role bota wyzej."

    return True, target.name


def count_actions(guild_id: int, user_id: int, action_name: str) -> int:
    con = db()
    value = con.execute(
        "SELECT COUNT(*) FROM actions WHERE guild_id=? AND user_id=? AND lower(action)=lower(?)",
        (guild_id, user_id, action_name)
    ).fetchone()[0]
    con.close()
    return value


def make_embed(title: str, description: str = "", *, footer: str | None = None):
    embed = discord.Embed(
        title=title,
        description=description,
        timestamp=datetime.now()
    )
    if footer:
        embed.set_footer(text=footer)
    return embed


def member_rank_from_ladder(member: discord.Member):
    ladder = detected_rank_ladder(member.guild)
    for role in reversed(ladder):
        if role in member.roles:
            return role
    return None


async def send_staff_log(interaction: discord.Interaction, title: str, member: discord.Member, reason: str, extra: str | None = None):
    embed = make_embed(
        title,
        f"👤 **Osoba:** {member.mention}\n"
        f"🛡️ **Wykonał:** {interaction.user.mention}\n"
        f"📝 **Powód:** {reason}"
    )
    if extra:
        embed.add_field(name="Szczegóły", value=extra, inline=False)
    embed.set_thumbnail(url=member.display_avatar.url)
    return embed


async def get_text_channel(guild: discord.Guild, channel_id: int):
    channel = guild.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except Exception:
            return None
    return channel if isinstance(channel, discord.TextChannel) else None


def action_embed(title: str, member: discord.Member, moderator: discord.Member, reason: str, *,
                 detail_name: str | None = None, detail_value: str | None = None):
    embed = polished_embed(
        title,
        "Blaine County Sheriff's Office • System kadrowy"
    )
    embed.add_field(name="👤 Funkcjonariusz", value=member.mention, inline=True)
    embed.add_field(name="🛡️ Wykonał", value=moderator.mention, inline=True)
    embed.add_field(name="📝 Powód", value=f"```{reason}```", inline=False)
    if detail_name and detail_value:
        embed.add_field(name=detail_name, value=detail_value, inline=False)
    embed.set_thumbnail(url=member.display_avatar.url)
    return embed


def notice_embed(title: str, description: str, *, footer: str = "BCSO • DzielnicaRP"):
    embed = discord.Embed(
        title=title,
        description=f"> {description.replace(chr(10), chr(10) + '> ')}",
        timestamp=datetime.now()
    )
    embed.set_footer(text=footer)
    return embed


def polished_embed(title: str, subtitle: str = "", *, footer: str = "BCSO • DzielnicaRP"):
    description = subtitle if subtitle else "System administracyjny BCSO"
    embed = discord.Embed(
        title=title,
        description=f"**{description}**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        timestamp=datetime.now()
    )
    embed.set_footer(text=footer)
    return embed


def member_has_any_role(member: discord.Member, role_ids: list[int]) -> bool:
    ids = {role.id for role in member.roles}
    return ANNOUNCEMENT_MASTER_ROLE_ID in ids or any(role_id in ids for role_id in role_ids)


def has_role_id(member: discord.Member, role_id: int) -> bool:
    return any(role.id == role_id for role in member.roles)


def large_announcement_text(text: str) -> str:
    """Discord nie ma dowolnego rozmiaru fontu; nagłówki Markdown dają największą czytelność."""
    parts = []
    for raw in text.splitlines():
        line = raw.strip()
        if line:
            parts.append(f"## {line}")
        else:
            parts.append("")
    return "\n".join(parts)[:3900]


def resolve_training_role(guild: discord.Guild, value: str):
    try:
        role_id = int(value)
    except (TypeError, ValueError):
        return None
    if role_id not in TRAINING_ROLE_IDS:
        return None
    return guild.get_role(role_id)


async def training_role_autocomplete(interaction: discord.Interaction, current: str):
    """Pokazuj WYŁĄCZNIE 8 ról z TRAINING_ROLE_IDS."""
    if interaction.guild is None:
        return []

    current_n = normalize_name(current)
    choices = []

    for role_id in TRAINING_ROLE_IDS:
        role = interaction.guild.get_role(role_id)
        if role is None:
            continue

        if not current_n or current_n in normalize_name(role.name) or current_n in str(role_id):
            choices.append(
                app_commands.Choice(
                    name=role.name[:100],
                    value=str(role.id)
                )
            )

    return choices[:8]




async def send_department_announcement(
    interaction: discord.Interaction,
    department_key: str,
    tresc: str,
    tytul: str | None = None
):
    cfg = DEPARTMENT_ANNOUNCEMENTS[department_key]

    if interaction.guild is None or not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message(
            embed=notice_embed("❌・BŁĄD", "Tej komendy można użyć tylko na serwerze."),
            ephemeral=True
        )
        return

    if not member_has_any_role(interaction.user, cfg["allowed_role_ids"]):
        allowed_mentions = " ".join(f"<@&{rid}>" for rid in cfg["allowed_role_ids"])
        await interaction.response.send_message(
            embed=notice_embed(
                "⛔・BRAK DOSTĘPU",
                f"Komenda jest dostępna wyłącznie dla uprawnionych ról.\n\n"
                f"**Role wydziału:** {allowed_mentions}\n"
                f"**Dostęp globalny:** <@&{ANNOUNCEMENT_MASTER_ROLE_ID}>"
            ),
            ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True, thinking=True)

    channel = await get_text_channel(interaction.guild, cfg["channel_id"])
    ping_role = interaction.guild.get_role(cfg["ping_role_id"])

    if channel is None:
        await interaction.followup.send(
            embed=notice_embed(
                "❌・BRAK KANAŁU",
                f"Bot nie widzi kanału docelowego <#{cfg['channel_id']}>."
            ),
            ephemeral=True
        )
        return

    if ping_role is None:
        await interaction.followup.send(
            embed=notice_embed(
                "❌・BRAK ROLI",
                f"Bot nie widzi roli do pingowania `<@&{cfg['ping_role_id']}>`."
            ),
            ephemeral=True
        )
        return

    title = (tytul or f"OGŁOSZENIE {cfg['label']}").strip()

    embed = discord.Embed(
        title=f"{cfg['icon']}・{title}",
        description=(
            f"### {cfg['label']} • OFICJALNY KOMUNIKAT\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{large_announcement_text(tresc)}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
        timestamp=datetime.now()
    )

    if interaction.guild.icon:
        embed.set_author(
            name=interaction.guild.name,
            icon_url=interaction.guild.icon.url
        )
        embed.set_thumbnail(url=interaction.guild.icon.url)
    else:
        embed.set_author(name=interaction.guild.name)

    embed.add_field(
        name="📣 Powiadomienie",
        value=ping_role.mention,
        inline=True
    )
    embed.add_field(
        name="👤 Autor",
        value=interaction.user.mention,
        inline=True
    )
    embed.set_footer(text=f"BCSO • {cfg['label']} • DzielnicaRP")

    try:
        await channel.send(
            content=ping_role.mention,
            embed=embed,
            allowed_mentions=discord.AllowedMentions(
                roles=True,
                users=False,
                everyone=False
            )
        )
    except discord.Forbidden:
        await interaction.followup.send(
            embed=notice_embed(
                "❌・BRAK UPRAWNIEŃ",
                "Bot nie może wysłać wiadomości, embeda albo pingować roli na tym kanale."
            ),
            ephemeral=True
        )
        return
    except discord.HTTPException as e:
        await interaction.followup.send(
            embed=notice_embed(
                "❌・BŁĄD DISCORDA",
                f"Discord odrzucił wiadomość: `{getattr(e, 'status', '?')}`."
            ),
            ephemeral=True
        )
        return

    await interaction.followup.send(
        embed=notice_embed(
            "✅・OGŁOSZENIE WYSŁANE",
            f"Ogłoszenie **{cfg['label']}** trafiło na {channel.mention} i pingnięto {ping_role.mention}."
        ),
        ephemeral=True
    )


async def send_action_log(interaction: discord.Interaction, channel_key: str, embed: discord.Embed):
    channel_id = ACTION_CHANNELS[channel_key]
    channel = await get_text_channel(interaction.guild, channel_id)
    if channel is None:
        return False, f"Bot nie widzi kanału logów `{channel_id}`."
    try:
        await channel.send(embed=embed)
        return True, channel.mention
    except discord.Forbidden:
        return False, f"Bot nie ma uprawnień do wysyłania na <#{channel_id}>."


async def send_success_log(interaction: discord.Interaction, command_name: str):
    if interaction.guild is None:
        return

    # /blacklista ma własny pełny publiczny embed, więc nie dublujemy go.
    if command_name == "blacklista":
        return

    channel = await get_text_channel(interaction.guild, BOT_SUCCESS_LOG_CHANNEL_ID)
    if channel is None:
        print(f"[SUCCESS LOG] Brak kanału {BOT_SUCCESS_LOG_CHANNEL_ID} dla /{command_name}")
        return

    embed = polished_embed(
        "✅・POMYŚLNIE WYKONANO KOMENDĘ",
        f"`/{command_name}` zakończyła się powodzeniem"
    )
    embed.add_field(name="👤 Użytkownik", value=interaction.user.mention, inline=True)
    embed.add_field(
        name="📍 Kanał",
        value=interaction.channel.mention if interaction.channel else "Nieznany",
        inline=True
    )
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.set_footer(text=f"BCSO • User ID: {interaction.user.id}")

    try:
        await channel.send(embed=embed)
    except Exception as e:
        print(f"[SUCCESS LOG ERROR] /{command_name}: {type(e).__name__}: {e}")



def is_ticket_channel(channel: discord.TextChannel) -> bool:
    """Rozpoznaje typowe kanały Ticket Tool / ticketowe."""
    name = normalize_name(channel.name)
    topic = normalize_name(channel.topic or "")
    category = normalize_name(channel.category.name if channel.category else "")

    keywords = ("ticket", "tickety", "support", "pomoc", "closed", "zamkniety", "zamkniete")
    return (
        any(k in name for k in keywords)
        or any(k in topic for k in keywords)
        or any(k in category for k in keywords)
    )


def track_ticket_channel(channel: discord.TextChannel):
    con = db()
    con.execute(
        "INSERT OR IGNORE INTO ticket_channels(guild_id, channel_id, channel_name, opened_at, transcript_sent) "
        "VALUES(?,?,?,?,0)",
        (
            channel.guild.id,
            channel.id,
            channel.name,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
    )
    con.commit()
    con.close()


def ticket_is_tracked(guild_id: int, channel_id: int) -> bool:
    con = db()
    row = con.execute(
        "SELECT 1 FROM ticket_channels WHERE guild_id=? AND channel_id=?",
        (guild_id, channel_id)
    ).fetchone()
    con.close()
    return bool(row)


def ticket_transcript_already_sent(guild_id: int, channel_id: int) -> bool:
    con = db()
    row = con.execute(
        "SELECT transcript_sent FROM ticket_channels WHERE guild_id=? AND channel_id=?",
        (guild_id, channel_id)
    ).fetchone()
    con.close()
    return bool(row and row[0])


def save_ticket_message(message: discord.Message):
    if message.guild is None or not isinstance(message.channel, discord.TextChannel):
        return

    attachments = "\n".join(a.url for a in message.attachments)
    content = message.content or ""
    if message.embeds and not content:
        content = "[Wiadomość embed]"
    if message.stickers:
        content += ("\n" if content else "") + "[Naklejki: " + ", ".join(s.name for s in message.stickers) + "]"

    con = db()
    con.execute(
        "INSERT INTO ticket_messages(guild_id,channel_id,message_id,author_id,author_name,content,attachments,created_at) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (
            message.guild.id,
            message.channel.id,
            message.id,
            message.author.id,
            str(message.author),
            content,
            attachments,
            message.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        )
    )
    con.commit()
    con.close()


def _register_pdf_font():
    """Spróbuj użyć Arial na Windows, żeby polskie znaki działały w PDF."""
    font_name = "Helvetica"
    candidates = [
        r"C:\\Windows\\Fonts\\arial.ttf",
        r"C:\\Windows\\Fonts\\segoeui.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                pdfmetrics.registerFont(TTFont("BotUnicode", path))
                return "BotUnicode"
            except Exception:
                pass
    return font_name


def build_ticket_pdf(guild_name: str, channel_name: str, opened_at: str, rows) -> BytesIO:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    font_name = _register_pdf_font()

    margin = 42
    y = height - 48

    def new_page():
        nonlocal y
        c.showPage()
        y = height - 48
        c.setFont(font_name, 9)

    def draw_wrapped(text_value: str, x: float, max_width: float, size: int = 9, leading: int = 12):
        nonlocal y
        c.setFont(font_name, size)
        words = (text_value or "").replace("\r", "").split()
        if not words:
            if y < 55:
                new_page()
            y -= leading
            return

        line = ""
        for word in words:
            trial = (line + " " + word).strip()
            if c.stringWidth(trial, font_name, size) <= max_width:
                line = trial
            else:
                if y < 55:
                    new_page()
                c.drawString(x, y, line)
                y -= leading
                line = word
        if line:
            if y < 55:
                new_page()
            c.drawString(x, y, line)
            y -= leading

    c.setTitle(f"Transcript - {channel_name}")
    c.setFont(font_name, 16)
    c.drawString(margin, y, "BCSO - TRANSKRYPT TICKETA")
    y -= 24
    c.setFont(font_name, 9)
    c.drawString(margin, y, f"Serwer: {guild_name}")
    y -= 13
    c.drawString(margin, y, f"Kanal: #{channel_name}")
    y -= 13
    c.drawString(margin, y, f"Otwarto: {opened_at}")
    y -= 20
    c.line(margin, y, width - margin, y)
    y -= 18

    for author_name, content, attachments, created_at in rows:
        if y < 80:
            new_page()

        c.setFont(font_name, 9)
        c.drawString(margin, y, f"[{created_at}] {author_name}")
        y -= 13

        draw_wrapped(content or "[brak treści]", margin + 12, width - margin * 2 - 12, 9, 12)

        if attachments:
            draw_wrapped("Załączniki: " + attachments.replace("\n", " | "), margin + 12, width - margin * 2 - 12, 8, 11)

        y -= 7
        c.line(margin, y, width - margin, y)
        y -= 12

    c.save()
    buf.seek(0)
    return buf


async def send_ticket_transcript(guild: discord.Guild, channel_id: int, fallback_name: str):
    if ticket_transcript_already_sent(guild.id, channel_id):
        return

    con = db()
    ticket_row = con.execute(
        "SELECT channel_name, opened_at FROM ticket_channels WHERE guild_id=? AND channel_id=?",
        (guild.id, channel_id)
    ).fetchone()
    rows = con.execute(
        "SELECT author_name, content, attachments, created_at FROM ticket_messages "
        "WHERE guild_id=? AND channel_id=? ORDER BY id ASC",
        (guild.id, channel_id)
    ).fetchall()
    con.close()

    if not ticket_row:
        return

    channel_name, opened_at = ticket_row
    channel_name = channel_name or fallback_name

    target = await get_text_channel(guild, TICKET_TRANSCRIPT_CHANNEL_ID)
    if target is None:
        print(f"[TICKET PDF] Brak kanału {TICKET_TRANSCRIPT_CHANNEL_ID}")
        return

    pdf = build_ticket_pdf(guild.name, channel_name, opened_at, rows)

    embed = polished_embed(
        "🎫・TRANSKRYPT TICKETA",
        f"Zarchiwizowano rozmowę z kanału `#{channel_name}`"
    )
    embed.add_field(name="💬 Wiadomości", value=str(len(rows)), inline=True)
    embed.add_field(name="🕒 Otwarto", value=opened_at, inline=True)
    embed.set_footer(text="BCSO • Archiwum ticketów")

    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", channel_name)[:80]
    await target.send(
        embed=embed,
        file=discord.File(pdf, filename=f"ticket_{safe_name}_{channel_id}.pdf")
    )

    con = db()
    con.execute(
        "UPDATE ticket_channels SET transcript_sent=1 WHERE guild_id=? AND channel_id=?",
        (guild.id, channel_id)
    )
    con.commit()
    con.close()


async def announce_bot_update(guild: discord.Guild):
    """Wyślij informację o nowej wersji tylko raz na serwer."""
    con = db()
    row = con.execute(
        "SELECT meta_value FROM bot_meta WHERE guild_id=? AND meta_key='announced_version'",
        (guild.id,)
    ).fetchone()
    con.close()

    if row and row[0] == BOT_VERSION:
        return

    channel = await get_text_channel(guild, CHANGELOG_CHANNEL_ID)
    if channel is None:
        print(f"[CHANGELOG] Brak kanału {CHANGELOG_CHANNEL_ID}")
        return

    embed = polished_embed(
        f"🛠️・AKTUALIZACJA BOTA {BOT_VERSION}",
        "Wprowadzono nowe zmiany w systemie BCSO"
    )
    embed.add_field(
        name="✨ Co zmieniono?",
        value="\n".join(f"• {item}" for item in BOT_CHANGES),
        inline=False
    )
    embed.set_footer(text="BCSO • Bot został zaktualizowany")

    await channel.send(embed=embed)

    con = db()
    con.execute(
        "INSERT OR REPLACE INTO bot_meta(guild_id,meta_key,meta_value) VALUES(?,?,?)",
        (guild.id, "announced_version", BOT_VERSION)
    )
    con.commit()
    con.close()



async def fetch_fivem_status():
    """
    Pobiera status FiveM dla cfx.re/join/3ygoz78.

    Kolejność:
    1. nowe API Cfx,
    2. starsze API FiveM,
    3. rozwiązanie cfx.re/join/... przez X-Citizenfx-Url,
    4. bezpośrednio dynamic.json + players.json.
    """
    timeout = aiohttp.ClientTimeout(total=15)
    headers = {
        "Accept": "application/json,text/plain,*/*",
        "User-Agent": "Mozilla/5.0 (compatible; BCSO-DzielnicaRP-Bot/1.0)"
    }

    def normalize_api_payload(payload):
        data = payload.get("Data") or payload.get("data") or payload
        if not isinstance(data, dict):
            return None

        players_list = data.get("players") or data.get("Players") or []
        players_count = len(players_list) if isinstance(players_list, list) else None

        clients = data.get("clients")
        if isinstance(clients, int):
            players_count = clients
        elif isinstance(clients, str) and clients.isdigit():
            players_count = int(clients)

        max_players = (
            data.get("svMaxclients")
            or data.get("sv_maxclients")
            or data.get("maxClients")
            or data.get("MaxClients")
        )
        try:
            if max_players is not None:
                max_players = int(max_players)
        except Exception:
            pass

        vars_data = data.get("vars") or {}
        hostname = (
            data.get("hostname")
            or data.get("Hostname")
            or vars_data.get("sv_projectName")
            or vars_data.get("sv_hostname")
        )

        endpoints = (
            data.get("connectEndPoints")
            or data.get("connectEndpoints")
            or data.get("endpoints")
            or []
        )

        return {
            "online": True,
            "players": players_count,
            "max_players": max_players,
            "hostname": hostname,
            "endpoint": endpoints[0] if isinstance(endpoints, list) and endpoints else None,
            "source": "Cfx API",
            "error": None
        }

    api_urls = [
        f"https://frontend.cfx-services.net/api/servers/single/{FIVEM_SERVER_ID}",
        f"https://servers-frontend.fivem.net/api/servers/single/{FIVEM_SERVER_ID}",
    ]

    errors = []

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # 1/2: public Cfx server-list APIs
            for url in api_urls:
                try:
                    async with session.get(url, headers=headers) as response:
                        if response.status == 200:
                            payload = await response.json(content_type=None)
                            parsed = normalize_api_payload(payload)
                            if parsed:
                                return parsed
                        errors.append(f"{url.split('/')[2]} HTTP {response.status}")
                except Exception as e:
                    errors.append(f"{url.split('/')[2]} {type(e).__name__}")

            # 3: resolve the cfx.re join code to the actual CitizenFX endpoint.
            resolved_base = None
            try:
                async with session.get(
                    FIVEM_CONNECT_URL,
                    headers=headers,
                    allow_redirects=False
                ) as response:
                    resolved_base = (
                        response.headers.get("X-Citizenfx-Url")
                        or response.headers.get("x-citizenfx-url")
                    )

                    # Some setups return a normal redirect instead.
                    if not resolved_base and response.status in (301, 302, 303, 307, 308):
                        location = response.headers.get("Location")
                        if location and (location.startswith("http://") or location.startswith("https://")):
                            resolved_base = location

                    if not resolved_base:
                        errors.append(f"cfx.re resolve HTTP {response.status}")
            except Exception as e:
                errors.append(f"cfx.re resolve {type(e).__name__}")

            if resolved_base:
                resolved_base = resolved_base.strip().rstrip("/")

                # Header usually points at the server base URL.
                if not resolved_base.startswith(("http://", "https://")):
                    resolved_base = "http://" + resolved_base

                dynamic_url = resolved_base + "/dynamic.json"
                players_url = resolved_base + "/players.json"
                info_url = resolved_base + "/info.json"

                dynamic = None
                player_list = None
                info = None

                try:
                    async with session.get(dynamic_url, headers=headers) as response:
                        if response.status == 200:
                            dynamic = await response.json(content_type=None)
                        else:
                            errors.append(f"dynamic.json HTTP {response.status}")
                except Exception as e:
                    errors.append(f"dynamic.json {type(e).__name__}")

                try:
                    async with session.get(players_url, headers=headers) as response:
                        if response.status == 200:
                            player_list = await response.json(content_type=None)
                        else:
                            errors.append(f"players.json HTTP {response.status}")
                except Exception as e:
                    errors.append(f"players.json {type(e).__name__}")

                try:
                    async with session.get(info_url, headers=headers) as response:
                        if response.status == 200:
                            info = await response.json(content_type=None)
                except Exception:
                    info = None

                if isinstance(dynamic, dict) or isinstance(player_list, list):
                    players_count = None
                    max_players = None
                    hostname = None

                    if isinstance(dynamic, dict):
                        clients = dynamic.get("clients")
                        if isinstance(clients, int):
                            players_count = clients
                        elif isinstance(clients, str) and clients.isdigit():
                            players_count = int(clients)

                        max_players = (
                            dynamic.get("sv_maxclients")
                            or dynamic.get("svMaxclients")
                            or dynamic.get("maxclients")
                        )
                        try:
                            if max_players is not None:
                                max_players = int(max_players)
                        except Exception:
                            pass

                        hostname = dynamic.get("hostname")

                    if isinstance(player_list, list):
                        players_count = len(player_list)

                    if isinstance(info, dict):
                        vars_data = info.get("vars") or {}
                        hostname = (
                            hostname
                            or vars_data.get("sv_projectName")
                            or vars_data.get("sv_hostname")
                        )

                    return {
                        "online": True,
                        "players": players_count,
                        "max_players": max_players,
                        "hostname": hostname,
                        "endpoint": resolved_base,
                        "source": "Direct FiveM",
                        "error": None
                    }

    except Exception as e:
        errors.append(f"Session {type(e).__name__}")

    return {
        "online": False,
        "players": None,
        "max_players": None,
        "hostname": None,
        "endpoint": None,
        "source": None,
        "error": " | ".join(errors[-3:]) if errors else "Brak odpowiedzi"
    }


def build_status_panel(guild: discord.Guild, fivem: dict) -> discord.Embed:
    bot_latency = round(bot.latency * 1000)
    bot_ok = bot.is_ready() and not bot.is_closed()

    embed = discord.Embed(
        title="📡・STATUS DzielnicaRP",
        description=(
            "## CENTRUM STATUSU\n"
            "> Automatycznie odświeżany panel BCSO i FiveM.\n"
            f"> Aktualizacja co **{FIVEM_STATUS_REFRESH_MINUTES} minut**."
        ),
        timestamp=datetime.now()
    )

    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    bot_status = (
        "🟢 **ONLINE**\n"
        f"> Ping: `{bot_latency} ms`\n"
        f"> Wersja: `{BOT_VERSION}`"
        if bot_ok
        else "🔴 **OFFLINE / PROBLEM**"
    )
    embed.add_field(
        name="🤖 BOT BCSO",
        value=bot_status,
        inline=False
    )

    if fivem.get("online"):
        players = fivem.get("players")
        max_players = fivem.get("max_players")
        player_text = str(players) if players is not None else "?"
        if max_players:
            player_text += f"/{max_players}"

        server_name = str(fivem.get("hostname") or "DzielnicaRP")[:100]
        fivem_value = (
            "🟢 **ONLINE**\n"
            f"> Serwer: **{server_name}**\n"
            f"> Gracze: **{player_text}**\n"
            f"> Connect: `{FIVEM_CONNECT_URL}`\n"
            f"> Źródło: `{fivem.get('source') or 'FiveM'}`"
        )
    else:
        fivem_value = (
            "🔴 **OFFLINE / BRAK DANYCH**\n"
            f"> Connect: `{FIVEM_CONNECT_URL}`\n"
            f"> Szczegóły: `{str(fivem.get('error') or 'brak odpowiedzi')[:180]}`"
        )

    embed.add_field(
        name="🎮 SERWER FIVEM",
        value=fivem_value,
        inline=False
    )

    embed.add_field(
        name="🕒 Ostatnia aktualizacja",
        value=discord.utils.format_dt(datetime.now().astimezone(), style="R"),
        inline=False
    )

    embed.set_footer(text="BCSO • DzielnicaRP • Automatyczne odświeżanie co 5 minut")
    return embed


async def update_fivem_status_panel():
    fivem = await fetch_fivem_status()

    for guild in bot.guilds:
        channel = await get_text_channel(guild, FIVEM_STATUS_CHANNEL_ID)
        if channel is None:
            print(f"[STATUS PANEL] Brak kanału {FIVEM_STATUS_CHANNEL_ID}")
            continue

        embed = build_status_panel(guild, fivem)

        con = db()
        row = con.execute(
            "SELECT meta_value FROM bot_meta WHERE guild_id=? AND meta_key=?",
            (guild.id, FIVEM_STATUS_MESSAGE_META_KEY)
        ).fetchone()
        con.close()

        message = None
        if row:
            try:
                message = await channel.fetch_message(int(row[0]))
            except Exception:
                message = None

        try:
            if message is None:
                message = await channel.send(embed=embed)

                con = db()
                con.execute(
                    "INSERT OR REPLACE INTO bot_meta(guild_id, meta_key, meta_value) VALUES(?,?,?)",
                    (guild.id, FIVEM_STATUS_MESSAGE_META_KEY, str(message.id))
                )
                con.commit()
                con.close()
            else:
                await message.edit(embed=embed)

        except Exception as e:
            print(f"[STATUS PANEL SEND ERROR] {type(e).__name__}: {e}")


@tasks.loop(minutes=FIVEM_STATUS_REFRESH_MINUTES)
async def fivem_status_task():
    await update_fivem_status_panel()


@fivem_status_task.before_loop
async def before_fivem_status_task():
    await bot.wait_until_ready()


# Jasna kolejnosc stopni widocznych na serwerze.
AUTO_RANKS = [
    "Cadet",
    "Probie Deputy",
    "Deputy",
    "Senior Deputy",
    "Corporal I",
    "Corporal II",
    "Sergeant",
    "Sergeant II",
    "Lieutenant",
    "Staff Lieutenant",
    "Captain",
    "Division Chief",
    "Asystent HC",
    "Assistant Sheriff",
    "UnderSheriff",
    "Sheriff",
]


def find_rank_role(guild: discord.Guild, rank_name: str):
    """Dopasuj dekorowaną rolę stopnia, ale nie role typu 'Sheriff Emergency Response Team'."""
    wanted = normalize_name(rank_name)
    candidates = []

    for role in guild.roles:
        n = normalize_name(role.name)

        # Rola może mieć emoji / separatory przed nazwą, np. "» | 👑 · Sheriff".
        # Szukamy końcówki nazwy, dzięki czemu:
        # - "Sheriff Emergency Response Team" NIE pasuje do Sheriff,
        # - "Deputy Commander of PD" NIE pasuje do Deputy.
        if n == wanted or n.endswith(" " + wanted) or n.endswith(wanted):
            extra = max(0, len(n) - len(wanted))
            candidates.append((extra, -role.position, role))

    if not candidates:
        return None

    # Najmniej dodatkowego tekstu = najdokładniejsze dopasowanie.
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][2]


def detected_rank_ladder(guild: discord.Guild):
    result = []
    for rank_name in AUTO_RANKS:
        role = find_rank_role(guild, rank_name)
        if role and role not in result:
            result.append(role)
    return result


async def send_training_action_log(
    interaction: discord.Interaction,
    member: discord.Member,
    training_role: discord.Role,
    action: str,
    reason: str
):
    """Dedykowany log /szkolenie nadaj i /szkolenie odbierz."""
    channel = await get_text_channel(interaction.guild, TRAINING_LOG_CHANNEL_ID)
    if channel is None:
        return False, f"Nie znaleziono kanału <#{TRAINING_LOG_CHANNEL_ID}>."

    is_add = action == "nadaj"
    embed = discord.Embed(
        title="🎓✅・NADANO SZKOLENIE" if is_add else "🎓🗑️・ODEBRANO SZKOLENIE",
        description=(
            f"## {member.mention}\n"
            f"> {'Otrzymał(a)' if is_add else 'Utracił(a)'} rolę szkoleniową {training_role.mention}."
        ),
        timestamp=datetime.now()
    )
    embed.add_field(name="🎓 Szkolenie", value=training_role.mention, inline=False)
    embed.add_field(name="👤 Funkcjonariusz", value=member.mention, inline=True)
    embed.add_field(name="🛡️ Wykonał", value=interaction.user.mention, inline=True)
    embed.add_field(name="📝 Powód", value=f"```{reason}```", inline=False)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text="BCSO • Rejestr szkoleń")

    try:
        await channel.send(embed=embed)
        return True, channel.mention
    except discord.Forbidden:
        return False, "Bot nie ma uprawnień do wysłania logu szkolenia."
    except discord.HTTPException as e:
        return False, f"Discord odrzucił log szkolenia: {getattr(e, 'status', '?')}."


async def action_reply(interaction, member, action, reason, points=0):
    add_action(interaction.guild_id, member.id, interaction.user.id, action, points, reason)
    embed = await send_staff_log(
        interaction,
        f"📋 {action}",
        member,
        reason,
        f"Punkty: **{points:+d}**" if points else None
    )
    await interaction.response.send_message(embed=embed)


@bot.event
async def on_ready():
    init_db()

    # Komendy mają istnieć TYLKO jako komendy serwerowe.
    # Dzięki temu Discord nie pokazuje dwóch identycznych wersji:
    # jednej globalnej i jednej serwerowej.
    for guild in bot.guilds:
        try:
            bot.tree.clear_commands(guild=guild)
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            print(f"Synchronizacja serwera: {guild.name} ({guild.id}) | Komendy: {len(synced)}")
        except Exception as e:
            print(f"Błąd synchronizacji serwera {guild.id}: {e}")

    # Usuń stare GLOBALNE komendy z Discorda.
    # Lokalne definicje zostały już skopiowane wyżej do serwera.
    try:
        bot.tree.clear_commands(guild=None)
        removed = await bot.tree.sync()
        print(f"Wyczyszczono globalne komendy. Pozostało globalnie: {len(removed)}")
    except Exception as e:
        print(f"Błąd czyszczenia globalnych komend: {e}")

    if not activity_test_task.is_running():
        activity_test_task.start()

    if not fivem_status_task.is_running():
        fivem_status_task.start()

    for guild in bot.guilds:
        # Zapamiętaj już istniejące kanały ticketowe.
        for channel in guild.text_channels:
            if is_ticket_channel(channel):
                track_ticket_channel(channel)
        try:
            await announce_bot_update(guild)
        except Exception as e:
            print(f"[CHANGELOG ERROR] {type(e).__name__}: {e}")

    # Krótki self-check konfiguracji po starcie.
    for guild in bot.guilds:
        configured_channels = {
            "hierarchia": HIERARCHY_CHANNEL_ID,
            "aktywność": ACTIVITY_TEST_CHANNEL_ID,
            "status FiveM": FIVEM_STATUS_CHANNEL_ID,
            "log szkoleń": TRAINING_LOG_CHANNEL_ID,
            "awans": AUTO_AWANS_LOG_CHANNEL_ID,
            "degrad": AUTO_DEGRAD_LOG_CHANNEL_ID,
        }
        missing = [
            f"{name}={channel_id}"
            for name, channel_id in configured_channels.items()
            if guild.get_channel(channel_id) is None
        ]
        if missing:
            print(f"[SELF-CHECK] {guild.name}: brak kanałów -> " + ", ".join(missing))
        else:
            print(f"[SELF-CHECK] {guild.name}: podstawowe kanały OK")

    print(f"Zalogowano jako {bot.user}")


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Czytelna obsługa błędów zamiast 'Aplikacja nie reaguje'."""
    if isinstance(error, app_commands.CheckFailure):
        message = "⛔ Nie masz uprawnień do użycia tej komendy."
    elif isinstance(error, app_commands.CommandOnCooldown):
        message = f"⏳ Spróbuj ponownie za **{error.retry_after:.1f}s**."
    else:
        original = getattr(error, "original", error)
        print(f"[SLASH ERROR] {type(original).__name__}: {original}")
        message = "❌ Wystąpił błąd podczas wykonywania komendy. Szczegóły zapisano w logach bota."

    try:
        embed = notice_embed("⚠️・BŁĄD KOMENDY", message)
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as send_error:
        print(f"[SLASH ERROR RESPONSE] {type(send_error).__name__}: {send_error}")


@bot.event
async def on_app_command_completion(interaction: discord.Interaction, command: app_commands.Command):
    """Loguj WYŁĄCZNIE zakończone sukcesem komendy."""
    try:
        await send_success_log(interaction, command.qualified_name)
    except Exception as e:
        print(f"[APP COMPLETION LOG ERROR] {type(e).__name__}: {e}")


@tasks.loop(time=time(hour=8, minute=30, tzinfo=ZoneInfo("Europe/Warsaw")))
async def activity_test_task():
    """Codzienny test aktywności o 08:30 czasu polskiego."""
    for guild in bot.guilds:
        channel = await get_text_channel(guild, ACTIVITY_TEST_CHANNEL_ID)
        if channel is None:
            print(f"[TEST AKTYWNOSCI] Brak kanału {ACTIVITY_TEST_CHANNEL_ID}")
            continue

        role = guild.get_role(ACTIVITY_PING_ROLE_ID)
        ping = role.mention if role else f"<@&{ACTIVITY_PING_ROLE_ID}>"
        embed = discord.Embed(
            title="📋・TEST AKTYWNOŚCI",
            description=(
                "## TEST AKTYWNOŚCI\n"
                "### Zareaguj 👍 pod tą wiadomością, aby potwierdzić swoją aktywność.\n\n"
                f"> Powiadomiona rola: {ping}\n"
                "> Wiadomość wysyłana automatycznie każdego dnia o **08:30**."
            ),
            timestamp=datetime.now()
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.set_footer(text="BCSO • Automatyczny test aktywności • 08:30")

        try:
            message = await channel.send(
                content=ping,
                embed=embed,
                allowed_mentions=discord.AllowedMentions(roles=True, users=False, everyone=False)
            )
            await message.add_reaction("👍")
        except Exception as e:
            print(f"[TEST AKTYWNOSCI ERROR] {type(e).__name__}: {e}")


@activity_test_task.before_loop
async def before_activity_test_task():
    await bot.wait_until_ready()


@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    before_ids = {r.id for r in before.roles}
    after_ids = {r.id for r in after.roles}
    added_ids = after_ids - before_ids

    # Automatyczny degrad x1 po nadaniu wskazanej roli.
    if AUTO_DEGRAD_TRIGGER_ROLE_ID in added_ids:
        try:
            await process_auto_rank_trigger(after, AUTO_DEGRAD_TRIGGER_ROLE_ID, -1)
        except Exception as e:
            print(f"[AUTO DEGRAD ERROR] {type(e).__name__}: {e}")

    # Automatyczny awans x1 po nadaniu wskazanej roli.
    if AUTO_AWANS_TRIGGER_ROLE_ID in added_ids:
        try:
            await process_auto_rank_trigger(after, AUTO_AWANS_TRIGGER_ROLE_ID, +1)
        except Exception as e:
            print(f"[AUTO AWANS ERROR] {type(e).__name__}: {e}")


@bot.event
async def on_guild_channel_create(channel):
    if isinstance(channel, discord.TextChannel) and is_ticket_channel(channel):
        track_ticket_channel(channel)


@bot.event
async def on_guild_channel_update(before, after):
    if not isinstance(after, discord.TextChannel):
        return

    # Jeśli Ticket Tool utworzył/zmienił kanał tak, że dopiero teraz wygląda jak ticket.
    if is_ticket_channel(after) and not ticket_is_tracked(after.guild.id, after.id):
        track_ticket_channel(after)

    # Typowy Ticket Tool przy zamknięciu zmienia nazwę na "closed-...".
    before_name = normalize_name(before.name)
    after_name = normalize_name(after.name)
    just_closed = ("closed" in after_name or "zamkn" in after_name) and after_name != before_name

    if just_closed and ticket_is_tracked(after.guild.id, after.id):
        try:
            await send_ticket_transcript(after.guild, after.id, after.name)
        except Exception as e:
            print(f"[TICKET CLOSE PDF ERROR] {type(e).__name__}: {e}")


@bot.event
async def on_guild_channel_delete(channel):
    if not isinstance(channel, discord.TextChannel):
        return
    if ticket_is_tracked(channel.guild.id, channel.id):
        try:
            await send_ticket_transcript(channel.guild, channel.id, channel.name)
        except Exception as e:
            print(f"[TICKET DELETE PDF ERROR] {type(e).__name__}: {e}")


@bot.event
async def on_message(message: discord.Message):
    if message.guild is not None and isinstance(message.channel, discord.TextChannel):
        # Jeśli wiadomość od Ticket Tool pojawiła się w kanale, oznacz go jako ticket.
        author_name = normalize_name(str(message.author))
        if "ticket tool" in author_name and not ticket_is_tracked(message.guild.id, message.channel.id):
            track_ticket_channel(message.channel)

        if ticket_is_tracked(message.guild.id, message.channel.id):
            save_ticket_message(message)

    await bot.process_commands(message)


@bot.tree.command(name="plus", description="Nadaj plus i automatycznie ustaw rolę Plus 1/3, 2/3 lub 3/3")
@app_commands.describe(osoba="Osoba", powod="Powód plusa")
async def plus(interaction: discord.Interaction, osoba: discord.Member, powod: str):
    if not await require_staff(interaction): return
    await interaction.response.defer(ephemeral=True)

    add_action(interaction.guild_id, osoba.id, interaction.user.id, "Plus", 1, powod)
    count = count_actions(interaction.guild_id, osoba.id, "Plus")
    ok, role_info = await set_progress_role(osoba, "Plus", count, 3)

    embed = action_embed(
        "✅・PLUS", osoba, interaction.user, powod,
        detail_name="📊 Stan",
        detail_value=f"**{min(count, 3)}/3**" + (f" • {role_info}" if ok else f"\\n⚠️ {role_info}")
    )
    sent, info = await send_action_log(interaction, "akta", embed)
    await interaction.followup.send(
        f"{'✅' if sent else '⚠️'} Plus zapisany. {info}",
        ephemeral=True
    )


@bot.tree.command(name="pochwala", description="Nadaj pochwałę i automatycznie ustaw rolę Pochwała 1/2 lub 2/2")
@app_commands.describe(osoba="Osoba", powod="Powód pochwały")
async def pochwala(interaction: discord.Interaction, osoba: discord.Member, powod: str):
    if not await require_staff(interaction): return
    await interaction.response.defer(ephemeral=True)

    add_action(interaction.guild_id, osoba.id, interaction.user.id, "Pochwala", 1, powod)
    count = count_actions(interaction.guild_id, osoba.id, "Pochwala")
    ok, role_info = await set_progress_role(osoba, "Pochwala", count, 2)

    embed = action_embed(
        "🌟・POCHWAŁA", osoba, interaction.user, powod,
        detail_name="📊 Stan",
        detail_value=f"**{min(count, 2)}/2**" + (f" • {role_info}" if ok else f"\\n⚠️ {role_info}")
    )
    sent, info = await send_action_log(interaction, "akta", embed)
    await interaction.followup.send(
        f"{'✅' if sent else '⚠️'} Pochwała zapisana. {info}",
        ephemeral=True
    )


@bot.tree.command(name="minus", description="Nadaj minus i automatycznie ustaw rolę Minus 1/3, 2/3 lub 3/3")
@app_commands.describe(osoba="Osoba", powod="Powód minusa")
async def minus(interaction: discord.Interaction, osoba: discord.Member, powod: str):
    if not await require_staff(interaction): return
    await interaction.response.defer(ephemeral=True)

    add_action(interaction.guild_id, osoba.id, interaction.user.id, "Minus", -1, powod)
    count = count_actions(interaction.guild_id, osoba.id, "Minus")
    ok, role_info = await set_progress_role(osoba, "Minus", count, 3)

    embed = action_embed(
        "🔴・MINUS", osoba, interaction.user, powod,
        detail_name="📊 Stan",
        detail_value=f"**{min(count, 3)}/3**" + (f" • {role_info}" if ok else f"\\n⚠️ {role_info}")
    )
    sent, info = await send_action_log(interaction, "akta", embed)
    await interaction.followup.send(
        f"{'✅' if sent else '⚠️'} Minus zapisany. {info}",
        ephemeral=True
    )


@bot.tree.command(name="nagana", description="Nadaj naganę i automatycznie ustaw rolę Nagana 1/2 lub 2/2")
@app_commands.describe(osoba="Osoba", powod="Powód nagany")
async def nagana(interaction: discord.Interaction, osoba: discord.Member, powod: str):
    if not await require_staff(interaction): return
    await interaction.response.defer(ephemeral=True)

    add_action(interaction.guild_id, osoba.id, interaction.user.id, "Nagana", -2, powod)
    count = count_actions(interaction.guild_id, osoba.id, "Nagana")
    ok, role_info = await set_progress_role(osoba, "Nagana", count, 2)

    embed = action_embed(
        "⛔・NAGANA", osoba, interaction.user, powod,
        detail_name="📊 Stan",
        detail_value=f"**{min(count, 2)}/2**" + (f" • {role_info}" if ok else f"\\n⚠️ {role_info}")
    )
    sent, info = await send_action_log(interaction, "akta", embed)
    await interaction.followup.send(
        f"{'✅' if sent else '⚠️'} Nagana zapisana. {info}",
        ephemeral=True
    )


@bot.tree.command(name="lota", description="Wystaw LOTA i usuń wszystkie możliwe role użytkownika")
@app_commands.describe(osoba="Osoba", powod="Powód LOTA")
async def lota(interaction: discord.Interaction, osoba: discord.Member, powod: str):
    if not await require_staff(interaction): return
    await interaction.response.defer(ephemeral=True)

    me = interaction.guild.me
    removable = [
        role for role in osoba.roles
        if role != interaction.guild.default_role
        and not role.managed
        and me is not None
        and role < me.top_role
    ]
    skipped = [
        role for role in osoba.roles
        if role != interaction.guild.default_role and role not in removable
    ]

    if removable:
        try:
            await osoba.remove_roles(*removable, reason=f"LOTA | {powod} | {interaction.user}")
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Bot nie może usunąć części ról. Ustaw rolę bota wyżej w hierarchii.",
                ephemeral=True
            )
            return

    add_action(interaction.guild_id, osoba.id, interaction.user.id, "LOTA", 0, powod)

    embed = action_embed(
        "🚪・LOTA", osoba, interaction.user, powod,
        detail_name="🧹 Role",
        detail_value=f"Usunięto: **{len(removable)}**" + (f"\\nPominięto niedostępne: **{len(skipped)}**" if skipped else "")
    )
    sent, info = await send_action_log(interaction, "lota", embed)
    await interaction.followup.send(
        f"{'✅' if sent else '⚠️'} LOTA wykonana. {info}",
        ephemeral=True
    )


@bot.tree.command(name="blacklista", description="Dodaj osobę na blacklistę i nadaj rolę blacklisty")
@app_commands.describe(osoba="Osoba", powod="Powód blacklisty")
async def blacklista(interaction: discord.Interaction, osoba: discord.Member, powod: str):
    if not await require_staff(interaction): return
    await interaction.response.defer(ephemeral=True)

    role = interaction.guild.get_role(BLACKLIST_ROLE_ID)
    if role is None:
        await interaction.followup.send(
            f"❌ Nie znaleziono roli blacklisty `{BLACKLIST_ROLE_ID}`.",
            ephemeral=True
        )
        return

    try:
        await osoba.add_roles(role, reason=f"Blacklista | {powod} | {interaction.user}")
    except discord.Forbidden:
        await interaction.followup.send(
            "❌ Bot nie może nadać roli blacklisty. Ustaw rolę bota wyżej.",
            ephemeral=True
        )
        return

    con = db()
    con.execute(
        "INSERT OR REPLACE INTO blacklist VALUES(?,?,?,?,?)",
        (interaction.guild_id, osoba.id, powod, interaction.user.id,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    con.commit()
    con.close()
    add_action(interaction.guild_id, osoba.id, interaction.user.id, "Blacklista", 0, powod)

    embed = action_embed(
        "🚫・BLACKLISTA", osoba, interaction.user, powod,
        detail_name="🏷️ Nadana rola",
        detail_value=role.mention
    )
    sent, info = await send_action_log(interaction, "blacklista", embed)

    public_channel = await get_text_channel(interaction.guild, BLACKLIST_PUBLIC_LOG_CHANNEL_ID)
    if public_channel is not None:
        try:
            public_embed = discord.Embed(
                title="🚫・BLACKLISTA BCSO",
                description="━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                timestamp=datetime.now()
            )
            public_embed.add_field(name="👤 Osoba", value=osoba.mention, inline=True)
            public_embed.add_field(name="🛡️ Wystawił", value=interaction.user.mention, inline=True)
            public_embed.add_field(name="📝 Powód", value=powod, inline=False)
            public_embed.add_field(name="🏷️ Nadana rola", value=role.mention, inline=False)
            public_embed.set_thumbnail(url=osoba.display_avatar.url)
            public_embed.set_footer(text="BCSO • Publiczna lista blacklist")
            await public_channel.send(embed=public_embed)
        except Exception as e:
            print(f"[BLACKLIST PUBLIC LOG] {type(e).__name__}: {e}")

    await interaction.followup.send(
        f"{'✅' if sent else '⚠️'} Blacklista nadana. {info}",
        ephemeral=True
    )


def get_rank_ladder_roles(guild: discord.Guild):
    con = db()
    rows = con.execute(
        "SELECT role_id, position FROM rank_roles WHERE guild_id=? ORDER BY position ASC",
        (guild.id,)
    ).fetchall()
    con.close()

    if rows:
        roles = [guild.get_role(row[0]) for row in rows]
        return [r for r in roles if r is not None]
    return detected_rank_ladder(guild)


def find_member_rank(member: discord.Member, ladder):
    role_to_index = {role.id: idx for idx, role in enumerate(ladder)}
    matches = [(role_to_index[r.id], r) for r in member.roles if r.id in role_to_index]
    if not matches:
        return None, None
    return max(matches, key=lambda x: x[0])


async def shift_member_rank(member: discord.Member, delta: int, reason: str):
    ladder = get_rank_ladder_roles(member.guild)
    if not ladder:
        return False, "Nie znaleziono drabinki rang.", None, None

    current_index, current_role = find_member_rank(member, ladder)
    if current_index is None:
        return False, "Osoba nie ma skonfigurowanej rangi.", None, None

    target_index = max(0, min(len(ladder) - 1, current_index + delta))
    if target_index == current_index:
        edge = "najwyższej" if delta > 0 else "najniższej"
        return False, f"Osoba jest już na {edge} randze.", current_role, current_role

    target_role = ladder[target_index]
    try:
        await member.remove_roles(current_role, reason=reason)
        await member.add_roles(target_role, reason=reason)
    except discord.Forbidden:
        return False, "Bot nie może zmienić rangi. Ustaw jego rolę wyżej w hierarchii.", current_role, target_role

    return True, "OK", current_role, target_role


async def send_auto_rank_trigger_log(
    member: discord.Member,
    trigger_role_id: int,
    direction: str,
    old_role=None,
    new_role=None,
    error: str | None = None,
    trigger_removed: bool | None = None
):
    channel_id = AUTO_AWANS_LOG_CHANNEL_ID if direction == "awans" else AUTO_DEGRAD_LOG_CHANNEL_ID
    channel = await get_text_channel(member.guild, channel_id)
    if channel is None:
        print(f"[AUTO RANK LOG] Brak kanału {channel_id}")
        return

    success = error is None
    title = "🤖⬆️・AUTOMATYCZNY AWANS x1" if direction == "awans" else "🤖⬇️・AUTOMATYCZNY DEGRAD x1"

    embed = discord.Embed(
        title=title,
        description=(
            f"## {member.mention}\n"
            f"> Akcja została wykonana automatycznie przez **BCSO BOT** po nadaniu roli "
            f"<@&{trigger_role_id}>."
            if success else
            f"## {member.mention}\n"
            f"> Bot wykrył rolę <@&{trigger_role_id}>, ale nie mógł wykonać zmiany stopnia."
        ),
        timestamp=datetime.now()
    )

    embed.add_field(
        name="🤖 Wystawił",
        value=(bot.user.mention if bot.user else "**BCSO BOT**") + " • **BOT**",
        inline=True
    )
    embed.add_field(
        name="📊 Operacja",
        value="**Awans x1**" if direction == "awans" else "**Degrad x1**",
        inline=True
    )

    if success and old_role and new_role:
        embed.add_field(
            name="🎖️ Zmiana stopnia",
            value=f"{old_role.mention}\n**→**\n{new_role.mention}",
            inline=False
        )
    else:
        embed.add_field(
            name="❌ Powód niewykonania",
            value=error or "Nieznany błąd",
            inline=False
        )

    if trigger_removed is True:
        trigger_text = f"✅ <@&{trigger_role_id}> została automatycznie usunięta po obsłużeniu akcji."
    elif trigger_removed is False:
        trigger_text = f"⚠️ Nie udało się usunąć <@&{trigger_role_id}>. Sprawdź hierarchię roli bota."
    else:
        trigger_text = f"<@&{trigger_role_id}>"

    embed.add_field(
        name="🏷️ Rola wyzwalająca",
        value=trigger_text,
        inline=False
    )

    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text="BCSO • Automatyczny system awansów i degradów • wystawione przez BOT")

    try:
        await channel.send(embed=embed)
    except Exception as e:
        print(f"[AUTO RANK LOG ERROR] {type(e).__name__}: {e}")


async def consume_trigger_role(member: discord.Member, trigger_role_id: int) -> bool:
    trigger_role = member.guild.get_role(trigger_role_id)
    if trigger_role is None:
        return True

    if trigger_role not in member.roles:
        return True

    try:
        await member.remove_roles(
            trigger_role,
            reason="Automatyczne usunięcie roli wyzwalającej po awansie/degradzie | BCSO BOT"
        )
        return True
    except (discord.Forbidden, discord.HTTPException) as e:
        print(f"[AUTO RANK TRIGGER REMOVE ERROR] {type(e).__name__}: {e}")
        return False


async def process_auto_rank_trigger(member: discord.Member, trigger_role_id: int, delta: int):
    direction = "awans" if delta > 0 else "degrad"
    reason = f"Automatyczny {direction} x1 po nadaniu roli {trigger_role_id} | BCSO BOT"

    ok, info, old_role, new_role = await shift_member_rank(member, delta, reason)

    if ok:
        moderator_id = bot.user.id if bot.user else 0
        add_action(
            member.guild.id,
            member.id,
            moderator_id,
            f"Automatyczny {direction.title()} x1: {old_role.name} -> {new_role.name}",
            0,
            reason
        )

    # Rola wyzwalająca jest jednorazowa — po obsłużeniu zawsze ją zużywamy.
    trigger_removed = await consume_trigger_role(member, trigger_role_id)

    await send_auto_rank_trigger_log(
        member,
        trigger_role_id,
        direction,
        old_role,
        new_role,
        None if ok else info,
        trigger_removed=trigger_removed
    )


@bot.tree.command(name="awans", description="Awansuj osobę automatycznie o wybraną liczbę rang")
@app_commands.describe(osoba="Osoba", ile="O ile rang awansować, np. 1 albo 3", powod="Powód awansu")
async def awans(interaction: discord.Interaction, osoba: discord.Member, ile: app_commands.Range[int, 1, 20] = 1, powod: str = "Awans"):
    if not await require_staff(interaction):
        return

    ok, info, current_role, target_role = await shift_member_rank(
        osoba, int(ile), f"{powod} | {interaction.user}"
    )
    if not ok:
        await interaction.response.send_message(f"❌ {info}", ephemeral=True)
        return

    add_action(
        interaction.guild_id, osoba.id, interaction.user.id,
        f"Awans x{ile}: {current_role.name} -> {target_role.name}", 0, powod
    )
    embed = action_embed(
        "⬆️・AWANS", osoba, interaction.user, powod,
        detail_name="🎖️ Zmiana stopnia",
        detail_value=f"**{current_role.name}**  ➜  **{target_role.name}**\nAwans: **x{ile}**"
    )
    sent, log_info = await send_action_log(interaction, "awans", embed)
    await interaction.response.send_message(
        f"{'✅' if sent else '⚠️'} Awans wykonany. {log_info}",
        ephemeral=True
    )


@bot.tree.command(name="degrad", description="Zdegraduj osobę automatycznie o wybraną liczbę rang")
@app_commands.describe(osoba="Osoba", ile="O ile rang zdegradować", powod="Powód degradacji")
async def degrad(interaction: discord.Interaction, osoba: discord.Member, ile: app_commands.Range[int, 1, 20] = 1, powod: str = "Degradacja"):
    if not await require_staff(interaction):
        return

    ok, info, current_role, target_role = await shift_member_rank(
        osoba, -int(ile), f"{powod} | {interaction.user}"
    )
    if not ok:
        await interaction.response.send_message(f"❌ {info}", ephemeral=True)
        return

    add_action(
        interaction.guild_id, osoba.id, interaction.user.id,
        f"Degrad x{ile}: {current_role.name} -> {target_role.name}", 0, powod
    )
    embed = action_embed(
        "⬇️・DEGRADACJA", osoba, interaction.user, powod,
        detail_name="🎖️ Zmiana stopnia",
        detail_value=f"**{current_role.name}**  ➜  **{target_role.name}**\nDegrad: **x{ile}**"
    )
    sent, log_info = await send_action_log(interaction, "degrad", embed)
    await interaction.response.send_message(
        f"{'✅' if sent else '⚠️'} Degrad wykonany. {log_info}",
        ephemeral=True
    )


rangi = app_commands.Group(name="rangi", description="Konfiguracja automatycznych awansow")


@rangi.command(name="dodaj", description="Dodaj role do drabinki rang")
@app_commands.describe(rola="Rola", pozycja="Kolejnosc od najnizszej: 1, 2, 3...")
async def rangi_dodaj(interaction: discord.Interaction, rola: discord.Role, pozycja: app_commands.Range[int, 1, 100]):
    if not await require_staff(interaction): return
    con = db()
    con.execute(
        "INSERT OR REPLACE INTO rank_roles(guild_id, role_id, position) VALUES(?,?,?)",
        (interaction.guild_id, rola.id, pozycja)
    )
    con.commit()
    con.close()
    await interaction.response.send_message(
        f"✅ Dodano {rola.mention} jako pozycje **{pozycja}** w drabince rang.", ephemeral=True
    )


@rangi.command(name="usun", description="Usun role z drabinki rang")
async def rangi_usun(interaction: discord.Interaction, rola: discord.Role):
    if not await require_staff(interaction): return
    con = db()
    con.execute(
        "DELETE FROM rank_roles WHERE guild_id=? AND role_id=?",
        (interaction.guild_id, rola.id)
    )
    con.commit()
    con.close()
    await interaction.response.send_message(
        f"🗑️ Usunieto {rola.mention} z drabinki rang.", ephemeral=True
    )


@rangi.command(name="lista", description="Pokaz skonfigurowana drabinke rang")
async def rangi_lista(interaction: discord.Interaction):
    con = db()
    rows = con.execute(
        "SELECT role_id, position FROM rank_roles WHERE guild_id=? ORDER BY position ASC",
        (interaction.guild_id,)
    ).fetchall()
    con.close()

    if not rows:
        await interaction.response.send_message("Drabinka rang jest pusta.", ephemeral=True)
        return

    lines = []
    for role_id, position in rows:
        role = interaction.guild.get_role(role_id)
        lines.append(f"**{position}.** {role.mention if role else f'Usunieta rola ({role_id})'}")

    embed = discord.Embed(
        title="📈・DRABINKA RANG",
        description="\n".join(lines),
        timestamp=datetime.now()
    )
    embed.set_footer(text="BCSO • Konfiguracja awansów")
    await interaction.response.send_message(embed=embed, ephemeral=True)


bot.tree.add_command(rangi)


@bot.tree.command(name="profil", description="Pokaż profil kadrowy osoby")
async def profil(interaction: discord.Interaction, osoba: discord.Member):
    con = db()
    rows = con.execute(
        "SELECT action, points FROM actions WHERE guild_id=? AND user_id=?",
        (interaction.guild_id, osoba.id)
    ).fetchall()
    bl = con.execute(
        "SELECT reason FROM blacklist WHERE guild_id=? AND user_id=?",
        (interaction.guild_id, osoba.id)
    ).fetchone()
    con.close()

    punkty = sum(x[1] for x in rows)
    plusy = count_actions(interaction.guild_id, osoba.id, "Plus")
    pochwaly = count_actions(interaction.guild_id, osoba.id, "Pochwala")
    minusy = count_actions(interaction.guild_id, osoba.id, "Minus")
    nagany = count_actions(interaction.guild_id, osoba.id, "Nagana")
    rank = member_rank_from_ladder(osoba)

    embed = polished_embed(
        f"📁・PROFIL KADROWY — {osoba.display_name}",
        "Podsumowanie kartoteki funkcjonariusza"
    )
    embed.set_thumbnail(url=osoba.display_avatar.url)
    embed.add_field(name="🎖️ Stopień", value=rank.mention if rank else "Brak rozpoznanego stopnia", inline=False)
    embed.add_field(name="✅ Plusy", value=f"**{plusy}**", inline=True)
    embed.add_field(name="🌟 Pochwały", value=f"**{pochwaly}**", inline=True)
    embed.add_field(name="🔴 Minusy", value=f"**{minusy}**", inline=True)
    embed.add_field(name="⛔ Nagany", value=f"**{nagany}**", inline=True)
    embed.add_field(name="📊 Bilans", value=f"**{punkty:+d}**", inline=True)
    embed.add_field(name="🚫 Blacklista", value="**TAK**" if bl else "**NIE**", inline=True)
    embed.set_footer(text=f"BCSO • Wpisów w bazie: {len(rows)}")

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="historia", description="Pokaż ostatnie wpisy osoby")
async def historia(interaction: discord.Interaction, osoba: discord.Member):
    con = db()
    rows = con.execute(
        "SELECT action, points, reason, created_at FROM actions "
        "WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 10",
        (interaction.guild_id, osoba.id)
    ).fetchall()
    con.close()

    embed = polished_embed(
        f"🗂️・HISTORIA — {osoba.display_name}",
        "Ostatnie wpisy w kartotece"
    )
    embed.set_thumbnail(url=osoba.display_avatar.url)

    if not rows:
        embed.add_field(name="Brak wpisów", value="Ta osoba nie ma jeszcze historii.", inline=False)
    else:
        for action, points, reason, created_at in rows:
            point_text = f" • {points:+d} pkt" if points else ""
            embed.add_field(
                name=f"{action}{point_text}",
                value=f"**Powód:** {reason}\\n`{created_at}`",
                inline=False
            )

    embed.set_footer(text="BCSO • Ostatnie 10 wpisów")
    await interaction.response.send_message(embed=embed)


szkolenie = app_commands.Group(name="szkolenie", description="Zarządzanie rolami szkoleniowymi")


@szkolenie.command(name="nadaj", description="Nadaj jedną z 8 zatwierdzonych ról szkoleniowych")
@app_commands.describe(
    osoba="Osoba",
    rola="Wybierz wyłącznie zatwierdzone szkolenie z listy",
    powod="Powód nadania"
)
@app_commands.autocomplete(rola=training_role_autocomplete)
async def szkolenie_nadaj(
    interaction: discord.Interaction,
    osoba: discord.Member,
    rola: str,
    powod: str = "Nadanie szkolenia"
):
    if not await require_staff(interaction):
        return

    training_role = resolve_training_role(interaction.guild, rola)
    if training_role is None:
        await interaction.response.send_message(
            "❌ Możesz wybrać **wyłącznie jedną z 8 zatwierdzonych ról szkoleniowych z listy**.",
            ephemeral=True
        )
        return

    if training_role.id == SPECIAL_TRAINING_ROLE_ID and not has_role_id(osoba, SPECIAL_TRAINING_REQUIRED_ROLE_ID):
        await interaction.response.send_message(
            f"❌ {osoba.mention} nie spełnia wymagania tego szkolenia.\n"
            f"Musi posiadać rolę <@&{SPECIAL_TRAINING_REQUIRED_ROLE_ID}>.",
            ephemeral=True
        )
        return

    if training_role in osoba.roles:
        await interaction.response.send_message(
            f"ℹ️ {osoba.mention} posiada już {training_role.mention}.",
            ephemeral=True
        )
        return

    try:
        await osoba.add_roles(training_role, reason=f"{powod} | {interaction.user}")
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ Nie mogę nadać tej roli. Przenieś rolę bota wyżej w hierarchii ról.",
            ephemeral=True
        )
        return

    add_action(
        interaction.guild_id,
        osoba.id,
        interaction.user.id,
        f"Szkolenie nadaj -> {training_role.name}",
        0,
        powod
    )

    logged, log_info = await send_training_action_log(
        interaction, osoba, training_role, "nadaj", powod
    )

    await interaction.response.send_message(
        embed=notice_embed(
            "✅・SZKOLENIE NADANE",
            f"Nadano {training_role.mention} osobie {osoba.mention}.\n"
            f"Log: {log_info if logged else '⚠️ ' + log_info}"
        ),
        ephemeral=True
    )


@szkolenie.command(name="odbierz", description="Odbierz jedną z 8 zatwierdzonych ról szkoleniowych")
@app_commands.describe(
    osoba="Osoba",
    rola="Wybierz wyłącznie zatwierdzone szkolenie z listy",
    powod="Powód odebrania"
)
@app_commands.autocomplete(rola=training_role_autocomplete)
async def szkolenie_odbierz(
    interaction: discord.Interaction,
    osoba: discord.Member,
    rola: str,
    powod: str = "Odebranie szkolenia"
):
    if not await require_staff(interaction):
        return

    training_role = resolve_training_role(interaction.guild, rola)
    if training_role is None:
        await interaction.response.send_message(
            "❌ Możesz wybrać **wyłącznie jedną z 8 zatwierdzonych ról szkoleniowych z listy**.",
            ephemeral=True
        )
        return

    if training_role not in osoba.roles:
        await interaction.response.send_message(
            f"ℹ️ {osoba.mention} nie posiada {training_role.mention}.",
            ephemeral=True
        )
        return

    try:
        await osoba.remove_roles(training_role, reason=f"{powod} | {interaction.user}")
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ Nie mogę odebrać tej roli. Przenieś rolę bota wyżej w hierarchii ról.",
            ephemeral=True
        )
        return

    add_action(
        interaction.guild_id,
        osoba.id,
        interaction.user.id,
        f"Szkolenie odbierz -> {training_role.name}",
        0,
        powod
    )

    logged, log_info = await send_training_action_log(
        interaction, osoba, training_role, "odbierz", powod
    )

    await interaction.response.send_message(
        embed=notice_embed(
            "✅・SZKOLENIE ODEBRANE",
            f"Odebrano {training_role.mention} osobie {osoba.mention}.\n"
            f"Log: {log_info if logged else '⚠️ ' + log_info}"
        ),
        ephemeral=True
    )


bot.tree.add_command(szkolenie)


@bot.tree.command(name="hierarchia", description="Wyślij aktualną hierarchię BCSO")
async def hierarchia(interaction: discord.Interaction):
    if not await require_staff(interaction):
        return

    await interaction.response.defer(ephemeral=True)

    channel = await get_text_channel(interaction.guild, HIERARCHY_CHANNEL_ID)
    if channel is None:
        await interaction.followup.send(
            embed=notice_embed("❌・BŁĄD", f"Nie znaleziono kanału hierarchii <#{HIERARCHY_CHANNEL_ID}>."),
            ephemeral=True
        )
        return

    owner_role = interaction.guild.get_role(HIERARCHY_OWNER_ROLE_ID)
    owner_member = next(
        (
            m for m in interaction.guild.members
            if normalize_name(m.name) == normalize_name(HIERARCHY_OWNER_USERNAME)
            or normalize_name(m.display_name) == normalize_name(HIERARCHY_OWNER_USERNAME)
            or (getattr(m, "global_name", None) and normalize_name(m.global_name) == normalize_name(HIERARCHY_OWNER_USERNAME))
        ),
        None
    )

    lines = []

    # Najwyższa pozycja nad Sheriffem.
    lines.append("## 👑・KIEROWNICTWO")
    role_text = owner_role.mention if owner_role else f"<@&{HIERARCHY_OWNER_ROLE_ID}>"
    owner_text = owner_member.mention if owner_member else f"**{HIERARCHY_OWNER_USERNAME}**"
    lines.append(f"**{role_text}**")
    lines.append(f"> 👑 {owner_text}")
    lines.append("")
    lines.append("────────────────────")
    lines.append("")

    sections = [
        ("HIGH COMMAND", ["Sheriff", "UnderSheriff", "Assistant Sheriff", "Asystent HC"]),
        ("SECOND COMMAND", ["Division Chief", "Captain"]),
        ("PATROL DIVISION", [
            "Staff Lieutenant", "Lieutenant", "Sergeant II", "Sergeant",
            "Corporal II", "Corporal I", "Senior Deputy", "Deputy",
            "Probie Deputy", "Cadet"
        ]),
    ]

    for section_title, rank_names in sections:
        lines.append(f"## {section_title}")
        lines.append("")

        for rank_name in rank_names:
            role = find_rank_role(interaction.guild, rank_name)
            if role is None:
                continue

            members = [m for m in role.members if not m.bot]
            lines.append(f"**{role.mention}**")

            if members:
                for member in members:
                    lines.append(f"> • {member.mention}")
            else:
                lines.append("> — brak osób —")

            lines.append("")

        lines.append("────────────────────")
        lines.append("")

    # Discord embed description ma limit 4096 znaków. Dzielimy pionowo na części.
    chunks = []
    current = []
    current_len = 0
    for line in lines:
        add_len = len(line) + 1
        if current and current_len + add_len > 3800:
            chunks.append("\n".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += add_len
    if current:
        chunks.append("\n".join(current))

    embeds = []
    for idx, chunk in enumerate(chunks):
        if idx == 0:
            embed = discord.Embed(
                title="🏛️・HIERARCHIA BCSO",
                description=chunk,
                timestamp=datetime.now()
            )
            if interaction.guild.icon:
                embed.set_thumbnail(url=interaction.guild.icon.url)
        else:
            embed = discord.Embed(
                title="🏛️・HIERARCHIA BCSO — ciąg dalszy",
                description=chunk,
                timestamp=datetime.now()
            )
        embed.set_footer(text=f"BCSO • Hierarchia automatyczna • {idx + 1}/{len(chunks)}")
        embeds.append(embed)

    try:
        await channel.send(embeds=embeds)
        await interaction.followup.send(
            embed=notice_embed("✅・GOTOWE", f"Hierarchia została wysłana na {channel.mention}."),
            ephemeral=True
        )
    except discord.Forbidden:
        await interaction.followup.send(
            embed=notice_embed("❌・BRAK UPRAWNIEŃ", "Bot nie może wysłać hierarchii na ten kanał."),
            ephemeral=True
        )


class AnnouncementChannel(app_commands.Transformer):
    async def transform(self, interaction: discord.Interaction, value: str):
        return value


@bot.tree.command(name="ogloszenie", description="Wyślij ogłoszenie na wybrany kanał")
@app_commands.describe(
    tresc="Treść ogłoszenia",
    kanal="Kanał, na który ma trafić ogłoszenie",
    tytul="Tytuł ogłoszenia"
)
@app_commands.choices(kanal=[
    app_commands.Choice(name="Ogłoszenia", value="ogloszenia"),
    app_commands.Choice(name="Ogłoszenie Zarząd", value="zarzad"),
])
async def ogloszenie(
    interaction: discord.Interaction,
    tresc: str,
    kanal: app_commands.Choice[str],
    tytul: str = "OGŁOSZENIE"
):
    # Najpierw sprawdzamy uprawnienia bez wysyłania odpowiedzi z helpera,
    # a następnie NATYCHMIAST deferujemy interakcję, żeby Discord nie pokazał
    # "Aplikacja nie reaguje".
    master_access = isinstance(interaction.user, discord.Member) and has_role_id(interaction.user, ANNOUNCEMENT_MASTER_ROLE_ID)
    if not is_staff(interaction) and not master_access:
        await interaction.response.send_message(
            "❌ Nie masz uprawnień do tej komendy.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True, thinking=True)

    try:
        channel_id = ANNOUNCEMENT_CHANNELS.get(kanal.value)
        if not channel_id:
            await interaction.followup.send("❌ Nieprawidłowy kanał.", ephemeral=True)
            return

        channel = interaction.guild.get_channel(channel_id)
        if channel is None:
            try:
                channel = await bot.fetch_channel(channel_id)
            except Exception as e:
                print(f"[OGLOSZENIE] Nie mogę pobrać kanału {channel_id}: {e}")
                await interaction.followup.send(
                    f"❌ Bot nie widzi kanału o ID `{channel_id}`. "
                    "Sprawdź ID oraz uprawnienia bota do kanału.",
                    ephemeral=True
                )
                return

        if kanal.value == "zarzad":
            ping_roles = [interaction.guild.get_role(rid) for rid in MANAGEMENT_ANNOUNCEMENT_ROLE_IDS]
        else:
            ping_roles = [interaction.guild.get_role(ANNOUNCEMENT_ROLE_ID)]
        ping_roles = [r for r in ping_roles if r is not None]
        if not ping_roles:
            await interaction.followup.send("❌ Nie znaleziono żadnej roli do pingowania.", ephemeral=True)
            return
        ping_text = " ".join(r.mention for r in ping_roles)

        embed = discord.Embed(
            title=f"📢・{tytul}",
            description=(
                "## OFICJALNE OGŁOSZENIE\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"{large_announcement_text(tresc)}\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            timestamp=datetime.now()
        )
        embed.add_field(
            name="🔔 Powiadomienie",
            value=ping_text,
            inline=False
        )
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.set_footer(text=f"BCSO • {interaction.user.display_name}")

        await channel.send(
            content=ping_text,
            embed=embed,
            allowed_mentions=discord.AllowedMentions(
                roles=True, users=False, everyone=False
            )
        )

        await interaction.followup.send(
            f"✅ Ogłoszenie zostało wysłane na {channel.mention}.",
            ephemeral=True
        )

    except discord.Forbidden:
        await interaction.followup.send(
            "❌ Bot nie ma uprawnień do wysyłania wiadomości/embedów "
            "albo pingowania roli na tym kanale.",
            ephemeral=True
        )
    except discord.HTTPException as e:
        print(f"[OGLOSZENIE HTTP] {e}")
        await interaction.followup.send(
            f"❌ Discord odrzucił wiadomość (`HTTP {getattr(e, 'status', '?')}`). "
            "Szczegóły są w czarnym oknie bota.",
            ephemeral=True
        )
    except Exception as e:
        print(f"[OGLOSZENIE ERROR] {type(e).__name__}: {e}")
        await interaction.followup.send(
            f"❌ Błąd `/ogloszenie`: `{type(e).__name__}`. "
            "Szczegóły zostały wypisane w konsoli bota.",
            ephemeral=True
        )


@bot.tree.command(name="urlop", description="Wypisz swój urlop")
@app_commands.describe(
    od_kiedy="Od kiedy? np. 05.09.2026",
    do_kiedy="Do kiedy? np. 10.09.2026",
    powod="Powód urlopu"
)
async def urlop(interaction: discord.Interaction, od_kiedy: str, do_kiedy: str, powod: str):
    if interaction.channel_id != URLOP_CHANNEL_ID:
        await interaction.response.send_message(
            f"❌ Komendy `/urlop` można używać tylko na <#{URLOP_CHANNEL_ID}>.",
            ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    role = interaction.guild.get_role(URLOP_ROLE_ID)
    if role is None:
        await interaction.followup.send(
            f"❌ Nie znaleziono roli urlopowej `{URLOP_ROLE_ID}`.",
            ephemeral=True
        )
        return

    try:
        await interaction.user.add_roles(
            role,
            reason=f"Urlop {od_kiedy} - {do_kiedy} | {powod}"
        )
    except discord.Forbidden:
        await interaction.followup.send(
            "❌ Bot nie może nadać roli urlopowej. Ustaw rolę bota wyżej.",
            ephemeral=True
        )
        return

    embed = polished_embed(
        "🏖️・URLOP",
        "Wniosek urlopowy funkcjonariusza"
    )
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.add_field(name="👤 Kto", value=interaction.user.mention, inline=False)
    embed.add_field(name="📅 Od kiedy", value=od_kiedy, inline=True)
    embed.add_field(name="📅 Do kiedy", value=do_kiedy, inline=True)
    embed.add_field(name="📝 Powód", value=f"```{powod}```", inline=False)
    embed.add_field(name="🏷️ Nadana rola", value=role.mention, inline=False)
    embed.set_footer(text="BCSO • System urlopowy")

    channel = await get_text_channel(interaction.guild, URLOP_CHANNEL_ID)
    if channel is None:
        await interaction.followup.send("❌ Bot nie widzi kanału urlopów.", ephemeral=True)
        return

    await channel.send(embed=embed)
    await interaction.followup.send(
        "✅ Urlop został zapisany i nadano Ci rolę urlopową.",
        ephemeral=True
    )


@bot.tree.command(name="wypowiedzenie", description="Złóż wypowiedzenie ze służby")
@app_commands.describe(
    imie_i_nazwisko="Imię i nazwisko postaci",
    powod="Powód wypowiedzenia"
)
async def wypowiedzenie(
    interaction: discord.Interaction,
    imie_i_nazwisko: str,
    powod: str
):
    if interaction.guild is None:
        await interaction.response.send_message(
            "❌ Tej komendy można użyć tylko na serwerze.",
            ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    member = interaction.user
    if not isinstance(member, discord.Member):
        await interaction.followup.send("❌ Nie udało się pobrać Twojego profilu serwerowego.", ephemeral=True)
        return

    # Zapisz obecny stopień zanim role zostaną zdjęte
    old_rank = member_rank_from_ladder(member)
    old_rank_text = old_rank.mention if old_rank else "Brak rozpoznanego stopnia"

    final_role = interaction.guild.get_role(RESIGNATION_ROLE_ID)
    if final_role is None:
        await interaction.followup.send(
            f"❌ Nie znaleziono roli końcowej `{RESIGNATION_ROLE_ID}`.",
            ephemeral=True
        )
        return

    me = interaction.guild.me
    removable = []
    skipped = []
    for role in member.roles:
        if role == interaction.guild.default_role or role.id == RESIGNATION_ROLE_ID:
            continue
        if role.managed:
            skipped.append(role)
            continue
        if me is not None and role < me.top_role:
            removable.append(role)
        else:
            skipped.append(role)

    try:
        if removable:
            await member.remove_roles(
                *removable,
                reason=f"Wypowiedzenie | {imie_i_nazwisko} | {powod}"
            )
        if final_role not in member.roles:
            await member.add_roles(
                final_role,
                reason=f"Wypowiedzenie | {imie_i_nazwisko}"
            )
    except discord.Forbidden:
        await interaction.followup.send(
            "❌ Bot nie może zmienić Twoich ról. Ustaw rolę bota wyżej w hierarchii.",
            ephemeral=True
        )
        return

    embed = polished_embed(
        "📄・WYPOWIEDZENIE",
        f"Funkcjonariusz {member.display_name} złożył wypowiedzenie"
    )
    embed.add_field(name="🎖️ Stopień", value=old_rank_text, inline=False)
    embed.add_field(name="📝 Powód", value=f"```{powod}```", inline=False)
    embed.add_field(name="👤 Imię i nazwisko", value=imie_i_nazwisko, inline=False)
    embed.add_field(name="🏷️ Pozostawiona rola", value=final_role.mention, inline=False)

    if skipped:
        embed.add_field(
            name="⚠️ Role, których bot nie mógł usunąć",
            value=", ".join(r.mention for r in skipped[:10]),
            inline=False
        )

    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text="BCSO • System wypowiedzeń")

    # Wypowiedzenie zawsze trafia na dedykowany kanał.
    resignation_channel = await get_text_channel(interaction.guild, RESIGNATION_CHANNEL_ID)
    if resignation_channel is None:
        await interaction.followup.send(
            f"❌ Bot nie widzi kanału wypowiedzeń <#{RESIGNATION_CHANNEL_ID}>.",
            ephemeral=True
        )
        return

    try:
        await resignation_channel.send(embed=embed)
    except discord.Forbidden:
        await interaction.followup.send(
            "❌ Bot nie ma uprawnień do wysyłania wypowiedzeń na dedykowany kanał.",
            ephemeral=True
        )
        return

    # Wpis do bazy historii
    add_action(
        interaction.guild_id,
        member.id,
        member.id,
        "Wypowiedzenie",
        0,
        powod
    )

    await interaction.followup.send(
        f"✅ Wypowiedzenie zapisane. Usunięto **{len(removable)}** ról i pozostawiono {final_role.mention}.",
        ephemeral=True
    )


@bot.tree.command(name="zawieszenie", description="Zawieś funkcjonariusza i zachowaj jego obecne role")
@app_commands.describe(osoba="Funkcjonariusz", powod="Powód zawieszenia")
async def zawieszenie(interaction: discord.Interaction, osoba: discord.Member, powod: str):
    if not await require_staff(interaction):
        return

    await interaction.response.defer(ephemeral=True)

    suspension_role = interaction.guild.get_role(SUSPENSION_ROLE_ID)
    if suspension_role is None:
        await interaction.followup.send(
            embed=notice_embed("❌・BŁĄD", f"Nie znaleziono roli zawieszenia `{SUSPENSION_ROLE_ID}`."),
            ephemeral=True
        )
        return

    me = interaction.guild.me
    removable = []
    saved_ids = []

    for role in osoba.roles:
        if role == interaction.guild.default_role or role.id == SUSPENSION_ROLE_ID:
            continue
        if role.managed:
            continue
        if me is not None and role < me.top_role:
            removable.append(role)
            saved_ids.append(role.id)

    if not saved_ids:
        await interaction.followup.send(
            embed=notice_embed("⚠️・BRAK RÓL", "Nie znaleziono ról, które bot może zdjąć i zapisać."),
            ephemeral=True
        )
        return

    con = db()
    con.execute(
        "INSERT OR REPLACE INTO suspensions(guild_id,user_id,role_ids,moderator_id,reason,created_at) "
        "VALUES(?,?,?,?,?,?)",
        (
            interaction.guild_id,
            osoba.id,
            ",".join(str(rid) for rid in saved_ids),
            interaction.user.id,
            powod,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
    )
    con.commit()
    con.close()

    try:
        await osoba.remove_roles(*removable, reason=f"Zawieszenie | {powod} | {interaction.user}")
        await osoba.add_roles(suspension_role, reason=f"Zawieszenie | {powod} | {interaction.user}")
    except discord.Forbidden:
        await interaction.followup.send(
            embed=notice_embed("❌・BRAK UPRAWNIEŃ", "Ustaw rolę bota wyżej w hierarchii."),
            ephemeral=True
        )
        return

    add_action(interaction.guild_id, osoba.id, interaction.user.id, "Zawieszenie", 0, powod)

    embed = action_embed(
        "⛔・ZAWIESZENIE", osoba, interaction.user, powod,
        detail_name="📦 Zapisane role",
        detail_value=f"Zapisano **{len(saved_ids)}** ról. Po zdjęciu zawieszenia bot spróbuje je przywrócić."
    )
    log_channel = await get_text_channel(interaction.guild, SUSPENSION_LOG_CHANNEL_ID)
    if log_channel:
        try:
            await log_channel.send(embed=embed)
        except Exception as e:
            print(f"[ZAWIESZENIE LOG] {type(e).__name__}: {e}")

    await interaction.followup.send(
        embed=notice_embed(
            "✅・ZAWIESZENIE NADANE",
            f"{osoba.mention} otrzymał(a) {suspension_role.mention}.\\n"
            f"Zapisano **{len(saved_ids)}** poprzednich ról."
        ),
        ephemeral=True
    )


@bot.tree.command(name="zdjemijzawieszenie", description="Zdejmij zawieszenie i przywróć zapisane role")
@app_commands.describe(osoba="Funkcjonariusz")
async def zdjemijzawieszenie(interaction: discord.Interaction, osoba: discord.Member):
    if not await require_staff(interaction):
        return

    await interaction.response.defer(ephemeral=True)

    con = db()
    row = con.execute(
        "SELECT role_ids, reason FROM suspensions WHERE guild_id=? AND user_id=?",
        (interaction.guild_id, osoba.id)
    ).fetchone()
    con.close()

    if not row:
        await interaction.followup.send(
            embed=notice_embed("⚠️・BRAK ZAPISU", f"{osoba.mention} nie ma zapisanego zawieszenia."),
            ephemeral=True
        )
        return

    role_ids_text, old_reason = row
    role_ids = [int(x) for x in role_ids_text.split(",") if x.strip().isdigit()]
    me = interaction.guild.me

    roles_to_restore = []
    missing = 0
    for role_id in role_ids:
        role = interaction.guild.get_role(role_id)
        if role is None:
            missing += 1
            continue
        if role.managed or (me is not None and role >= me.top_role):
            missing += 1
            continue
        roles_to_restore.append(role)

    suspension_role = interaction.guild.get_role(SUSPENSION_ROLE_ID)

    try:
        if suspension_role and suspension_role in osoba.roles:
            await osoba.remove_roles(suspension_role, reason=f"Zdjęcie zawieszenia | {interaction.user}")
        if roles_to_restore:
            await osoba.add_roles(*roles_to_restore, reason=f"Przywrócenie ról po zawieszeniu | {interaction.user}")
    except discord.Forbidden:
        await interaction.followup.send(
            embed=notice_embed("❌・BRAK UPRAWNIEŃ", "Bot nie może przywrócić części ról. Ustaw jego rolę wyżej."),
            ephemeral=True
        )
        return

    con = db()
    con.execute(
        "DELETE FROM suspensions WHERE guild_id=? AND user_id=?",
        (interaction.guild_id, osoba.id)
    )
    con.commit()
    con.close()

    add_action(interaction.guild_id, osoba.id, interaction.user.id, "Zdjęcie zawieszenia", 0, old_reason)

    embed = action_embed(
        "✅・ZDJĘCIE ZAWIESZENIA", osoba, interaction.user, old_reason,
        detail_name="📦 Przywrócone role",
        detail_value=f"Przywrócono **{len(roles_to_restore)}** ról."
                     + (f"\\n⚠️ Nie udało się przywrócić: **{missing}**." if missing else "")
    )
    log_channel = await get_text_channel(interaction.guild, SUSPENSION_LOG_CHANNEL_ID)
    if log_channel:
        try:
            await log_channel.send(embed=embed)
        except Exception as e:
            print(f"[ZDEJMIJ ZAWIESZENIE LOG] {type(e).__name__}: {e}")

    await interaction.followup.send(
        embed=notice_embed(
            "✅・ZAWIESZENIE ZDJĘTE",
            f"Przywrócono {osoba.mention} **{len(roles_to_restore)}** zapisanych ról."
        ),
        ephemeral=True
    )


@bot.tree.command(name="restart", description="Uruchom ponownie bota")
async def restart(interaction: discord.Interaction):
    if not is_staff(interaction):
        await interaction.response.send_message(
            "❌ Nie masz uprawnień do restartowania bota.", ephemeral=True
        )
        return

    await interaction.response.send_message(
        "🔄 Restart bota... wrócę za kilka sekund.", ephemeral=True
    )
    # Kod 75 rozpoznaje START.bat i uruchamia proces ponownie.
    await bot.close()
    await asyncio.sleep(1)
    os._exit(75)


@bot.tree.error
async def app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    print(f"[SLASH ERROR] {type(error).__name__}: {error}")
    try:
        msg = f"❌ Wystąpił błąd: `{type(error).__name__}`. Sprawdź konsolę bota."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception as send_error:
        print(f"[ERROR HANDLER] {send_error}")


ogloszenie_wydzial = app_commands.Group(
    name="ogłoszenie",
    description="Ogłoszenia wydziałowe BCSO"
)


@ogloszenie_wydzial.command(name="iad", description="Wyślij oficjalne ogłoszenie IAD")
@app_commands.describe(
    tresc="Treść ogłoszenia",
    tytul="Opcjonalny własny tytuł"
)
async def ogloszenie_iad(
    interaction: discord.Interaction,
    tresc: str,
    tytul: str | None = None
):
    await send_department_announcement(interaction, "iad", tresc, tytul)


@ogloszenie_wydzial.command(name="sert", description="Wyślij oficjalne ogłoszenie SERT")
@app_commands.describe(
    tresc="Treść ogłoszenia",
    tytul="Opcjonalny własny tytuł"
)
async def ogloszenie_sert(
    interaction: discord.Interaction,
    tresc: str,
    tytul: str | None = None
):
    await send_department_announcement(interaction, "sert", tresc, tytul)


@ogloszenie_wydzial.command(name="ddu", description="Wyślij oficjalne ogłoszenie DDU")
@app_commands.describe(
    tresc="Treść ogłoszenia",
    tytul="Opcjonalny własny tytuł"
)
async def ogloszenie_ddu(
    interaction: discord.Interaction,
    tresc: str,
    tytul: str | None = None
):
    await send_department_announcement(interaction, "ddu", tresc, tytul)


@ogloszenie_wydzial.command(name="ftd", description="Wyślij oficjalne ogłoszenie FTD")
@app_commands.describe(
    tresc="Treść ogłoszenia",
    tytul="Opcjonalny własny tytuł"
)
async def ogloszenie_ftd(
    interaction: discord.Interaction,
    tresc: str,
    tytul: str | None = None
):
    await send_department_announcement(interaction, "ftd", tresc, tytul)




bot.tree.add_command(ogloszenie_wydzial)


init_db()
bot.run(TOKEN)
