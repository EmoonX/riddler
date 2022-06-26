from itertools import permutations
import re

from discord.ext import commands
from discord_slash import (
    cog_ext, SlashContext, SlashCommandOptionType as OptType
)
from discord_slash.utils.manage_commands import create_option
from nltk.corpus import words

# Set of lowercase English words (as char tuples)
word_set = set(tuple(word.lower()) for word in words.words())


def _required_str_option(name: str, description: str) -> dict:
    '''Wrapper function for creating a required string command option.'''
    return create_option(
        name=name,
        description=description,
        option_type=OptType.from_type(str),
        required=True,
    )


def _shift_char(char: str, shift: int) -> str:
    '''Shift char by given amount on the alphabet.'''
    code = ord(char)
    if ord('A') <= code <= ord('Z'):
        delta = ord('A')
    elif ord('a') <= code <= ord('z'):
        delta = ord('a')
    else:
        return
    code -= delta
    code = (code + shift + 26) % 26
    code += delta
    return chr(code)


async def _error_message(ctx: SlashContext, text: str):
    '''Send custom hidden error message.'''
    await ctx.send(f"_[ERROR] {text}_", hidden=True)


class Decipher(commands.Cog):
    '''Several commands for deciphering codes and solving things.'''

    def __init__(self, bot):
        self.bot = bot

    @cog_ext.cog_slash(
        name='anagram',
        options=[_required_str_option(
            'word', 'Word to be anagrammed (max length: 10).'
        )],
    )
    async def anagram(self, ctx: SlashContext, word: str):
        '''Find all available English language anagrams for a given word.'''
        if len(word) > 10:
            await _error_message(ctx, 'Too big of a word.')
            return
        text = f"Anagrams of ***{word}***:"
        valid_anagrams = set()
        for perm in permutations(word):
            if perm in word_set and perm not in valid_anagrams:
                valid_anagrams.add(perm)
        if valid_anagrams:
            for perm in sorted(valid_anagrams):
                word = ''.join(perm)
                text += f"\n• _{word}_"
        else:
            text += '\nNone found...'
        await ctx.send(text)

    @cog_ext.cog_slash(
        name='ascii_to_text',
        options=[_required_str_option(
            'ascii_codes', 'List of space-separated ASCII decimal codes.'
        )],
    )
    async def ascii_to_text(self, ctx: SlashContext, ascii_codes: str):
        '''Convert ASCII codes to text.'''
        bad_chars = re.search(r'[^\d\s]', ascii_codes) is not None
        if bad_chars:
            await _error_message(
                ctx, 'Text should only contain numbers and whitespace.'
            )
            return
        ascii_list = ascii_codes.split()
        text = ''.join(chr(int(k)) for k in ascii_list)
        await ctx.send(text)

    @cog_ext.cog_slash(
        name='atbash',
        options=[_required_str_option(
            'text', 'Text to be decoded/encoded.'
        )],
    )
    async def atbash(self, ctx: SlashContext, text: str):
        '''A-Z cipher. Swaps each letter \
        for its reverse in the latin alphabet.'''
        decoded_text = list(text)
        for i, char in enumerate(text):
            if char.isalpha():
                k = ord('a') if char.islower() else ord('A')
                char = chr((25 - (ord(char) - k)) + k)
            decoded_text[i] = char
        decoded_text = ''.join(decoded_text)
        await ctx.send(decoded_text)

    @cog_ext.cog_slash(
        name='binary_to_text',
        options=[_required_str_option(
            'binary_code',
            'Binary string of 0s and 1s (and possibly whitespace).'
        )],
    )
    async def binary_to_text(self, ctx: SlashContext, binary_code: str):
        '''Convert binary string(s) to ASCII character representation.'''
        bad_chars = re.search(r'[^01\s]', binary_code) is not None
        if bad_chars:
            await _error_message(
                ctx, 'Code should only contain 0s, 1s and whitespace.'
            )
            return
        binary_code = re.sub(r'\s', '', binary_code)
        ascii_list = []
        for k in range(0, len(binary_code) - 7, 8):
            binary = binary_code[k:k+8]
            n = int(binary, 2)
            c = chr(n)
            ascii_list.append(c)
        text = ''.join(ascii_list)
        if not text or text.isspace():
            await _error_message(ctx, 'Empty message.')
            return
        await ctx.send(text)

    @cog_ext.cog_slash(
        name='caesar',
        options=[
            _required_str_option('ciphertext', 'Caesar-shifted ciphertext.'),
            create_option(
                name='shift',
                description=(
                    'How many positions each char should be shifted on '
                        'the alphabet (sign infers direction).'
                ),
                option_type=OptType.from_type(int),
                required=True,
            )
        ],
    )
    async def caesar(
        self, ctx: SlashContext, ciphertext: str, shift: int
    ):
        '''Decode ciphertext using Caesar cipher with given shift.'''
        text = await self._caesar_base(ciphertext, shift)
        await ctx.send(text)

    @staticmethod
    def _caesar_base(text: str, shift: int):
        '''Reusable base Caesar cipher method.'''
        decoded_chars = list(text)
        for i, char in enumerate(text):
            char = _shift_char(char, shift)
            if char:
                decoded_chars[i] = char
        text = ''.join(decoded_chars)
        return text

    @cog_ext.cog_slash(
        name='crossword',
        options=[_required_str_option(
            'pattern',
            "Pattern to be searched for, with '?' as wildcard."
        )],
    )
    async def crossword_solver(self, ctx: SlashContext, pattern: str):
        '''Search for English words that match given pattern.'''

        def _match(pattern: str, word: str):
            '''Wildcard match between pattern and word.'''
            if len(pattern) != len(word):
                return False
            for i, _ in enumerate(pattern):
                if pattern[i] not in (word[i], '?'):
                    return False
            return True

        # Build list of solutions by exhaustively iteracting over word set
        text = f"Solutions for ***{pattern}***:"
        solutions = []
        for word in word_set:
            if _match(pattern, word):
                solutions.append(''.join(word))

        # Show ordered solutions (up to a hard limit)
        if solutions:
            max_shown = 16
            for count, word in enumerate(sorted(solutions)):
                text += f"\n• _{word}_"
                if count == max_shown - 1:
                    break
            if len(solutions) > max_shown:
                excess = len(solutions) - max_shown
                text += f"\n(+ ***{excess}*** more not shown here...)"
        else:
            text += '\nNone found...'
        await ctx.send(text)

    @cog_ext.cog_slash(
        name='morse',
        options=[_required_str_option(
            'code',
            'Dots (.) and dashes (-). Use spaces ( ) for separating '
                'letters and slashes (/) for words.'
        )],
    )
    async def morse(self, ctx: SlashContext, code: str):
        '''Decode Morse-encoded text.'''

        morse = {
            '.-'  : 'A', '-...': 'B', '-.-.': 'C', '-..' : 'D',
            '.'   : 'E', '..-.': 'F', '--.' : 'G', '....': 'H',
            '..'  : 'I', '.---': 'J', '-.-' : 'K', '.-..': 'L',
            '--'  : 'M', '-.'  : 'N', '---' : 'O', '.--.': 'P',
            '--.-': 'Q', '.-.' : 'R', '...' : 'S', '-'   : 'T',
            '..-' : 'U', '...-': 'V', '.--' : 'W',
            '-..-': 'X', '-.--': 'Y', '--..': 'Z',

            '-----': '0', '.----': '1', '..---': '2',
            '...--': '3', '....-': '4', '.....': '5',
            '-....': '6', '--...': '7', '---..': '8', '----.': '9',

            '.-.-.-': '.', '--..--' : ',', '..--..': '?',
            '.----.': "'", '-.-.--' : '!', '-..-.' : '/',
            '-.--.' : '(', '-.--.-' : ')', '.-...' : '&',
            '---...': ':', '-.-.-.' : ';', '-...-' : '=',
            '.-.-.' : '+', '-....-' : '-', '..--.-': '_',
            '.-..-.': '"', '...-..-': '$', '.--.-.': '@',
        }
        segments = code.split('/')
        decoded_text = []
        for segment in segments:
            word = []
            codes = segment.split()
            for code in codes:
                char = morse.get(code, '?')
                word.append(char)
            decoded_text.append(''.join(word))
        decoded_text = ' '.join(decoded_text)
        await ctx.send(decoded_text)

    @cog_ext.cog_slash(
        name='reverse',
        options=[_required_str_option(
            'text', 'Text to be reversed.'
        )],
    )
    async def reverse(self, ctx: SlashContext, text: str):
        '''Reverse a string of characters.'''
        reversed_text = text[::-1]
        await ctx.send(reversed_text)

    @cog_ext.cog_slash(
        name='rot13',
        options=[_required_str_option(
            'text', 'Text to be decoded/encoded.'
        )],
    )
    async def rot13(self, ctx: SlashContext, text: str):
        '''Shift each letter 13 positions in the alphabet.'''
        decoded_text = self._caesar_base(text, 13)
        await ctx.send(decoded_text)

    @cog_ext.cog_slash(
        name='vigenere',
        options=[
            _required_str_option('ciphertext', 'Vigenère-encoded ciphertext.'),
            _required_str_option('key', 'Alphabetic keyword to be applied.'),
        ],
    )
    async def vigenere(
        self, ctx: SlashContext, ciphertext: str, key: str
    ):
        '''Decode ciphertext using Vigenère method with given key.'''
        if not key.isalpha():
            await _error_message(ctx, 'Non-alphabetic keyword.')
            return
        key = key.upper()
        j = 0
        decoded_chars = list(ciphertext)
        for i, char in enumerate(decoded_chars):
            shift = -(ord(key[j]) - ord('A'))
            char = _shift_char(char, shift)
            if char:
                decoded_chars[i] = char
                j = (j + 1) % len(key)
        decoded_text = ''.join(decoded_chars)
        await ctx.send(decoded_text)


def setup(bot: commands.Bot):
    '''Add cog every time extension (module) is (re)loaded.'''
    bot.add_cog(Decipher(bot))
