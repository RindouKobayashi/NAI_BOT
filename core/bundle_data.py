from typing import TypedDict
import discord

class BundleData(TypedDict):
    request_id: int
    interaction: discord.Interaction
    message: discord.Message
    params: dict
    checking_params: dict
    position: int