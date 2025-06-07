import os
from pathlib import Path
import shutil

import requests

from credentials import get_path_credentials
from inject import get_levels, get_riddle
from util.db import database

class LevelUpdater:
    '''Single level update handler.'''

    alias: str
    riddle: dict
    all_levels_by_set: dict[int, dict[int, dict]]
    current_set: dict | None

    @classmethod
    async def create(cls, alias: str) -> type:
        '''Factory method for creating a riddle-aware updater.'''

        # Build multi-level dict of indexed sets and levels
        all_levels = await get_levels(alias)
        all_levels_by_set = {}
        for level in all_levels.values():
            set_index = level['set_index']
            if not (level_set := all_levels_by_set.get(set_index)):
                level_set = all_levels_by_set[set_index] = {
                    'index': set_index,
                    'name': level['level_set'],
                    'levels': {},
                }
            level_set['levels'] |= {level['index']: level}

        class RiddleLevelUpdater(
            cls,
            alias=alias,
            riddle=(await get_riddle(alias)),
            all_levels_by_set=all_levels_by_set,
            current_set=None,
        ):
            '''Riddle-wise level update handler.'''

        return RiddleLevelUpdater

    def __init_subclass__(cls, **attrs):
        '''Set keyword arguments as subclass attributes.'''
        for name, value in attrs.items():
            setattr(cls, name, value)

    def __init__(
        self, level_name: str | None, set_name: str | None, paths: list[str],
    ):
        if (cls := self.__class__) == LevelUpdater:
            # Do not allow base class initialization
            raise NotImplementedError

        if not level_name:
            # Levelless update
            self.level = self.level_set = None
            return

        self._retrieve_level_and_set(level_name, set_name)

        if not self.level and not cls.current_set and not set_name:
            # Missing set name for _new AND topmost_ level entry
            raise TypeError(
                f"[{cls.alias}] missing set for new level '{level_name}'"
            )
        if self.level and set_name and self.level['level_set'] != set_name:
            # Wrong (and superfluously supplied) set name for an existing level
            raise ValueError(
                f"[{cls.alias}] "
                f"mismatching sets for existing level '{level_name}': "
                f"'{self.level['level_set']}' (current) and '{set_name}' (given)"
            )

        self._level_name = level_name
        self._set_name = set_name or self.level_set['name']
        self.paths = paths

    def _retrieve_level_and_set(self, level_name: str, set_name: str):
        '''Search for and retrieve (possibly existing) level and/or level set.'''
        self.level = None
        self.level_set = self.__class__.current_set if not set_name else None
        for level_set in self.all_levels_by_set.values():
            for level in level_set['levels'].values():
                if level['name'] == level_name:
                    self.level = level
                    self.level_set = level_set
                    return
            if level_set['name'] == set_name:
                self.level_set = level_set

    async def process_level(self):
        '''Process level data.'''

        if not self.level:
            if not self.level_set:
                self.log(
                    f"Creating new level set \033[1m{self._set_name}\033[0m…"
                )
                await self._add_new_level_set()
            self.log(
                f"Adding level \033[1m{self._level_name}\033[0m to the database…"
            )
            await self._add_new_level()
        else:
            self.log(
                f"Level \033[1m{self._level_name}\033[0m found in the database."
            )

        if previous_level := self._get_previous_level():
            await self._add_requirement(previous_level)
            if not previous_level['answer'] and self.paths:
                await self._update_previous_answer(previous_level)

        # Update riddle-wise set tracker
        self.__class__.current_set = self.level_set

    async def _add_new_level_set(self):
        '''Add new entry to level set entry.'''
        set_index = max(idx for idx in self.all_levels_by_set if idx < 99) + 1
        query = '''
            INSERT INTO level_sets
                (riddle, `index`, name)
            VALUES (:riddle, :index, :name)
        '''
        values = {
            'riddle': self.alias,
            'index': set_index,
            'name': self._set_name,
        }
        await database.execute(query, values)        
        self.level_set = values | {'levels': {}}
        self.__class__.all_levels_by_set[set_index] = self.level_set

    async def _add_new_level(self):
        '''Add new level entry.'''
        index = max(self.level_set['levels'].keys(), default=0) + 1
        query = '''
            INSERT INTO levels (
                riddle, level_set, set_index, `index`, name,
                path, discord_category, discord_name
            ) VALUES (
                :riddle, :level_set, :set_index, :index, :name,
                :path, :discord_category, :discord_name
            )
        '''
        values = {
            'riddle': self.alias,
            'set_index': self.level_set['index'],
            'level_set': self._set_name,
            'index': index,
            'name': self._level_name,
            'path': self.paths[0] if self.paths else None,
            'discord_category': self._set_name,
            'discord_name': self._level_name.lower().replace(' ', '-'),
        }
        await database.execute(query, values)
        self.level_set['levels'][index] = self.level = values

    async def _add_requirement(self, required_level: dict):
        '''Add single requirement entry for level.'''

        query = '''
            SELECT 1 FROM level_requirements
            WHERE riddle = :riddle AND level_name = :level_name
        '''
        values = {'riddle': self.alias, 'level_name': self.level['name']}
        if await database.fetch_val(query, values):
            # Do not add further requirements if one is already present
            return

        query = '''
            INSERT INTO level_requirements
                (riddle, level_name, requires)
            VALUES (:riddle, :level_name, :requires)
        '''
        values |= {'requires': required_level['name']}
        await database.execute(query, values)

    def _get_previous_level(self) -> dict | None:
        '''Get level before the current one in the set_index/index ordering,'''

        previous_index = self.level['index'] - 1
        if previous_in_set := self.level_set.get(previous_index):
            return previous_in_set

        previous_set_index = self.level['set_index'] - 1
        if previous_set := self.all_levels_by_set.get(previous_set_index):
            levels = previous_set['levels']
            last_in_previous_set = levels[max(levels.keys())]
            return last_in_previous_set

        return None

    async def _update_previous_answer(self, previous_level: dict):
        '''Set previous level's answer as the current one's front path.'''
        query = '''
            UPDATE levels
            SET answer = :answer
            WHERE riddle = :riddle AND name = :name
        '''
        values = {
            'riddle': self.alias,
            'name': previous_level['name'],
            'answer': self.paths[0],
        }
        await database.execute(query, values)
        previous_level['answer'] = self.paths[0]

    async def process_image(self, image_path: str) -> str | None:
        '''Fetch image content from riddle website and update related info.'''

        # Send HTTP request to retrieve image file
        image_url = f"{self.riddle['root_path']}{image_path}"
        credentials = await get_path_credentials(self.alias, image_path)
        username = credentials['username']
        password = credentials['password']
        if username or password:
            image_url = image_url.replace(
                '://', f"://{username or ''}:{password or ''}@"
            )
        self.log(
            f"Fetching level image from \033[3;4m{image_url}\033[0m... ", end=''
        )
        res = requests.get(image_url, stream=True, timeout=10)
        print(f"\033[1m{'OK' if res.ok else res.status_code}\033[0m", flush=True)

        if not res.ok:
            # Couldn't retrieve image from external host
            return None

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

    async def process_page(self, path: str):
        '''Insert/update page in(to) DB, possibly attached to a level.'''

        # Insert page entry if indeed new
        query = '''
            INSERT IGNORE INTO level_pages
                (`riddle`, `path`, `level_name`)
            VALUES (:riddle, :path, :level_name)
        '''
        values = {
            'riddle': self.alias,
            'path': path,
            'level_name': self.level['name'] if self.level else None,
        }
        if await database.execute(query, values):
            self.log(
                f"Added new page \033[3m{path}\033[0m "
                + (f"({self.level['name']}) " if self.level else '')
                + 'to the database'
            )
            return

        # Page entry already present, update level if suitable
        query = '''
            UPDATE level_pages
            SET level_name = :level_name
            WHERE riddle = :riddle AND path = :path
        '''
        if await database.execute(query, values):
            if self.level:
                self.log(
                    f"Updated level "
                    f"for page \033[3m{path}\033[0m ({self.level['name']})"
                )
            else:
                self.log(f"Delisted page \033[3m{path}\033[0m")
            return

        self.log(
            f"Skipping page \033[3m{path}\033[0m"
            + (f" ({self.level['name']})" if self.level else '')
        )

    @classmethod
    def log(cls, msg: str, end: str = '\n'):
        '''Log message.'''
        print(f"> \033[1m[{cls.alias}]\033[0m {msg}", end=end, flush=True)
