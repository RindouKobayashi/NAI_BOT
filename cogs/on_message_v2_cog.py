import discord
import settings
from settings import logger
from discord.ext import commands
import json
import aiohttp

class ON_MESSAGE_V2(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.blacklist = self.load_blacklist()
        # Hardcode destination server ID for now, can be moved to settings.py later
        self.destination_server_id = "409959440616390668"

    def load_blacklist(self):
        file_path = 'database/message_duplicator_blacklist.json'
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"{file_path} not found. Creating an empty one.")
            empty_blacklist = {"blacklisted_servers": [], "blacklisted_channels": []}
            with open(file_path, 'w') as f:
                json.dump(empty_blacklist, f, indent=2)
            return empty_blacklist
        except json.JSONDecodeError:
            logger.error(f"Error decoding {file_path}. Returning empty blacklist.")
            return {"blacklisted_servers": [], "blacklisted_channels": []}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.author.id == self.bot.owner_id:
            return

        # Blacklist check
        if str(message.guild.id) in self.blacklist.get("blacklisted_servers", []):
            return
        if str(message.channel.id) in self.blacklist.get("blacklisted_channels", []):
            return

        # --- Message Duplication Logic ---
        # Only process messages from non-destination servers
        if str(message.guild.id) != self.destination_server_id:
            destination_guild = self.bot.get_guild(int(self.destination_server_id))
            if not destination_guild:
                logger.error(f"Destination server with ID {self.destination_server_id} not found.")
                return

            # Find or create category
            category_name = f"From {message.guild.name}"
            category = discord.utils.get(destination_guild.categories, name=category_name)
            if not category:
                try:
                    category = await destination_guild.create_category(category_name)
                    logger.info(f"Created category '{category_name}' in destination server.")
                except discord.Forbidden:
                    logger.error(f"Missing permissions to create category '{category_name}' in destination server.")
                    return
                except Exception as e:
                    logger.error(f"Error creating category '{category_name}': {e}")
                    return

            # Find or create channel within category
            channel_name = message.channel.name.lower().replace(' ', '-')
            # Ensure channel name is valid and unique if needed (Discord limit is 100 chars)
            if len(channel_name) > 100:
                channel_name = channel_name[:95] + "-" + str(message.channel.id)[:4] # Append part of ID for uniqueness

            destination_channel = discord.utils.get(category.text_channels, name=channel_name)
            if not destination_channel:
                try:
                    destination_channel = await category.create_text_channel(channel_name)
                    logger.info(f"Created channel '{channel_name}' in category '{category_name}'.")
                except discord.Forbidden:
                    logger.error(f"Missing permissions to create channel '{channel_name}' in category '{category_name}'.")
                    return
                except Exception as e:
                    logger.error(f"Error creating channel '{channel_name}': {e}")
                    return

            # Find or create webhook for the destination channel
            webhooks = await destination_channel.webhooks()
            webhook = discord.utils.get(webhooks, name="Message Duplicator Webhook")
            if not webhook:
                try:
                    webhook = await destination_channel.create_webhook(name="Message Duplicator Webhook")
                    logger.info(f"Created webhook in channel '{destination_channel.name}'.")
                except discord.Forbidden:
                    logger.error(f"Missing permissions to create webhook in channel '{destination_channel.name}'.")
                    return
                except Exception as e:
                    logger.error(f"Error creating webhook: {e}")
                    return

            # Handle attachments
            files_to_send = []
            for attachment in message.attachments:
                try:
                    file = await attachment.to_file()
                    files_to_send.append(file)
                except Exception as e:
                    logger.error(f"Error downloading attachment {attachment.filename}: {e}")
                    # Decide how to handle download errors - skip attachment or the whole message?
                    # For now, we'll just log and skip this attachment.

            # Construct and send webhook payload
            payload = {
                "content": message.content,
                "username": message.author.display_name, # Use display_name (server nickname)
                "avatar_url": message.author.avatar.url if message.author.avatar else message.author.default_avatar.url,
                "embeds": [embed.to_dict() for embed in message.embeds]
            }

            try:
                async with aiohttp.ClientSession() as session:
                    if files_to_send:
                        await webhook.send(**payload, files=files_to_send)
                    else:
                        await webhook.send(**payload)
            except Exception as e:
                logger.error(f"Error sending message via webhook: {e}")
            finally:
                # Close the files after sending
                for file in files_to_send:
                    file.close()


async def setup(bot: commands.Bot):
    await bot.add_cog(ON_MESSAGE_V2(bot))
