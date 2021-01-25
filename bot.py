import discord
from discord.ext import commands

# intents thingamajig for newer discord.py API version
intents = discord.Intents.default()
intents.members = True

# Create bot (commands are designated starting with '!')
bot = commands.Bot(command_prefix='!', intents=intents)
