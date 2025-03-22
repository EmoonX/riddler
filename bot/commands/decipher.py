from itertools import permutations
import re
import string
from typing import Optional

from bitarray import bitarray
from discord import app_commands, Interaction
from discord.ext import commands
from nltk.corpus import words

from bot import bot

# Set of lowercase English words (as char tuples)

word_set = set(tuple(word.lower()) for word in words.words())


# def _required_str_option(name: str, description: str) -> dict:
#     '''Wrapper function for creating a required string command option.'''
#     return create_option(
#         name=name,
#         description=description,
#         option_type=OptType.from_type(str),
#         required=True,
#     )


class Decipher(commands.Cog):
    '''Several commands for deciphering codes and solving stuff.'''
    
    group = app_commands.Group(
        name="decipher",
        description="Deciphering tools"
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @group.command()
    async def a1z26(self, interaction: Interaction, numbers: str):
        '''
        Replace a sequence of numbers by letters in the alphabet
        (a=1, b=2, ..., z=26).
        
        Args
            numbers: Sequence of space-separated numbers, each between 1 and 26.
        '''

        chars = []
        for number in numbers.split():
            try:
                number = int(number)
                if not (1 <= number <= 26):
                    raise ValueError
            except ValueError:
                return
            char = chr(ord('a') + number - 1)
            chars.append(char)

        word = ''.join(chars)
        await interaction.response.send_message(word)

    @group.command()
    async def anagram(self, interaction: Interaction, word: str):
        '''
        Find all available English language anagrams for a given word.
        
        Args
            word: Word to be anagrammed (max length: 10).
        '''
        
        if len(word) > 10:
            # await _error_message(ctx, 'Too big of a word.')
            return

        word = word.lower()
        valid_anagrams = set()
        for perm in permutations(word):
            if perm in word_set and perm not in valid_anagrams:
                valid_anagrams.add(perm)
        
        text = f"Anagrams of ***{word}***:"
        if valid_anagrams:
            for perm in sorted(valid_anagrams):
                word = ''.join(perm)
                text += f"\n• _{word}_"
        else:
            text += '\nNone found...'
            
        await interaction.response.send_message(text)

    @group.command()
    async def ascii_to_text(self, interaction: Interaction, ascii_codes: str):
        '''
        Convert ASCII codes into text.
        
        Args:
            ascii_codes: Sequence of space-separated ASCII decimal codes.
        '''
        bad_chars = re.search(r'[^\d\s]', ascii_codes) is not None
        if bad_chars:
            # await _error_message(
            #     ctx, 'Text should only contain numbers and whitespace.'
            # )
            return
        ascii_list = ascii_codes.split()
        text = ''.join(chr(int(k)) for k in ascii_list)
        await interaction.response.send_message(text)

    @group.command()
    async def atbash(self, interaction: Interaction, text: str):
        '''
        A-Z cipher. Swaps each letter for its reverse in the latin alphabet.
        
        Args:
            text: Text to be decoded/encoded.
        '''
        decoded_text = list(text)
        for i, char in enumerate(text):
            if char.isalpha():
                k = ord('a') if char.islower() else ord('A')
                char = chr((25 - (ord(char) - k)) + k)
            decoded_text[i] = char
        decoded_text = ''.join(decoded_text)
        await interaction.response.send_message(decoded_text)

    @group.command()
    async def base64(self, interaction: Interaction, code: str):
        '''
        Decode Base64-encoded text.
        
        Args:
            code: Base64-encoded text (valid characters: A-Z|a-z|+|/|= ).
        '''

        alphabet = ''.join([
            string.ascii_uppercase,
            string.ascii_lowercase,
            string.digits,
            '+/'
        ])
        bits = bitarray()
        for char in code:
            k = alphabet.find(char)
            if k != -1:
                bits += f"{k:06b}"
                
        size = len(bits) // 8 * 8
        text = bits[:size].tobytes().decode('utf-8')
        
        await interaction.response.send_message(text)

    @group.command()
    async def binary_to_text(self, interaction: Interaction, binary_code: str):
        '''
        Convert binary string(s) into their ASCII character representation.
        
        Args:
            binary_code: Binary string of 0s and 1s (and possibly whitespace).
        '''
        bad_chars = re.search(r'[^01\s]', binary_code) is not None
        if bad_chars:
            # await _error_message(
            #     ctx, 'Code should only contain 0s, 1s and whitespace.'
            # )
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
            # await _error_message(ctx, 'Empty message.')
            return
        await interaction.response.send_message(text)

    @group.command()
    async def caesar(self, interaction: Interaction, text: str, shift: int):
        '''
        Decode text using Caesar Cipher with given shift.
        
        Args:
            text: Caesar-shifted ciphertext.
            shift: How many positions each char should be shifted
                in the alphabet (sign infers direction).
        '''
        text = Util.caesar_base(text, shift)
        await interaction.response.send_message(text)

    @group.command()
    async def crossword_solver(self, interaction: Interaction, pattern: str):
        '''
        Search for English words that match given pattern.
        
        Args:
            pattern: Pattern to be searched for, with '?' as wildcard.
        '''

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
        
        await interaction.response.send_message(text)

    @group.command()
    async def morse(self, interaction: Interaction, code: str):
        '''
        Decode Morse-encoded text.
        
        Args:
            code: Dots (.) and dashes (-). Use spaces ( )
                for separating letters and slashes (/) for words.
        '''

        morse_to_char = {
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
                char = morse_to_char.get(code, '?')
                word.append(char)
            decoded_text.append(''.join(word))

        decoded_text = ' '.join(decoded_text)
        
        await interaction.response.send_message(decoded_text)

    @group.command()
    async def reverse(self, interaction: Interaction, text: str):
        '''
        Reverse a string of characters.
        
        Args:
            text: Text to be reversed.
        '''
        await interaction.response.send_message(text[::-1])

    @group.command()
    async def rot13(self, interaction: Interaction, text: str):
        '''
        Shift each letter by 13 positions in the alphabet.
        
        Args:
            text: Text to be shifted.
        '''
        decoded_text = Util.caesar_base(text, 13)
        await interaction.response.send_message(decoded_text)

    @group.command()
    async def vigenere(self, interaction: Interaction, text: str, key: str):
        '''
        Decode text using the Vigenère method with given key.
        
        Args:
            text: Vigenère-encoded ciphertext.
            key: Alphabetic keyword to be applied.
        '''
        if not key.isalpha():
            # await _error_message(ctx, 'Non-alphabetic keyword.')
            return
        key = key.upper()
        j = 0
        decoded_chars = list(text)
        for i, char in enumerate(decoded_chars):
            shift = -(ord(key[j]) - ord('A'))
            char = Util.shift_char(char, shift)
            if char:
                decoded_chars[i] = char
                j = (j + 1) % len(key)
        decoded_text = ''.join(decoded_chars)
        await interaction.response.send_message(decoded_text)
    

class Util:
        
    @staticmethod
    def caesar_base(text: str, shift: int):
        '''Reusable base Caesar cipher method.'''
        decoded_chars = list(text)
        for i, char in enumerate(text):
            char = __class__.shift_char(char, shift)
            if char:
                decoded_chars[i] = char
        text = ''.join(decoded_chars)
        return text

    @staticmethod
    def shift_char(char: str, shift: int) -> Optional[str]:
        '''Shift char in the alphabet by amount of positions.'''
        code = ord(char)
        if ord('A') <= code <= ord('Z'):
            delta = ord('A')
        elif ord('a') <= code <= ord('z'):
            delta = ord('a')
        else:
            return None
        code -= delta
        code = (code + shift + 26) % 26
        code += delta
        return chr(code)


# async def _error_message(interaction: Interaction, text: str):
#     '''Send custom hidden error message.'''
#     await send(interaction, f"_[ERROR] {text}_", hidden=True)


async def setup(bot: commands.Bot):
    '''Add cog every time extension (module) is (re)loaded.'''
    await bot.add_cog(Decipher(bot))
