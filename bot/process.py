from discord import Member
from discord.utils import get
import bcrypt

from bot import bot
from riddle import Riddle, riddles
from util.db import database


@bot.ipc.route()
def process(data):
    """Level pages (one or more folders deep)."""
    def search_and_add_to_db(table, level, rank=''):
        """Search if level was yet not completed or secret yet not found.
        If true, add user and datetime of completion to respective table."""
        cursor.execute("SELECT username FROM " + table + " "
                "WHERE username = %s AND level_id = %s",
                (session['user']['username'], level,))
        found = cursor.fetchone()
        if not found:
            time = datetime.utcnow()
            aux = ", NULL)" if table == 'user_levelcompletion' else ")"
            cursor.execute("INSERT INTO " + table +
                    " VALUES (%s, %s, %s, %s" + aux,
                    (session['user']['username'], level, time,
                        session['user']['cur_page_count']))

            if table == 'user_levelcompletion':
                # Update global user completion count
                cursor.execute("UPDATE levels "
                        "SET completion_count = completion_count + 1 "
                        "WHERE id = %s", (level,))

                # Update user and country scores
                points = level_ranks[rank][0]
                cursor.execute("UPDATE accounts "
                        "SET score = score + %s WHERE username = %s",
                        (points, session['user']['username']))
                cursor.execute("UPDATE countries "
                        "SET total_score = total_score + %s "
                        "WHERE alpha_2 = %s",
                        (points, session['user']['country']))

                if not 'Status' in level:
                    # Update current_level count and reset user's page count
                    nonlocal current_level
                    current_level = "%02d" % (int(level) + 1)
                    cursor.execute("UPDATE accounts "
                            "SET current_level = %s, cur_page_count = 0 "
                            "WHERE username = %s",
                            (current_level, session['user']['username']))
                    session['user']['current_level'] = current_level
                    session['user']['cur_page_count'] = 0

                    # Update countries table too
                    cursor.execute("UPDATE countries "
                            "SET highest_level = GREATEST(highest_level, %s) "
                            "WHERE alpha_2 = %s",
                            (current_level, session['user']['country']))
                    if int(current_level) > get_level_count()[0]:
                        cursor.execute("UPDATE countries "
                                "SET winners_count = winners_count + 1 "
                                "WHERE alpha_2 = %s",
                                (session['user']['country'],))

    def has_access():
        """Check if user can access level_id,
                having reached current_level so far."""
        # Admins can access everything!
        if session['user']['rank'] == 'Site Administrator':
            return True

        if "Status" in level_id:
            # Secret level, check previous id in respective table
            cursor = get_cursor()
            cursor.execute("SELECT * FROM user_secretsfound "
                    "WHERE level_id = %s", (level_id,))
            secret_found = cursor.fetchone()
            return secret_found

        # Return if level is *at most* the current_level
        return int(level_id) <= int(current_level)

    # Increment user current page count (if it's an .htm one)
    path = data.path
    is_htm = path[-4:] == '.htm'
    if is_htm:
        cursor.execute("UPDATE accounts "
                "SET cur_page_count = cur_page_count + 1 "
                "WHERE username = %s", (session['user']['username'],))
        mysql.connection.commit()
        session['user']['cur_page_count'] += 1

    # Get user's current reached level and requested level number
    current_level = session['user']['current_level']
    cursor.execute("SELECT * FROM level_pages WHERE path = %s", (path,))
    page = cursor.fetchone()
    if not page:
        # Page not found!
        abort(404)
    level_id = page["level_id"]

    if htm:
        # Get user's current level info from DB
        cursor.execute("SELECT * FROM levels WHERE id = %s",
                (current_level,))
        level = cursor.fetchone()

        # If user entered a correct and new answer, register time on DB
        total, _ = get_level_count()
        if int(current_level) <= total and path == level["answer"]:
            search_and_add_to_db("user_levelcompletion",
                    current_level, level['rank'])

            # Create unique filename with user/level for Discord use
            discord_tag = session['user']['discord_tag']
            filename = "%s-%s" % (discord_tag, level['id'])
            #os.mknod("tmp/" + filename)

        else:
            # Check if a secret level has been found
            cursor.execute("SELECT * FROM levels "
                    "WHERE SUBSTR(id, 1, 6) = 'Status' AND "
                    "path = %s", (path,))
            secret = cursor.fetchone()
            if secret:
                search_and_add_to_db('user_secretsfound', secret['id'])
            else:
                # Otherwise, check if a secret level has been beaten
                cursor.execute("SELECT * FROM levels "
                        "WHERE SUBSTR(id, 1, 6) = 'Status' AND "
                        "answer = %s", (path,))
                secret = cursor.fetchone()
                if secret:
                    search_and_add_to_db('user_levelcompletion',
                            secret['id'], secret['rank'])

    if not has_access():
        # Forbid user from accessing any level further than permitted
        abort(403)

    # Register into database new page access (if applicable)
    tnow = datetime.utcnow()
    cursor.execute("INSERT IGNORE INTO user_pageaccess VALUES (%s, %s, %s, %s)",
            (session['user']['username'], level_id, path, tnow))

    # If it's an achievement page, add it to user's collection
    cursor.execute("SELECT * FROM achievements "
            "WHERE path = %s", (path,))
    cheevo = cursor.fetchone()
    if cheevo:
        cursor.execute("SELECT username from user_achievements "
                "WHERE username = %s and title = %s",
                (session['user']['username'], cheevo['title']))
        has_cheevo = (cursor.fetchone() is not None)
        if not has_cheevo:
            cursor.execute("INSERT INTO user_achievements VALUES (%s, %s)",
                    (session['user']['username'], cheevo['title']))
            # Update user and country score
            points = cheevo['points']
            cursor.execute("UPDATE accounts "
                    "SET score = score + %s WHERE username = %s",
                    (points, session['user']['username']))
            cursor.execute("UPDATE countries "
                    "SET total_score = total_score + %s "
                    "WHERE alpha_2 = %s",
                    (points, session['user']['country']))


    # Commit changes to DB
    mysql.connection.commit()

    # If the level page is indeed a .htm, render its template
    if htm:
        path = "levels/" + path
        return render_and_count(path, {})


