import settings
import random
from settings import logger
import discord
from discord import app_commands
from core.nai_utils import calculate_resolution, prompt_to_nai
from core.dict_annotation import Checking_Params
from core.nai_vars import Nai_vars


async def check_params(checking_params: Checking_Params, interaction: discord.Interaction):
        
        try:

            ### Check if command used in server ANIMEAI_SERVER
            if interaction.guild_id == settings.ANIMEAI_SERVER:
                # Check if command used in channel IMAGE_GEN_BOT_CHANNEL
                if interaction.channel_id != settings.IMAGE_GEN_BOT_CHANNEL and interaction.channel_id != settings.SFW_IMAGE_GEN_BOT_CHANNEL:
                    raise ValueError(f"`Command can only be used in `<#{settings.SFW_IMAGE_GEN_BOT_CHANNEL}> or <#{settings.IMAGE_GEN_BOT_CHANNEL}>")
                
            ### Process model
            if checking_params["model"] not in Nai_vars.models:
                checking_params["model"] = checking_params["model"].value

            ### Make width to be a multiple of 64
            if checking_params["width"] % Nai_vars.width.step != 0:
                checking_params["width"] = (checking_params["width"] // Nai_vars.width.step + 1) * Nai_vars.width.step

            ### Make height to be a multiple of 64
            if checking_params["height"] % Nai_vars.height.step != 0:
                checking_params["height"] = (checking_params["height"] // Nai_vars.height.step + 1) * Nai_vars.height.step
            
            ### Check pixel limit 
            pixel_limit = Nai_vars.pixel_limit(checking_params["model"]).pixel_limit
            if checking_params["width"] * checking_params["height"] > pixel_limit:
                raise ValueError(f"`Image resolution ({checking_params['width']}x{checking_params['height']}) exceeds the pixel limit ({pixel_limit}px).`")

            ### Check upscale
            if checking_params["upscale"] == True:
                # Check if width x height <= 640 x 640
                if checking_params["width"] * checking_params["height"] > Nai_vars.upscale_limit_pixels:
                    raise ValueError(f"`Image resolution ({checking_params['width']}x{checking_params['height']}) exceeds the pixel limit ({Nai_vars.upscale_limit_pixels}px) for upscaling.`")
            
            ### Check steps limit
            if checking_params["steps"] > Nai_vars.steps.max_value or checking_params["steps"] < Nai_vars.steps.min_value:
                raise ValueError(f"`Steps ({checking_params['steps']}) is out of range. Must be between {Nai_vars.steps.min_value} and {Nai_vars.steps.max_value}.`")
            
            ### Check seed
            if checking_params["seed"] > 9999999999 or checking_params["seed"] < 0:
                raise ValueError(f"`Seed ({checking_params['seed']}) is out of range. Must be between 0 and 9999999999.`")
            if checking_params["seed"] <= 0:
                checking_params["seed"] = random.randint(0, 9999999999)

            ### Ensure cfg is in step increments
            if checking_params["cfg"] % Nai_vars.cfg.step != 0:
                checking_params["cfg"] = (checking_params["cfg"] // Nai_vars.cfg.step + 1) * Nai_vars.cfg.step

            ### Check cfg
            if checking_params["cfg"] > Nai_vars.cfg.max_value or checking_params["cfg"] < Nai_vars.cfg.min_value:
                raise ValueError(f"`CFG scale ({checking_params['cfg']}) is out of range. Must be between {Nai_vars.cfg.min_value} and {Nai_vars.cfg.max_value}.`")
            
            ### Process sampler
            if checking_params["sampler"] not in Nai_vars.samplers:
                checking_params["sampler"] = checking_params["sampler"].value

            ### Process noise schedule
            if checking_params["noise_schedule"] not in Nai_vars.noise_schedule:
                checking_params["noise_schedule"] = checking_params["noise_schedule"].value

            ### Process smea
            if checking_params["smea"] not in ["SMEA", "SMEA+DYN", "None"]:
                checking_params["smea"] = checking_params["smea"].value
            if checking_params["smea"] == "SMEA":
                checking_params["sm"] = True
                checking_params["sm_dyn"] = False
            elif checking_params["smea"] == "SMEA+DYN":
                checking_params["sm"] = True
                checking_params["sm_dyn"] = True
            else:
                checking_params["sm"] = False
                checking_params["sm_dyn"] = False

            ### Process prompt and negative prompt with function prompt_to_nai if prompt_conversion_toggle is True
            if checking_params["prompt_conversion_toggle"]:
                checking_params["positive"] = prompt_to_nai(checking_params["positive"])
                if checking_params["negative"] is not None:
                    checking_params["negative"] = prompt_to_nai(checking_params["negative"])

            ### Process negative prompt with tags
            if checking_params["undesired_content_presets"] not in Nai_vars.undesired_content_presets(model=checking_params["model"]).types:
                checking_params["undesired_content_presets"] = checking_params["undesired_content_presets"].value
            
            ### Check if negative prompt is empty
            if checking_params["negative"] is None:
                checking_params["negative"] = ""
            else:
                if checking_params["negative"][-1] != ",":
                    checking_params["negative"] += ", "    
            
            #### Get other presets name instead of current
            #other_presets = Nai_vars.undesired_content_presets(model=checking_params["model"]).types
            #other_presets.remove(checking_params["undesired_content_presets"])
            #logger.info(other_presets)
            #### Check if negative prompt contains tags from other 3 presets
            #for preset in other_presets:
            #    if checking_params["negative"].find(Nai_vars.undesired_content_presets(model=checking_params["model"]).presets[preset]) != -1:
            #        checking_params["negative"] = checking_params["negative"].replace(Nai_vars.undesired_content_presets(model=checking_params["model"]).presets[preset], "")

            ### Prepend negative prompt with tags
            ### Check if negative prompt already contained undesired content presets tags
            if checking_params["negative"].find(Nai_vars.undesired_content_presets(model=checking_params["model"]).presets[checking_params["undesired_content_presets"]]) == -1: ## If not already contains
                #logger.info("FOUND: " + Nai_vars.undesired_content_presets(model=checking_params["model"]).presets[checking_params["undesired_content_presets"]])
                checking_params["negative"] = Nai_vars.undesired_content_presets(model=checking_params["model"]).presets[checking_params["undesired_content_presets"]] + checking_params["negative"] ## Add tags

            ### Check quality_toggle
            if checking_params["quality_toggle"] == True:
                ### Check if positive prompt already contained quality tags
                if checking_params["positive"].find(Nai_vars.quality_tags(model=checking_params["model"]).tags) == -1:
                    if Nai_vars.quality_tags(model=checking_params["model"]).add_way == "prepend":
                        checking_params["positive"] += Nai_vars.quality_tags(model=checking_params["model"]).tags
                    elif Nai_vars.quality_tags(model=checking_params["model"]).add_way == "append":
                        if checking_params["positive"][-1] != ",":
                            checking_params["positive"] += ", "
                        checking_params["positive"] += Nai_vars.quality_tags(model=checking_params["model"]).tags
            else:
                if checking_params["positive"].find(Nai_vars.quality_tags(model=checking_params["model"]).tags) != -1:
                    checking_params["positive"] = checking_params["positive"].replace(Nai_vars.quality_tags(model=checking_params["model"]).tags, "")
            return checking_params

        except Exception as e:
            logger.error(f"Error in check_params: {e}")
            await interaction.edit_original_response(content=f"{str(e)}")