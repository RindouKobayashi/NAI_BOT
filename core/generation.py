from pathlib import Path
import settings
import aiohttp
import json
import zipfile
import io
import base64
import asyncio
import uuid
from typing import AsyncGenerator
from PIL import Image as PILImage # Import Pillow Image
from enum import Enum

from settings import logger, NAI_API_TOKEN, random, STATS_DIR
from pathlib import Path
from datetime import datetime
from discord import Interaction, Message, File, AllowedMentions
from discord.ext import commands
import core.dict_annotation as da
from core.viewhandler import RemixView
from core.wd_tagger import predict
from core.nai_stats import (
    stats_manager, # Import the existing stats_manager instance
    NAIGenerationHistory,
    GenerationParameters,
    GenerationResult
)

class SSEEventType(Enum):
    """Enum for Server-Sent Event types."""
    INTERMEDIATE = "intermediate"
    FINAL = "final"
    ERROR = "error"

class SSEEvent:
    """Simple class to represent a Server-Sent Event from the stream."""
    def __init__(self, event_type: SSEEventType, data: dict, total_steps: int):
        self.event_type = event_type
        self.data = data
        self.image: PILImage.Image | None = None
        self.step: int | None = data.get("step_ix")
        self.total_steps: int | None = total_steps

        if "image" in data and data["image"] is not None:
            try:
                # The image data in the SSE stream is base64 encoded.
                self.image = PILImage.open(io.BytesIO(base64.b64decode(data["image"])))
            except Exception as e:
                logger.error(f"Failed to open image from SSE event: {e}")
                self.image = None

    def __repr__(self):
        return f"SSEEvent(event_type={self.event_type.value}, step={self.step})"


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
                return await response.read(), response.status
            except aiohttp.ClientResponseError as e:
                if e.status == 429:
                    logger.error("NovelAI API rate limit exceeded. (429)")
                    return None, e.status
                else:
                    logger.error(f"NovelAI API error: {e}")
                    return None, e.status

    @staticmethod
    async def generate_image_stream(session, access_token, prompt, model, action, parameters, total_steps) -> AsyncGenerator[SSEEvent, None]:
        """
        Connects to the NovelAI image generation streaming endpoint and yields SSEEvents.
        This version manually processes the stream to avoid buffer overflows with large image data.
        """
        data = {"input": prompt, "model": model, "action": action, "parameters": parameters}
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "text/event-stream"}
        
        async with session.post(f"{NovelAIAPI.BASE_URL}/ai/generate-image-stream", json=data, headers=headers) as response:
            response.raise_for_status()
            
            buffer = b""
            event_type = None
            async for chunk in response.content.iter_chunked(1024):
                buffer += chunk
                
                while b"\n\n" in buffer:
                    event_data, buffer = buffer.split(b"\n\n", 1)
                    event_lines = event_data.decode('utf-8').split('\n')
                    
                    for line in event_lines:
                        if line.startswith('event:'):
                            event_type = line[len('event:'):].strip()
                        elif line.startswith('data:'):
                            payload_str = line[len('data:'):].strip()
                            if event_type:
                                try:
                                    payload_json = json.loads(payload_str)
                                    sse_event_type = SSEEventType(event_type)
                                    yield SSEEvent(sse_event_type, payload_json, total_steps)
                                except (json.JSONDecodeError, ValueError) as e:
                                    logger.warning(f"Failed to parse SSE data or unknown event type '{event_type}': {e}")
                                finally:
                                    event_type = None

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
                    "skip_cfg_above_sigma": bundle_data['params']['skip_cfg_above_sigma'] if bundle_data['params']['skip_cfg_above_sigma'] else None,
                }

                if bundle_data['params']['model'] in ["nai-diffusion-4-full", "nai-diffusion-4-5-curated", "nai-diffusion-4-5-full"]:
                    nai_params["v4_prompt"] = {
                        "caption": {
                            "base_caption": bundle_data['params']['positive'],
                            "char_captions": [],
                        },
                        "use_coords": False,
                        "use_order": False,
                    }
                    nai_params["v4_negative_prompt"] = {
                        "caption": {
                            "base_caption": bundle_data['params']['negative'],
                            "char_captions": [],
                        },
                        "use_coords": False,
                        "use_order": False,
                    }
                    nai_params["legacy_v3_extend"] = False
                    if bundle_data['params']['noise_schedule'] == "native":
                        nai_params["noise_schedule"] = "karras"

                vibe_transfer_data = bundle_data['params'].get('vibe_transfer_data')
                if vibe_transfer_data:
                    nai_params['reference_image_multiple'] = []
                    nai_params['reference_information_extracted_multiple'] = []
                    nai_params['reference_strength_multiple'] = []

                    for entry in vibe_transfer_data:
                        nai_params['reference_image_multiple'].append(entry['image'])
                        nai_params['reference_information_extracted_multiple'].append(entry['info_extracted'])
                        nai_params['reference_strength_multiple'].append(entry['ref_strength'])
                
                message = await message.edit(content=f"<a:evilrv1:1269168240102215731> Generating image <a:evilrv1:1269168240102215731>\nModel: `{bundle_data['params']['model']}`")

                start_time = datetime.now()

                generation_params = GenerationParameters(
                    positive_prompt=bundle_data['params']['positive'],
                    negative_prompt=bundle_data['params']['negative'],
                    width=bundle_data['params']['width'],
                    height=bundle_data['params']['height'],
                    steps=bundle_data['params']['steps'],
                    cfg=bundle_data['params']['cfg'],
                    sampler=bundle_data['params']['sampler'],
                    noise_schedule=bundle_data['params']['noise_schedule'],
                    smea=bundle_data['params']['sm'] or bundle_data['params']['sm_dyn'],
                    seed=bundle_data['params']['seed'],
                    model=bundle_data['params']['model'],
                    quality_toggle=bundle_data['checking_params']['quality_toggle'],
                    undesired_content=bundle_data['params']['negative'],
                    prompt_conversion=bundle_data['checking_params']['prompt_conversion_toggle'],
                    upscale=bundle_data['params']['upscale'],
                    decrisper=bundle_data['params']['dynamic_thresholding'],
                    variety_plus=bundle_data['params']['skip_cfg_above_sigma'],
                    vibe_transfer_used=bool(vibe_transfer_data),
                    undesired_content_preset=bundle_data['checking_params']['undesired_content_presets']
                )

                final_image_bytes = None
                timelapse_frames = []

                if bundle_data.get('streaming', False):
                    message = await message.edit(content=f"<a:evilrv1:1269168240102215731> Generating image (Streaming) <a:evilrv1:1269168240102215731>\nModel: `{bundle_data['params']['model']}`")
                    
                    last_update_time = asyncio.get_event_loop().time()

                    async for event in NovelAIAPI.generate_image_stream(
                        session,
                        NAI_API_TOKEN,
                        bundle_data['params']['positive'],
                        bundle_data['params']['model'],
                        "generate",
                        parameters=nai_params,
                        total_steps=bundle_data['params']['steps']
                    ):
                        if event.event_type == SSEEventType.INTERMEDIATE and event.image:
                            timelapse_frames.append(event.image)
                            current_time = asyncio.get_event_loop().time()
                            if event.step is not None and (current_time - last_update_time) > 1.0:
                                try:
                                    img_byte_arr = io.BytesIO()
                                    event.image.save(img_byte_arr, format="PNG")
                                    img_byte_arr.seek(0)
                                    file = File(img_byte_arr, filename="preview.png")
                                    await message.edit(
                                        content=f"<a:evilrv1:1269168240102215731> Generating image (Streaming) <a:evilrv1:1269168240102215731>\nModel: `{bundle_data['params']['model']}`\nStep: {event.step}/{event.total_steps or '?'}",
                                        attachments=[file]
                                    )
                                    last_update_time = current_time
                                except Exception as e:
                                    logger.error(f"Failed to update message with intermediate step: {e}")

                        elif event.event_type == SSEEventType.FINAL and event.image:
                            timelapse_frames.append(event.image)
                            img_byte_arr = io.BytesIO()
                            event.image.save(img_byte_arr, format="PNG")
                            final_image_bytes = img_byte_arr.getvalue()
                            break

                        elif event.event_type == SSEEventType.ERROR:
                            error_msg = event.data.get("message", "Unknown streaming error")
                            logger.error(f"NovelAI streaming error: {error_msg}")
                            raise Exception(f"NovelAI Streaming Error: {error_msg}")

                    if final_image_bytes is None:
                         raise Exception("Streaming finished without providing a final image.")

                else:
                    zipped_bytes, status = await NovelAIAPI.generate_image(
                        session,
                        NAI_API_TOKEN,
                        bundle_data['params']['positive'],
                        bundle_data['params']['model'],
                        "generate",
                        parameters=nai_params
                    )
                    if status != 200:
                        error_messages = {
                            400: "Bad request - The request was invalid or cannot be otherwise served",
                            401: "Unauthorized - Invalid API token",
                            402: "Payment Required - Payment is required to access this resource",
                            403: "Forbidden - Access to the resource is forbidden",
                            404: "Not Found - The requested resource was not found",
                            429: "Rate Limit Exceeded - Please try again later",
                            500: "Internal Server Error - NovelAI service issue",
                            502: "Bad Gateway - NovelAI service temporarily down",
                            503: "Service Unavailable - NovelAI is currently unavailable",
                            504: "Gateway Timeout - NovelAI service timed out",
                        }
                        error_msg = error_messages.get(status, f"NovelAI API status code: {status}")
                        logger.error(f"NovelAI API returned status code {error_msg}")
                        raise Exception(f"NovelAI API Error: {error_msg}")

                    zipped = zipfile.ZipFile(io.BytesIO(zipped_bytes))
                    final_image_bytes = zipped.read(zipped.infolist()[0])

                image_base64 = base64.b64encode(final_image_bytes).decode("utf-8")

                if bundle_data['params']['upscale']:
                    upscaled_bytes = await NovelAIAPI.upscale(
                        session,
                        NAI_API_TOKEN,
                        image_base64,
                        bundle_data['params']['width'],
                        bundle_data['params']['height'],
                        4,
                    )
                    zipped_upscale = zipfile.ZipFile(io.BytesIO(upscaled_bytes))
                    final_image_bytes = zipped_upscale.read(zipped_upscale.infolist()[0])
                    
                file_path = f"nai_generated_{interaction.user.id}.png"
                output_dir = Path("nai_output")
                output_dir.mkdir(exist_ok=True)
                (output_dir / file_path).write_bytes(final_image_bytes)

                end_time = datetime.now()
                elapsed_time = round((end_time - start_time).total_seconds(), 2)

                reply_content = f"Seed: `{bundle_data['params']['seed']}` | Elapsed time: `{elapsed_time}s`"
                reply_content += f"\nBy: {interaction.user.mention}"

                files = []
                file_path_full = str(output_dir / file_path)
                file = File(file_path_full)
                files.append(file)

                if timelapse_frames:
                    timelapse_path = output_dir / f"timelapse_{interaction.user.id}.gif"
                    timelapse_frames[0].save(
                        timelapse_path,
                        save_all=True,
                        append_images=timelapse_frames[1:],
                        optimize=False,
                        duration=100,
                        loop=0
                    )
                    
                database_channel = bot.get_channel(settings.DATABASE_CHANNEL_ID)
                reply_content_db = reply_content
                
                # Update stats using the stats_manager
                generation_result = GenerationResult(
                    success=True,
                    error_message=None,
                    database_message_id=database_message.id if 'database_message' in locals() else None,
                    attempts_made=2 - bundle_data['number_of_tries']
                )

                generation_history = NAIGenerationHistory(
                    generation_id=request_id,
                    timestamp=datetime.now().isoformat(),
                    user_id=interaction.user.id,
                    generation_time=elapsed_time,
                    parameters=generation_params,
                    result=generation_result
                )
                if stats_manager.add_generation(generation_history):
                    stats_manager.save_data()

                if interaction.guild is None:
                    reply_content_db += f"\nChannel: {interaction.user.mention}'s DM"
                else:
                    interaction_channel_link = f"https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}"
                    reply_content_db += f"\nChannel: {interaction_channel_link}"
                
                # Re-open file for database send
                db_files = [File(file_path_full)]
                if settings.TO_DATABASE:
                    database_message = await database_channel.send(content=reply_content_db, files=db_files, allowed_mentions=AllowedMentions.none())
                else:
                    database_message = await database_channel.send(content=reply_content_db, files=db_files, allowed_mentions=AllowedMentions.none(), delete_after=20)
                
                attachment = database_message.attachments[0]
                image_url = attachment.url if attachment else None

                # Re-open file for final reply
                final_files = [File(file_path_full)]
                if timelapse_frames:
                    final_files.append(File(str(timelapse_path)))

                if interaction.guild_id == settings.ANIMEAI_SERVER and interaction.channel_id == settings.SFW_IMAGE_GEN_BOT_CHANNEL:
                    warning_message = f"<a:neuroKuru:1279864980795035783> Classifying image...\n-# If image is classified as NSFW, it will be forwarded to the NSFW channel.\n-# Want to skip classification? Use bot in {bot.get_channel(settings.IMAGE_GEN_BOT_CHANNEL).mention}"
                    message = await message.edit(content=warning_message, attachments=[])
                    
                    if image_url:
                        confidence_levels, highest_confidence_level, is_nsfw = predict(image_url)
                        if is_nsfw:
                            nsfw_channel = bot.get_channel(settings.IMAGE_GEN_BOT_CHANNEL)
                            forward_message = await nsfw_channel.send(content=f"{reply_content}\n[View Request]({message.jump_url})", files=final_files)
                            await forward_message.add_reaction("🗑️")
                            
                            reply_content += f"\nForwarded to {nsfw_channel.mention} due to `NSFW` content.\n[View Forwarded Message]({forward_message.jump_url})"
                            await message.edit(content=reply_content, attachments=[])
                            bundle_data['message'] = forward_message
                        else:
                            message = await message.edit(content=reply_content, attachments=final_files)
                            await message.add_reaction("🗑️")
                            await message.add_reaction("🔎")
                    else:
                        await message.edit(content="Error: Could not retrieve image URL for classification.", attachments=[])
                else:
                    message = await message.edit(content=reply_content, attachments=final_files)
                    await message.add_reaction("🗑️")
                    await message.add_reaction("🔎")
                
                forward_channel = bot.get_channel(settings.IMAGE_GEN_BOT_CHANNEL)
                settings.Globals.remix_views[request_id] = RemixView(bundle_data, forward_channel)
                await settings.Globals.remix_views[request_id].send()

                if interaction.channel.id == 1157817614245052446:
                    await message.add_reaction("🔎")
                    await message.add_reaction("🗑️")
                
                generation_result = GenerationResult(
                    success=True,
                    error_message=None,
                    database_message_id=database_message.id if 'database_message' in locals() else None,
                    attempts_made=2 - bundle_data['number_of_tries']
                )
                
                generation_history = NAIGenerationHistory(
                    generation_id=request_id,
                    timestamp=datetime.now().isoformat(),
                    user_id=interaction.user.id,
                    generation_time=elapsed_time,
                    parameters=generation_params,
                    result=generation_result
                )
                if stats_manager.add_generation(generation_history):
                    stats_manager.save_data()
                
                return True

        except Exception as e:
            logger.error(f"Error processing request: {str(e)}")

            if 'request_id' in locals() and 'generation_params' in locals() and 'interaction' in locals():
                generation_result = GenerationResult(
                    success=False,
                    error_message=str(e),
                    database_message_id=None,
                    attempts_made=2 - bundle_data.get('number_of_tries', 1)
                )

                generation_history = NAIGenerationHistory(
                    generation_id=request_id,
                    timestamp=datetime.now().isoformat(),
                    user_id=interaction.user.id,
                    generation_time=0.0,
                    parameters=generation_params,
                    result=generation_result
                )
                stats_manager.add_generation(generation_history)
                stats_manager.save_data()

            if bundle_data.get('number_of_tries', 0) > 0:
                reply_content = f"⚠️`{str(e)}`. Retrying in `10` seconds. (`{bundle_data['number_of_tries']}` tries left)"
                await message.edit(content=reply_content, attachments=[])
                await asyncio.sleep(10)
            else:
                reply_content = f"❌`{str(e)}`. Please try again later."
                await message.edit(content=reply_content, attachments=[])
                return False

# The process_director_tools function remains unchanged. Please include it in your final file.
# NOTE: The provided snippet for process_director_tools is correct and does not need changes.
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

                generation_params = GenerationParameters(
                    positive_prompt=bundle_data['director_tools_params']['prompt'],
                    negative_prompt=None,
                    width=bundle_data['director_tools_params']['width'],
                    height=bundle_data['director_tools_params']['height'],
                    steps=0,  # Director tools don't use these parameters
                    cfg=0.0,
                    sampler="",
                    noise_schedule="",
                    smea="",
                    seed=0,
                    model="director-tools",
                    quality_toggle=False,
                    undesired_content=bundle_data['director_tools_params']['prompt'], # Use the prompt for director tools
                    prompt_conversion=False,
                    upscale=False,
                    decrisper=False,
                    variety_plus=False,
                    vibe_transfer=False,
                    undesired_content_preset=None # Director tools don't have UC presets
                )

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
