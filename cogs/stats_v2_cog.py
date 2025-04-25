import discord
import json
from discord.ext import commands, tasks
from discord import app_commands
from settings import logger
import settings
import core.nai_stats as nai_stats_core
from core.nai_vars import Nai_vars # Import Nai_vars
from PIL import Image
import io
import uuid
from datetime import datetime
from typing import Optional, Union, Tuple # Import Union and Tuple for type hints
import re # Import regex module
from PIL.ExifTags import TAGS # Import TAGS for debugging metadata
import asyncio # Import asyncio for read_info_from_image_stealth and parallel processing
import gzip # Import gzip for read_info_from_image_stealth
from collections import OrderedDict # Import OrderedDict for read_attachment_metadata
import traceback # Import traceback for detailed error logging

# --- Helper functions for metadata extraction and parsing ---

def comfyui_get_data(dat):
    """Extract prompt/loras/checkpoints from comfy metadata"""
    try:
        aa = []
        # Ensure dat is a dictionary before iterating
        if not isinstance(dat, dict):
             logger.warning(f"comfyui_get_data received non-dict data: {type(dat)}")
             return []

        for _, value in dat.items():
            if isinstance(value, dict) and 'class_type' in value and 'inputs' in value:
                if value['class_type'] == "CLIPTextEncode" and 'text' in value['inputs']:
                    aa.append({"val": str(value['inputs']['text'])[:1023], # Ensure text is string
                            "type": "prompt"})
                elif value['class_type'] == "CheckpointLoaderSimple" and 'ckpt_name' in value['inputs']:
                    aa.append({"val": str(value['inputs']['ckpt_name'])[:1023], # Ensure ckpt_name is string
                            "type": "model"})
                elif value['class_type'] == "LoraLoader" and 'lora_name' in value['inputs']:
                    aa.append({"val": str(value['inputs']['lora_name'])[:1023], # Ensure lora_name is string
                            "type": "lora"})
        return aa
    except Exception as e: # Catch broader exceptions during processing
        logger.error(f"Error parsing ComfyUI data: {e}", exc_info=True)
        return []

async def read_info_from_image_stealth(image: Image.Image):
    """Read stealth PNGInfo"""
    width, height = image.size
    has_alpha = image.mode == "RGBA"
    mode = None
    compressed = False
    binary_data = []
    buffer_a = []
    buffer_rgb = []
    index_a = 0
    index_rgb = 0
    sig_confirmed = False
    confirming_signature = True
    reading_param_len = False
    reading_param = False
    read_end = False

    # Define the synchronous pixel processing logic
    def process_pixels_sync(img, has_alpha):
        pixels = img.load()
        local_buffer_a = []
        local_buffer_rgb = []
        local_index_a = 0
        local_index_rgb = 0
        local_sig_confirmed = False
        local_confirming_signature = True
        local_reading_param_len = False
        local_reading_param = False
        local_read_end = False
        local_mode = None
        local_compressed = False
        local_binary_data = []
        local_param_len = 0

        for x in range(img.size[0]):
            for y in range(img.size[1]):
                if has_alpha:
                    r, g, b, a = pixels[x, y]
                    local_buffer_a.append(str(a & 1))
                    local_index_a += 1
                else:
                    r, g, b = pixels[x, y]
                local_buffer_rgb.append(str(r & 1))
                local_buffer_rgb.append(str(g & 1))
                local_buffer_rgb.append(str(b & 1))
                local_index_rgb += 3

                if local_confirming_signature:
                    if local_index_a == len("stealth_pnginfo") * 8:
                        buffer_a_str = ''.join(local_buffer_a)
                        decoded_sig = bytearray(
                            int(buffer_a_str[i : i + 8], 2) for i in range(0, len(buffer_a_str), 8)
                        ).decode("utf-8", errors="ignore")
                        if decoded_sig in {"stealth_pnginfo", "stealth_pngcomp"}:
                            local_confirming_signature = False
                            local_sig_confirmed = True
                            local_reading_param_len = True
                            local_mode = "alpha"
                            if decoded_sig == "stealth_pngcomp":
                                local_compressed = True
                            local_buffer_a = []
                            local_index_a = 0
                        else:
                            local_read_end = True
                            break
                    elif local_index_rgb == len("stealth_pnginfo") * 8:
                        buffer_rgb_str = ''.join(local_buffer_rgb)
                        decoded_sig = bytearray(
                            int(buffer_rgb_str[i : i + 8], 2) for i in range(0, len(buffer_rgb_str), 8)
                        ).decode("utf-8", errors="ignore")
                        if decoded_sig in {"stealth_rgbinfo", "stealth_rgbcomp"}:
                            local_confirming_signature = False
                            local_sig_confirmed = True
                            local_reading_param_len = True
                            local_mode = "rgb"
                            if decoded_sig == "stealth_rgbcomp":
                                local_compressed = True
                            local_buffer_rgb = []
                            local_index_rgb = 0
                elif local_reading_param_len:
                    if local_mode == "alpha":
                        if local_index_a == 32:
                            local_param_len = int("".join(local_buffer_a), 2)
                            local_reading_param_len = False
                            local_reading_param = True
                            local_buffer_a = []
                            local_index_a = 0
                    else:
                        if local_index_rgb == 33:
                            pop = local_buffer_rgb.pop()
                            local_param_len = int("".join(local_buffer_rgb), 2)
                            local_reading_param_len = False
                            local_reading_param = True
                            local_buffer_rgb = [pop]
                            local_index_rgb = 1
                elif local_reading_param:
                    if local_mode == "alpha":
                        if local_index_a == local_param_len:
                            local_binary_data = local_buffer_a
                            local_read_end = True
                            break
                    else:
                        if local_index_rgb >= local_param_len:
                            diff = local_param_len - local_index_rgb
                            if diff < 0:
                                local_buffer_rgb = local_buffer_rgb[:diff]
                            local_binary_data = local_buffer_rgb
                            local_read_end = True
                            break
                else:
                    local_read_end = True
                    break
            if local_read_end:
                break

        return local_sig_confirmed, local_binary_data, local_compressed

    # Run the synchronous pixel processing in a separate thread
    sig_confirmed, binary_data, compressed = await asyncio.to_thread(process_pixels_sync, image, has_alpha)

    if sig_confirmed and binary_data:
        binary_data_str = ''.join(binary_data)
        byte_data = bytearray(int(binary_data_str[i : i + 8], 2) for i in range(0, len(binary_data_str), 8))
        try:
            if compressed:
                decoded_data = gzip.decompress(bytes(byte_data)).decode("utf-8")
            else:
                decoded_data = byte_data.decode("utf-8", errors="ignore")
            return decoded_data
        except Exception as e:
            logger.error(f"Error decompressing or decoding stealth data: {e}")
    return None

