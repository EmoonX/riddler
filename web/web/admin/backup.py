from datetime import datetime
import hashlib

from pymysql.err import IntegrityError

from util.db import database


class Backup:

    def __init__(self, alias: str, path: str, data: str):
        self.alias = alias
        self.path = path
        self.data = data
        self.hash = hashlib.md5(data).hexdigest()

    async def record_page_hash(self) -> bool:
        query = '''
            INSERT INTO _page_hashes
                (riddle, path, hash)
            VALUES (:riddle, :path, :hash)
        '''
        values = {'riddle': self.alias, 'path': self.path, 'hash': self.hash}
        try:
            await database.execute(query, values)
        except IntegrityError:
            pass
        else:
            tnow = datetime.utcnow()
            print(
                f"> \033[1m[{self.alias}]\033[0m "
                f"New hash \033[1m{self.hash}\033[0m "
                f"for page \033[1;3m{self.path}\033[0m "
                f"({tnow})",
                flush=True
            )