import discord
from discord import app_commands
from discord.ext import commands
from settings import logger, AUTOCOMPLETE_DATA, uuid
import base64
import io
import requests
import dotenv
import asyncio
import os # Import the os module
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
from core.nai_stats import stats_manager
import matplotlib
matplotlib.use('Agg')  # Use Agg backend to avoid needing GUI
import matplotlib.pyplot as plt
import io
from datetime import datetime, timezone # Import datetime and timezone here

# Import utility functions
from core.nai_utils import prompt_to_nai, calculate_resolution

# Common colors for embeds
BLUE = discord.Color.blue()
GREEN = discord.Color.green()
GOLD = discord.Color.gold()

class NAI(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        if settings.NAI_API_TOKEN is not None:
            self.access_token = settings.NAI_API_TOKEN
        else:
            raise RuntimeError("Please ensure that NAI_ACCESS_TOKEN is set in your .env file.")
        
        self.output_dir = "nai_output"
        self.leaderboard_opt_file = Path("database/leaderboard_opt_status.json")

        # Run vibe transfer data migration on cog load
        asyncio.create_task(self.migrate_vibe_transfer_data())

    async def migrate_vibe_transfer_data(self):
        """Migrate old vibe transfer data format to the new preset format."""
        #logger.info("Starting vibe transfer data migration...")
        user_vibe_transfer_dir = settings.USER_VIBE_TRANSFER_DIR
        os.makedirs(user_vibe_transfer_dir, exist_ok=True) # Ensure directory exists

        for filename in os.listdir(user_vibe_transfer_dir):
            if filename.endswith(".json"):
                user_file_path = os.path.join(user_vibe_transfer_dir, filename)
                user_id = filename[:-5] # Remove .json extension

                try:
                    with open(user_file_path, "r") as f:
                        user_data = json.load(f)

                    # Check if the data is in the old list format (not a dictionary with "presets")
                    if isinstance(user_data, list):
                        logger.info(f"Migrating old data format for user {user_id}")
                        # Wrap the old list data in the new preset structure
                        new_data = {"presets": {"Migrated Data": user_data}}

                        # Save the new data, overwriting the old file
                        with open(user_file_path, "w") as f:
                            json.dump(new_data, f, indent=4)
                        logger.info(f"Migration successful for user {user_id}")
                    elif isinstance(user_data, dict) and "presets" in user_data:
                        logger.debug(f"Data for user {user_id} is already in the new format. Skipping migration.")
                    else:
                        logger.debug(f"Unknown data format for user {user_id} in {filename}. Skipping migration.")

                except json.JSONDecodeError:
                    logger.error(f"Error decoding JSON from {filename}. Skipping migration for this file.")
                except Exception as e:
                    logger.error(f"Error during migration for user {user_id} ({filename}): {e}. Skipping this file.")

        #logger.info("Vibe transfer data migration complete.")


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
        load_preset="Load a preset for NAI generation",
        vibe_transfer_preset="Load a vibe transfer preset",
        streaming="Enable streaming image generation (default: False)" # Added streaming option
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
                  load_preset: str = None,
                  vibe_transfer_preset: str = None,
                  streaming: bool = False # Added streaming parameter
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
            if quality_toggle is None:
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
            if streaming is None: # Ensure streaming defaults to False if not provided
                streaming = False

            # Determine vibe_transfer_switch and load data based on vibe_transfer_preset
            vibe_transfer_switch = False
            vibe_transfer_data = None
            if vibe_transfer_preset:
                user_id = str(interaction.user.id)
                user_file_path = f"{settings.USER_VIBE_TRANSFER_DIR}/{user_id}.json"

                if os.path.exists(user_file_path):
                    try:
                        with open(user_file_path, "r") as f:
                            loaded_data = json.load(f)
                            if isinstance(loaded_data, dict) and "presets" in loaded_data and vibe_transfer_preset in loaded_data["presets"]:
                                vibe_transfer_data = loaded_data["presets"][vibe_transfer_preset]
                                vibe_transfer_switch = True # Enable switch if preset data is found
                            else:
                                await interaction.followup.send(f"Vibe transfer preset `{vibe_transfer_preset}` not found.", ephemeral=True)
                                return # Stop execution if preset not found
                    except json.JSONDecodeError:
                        logger.error(f"Error decoding JSON from {user_file_path} during NAI command. Cannot load preset.")
                        await interaction.followup.send(f"Error loading vibe transfer preset `{vibe_transfer_preset}`.", ephemeral=True)
                        return # Stop execution on error
                    except Exception as e:
                        logger.error(f"Error loading vibe transfer preset {vibe_transfer_preset} for user {user_id}: {e}.")
                        await interaction.followup.send(f"Error loading vibe transfer preset `{vibe_transfer_preset}`.", ephemeral=True)
                        return # Stop execution on error
                else:
                    await interaction.followup.send(f"Vibe transfer preset `{vibe_transfer_preset}` not found.", ephemeral=True)
                    return # Stop execution if file doesn't exist


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
                vibe_transfer_preset=vibe_transfer_preset,
                vibe_transfer_data=vibe_transfer_data,
                streaming=streaming # Pass streaming to checking_params
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
                dynamic_thresholding=checking_params["dynamic_thresholding"],
                skip_cfg_above_sigma=checking_params["skip_cfg_above_sigma"],
                upscale=checking_params["upscale"],
                vibe_transfer_preset=checking_params["vibe_transfer_preset"],
                vibe_transfer_data=checking_params["vibe_transfer_data"]
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
                streaming=checking_params["streaming"] # Pass streaming to bundle_data
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

    @nai.autocomplete('vibe_transfer_preset')
    async def nai_vibe_transfer_preset_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        user_id = str(interaction.user.id)
        user_file_path = f"{settings.USER_VIBE_TRANSFER_DIR}/{user_id}.json"

        if not os.path.exists(user_file_path):
            return []

        user_data = {"presets": {}}
        try:
            with open(user_file_path, "r") as f:
                loaded_data = json.load(f)
                if isinstance(loaded_data, dict) and "presets" in loaded_data:
                    user_data = loaded_data
                else:
                    # Fallback for old format if migration didn't run
                    user_data["presets"]["Migrated Data (Fallback)"] = loaded_data
        except json.JSONDecodeError:
            return []
        except Exception:
            return []

        results = [
            app_commands.Choice(name=preset_name, value=preset_name)
            for preset_name in user_data["presets"]
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

    @nai.autocomplete('vibe_transfer_preset')
    async def nai_vibe_transfer_preset_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        user_id = str(interaction.user.id)
        user_file_path = f"{settings.USER_VIBE_TRANSFER_DIR}/{user_id}.json"

        if not os.path.exists(user_file_path):
            return []

        user_data = {"presets": {}}
        try:
            with open(user_file_path, "r") as f:
                loaded_data = json.load(f)
                if isinstance(loaded_data, dict) and "presets" in loaded_data:
                    user_data = loaded_data
                else:
                    # Fallback for old format if migration didn't run
                    user_data["presets"]["Migrated Data (Fallback)"] = loaded_data
        except json.JSONDecodeError:
            return []
        except Exception:
            return []

        results = [
            app_commands.Choice(name=preset_name, value=preset_name)
            for preset_name in user_data["presets"]
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
    @app_commands.describe(
        preset_name="Name for this vibe transfer preset",
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
                            preset_name: str,
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

            # Ensure the directory exists
            os.makedirs(settings.USER_VIBE_TRANSFER_DIR, exist_ok=True)

            # Load existing data or create new structure
            user_data = {"presets": {}}
            if os.path.exists(user_file_path):
                try:
                    with open(user_file_path, "r") as f:
                        loaded_data = json.load(f)
                        # Check if the loaded data is in the new preset format
                        if isinstance(loaded_data, dict) and "presets" in loaded_data:
                            user_data = loaded_data
                        else:
                            # This case should ideally be handled by the migration logic on startup,
                            # but as a fallback, treat old format as a single preset.
                            logger.warning(f"Old vibe transfer data format detected for user {user_id}. Migration might not have run.")
                            user_data["presets"]["Migrated Data (Fallback)"] = loaded_data # Put old data under a fallback preset name
                except json.JSONDecodeError:
                    logger.error(f"Error decoding JSON from {user_file_path}. Starting with empty data.")
                    user_data = {"presets": {}}
                except Exception as e:
                    logger.error(f"Error loading vibe transfer data for user {user_id}: {e}. Starting with empty data.")
                    user_data = {"presets": {}}


            # Prepare the image data for the new preset
            preset_image_data = []
            for image, info, strength in zip(images, infos, strengths):
                if image is not None:
                    image_bytes = await image.read()
                    image_string = base64.b64encode(image_bytes).decode("utf-8")
                    preset_image_data.append({
                        "image": image_string,
                        "info_extracted": info,
                        "ref_strength": strength
                    })

            # Add/Update the preset with the new image data
            user_data["presets"][preset_name] = preset_image_data

            # Save to file
            with open(user_file_path, "w") as f:
                json.dump(user_data, f, indent=4)

            await interaction.edit_original_response(content=f"Vibe transfer data saved successfully under preset `{preset_name}`.")

        except ValueError as ve:
            logger.error(f"Error in VIBE_TRANSFER command (validation): {str(ve)}")
            await interaction.edit_original_response(content=f"❌ Parameter Error: `{str(ve)}`")
        except Exception as e:
            logger.error(f"Error in VIBE_TRANSFER command: {str(e)}")
            await interaction.edit_original_response(content=f"❌ An error occurred while processing the command. `{str(e)}`")

    @app_commands.command(name="view_vibe_transfer", description="View your saved vibe transfer data and edit them")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.describe(
        preset_name="The name of the preset to view (optional)",
        ephemeral="Whether the reply should be ephemeral (default: True)"
    )
    async def view_vibe_transfer(self, interaction: discord.Interaction, preset_name: str = None, ephemeral: bool = True):
        logger.info(f"COMMAND 'VIEW_VIBE_TRANSFER' USED BY: {interaction.user} ({interaction.user.id})")
        await interaction.response.defer(ephemeral=ephemeral)

        user_id = str(interaction.user.id)
        user_file_path = f"{settings.USER_VIBE_TRANSFER_DIR}/{user_id}.json"

        user_data = {"presets": {}}
        if os.path.exists(user_file_path):
            try:
                with open(user_file_path, "r") as f:
                    loaded_data = json.load(f)
                    if isinstance(loaded_data, dict) and "presets" in loaded_data:
                        user_data = loaded_data
                    else:
                         # Fallback for old format if migration didn't run
                         logger.warning(f"Old vibe transfer data format detected for user {user_id} during view. Migration might not have run.")
                         user_data["presets"]["Migrated Data (Fallback)"] = loaded_data
            except json.JSONDecodeError:
                logger.error(f"Error decoding JSON from {user_file_path} during view. No data loaded.")
                user_data = {"presets": {}}
            except Exception as e:
                logger.error(f"Error loading vibe transfer data for user {user_id} during view: {e}. No data loaded.")
                user_data = {"presets": {}}

        if not user_data["presets"]:
            await interaction.followup.send("You have no saved vibe transfer presets.", ephemeral=ephemeral)
            return

        # If a preset name is provided, check if it exists
        if preset_name and preset_name not in user_data["presets"]:
             await interaction.followup.send(f"Preset `{preset_name}` not found.", ephemeral=ephemeral)
             return

        # If no preset name is provided, default to the first one or "Migrated Data (Fallback)" if it exists
        if not preset_name:
            if "Migrated Data (Fallback)" in user_data["presets"]:
                preset_name = "Migrated Data (Fallback)"
            elif user_data["presets"]:
                preset_name = list(user_data["presets"].keys())[0]
            else:
                 # Should not happen if the check above passes, but for safety
                 await interaction.followup.send("You have no saved vibe transfer presets.", ephemeral=ephemeral)
                 return


        pagination_view = VibeTransferView(interaction=interaction, user_data=user_data, initial_preset_name=preset_name)
        await pagination_view.send()

    @view_vibe_transfer.autocomplete('preset_name')
    async def view_vibe_transfer_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        user_id = str(interaction.user.id)
        user_file_path = f"{settings.USER_VIBE_TRANSFER_DIR}/{user_id}.json"

        if not os.path.exists(user_file_path):
            return []

        user_data = {"presets": {}}
        try:
            with open(user_file_path, "r") as f:
                loaded_data = json.load(f)
                if isinstance(loaded_data, dict) and "presets" in loaded_data:
                    user_data = loaded_data
                else:
                    # Fallback for old format if migration didn't run
                    user_data["presets"]["Migrated Data (Fallback)"] = loaded_data
        except json.JSONDecodeError:
            return []
        except Exception:
            return []

        results = [
            app_commands.Choice(name=preset_name, value=preset_name)
            for preset_name in user_data["presets"]
            if preset_name.lower().startswith(current.lower())
        ]

        return results[:25]

    @app_commands.command(name="nai-stats", description="View your NAI generation statistics (Bot owner can view other users' stats)")
    @app_commands.describe(
        user="The user whose stats you want to view (Owner only)",
        ephemeral="Whether the reply should be ephemeral (default: False)"
    )
    async def nai_stats(self, interaction: discord.Interaction, user: discord.User = None, ephemeral: bool = False):
        """View detailed NAI generation statistics for a user"""
        logger.info(f"COMMAND 'NAI-STATS' USED BY: {interaction.user} ({interaction.user.id})")

        # Check if a user was specified and the interaction user is not the owner
        if user is not None and interaction.user.id != settings.BOT_OWNER_ID:
            await interaction.response.send_message("Only the bot owner can view other users' statistics.", ephemeral=True)
            return

        target_user = user or interaction.user
        
        await interaction.response.defer(ephemeral=ephemeral)
        
        # Get user stats
        user_stats = stats_manager.get_user_stats(target_user.id)
        if not user_stats or user_stats.total_generations == 0:
            await interaction.followup.send(f"No generation statistics found for {target_user.mention}!", ephemeral=ephemeral)
            return

        # Create main embed
        embed = discord.Embed(
            title=f"🎨 NAI Statistics for {target_user.name}",
            color=BLUE
        )
        
        # Basic stats
        success_rate = user_stats.successful_generations / user_stats.total_generations * 100
        avg_time = user_stats.total_generation_time / user_stats.total_generations
        
        # Generation stats
        embed.add_field(
            name="Generation Stats",
            value=f"Total Generations: `{user_stats.total_generations}`\n"
                  f"Successful Generations: `{user_stats.successful_generations}`\n"
                  f"Success Rate: `{success_rate:.1f}%`",
            inline=True
        )

        # Time stats
        first_gen_str = user_stats.first_generation
        last_gen_str = user_stats.last_generation

        display_first_gen = 'N/A'
        display_last_gen = 'N/A'

        if first_gen_str and last_gen_str:
            try:
                first_gen_date = datetime.fromisoformat(first_gen_str).astimezone(timezone.utc)
                last_gen_date = datetime.fromisoformat(last_gen_str).astimezone(timezone.utc)

                # Compare timezone-aware datetimes
                if first_gen_date <= last_gen_date:
                    display_first_gen = first_gen_str[:10]
                    display_last_gen = last_gen_str[:10]
                else:
                    # Dates are swapped, display them in chronological order
                    display_first_gen = last_gen_str[:10]
                    display_last_gen = first_gen_str[:10]
            except ValueError:
                # Handle invalid date format if necessary
                display_first_gen = f"Error: {first_gen_str[:10]}" if first_gen_str else 'N/A'
                display_last_gen = f"Error: {last_gen_str[:10]}" if last_gen_str else 'N/A'
        elif first_gen_str:
             display_first_gen = first_gen_str[:10]
        elif last_gen_str:
             display_last_gen = last_gen_str[:10]

        embed.add_field(
            name="Time Stats",
            value=f"Total Time: `{user_stats.total_generation_time:.1f}s`\n"
                  f"Average Time: `{avg_time:.1f}s`\n"
                  f"First Gen: `{display_first_gen}`\n"
                  f"Last Gen: `{display_last_gen}`",
            inline=True
        )

        # Most used models
        models = sorted(user_stats.models_used.items(), key=lambda x: x[1], reverse=True)[:3]
        embed.add_field(
            name="Top Models",
            value="\n".join(f"{model}: `{count}`" for model, count in models) or "No data",
            inline=True
        )
        
        # Most used sizes
        sizes = sorted(user_stats.most_used_sizes.items(), key=lambda x: x[1], reverse=True)[:5]
        embed.add_field(
            name="Top Sizes",
            value="\n".join(f"{size}: `{count}`" for size, count in sizes) or "No data",
            inline=True
        )
        
        # Most used samplers
        samplers = sorted(user_stats.samplers_used.items(), key=lambda x: x[1], reverse=True)[:3]
        embed.add_field(
            name="Top Samplers",
            value="\n".join(f"{str(sampler)}: `{count}`" for sampler, count in samplers) or "No data",
            inline=True
        )
        
        # Calculate most used UC preset
        most_used_preset = "N/A"
        if user_stats.preset_usage:
            try:
                most_used_preset = max(user_stats.preset_usage.items(), key=lambda item: item[1])[0]
            except ValueError: # Handle case where dict is empty but not None
                 most_used_preset = "N/A"


        # Calculate top user UC presets
        top_user_presets = sorted(user_stats.preset_usage.items(), key=lambda x: x[1], reverse=True)[:3]
        top_user_presets_str = "\n".join(f"{preset}: `{count}`" for preset, count in top_user_presets) or "No data"

        # Feature usage
        embed.add_field(
            name="Feature Usage",
            value=f"Upscale Count: `{user_stats.upscale_count}`\n"
                  f"Vibe Transfer Count: `{user_stats.vibe_transfer_count}`\n"
                  f"Quality Toggle Count: `{user_stats.quality_toggle_count}`\n"
                  f"Decrisper Count: `{user_stats.decrisper_count}`\n"
                  f"Variety Plus Count: `{user_stats.variety_plus_count}`\n"
                  f"Top UC Presets:\n{top_user_presets_str}",
            inline=True
        )

        # Create monthly activity graph
        if user_stats.monthly_usage:
            plt.figure(figsize=(10, 4))
            # Get months and sort them chronologically
            sorted_months_ym = sorted(user_stats.monthly_usage.keys())
            # Select the last 6 months
            months_to_plot_ym = sorted_months_ym[-6:]
            # Get counts for the selected months
            counts = [user_stats.monthly_usage[m] for m in months_to_plot_ym]
            
            # Format month strings to "Month Year"
            formatted_months = [datetime.strptime(m, "%Y-%m").strftime("%b %Y") for m in months_to_plot_ym]

            plt.bar(range(len(months_to_plot_ym)), counts)
            plt.xticks(range(len(months_to_plot_ym)), formatted_months, rotation=45, ha='right') # Rotate labels for readability
            plt.title("Monthly Activity")
            plt.xlabel("Month")
            plt.ylabel("Generations")
            plt.tight_layout() # Adjust layout to prevent labels overlapping

            # Save plot to bytes
            buf = io.BytesIO()
            plt.savefig(buf, format='png')
            buf.seek(0)
            plt.close()
            
            # Create file from bytes
            file = discord.File(buf, filename="activity.png")
            embed.set_image(url="attachment://activity.png")
            
            await interaction.followup.send(embed=embed, file=file, ephemeral=ephemeral)
        else:
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)

    @app_commands.command(name="nai-history", description="View your recent NAI generations (Still in testing)")
    @app_commands.describe(
        user="The user whose history you want to view (Owner only)",
        ephemeral="Whether the reply should be ephemeral (default: False)"
    )
    async def nai_history(self, interaction: discord.Interaction, user: discord.User = None, ephemeral: bool = False):
        """View recent generation history for a user"""
        logger.info(f"COMMAND 'NAI-HISTORY' USED BY: {interaction.user} ({interaction.user.id})")

        if interaction.user.id != settings.BOT_OWNER_ID:
            await interaction.response.send_message("This command is currently in testing and only available to the bot owner.", ephemeral=True)
            return

        target_user = user or interaction.user

        await interaction.response.defer(ephemeral=ephemeral)

        # Get user history
        history = stats_manager.get_user_history(target_user.id, limit=3)  # Last 3 generations
        if not history:
            await interaction.followup.send(f"No generation history found for {target_user.mention}!", ephemeral=ephemeral)
            return

        embed = discord.Embed(
            title=f"🎨 Recent Generations for {target_user.name}",
            color=BLUE
        )
        
        for i, gen in enumerate(history):
            status = "✅" if gen.result.success else "❌"
            params = gen.parameters
            
            # Construct the /nai command string
            command_str = f"/nai positive: \"{params.positive_prompt}\""
            if params.negative_prompt:
                command_str += f" negative: \"{params.negative_prompt}\""
            command_str += f" width: {params.width} height: {params.height} steps: {params.steps} cfg: {params.cfg}"
            command_str += f" sampler: {params.sampler} noise_schedule: {params.noise_schedule}"
            # Only include smea if it's a specific mode (not None)
            if params.smea in ["SMEA", "SMEA+DYN"]:
                 command_str += f" smea: {params.smea}"
            command_str += f" seed: {params.seed}"
            command_str += f" model: {params.model}"
            # Only include optional parameters if they are not their default values or are explicitly set
            if getattr(params, 'quality_toggle', True) is not True: # Safely access quality_toggle
                 command_str += f" quality_toggle: {getattr(params, 'quality_toggle', True)}"
            if getattr(params, 'undesired_content_preset', 'heavy') != 'heavy': # Safely access undesired_content_preset
                 command_str += f" undesired_content_presets: {getattr(params, 'undesired_content_preset', 'heavy')}"
            if getattr(params, 'prompt_conversion', False) is not False: # Safely access prompt_conversion
                 command_str += f" prompt_conversion_toggle: {getattr(params, 'prompt_conversion', False)}"
            if getattr(params, 'upscale', False) is not False: # Safely access upscale
                 command_str += f" upscale: {getattr(params, 'upscale', False)}"
            if getattr(params, 'decrisper', False) is not False: # Safely access decrisper (Dynamic Thresholding)
                 command_str += f" decrisper: {getattr(params, 'decrisper', False)}"
            if getattr(params, 'variety_plus', False) is not False: # Safely access variety_plus (Skip CFG Above Sigma)
                 command_str += f" variety_plus: {getattr(params, 'variety_plus', False)}"
            if getattr(params, 'vibe_transfer_preset', None): # Safely access vibe_transfer_preset
                 command_str += f" vibe_transfer_preset: \"{getattr(params, 'vibe_transfer_preset', None)}\""


            # Truncate prompts if too long for embed field value
            display_positive = params.positive_prompt # Use positive_prompt from GenerationParameters
            display_negative = params.negative_prompt or "N/A"
            max_prompt_length = 200 # Arbitrary limit to keep embed readable
            if len(display_positive) > max_prompt_length:
                display_positive = display_positive[:max_prompt_length] + "..."
            if len(display_negative) > max_prompt_length:
                display_negative = display_negative[:max_prompt_length] + "..."

            value = (
                f"Status: {status}\n"
                f"Time: `{gen.generation_time:.1f}s`\n"
                f"Prompt: ```{display_positive}```\n"
                f"Negative Prompt: ```{display_negative}```\n"
                f"Model: `{params.model}`\n"
                f"Size: `{params.width}x{params.height}`\n"
                f"Seed: `{params.seed}`\n"
                f"Sampler: `{params.sampler}`\n"
                f"Steps: `{params.steps}`\n"
                f"CFG: `{params.cfg}`\n"
                f"UC Preset: `{params.undesired_content_preset or 'N/A'}`\n" # Use undesired_content_preset from GenerationParameters
                f"Decrisper: `{getattr(params, 'decrisper', False)}`\n" # Safely access decrisper
                f"Variety Plus: `{getattr(params, 'variety_plus', False)}`" # Safely access variety_plus
            )
            
            # Add Vibe Transfer Preset if used
            vibe_transfer_preset_name = getattr(params, 'vibe_transfer_preset', None)
            if vibe_transfer_preset_name:
                 value += f"\nVibe Transfer Preset: `{vibe_transfer_preset_name}`"


            if gen.result.error_message:
                value += f"\nError: `{gen.result.error_message}`"

            # Truncate value if it exceeds Discord's embed field value limit (1024 characters)
            if len(value) > 1024:
                value = value[:1021] + "..."

            embed.add_field(
                name=f"Generation {len(history) - i} ({gen.timestamp[:19]})",  # Show up to seconds, number from most recent
                value=value,
                inline=False
            )
        
        await interaction.followup.send(embed=embed)

        # Send separate messages for the full command strings
        for i, gen in enumerate(history):
            params = gen.parameters
            
            # Construct the full /nai command string
            command_str = f"/nai positive: \"{params.positive_prompt}\""
            if params.negative_prompt:
                command_str += f" negative: \"{params.negative_prompt}\""
            command_str += f" width: {params.width} height: {params.height} steps: {params.steps} cfg: {params.cfg}"
            command_str += f" sampler: {params.sampler} noise_schedule: {params.noise_schedule}"
            if params.smea and params.smea != "None":
                 command_str += f" smea: {params.smea}"
            command_str += f" seed: {params.seed}"
            command_str += f" model: {params.model}"
            # Only include optional parameters if they are not their default values or are explicitly set
            if getattr(params, 'quality_toggle', True) is not True: # Safely access quality_toggle
                 command_str += f" quality_toggle: {getattr(params, 'quality_toggle', True)}"
            if getattr(params, 'undesired_content_preset', 'heavy') != 'heavy': # Safely access undesired_content_preset
                 command_str += f" undesired_content_presets: {getattr(params, 'undesired_content_preset', 'heavy')}"
            if getattr(params, 'prompt_conversion', False) is not False: # Safely access prompt_conversion
                 command_str += f" prompt_conversion_toggle: {getattr(params, 'prompt_conversion', False)}"
            if getattr(params, 'upscale', False) is not False: # Safely access upscale
                 command_str += f" upscale: {getattr(params, 'upscale', False)}"
            if getattr(params, 'decrisper', False) is not False: # Safely access decrisper
                 command_str += f" decrisper: {getattr(params, 'decrisper', False)}"
            if getattr(params, 'variety_plus', False) is not False: # Safely access variety_plus
                 command_str += f" variety_plus: {getattr(params, 'variety_plus', False)}"
            if getattr(params, 'vibe_transfer_preset', None): # Include preset name if used
                 command_str += f" vibe_transfer_preset: \"{getattr(params, 'vibe_transfer_preset', None)}\""


            await interaction.followup.send(f"Command for Generation {len(history) - i}:\n```{command_str}```", ephemeral=ephemeral)

    @app_commands.command(name="nai-leaderboard", description="View global NAI generation leaderboard")
    @app_commands.describe(
        ephemeral="Whether the reply should be ephemeral (default: False)"
    )
    async def nai_leaderboard(self, interaction: discord.Interaction, ephemeral: bool = False):
        """View global generation leaderboard"""
        logger.info(f"COMMAND 'NAI-LEADERBOARD' USED BY: {interaction.user} ({interaction.user.id})")

        await interaction.response.defer(ephemeral=ephemeral)

        # Get all user stats and sort by total generations
        all_user_stats = list(stats_manager.user_stats.values())
        sorted_users = sorted(all_user_stats, key=lambda x: x.total_generations, reverse=True)

        if not sorted_users:
            await interaction.followup.send("No user statistics available yet!", ephemeral=ephemeral)
            return

        # Find the invoking user's rank and stats
        invoking_user_id = interaction.user.id
        invoking_user_stats = None
        invoking_user_rank = -1 # -1 means not found

        for i, user_stats in enumerate(sorted_users):
            if user_stats.user_id == invoking_user_id:
                invoking_user_stats = user_stats
                invoking_user_rank = i + 1
                break

        # Read opt-in status
        opt_status = {}
        if self.leaderboard_opt_file.exists():
            try:
                with open(self.leaderboard_opt_file, "r") as f:
                    opt_status = json.load(f)
            except json.JSONDecodeError:
                logger.error(f"Error decoding JSON from {self.leaderboard_opt_file}. Proceeding with default (opt-out) for all.")
                opt_status = {}

        # Create main embed
        embed = discord.Embed(
            title="🏆 NAI Generation Leaderboard",
            color=GOLD
        )

        # --- Top 10 Section ---
        top_users = sorted_users[:10]
        leaderboard_value = ""
        if top_users:
            for i, user_stats in enumerate(top_users):
                user_id_str = str(user_stats.user_id)
                # Determine user display based on if it's the invoking user, or opt-in status
                user_display = "Anonymous User" # Default display for opted-out users
                if user_stats.user_id == invoking_user_id and not ephemeral and not opt_status.get(str(invoking_user_id), False):
                    user_display = "Anonymous User"
                elif user_stats.user_id == invoking_user_id:
                     user_display = interaction.user.mention
                elif opt_status.get(user_id_str, False): # Check if user opted in (default is False)
                     user_obj = self.bot.get_user(user_stats.user_id)
                     user_display = user_obj.mention if user_obj else f"<@{user_stats.user_id}>"


                leaderboard_value += f"**{i+1}. {user_display}** `{user_stats.total_generations}` generations\n"
        else:
            leaderboard_value = "No users in the leaderboard yet."

        embed.add_field(
            name="Top 10 Generators",
            value=leaderboard_value,
            inline=False
        )

        # --- Invoking User's Section ---
        user_section_value = ""
        # Only show "Your Stats" if ephemeral is True OR the invoking user is opted in OR is the bot owner
        invoking_user_id_str = str(invoking_user_id)
        if ephemeral or opt_status.get(invoking_user_id_str, False) or invoking_user_id == self.bot.owner_id:
            if invoking_user_stats:
                user_section_value += f"Your Rank: **#{invoking_user_rank}**\n"
                user_section_value += f"Your Generations: `{invoking_user_stats.total_generations}`\n"

                # Calculate generations needed for next rank
                if invoking_user_rank > 1:
                    next_rank_user_stats = sorted_users[invoking_user_rank - 2] # Rank is 1-based, index is 0-based
                    next_rank_user_id_str = str(next_rank_user_stats.user_id)
                    next_rank_user_display = "Anonymous User"
                    if next_rank_user_stats.user_id == invoking_user_id and not ephemeral and not opt_status.get(str(invoking_user_id), False):
                         next_rank_user_display = "Anonymous User"
                    elif next_rank_user_stats.user_id == invoking_user_id:
                         next_rank_user_display = interaction.user.mention
                    elif opt_status.get(next_rank_user_id_str, False): # Check if user opted in (default is False)
                         user_above_obj = self.bot.get_user(next_rank_user_stats.user_id)
                         next_rank_user_display = user_above_obj.mention if user_above_obj else f"<@{next_rank_user_stats.user_id}>"


                    gens_needed = next_rank_user_stats.total_generations - invoking_user_stats.total_generations
                    user_section_value += f"Generations needed for next rank (to surpass {next_rank_user_display}): `{gens_needed}`\n"
                else:
                    user_section_value += "You are currently Rank #1!\n"

                # Include users above and below if not in top 10
                if invoking_user_rank > 10:
                    user_section_value += "\nNearby Ranks:\n"
                    # User above (if exists)
                    if invoking_user_rank > 1:
                        user_above_stats = sorted_users[invoking_user_rank - 2]
                        user_above_id_str = str(user_above_stats.user_id)
                        user_above_display = "Anonymous User"
                        if user_above_stats.user_id == invoking_user_id and not ephemeral and not opt_status.get(str(invoking_user_id), False):
                             user_above_display = "Anonymous User"
                        elif user_above_stats.user_id == invoking_user_id:
                             user_above_display = interaction.user.mention
                        elif opt_status.get(user_above_id_str, False): # Check if user opted in (default is False)
                             user_above_obj = self.bot.get_user(user_above_stats.user_id)
                             user_above_display = user_above_obj.mention if user_above_obj else f"<@{user_above_stats.user_id}>"

                    user_section_value += f"**#{invoking_user_rank - 1}. {user_above_display}** `{invoking_user_stats.total_generations}` generations\n"

                    # Invoking user
                    invoking_user_display_nearby = interaction.user.mention
                    if not ephemeral and not opt_status.get(str(invoking_user_id), False):
                         invoking_user_display_nearby = "Anonymous User"
                    user_section_value += f"**#{invoking_user_rank}. {invoking_user_display_nearby}** `{invoking_user_stats.total_generations}` generations\n"

                    # User below (if exists)
                    if invoking_user_rank < len(sorted_users):
                        user_below_stats = sorted_users[invoking_user_rank]
                        user_below_id_str = str(user_below_stats.user_id)
                        user_below_display = "Anonymous User"
                        if user_below_stats.user_id == invoking_user_id and not ephemeral and not opt_status.get(str(invoking_user_id), False):
                             user_below_display = "Anonymous User"
                        elif user_below_stats.user_id == invoking_user_id:
                             user_below_display = interaction.user.mention
                        elif opt_status.get(user_below_id_str, False): # Check if user opted in (default is False)
                             user_below_obj = self.bot.get_user(user_below_stats.user_id)
                             user_below_display = user_below_obj.mention if user_below_obj else f"<@{user_below_stats.user_id}>"

                        user_section_value += f"**#{invoking_user_rank + 1}. {user_below_display}** `{user_below_stats.total_generations}` generations\n"

            else:
                user_section_value = "You have not generated any images yet to be on the leaderboard."

            embed.add_field(
                name=f"Your Stats ({interaction.user.name})",
                value=user_section_value,
                inline=False
            )


        # Add some overall global stats for context
        global_stats = stats_manager.get_global_stats()
        embed.add_field(
            name="Overall Stats",
            value=f"Total Generations (Global): `{global_stats.total_generations}`\n"
                  f"Total Users: `{global_stats.total_users}`",
            inline=False
        )

        # Add footer
        embed.set_footer(text="Use /nai-leaderboard-opt to control if your name is shown on the leaderboard.")

        await interaction.followup.send(embed=embed, allowed_mentions=discord.AllowedMentions.none(), ephemeral=ephemeral)

    @app_commands.command(name="nai-leaderboard-opt", description="Opt in or out of being shown on the global leaderboard")
    @app_commands.describe(
        opt_in="Whether to opt in (True) or opt out (False) of the leaderboard"
    )
    async def nai_leaderboard_opt(self, interaction: discord.Interaction, opt_in: bool):
        """Opt in or out of being shown on the global leaderboard"""
        logger.info(f"COMMAND 'NAI-LEADERBOARD-OPT' USED BY: {interaction.user} ({interaction.user.id})")

        await interaction.response.defer(ephemeral=True)

        user_id_str = str(interaction.user.id)
        opt_status = {}

        # Read existing status
        if self.leaderboard_opt_file.exists():
            try:
                with open(self.leaderboard_opt_file, "r") as f:
                    opt_status = json.load(f)
            except json.JSONDecodeError:
                logger.error(f"Error decoding JSON from {self.leaderboard_opt_file}. Starting with empty status.")
                opt_status = {}

        # Update user's status
        opt_status[user_id_str] = opt_in

        # Ensure directory exists
        self.leaderboard_opt_file.parent.mkdir(parents=True, exist_ok=True)

        # Write updated status
        try:
            with open(self.leaderboard_opt_file, "w") as f:
                json.dump(opt_status, f, indent=4)
            status_message = "opted in to" if opt_in else "opted out of"
            await interaction.followup.send(f"You have successfully {status_message} the global leaderboard.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error writing leaderboard opt status to file: {e}")
            await interaction.followup.send(f"An error occurred while updating your leaderboard opt status: {e}", ephemeral=True)


    @app_commands.command(name="nai-stats-debug", description="Debug NAI stats system")
    async def nai_stats_debug(self, interaction: discord.Interaction, user: discord.User = None):
        """Debug command to check NAI stats system"""
        logger.info(f"COMMAND 'NAI-STATS-DEBUG' USED BY: {interaction.user} ({interaction.user.id})")

        if interaction.user.id != settings.BOT_OWNER_ID:
            await interaction.response.send_message("This command is currently in testing and only available to the bot owner.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        debug_info = ["```\n=== NAI Stats Debug Report ==="]
        
        if user:
            debug_info.append(f"\n=== User Specific Integrity Check for User ID: {user.id} ===")
            user_stats = stats_manager.get_user_stats(user.id)
            
            if not user_stats or user_stats.total_generations == 0:
                debug_info.append(f"No generation statistics found for user ID {user.id}.")
            else:
                total_generations = user_stats.total_generations
                sum_models = sum(user_stats.models_used.values())
                sum_sizes = sum(user_stats.most_used_sizes.values())
                sum_samplers = sum(user_stats.samplers_used.values())
                
                debug_info.append(f"Total Generations: {total_generations}")
                debug_info.append(f"Sum of Models Used Counts: {sum_models}")
                debug_info.append(f"Sum of Sizes Used Counts: {sum_sizes}")
                debug_info.append(f"Sum of Samplers Used Counts: {sum_samplers}")
                
                issues_found = False
                if total_generations != sum_models:
                    debug_info.append(f"❌ Discrepancy: Total Generations ({total_generations}) != Sum of Models Used ({sum_models})")
                    issues_found = True
                if total_generations != sum_sizes:
                    debug_info.append(f"❌ Discrepancy: Total Generations ({total_generations}) != Sum of Sizes Used ({sum_sizes})")
                    issues_found = True
                if total_generations != sum_samplers:
                    debug_info.append(f"❌ Discrepancy: Total Generations ({total_generations}) != Sum of Samplers Used ({sum_samplers})")
                    issues_found = True
                    
                if not issues_found:
                    debug_info.append("✅ User specific counts match Total Generations.")
                    
        else:
            # Directory Structure Check
            debug_info.append("\n=== Directory Structure ===")
            for directory in [settings.STATS_DIR, settings.USER_STATS_DIR, settings.GLOBAL_STATS_DIR]:
                debug_info.append(f"\nDirectory: {directory}")
                debug_info.append(f"Exists: {directory.exists()}")
                if directory.exists():
                    try:
                        test_file = directory / ".test_write"
                        test_file.write_text("test")
                        test_file.unlink()
                        debug_info.append("Write permissions: ✅")
                    except Exception as e:
                        debug_info.append(f"Write permissions: ❌ ({str(e)})")
                    
                    debug_info.append("Contents:")
                    for item in directory.iterdir():
                        debug_info.append(f"- {item.name}")
                        if item.is_file() and item.suffix == '.json':
                            try:
                                with open(item, 'r') as f:
                                    data = json.load(f)
                                    data_size = len(str(data))
                                    debug_info.append(f"  Size: {data_size} chars")
                                    
                                    # Add specific data checks based on file type
                                    if item.name == "nai_history.json":
                                        debug_info.append(f"  History entries: {len(data)}")
                                        if data:
                                            latest = data[-1]
                                            debug_info.append(f"  Latest entry: {latest.get('timestamp', 'N/A')}")
                                    
                                    elif item.name == "nai_user_stats.json":
                                        user_count = len(data)
                                        total_gens = sum(d.get('total_generations', 0) for d in data.values())
                                        debug_info.append(f"  Users: {user_count}")
                                        debug_info.append(f"  Total generations: {total_gens}")
                                    
                                    elif item.name == "nai_global_stats.json":
                                        debug_info.append(f"  Total generations: {data.get('total_generations', 0)}")
                                        debug_info.append(f"  Total users: {data.get('total_users', 0)}")
                                        debug_info.append(f"  Active today: {data.get('active_users_today', 0)}")
                                    
                            except json.JSONDecodeError as je:
                                debug_info.append(f"  Error reading: ❌ Invalid JSON at position {je.pos}")
                            except Exception as e:
                                debug_info.append(f"  Error reading: ❌ {str(e)}")

            # Stats Manager State
            debug_info.append("\n=== Stats Manager State ===")
            debug_info.append(f"History entries: {len(stats_manager.history)}")
            debug_info.append(f"User stats entries: {len(stats_manager.user_stats)}")
            debug_info.append(f"Global total generations: {stats_manager.global_stats.total_generations}")
            
            # Data Integrity Check (Global)
            debug_info.append("\n=== Data Integrity Check (Global) ===")
            try:
                issues = stats_manager.verify_stats_integrity()
                any_issues = False
                for category, category_issues in issues.items():
                    if category_issues:
                        any_issues = True
                        debug_info.append(f"\n{category.title()} Issues:")
                        for issue in category_issues[:5]:  # Show only first 5 issues per category
                            debug_info.append(f"❌ {issue}")
                        if len(category_issues) > 5:
                            debug_info.append(f"... and {len(category_issues) - 5} more issues")
                
                if not any_issues:
                    debug_info.append("✅ No global integrity issues found")
            except Exception as e:
                debug_info.append(f"\n❌ Error during integrity check: {str(e)}")

        debug_info.append("```")  # Close code block
        
        # Send the report
        # Split into chunks if too long
        report = "\n".join(debug_info)
        if len(report) > 1990:  # Discord's limit is 2000, leave some room for ```
            chunks = []
            current_chunk = []
            current_length = 0
            
            for line in debug_info:
                if current_length + len(line) + 10 > 1990:  # +10 for ```\n and \n```
                    chunks.append("```\n" + "\n".join(current_chunk) + "\n```")
                    current_chunk = []
                    current_length = 0
                current_chunk.append(line)
                current_length += len(line) + 1  # +1 for newline
            
            if current_chunk:
                chunks.append("```\n" + "\n".join(current_chunk) + "\n```")
            
            for i, chunk in enumerate(chunks, 1):
                await interaction.followup.send(f"Debug Report (Part {i}/{len(chunks)}):\n{chunk}")
        else:
            await interaction.followup.send(report)



async def setup(bot: commands.Bot):
    await bot.add_cog(NAI(bot))