async def read_attachment_raw_metadata(attachment: discord.Attachment) -> Optional[str]:
    """Download and read raw image metadata from an attachment."""
    try:
        image_data = await attachment.read()

        # Use asyncio.to_thread for the synchronous Image.open operation
        def open_image_sync():
            return Image.open(io.BytesIO(image_data))

        # Run the synchronous image opening in a separate thread
        img = await asyncio.to_thread(open_image_sync)

        with img:
            if img.info:
                # Prioritize 'parameters', then 'prompt', then 'Comment'
                if 'parameters' in img.info:
                    return img.info['parameters']
                elif 'prompt' in img.info:
                    return img.info['prompt']
                elif 'Comment' in img.info:
                    return img.info["Comment"]
                else:
                    # Check for ComfyUI data if other standard tags not found
                    try:
                        # Attempt to parse img.info as JSON for ComfyUI
                        # Note: img.info is already a dictionary, no need to dump/load
                        comfy_data = comfyui_get_data(img.info)
                        if comfy_data:
                            # Return a string representation of ComfyUI data
                            return json.dumps(comfy_data, indent=2)
                    except Exception as e:
                         logger.debug(f"Could not parse img.info as ComfyUI data: {e}")
                         pass # Not ComfyUI data, continue

            # If no standard info or ComfyUI data, check for stealth info
            stealth_info = await read_info_from_image_stealth(img)
            if stealth_info:
                return stealth_info

    except Exception as error:
        logger.error(f"Error reading raw metadata for attachment {attachment.filename}: {type(error).__name__}: {error}", exc_info=True)
        return None

    return None # No metadata found by any method


