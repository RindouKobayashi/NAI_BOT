import settings
import aiohttp
import json
import zipfile
import io
import base64
import asyncio
from settings import logger, NAI_API_TOKEN
from pathlib import Path
from datetime import datetime
from discord import Interaction, Message, File, AllowedMentions
from discord.ext import commands
import core.dict_annotation as da
from core.viewhandler import RemixView
from core.wd_tagger import predict

class NovelAIAPI:
    BASE_URL = "https://image.novelai.net"
    OTHER_URL = "https://api.novelai.net"

    @staticmethod
    async def generate_image(session, access_token, prompt, model, action, parameters):
        data = {"input": prompt, "model": model, "action": action, "parameters": parameters}
        headers = {"Authorization": f"Bearer {access_token}"}
        async with session.post(f"{NovelAIAPI.BASE_URL}/ai/generate-image", json=data, headers=headers) as response:
            try:
                response.raise_for_status()
                logger.info(f"NovelAI API response: {response.status}")
                return await response.read(), response.status
            except aiohttp.ClientResponseError as e:
                if e.status == 429:
                    # Try again in 10 seconds
                    logger.error("NovelAI API rate limit exceeded. (429)")
                    return None, e.status
                else:
                    logger.error(f"NovelAI API error: {e}")
                    return None, e.status

    @staticmethod
    async def director_tools(session, access_token, width, height, image, req_type, prompt: str = "", defry: int = 0):
        data = {
            "width": width,
            "height": height,
            "image": image,
            "prompt": prompt,
            "req_type": req_type,
            "defry": defry
        }
        headers = {"Authorization": f"Bearer {access_token}"}
        async with session.post(f"{NovelAIAPI.BASE_URL}/ai/augment-image", json=data, headers=headers) as response:
            response.raise_for_status()
            return await response.read()

    @staticmethod
    async def upscale(session, access_token, image_base64: str, width: int, height: int, scale: int):
        data = {"image": image_base64, "width": width, "height": height, "scale": scale}
        headers = {"Authorization": f"Bearer {access_token}"}
        async with session.post(f"{NovelAIAPI.OTHER_URL}/ai/upscale", json=data, headers=headers) as response:
            response.raise_for_status()
            return await response.read()

