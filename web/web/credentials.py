from datetime import datetime
import os

from pymysql.err import IntegrityError
import requests
from requests.auth import HTTPBasicAuth

from auth import discord
from util.db import database


async def process_credentials(
    riddle: dict, path: str, credentials: dict[str, str]
) -> bool:

    alias = riddle['alias']
    username = credentials['username']
    password = credentials['password']
    user = await discord.get_user()
    tnow = datetime.utcnow()

    def _log_received_credentials(folder_path: str, success: bool):
        escape_code = 1 if success else 9
        print(
            f"\033[1m[{alias}]\033[0m "
            f"Received credentials "
            f"\033[3m\033[{escape_code}m{username}:{password}\033[0m\033[0m "
            f"for \033[1m{folder_path}\033[0m "
            f"from \033[1m{user.name}\033[0m "
            f"({tnow})"
        )

    url = f"{riddle['root_path']}{path}"
    res = requests.get(url)
    if res.ok:
        # False alarm, path isn't protected at all
        return True

    folder_path = os.path.dirname(path)
    res = requests.get(url, auth=HTTPBasicAuth(username, password))
    if res.status_code == 401:
        # Wrong credentials received
        _log_received_credentials(folder_path, success=False)
        return False
    
    # Correct credentials for uncatalogued folder; record them
    await _record_new_credentials(alias, folder_path, username, password)

    # Catalogued folder and correct credentials,
    # so create user record if not there yet
    query = '''
        INSERT IGNORE INTO user_credentials (
            riddle, username, folder_path, access_time
        ) VALUES (
            :riddle, :username, :folder_path, :access_time
        )
    '''
    values = {
        'riddle': alias,
        'username': user.name,
        'folder_path': folder_path,
        'access_time': tnow,
    }
    await database.execute(query, values)
    _log_received_credentials(folder_path, success=True)

    return True


async def _record_new_credentials(
    alias: str, folder_path: str, username: str, password: str
):

    query = '''
        INSERT INTO found_credentials (
            riddle, folder_path, cred_username, cred_password,
            acc_username, access_time
        ) VALUES (
            :riddle, :folder_path, :cred_username, :cred_password,
            :acc_username, :access_time
        )
    '''
    values = {
        'riddle': alias,
        'folder_path': folder_path,
        'cred_username': username,
        'cred_password': password,
        'acc_username': (await discord.get_user()).name,
        'access_time': datetime.utcnow(),
    }
    try:
        await database.execute(query, values)
    except IntegrityError as e:
        return
    else:
        user = await discord.get_user()
        tnow = datetime.utcnow()
        print(
            f"> \033[1m[{alias}]\033[0m "
            f"Found new credentials \033[1m{username}:{password}\033[0m "
            f"for \033[1;3m{folder_path}\033[0m "
            f"by \033[1m{user.name}\033[0m "
            f"({tnow})"
        )

    # Register credentials as new ones
    query = '''
        INSERT IGNORE INTO riddle_credentials (
            riddle, folder_path, username, password
        ) VALUES (
            :riddle, :folder_path, :username, :password
        )
    '''
    values = {
        'riddle': alias,
        'folder_path': folder_path,
        'username': username,
        'password': password,
    }
    await database.execute(query, values)
