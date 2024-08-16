from typing import TypedDict, Union
import discord
from discord import app_commands
from copy import deepcopy


class Checking_Params(TypedDict):
    positive: str
    negative: str
    width: int
    height: int
    steps: int
    cfg: float
    sampler: Union[app_commands.Choice[str], str]
    smea: Union[app_commands.Choice[str], str]
    seed: int
    model: app_commands.Choice[str]
    quality_toggle: bool
    undesired_content_presets: app_commands.Choice[str]
    prompt_conversion_toggle: bool
    upscale: bool
    vibe_transfer_switch: bool

class Params(TypedDict):
    positive: str
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

class BundleData(TypedDict):
    request_id: int
    interaction: discord.Interaction
    message: discord.Message
    params: Params
    checking_params: Checking_Params
    position: int
    reference_message: discord.Message = None

def deep_copy_bundle_data(bundle_data: BundleData) -> BundleData:
    return BundleData(
        request_id=bundle_data["request_id"],
        interaction=bundle_data["interaction"],
        message=bundle_data["message"],
        params=bundle_data["params"],  # Shallow copy assuming `params` doesn't need deep copy
        checking_params=deepcopy(bundle_data["checking_params"]),  # Deep copy for nested dict
        position=bundle_data["position"],
        reference_message=bundle_data["reference_message"]
    )