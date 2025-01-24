from datetime import datetime
import hashlib
import os
from pathlib import Path

from pymysql.err import IntegrityError

from util.db import database


class PageBackup:

    def __init__(self, alias: str, path: str, content: bytes):
        self.alias = alias
        self.path = path
        self.content = content
        self.content_hash = hashlib.md5(content).hexdigest()

    async def record_hash(self) -> bool:
        query = '''
            INSERT INTO _page_hashes
                (riddle, path, content_hash)
            VALUES (:riddle, :path, :content_hash)
        '''
        values = {
            'riddle': self.alias,
            'path': self.path,
            'content_hash': self.content_hash,
        }
        try:
            await database.execute(query, values)
        except IntegrityError:
            return False

        return True

    def save(self):
        full_path = f"../backup/{self.alias}{self.path}"
        dir_path = os.path.dirname(full_path)
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        with open(full_path, 'wb') as file:
            file.write(self.content)
            tnow = datetime.utcnow()
            print(
                f"> \033[1m[{self.alias}]\033[0m "
                f"Saved new page with hash \033[1m{self.content_hash}\033[0m "
                f"for path \033[1;3m{self.path}\033[0m "
                f"({tnow})",
                flush=True
            )
