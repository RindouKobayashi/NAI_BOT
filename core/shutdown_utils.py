import discord
import settings
import asyncio
from settings import logger
import core.queuehandler as queuehandler
from core.viewhandler import RemixView
import aiohttp # Import aiohttp for exception handling

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
        except aiohttp.client_exceptions.ClientOSError as e:
            logger.error(f"Failed to edit message {message.id} during shutdown due to connection error: {e}")
        except discord.NotFound:
            # Message has already been deleted
            pass
        except discord.HTTPException as e:
            logger.error(f"Failed to edit message {message.id} on exit: {e}")
        except Exception as e: # Catch any other unexpected errors
            logger.error(f"An unexpected error occurred while editing message {message.id} during shutdown: {e}")


    for view in settings.Globals.select_views.values():
        view: RemixView
        view.stop()
        for child in view.children:
            child: discord.ui.Button | discord.ui.Select
            child.disabled = True
        message = view.bundle_data["message"]
        try:
            await message.edit(view=view)
        except aiohttp.client_exceptions.ClientOSError as e:
            logger.error(f"Failed to edit message {message.id} during shutdown due to connection error: {e}")
        except discord.NotFound:
            # Message has already been deleted
            pass
        except discord.HTTPException as e:
            logger.error(f"Failed to edit message {message.id} on exit: {e}")
        except Exception as e: # Catch any other unexpected errors
            logger.error(f"An unexpected error occurred while editing message {message.id} during shutdown: {e}")
