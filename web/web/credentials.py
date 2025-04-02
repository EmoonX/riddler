from datetime import datetime
import os

from pymysql.err import IntegrityError
import requests
from requests.auth import HTTPBasicAuth

from auth import discord, User
from util.db import database


async def process_credentials(
    riddle: dict,
    path: str,
    credentials: tuple[str, str],
    status_code: int
) -> bool:

    alias = riddle['alias']
    username, password = credentials
    user = await discord.get_user()

    def _log_received_credentials(folder_path: str, success: bool):
        '''Log received credentials based on their correctness.'''

        if success and not username:
            # No credentials needed nor received
            return

        print(
            f"\033[1m[{alias}]\033[0m "
            + ((
                'Received correct credentials '
                f"\033[1m{username}:{password}\033[0m "
            ) if success else (
                'Received wrong credentials '
            )) +
            f"for \033[3m\033[1m{folder_path}\033[0m "
            f"from \033[1m{user.name}\033[0m "
            f"({datetime.utcnow()})"
        )

    if status_code == 401:
        # User (almost certainly) couldn't access page, so don't even bother
        # _log_received_credentials(os.path.dirname(path), success=False)
        return False

    path_credentials = await get_path_credentials(alias, path)
    if not path_credentials['username'] and credentials == ('', ''):
        # No credentials found, no credentials given and no 401 received,
        # so we assume unprotected folder to avoid frequent HTTP checks
        return True

    correct_credentials = (
        path_credentials['username'], path_credentials['password']
    )
    folder_path = path_credentials['folder_path']
    if credentials in [correct_credentials, ('', '')]:
        # Grant access if user has unlocked protected folder before
        if await has_unlocked_folder_credentials(alias, user, folder_path):
            return True

    if correct_credentials == ('???', '???'):
        username, password = ('???', '???')
    else:
        # Possibly new/different credentials, so HTTP-double-check them
        folder_path = path
        while folder_path:
            url = f"{riddle['root_path']}{os.path.dirname(folder_path)}"

            res = requests.get(url)
            if res.status_code != 401:
                if folder_path == path:
                    # Path isn't protected at all
                    return True
                break

            res = requests.get(url, auth=HTTPBasicAuth(username, password))
            if res.status_code == 401:
                if folder_path == path:
                    # Wrong user credentials
                    return False
                break

            folder_path = os.path.dirname(folder_path)
    
        # Correct credentials; possibly record them
        await _record_credentials(alias, folder_path, username, password)

    # Create new user record
    query = '''
        INSERT IGNORE INTO user_credentials
            (riddle, username, folder_path, unlock_time)
        VALUES (:riddle, :username, :folder_path, :unlock_time)
    '''
    values = {
        'riddle': alias,
        'username': user.name,
        'folder_path': folder_path,
        'unlock_time': datetime.utcnow(),
    }
    await database.execute(query, values)
    _log_received_credentials(folder_path, success=True)

    return True


async def _record_credentials(
    alias: str, folder_path: str, username: str, password: str
):

    user = await discord.get_user()
    query = '''
        INSERT INTO _found_credentials (
            riddle, folder_path, cred_username, cred_password,
            acc_username, unlock_time
        ) VALUES (
            :riddle, :folder_path, :cred_username, :cred_password,
            :acc_username, :unlock_time
        )
    '''
    values = {
        'riddle': alias,
        'folder_path': folder_path,
        'cred_username': username,
        'cred_password': password,
        'acc_username': user.name,
        'unlock_time': datetime.utcnow(),
    }
    try:
        await database.execute(query, values)
    except IntegrityError:
        return
    else:
        print(
            f"> \033[1m[{alias}]\033[0m "
            f"Found new credentials \033[1m{username}:{password}\033[0m "
            f"for \033[1;3m{folder_path}\033[0m "
            f"by \033[1m{user.name}\033[0m "
            f"({datetime.utcnow()})"
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


async def get_path_credentials(alias: str, path: str) -> dict[str, str]:

    query = '''
        SELECT * FROM riddle_credentials
        WHERE riddle = :riddle
    '''
    values = {'riddle': alias}
    result = await database.fetch_all(query, values)
    all_credentials = {row['folder_path']: row for row in result}

    parsed_path = path.split('/')
    while parsed_path:
        path = '/'.join(parsed_path)
        credentials = all_credentials.get(path)
        if credentials:
            # Credentials and innermost protect folder found
            return {
                'folder_path': path,
                'username': credentials['username'],
                'password': credentials['password'],
            }
        parsed_path.pop()

    # No credentials found at all
    return {
        'folder_path': '/',
        'username': '',
        'password': '',
    }


async def has_unlocked_folder_credentials(
    alias: str, user: User, folder_path: str
) -> bool:

    query = '''
        SELECT 1 FROM user_credentials
        WHERE riddle = :riddle
            AND username = :username
            AND folder_path = :folder_path
    '''
    values = {
        'riddle': alias,
        'username': user.name,
        'folder_path': folder_path,
    }
    has_user_unlocked = await database.fetch_val(query, values)
    return has_user_unlocked


async def get_all_unlocked_credentials(
    alias: str, user: User
) -> dict[str, dict]:

    query = '''
        SELECT rc.folder_path, rc.username, rc.password
        FROM riddle_credentials rc INNER JOIN user_credentials uc
            ON rc.riddle = uc.riddle AND rc.folder_path = uc.folder_path
        WHERE rc.riddle = :riddle AND uc.username LIKE :username
    '''
    values = {
        'riddle': alias,
        'username': user.name if user else '%',
    }
    result = await database.fetch_all(query, values)
    credentials = {
        row['folder_path']: {
            'username': row['username'],
            'password': row['password'],
        }
        for row in result
    }
    return credentials