async def process_txt2img(bot: commands.Bot, bundle_data: da.BundleData):
    while bundle_data['number_of_tries'] >= 1:
        try:
            bundle_data['number_of_tries'] -= 1
            async with aiohttp.ClientSession() as session:

                request_id = bundle_data['request_id']
                interaction: Interaction = bundle_data['interaction']
                message: Message = bundle_data['message']
                
                nai_params = {
                    "width": bundle_data['params']['width'],
                    "height": bundle_data['params']['height'],
                    "n_samples": 1,
                    "seed": bundle_data['params']['seed'],
                    "sampler": bundle_data['params']['sampler'],
                    "steps": bundle_data['params']['steps'],
                    "scale": bundle_data['params']['cfg'],
                    "uncond_scale": 1.0,
                    "negative_prompt": bundle_data['params']['negative'],
                    "sm": bundle_data['params']['sm'],
                    "sm_dyn": bundle_data['params']['sm_dyn'],
                    "cfg_rescale": 0,
                    "noise_schedule": bundle_data['params']['noise_schedule'],
                    "legacy": False,
                    "dynamic_thresholding": bundle_data['params']['dynamic_thresholding'],
                }

                if bundle_data['params']['vibe_transfer_switch']:
                    # Extract image, info and strength value from user database
                    user_file_path = f"{settings.USER_VIBE_TRANSFER_DIR}/{interaction.user.id}.json"
                    nai_params['reference_image_multiple'] = []
                    nai_params['reference_information_extracted_multiple'] = []
                    nai_params['reference_strength_multiple'] = []

                    if Path(user_file_path).exists():
                        with open(user_file_path, "r") as user_file:
                            user_data = json.load(user_file)
                            for entry in user_data:
                                # Append image, info_extracted and ref_strength to nai_params
                                nai_params['reference_image_multiple'].append(entry['image'])
                                nai_params['reference_information_extracted_multiple'].append(entry['info_extracted'])
                                nai_params['reference_strength_multiple'].append(entry['ref_strength'])

                message = await message.edit(content=f"<a:evilrv1:1269168240102215731> Generating image <a:evilrv1:1269168240102215731>")

                # Start the timer
                start_time = datetime.now()

                # Call the NovelAI API
                zipped_bytes, status = await NovelAIAPI.generate_image(
                    session,
                    NAI_API_TOKEN,
                    bundle_data['params']['positive'],
                    bundle_data['params']['model'],
                    "generate",
                    parameters=nai_params
                )
                # Check the status
                if status != 200:
                    # Raise an exception if the status is not 200
                    raise Exception(f"NovelAI API returned status code {status}")

                # Process the response
                zipped = zipfile.ZipFile(io.BytesIO(zipped_bytes))
                image_bytes = zipped.read(zipped.infolist()[0])
                image_base64 = base64.b64encode(image_bytes).decode("utf-8")

                # Check if upscale is enabled
                if bundle_data['params']['upscale']:
                    image_bytes = await NovelAIAPI.upscale(
                        session,
                        NAI_API_TOKEN,
                        image_base64,
                        bundle_data['params']['width'],
                        bundle_data['params']['height'],
                        4,
                    )
                    zipped = zipfile.ZipFile(io.BytesIO(image_bytes))
                    image_bytes = zipped.read(zipped.infolist()[0])
                    
                # Save the image
                file_path = f"nai_generated_{interaction.user.id}.png"
                output_dir = Path("nai_output")
                output_dir.mkdir(exist_ok=True)
                (output_dir / file_path).write_bytes(image_bytes)

                # Stop the timer
                end_time = datetime.now()
                elapsed_time = end_time - start_time
                elapsed_time = round(elapsed_time.total_seconds(), 2)

                # Some information for the user
                reply_content = f"Seed: `{bundle_data['params']['seed']}` | Elapsed time: `{elapsed_time}s`"
                reply_content += f"\nBy: {interaction.user.mention}"

                # Prepare the image as a file
                files = []
                file_path = f"{output_dir}/{file_path}"
                file = File(file_path)
                files.append(file)

                # Forward the image to database if enabled
                # Database channel
                database_channel = bot.get_channel(settings.DATABASE_CHANNEL_ID)
                database_channel_2 = bot.get_channel(settings.DATABASE_CHANNEL_2_ID)
                reply_content_db = reply_content

                # Additional info for the database (adding channel of interaction if it's not dm)
                if interaction.guild is None:
                    # DM
                    # Copy reply_content to reply_content_db
                    reply_content_db += f"\nChannel: {interaction.user.mention}'s DM"
                else:
                    interaction_channel_link = f"https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}"
                    reply_content_db += f"\nChannel: {interaction_channel_link}"
                if settings.TO_DATABASE:
                    database_message = await database_channel.send(content=reply_content_db, files=files, allowed_mentions=AllowedMentions.none())
                else:
                    # Meaning testing, so delete message after 20 seconds
                    database_message = await database_channel.send(content=reply_content_db, files=files, allowed_mentions=AllowedMentions.none(), delete_after=20)
                # Forward to database 2
                # Reopen the file for actual posting
                file = File(file_path)
                files = [file]
                data_base_message_2 = await database_channel_2.send(content=reply_content_db, files=files, allowed_mentions=AllowedMentions.none())

                # Get image url from message
                attachment = database_message.attachments[0]
                if attachment is not None:
                    image_url = attachment.url

                # Reopen the file for actual posting
                file = File(file_path)
                files = [file]

                if interaction.guild_id == settings.ANIMEAI_SERVER: # If bot is in animeai server
                    if interaction.channel_id == settings.SFW_IMAGE_GEN_BOT_CHANNEL: # If channel is image gen bot channel (sfw)
                        warning_message = f"<a:neuroKuru:1279864980795035783> Classifying image <a:neuroKuru:1279864980795035783>"
                        warning_message += f"\n-# If image is classified as NSFW, it will be forwarded to the NSFW channel"
                        warning_message += f"\n-# Want to skip classification? Use bot in {bot.get_channel(settings.IMAGE_GEN_BOT_CHANNEL).mention}"
                        message = await message.edit(content=warning_message)
                        # Call predict function (TESTING)
                        confidence_levels, highest_confidence_level, is_nsfw = predict(image_url)
                        #for label, confidence in confidence_levels.items():
                        #    reply_content += f"\n{label}: {confidence:.2f}"
                        #reply_content += f"\n{confidence_levels}\n{highest_confidence_level}"

                        if is_nsfw:
                            channel = bot.get_channel(settings.IMAGE_GEN_BOT_CHANNEL) # Channel for image gen bot channel (nsfw)
                            forward_message = await channel.send(content=f"{reply_content}\n[View Request]({message.jump_url})", files=files)
                            # Edit message to include a link to the forwarded message
                            reply_content += f"\nForwarded to {channel.mention} due to `NSFW` content"
                            reply_content += f"\n[View Forwarded Message]({forward_message.jump_url})"
                            await message.edit(content=reply_content)
                            bundle_data['message'] = forward_message
                            # Add reaction to forward message
                            await forward_message.add_reaction("🗑️")
                            await forward_message.add_reaction("🔎")
                        else:
                            message = await message.edit(content=reply_content, attachments=files)
                            # Add reaction to message
                            await message.add_reaction("🗑️")
                            await message.add_reaction("🔎")

                    else:
                        await message.edit(content=reply_content, attachments=files)
                        # Add reaction to message
                        await message.add_reaction("🗑️")
                        await message.add_reaction("🔎")

                else:
                    message = await message.edit(content=reply_content, attachments=files)
                
                # Prepare RemixView
                settings.Globals.remix_views[request_id] = RemixView(bundle_data)
                await settings.Globals.remix_views[request_id].send()

                # Check if channel posted on is 1157817614245052446 then add reaction
                if interaction.channel.id == 1157817614245052446:
                    await message.add_reaction("🔎")
                    await message.add_reaction("🗑️")
                
                return True

        except Exception as e:
            logger.error(f"Error processing request: {str(e)}")
            if bundle_data['number_of_tries'] > 0:
                reply_content = f"An error occurred while processing your request. Retrying in `10` seconds. (`{bundle_data['number_of_tries']}` tries left)"
                await message.edit(content=reply_content)
                await asyncio.sleep(10)
                #await process_txt2img(bot, bundle_data)
            else:
                reply_content = f"An error occurred while processing your request. Please try again later."
                await message.edit(content=reply_content)
                return False

