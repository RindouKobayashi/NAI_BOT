import discord
import settings
from settings import logger
from discord.ext import commands

class REACTION(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Check if reaction is 🗑️, if it's in certain channel and message by bot, if yes, delete it"""

        # Check if bot is reacting
        if payload.user_id == self.bot.user.id:
            return
        
        # Check if reaction is 🗑️
        if payload.emoji.name == "🗑️":
            
            # Check if it's in the correct channel (replace with your actual channel ID)
            if payload.channel_id != settings.IMAGE_GEN_BOT_CHANNEL:
                return
            
            # Get payload.message
            message = await self.bot.get_channel(payload.channel_id).fetch_message(payload.message_id)
            
            # Check number of reactions
            for reaction in message.reactions:
                if reaction.emoji == "🗑️":
                    # Check if reaction count is above 2
                    if reaction.count > 2:
                        await message.delete()
                        break
            
            # Check if there's at least one mention
            if not message.mentions:
                return
            
            # Original command author
            original_user = message.mentions[0]

            # Check if it's the original command author
            if original_user.id != payload.user_id:
                return
            
            # Delete message
            await message.delete()





async def setup(bot: commands.Bot):
    await bot.add_cog(REACTION(bot))
    logger.info("COG LOADED: REACTION - COG FILE: reaction_cog.py")