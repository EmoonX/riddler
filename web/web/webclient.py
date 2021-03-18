import aiohttp
import json


async def bot_request(path: str, **kwargs):
    url = 'http://localhost:4757/' + path
    
    for param, value in kwargs.items():
        if type(value) in (list, dict):
            kwargs[param] = json.dumps(value)
        elif type(value) == bool or value is None:
            kwargs[param] = int(bool(value))
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=kwargs) as resp:
            text = await resp.text()
            return text