def parse_metadata_to_params(raw_metadata: str) -> Optional[nai_stats_core.GenerationParameters]:
    """
    Parses raw metadata string into GenerationParameters dataclass.
    This function needs to handle different potential formats (NovelAI JSON, A1111 string, ComfyUI JSON).
    Based on the user's provided NovelAI JSON format.
    """
    try:
        metadata = json.loads(raw_metadata)
        # If json.loads succeeds, assume it's the expected NAI JSON format (or the content of the Comment key)
        # Map the extracted JSON data to the GenerationParameters dataclass
        params_data = {
            "positive_prompt": metadata.get("prompt", ""),
            "negative_prompt": metadata.get("uc", metadata.get("negative_prompt", "")), # Use 'uc' or 'negative_prompt'
            "width": metadata.get("width", 512),
            "height": metadata.get("height", 512),
            "steps": metadata.get("steps", 28),
            "cfg": metadata.get("scale", 7.0), # Use 'scale' from JSON for 'cfg'
            "sampler": metadata.get("sampler", "unknown"), # Default to "unknown" if not found
            "noise_schedule": metadata.get("noise_schedule", "unknown"), # Default to "unknown"
            "smea": "sm_dyn" if metadata.get("sm_dyn", False) else ("sm" if metadata.get("sm", False) else "off"), # Map sm/sm_dyn to smea string
            "seed": metadata.get("seed", 0),
            # Determine model based on v4_prompt presence
            "model": "nai-diffusion-4-full" if "v4_prompt" in metadata else "nai-diffusion-3",
            "quality_toggle": metadata.get("quality_toggle", False), # Default False
            "undesired_content": metadata.get("uc", ""), # Use 'uc' for undesired_content
            "prompt_conversion": metadata.get("prompt_conversion", False), # Default False
            "upscale": metadata.get("upscale", False), # Default False
            "decrisper": metadata.get("dynamic_thresholding", False), # Default False
            "variety_plus": metadata.get("variety_plus", False), # Default False
            "vibe_transfer": metadata.get("vibe_transfer", False), # Default False
            "undesired_content_preset": None # Initialize preset field
        }

        # Ensure all required fields are present, even if with default values
        required_fields = nai_stats_core.GenerationParameters.__dataclass_fields__.keys()
        for field_name in required_fields:
            if field_name == "undesired_content_preset":
                continue
            if field_name not in params_data:
                logger.warning(f"Missing expected metadata field: {field_name}")
                params_data[field_name] = None # Or a sensible default

        return nai_stats_core.GenerationParameters(**params_data)

    except json.JSONDecodeError:
        logger.debug("Metadata is not a valid JSON string for parsing into NAI parameters.")
        return None # Not a valid JSON string for this format
    except Exception as e:
        logger.error(f"Error parsing raw metadata string: {e}")
        return None


# --- End of helper functions ---

