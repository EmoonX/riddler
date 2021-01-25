from discord.utils import get

from bot import bot


# --------------------------------------------------------------------------- #


@bot.command()
async def decipher(ctx):
    guild = bot.guilds[0]
    name = ctx.message.author.name
    member = get(guild.members, name=name)
    if ctx.message.guild or not member.guild_permissions.administrator:
        return

    content = ctx.message.content.split('\n', maxsplit=2)
    aux = content[1].split()
    if len(content) != 3 or len(aux) < 2 or len(aux) % 2 != 0:
        # Command usage
        text = '> `!decipher` - immortalize your name(s) on HoF (for now)\n' \
                '> \n' \
                '> • Usage: `!decipher\n' \
                '> <member> <flag>`\n' \
                '> `<message>`\n' \
                '> \n' \
                '> • Usage: `!decipher\n' \
                '> <team_member_1> <flag_1> <team_member_2> <flag_2> ...`\n' \
                '> `<message>`\n' \
                '> \n' \
                '> `member`: Your username, if you solved all alone\n' \
                '> `team_member_X`: the team members, if group solving\n' \
                '> `flag`: the emoji representing member\'s country\n' \
                '> `message`: your message to appear on the Hall of Fame\n' \
                '> \n' \
                '> • Be warned, as this is an one-use only command! After'  \
                    ' sending your message, it will be immortalized on the' \
                    ' HoF and you (and other team members, if applicable)' \
                    ' won\'t be able to reappear on the current temp-end HoF.' \
                    ' Yet, since we\'re nice, we\'ll gladly edit the message' \
                    ' afterwards if needed :)\n' \
                '> \n' \
                '> • P.S: Congratulations!'
        await ctx.message.channel.send(text)
        return

    ids = []
    for name in (aux[0],):
        member = get(guild.members, name=name)
        ids.append('<@!%d>' % member.id)
    aux = ', '.join(ids[:-1])
    if len(aux) > 1:
        ids = aux + ' and ' + ids[-1]
    else:
        ids = ids[0]
    text = '> **%s has reached temp end! Congrats!**\n' % ids
    channel = get(guild.channels, name='achievements')
    await channel.send(text)
    return

    # Build list of current winners
    winners = []
    for filename in ('winners_solo.txt', 'winners_group.txt'):
        with open(filename, 'r') as file:
            while True:
                line = file.read()
                if not line:
                    break
                for member in line.split():
                    winners.append(member)

    # Create member and flag lists
    members = aux[1][::2]
    flags = aux[1][1::2]
