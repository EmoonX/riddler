import discord
from discord import InteractionResponded
from discord.app_commands import AppCommandError
from discord.app_commands.errors import CommandInvokeError
from discord.utils import format_dt

from bot import bot


@bot.tree.error
async def on_error(
    interaction: discord.Interaction,
    error: AppCommandError | Exception,
):

    if isinstance(error, CommandInvokeError):
        error = error.original
        
    message = f"""
        \nException: {error.__class__.__name__},"
        " Command: {self.command.qualified_name if self.command else None},"
        " User: {self.user},"
        " Time: {format_dt(self.created_at, style='F')}
        \n
    """
    message = f"An error occurred: {message}"
    
    try:
        await self.send(message)
    except InteractionResponded:
        await self.followup.send(message)


async def setup(_):
    pass