async def process_attachment_task(semaphore: asyncio.Semaphore, attachment: discord.Attachment, message: discord.Message, generating_user_id: int, elapsed_time: float) -> Tuple[int, int, int, int]:
    """Helper function to process a single attachment concurrently."""
    processed_count = 0
    processed_count = 0
    error_count = 0
    metadata_found_count = 0
    skipped_duplicates_count = 0
    processed_image_in_message = False # Flag to process only the first image

    async with semaphore:
        logger.debug(f"Checking attachment {attachment.id} with content type {attachment.content_type}")
        if attachment.content_type and attachment.content_type.startswith('image/'):
            if processed_image_in_message:
                logger.debug(f"Skipping additional image attachment {attachment.id} in message {message.id}")
                return processed_count, metadata_found_count, error_count, skipped_duplicates_count # Return counts without processing

            processed_image_in_message = True # Mark that we are processing the first image

            logger.debug(f"Attachment {attachment.id} is an image, attempting metadata extraction.")
            try:
                raw_metadata = await read_attachment_raw_metadata(attachment)

                if raw_metadata:
                    params = parse_metadata_to_params(raw_metadata)

                    if params:
                        metadata_found_count += 1
                        logger.debug(f"Metadata successfully parsed for image from message {message.id}. Params: {params}")

                        # Determine if it's vibe transfer, variety plus, or quality toggle based on the parsed JSON
                        # Note: This logic assumes raw_metadata is the JSON string itself, which is true if it came from the 'Comment' field
                        is_vibe_transfer = False
                        is_variety_plus = False
                        is_quality_toggle_on = False # Assume quality toggle is off by default
                        detected_undesired_content_preset = None # Initialize preset variable

                        parsed_metadata = None
                        try:
                            # Attempt to parse raw_metadata as JSON to extract additional flags
                            parsed_metadata = json.loads(raw_metadata)
                        except json.JSONDecodeError:
                            logger.debug(f"Raw metadata for message {message.id} is not valid JSON for flag extraction.")
                            # parsed_metadata remains None

                        if parsed_metadata and isinstance(parsed_metadata, dict):
                            # Check for Vibe Transfer
                            ref_strength = parsed_metadata.get("reference_strength_multiple")
                            if isinstance(ref_strength, list) and ref_strength: # Check if it's a non-empty list
                                is_vibe_transfer = True
                                logger.debug(f"Detected vibe transfer based on non-empty 'reference_strength_multiple' in JSON metadata for message {message.id}")
                            elif ref_strength is not None: # Log if the key exists but isn't a non-empty list
                                 logger.debug(f"'reference_strength_multiple' found but is not a non-empty list for message {message.id}. Value: {ref_strength}")

                            # Check for Variety Plus
                            skip_cfg = parsed_metadata.get("skip_cfg_above_sigma")
                            if skip_cfg is not None: # Check if the key exists and is not null
                                is_variety_plus = True
                                logger.debug(f"Detected variety plus based on non-null 'skip_cfg_above_sigma' in JSON metadata for message {message.id}. Value: {skip_cfg}")

                            # Check for Quality Toggle based on presence of quality tags in the prompt
                            prompt_text = parsed_metadata.get("prompt", "")
                            if prompt_text:
                                # Use the model determined during initial parsing
                                model_used = params.model
                                try:
                                    # Use Nai_vars from the import
                                    quality_tags_obj = Nai_vars.quality_tags(model=model_used)
                                    cleaned_prompt_text = prompt_text.strip()
                                    # Split the prompt text into a set of cleaned tags
                                    prompt_tags = set(tag.strip() for tag in cleaned_prompt_text.split(',') if tag.strip())
                                    # Split the quality tags into a set of cleaned tags
                                    quality_tags_set = set(tag.strip() for tag in quality_tags_obj.tags.split(',') if tag.strip())

                                    # Check if the set of quality tags is a subset of the prompt tags
                                    if quality_tags_set and quality_tags_set.issubset(prompt_tags): # Ensure quality tags set is not empty before checking subset
                                        is_quality_toggle_on = True
                                        logger.debug(f"Detected quality toggle based on tag set containment in prompt for message {message.id}")
                                except Exception as tag_e:
                                    logger.warning(f"Could not get quality tags for model {model_used} for message {message.id}: {tag_e}")

                            # Check for Undesired Content Preset
                            undesired_content_text = parsed_metadata.get("uc", "") # Get the raw UC text from metadata
                            if undesired_content_text:
                                # Use the model determined during initial parsing
                                model_used = params.model
                                try:
                                    # Use Nai_vars from the import
                                    uc_presets_obj = Nai_vars.undesired_content_presets(model=model_used)
                                    # Check for Undesired Content Preset by comparing sets of tags
                                    cleaned_uc_text = undesired_content_text.strip()
                                    # Split the raw UC text into a set of cleaned tags
                                    raw_uc_tags = set(tag.strip() for tag in cleaned_uc_text.split(',') if tag.strip())

                                    for preset_name, preset_value in uc_presets_obj.presets.items():
                                        cleaned_preset_value = preset_value.strip()
                                        # Split the preset value into a set of cleaned tags
                                        preset_tags = set(tag.strip() for tag in cleaned_preset_value.split(',') if tag.strip())

                                        # Check if the set of preset tags is a subset of the raw UC tags
                                        if preset_tags and preset_tags.issubset(raw_uc_tags): # Ensure preset tags is not empty before checking subset
                                            detected_undesired_content_preset = preset_name
                                            logger.debug(f"Detected undesired content preset '{preset_name}' based on tag set containment for message {message.id}")
                                            break # Found a match, no need to check other presets
                                except Exception as uc_e:
                                    logger.warning(f"Could not check undesired content presets for model {model_used} for message {message.id}: {uc_e}")


                        # Create a new GenerationParameters object with the correct values
                        # Use the successfully parsed params and update flags based on parsed_metadata
                        updated_params = nai_stats_core.GenerationParameters(
                            positive_prompt=params.positive_prompt,
                            negative_prompt=params.negative_prompt,
                            width=params.width,
                            height=params.height,
                            steps=params.steps,
                            cfg=params.cfg,
                            sampler=params.sampler,
                            noise_schedule=params.noise_schedule,
                            smea=params.smea,
                            seed=params.seed,
                            model=params.model,
                            quality_toggle=is_quality_toggle_on, # Set based on the check
                            undesired_content=params.undesired_content, # Keep the raw UC text from initial parse
                            undesired_content_preset=detected_undesired_content_preset, # Set the detected preset name
                            prompt_conversion=params.prompt_conversion,
                            upscale=params.upscale,
                            decrisper=params.decrisper,
                            variety_plus=is_variety_plus, # Set based on the check
                            vibe_transfer=is_vibe_transfer # Set based on the check
                        )

                        # Only create and add history entry if parameters were successfully parsed
                        history_entry = nai_stats_core.NAIGenerationHistory(
                            generation_id=str(uuid.uuid4()),
                            timestamp=message.created_at.isoformat(),
                            user_id=generating_user_id,
                            generation_time=elapsed_time,
                            parameters=updated_params,
                            result=nai_stats_core.GenerationResult(
                                success=True, # Mark as success since parameters were parsed
                                error_message=None,
                                database_message_id=message.id,
                                attempts_made=1 # Set attempts_made to 1 for historical entries
                            )
                        )

                        try:
                            # Access the stats_manager instance initialized in core.nai_stats
                            added_successfully = nai_stats_core.stats_manager.add_generation(history_entry)
                            if added_successfully:
                                processed_count += 1
                                logger.debug(f"Successfully added generation to stats for message {message.id}")
                            else:
                                skipped_duplicates_count += 1
                                logger.debug(f"Skipped duplicate generation for message {message.id}")
                        except Exception as stats_e:
                            logger.error(f"Error adding generation to stats manager for message {message.id}: {stats_e}")
                            error_count += 1
                    else:
                        # Parsing failed, log warning and increment error count, but do NOT create history entry
                        logger.warning(f"Raw metadata found but could not be parsed into NAI Generation Parameters for image from message {message.id}. Raw: {raw_metadata[:200]}...")
                        error_count += 1
                else:
                    # No raw metadata found, log warning and increment error count, but do NOT create history entry
                    logger.warning(f"No parsable raw metadata found in image from message {message.id}")
                    error_count += 1

            except Exception as img_e:
                logger.error(f"Error processing image attachment from message {message.id}: {img_e}")
                error_count += 1
        else:
            logger.debug(f"Attachment {attachment.id} is not an image, skipping.")

    return processed_count, metadata_found_count, error_count, skipped_duplicates_count


