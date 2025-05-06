import discord
import settings
import asyncio
from discord.ext import commands
from settings import logger
import core.queuehandler as queuehandler
from contextmenu import image_contextmenu

from core.viewhandler import RemixView
from core.shutdown_utils import shutdown_tasks


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

    await bot.tree.sync() # Sync globally or to specific guild(s)

    # load contextmenu
    image_contextmenu.contextmenu(bot)

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