async def process_director_tools(bot: commands.Bot, bundle_data: da.BundleData):
    while bundle_data['number_of_tries'] >= 1:
        try:
            bundle_data['number_of_tries'] -= 1
            async with aiohttp.ClientSession() as session:
                if bundle_data["director_tools_params"]["req_type"] == "emotion":
                    bundle_data["director_tools_params"]["prompt"] = f"{bundle_data['director_tools_params']['emotion']};;{bundle_data['director_tools_params']['prompt']}"
                request_id = bundle_data['request_id']
                interaction: Interaction = bundle_data['interaction']
                message: Message = bundle_data['message']
                original_image = await bundle_data['director_tools_params']['image'].read()
                original_image_string = base64.b64encode(original_image).decode("utf-8")

                message = await message.edit(content="<a:evilrv1:1269168240102215731> Directing image <a:evilrv1:1269168240102215731>")

                # Start the timer
                start_time = datetime.now()

                # Call director tools API
                zipped_bytes = await NovelAIAPI.director_tools(
                    session,
                    NAI_API_TOKEN,
                    width=bundle_data['director_tools_params']['width'],
                    height=bundle_data['director_tools_params']['height'],
                    image=original_image_string,
                    req_type=bundle_data['director_tools_params']['req_type'],
                    prompt=bundle_data['director_tools_params']['prompt'],
                    defry=bundle_data['director_tools_params']['defry'],
                )

                # Process the response
                zipped = zipfile.ZipFile(io.BytesIO(zipped_bytes))
                image_bytes = zipped.read(zipped.infolist()[0])

                # Save the image
                file_path = f"director_tools_{interaction.user.id}.png"
                original_file_path = f"original_{file_path}"
                output_dir = Path("nai_output")
                output_dir.mkdir(exist_ok=True)
                (output_dir / file_path).write_bytes(image_bytes)
                (output_dir / original_file_path).write_bytes(original_image)

                # Stop the timer
                end_time = datetime.now()
                elapsed_time = end_time - start_time
                elapsed_time = round(elapsed_time.total_seconds(), 2)

                # Some information for the user
                reply_content = f"Request: `{bundle_data['director_tools_params']['req_type']}` | Elapsed time: `{elapsed_time}s`"
                reply_content += f"\nBy: {interaction.user.mention}"

                # Send the image
                files = []
                file_path = f"{output_dir}/{file_path}"
                original_file_path = f"{output_dir}/{original_file_path}"
                file = File(file_path)
                files.append(File(original_file_path))
                files.append(file)
                await message.edit(content=reply_content, attachments=files)

                # Forward the image to database if enabled
                if settings.TO_DATABASE:
                    # Database channel
                    database_channel = bot.get_channel(settings.DATABASE_CHANNEL_ID)

                    # Reopen the file for forwarding
                    files = []
                    file = File(file_path)
                    files.append(File(original_file_path))
                    files.append(file)

                    # Additional info for the database (adding channel of interaction)
                    interaction_channel_link = f"https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}"
                    reply_content += f"\nChannel: {interaction_channel_link}"
                    await database_channel.send(content=reply_content, files=files, allowed_mentions=AllowedMentions.none())

                # Check if channel posted on is IMAGE_GEN_BOT_CHANNEL then add reaction
                if interaction.channel.id == settings.IMAGE_GEN_BOT_CHANNEL:
                    await message.add_reaction("🗑️")

                return True
            
        except Exception as e:
            logger.error(f"Error processing request: {str(e)}")
            if bundle_data['number_of_tries'] > 0:
                reply_content = f"An error occurred while processing your request. Retrying in `10` seconds. (`{bundle_data['number_of_tries']}` tries left)"
                await message.edit(content=reply_content)
                await asyncio.sleep(10)
                await process_director_tools(bot, bundle_data)
            else:
                reply_content = f"An error occurred while processing your request. Please try again later."
                await message.edit(content=reply_content)
                return True