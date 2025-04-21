import discord
import json
from discord.ext import commands, tasks
from settings import logger
import settings

class StatsCog(commands.Cog):
    """Handles displaying NAI statistics in a designated channel."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.stats_channel_id = 1363733615434793011
        self.stats_message = None
        self.update_stats.start()

    def cog_unload(self):
        self.update_stats.cancel()

    async def get_or_create_stats_message(self):
        """Gets existing stats message or creates a new one."""
        channel = self.bot.get_channel(self.stats_channel_id)
        if not channel:
            logger.error(f"Could not find stats channel {self.stats_channel_id}")
            return None

        # Try to find existing message from bot
        async for message in channel.history(limit=50):
            if message.author == self.bot.user:
                return message

        # Create new message if none found
        try:
            return await channel.send("Initializing statistics...")
        except Exception as e:
            logger.error(f"Failed to send initial stats message: {e}", exc_info=True)
            return None

    def format_stats(self, nai_data):
        """Formats statistics into a readable message."""
        # Sort users by NAI Generations count in descending order
        sorted_users = sorted(nai_data.items(), key=lambda x: x[1], reverse=True)
        
        message_lines = ["**NAI Statistics**\n"]
        for user_id, count in sorted_users:
            mention = f"<@{user_id}>"
            message_lines.append(f"{mention} - `{count}` NAI generations")

        return "\n".join(message_lines)

    @tasks.loop(minutes=1)
    async def update_stats(self):
        """Updates the stats message with current NAI generation counts."""
        try:
            # Load NAI stats data
            with open(settings.STATS_JSON, "r") as f:
                nai_stats = json.load(f)

            # Get or create message
            if not self.stats_message:
                self.stats_message = await self.get_or_create_stats_message()
                if not self.stats_message:
                    return

            # Format and update message
            formatted_stats = self.format_stats(nai_stats)
            await self.stats_message.edit(content=formatted_stats)
            logger.debug("Updated NAI statistics message")
        except Exception as e:
            logger.error(f"Error in update_stats loop: {e}", exc_info=True)

    @update_stats.before_loop
    async def before_update_stats(self):
        """Waits until the bot is ready before starting the loop."""
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    """Adds the StatsCog to the bot."""
    await bot.add_cog(StatsCog(bot))