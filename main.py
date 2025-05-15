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
    

@bot.event
async def on_ready():
    logger.info(f"User: {bot.user} (ID: {bot.user.id})")
    """ for guild in bot.guilds:
        member = guild.get_member(bot.user.id)
        await member.edit(nick=None) """
    
    # Start queuehandler
    await queuehandler.start_queue(bot)

    # load cogs from cog 
    for cog_file in settings.COGS_DIR.glob("*cog.py"):
        if cog_file.name != "__init__.py":
            await bot.load_extension(f"cogs.{cog_file.name[:-3]}")
            logger.info(f"COG LOADED: {cog_file.name[:-3]} - COG FILE: {cog_file.name}")

    #await bot.tree.sync() # Sync globally or to specific guild(s)

    # Add the update notification check to each command in the tree
    for command in bot.tree.walk_commands():
        command.add_check(notify_user_of_update)
    logger.info("Update notification check added to all commands in the tree.")

    # load contextmenu
    image_contextmenu.contextmenu(bot)

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
        logger.info(f"Notified Users Data Loaded: {len(bot.notified_users_data.get(bot.current_version, []))} users notified for this version.")

    except Exception as e:
        logger.error(f"An error occurred while loading update notification data: {e}")

async def main():
    try:
        await bot.start(settings.DISCORD_API_TOKEN)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt. Shutting down...")
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
