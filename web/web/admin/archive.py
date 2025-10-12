from datetime import datetime
import hashlib
import os
from pathlib import Path
from typing import overload, Self

from util.db import database


class ArchivedPage:

    @classmethod
    async def get_latest_snapshot(cls, alias: str, path: str) -> Self | None:
        '''Retrieve latest archived page snapshot, based on retrieval time.'''
        query = '''
            SELECT * FROM _page_hashes
            WHERE riddle = :riddle AND path = :path
            ORDER BY retrieval_time DESC
            LIMIT 1
        '''
        values = {'riddle': alias, 'path': path}
        latest_snapshot = await database.fetch_one(query, values)
        if not latest_snapshot:
            return None        
        return cls(alias, path, content_hash=latest_snapshot['content_hash'])

    @overload
    def __init__(self, alias: str, path: str, content: bytes):
        ...

    @overload
    def __init__(self, alias: str, path: str, content_hash: str):
        ...

    def __init__(
        self,
        alias: str,
        path: str,
        content: bytes | None = None,
        content_hash: str | None = None,
    ):
        self.alias = alias
        self.path = Path(path)
        self.local_path = self._get_local_path()
        if content is not None:
            self.content = content
            self.content_hash = hashlib.md5(content).hexdigest()
        elif content_hash:
            self.content = self._read_local_file()
            self.content_hash = content_hash
            self.retrieval_time = self._get_local_mtime()
        else:
            raise TypeError

    def _get_local_path(self) -> Path:
        '''Ǵet full sanitized path to the (currently or to-be) archived page.'''
        base_path = Path(str(self.path).replace('..', '(parent)'))
        if not base_path.suffix:
            if base_path == Path('/'):
                base_path = Path('/(root)')
            base_path = base_path.with_suffix('.page')
        return Path(f"../archive/{self.alias}{base_path}")

    async def record_hash(self) -> bool:
        '''Record possibly new content hash, return whether successful.'''

        query = '''
            SELECT retrieval_time FROM _page_hashes
            WHERE riddle = :riddle
                AND path = :path
                AND content_hash = :content_hash
        '''
        values = {
            'riddle': self.alias,
            'path': self.path,
            'content_hash': self.content_hash,
        }
        if retrieval_time := await database.fetch_val(query, values):
            self.retrieval_time = retrieval_time
            return False

        self.retrieval_time = datetime.utcnow()
        query = '''
            INSERT INTO _page_hashes
                (riddle, path, content_hash, retrieval_time)
            VALUES (:riddle, :path, :content_hash, :retrieval_time)
        '''
        values |= {'retrieval_time': self.retrieval_time}
        await database.execute(query, values)

        return True

    def save(self):
        '''Save new content retrieved page as part of the archive.'''
        local_content = self._read_local_file()
        if local_content:
            # Old content already exists
            local_hash = hashlib.md5(local_content).hexdigest()
            if local_hash != self.content_hash:
                # Retrieved content is indeed new, so rename old one
                self._rename_file_as_hidden()
        self._save_local_file()

    def _read_local_file(self) -> bytes | None:
        '''
        Read the currently stored local file.
        Return its contents as raw data, or `None` if nonexisting.
        '''
        try:
            with open(self.local_path, 'rb') as file:
                return file.read()
        except FileNotFoundError:
            return None

    def _save_local_file(self):
        '''Save new local file, creating intermediate directories as needed.'''
        Path(self.local_path.parent).mkdir(parents=True, exist_ok=True)
        with open(self.local_path, 'wb') as file:
            file.write(self.content)
            print(
                f"> \033[1m[{self.alias}]\033[0m "
                f"Saved new content from \033[1;3m{self.path}\033[0m "
                f"with hash \033[1m{self.content_hash}\033[0m "
                f"({self.retrieval_time})",
                flush=True
            )

    def _rename_file_as_hidden(self):
        '''
        Rename local file as hidden (i.e starting with '.'),
        appending its modification date to the filename.
        '''
        local_mtime = self._get_local_mtime().strftime("%Y-%m-%d")
        renamed_filename = f".{self.local_path.name}-{local_mtime}"
        renamed_path = f"{self.local_path.parent}/{renamed_filename}"
        os.rename(self.local_path, renamed_path)

    def _get_local_mtime(self) -> datetime:
        '''Get current local file's modification/retrieval time.'''
        return datetime.fromtimestamp(self.local_path.stat().st_mtime)
