from typing import TypedDict
import discord
from discord import app_commands

class BundleData(TypedDict):
    request_id: int
    interaction: discord.Interaction
    message: discord.Message
    params: dict
    checking_params: dict
    position: int

class Checking_Params(TypedDict):
    positive: str
    negative: str
    width: int
    height: int
    steps: int
    cfg: float
    sampler: app_commands.Choice[str]
    smea: app_commands.Choice[str]
    seed: int
    model: app_commands.Choice[str]
    quality_toggle: bool
    undesired_content_preset: app_commands.Choice[str]
    prompt_conversion_toggle: bool
    upscale: bool
    vibe_transfer_switch: bool

class Params(TypedDict):
    prompt: str
    width: int
    height: int
    steps: int
    cfg: float
    sampler: str
    sm: bool
    sm_dyn: bool
    seed: int
    model: str
    upscale: bool
    vibe_transfer_switch: bool