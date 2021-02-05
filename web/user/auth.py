import os

from quart import Blueprint, Quart
from quart_discord import DiscordOAuth2Session

# !! Only in development environment.
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = 'true'

# Create app blueprint
user_auth = Blueprint('user_auth', __name__)

# Discord OAuth2 session
discord: DiscordOAuth2Session


def discord_session_init(app: Quart):
    '''Configure and create Discord OAuth2 object.'''
    # Discord OAuth2 configs
    app.config['DISCORD_CLIENT_ID'] = 803127673165053993
    app.config['DISCORD_CLIENT_SECRET'] = os.getenv('DISCORD_CLIENT_SECRET')
    app.config['DISCORD_REDIRECT_URI'] = \
            'https://riddler.emoon.dev/callback/'
    app.config['DISCORD_BOT_TOKEN'] = os.getenv('DISCORD_BOT_TOKEN')

    # Create session object
    global discord
    discord = DiscordOAuth2Session(app)


@user_auth.route('/login/', methods=['GET'])
async def login():
    '''Create Discord session and redirect to callback URL.'''
    return await discord.create_session(scope=['identify'])


@user_auth.route('/callback/')
async def callback():
    '''Callback for OAuth2 authentication.'''
    await discord.callback()
    user = await discord.fetch_user()
    return 'Hello %s!<br>Here\'s your user info: %s' \
            % (user.name, user)


@user_auth.route('/logout/')
async def logout():
    '''Revokes credentials and logs user out of application.'''
    discord.revoke()
    return 'Logged out. :('