@bot.ipc.route()
async def unlock(data):
    '''Unlock channels and/or roles in case path corresponds
    to a level front page or secret answer.'''

    # Get guild and member object from player's id
    riddle = riddles[data.alias]
    guild = riddle.guild
    member = get(guild.members, id=data.player_id)
    if not member:
        # Not currently a member
        return

    # Get guild member object from player and their current level
    current_level = ''
    for role in member.roles:
        if 'reached-' in role.name:
            aux = role.name.strip('reached-')
            if aux not in riddle.secret_levels:
                current_level = aux
                break
    
    # Find if the path corresponds to a level front page or secret answer
    print(data.path)
    for id, level in riddle.levels.items():
        if level['path'] == data.path:
            await advance(riddle, member, id, current_level)
            return
    for id, level in riddle.secret_levels.items():
        if level['path'] == data.path:
            await advance(riddle, member, id, current_level)
            return
        elif level['answer_path'] == data.path:
            await solve(riddle, member, level)


async def advance(riddle: Riddle, member: Member, id: str, current_level: str):
    '''Advance to further level when player arrives at a level front page.
    "reached" role is granted to user and thus given access to channel(s).'''

    # Avoid backtracking if level has already been unlocked
    ok = False
    for level in riddle.levels:
        if level == current_level:
            ok = True
        elif level == id:
            if not ok:
                return
            else:
                break

    # Get channel and roles corresponding to level
    guild = riddle.guild
    channel = get(guild.channels, name=id)
    role = None
    if id in riddle.levels:
        name = 'reached-' + current_level
        role = get(channel.changed_roles, name=name)
    elif id in riddle.secret_levels:
        name = 'reached-' + id
        role = get(member.roles, name=name)
        if not role:
            # For secret levels, solved implies reached too
            name = 'solved-' + id
            role = get(member.roles, name=name)
    if role:
        # User already unlocked that channel
        return

    # If a normal level, remove old "reached" roles from user
    if id in riddle.levels:
        for role in member.roles:
            if 'reached-' in role.name:
                old_level = role.name.strip('reached-')
                if old_level in riddle.levels:
                    await member.remove_roles(role)
                    break

    # Add "reached" role to member
    name = 'reached-' + id
    role = get(guild.roles, name=name)
    await member.add_roles(role)

    # If a normal level, change nickname to current level
    if id in riddle.levels:
        s = '[' + id + ']'
        await update_nickname(member, s)

    # Log unlocking procedure and send message to member
    print('> [%s] %s#%s unlocked channel #%s' \
            % (guild.name, member.name, member.discriminator, id))
    text = '**[%s]** You successfully unlocked channel **#%s**!\n' \
            % (guild.name, id)
    if id in riddle.levels:
        text += 'Your nickname is now **%s**.' % member.nick
    else:
        text += 'Your nickname is unchanged.'
    await member.send(text)


