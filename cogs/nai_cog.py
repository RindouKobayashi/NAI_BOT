import discord
from discord import app_commands
from discord.ext import commands
from settings import logger, AUTOCOMPLETE_DATA
import base64
import io
import requests
import dotenv
import asyncio
from os import environ as env
import zipfile
from pathlib import Path
import settings
from core.queuehandler import nai_queue
import random
import json
from core.viewhandler import PaginationView

# Import utility functions
from core.nai_utils import prompt_to_nai, calculate_resolution



class NAI(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        if settings.NAI_API_TOKEN is not None:
            self.access_token = settings.NAI_API_TOKEN
        else:
            raise RuntimeError("Please ensure that NAI_ACCESS_TOKEN is set in your .env file.")
        
        self.output_dir = "nai_output"

    @app_commands.command(name="nai", description="Generate an image using NovelAI")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.choices(
        sampler=[
            app_commands.Choice(name="k_euler", value="k_euler"),
            app_commands.Choice(name="k_euler_ancestral", value="k_euler_ancestral"),
            app_commands.Choice(name="k_dpmpp_2s_ancestral", value="k_dpmpp_2s_ancestral"),
            app_commands.Choice(name="k_dpmpp_2m", value="k_dpmpp_2m"),
            app_commands.Choice(name="k_dpmpp_sde", value="k_dpmpp_sde"),
            app_commands.Choice(name="ddim", value="ddim"),
        ],
        model=[
            app_commands.Choice(name="nai-diffusion-3", value="nai-diffusion-3"),
            app_commands.Choice(name="nai-diffusion-2", value="nai-diffusion-2"),
            app_commands.Choice(name="nai-diffusion", value="nai-diffusion"),
            app_commands.Choice(name="safe-diffusion", value="safe-diffusion"),
            app_commands.Choice(name="nai-diffusion-furry", value="nai-diffusion-furry"),
            app_commands.Choice(name="nai-diffusion-furry-3", value="nai-diffusion-furry-3"),
        ],
        undesired_content_presets=[
            app_commands.Choice(name="Heavy", value="heavy"),
            app_commands.Choice(name="Light", value="light"),
            app_commands.Choice(name="Human_Focus", value="human_focus"),
            app_commands.Choice(name="None", value="none"),
        ]
    )
    @app_commands.describe(
        positive="Positive prompt for image generation",
        negative="Negative prompt for image generation",
        width="Image width (default: 832)",
        height="Image height (default: 1216)",
        steps="Number of steps (default: 28)",
        cfg="CFG scale (default: 5.0)",
        sampler="Sampling method (default: k_euler)",
        seed="Seed for generation (default: 0, random)",
        model="Model to use (default: nai-diffusion-3)",
        quality_toggle="Tags to increase qualityh will be prepended to the prompt (default: True)",
        undesired_content_presets="Undesired content presets (default: Heavy)",
        prompt_conversion_toggle="Convert Auto1111 way of prompt to NovelAI way of prompt (default: False)",
        vibe_transfer_switch="Vibe transfer switch (default: False)",
    )
    async def nai(self, interaction: discord.Interaction, 
                  positive: str, 
                  negative: str = None, 
                  width: int = 832, 
                  height: int = 1216, 
                  steps: int = 28, 
                  cfg: float = 5.0, 
                  sampler: app_commands.Choice[str] = "k_euler", 
                  seed: int = 0,
                  model: app_commands.Choice[str] = "nai-diffusion-3",
                  quality_toggle: bool = True,
                  undesired_content_presets: app_commands.Choice[str] = "heavy",
                  prompt_conversion_toggle: bool = False,
                  vibe_transfer_switch: bool = False,
                  ):
        logger.info(f"COMMAND 'NAI' USED BY: {interaction.user} ({interaction.user.id})")
        await interaction.response.defer()

        # Define min, max, step values
        min_cfg, max_cfg, cfg_step = 0.0, 10.0, 0.1

        try:

            await interaction.followup.send("Checking parameters...")

            # Check if command used in server 1024739383124963429
            if interaction.guild.id == settings.SERVER_ID:
                # Check if command used in channel 1261084844230705182
                if interaction.channel.id != settings.CHANNEL_ID:
                    raise ValueError(f"`Command can only be used in `<#{settings.CHANNEL_ID}>")

            # Process model
            if model != "nai-diffusion-3":
                model = model.value

            # Check pixel limit
            pixel_limit = 1024*1024 if model in ("nai-diffusion-2", "nai-diffusion-3", "nai-diffusion-furry-3") else 640*640
            if width*height > pixel_limit:
                raise ValueError(f"`Image resolution ({width}x{height}) exceeds the pixel limit ({pixel_limit}px).`")
            
            # Check steps limit
            if steps > 28:
                raise ValueError("`Steps must be less than or equal to 28.`")
            
            # Check seed
            if seed <= 0:
                seed = random.randint(0, 9999999999)

            # Enforce cfg constraints
            cfg = max(min_cfg, min(max_cfg, round(cfg / cfg_step) * cfg_step))

            width, height = calculate_resolution(width*height, (width, height))


            # Process sampler
            if sampler != "k_euler":
                sampler = sampler.value
            #logger.info(f"Sampler: {sampler}")

            # Process prompt and negative prompt with function prompt_to_nai if prompt_conversation_toggle is True
            if prompt_conversion_toggle:
                positive = prompt_to_nai(positive)
                if negative is not None:
                    negative = prompt_to_nai(negative)

            # Process prompt with tags
            if quality_toggle:
                positive = f"{positive}, best quality, amazing quality, very aesthetic, absurdres"

            # Process negative prompt with tags
            if undesired_content_presets == "heavy":
                undesired_content_presets = app_commands.Choice(name="Heavy", value="heavy")
            if undesired_content_presets != None:
                # Check if negative prompt is empty
                if negative is None:
                    negative = ""
                if undesired_content_presets.value == "heavy":
                    # Check model to see what tags to add
                    if model == "nai-diffusion-3":
                        negative = "lowres, {bad}, error, fewer, extra, missing, worst quality, jpeg artifacts, bad quality, watermark, unfinished, displeasing, chromatic aberration, signature, extra digits, artistic error, username, scan, [abstract]," + negative
                    elif model == "nai-diffusion-2":
                        negative = "lowres, bad, text, error, missing, extra, fewer, cropped, jpeg artifacts, worst quality, bad quality, watermark, displeasing, unfinished, chromatic aberration, scan, scan artifacts," + negative
                    elif model == "nai-diffusion-furry" or model == "nai-diffusion-furry-3":
                        negative = "{{worst quality}}, [displeasing], {unusual pupils}, guide lines, {{unfinished}}, {bad}, url, artist name, {{tall image}}, mosaic, {sketch page}, comic panel, impact (font), [dated], {logo}, ych, {what}, {where is your god now}, {distorted text}, repeated text, {floating head}, {1994}, {widescreen}, absolutely everyone, sequence, {compression artifacts}, hard translated, {cropped}, {commissioner name}, unknown text, high contrast," + negative
                elif undesired_content_presets.value == "light":
                    # Check model to see what tags to add
                    if model == "nai-diffusion-3" or model == "nai-diffusion-2":
                        negative = "lowres, jpeg artifacts, worst quality, watermark, blurry, very displeasing," + negative
                    elif model == "nai-diffusion-furry" or model == "nai-diffusion-furry-3":
                        negative = "{worst quality}, guide lines, unfinished, bad, url, tall image, widescreen, compression artifacts, unknown text," + negative
                elif undesired_content_presets.value == "human_focus":
                    # Check model to see what tags to add
                    if model == "nai-diffusion-3":
                        negative = "lowres, {bad}, error, fewer, extra, missing, worst quality, jpeg artifacts, bad quality, watermark, unfinished, displeasing, chromatic aberration, signature, extra digits, artistic error, username, scan, [abstract], bad anatomy, bad hands, @_@, mismatched pupils, heart-shaped pupils, glowing eyes," + negative
            
            params = {
                "positive": positive,
                "negative": negative,
                "width": width,
                "height": height,
                "steps": steps,
                "cfg": cfg,
                "sampler": sampler,
                "seed": seed,
                "model": model,
                "vibe_transfer_switch": vibe_transfer_switch,
            }

            
            # Add the request to the queue
            message = await interaction.edit_original_response(content="Adding your request to the queue...")
            success = await nai_queue.add_to_queue(interaction, params, message)

            if not success:
                # The message has already been edited in the add_to_queue function
                return

        except Exception as e:
            logger.error(f"Error in NAI command: {str(e)}")
            await interaction.edit_original_response(content=f"An error occurred while queueing the image generation. {str(e)}")

    @nai.autocomplete('positive')
    async def nai_positive_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        def search_current_term(query):
            terms = query.split(',')
            current_term = terms[-1].strip().lower()
            
            if not current_term:
                return []

            results = [
                tag for tag in AUTOCOMPLETE_DATA
                if tag.lower().startswith(current_term)
            ]

            return results[:25]  # Limit to 25 results as per Discord's limit

        results = await asyncio.to_thread(search_current_term, current)
        
        # Prepare the choices, including the parts of the query that are already typed
        prefix = ','.join(current.split(',')[:-1]).strip()
        if prefix:
            prefix += ', '
        
        valid_choices = [
            app_commands.Choice(name=f"{prefix}{item}"[:100], value=f"{prefix}{item}")
            for item in results
            if len(item) > 0  # Ensure item is not empty
        ]
        
        return valid_choices
    @nai.autocomplete('negative')
    async def nai_positive_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        def search_current_term(query):
            terms = query.split(',')
            current_term = terms[-1].strip().lower()
            
            if not current_term:
                return []

            results = [
                tag for tag in AUTOCOMPLETE_DATA
                if tag.lower().startswith(current_term)
            ]

            return results[:25]  # Limit to 25 results as per Discord's limit

        results = await asyncio.to_thread(search_current_term, current)
        
        # Prepare the choices, including the parts of the query that are already typed
        prefix = ','.join(current.split(',')[:-1]).strip()
        if prefix:
            prefix += ', '
        
        valid_choices = [
            app_commands.Choice(name=f"{prefix}{item}"[:100], value=f"{prefix}{item}")
            for item in results
            if len(item) > 0  # Ensure item is not empty
        ]
        
        return valid_choices
    

    @app_commands.command(name="vibe_transfer", description="Store reference images for vibe transfer with info and strength value")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.describe(
        image_1="Reference image 1",
        image_1_info_extracted="Extracted image 1 info",
        image_1_ref_strength="Reference image 1 strength",
        image_2="Reference image 2",
        image_2_info_extracted="Extracted image 2 info",
        image_2_ref_strength="Reference image 2 strength",
        image_3="Reference image 3",
        image_3_info_extracted="Extracted image 3 info",
        image_3_ref_strength="Reference image 3 strength",
        image_4="Reference image 4",
        image_4_info_extracted="Extracted image 4 info",
        image_4_ref_strength="Reference image 4 strength",
        image_5="Reference image 5",
        image_5_info_extracted="Extracted image 5 info",
        image_5_ref_strength="Reference image 5 strength",
    )
    async def vibe_trasnfer(self, interaction: discord.Interaction,
                            image_1: discord.Attachment,
                            image_1_info_extracted: float,
                            image_1_ref_strength: float,
                            image_2: discord.Attachment = None,
                            image_2_info_extracted: float = None,
                            image_2_ref_strength: float = None,
                            image_3: discord.Attachment = None,
                            image_3_info_extracted: float = None,
                            image_3_ref_strength: float = None,
                            image_4: discord.Attachment = None,
                            image_4_info_extracted: float = None,
                            image_4_ref_strength: float = None,
                            image_5: discord.Attachment = None,
                            image_5_info_extracted: float = None,
                            image_5_ref_strength: float = None,
                            ):
        logger.info(f"COMMAND 'VIBE_TRANSFER' USED BY: {interaction.user} ({interaction.user.id})")

        await interaction.response.defer(ephemeral=True)

        try:
            # Prepare lists of images and their corresponding info and strength values
            images = [image_1, image_2, image_3, image_4, image_5]
            infos = [image_1_info_extracted, image_2_info_extracted, image_3_info_extracted, image_4_info_extracted, image_5_info_extracted]
            strengths = [image_1_ref_strength, image_2_ref_strength, image_3_ref_strength, image_4_ref_strength, image_5_ref_strength]

            # Check values are between 0 and 1 for all strength values and info extracted values
            for info, strength in zip(infos, strengths):
                if info is not None and not 0 <= info <= 1:
                    raise ValueError("Info extracted value must be between 0 and 1.")
                if strength is not None and not 0 <= strength <= 1:
                    raise ValueError("Reference strength value must be between 0 and 1.")
                    
            # Check all attachments are valid images
            for attachment in images:
                if attachment is not None and not attachment.filename.lower().endswith((".png", ".jpg", ".jpeg")):
                    raise ValueError("Only PNG, JPG, and JPEG images are supported.")

            # Create a json file named their user ID storing in database
            user_id = str(interaction.user.id)
            user_file_path = f"{settings.USER_VIBE_TRANSFER_DIR}/{user_id}.json"

            json_data = []

            for image, info, strength in zip(images, infos, strengths):
                if image is not None:
                    image_bytes = await image.read()
                    image_string = base64.b64encode(image_bytes).decode("utf-8")
                    json_data.append({
                        "image": image_string,
                        "info_extracted": info,
                        "ref_strength": strength
                    })

            with open(user_file_path, "w") as f:
                json.dump(json_data, f, indent=4)

            await interaction.edit_original_response(content="Vibe transfer data saved successfully.")

        except Exception as e:
            logger.error(f"Error in NAI command: {str(e)}")
            await interaction.edit_original_response(content=f"An error occurred while processing the command. `{str(e)}`")

    @app_commands.command(name="view_vibe_transfer", description="View your saved vibe transfer data and edit them")
    @app_commands.allowed_installs(guilds=True, users=True)
    async def view_vibe_transfer(self, interaction: discord.Interaction):
        logger.info(f"COMMAND 'VIEW_VIBE_TRANSFER' USED BY: {interaction.user} ({interaction.user.id})")
        await interaction.response.defer()
        pagination_view = PaginationView(interaction=interaction)
        await pagination_view.send()
        

async def setup(bot: commands.Bot):
    await bot.add_cog(NAI(bot))
    logger.info("COG LOADED: NAI - COG FILE: nai_cog.py")
