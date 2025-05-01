import discord
import random
from discord.ext import commands, tasks
from settings import logger
from datetime import timedelta

class PresenceCog(commands.Cog):
    """Handles the bot's auto-rotating presence."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.guild_count = 0
        self.current_status = None
        self.start_time = discord.utils.utcnow()
        self.change_status.start()

    def cog_unload(self):
        self.change_status.cancel()

    def get_statuses(self):
        """Returns dynamic statuses including bot info"""
        # Temporary test start times for uptime display
        test_start_times = [
            discord.utils.utcnow(), # Just started
            discord.utils.utcnow() - timedelta(seconds=30), # Seconds
            discord.utils.utcnow() - timedelta(minutes=5, seconds=30), # Minutes and seconds
            discord.utils.utcnow() - timedelta(hours=2, minutes=15), # Hours and minutes
            discord.utils.utcnow() - timedelta(days=3, hours=10), # Days and hours
            discord.utils.utcnow() - timedelta(days=5), # Days only
            discord.utils.utcnow() - timedelta(hours=10), # Hours only
            discord.utils.utcnow() - timedelta(minutes=30), # Minutes only
            discord.utils.utcnow() - timedelta(days=1, minutes=1), # Day and minute
            discord.utils.utcnow() - timedelta(hours=1, seconds=1), # Hour and second
        ]

        # Use a test start time for now
        # Cycle through the test start times for demonstration
        test_index = (self.change_status.current_loop) % len(test_start_times)
        current_test_time = test_start_times[test_index]

        # Calculate and format uptime using the test time
        uptime_seconds = (discord.utils.utcnow() - current_test_time).total_seconds()
        display_parts = []

        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        seconds = int(uptime_seconds % 60)

        if days > 0:
            display_parts.append(f"{days} day{'s' if days > 1 else ''}")
        if hours > 0 and len(display_parts) < 2:
            display_parts.append(f"{hours} hr{'s' if hours > 1 else ''}")
        if minutes > 0 and len(display_parts) < 2:
            display_parts.append(f"{minutes} min{'s' if minutes > 1 else ''}")
        # Only include seconds if uptime is less than a minute and no other parts are included, and only if it's one of the top two largest units
        if seconds > 0 and len(display_parts) < 2 and not display_parts:
             display_parts.append(f"{seconds} sec{'s' if seconds > 1 else ''}")

        uptime_str = " ".join(display_parts) if display_parts else "just started"

        # Define all statuses (including original ones)
        all_statuses = [
            (discord.ActivityType.playing, "with NovelAI"),
            (discord.ActivityType.watching, f"{self.guild_count} servers"),
            (discord.ActivityType.watching, "anime art"),
            (discord.ActivityType.watching, "art being generated"),
            (discord.ActivityType.listening, "prompt requests"),
            (discord.ActivityType.playing, "with image generation"),
            (discord.ActivityType.watching, f"{len(self.bot.users)} artists"),
            (discord.ActivityType.listening, "image commands"),
            (discord.ActivityType.playing, "with AI art"),
            (discord.ActivityType.watching, "masterpieces form"),
            (discord.ActivityType.watching, f"Uptime: {uptime_str}"), # Add the uptime status
        ]

        # Add ping status only if latency is finite
        if self.bot.latency != float('inf'):
             all_statuses.append((discord.ActivityType.listening, f"Ping: {round(self.bot.latency * 1000)}ms"))

        # Temporarily filter to only show uptime for testing
        # In a real scenario, you would remove this line
        all_statuses = [(discord.ActivityType.watching, f"Uptime: {uptime_str}")]


        # Filter out current status if it exists
        if self.current_status:
            return [s for s in all_statuses if s != self.current_status]
        return all_statuses

    @tasks.loop(seconds=12)
    async def change_status(self):
        """Cycles through dynamic statuses without repeating."""
        try:
            self.guild_count = len(self.bot.guilds)
            available_statuses = self.get_statuses()
            if not available_statuses:
                return
            
            self.current_status = random.choice(available_statuses)
            activity_type, status_text = self.current_status
            activity = discord.Activity(type=activity_type, name=status_text)
            await self.bot.change_presence(activity=activity)
            logger.debug(f"Changed presence to: {activity_type.name} {status_text}")
        except Exception as e:
            logger.error(f"Error in change_status loop: {e}", exc_info=True)

    @change_status.before_loop
    async def before_change_status(self):
        """Waits until the bot is ready before starting the loop."""
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    """Adds the PresenceCog to the bot."""
    await bot.add_cog(PresenceCog(bot))
