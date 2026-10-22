import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
import httpx2

# all_pages = ...
# good = ...
# bad = ...
pages = set()


def retrieve_all(riddle: dict):
    global pages
    pages = set()
    print(f"\n\n>>> {riddle['alias']} <<<")
    retrieve_search(riddle)
    good[riddle['alias']] = pages


def retrieve_search(riddle: dict):
     host = urlsplit(riddle['root_path']).hostname
     for start in range(0, 10000, 100):
         search_url = f"https://neocities.org/search?q=site:{host}&start={start}"
         print(f"\n[{search_url}]")
         res = httpx2.get(search_url)
         if not res.is_success:
             return
         soup = BeautifulSoup(res.text)
         for a in soup.select('.result-url > a'):
             href = a.attrs['href']
             if riddle['root_path'].endswith('/*'):
                 if not href.startswith(riddle['root_path'].removesuffix('/*')):
                     continue
             for ext in {'.htm', '.html'}:
                 path = href.removeprefix(riddle['root_path'].removesuffix('/*'))
                 path += ext if not path.endswith('/') else f"index{ext}"
                 if path not in all_pages[riddle['alias']]:
                     retrieve_page(riddle, path)


def retrieve_page(riddle: dict, path: str):
    root_path = riddle['root_path']   
    url = f"{root_path.removesuffix('/*')}{path.replace('.', '%2E')}"
    res = httpx2.get(url)
    if not res.is_success:
        return
    pages.add(path)
    print(path)
    html = res.text
    for href in re.findall(r'(((\w+):?)?([/.]\w*)*\w+[.]\w+)', html):
        #print(f"  >> {href}")
        path2 = urljoin(path, href[0])
        path2 = path2.removeprefix(root_path.removesuffix('/*'))
        path2 = path2.removeprefix(f"/{root_path.split('/', 3)[-1]}")
        if path2.startswith('http'):
            continue
        if not Path(path2).suffix:
            path2 += Path(path).suffix
        if path2.endswith(('/.htm', '/.html')):
            path2 = path2.rpartition('.')[0] + 'index.html'
        if path2[0] != '/':
            path2 = f"/{path2}"
        path2 = path2.partition('#')[0].partition('?')[0]
        if path2 not in pages and path2 not in bad and path2 not in all_pages[riddle['alias']]:
            url = f"{root_path.removesuffix('/*')}{path2.replace('.', '%2E')}"
            #print(f"...{url}")
            res = httpx2.head(url)
            if res.is_success:
                pages.add(path2)
                print(f"  {path2}")
            else:
                bad.add(path2)


def is_binary(path: Path) -> bool:
    return b'\x00' in path.read_bytes()