async def solve(riddle: Riddle, member: Member, level: dict):
    '''Grant "solved" role upon completion of a level (like a secret one).'''

    # Check if member already solved level
    guild = riddle.guild
    id = level['level_id']
    name = 'solved-' + id
    solved = get(guild.roles, name=name)
    if solved in member.roles:
        return

    # Deny solve if member didn't arrive at the level proper yet
    name = 'reached-' + id
    reached = get(member.roles, name=name)
    if not reached:
        print('> [%s] [WARNING] %s#%s tried to solve ' \
                'secret level "%s" without reaching it' \
                % (guild.name, member.name, member.discriminator, id))
        return
    
    # Remove old "reached" role and add "solved" role to member
    await member.remove_roles(reached)
    await member.add_roles(solved)

    # Log solving procedure and send message to member
    print('> [%s] %s#%s completed secret level "%s"' \
            % (guild.name, member.name, member.discriminator, id))
    text = '**[%s]** You successfully solved secret level **%s**!\n' \
            % (guild.name, id)
    await member.send(text)


@bot.command()
async def finish(ctx):
    # Only allow finishing by PM to bot
    message = ctx.message
    author = message.author
    if message.guild and not message.channel.name == 'command-test':
        # Purge all traces of wrong message >:)
        await message.delete()
        text = '`!finish` must be sent by PM to me!'
        await author.send(text)
        return

    aux = message.content.split()[1:]
    text = ''
    if len(aux) != 2:
        # Command usage
        text = '> `!finish`: Finish game ||(for now?)|| (PM ONLY!)\n' \
                '> \n' \
                '> • Usage: `!finish guild_alias final_answer`\n' \
                '> `guild_alias`: the alias of riddle\'s guild/server\n' \
                '> `final_answer`: the final level\'s answer\n'
    else:
        alias, answer = aux
        if not alias in riddles:
            # Invalid alias
            text = 'Inserted alias doesn\'t match any valid guild!\n'
        else:
            riddle = riddles[alias]
            guild = riddle.guild
            member = get(guild.members, id=author.id)
            if not member:
                # Not currently a member
                text = 'You aren\'t currently a member ' \
                        'of the _%s_ guild.\n' % guild.name
            else :
                # Check if player unlocked final level before trying to finish
                final_level = next(reversed(riddle.levels))
                name = 'reached-%s' % final_level
                final_role = get(member.roles, name=name)
                if not final_role:
                    text = 'You need to `!unlock` the final level first. :)'
                else:
                    # Check if inputted answer matches correct one (by hash)
                    match = bcrypt.checkpw(answer.encode('utf-8'),
                            riddle.final_answer_hash) 

                    if match:
                        # Player completed the game (for now?)
                        text = 'Congrats!'

                        # Swap last level's "reached" role for "winners" role
                        await member.remove_roles(final_role)
                        winners = get(guild.roles, name='winners')
                        await member.add_roles(winners)

                        # Update nickname with winner's badge
                        s = riddle.winner_suffix
                        await update_nickname(member, s)

                    else:
                        # Player got answer "wrong"
                        text = 'Please, go back and finish the final level...'
    
    await message.channel.send(text)


async def update_nickname(member: Member, s: str):
    '''Update user's nickname to reflect current level.
    In case it exceeds 32 characters, shorten the member's name to fit.'''
    name = member.name
    total = len(name) + 1 + len(s)
    if total > 32:
        excess = total - 32
        name = name[:(-(excess + 5))] + '(...)'
    nick = name + ' ' + s
    await member.edit(nick=nick)
