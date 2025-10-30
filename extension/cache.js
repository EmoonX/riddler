/** Cache-retrieve URL asset, avoiding subsequent request bloat. */
export async function retrieveWithCache(cacheName, url) {
  const cache = await caches.open(cacheName);
  let response = await cache.match(url);
  if (! response) {
    try {
      await cache.add(url);
    } catch {
      // Couldn't fetch external asset (usually 404)
      return null;
    }
    response = await cache.match(url);
  }
  const blob = await response.blob();
  return await new Promise(resolve => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result);
    reader.readAsDataURL(blob);
  });
}
