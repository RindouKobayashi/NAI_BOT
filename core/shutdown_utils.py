import discord
import settings
import asyncio
from settings import logger
import core.queuehandler as queuehandler
from core.viewhandler import RemixView
import aiohttp # Import aiohttp for exception handling

async def edit_message_safe(message, view):
    """Safely edit a message with error handling."""
    try:
        await message.edit(view=view)
    except Exception as e:
        # Log but don't raise - we expect some edits to fail during shutdown
        logger.debug(f"Expected edit failure during shutdown for message {message.id}: {e}")

async def shutdown_tasks():
    """Perform shutdown tasks"""
    logger.warning("Bot is shutting down...")

    # Stop the queue first
    await queuehandler.stop_queue()
    
    # Get bot instance from settings (where it's stored during startup)
    bot = settings.Globals.bot

    # Close bot's HTTP session if it exists
    if hasattr(bot, 'http'):
        if hasattr(bot.http, '_client_session') and not bot.http._client_session.closed:
            await bot.http._client_session.close()
            # Small delay to allow connections to close gracefully
            await asyncio.sleep(0.5)

    try:
        # Process views with a short timeout to ensure we complete before session close
        async with asyncio.timeout(5.0):  # 5 second timeout
            # Make copies of the views to prevent modification during iteration
            remix_views = list(settings.Globals.remix_views.values())
            select_views = list(settings.Globals.select_views.values())

            # Disable all views immediately without waiting for message edits
            for view in remix_views + select_views:
                view: RemixView
                view.stop()
                for child in view.children:
                    child: discord.ui.Button | discord.ui.Select
                    child.disabled = True

            # Now attempt to update messages, with proper exception handling
            update_tasks = []
            for view in remix_views + select_views:
                message = view.bundle_data["message"]
                task = asyncio.create_task(edit_message_safe(message, view))
                update_tasks.append(task)

            if update_tasks:
                # Wait for all updates but handle timeouts gracefully
                try:
                    async with asyncio.timeout(3.0):  # 3 second timeout for message updates
                        await asyncio.gather(*update_tasks, return_exceptions=True)
                except asyncio.TimeoutError:
                    logger.debug("Some message updates timed out during shutdown - this is expected")
                except Exception as e:
                    logger.debug(f"Non-critical error during message updates: {e}")

    except asyncio.TimeoutError:
        logger.warning("View cleanup timed out during shutdown, proceeding with shutdown anyway")
    except Exception as e:
        logger.error(f"Error during view cleanup: {e}")
    finally:
        # Clean up any remaining tasks and ensure sessions are closed
        for task in asyncio.all_tasks():
            if task != asyncio.current_task():
                # Extra cleanup for aiohttp sessions/connectors before canceling
                for attr in ['_session', '_connector']:
                    try:
                        if hasattr(task, attr):
                            session_or_connector = getattr(task, attr)
                            if hasattr(session_or_connector, 'closed') and not session_or_connector.closed:
                                await session_or_connector.close()
                    except Exception as e:
                        logger.debug(f"Non-critical error during {attr} cleanup: {e}")
                
                task.cancel()

        # Always clear the view dictionaries
        settings.Globals.remix_views.clear()
        settings.Globals.select_views.clear()

        # Final check for any remaining unclosed connectors
        for task in asyncio.all_tasks():
            for attr in ['_session', '_connector']:
                try:
                    if hasattr(task, attr):
                        session_or_connector = getattr(task, attr)
                        if hasattr(session_or_connector, 'closed') and not session_or_connector.closed:
                            await session_or_connector.close()
                except Exception as e:
                    logger.debug(f"Non-critical error during final {attr} cleanup: {e}")
