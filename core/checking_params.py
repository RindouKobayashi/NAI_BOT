import settings
import random
from settings import logger
import discord
from discord import app_commands
from core.nai_utils import calculate_resolution, prompt_to_nai
from core.dict_annotation import Checking_Params


async def check_params(checking_params: Checking_Params, interaction: discord.Interaction):
        
        try:

            # Check if command used in server ANIMEAI_SERVER
            if interaction.guild_id == settings.ANIMEAI_SERVER:
                # Check if command used in channel IMAGE_GEN_BOT_CHANNEL
                if interaction.channel_id != settings.IMAGE_GEN_BOT_CHANNEL:
                    raise ValueError(f"`Command can only be used in `<#{settings.IMAGE_GEN_BOT_CHANNEL}>")
                
            # Process model
            if checking_params["model"] != "nai-diffusion-3":
                checking_params["model"] = checking_params["model"].value

            # Check pixel limit
            pixel_limit = 1024*1024 if checking_params["model"] in ("nai-diffusion-2", "nai-diffusion-3", "nai-diffusion-furry-3") else 640*640
            if checking_params["width"] * checking_params["height"] > pixel_limit:
                raise ValueError(f"`Image resolution ({checking_params['width']}x{checking_params['height']}) exceeds the pixel limit ({pixel_limit}px).`")

            # Check upscale
            if checking_params["upscale"] == True:
                # Check if width x height <= 640 x 640
                if checking_params["width"] * checking_params["height"] > 640 * 640:
                    raise ValueError(f"`Image resolution ({checking_params['width']}x{checking_params['height']}) exceeds the pixel limit (640x640) for upscaling.`")
            
            # Check steps limit
            if checking_params["steps"] > 28:
                raise ValueError(f"`Steps ({checking_params['steps']}) exceeds the steps limit (28).`")
            
            # Check seed
            if checking_params["seed"] <= 0:
                checking_params["seed"] = random.randint(0, 9999999999)

            # Enforce cfg constraint
            min_cfg, max_cfg, cfg_step = 0.0, 10.0, 0.1
            checking_params["cfg"] = max(min_cfg, min(max_cfg, round(checking_params["cfg"] / cfg_step) * cfg_step))
            
            checking_params["width"], checking_params["height"] = calculate_resolution(checking_params["width"]*checking_params["height"], (checking_params["width"], checking_params["height"]))

            # Process sampler and SMEA
            if checking_params["sampler"] != "k_euler":
                checking_params["sampler"] = checking_params["sampler"].value
            if checking_params["smea"] != "None":
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
            elif checking_params["smea"] == "None":
                checking_params["sm"] = False
                checking_params["sm_dyn"] = False

            # Process prompt and negative prompt with function prompt_to_nai if prompt_conversion_toggle is True
            if checking_params["prompt_conversion_toggle"]:
                checking_params["positive"] = prompt_to_nai(checking_params["positive"])
                if checking_params["negative"] is not None:
                    checking_params["negative"] = prompt_to_nai(checking_params["negative"])

            # Process negative prompt with tags
            if checking_params["undesired_content_presets"] == "heavy":
                checking_params["undesired_content_presets"] = app_commands.Choice(name="heavy", value="heavy")
            if checking_params["undesired_content_presets"] != None:
                # Check if negative prompt is empty
                if checking_params["negative"] is None:
                    checking_params["negative"] = ""
                if checking_params["undesired_content_presets"].value == "heavy":
                    # Check model to see what tags to add
                    if checking_params["model"] == "nai-diffusion-3":
                        checking_params["negative"] +=  "lowres, {bad}, error, fewer, extra, missing, worst quality, jpeg artifacts, bad quality, watermark, unfinished, displeasing, chromatic aberration, signature, extra digits, artistic error, username, scan, [abstract]," + checking_params["negative"]
                    elif checking_params["model"] == "nai-diffusion-2":
                        checking_params["negative"] = "lowres, bad, text, error, missing, extra, fewer, cropped, jpeg artifacts, worst quality, bad quality, watermark, displeasing, unfinished, chromatic aberration, scan, scan artifacts," + checking_params["negative"]
                    elif checking_params["model"] == "nai-diffusion-furry" or checking_params["model"] == "nai-diffusion-furry-3":
                        checking_params["negative"] = "{{worst quality}}, [displeasing], {unusual pupils}, guide lines, {{unfinished}}, {bad}, url, artist name, {{tall image}}, mosaic, {sketch page}, comic panel, impact (font), [dated], {logo}, ych, {what}, {where is your god now}, {distorted text}, repeated text, {floating head}, {1994}, {widescreen}, absolutely everyone, sequence, {compression artifacts}, hard translated, {cropped}, {commissioner name}, unknown text, high contrast," + checking_params["negative"]
                elif checking_params["undesired_content_presets"].value == "light":
                    # Check model to see what tags to add
                    if checking_params["model"] == "nai-diffusion-3" or checking_params["model"] == "nai-diffusion-2":
                        checking_params["negative"] = "lowres, jpeg artifacts, worst quality, watermark, blurry, very displeasing," + checking_params["negative"]
                    elif checking_params["model"] == "nai-diffusion-furry" or checking_params["model"] == "nai-diffusion-furry-3":
                        checking_params["negative"] = "{worst quality}, guide lines, unfinished, bad, url, tall image, widescreen, compression artifacts, unknown text," + checking_params["negative"]
                elif checking_params["undesired_content_presets"].value == "human_focus":
                    # Check model to see what tags to add
                    if checking_params["model"] == "nai-diffusion-3":
                        checking_params['negative'] = "lowres, {bad}, error, fewer, extra, missing, worst quality, jpeg artifacts, bad quality, watermark, unfinished, displeasing, chromatic aberration, signature, extra digits, artistic error, username, scan, [abstract], bad anatomy, bad hands, @_@, mismatched pupils, heart-shaped pupils, glowing eyes," + checking_params['negative']

            return checking_params

        except Exception as e:
            logger.error(f"Error in check_params: {e}")
            await interaction.edit_original_response(content=f"{str(e)}")