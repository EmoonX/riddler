import os
import sys
import logging

from dotenv import load_dotenv
from cogwatch import Watcher

# Allow util folder to be visible
sys.path.append('..')

# Load environment variables from .env file
load_dotenv(verbose=True)

# Allow logging info
logging.basicConfig(level=logging.INFO)

from bot import bot
from riddle import build_riddles


@bot.event
async def on_ready():
    '''Procedures upon bot initialization.'''

    logging.info('> Bot up and running!')
    
    # Start cogwatch on commands folder
    watcher = Watcher(bot, path='commands', preload=True)
    await watcher.start()

    # Build riddles dict
    await build_riddles()

    # from discord.utils import get
    # from time import sleep
    # from util.db import database
    # s = '''zitman
    #     shaharc
    #     Catz
    #     otherlego
    #     carbo25
    #     thecatthatplayz
    #     sable
    #     Shen Qiang
    #     Selenium
    #     Mtn.Laurel
    #     alchimista
    #     thedude
    #     Queen
    #     ASTROBOSS
    #     AlessaMason
    #     Rafa
    #     Zodiac
    #     makateller
    #     umsyt
    #     GhostsTheElder
    #     Antoine S
    #     FlyingOmelet
    #     LiahnovTechenski
    #     Picklemaniac
    #     Tyte
    #     denpao
    #     NinthLyfe
    #     adsyo
    #     無名鼎鼎
    #     wolbee
    #     DCesar
    #     nofanksluv she/her
    #     B e h i n d
    #     DR
    #     Kafka
    #     Lorelei
    #     cdb513
    #     Xwam
    #     ellyerin
    #     Emoon
    #     '''
    # try:
    #     names_list = s.split()
    #     aaa = bot.get_all_members()
    #     members = [member for member in aaa]
    #     for member in members:
    #         logging.info(member)
    #     for name in names_list:
    #         query = 'SELECT * FROM accounts ' \
    #                 'WHERE username = :username ' \
    #                 'ORDER BY global_score DESC'
    #         values = {'username': name}
    #         player = await database.fetch_one(query, values)
    #         if player:
    #             logging.info(player)
    #             member = get(members, name=player['username'],
    #                     discriminator=player['discriminator'])
    #             logging.info(member)
    #             text = \
    #                 'Hello! If you\'re receiving this message, that means' \
    #                 ' you\'re a valuable riddle player (i.e this isn\'t being sent to everyone!). However, for one reason or the other, you still haven\'t' \
    #                 ' joined the **Wonderland II** guild. We recommend doing' \
    #                 ' so for having access to fresh announcements, overall' \
    #                 ' riddles/Riddler discussion, eventual bug reporting and much more!\n\n' \
    #                 'See ya!\n' \
    #                 'https://discord.gg/ktaPPtnPSn'
    #             await member.send(text)
    # except:
    #     import traceback
    #     tb = traceback.format_exc()
    #     logging.error(tb)

    # guild = get(bot.guilds, name='Genius Riddle')
    # role = get(guild.roles, name='Autumn Sommeliers')
    # for channel in guild.channels:
    #     if 'autumn' in channel.name:
    #         await channel.set_permissions(role, read_messages=True)


if __name__ == '__main__':
    # Start bot with secret token
    token = os.getenv('DISCORD_TOKEN')
    bot.run(token)
