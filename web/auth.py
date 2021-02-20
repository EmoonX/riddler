import os

from quart import Quart, Blueprint, request, session, \
        render_template, redirect, url_for
from quart_discord import DiscordOAuth2Session
from quart.sessions import SecureCookieSessionInterface

from util.db import database

# Discord OAuth2 sessionz
discord: DiscordOAuth2Session

# Interface for storing Quart session cookie
session_cookie: SecureCookieSessionInterface

# Create app blueprint
auth = Blueprint('players_auth', __name__)


def discord_session_init(app: Quart):
    '''Configure and create Discord OAuth2 object.'''
    
    # Discord OAuth2 configs
    app.config['DISCORD_CLIENT_ID'] = 803127673165053993
    app.config['DISCORD_CLIENT_SECRET'] = os.getenv('DISCORD_CLIENT_SECRET')
    app.config['DISCORD_REDIRECT_URI'] = \
            'https://riddler.emoon.dev/callback/'
    app.config['DISCORD_BOT_TOKEN'] = os.getenv('DISCORD_TOKEN')

    # Create session object
    global discord
    discord = DiscordOAuth2Session(app)

    # Create session cookie
    global session_cookie
    session_cookie = \
            SecureCookieSessionInterface().get_signing_serializer(app)


@auth.route('/register/', methods=['GET', 'POST'])
async def register():
    '''Register new account on database based on Discord auth.'''
    
    # Render registration page on GET
    user = await discord.fetch_user()
    if request.method == 'GET':
        return await render_template('players/register.htm', user=user)
    
    # Insert value on accounts table
    form = await request.form
    query = 'INSERT INTO accounts ' \
            '(username, discriminator, country) ' \
            'VALUES (:name, :disc, :country)'
    values = {'name': user.name, 'disc': user.discriminator,
            'country': form['country']}
    await database.execute(query, values)

    # Redirect to post-registration page
    return redirect(url_for('account.settings',
            msg='Registration successful!'))


@auth.route('/login/', methods=['GET'])
async def login():
    '''Create Discord session and redirect to callback URL.'''
    scope = ['identify', 'guilds']
    return await discord.create_session(scope=scope)


@auth.route('/callback/')
async def callback():
    '''Callback for OAuth2 authentication.'''

    # Execute the callback
    await discord.callback()

    # If user doesn't have an account on database, do registration
    user = await discord.fetch_user()
    query = 'SELECT * FROM accounts ' \
            'WHERE username = :name AND discriminator = :disc'
    values= {'name': user.name, 'disc': user.discriminator}
    found = await database.fetch_one(query, values)
    if not found:
        return redirect(url_for('.register'))
    
    # Save account database info on session dict
    query = 'SELECT * FROM accounts ' \
            'WHERE username = :name AND discriminator = :disc'
    values = {'name': user.name, 'disc': user.discriminator}
    result = await database.fetch_one(query, values)
    session['country'] = result['country']

    # Otherwise, redirect to post-login page
    return redirect(url_for('account.settings',
            msg='Successful login!'))


@auth.route('/logout/')
async def logout():
    '''Revoke credentials and logs user out of application.'''

    # Discord credentials are gone
    discord.revoke()

    # Get rid of session data
    if 'user' in session:
        session.pop('user')

    # Return something
    return 'Logged out. :('
