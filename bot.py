import discord
from discord.ext import commands

# intents thingamajig for newer discord.py API version
intents = discord.Intents.default()
intents.members = True

class Bot(commands.Bot):
    """Main bot class"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def on_ipc_ready(self):
        """Event dispatched upon the IPC being ready"""
        print("IPC ready")

    async def on_ready(self):
        """Event dispatched upon our discord bot being ready"""
        print("Bot ready")
    
    async def on_ipc_error(self, endpoint, error):
        """Called upon an error being raised within an IPC route"""
        print(endpoint, "raised", error)

# Create bot (commands are designated starting with '!')
bot = Bot(command_prefix='!', intents=intents)
