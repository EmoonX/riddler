import aiohttp


async def bot_request(path: str, **kwargs):
    url = 'http://localhost:4757/' + path
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=kwargs) as resp:
            text = await resp.text()
            return text
