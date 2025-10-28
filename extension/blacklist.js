/** Auto-replace links to blacklisted pages */
async function replaceLinks() {
  for (const a of $('a')) {
    const url = new URL(a.href, window.location.href).href;
    const [riddle, path] = await parseRiddleAndPath(url);
    const blacklistEntry = riddle?.blacklistedPages.find(
      entry => stripHtmlExtension(entry.path) === stripHtmlExtension(path)
    );
    if (blacklistEntry) {
      const rootPath = riddle.rootPath.replace(/[/][*]$/, '');
      a.href = `${rootPath}${blacklistEntry.nextPath}`;
    }
  }
}

async function parseRiddleAndPath(url) {
  const resp = await chrome.runtime.sendMessage({
    name: 'parseRiddleAndPath',
    url: url,
  });
  return [resp.riddle, resp.path];
}

function stripHtmlExtension(path) {
  return path.replace(/[.]htm[l]?$/, '');
}

(async () => replaceLinks())();
