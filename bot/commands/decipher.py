import re

from discord.ext import commands
from discord_slash import (
    cog_ext, SlashContext, SlashCommandOptionType as OptType
)
from discord_slash.utils.manage_commands import create_option


class Decipher(commands.Cog):
    '''Several commands for deciphering codes.'''

    def __init__(self, bot):
        self.bot = bot

    @cog_ext.cog_slash(
        name='bintoascii',
        options=[create_option(
            name='binary_code',
            description=(
                'Binary string of 0s and 1s (and possibly whitespace)'
            ),
            option_type=OptType.from_type(str),
            required=True,
        )],
    )
    async def bintoascii(self, ctx: SlashContext, binary_code: str):
        '''Convert binary string(s) to ASCII character representation.'''

        # Ignore anything that isn't '0' or '1'
        binary_code = re.sub('[^01]', '', binary_code)

        # Build list of converted chars from binary groups of 8
        ascii_str = []
        for k in range(0, len(binary_code) - 7, 8):
            bin = binary_code[k:k+8]
            n = int(bin, 2)
            c = chr(n)
            ascii_str.append(c)

        # Get resulting string (possibly blank) and send it
        ascii_str = ''.join(ascii_str)
        if ascii_str.isspace():
            ascii_str = '_This message was intentionally left blank._'
        await ctx.send(ascii_str)


def setup(bot: commands.Bot):
    '''Add cog every time extension (module) is (re)loaded.'''
    bot.add_cog(Decipher(bot))
