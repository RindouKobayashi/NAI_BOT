import discord
import settings
import asyncio
from discord.ext import commands
from settings import logger
import core.queuehandler as queuehandler

from core.viewhandler import RemixView


# Discord Bot Permission
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)
    

@bot.event
async def on_ready():
    logger.info(f"User: {bot.user} (ID: {bot.user.id})")

    
    # Start queuehandler
    await queuehandler.start_queue(bot)

    # load cogs from cog 
    for cof_file in settings.COGS_DIR.glob("*cog.py"):
        if cof_file.name != "__init__.py":
            await bot.load_extension(f"cogs.{cof_file.name[:-3]}")

    # Change presence 
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="you"))

async def shutdown_tasks():
    """Perform shutdown tasks"""
    logger.warning("Bot is shutting down...")

    # Stop the queue
    await queuehandler.stop_queue()

    # Disable all active views
    for view in settings.Globals.remix_views.values():
        view: RemixView
        view.stop()
        for child in view.children:
            child: discord.ui.Button | discord.ui.Select
            child.disabled = True
        #view.reseed.disabled = True
        #view.remix.disabled = True
        message = view.bundle_data["message"]
        try:
            await message.edit(view=view)
        except discord.NotFound:
            # Message has already been deleted
            pass
        except discord.HTTPException as e:
            logger.error(f"Failed to edit message on exit: {e}")
            pass

    for view in settings.Globals.select_views.values():
        view: RemixView
        view.stop()
        for child in view.children:
            child: discord.ui.Button | discord.ui.Select
            child.disabled = True
        message = view.bundle_data["message"]
        try:
            await message.edit(view=view)
        except discord.NotFound:
            # Message has already been deleted
            pass
        except discord.HTTPException as e:
            logger.error(f"Failed to edit message on exit: {e}")
            pass

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