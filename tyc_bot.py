"""
TYC Discord Bot — Role Auto-Assigner
======================================
Reads from a Google Apps Script endpoint (which reads your Google Sheet).
When a member is newly approved (status = Active, discordSynced = No),
the bot looks them up by Discord username and assigns their role in:
  - The national TYC server
  - Their provincial server

Setup:
  1. pip install discord.py aiohttp
  2. Fill in CONFIGURATION below
  3. Deploy to Render (see README)
"""

import discord
import aiohttp
import asyncio
import logging
import os
from discord.ext import tasks

# ── CONFIGURATION ─────────────────────────────────────────────────────────────
# Put these in Render environment variables — do NOT hardcode in production

BOT_TOKEN     = os.getenv("DISCORD_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
SHEETS_URL    = os.getenv("SHEETS_URL", "YOUR_APPS_SCRIPT_URL_HERE")  # Web App URL
POLL_INTERVAL = 120  # seconds between polls

# Server IDs — right-click server icon → Copy Server ID (enable Developer Mode first)
NATIONAL_SERVER_ID = int(os.getenv("NATIONAL_SERVER_ID", "0"))

PROVINCE_SERVER_IDS = {
    "Ontario":       int(os.getenv("SERVER_ONTARIO",       "0")),
    "Nova Scotia":   int(os.getenv("SERVER_NOVA_SCOTIA",   "0")),
    "Quebec":        int(os.getenv("SERVER_QUEBEC",         "0")),
    "New Brunswick": int(os.getenv("SERVER_NEW_BRUNSWICK", "0")),
    "Alberta":       int(os.getenv("SERVER_ALBERTA",       "0")),
    "Saskatchewan":  int(os.getenv("SERVER_SASKATCHEWAN",  "0")),
}

# Role names as they exist in Discord (must match exactly)
# National server roles
NATIONAL_ROLE_MAP = {
    "CEO":                  "C-Suite",
    "COO":                  "C-Suite",
    "CIO":                  "C-Suite",
    "CCO":                  "C-Suite",
    "Provincial President": "Provincial President",
    "Municipal Executive":  "Municipal Executive",
    "Member":               "Member",
}

# Provincial server roles (same logic applies)
PROVINCIAL_ROLE_MAP = {
    "CEO":                  "C-Suite",
    "COO":                  "C-Suite",
    "CIO":                  "C-Suite",
    "CCO":                  "C-Suite",
    "Provincial President": "Provincial President",
    "Municipal Executive":  "Municipal Executive",
    "Member":               "Member",
}

# ── BOT SETUP ─────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("TYCBot")

intents = discord.Intents.default()
intents.members = True  # Required — enable in Discord Developer Portal → Bot → Privileged Intents
bot = discord.Client(intents=intents)

already_processed = set()  # Track Discord usernames we've already assigned roles to this session


# ── FETCH MEMBERS FROM GOOGLE SHEETS ──────────────────────────────────────────
async def fetch_pending_syncs():
    """
    Calls the Apps Script web app, which returns JSON of Active members
    where discordSynced == 'No'.
    Expected JSON format:
    [
      {
        "name": "Jane Doe",
        "discord": "janedoe#1234",
        "role": "Provincial President",
        "province": "Ontario",
        "email": "jane@example.com"
      },
      ...
    ]
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(SHEETS_URL, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    return data if isinstance(data, list) else []
                else:
                    log.warning(f"Apps Script returned status {resp.status}")
                    return []
    except Exception as e:
        log.error(f"Failed to fetch from Apps Script: {e}")
        return []


async def mark_synced_on_sheet(discord_username: str):
    """
    Calls the Apps Script to mark a member as synced.
    Apps Script should accept ?action=markSynced&discord=username
    """
    try:
        url = f"{SHEETS_URL}?action=markSynced&discord={discord_username}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    log.info(f"Marked {discord_username} as synced on sheet")
                else:
                    log.warning(f"markSynced returned {resp.status} for {discord_username}")
    except Exception as e:
        log.error(f"Failed to mark synced for {discord_username}: {e}")


# ── ROLE ASSIGNMENT ────────────────────────────────────────────────────────────
def find_member_by_username(guild: discord.Guild, discord_username: str) -> discord.Member | None:
    """Find a Discord guild member by their username (handles both old user#0000 and new format)."""
    discord_username = discord_username.strip().lower()
    for member in guild.members:
        # New username format (no discriminator)
        if member.name.lower() == discord_username:
            return member
        # Old format: username#1234
        if f"{member.name}#{member.discriminator}".lower() == discord_username:
            return member
        # Display name fallback
        if member.display_name.lower() == discord_username:
            return member
    return None


async def assign_role_in_guild(guild: discord.Guild, discord_username: str, role_name: str) -> bool:
    """Assign a role to a member in a specific guild. Returns True on success."""
    member = find_member_by_username(guild, discord_username)
    if not member:
        log.warning(f"  Could not find '{discord_username}' in '{guild.name}'")
        return False

    role = discord.utils.get(guild.roles, name=role_name)
    if not role:
        log.warning(f"  Role '{role_name}' not found in '{guild.name}' — create it in Discord first")
        return False

    if role in member.roles:
        log.info(f"  '{discord_username}' already has role '{role_name}' in '{guild.name}'")
        return True

    try:
        await member.add_roles(role, reason="TYC Member Tracker auto-assign")
        log.info(f"  Assigned '{role_name}' to '{discord_username}' in '{guild.name}'")
        return True
    except discord.Forbidden:
        log.error(f"  Bot lacks permission to assign roles in '{guild.name}'")
        return False
    except Exception as e:
        log.error(f"  Error assigning role in '{guild.name}': {e}")
        return False


async def process_member(member_data: dict):
    """Handle role assignment for one approved member across national + provincial servers."""
    discord_username = member_data.get("discord", "").strip()
    role            = member_data.get("role", "Member")
    province        = member_data.get("province", "")
    name            = member_data.get("name", discord_username)

    if not discord_username:
        log.warning(f"Skipping member '{name}' — no Discord username")
        return

    if discord_username.lower() in already_processed:
        return

    log.info(f"Processing: {name} | {role} | {province} | @{discord_username}")

    national_role_name  = NATIONAL_ROLE_MAP.get(role, "Member")
    provincial_role_name = PROVINCIAL_ROLE_MAP.get(role, "Member")

    success = True

    # 1. National server
    national_guild = bot.get_guild(NATIONAL_SERVER_ID)
    if national_guild:
        ok = await assign_role_in_guild(national_guild, discord_username, national_role_name)
        success = success and ok
    else:
        log.warning(f"National server (ID {NATIONAL_SERVER_ID}) not found — is the bot a member?")
        success = False

    # 2. Provincial server
    prov_server_id = PROVINCE_SERVER_IDS.get(province, 0)
    if prov_server_id:
        prov_guild = bot.get_guild(prov_server_id)
        if prov_guild:
            ok = await assign_role_in_guild(prov_guild, discord_username, provincial_role_name)
            success = success and ok
        else:
            log.warning(f"Provincial server for '{province}' not found — is the bot a member?")
    else:
        log.warning(f"No server ID configured for province: '{province}'")

    # Mark synced if fully successful
    if success:
        already_processed.add(discord_username.lower())
        await mark_synced_on_sheet(discord_username)
    else:
        log.warning(f"Role assignment incomplete for {name} — will retry next poll")


# ── POLL LOOP ─────────────────────────────────────────────────────────────────
@tasks.loop(seconds=POLL_INTERVAL)
async def poll_sheet():
    log.info("Polling Google Sheet for pending syncs...")
    members = await fetch_pending_syncs()
    if not members:
        log.info("No pending syncs found.")
        return
    log.info(f"Found {len(members)} member(s) to sync.")
    for m in members:
        await process_member(m)
        await asyncio.sleep(1)  # Rate-limit friendly


@poll_sheet.before_loop
async def before_poll():
    await bot.wait_until_ready()
    log.info("Bot ready — starting poll loop")


# ── EVENTS ────────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    log.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    log.info(f"Connected to {len(bot.guilds)} server(s):")
    for g in bot.guilds:
        log.info(f"  - {g.name} (ID: {g.id})")
    poll_sheet.start()


# ── RUN ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    bot.run(BOT_TOKEN)
