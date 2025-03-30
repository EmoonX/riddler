from datetime import datetime
import hashlib
import os
from pathlib import Path

from pymysql.err import IntegrityError

from util.db import database


class ArchivePage:

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
        base_path = self.path.replace('..', '(parent)')
        full_path = Path(f"../archive/{self.alias}{base_path}")
        if full_path.is_file():
            # If the currently archived file is indeed a different one,
            # rename it as hidden and concatenate its datetime
            with open(full_path, 'rb') as old_file:
                old_content = old_file.read()
                old_hash = hashlib.md5(old_content).hexdigest()
                if old_hash != self.content_hash:
                    old_mtime = (
                        datetime.fromtimestamp(full_path.stat().st_mtime)
                        .strftime("%Y-%m-%d")
                    )
                    renamed_filename = f".{full_path.name}-{old_mtime}"
                    renamed_path = f"{full_path.parent}/{renamed_filename}"
                    os.rename(full_path, renamed_path)

        # Recursively create directories (if needed) and save new archived file
        Path(full_path.parent).mkdir(parents=True, exist_ok=True)
        with open(full_path, 'wb') as file:
            file.write(self.content)
            tnow = datetime.utcnow()
            print(
                f"> \033[1m[{self.alias}]\033[0m "
                    f"Saved new content from \033[1;3m{self.path}\033[0m "
                    f"with hash \033[1m{self.content_hash}\033[0m "
                    f"({tnow})",
                flush=True
            )
