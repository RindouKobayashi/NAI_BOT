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
                return await response.read()
            except aiohttp.ClientResponseError as e:
                if e.status == 429:
                    # Try again in 10 seconds
                    logger.error("NovelAI API rate limit exceeded. (429)")
                    return None
                    raise Exception(f"NovelAI API rate limit exceeded. (429)")
                else:
                    raise

    @staticmethod
    async def upscale(session, access_token, image_base64: str, width: int, height: int, scale: int):
        data = {"image": image_base64, "width": width, "height": height, "scale": scale}
        headers = {"Authorization": f"Bearer {access_token}"}
        async with session.post(f"{NovelAIAPI.OTHER_URL}/ai/upscale", json=data, headers=headers) as response:
            response.raise_for_status()
            return await response.read()

async def process_txt2img(bot: commands.Bot, bundle_data: da.BundleData):
    number_of_tries = 1
    while number_of_tries > 0:
        try:
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
                    "noise_schedule": "native",
                    "legacy": False,
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
                zipped_bytes = await NovelAIAPI.generate_image(
                    session,
                    NAI_API_TOKEN,
                    bundle_data['params']['positive'],
                    bundle_data['params']['model'],
                    "generate",
                    parameters=nai_params
                )

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

                # Send the image
                files = []
                file_path = f"{output_dir}/{file_path}"
                file = File(file_path)
                files.append(file)
                await message.edit(content=reply_content, attachments=files)

                # Prepare RemixView
                settings.Globals.remix_views[request_id] = RemixView(bundle_data)
                await settings.Globals.remix_views[request_id].send()

                # Forward the image to database if enabled
                if settings.TO_DATABASE:
                    # Database channel
                    database_channel = bot.get_channel(settings.DATABASE_CHANNEL_ID)

                    # Reopen the file for forwarding
                    file = File(file_path)
                    files = [file]

                    # Additional info for the database (adding channel of interaction)
                    interaction_channel_link = f"https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}"
                    reply_content += f"\nChannel: {interaction_channel_link}"
                    await database_channel.send(content=reply_content, files=files, allowed_mentions=AllowedMentions.none())

                # Check if channel posted on is 1157817614245052446 then add reaction
                if interaction.channel.id == 1157817614245052446:
                    await message.add_reaction("🔎")

                # Check if channel posted on is IMAGE_GEN_BOT_CHANNEL then add reaction
                if interaction.channel.id == settings.IMAGE_GEN_BOT_CHANNEL:
                    await message.add_reaction("🗑️")
                
                return True

        except Exception as e:
            logger.error(f"Error processing request: {str(e)}")
            if number_of_tries > 0:
                reply_content = f"An error occurred while processing your request. Retrying in `10` seconds. (`{number_of_tries}` tries left)"
                await message.edit(content=reply_content)
                number_of_tries -= 1
                await asyncio.sleep(10)
                await process_txt2img(bot, bundle_data)
            else:
                reply_content = f"An error occurred while processing your request. Please try again later."
                await message.edit(content=reply_content)