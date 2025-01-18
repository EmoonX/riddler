import csv
import json
from typing import Self

from quart import Blueprint

from inject import get_riddles
from levels import get_pages

export = Blueprint('players_export', __name__)


class Export:

    @classmethod
    async def build(cls) -> Self:
        self = cls()
        self.data = {}
        riddles = await get_riddles(unlisted=True)
        for riddle in riddles:
            pages = await get_pages(riddle['alias'], jsonize=False)
            self.data[riddle['alias']] = pages
        
        return self

    def to_json(self) -> str:

        def _get_paths(token: dict) -> list[tuple[str, str]]:
            if not 'children' in token:
                return [(token['access_time'], token['path'])]
            paths = []
            for child in token['children'].values():
                paths += _get_paths(child)
            return paths

        for alias, riddle in self.data.items():
            for level_name, level in riddle.items():
                paths = _get_paths(level['/'])
                level = []
                for access_time, path in sorted(paths):
                    level.append({
                        'path': path,
                        'access_time': access_time,
                    })
                riddle[level_name]['pages'] = level
                riddle[level_name] |= {
                    'pages_found': riddle[level_name]['/']['filesFound'],
                    'pages_total': riddle[level_name]['/']['filesTotal'],
                }
                del riddle[level_name]['/']

        return json.dumps(self.data, indent=2)


@export.route('/account/export-riddle-data')
async def export_user_riddle_data():
    return (await Export.build()).to_json()