class StatsV2Cog(commands.Cog):
    """Handles processing historical NAI generations from Discord messages."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="process_history_v2", description="Process image attachments in a channel's history to update NAI stats. (Owner Only)")
    @app_commands.guild_only() # Make it a guild command
    @commands.is_owner() # Restrict this command to the bot owner
    async def process_history_v2(self, interaction: discord.Interaction, channel_id: str):
        """Processes image attachments in a channel's history to update NAI stats."""
        await interaction.response.send_message(f"Starting to process history for channel ID: {channel_id}...", ephemeral=True)

        try:
            channel = await self.bot.fetch_channel(int(channel_id))
        except (discord.NotFound, ValueError):
            await interaction.followup.send(f"Error: Could not find channel with ID {channel_id}.", ephemeral=True)
            return

        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
             await interaction.followup.send(f"Error: Channel ID {channel_id} is not a text channel or thread.", ephemeral=True)
             return

        processed_count = 0
        error_count = 0
        metadata_found_count = 0
        skipped_duplicates_count = 0 # Counter for skipped duplicates
        skipped_directortools_count = 0 # Counter for skipped directortools messages
        message_count = 0
        tasks = []
        semaphore = asyncio.Semaphore(100) # Limit to 100 concurrent tasks (increased for potential speedup)

        try:
            async for message in channel.history(limit=None):
                message_count += 1
                if message_count % 100 == 0: # Log every 100 messages
                    logger.info(f"Processing history in channel {channel_id}: Checked {message_count} messages so far.")
                    # Periodically process accumulated tasks to avoid excessive memory usage
                    if tasks:
                        results = await asyncio.gather(*tasks)
                        tasks = [] # Clear tasks after gathering
                        for p, m, e, s in results: # Unpack 4 values
                            processed_count += p
                            metadata_found_count += m
                            error_count += e
                            skipped_duplicates_count += s # Accumulate skipped count

                        # Periodically save data
                        try:
                            nai_stats_core.stats_manager.save_data()
                            logger.info(f"Periodically saved stats data after processing {message_count} messages.")
                        except Exception as save_e:
                            logger.error(f"Error during periodic save: {save_e}")


                if not message.author.bot:
                    logger.debug(f"Skipping non-bot message {message.id} from user {message.author.id}")
                    continue

                # Check if the message has exactly 2 attachments, indicating it might be from directortools
                if len(message.attachments) == 2:
                    logger.debug(f"Skipping message {message.id} with 2 attachments (potential directortools).")
                    skipped_directortools_count += 1
                    continue # Skip processing attachments for this message

                logger.debug(f"Processing bot message {message.id}")

                user_id_match = re.search(r"By: <@(\d+)>", message.content)
                if not user_id_match:
                    logger.warning(f"Skipping bot message {message.id}: Could not find 'By: <@USER_ID>' pattern in content.")
                    continue

                generating_user_id = int(user_id_match.group(1))
                logger.debug(f"Extracted generating user ID: {generating_user_id} from message {message.id}")

                elapsed_time = 0.0
                time_match = re.search(r"Elapsed time: `(\d+\.?\d*)s`", message.content)
                if time_match:
                    try:
                        elapsed_time = float(time_match.group(1))
                        logger.debug(f"Extracted elapsed time: {elapsed_time}s from message {message.id}")
                    except ValueError:
                        logger.warning(f"Could not convert elapsed time to float for message {message.id}. Found: {time_match.group(1)}")

                # Create tasks for processing attachments concurrently
                for attachment in message.attachments:
                    if attachment.content_type and attachment.content_type.startswith('image/'):
                        tasks.append(process_attachment_task(semaphore, attachment, message, generating_user_id, elapsed_time))

            # Process any remaining tasks after the loop finishes
            if tasks:
                results = await asyncio.gather(*tasks)
                for p, m, e, s in results: # Unpack 4 values
                    processed_count += p
                    metadata_found_count += m
                    error_count += e
                    skipped_duplicates_count += s # Accumulate skipped count

            # Final save after processing all messages
            try:
                nai_stats_core.stats_manager.save_data()
                logger.info("Final save of stats data after history processing.")
            except Exception as save_e:
                logger.error(f"Error during final save: {save_e}")


            logger.info(f"Finished iterating through {message_count} messages in channel {channel_id}.")
            # Send final summary message to the channel
            await channel.send(f"Finished processing history for channel ID: {channel_id}.")
            await channel.send(f"Summary: Checked {message_count} messages. Skipped {skipped_directortools_count} messages with 2 attachments. Processed {processed_count} images with metadata, found metadata in {metadata_found_count} images, encountered {error_count} errors, skipped {skipped_duplicates_count} duplicates.")

        except Exception as e:
            logger.error(f"An unexpected error occurred during history processing: {e}", exc_info=True)
            # Send error message to the channel
            await channel.send(f"An unexpected error occurred during history processing.")

    @app_commands.command(name="process_specific_messages", description="Process specific message IDs to update NAI stats, overwriting existing entries.")
    @app_commands.guild_only() # Make it a guild command
    @commands.is_owner() # Restrict this command to the bot owner
    async def process_specific_messages(self, interaction: discord.Interaction, channel_id: str, message_ids_str: str):
        """Processes specific message IDs to update NAI stats, overwriting existing entries."""
        await interaction.response.send_message(f"Starting to process specific message IDs in channel ID: {channel_id}...", ephemeral=True)

        try:
            channel = await self.bot.fetch_channel(int(channel_id))
        except (discord.NotFound, ValueError):
            await interaction.followup.send(f"Error: Could not find channel with ID {channel_id}.", ephemeral=True)
            return

        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
             await interaction.followup.send(f"Error: Channel ID {channel_id} is not a text channel or thread.", ephemeral=True)
             return

        message_ids = []
        try:
            # Parse comma-separated message IDs
            message_ids = [int(id.strip()) for id in message_ids_str.split(',') if id.strip()]
            if not message_ids:
                 await interaction.followup.send("Error: No valid message IDs provided.", ephemeral=True)
                 return
        except ValueError:
            await interaction.followup.send("Error: Invalid message ID format. Please provide a comma-separated list of numbers.", ephemeral=True)
            return

        processed_count = 0
        error_count = 0
        metadata_found_count = 0
        overwritten_count = 0 # Counter for overwritten entries
        failed_fetch_count = 0 # Counter for messages that couldn't be fetched
        skipped_directortools_count = 0 # Counter for skipped directortools messages

        semaphore = asyncio.Semaphore(20) # Limit concurrent message fetches/processing

        messages_to_process = []
        # Fetch messages concurrently
        async def fetch_message_task(sem: asyncio.Semaphore, channel: Union[discord.TextChannel, discord.Thread], message_id: int):
            async with sem:
                try:
                    message = await channel.fetch_message(message_id)
                    return message
                except (discord.NotFound, discord.Forbidden, discord.HTTPException) as e:
                    logger.warning(f"Could not fetch message {message_id}: {e}")
                    return None

        fetch_tasks = [fetch_message_task(semaphore, channel, msg_id) for msg_id in message_ids]
        fetched_messages = await asyncio.gather(*fetch_tasks)

        # Filter out failed fetches and process valid messages
        for message in fetched_messages:
            if message:
                messages_to_process.append(message)
            else:
                failed_fetch_count += 1

        # Process messages and their attachments concurrently
        async def process_single_message_task(sem: asyncio.Semaphore, message: discord.Message) -> Tuple[int, int, int, int, int]: # Added skipped_directortools_count to return tuple
            processed = 0
            metadata_found = 0
            errors = 0
            overwritten = 0
            skipped_directortools = 0 # Counter for this specific message task
            processed_image_in_message = False # Flag to process only the first image

            async with sem:
                logger.debug(f"Processing message {message.id}")

                # Check if the message has exactly 2 attachments, indicating it might be from directortools
                if len(message.attachments) == 2:
                    logger.debug(f"Skipping message {message.id} with 2 attachments (potential directortools).")
                    skipped_directortools = 1
                    return processed, metadata_found, errors, overwritten, skipped_directortools # Return immediately


                user_id_match = re.search(r"By: <@(\d+)>", message.content)
                if not user_id_match:
                    logger.warning(f"Skipping message {message.id}: Could not find 'By: <@USER_ID>' pattern in content.")
                    errors += 1
                    return processed, metadata_found, errors, overwritten, skipped_directortools # Return 5 values

                generating_user_id = int(user_id_match.group(1))
                logger.debug(f"Extracted generating user ID: {generating_user_id} from message {message.id}")

                elapsed_time = 0.0
                time_match = re.search(r"Elapsed time: `(\d+\.?\d*)s`", message.content)
                if time_match:
                    try:
                        elapsed_time = float(time_match.group(1))
                        logger.debug(f"Extracted elapsed time: {elapsed_time}s from message {message.id}")
                    except ValueError:
                        logger.warning(f"Could not convert elapsed time to float for message {message.id}. Found: {time_match.group(1)}")

                # Process attachments within this message
                for attachment in message.attachments:
                    if attachment.content_type and attachment.content_type.startswith('image/'):
                        if processed_image_in_message:
                            logger.debug(f"Skipping additional image attachment {attachment.id} in message {message.id}")
                            continue # Skip if we've already processed an image in this message

                        processed_image_in_message = True # Mark that we are processing the first image

                        logger.debug(f"Processing attachment {attachment.id} from message {message.id}")
                        try:
                            raw_metadata = await read_attachment_raw_metadata(attachment)

                            if raw_metadata:
                                logger.debug(f"Raw metadata extracted for message {message.id}: {raw_metadata[:500]}...") # Log raw metadata (truncated)
                                params = parse_metadata_to_params(raw_metadata)
                                logger.debug(f"Result of parse_metadata_to_params for message {message.id}: {params}")

                                if params:
                                    metadata_found += 1
                                    logger.debug(f"Metadata successfully parsed for image from message {message.id}. Params: {params}")

                                    # Determine additional flags from raw_metadata (assuming it's JSON)
                                    is_vibe_transfer = False
                                    is_variety_plus = False
                                    is_quality_toggle_on = False
                                    detected_undesired_content_preset = None

                                    parsed_metadata = None
                                    try:
                                        parsed_metadata = json.loads(raw_metadata)
                                    except json.JSONDecodeError:
                                        logger.debug(f"Raw metadata for message {message.id} is not valid JSON for flag extraction.")

                                    if parsed_metadata and isinstance(parsed_metadata, dict):
                                        ref_strength = parsed_metadata.get("reference_strength_multiple")
                                        if isinstance(ref_strength, list) and ref_strength:
                                            is_vibe_transfer = True
                                        skip_cfg = parsed_metadata.get("skip_cfg_above_sigma")
                                        if skip_cfg is not None:
                                            is_variety_plus = True
                                        prompt_text = parsed_metadata.get("prompt", "")
                                        if prompt_text:
                                            model_used = params.model
                                            try:
                                                quality_tags_obj = Nai_vars.quality_tags(model=model_used)
                                                cleaned_prompt_text = prompt_text.strip()
                                                prompt_tags = set(tag.strip() for tag in cleaned_prompt_text.split(',') if tag.strip())
                                                quality_tags_set = set(tag.strip() for tag in quality_tags_obj.tags.split(',') if tag.strip())
                                                if quality_tags_set and quality_tags_set.issubset(prompt_tags):
                                                    is_quality_toggle_on = True
                                            except Exception as tag_e:
                                                logger.warning(f"Could not get quality tags for model {model_used} for message {message.id}: {tag_e}")

                                        undesired_content_text = parsed_metadata.get("uc", "")
                                        if undesired_content_text:
                                            model_used = params.model
                                            try:
                                                uc_presets_obj = Nai_vars.undesired_content_presets(model=model_used)
                                                cleaned_uc_text = undesired_content_text.strip()
                                                raw_uc_tags = set(tag.strip() for tag in cleaned_uc_text.split(',') if tag.strip())
                                                for preset_name, preset_value in uc_presets_obj.presets.items():
                                                    cleaned_preset_value = preset_value.strip()
                                                    preset_tags = set(tag.strip() for tag in cleaned_preset_value.split(',') if tag.strip())
                                                    if preset_tags and preset_tags.issubset(raw_uc_tags):
                                                        detected_undesired_content_preset = preset_name
                                                        break
                                            except Exception as uc_e:
                                                logger.warning(f"Could not check undesired content presets for model {model_used} for message {message.id}: {uc_e}")


                                    updated_params = nai_stats_core.GenerationParameters(
                                        positive_prompt=params.positive_prompt,
                                        negative_prompt=params.negative_prompt,
                                        width=params.width,
                                        height=params.height,
                                        steps=params.steps,
                                        cfg=params.cfg,
                                        sampler=params.sampler,
                                        noise_schedule=params.noise_schedule,
                                        smea=params.smea,
                                        seed=params.seed,
                                        model=params.model,
                                        quality_toggle=is_quality_toggle_on,
                                        undesired_content=params.undesired_content,
                                        undesired_content_preset=detected_undesired_content_preset,
                                        prompt_conversion=params.prompt_conversion,
                                        upscale=params.upscale,
                                        decrisper=params.decrisper,
                                        variety_plus=is_variety_plus,
                                        vibe_transfer=is_vibe_transfer
                                    )

                                    history_entry = nai_stats_core.NAIGenerationHistory(
                                        generation_id=str(uuid.uuid4()), # Generate a new UUID for the history entry
                                        timestamp=message.created_at.isoformat(),
                                        user_id=generating_user_id,
                                        generation_time=elapsed_time,
                                        parameters=updated_params,
                                        result=nai_stats_core.GenerationResult(
                                            success=True,
                                            error_message=None,
                                            database_message_id=message.id,
                                            attempts_made=1
                                        )
                                    )

                                    # Add/Overwrite generation using the overwrite=True flag
                                    added_successfully = nai_stats_core.stats_manager.add_generation(history_entry, overwrite=True)
                                    if added_successfully:
                                        processed += 1
                                        # We don't track overwritten vs new adds here, just total processed
                                        logger.debug(f"Successfully added/overwritten generation for message {message.id}")
                                    else:
                                        # This case should ideally not be hit with overwrite=True unless there's another error
                                        logger.warning(f"Failed to add/overwrite generation for message {message.id} unexpectedly.")
                                        errors += 1

                                else:
                                    logger.warning(f"Raw metadata found but could not be parsed for message {message.id}. Raw: {raw_metadata[:200]}...")
                                    errors += 1
                            else:
                                logger.warning(f"No parsable raw metadata found in image from message {message.id}")
                                errors += 1

                        except Exception as img_e:
                            logger.error(f"Error processing image attachment from message {message.id}: {img_e}")
                            errors += 1
                    else:
                        logger.debug(f"Attachment {attachment.id} from message {message.id} is not an image, skipping.")

            return processed, metadata_found, errors, overwritten, skipped_directortools # Return 5 values

        process_tasks = [process_single_message_task(semaphore, msg) for msg in messages_to_process]
        processing_results = await asyncio.gather(*process_tasks)

        for p, m, e, o, s in processing_results: # Unpack 5 values
            processed_count += p
            metadata_found_count += m
            error_count += e
            overwritten_count += o # This counter isn't strictly needed with overwrite=True, but keep for consistency
            skipped_directortools_count += s # Accumulate skipped count

        # Save data after processing all specified messages
        try:
            nai_stats_core.stats_manager.save_data()
            logger.info("Final save of stats data after processing specific messages.")
        except Exception as save_e:
            logger.error(f"Error during final save after specific message processing: {save_e}")


        await interaction.followup.send(f"Finished processing specified messages in channel ID: {channel_id}.", ephemeral=True)
        await interaction.followup.send(f"Summary: Attempted to process {len(message_ids)} messages. Skipped {skipped_directortools_count} messages with 2 attachments. Successfully processed {processed_count} images with metadata, found metadata in {metadata_found_count} images, encountered {error_count} errors during processing, failed to fetch {failed_fetch_count} messages.", ephemeral=True)


    @app_commands.command(name="debug_metadata", description="Extracts and displays raw metadata from an image attachment in a message.")
    @app_commands.guild_only() # Make it a guild command
    @commands.is_owner() # Restrict this command to the bot owner
    async def debug_metadata(self, interaction: discord.Interaction, message_id: str, attachment_index: int = 0):
        """Debug command to extract and display raw image metadata."""
        await interaction.response.send_message(f"Attempting to extract metadata from message ID: {message_id}, attachment index: {attachment_index}...", ephemeral=True)

        try:
            # Fetch the message
            try:
                message = await interaction.channel.fetch_message(int(message_id))
            except (discord.NotFound, ValueError):
                await interaction.followup.send(f"Error: Could not find message with ID {message_id} in this channel.", ephemeral=True)
                return

            # Check for attachments and index validity
            if not message.attachments:
                await interaction.followup.send(f"Error: Message {message.id} has no attachments.", ephemeral=True)
                return
            if attachment_index < 0 or attachment_index >= len(message.attachments):
                await interaction.followup.send(f"Error: Invalid attachment index {attachment_index}. Message {message.id} has {len(message.attachments)} attachments.", ephemeral=True)
                return

            attachment = message.attachments[attachment_index]

            # Check if attachment is an image
            if not attachment.content_type or not attachment.content_type.startswith('image/'):
                await interaction.followup.send(f"Error: Attachment at index {attachment_index} is not an image (Content Type: {attachment.content_type}).", ephemeral=True)
                return

            # Use the robust raw metadata extraction function
            raw_metadata = await read_attachment_raw_metadata(attachment)

            if raw_metadata:
                metadata_output = "Raw Metadata:\n"
                # Attempt to pretty print if it's a JSON string
                try:
                    parsed_json = json.loads(raw_metadata)
                    metadata_output += "```json\n" + json.dumps(parsed_json, indent=2) + "\n```"
                except json.JSONDecodeError:
                    # If not JSON, just print the raw string
                    metadata_output += "```\n" + raw_metadata + "\n```"

                # Save the metadata to a file instead of sending to Discord
                file_path = "logs/metadata_debug.txt"
                try:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(metadata_output)
                    await interaction.followup.send(f"Raw metadata saved to `{file_path}`.", ephemeral=True)
                except Exception as file_error:
                    logger.error(f"Error saving metadata to file {file_path}: {file_error}", exc_info=True)
                    await interaction.followup.send(f"Error saving metadata to file.", ephemeral=True)

            else:
                await interaction.followup.send("No parsable raw metadata found in the image.", ephemeral=True)

        except Exception as e:
            logger.error(f"An unexpected error occurred during metadata debugging: {e}", exc_info=True)
            await interaction.followup.send(f"An unexpected error occurred.", ephemeral=True)


async def setup(bot: commands.Bot):
    """Adds the StatsV2Cog to the bot."""
    await bot.add_cog(StatsV2Cog(bot))
    # Sync commands to make slash commands available
    # Consider syncing to specific guilds during development
    await bot.tree.sync() # Sync globally or to specific guild(s)
