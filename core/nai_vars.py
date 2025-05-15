from discord import app_commands
from settings import logger
import random
import discord

class Nai_vars:
    models = ["nai-diffusion-4-5-curated","nai-diffusion-4-full", "nai-diffusion", "nai-diffusion-2", "nai-diffusion-3", "safe-diffusion", "nai-diffusion-furry", "nai-diffusion-furry-3"]
    models_choices = [app_commands.Choice(name=name, value=name) for name in models]
    models_select_options = [discord.SelectOption(label=name, description=name) for name in models]
    samplers = ["k_euler", "k_euler_ancestral", "k_dpmpp_2s_ancestral", "k_dpmpp_2m", "k_dpmpp_sde", "k_dpmpp_2m_sde", "ddim_v3"]
    samplers_choices = [app_commands.Choice(name=name, value=name) for name in samplers]
    samplers_options = [discord.SelectOption(label=name, value=name, description=name) for name in samplers]
    smea = ["SMEA", "SMEA+DYN", "None"]
    noise_schedule = ["native", "karras", "exponential", "polyexponential"]
    noise_schedule_choices = [app_commands.Choice(name=name, value=name) for name in noise_schedule]
    noise_schedule_options = [discord.SelectOption(label=name, value=name, description=name) for name in noise_schedule]
    smea_choices = [app_commands.Choice(name=name, value=name) for name in smea]

    upscale_limit_pixels = 640*640

    class width():
        max_value = 2048
        min_value = 64
        step = 64
        default = 832
    
    class height():
        max_value = 2048
        min_value = 64
        step = 64
        default = 1216

    class pixel_limit():
        def __init__(self, model):
            self.model = model
            if self.model in ["nai-diffusion-2", "nai-diffusion-3", "nai-diffusion-furry-3", "nai-diffusion-4-full", "nai-diffusion-4-5-curated"]:
                self.pixel_limit = 1024*1024
            else:
                self.pixel_limit = 640*640
    
    class steps():
        max_value = 28
        min_value = 1
        default = 28

    class cfg():
        max_value = 10.0
        min_value = 0.0
        step = 0.1
        default = 5.0

    class seed():
        max_value = 9999999999
        min_value = 0

    class undesired_content_presets():
        types = ["heavy", "light", "human_focus", "none"]
        presets_choices = [app_commands.Choice(name=name.capitalize(), value=name) for name in types]
        def __init__(self, model):
            self.model = model
            if self.model == "nai-diffusion-3":
                self.presets = {
                    "heavy": "lowres, {bad}, error, fewer, extra, missing, worst quality, jpeg artifacts, bad quality, watermark, unfinished, displeasing, chromatic aberration, signature, extra digits, artistic error, username, scan, [abstract],",
                    "light": "lowres, jpeg artifacts, worst quality, watermark, blurry, very displeasing,",
                    "human_focus": "lowres, {bad}, error, fewer, extra, missing, worst quality, jpeg artifacts, bad quality, watermark, unfinished, displeasing, chromatic aberration, signature, extra digits, artistic error, username, scan, [abstract], bad anatomy, bad hands, @_@, mismatched pupils, heart-shaped pupils, glowing eyes,",
                    "none": ""
                }
            elif self.model == "nai-diffusion-2":
                self.presets = {
                    "heavy": "lowres, bad, text, error, missing, extra, fewer, cropped, jpeg artifacts, worst quality, bad quality, watermark, displeasing, unfinished, chromatic aberration, scan, scan artifacts,",
                    "light": "lowres, jpeg artifacts, worst quality, watermark, blurry, very displeasing,",
                    "human_focus": "",
                    "none": ""
                }
            elif self.model == "nai-diffusion":
                self.presets = {
                    "heavy": "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry,",
                    "light": "lowres, text, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry,",
                    "human_focus": "",
                    "none": ""
                }
            elif self.model == "nai-diffusion-furry-3":
                self.presets = {
                    "heavy": "{{worst quality}}, [displeasing], {unusual pupils}, guide lines, {{unfinished}}, {bad}, url, artist name, {{tall image}}, mosaic, {sketch page}, comic panel, impact (font), [dated], {logo}, ych, {what}, {where is your god now}, {distorted text}, repeated text, {floating head}, {1994}, {widescreen}, absolutely everyone, sequence, {compression artifacts}, hard translated, {cropped}, {commissioner name}, unknown text, high contrast,",
                    "light": "{worst quality}, guide lines, unfinished, bad, url, tall image, widescreen, compression artifacts, unknown text,",
                    "human_focus": "",
                    "none": ""
                }
            elif self.model == "nai-diffusion-furry":
                self.presets = {
                    "heavy": "{worst quality}, low quality, distracting watermark, [nightmare fuel], {{unfinished}}, deformed, outline, pattern, simple background,",
                    "light": "worst quality, low quality, what has science done, what, nightmare fuel, eldritch horror, where is your god now, why,",
                    "human_focus": "",
                    "none": ""
                }
            elif self.model == "nai-diffusion-4-full":
                self.presets = {
                    "heavy": "blurry, lowres, error, film grain, scan artifacts, worst quality, bad quality, jpeg artifacts, very displeasing, chromatic aberration, multiple views, logo, too many watermarks",
                    "light": "blurry, lowres, error, worst quality, bad quality, jpeg artifacts, very displeasing",
                    "human_focus": "",
                    "none": ""
                }
            elif self.model == "nai-diffusion-4-5-curated":
                self.presets = {
                    "heavy": "blurry, lowres, upscaled, artistic error, film grain, scan artifacts, worst quality, bad quality, jpeg artifacts, very displeasing, chromatic aberration, halftone, multiple views, logo, too many watermarks, negative space, blank page",
                    "light": "blurry, lowres, upscaled, artistic error, scan artifacts, jpeg artifacts, logo, too many watermarks, negative space, blank page",
                    "human_focus": "blurry, lowres, upscaled, artistic error, film grain, scan artifacts, bad anatomy, bad hands, worst quality, bad quality, jpeg artifacts, very displeasing, chromatic aberration, halftone, multiple views, logo, too many watermarks, @_@, mismatched pupils, glowing eyes, negative space, blank page",
                    "none": ""
                }
            self.undesired_content_select_options = [discord.SelectOption(label=name, value=name) for name in self.presets.keys()]

    class quality_tags():
        def __init__(self, model):
            self.model = model
            if self.model == "nai-diffusion-3":
                self.tags = "best quality, amazing quality, very aesthetic, absurdres"
                self.add_way = "append"
            elif self.model == "nai-diffusion-2":
                self.tags = "very aesthetic, best quality, absurdres, "
                self.add_way = "prepend"
            elif self.model == "nai-diffusion-furry-3":
                self.tags = "{best quality}, {amazing quality}"
                self.add_way = "append"
            elif self.model in ["nai-diffusion", "nai-diffusion-furry"]:
                self.tags = "masterpiece, best quality, "
                self.add_way = "prepend"
            elif self.model == "nai-diffusion-4-full":
                self.tags = "no text, best quality, very aesthetic, absurdres"
                self.add_way = "append"
            elif self.model == "nai-diffusion-4-5-curated":
                self.tags = "very aesthetic, location, masterpiece, no text, -0.8::feet::, rating:general"
                self.add_way = "append"

    class director_tools():
        req_type = ["lineart", "sketch", "colorize", "emotion", "declutter"]
        req_type_choice = [app_commands.Choice(name=name, value=name) for name in req_type]
        emotions = ["neutral", "happy", "sad", "angry", "surprise", "tired", "excited",
                    "nervous", "thinking", "confused", "shy", "disgusted", "smug",
                    "bored", "laughing", "irritated", "aroused", "embarrassed", "worried",
                    "love", "determined", "hurt", "playful"]
        emotions_choice = [app_commands.Choice(name=name, value=f"{name};;") for name in emotions]
        defry = ["0", "1", "2", "3", "4", "5"]
        defry_choice = [app_commands.Choice(name=name, value=name) for name in defry]