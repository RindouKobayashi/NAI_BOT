import discord
from discord import app_commands
from discord.ext import commands
from settings import logger, AUTOCOMPLETE_DATA, uuid
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
import uuid
from core.viewhandler import VibeTransferView
from core.checking_params import check_params
import core.dict_annotation as da
from core.nai_vars import Nai_vars

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
        sampler=Nai_vars.samplers_choices,
        noise_schedule=Nai_vars.noise_schedule_choices,
        model=Nai_vars.models_choices,
        undesired_content_presets=Nai_vars.undesired_content_presets.presets_choices,
        smea=Nai_vars.smea_choices
    )
    @app_commands.describe(
        positive="Positive prompt for image generation",
        negative="Negative prompt for image generation",
        width=f"Image width in 64 step increments (default: {Nai_vars.width.default})",
        height=f"Image height in 64 step increments (default: {Nai_vars.height.default})",
        steps=f"Number of steps (default: {Nai_vars.steps.default})",
        cfg="CFG scale (default: 5.0)",
        sampler="Sampling method (default: k_euler)",
        noise_schedule="Noise schedule (default: native)",
        smea="SMEA and SMEA+DYN versions of samplers perform better at high res (default: None)",
        seed="Seed for generation (default: 0, random)",
        model="Model to use (default: nai-diffusion-3)",
        quality_toggle="Tags to increase quality, will be prepended to the prompt (default: True)",
        undesired_content_presets="Undesired content presets (default: Heavy)",
        prompt_conversion_toggle="Convert Auto1111 way of prompt to NovelAI way of prompt (default: False)",
        upscale="Upscale image by 4x. Only available for images up to 640x640 (default: False)",
        decrisper="Basically dynamic thresholding (default: False)",
        variety_plus="Enable guidance only after body been formed, improved diversity, saturation of samples. (default: False)",
        vibe_transfer_switch="Vibe transfer switch (default: False)",
        load_preset="Load a preset for NAI generation"
    )
    async def nai(self, interaction: discord.Interaction, 
                  positive: str, 
                  negative: str = None, 
                  width: int = None, 
                  height: int = None, 
                  steps: int = None, 
                  cfg: float = None, 
                  sampler: app_commands.Choice[str] = None, 
                  noise_schedule: app_commands.Choice[str] = None,
                  smea: app_commands.Choice[str] = None,
                  seed: int = None,
                  model: app_commands.Choice[str] = None,
                  quality_toggle: bool = None,
                  undesired_content_presets: app_commands.Choice[str] = None,
                  prompt_conversion_toggle: bool = None,
                  upscale: bool = None,
                  decrisper: bool = None,
                  variety_plus: bool = None,
                  vibe_transfer_switch: bool = None,
                  load_preset: str = None
                  ):
        logger.info(f"COMMAND 'NAI' USED BY: {interaction.user} ({interaction.user.id})")

        try:
            if interaction.guild_id not in settings.SERVER_WHITELIST and interaction.guild is not None:
                response = f"This command is not available in this server, contact <@125331697867816961> or use `/feedback` to request whitelist."
                response += f"\n-# This is done because people were using this command in server with NAI staff."
                await interaction.response.send_message(response, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())
                return
            await interaction.response.defer()
            
            await interaction.followup.send("Checking parameters...")

            # Load the preset if specified
            if load_preset:
                user_id = str(interaction.user.id)
                user_nai_presets_dir = settings.USER_NAI_PRESETS_DIR / f"{user_id}.json"

                if user_nai_presets_dir.exists():
                    with open(user_nai_presets_dir, "r") as f:
                        user_presets = json.load(f)
                        if load_preset in user_presets["presets"]:
                            message = await interaction.edit_original_response(content="Preset found, loading preset...")
                            preset_data = user_presets["presets"][load_preset]
                            # Overwrite the parameters with the preset data only if data is not provided
                            if not negative:
                                negative = preset_data["negative"]
                            if not width:
                                width = preset_data["width"]
                            if not height:
                                height = preset_data["height"]
                            if not steps:
                                steps = preset_data["steps"]
                            if not cfg:
                                cfg = preset_data["cfg"]
                            if not sampler:
                                sampler = preset_data["sampler"]
                            if not noise_schedule:
                                noise_schedule = preset_data["noise_schedule"]
                            if not smea:
                                smea = preset_data["smea"]
                            if not seed:
                                seed = preset_data["seed"]
                            if not model:
                                model = preset_data["model"]
                            if not quality_toggle:
                                quality_toggle = preset_data["quality_toggle"]
                            if not undesired_content_presets:
                                undesired_content_presets = preset_data["undesired_content_presets"]
                            if not prompt_conversion_toggle:
                                prompt_conversion_toggle = preset_data["prompt_conversion_toggle"]
                            if not upscale:
                                upscale = preset_data["upscale"]
                            if not decrisper:
                                decrisper = preset_data["decrisper"]
                            if not variety_plus:
                                variety_plus = preset_data["variety_plus"]
                            if not vibe_transfer_switch:
                                vibe_transfer_switch = preset_data["vibe_transfer_switch"]
                            await message.edit(content="Preset loaded successfully!")

            # Change none to default values
            if not negative:
                negative = None
            if not width:
                width = Nai_vars.width.default
            if not height:
                height = Nai_vars.height.default
            if not steps:
                steps = Nai_vars.steps.default
            if not cfg:
                cfg = Nai_vars.cfg.default
            if not sampler:
                sampler = "k_euler"
            if not noise_schedule:
                noise_schedule = "native"
            if not smea:
                smea = "None"
            if not seed:
                seed = 0
            if not model:
                model = "nai-diffusion-3"
            if not quality_toggle:
                quality_toggle = True
            if not undesired_content_presets:
                undesired_content_presets = "heavy"
            if not prompt_conversion_toggle:
                prompt_conversion_toggle = False
            if not upscale:
                upscale = False 
            if not decrisper:
                decrisper = False
            if not variety_plus:
                variety_plus = False
            if not vibe_transfer_switch:
                vibe_transfer_switch = False

            checking_params: da.Checking_Params = da.create_with_defaults(
                da.Checking_Params,
                positive=positive,
                negative=negative,
                width=width,
                height=height,
                steps=steps,
                cfg=cfg,
                sampler=sampler,
                noise_schedule=noise_schedule,
                smea=smea,
                seed=seed,
                model=model,
                quality_toggle=quality_toggle,
                undesired_content_presets=undesired_content_presets,
                prompt_conversion_toggle=prompt_conversion_toggle,
                upscale=upscale,
                dynamic_thresholding=decrisper,
                skip_cfg_above_sigma=variety_plus,
                vibe_transfer_switch=vibe_transfer_switch
            )

            checking_params = await check_params(checking_params, interaction)

            # Unpack the parameters   

            params: da.Params = da.create_with_defaults(
                da.Params,
                positive=checking_params["positive"],
                negative=checking_params["negative"],
                width=checking_params["width"],
                height=checking_params["height"],
                steps=checking_params["steps"],
                cfg=checking_params["cfg"],
                sampler=checking_params["sampler"],
                noise_schedule=checking_params["noise_schedule"],
                sm=checking_params["sm"],
                sm_dyn=checking_params["sm_dyn"],
                seed=checking_params["seed"],
                model=checking_params["model"],
                vibe_transfer_switch=checking_params["vibe_transfer_switch"],
                dynamic_thresholding=checking_params["dynamic_thresholding"],
                skip_cfg_above_sigma=checking_params["skip_cfg_above_sigma"],
                upscale=checking_params["upscale"],
            )

            message = await interaction.edit_original_response(content="Adding your request to the queue...")

            # Create a bundle_data that contains all the parameters
            bundle_data: da.BundleData = da.create_with_defaults(
                da.BundleData,
                type="txt2img",
                request_id=str(uuid.uuid4()),
                interaction=interaction,
                message=message,
                params=params,
                checking_params=checking_params,
            )
            
            # Add the request to the queue
            success = await nai_queue.add_to_queue(bundle_data)

            if not success:
                # The message has already been edited in the add_to_queue function
                return

        except Exception as e:
            logger.error(f"Error in NAI command: {str(e)}")
            #await interaction.edit_original_response(content=f"An error occurred while queueing the image generation. {str(e)}")
            pass

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
            app_commands.Choice(name=f"{prefix}{item}"[:100], value=f"{prefix}{item}"[:100])
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
            app_commands.Choice(name=f"{prefix}{item}"[:100], value=f"{prefix}{item}"[:100])
            for item in results
            if len(item) > 0  # Ensure item is not empty
        ]
        
        return valid_choices
    
    @nai.autocomplete('load_preset')
    async def nai_load_preset_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        user_id = str(interaction.user.id)
        user_nai_presets_dir = settings.USER_NAI_PRESETS_DIR / f"{user_id}.json"

        if not user_nai_presets_dir.exists():
            return []
        
        with open(user_nai_presets_dir, "r") as f:
            user_presets = json.load(f)

        results = [
            app_commands.Choice(name=preset_name, value=preset_name)
            for preset_name in user_presets["presets"]
            if preset_name.lower().startswith(current.lower())
        ]

        return results[:25]
    
    @app_commands.command(name="save_nai_preset", description="Save your custom NAI generation settings as a preset")
    @app_commands.choices(
        sampler=Nai_vars.samplers_choices,
        noise_schedule=Nai_vars.noise_schedule_choices,
        model=Nai_vars.models_choices,
        undesired_content_presets=Nai_vars.undesired_content_presets.presets_choices,
        smea=Nai_vars.smea_choices
    )
    @app_commands.describe(
        preset_name="Name of the preset",
        negative="Negative prompt for image generation",
        width=f"Image width in 64 step increments (default: {Nai_vars.width.default})",
        height=f"Image height in 64 step increments (default: {Nai_vars.height.default})",
        steps=f"Number of steps (default: {Nai_vars.steps.default})",
        cfg="CFG scale (default: 5.0)",
        sampler="Sampling method (default: k_euler)",
        noise_schedule="Noise schedule (default: native)",
        smea="SMEA and SMEA+DYN versions of samplers perform better at high res (default: None)",
        seed="Seed for generation (default: 0, random)",
        model="Model to use (default: nai-diffusion-3)",
        quality_toggle="Tags to increase quality, will be prepended to the prompt (default: True)",
        undesired_content_presets="Undesired content presets (default: Heavy)",
        prompt_conversion_toggle="Convert Auto1111 way of prompt to NovelAI way of prompt (default: False)",
        upscale="Upscale image by 4x. Only available for images up to 640x640 (default: False)",
        decrisper="Basically dynamic thresholding (default: False)",
        variety_plus="Enable guidance only after body been formed, improved diversity, saturation of samples. (default: False)",
        vibe_transfer_switch="Vibe transfer switch (default: False)",
    )
    async def save_nai_preset(self, interaction: discord.Interaction,
                              preset_name: str,
                              negative: str = None, 
                              width: int = Nai_vars.width.default, 
                              height: int = Nai_vars.height.default, 
                              steps: int = Nai_vars.steps.default, 
                              cfg: float = Nai_vars.cfg.default, 
                              sampler: app_commands.Choice[str] = "k_euler", 
                              noise_schedule: app_commands.Choice[str] = "native",
                              smea: app_commands.Choice[str] = "None",
                              seed: int = 0,
                              model: app_commands.Choice[str] = "nai-diffusion-3",
                              quality_toggle: bool = True,
                              undesired_content_presets: app_commands.Choice[str] = "heavy",
                              prompt_conversion_toggle: bool = False,
                              upscale: bool = False,
                              decrisper: bool = False,
                              variety_plus: bool = False,
                              vibe_transfer_switch: bool = False,
                              ):
        """Save your custom NAI generation settings as a preset"""
        logger.info(f"COMMAND 'SAVE_NAI_PRESET' USED BY: {interaction.user} ({interaction.user.id})")

        try:
            await interaction.response.defer(thinking=True)

            # Create user settings file path
            user_id = str(interaction.user.id)
            user_nai_presets_dir = settings.USER_NAI_PRESETS_DIR / f"{user_id}.json"

            # Load existing presets or create a new one
            if user_nai_presets_dir.exists():
                with open(user_nai_presets_dir, "r") as f:
                    user_presets = json.load(f)
            else:
                user_presets = {"presets": {}}

            # Create new preset
            preset_data = {
                "negative": negative,
                "width": width,
                "height": height,
                "steps": steps,
                "cfg": cfg,
                "sampler": sampler.value if isinstance(sampler, app_commands.Choice) else sampler,
                "noise_schedule": noise_schedule.value if isinstance(noise_schedule, app_commands.Choice) else noise_schedule,
                "smea": smea.value if isinstance(smea, app_commands.Choice) else smea,
                "seed": seed,
                "model": model.value if isinstance(model, app_commands.Choice) else model,
                "quality_toggle": quality_toggle,
                "undesired_content_presets": undesired_content_presets.value if isinstance(undesired_content_presets, app_commands.Choice) else undesired_content_presets,
                "prompt_conversion_toggle": prompt_conversion_toggle,
                "upscale": upscale,
                "decrisper": decrisper,
                "variety_plus": variety_plus,
                "vibe_transfer_switch": vibe_transfer_switch,
            }

            # Add/Update the preset
            user_presets["presets"][preset_name] = preset_data

            # Save to file
            with open(user_nai_presets_dir, "w") as f:
                json.dump(user_presets, f, indent=4)

            # Create embed for confirmation
            embed = discord.Embed(
                title="Preset saved successfully",
                description=f"Preset `{preset_name}` saved successfully.",
                color=discord.Color.green()
            )

            # Add fields for key-value pairs
            for key, value in preset_data.items():
                embed.add_field(name=key, value=value, inline=True)

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in NAI command: {str(e)}")
            await interaction.followup.send(f"❌ An error occurred while saving the preset. `{str(e)}`", ephemeral=True)

    @app_commands.command(name="view_nai_presets", description="View your saved NAI presets")
    async def view_nai_presets(self, interaction: discord.Interaction, preset_name: str):
        """View your saved NAI presets"""
        logger.info(f"COMMAND 'VIEW_NAI_PRESETS' USED BY: {interaction.user} ({interaction.user.id})")
        try:
            await interaction.response.defer(thinking=True)

            user_id = str(interaction.user.id)
            user_nai_presets_dir = settings.USER_NAI_PRESETS_DIR / f"{user_id}.json"

            embed = discord.Embed(
                title="Your NAI presets",
                color=discord.Color.blurple()
            )

            # Add fields for key-value pairs
            if user_nai_presets_dir.exists():
                with open(user_nai_presets_dir, "r") as f:
                    user_presets = json.load(f)

                if preset_name in user_presets["presets"]:
                    preset_data = user_presets["presets"][preset_name]
                    for key, value in preset_data.items():
                        embed.add_field(name=key, value=value, inline=True)

                    await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error in NAI command: {str(e)}")
            await interaction.followup.send(f"❌ An error occurred while viewing the preset. `{str(e)}`", ephemeral=True)



    @view_nai_presets.autocomplete('preset_name')
    async def view_nai_presets_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        user_id = str(interaction.user.id)
        user_nai_presets_dir = settings.USER_NAI_PRESETS_DIR / f"{user_id}.json"

        if not user_nai_presets_dir.exists():
            return []

        with open(user_nai_presets_dir, "r") as f:
            user_presets = json.load(f)

        results = [
            app_commands.Choice(name=preset_name, value=preset_name)
            for preset_name in user_presets["presets"]
            if preset_name.lower().startswith(current.lower())
        ]

        return results[:25]

    @app_commands.command(name="director_tools", description="Use director tools (for image up to 1024x1024)")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.choices(
        req_type=Nai_vars.director_tools.req_type_choice,
        emotion=Nai_vars.director_tools.emotions_choice,
        defry=Nai_vars.director_tools.defry_choice
    )
    @app_commands.describe(
        req_type="Request type",
        emotion="Emotion (only applicable to 'emotion' request type)",
        defry="Defry (only applicable to 'colorize' and 'emotion' request type, default: 0)",
        prompt="Optional prompt (only applicable to 'colorize' and 'emotion' request type)"
    )
    async def director_tools(self,
                             interaction: discord.Interaction,
                             req_type: app_commands.Choice[str],
                             image: discord.Attachment,
                             emotion: app_commands.Choice[str] = None,
                             defry: app_commands.Choice[str] = None,
                             prompt: str = ""
                             ):
        logger.info(f"COMMAND 'DIRECTOR_TOOLS' USED BY: {interaction.user} ({interaction.user.id})")
        await interaction.response.defer()
        try:
            # Check if the attachment is an image
            await interaction.followup.send("Checking parameters...")
            if not image.filename.lower().endswith((".png", ".jpg", ".jpeg", "webp")):
                raise ValueError("Only `PNG`, `JPG`, `JPEG`, and `WebP` files are suppored.")
            
            # Check if image is smaller than 1024x1024
            if image.height * image.width > 1024 * 1024:
                raise ValueError(f"Image must be smaller than `{1024*1024}`px (`1024`x`1024`px).")
            
            message = await interaction.edit_original_response(content="Adding your request to the queue...")
            
            # Create a bundle_data that contains the image and the request type
            bundle_data: da.BundleData = da.create_with_defaults(
                da.BundleData,
                type = "director_tools",
                request_id = str(uuid.uuid4()),
                interaction = interaction,
                message = message,
                director_tools_params = {
                    "width": image.width,
                    "height": image.height,
                    "image": image,
                    "req_type": req_type.value,
                    "prompt": prompt,
                    "defry": int(defry.value) if defry else 0,
                    "emotion": emotion.value if emotion else None
                }
            )
            
            # Add the request to the queue
            success = await nai_queue.add_to_queue(bundle_data)

            if not success:
                return
            
        except Exception as e:
            logger.error(f"Error processing 'DIRECTOR_TOOLS' command: {str(e)}")
            message = await interaction.edit_original_response(content=f"Error: {str(e)}",)
            await message.delete(delay=10)

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
                if attachment is not None and not attachment.filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                    raise ValueError("Only `PNG`, `JPG`, `JPEG` and `WebP` images are supported.")

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
    async def view_vibe_transfer(self, interaction: discord.Interaction, ephemeral: bool = True):
        logger.info(f"COMMAND 'VIEW_VIBE_TRANSFER' USED BY: {interaction.user} ({interaction.user.id})")
        await interaction.response.defer(ephemeral=ephemeral)
        pagination_view = VibeTransferView(interaction=interaction)
        await pagination_view.send()


async def setup(bot: commands.Bot):
    await bot.add_cog(NAI(bot))
    logger.info("COG LOADED: NAI - COG FILE: nai_cog.py")
