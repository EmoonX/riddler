from collections import defaultdict
import os
from pathlib import Path
import shutil

from pymysql.err import IntegrityError
import requests

from credentials import get_path_credentials
from inject import get_riddle
from util.db import database

class LevelUpdater:
    '''Single level update handler.'''

    alias: str
    riddle: dict
    all_levels_by_name: dict[str, dict]
    all_levels_by_set: defaultdict[int, dict[int, dict]]

    @classmethod
    async def create(cls, alias: str) -> type:
        query = '''
            SELECT * FROM levels
            WHERE riddle = :riddle
            ORDER BY set_index, `index`
        '''
        values = {'riddle': alias}
        result = await database.fetch_all(query, values)
        riddle = await get_riddle(alias)
        all_levels_by_name = {level['name']: level for level in result}
        all_levels_by_set = defaultdict(dict) | {
            level['set_index']: {
                'index': level['set_index'],
                'name': level['level_set'],
                'levels': {level['index']: level},
            }
            for level in result
        }

        class _LevelUpdater(cls):
            alias: str = alias
            riddle: dict = riddle
            all_levels_by_name: dict[str, dict] = all_levels_by_name
            all_levels_by_set: defaultdict[int, dict[int, dict]] = all_levels_by_set

        return _LevelUpdater

    def __init__(self, level_name: str, set_name: str, pages: list[str]):
        self.level_name = level_name
        self.level = self.all_levels_by_name.get(level_name)
        self.set_name = set_name
        self.level_set = next(
            (
                idx for idx in self.all_levels_by_set
                if self.all_levels_by_set[idx]['name'] == set_name
            ),
            None,
        )
        self.pages = pages

    async def process_level(self):
        '''Process level data.'''

        if not self.level:
            # New level (and possibly new level set)
            if not self.level_set:
                self._add_new_level_set()
                self._log(
                    'Created new level set '
                    f"\033[1m{self.level_set['name']}\033[0m."
                )
            self._add_new_level()
            self._log(
                f"Added level \033[1m{self.level['name']}\033[0m "
                'to the database.'
            )
        else:
            self._log(
                f"Level \033[1m{self.level['name']}\033[0m "
                'already in the database…'
            )

        set_index, index = self.level_set['index'], self.level['index']
        self.all_levels_by_set[set_index][index] = self.level
        if previous_level := self.all_levels_by_set[set_index].get(index - 1):
            if self.pages:
                # If absent, automatically set previous level's answer
                # as the current one's front path
                query = '''
                    UPDATE levels
                    SET answer = :answer
                    WHERE riddle = :riddle AND name = :name AND answer is NULL
                '''
                values = {
                    'riddle': self.alias,
                    'name': previous_level['name'],
                    'answer': self.pages[0],
                }
                await database.execute(query, values)

            await self._add_requirement(previous_level['name'])

    async def _add_new_level_set(self):
        query = '''
            INSERT INTO level_sets
                (riddle, index, name)
            VALUES (:riddle, :index, :name)
        '''
        values = {
            'riddle': self.alias,
            'index': max(idx for idx in self.all_levels_by_set if idx < 99),
            'name': self.set_name,
        }
        await database.execute(query, values)
        self.level_set = values | {'levels': {}}

    async def _add_new_level(self):
        query = '''
            INSERT INTO levels (
                riddle, level_set, set_index, `index`, name,
                `path`, image, discord_category, discord_name
            ) VALUES (
                :riddle, :level_set, :set_index, :index, :name,
                :path, :image, :discord_category, :discord_name
            )
        '''
        values = {
            'riddle': self.alias,
            'set_index': self.level_set['index'],
            'level_set': self.set_name,
            'index': len(self.level_set['levels']) + 1,
            'name': self.level_name,
            'path': self.pages[0] if self.pages else None,
            'discord_category': self.set_name,
            'discord_name': self.level_name.lower().replace(' ', '-'),
        }
        await database.execute(query, values)
        self.level = values

    async def _add_requirement(self, requires: str):
        '''Add requirement DB entry for level.'''
        query = '''
            INSERT IGNORE INTO level_requirements
                (riddle, level_name, requires)
            VALUES (:riddle, :level_name, :requires)
        '''
        values = {
            'riddle': self.alias,
            'level_name': self.level['name'],
            'requires': requires,
        }
        await database.execute(query, values)

    async def process_image(self, image_path: str) -> str | None:
        '''Fetch image content from riddle website and update related info.'''

        # Send HTTP request to retrieve image file
        image_url = f"{self.riddle['root_path']}{image_path}"
        credentials = await get_path_credentials(self.alias, image_path)
        if username := credentials['username']:
            password = credentials['password']
            image_url = image_url.replace('://', f"://{username}:{password}@")
        print(
            f"> \033[1m[{self.alias}]\033[0m "
            f"Fetching level image from \033[3m{image_url}\033[0m… ",
            end=''
        )
        res = requests.get(image_url, stream=True, timeout=10)
        print(f"\033[1m{'OK' if res.ok else res.status_code}\033[0m")

        if res.ok:
            # Image found and retrieved, so save it
            image_filename = os.path.basename(image_path)
            image_dir = f"../static/thumbs/{self.alias}"
            save_path = f"{image_dir}/{image_filename}"
            Path(image_dir).mkdir(parents=True, exist_ok=True)
            with open(save_path, 'wb') as image:
                shutil.copyfileobj(res.raw, image)

            # Add or update image's filename
            query = '''
                UPDATE levels
                SET image = :image
                WHERE riddle = :riddle AND name = :name
            '''
            values = {
                'riddle': self.alias,
                'name': self.level['name'],
                'image': image_filename,
            }
            await database.execute(query, values)

            return image_filename

        return None

    async def process_page(self, path: str):
        '''Insert/update page in DB, possibly attached to a level.'''

        query = '''
            INSERT INTO level_pages
                (`riddle`, `path`, `level_name`)
            VALUES (:riddle, :path, :level_name)
        '''
        values = {
            'riddle': self.alias,
            'path': path,
            'level_name': self.level['name'],
        }
        if await database.execute(query, values):
            # Page added as part of the level
            self._log(
                f"Added page \033[3m{path}\033[0m "
                f"({self.level['name']}) " if self.level else ''
                'to the database!'
            )
        else:
            # Page already present, update level if suitable
            if self.level:
                query = '''
                    UPDATE level_pages
                    SET level_name = :level_name
                    WHERE riddle = :riddle AND path = :path
                '''
                if await database.execute(query, values):
                    self._log(
                        f"Updated level "
                        f"for page \033[3m{path}\033[0m ({self.level['name']})…"
                    )
                    return
            self._log(
                f"Skipping page \033[3m{path}\033[0m ({self.level['name']})…"
            )

    @classmethod
    def _log(cls, msg: str, end: str = '\n'):
        '''Log message.'''
        print(f"> \033[1m[{cls.alias}]\033[0m {msg}", end=end, flush=True)


def _is_image(path: str) -> bool:
    '''Check if path points to an image file.'''
    _, ext = os.path.splitext(path)
    return ext.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
