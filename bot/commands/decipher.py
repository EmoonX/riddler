from itertools import permutations
import re

from discord.ext import commands
from discord_slash import (
    cog_ext, SlashContext, SlashCommandOptionType as OptType
)
from discord_slash.utils.manage_commands import create_option
from nltk.corpus import words

# Set of English words (as char tuples)
word_set = set(tuple(word) for word in words.words())


def _required_str_option(name: str, description: str) -> dict:
    '''Wrapper function for creating a required string command option.'''
    return create_option(
        name=name,
        description=description,
        option_type=OptType.from_type(str),
        required=True,
    )


class Decipher(commands.Cog):
    '''Several commands for deciphering codes and solving things.'''

    def __init__(self, bot):
        self.bot = bot

    @cog_ext.cog_slash(
        name='anagram',
        options=[create_option(
            name='word',
            description='Word to be anagrammed (max length: 10).',
            option_type=OptType.from_type(str),
            required=True,
        )],
    )
    async def anagram(self, ctx: SlashContext, word: str):
        '''Find all available English language anagrams of a given word.'''
        if len(word) > 10:
            await ctx.send('Too big of a word.')
            return
        text = f"Anagrams of ***{word}***:"
        valid_anagrams = set()
        for perm in permutations(word):
            if perm in word_set and perm not in valid_anagrams:
                new_word = ''.join(perm)
                text += f"\n• _{new_word}_"
                valid_anagrams.add(perm)
        if not valid_anagrams:
            text += '\nNone found...'
        await ctx.send(text)

    @cog_ext.cog_slash(
        name='ascii_to_text',
        options=[create_option(
            name='ascii_codes',
            description=(
                'List of space-separated ASCII decimal codes.'
            ),
            option_type=OptType.from_type(str),
            required=True,
        )],
    )
    async def ascii_to_text(self, ctx: SlashContext, ascii_codes: str):
        '''Convert ASCII codes to text.'''
        ascii_list = ascii_codes.split()
        text = ''.join(chr(int(k)) for k in ascii_list)
        if text.isspace():
            text = '_This message was intentionally left blank._'
        await ctx.send(text)

    @cog_ext.cog_slash(
        name='binary_to_text',
        options=[create_option(
            name='binary_code',
            description=(
                'Binary string of 0s and 1s (and possibly whitespace).'
            ),
            option_type=OptType.from_type(str),
            required=True,
        )],
    )
    async def binary_to_text(self, ctx: SlashContext, binary_code: str):
        '''Convert binary string(s) to ASCII character representation.'''

        # Ignore anything that isn't '0' or '1'
        binary_code = re.sub('[^01]', '', binary_code)

        # Build list of converted chars from binary groups of 8
        ascii_str = []
        for k in range(0, len(binary_code) - 7, 8):
            binary = binary_code[k:k+8]
            n = int(binary, 2)
            c = chr(n)
            ascii_str.append(c)

        # Get resulting string (possibly blank) and send it
        text = ''.join(ascii_str)
        if text.isspace():
            text = '_This message was intentionally left blank._'
        await ctx.send(text)

    @cog_ext.cog_slash(
        name='vigenere',
        options=[
            _required_str_option('ciphertext', 'Vigenère-encoded ciphertext.'),
            _required_str_option('key', 'Alphabetic keyword to be applied.'),
        ],
    )
    async def vigenere_decode(
        self, ctx: SlashContext, ciphertext: str, key: str
    ):
        '''Decode ciphertext using Vigenère method with given key.'''
        if not key.isalpha():
            await ctx.send('_[ERROR] Non-alphabetic keyword._', hidden=True)
            return
        key = key.upper()
        j = 0
        decoded_chars = list(ciphertext)
        for i, char in enumerate(decoded_chars):
            code = ord(char)
            if ord('A') <= code <= ord('Z'):
                # Uppercase letters
                delta = ord('A')
            elif ord('a') <= code <= ord('z'):
                # Lowercase letters
                delta = ord('a')
            else:
                # Ignore anything else
                continue
            index = ord(key[j]) - ord('A')
            code -= delta
            code = (code - index + 26) % 26
            code += delta
            decoded_chars[i] = chr(code)
            j = (j + 1) % len(key)
        decoded_text = ''.join(decoded_chars)
        await ctx.send(decoded_text)


def setup(bot: commands.Bot):
    '''Add cog every time extension (module) is (re)loaded.'''
    bot.add_cog(Decipher(bot))
