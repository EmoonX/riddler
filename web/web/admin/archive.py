from datetime import datetime
import hashlib
import os
from pathlib import Path
from typing import Self

from util.db import database


class PageSnapshot:
    '''Archived page snapshot.'''

    @classmethod
    async def get_latest(cls, alias: str, path: Path | str) -> Self | None:
        '''Get latest snapshot for given page, based on retrieval time.'''
        query = '''
            SELECT * FROM _page_hashes
            WHERE riddle = :riddle AND path = :path
            ORDER BY retrieval_time DESC
        '''
        values = {'riddle': alias, 'path': path}
        data = await database.fetch_one(query, values)
        if not data:
            return None
        return cls(
            alias,
            path,
            retrieval_time=data['retrieval_time'],
            content_hash=data['content_hash'],
            last_modified=data['last_modified'],
        )

    def __init__(
        self,
        alias: str,
        path: Path | str,
        retrieval_time: datetime,
        last_modified: datetime | None = None,
        content: bytes | None = None,
        content_hash: str | None = None,
    ):
        self.alias = alias
        self.path = Path(path)
        self.local_path = self._get_local_path()
        self.retrieval_time = retrieval_time
        self.last_modified = last_modified
        self.content = content
        if content is not None:
            self.content_hash = hashlib.md5(content).hexdigest()
        else:
            self.content_hash = content_hash

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

        values = {
            'riddle': self.alias,
            'path': self.path,
            'content_hash': self.content_hash,
            'last_modified': self.last_modified,
        }
        last_snapshot = await PageSnapshot.get_latest(self.alias, self.path)
        if last_snapshot and last_snapshot.content_hash == self.content_hash:
            # Update `last_modified` field when missing;
            # avoid overwriting it on trivial same-hash header value changes
            self.retrieval_time = last_snapshot.retrieval_time
            query = '''
                UPDATE _page_hashes
                SET last_modified = :last_modified
                WHERE riddle = :riddle
                    AND path = :path
                    AND content_hash = :content_hash
                    AND last_modified IS NULL
            '''
            await database.execute(query, values)

            return False

        # Unseen page or differing hash from last; insert new snapshot entry
        query = '''
            INSERT INTO _page_hashes
                (riddle, path, content_hash, last_modified, retrieval_time)
            VALUES
                (:riddle, :path, :content_hash, :last_modified, :retrieval_time)
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
        local_mtime = self.retrieval_time.strftime("%Y-%m-%d")
        renamed_filename = f".{self.local_path.name}-{local_mtime}"
        renamed_path = f"{self.local_path.parent}/{renamed_filename}"
        os.rename(self.local_path, renamed_path)
