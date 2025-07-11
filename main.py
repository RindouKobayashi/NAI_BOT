import discord
import settings
import asyncio
from discord.ext import commands
from settings import logger
import core.queuehandler as queuehandler
import json
import os
from contextmenu import image_contextmenu

from core.viewhandler import RemixView
from core.shutdown_utils import shutdown_tasks
from core.update_notifier import notify_user_of_update



# Discord Bot Permission
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='~', intents=intents)
settings.Globals.bot = bot  # Store bot instance in Globals for access during shutdown


@bot.event
async def on_ready():
    logger.info("="*50)
    logger.info("Bot Starting")
    logger.info(f"Discord Bot Process PID: {os.getpid()} (This is the actual bot process)")
    logger.info(f"User: {bot.user} (ID: {bot.user.id})")
    
    # Keep track of start time for uptime calculation
    bot.start_time = discord.utils.utcnow()
    
    # Start queuehandler
    await queuehandler.start_queue(bot)

    # load cogs from cog 
    for cog_file in settings.COGS_DIR.glob("*cog.py"):
        if cog_file.name != "__init__.py":
            await bot.load_extension(f"cogs.{cog_file.name[:-3]}")
            logger.info(f"COG LOADED: {cog_file.name[:-3]} - COG FILE: {cog_file.name}")

    #await bot.tree.sync() # Sync globally

    for guild_id in settings.DEVELOPER_SERVERS_LIST: # Sync for developer servers
        synced_guild = await bot.tree.sync(guild=discord.Object(id=guild_id))
        logger.info(f"Synced commands for guild: {guild_id}")

    # Add the update notification check to each command in the tree skipping group commands
    for command in bot.tree.walk_commands():
        if isinstance(command, discord.app_commands.Command):
            # Add the update notification check to the command
            command.add_check(notify_user_of_update)

    # load contextmenu
    image_contextmenu.contextmenu(bot)
    logger.info("Context menu loaded")

    # Load version, changelog, and notified users data
    bot.current_version = "Unknown"
    bot.changelog_content = "Changelog not loaded."
    bot.notified_users_data = {}

    try:
        if os.path.exists(settings.VERSION_FILE):
            with open(settings.VERSION_FILE, "r") as f:
                bot.current_version = f.read().strip()
        else:
            logger.warning(f"Version file not found at {settings.VERSION_FILE}.")

        if os.path.exists(settings.CHANGELOG_FILE):
            with open(settings.CHANGELOG_FILE, "r", encoding='utf-8') as f:
                bot.changelog_content = f.read()
        else:
            logger.warning(f"Changelog file not found at {settings.CHANGELOG_FILE}.")

        if os.path.exists(settings.NOTIFIED_USERS_FILE):
            try:
                with open(settings.NOTIFIED_USERS_FILE, "r") as f:
                    bot.notified_users_data = json.load(f)
            except json.JSONDecodeError:
                logger.error(f"Error decoding JSON from {settings.NOTIFIED_USERS_FILE}. Starting with empty notified users data.")
                bot.notified_users_data = {}
            except Exception as e:
                logger.error(f"Error loading notified users data from {settings.NOTIFIED_USERS_FILE}: {e}. Starting with empty notified users data.")
                bot.notified_users_data = {}
        else:
            logger.warning(f"Notified users file not found at {settings.NOTIFIED_USERS_FILE}. Starting with empty notified users data.")
            bot.notified_users_data = {}

        logger.info(f"Bot Version: {bot.current_version}")
        logger.debug(f"Notified Users Data Loaded: {len(bot.notified_users_data.get(bot.current_version, []))} users notified for this version.")

    except Exception as e:
        logger.error(f"An error occurred while loading update notification data: {e}")

    logger.info(f"Bot is ready and all {len(bot.cogs)} cogs have been loaded")
    logger.info("="*50)

async def main():
    try:
        await bot.start(settings.DISCORD_API_TOKEN)
    finally:
        await shutdown_tasks()
        if not bot.is_closed():
            await bot.close()

def run():
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Initiating shutdown...")
    finally:
        pending = asyncio.all_tasks(loop=loop)
        for task in pending:
            task.cancel()
        group = asyncio.gather(*pending, return_exceptions=True)
        loop.run_until_complete(group)
        loop.close()
        logger.info("Bot has shut down.")

if __name__ == "__main__":
    run()
