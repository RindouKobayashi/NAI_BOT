from typing import TypedDict, Union, Dict, Any
import discord
from discord import app_commands
from copy import deepcopy


class Checking_Params(TypedDict, total=False):
    positive: str
    negative: str
    width: int
    height: int
    steps: int
    cfg: float
    sampler: Union[app_commands.Choice[str], str]
    noise_schedule: Union[app_commands.Choice[str], str]
    smea: Union[app_commands.Choice[str], str]
    seed: int
    model: app_commands.Choice[str]
    quality_toggle: bool
    undesired_content_presets: app_commands.Choice[str]
    prompt_conversion_toggle: bool
    upscale: bool
    dynamic_thresholding: bool
    vibe_transfer_switch: bool

class Params(TypedDict, total=False):
    positive: str
    width: int
    height: int
    steps: int
    cfg: float
    sampler: str
    noise_schedule: str
    sm: bool
    sm_dyn: bool
    seed: int
    model: str
    upscale: bool
    dynamic_thresholding: bool
    vibe_transfer_switch: bool

class Director_Tools_Params(TypedDict, total=False):
    width: int
    height: int
    image: discord.Attachment
    req_type: str
    prompt: str
    defry: int
    emotion: str

class BundleData(TypedDict, total=False):
    request_id: int = None
    type: str = None
    interaction: discord.Interaction = None
    message: discord.Message = None
    params: Params = None
    checking_params: Checking_Params = None
    position: int = None
    reference_message: discord.Message = None
    director_tools_params: Director_Tools_Params = None
    number_of_tries: int = 2

def create_with_defaults(typed_dict_class: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    # Initialize with None for all fields based on the TypedDict annotations
    default_dict = {key: getattr(typed_dict_class, key, None) for key in typed_dict_class.__annotations__.keys()}
    # Update with provided values
    default_dict.update(kwargs)
    return default_dict


def deep_copy_bundle_data(bundle_data: BundleData) -> BundleData:
    return BundleData(
        request_id=deepcopy(bundle_data.get("request_id")),
        type=deepcopy(bundle_data.get("type")),
        interaction=bundle_data.get("interaction"),
        message=bundle_data.get("message"),
        params=deepcopy(bundle_data.get("params")),  # Deep copy to ensure nested structures are copied
        checking_params=deepcopy(bundle_data.get("checking_params")),  # Deep copy for nested dict
        position=bundle_data.get("position"),
        reference_message=bundle_data.get("reference_message"),
        director_tools_params=deepcopy(bundle_data.get("director_tools_params")),  # Deep copy if necessary
        number_of_tries=bundle_data.get("number_of_tries"),
    )