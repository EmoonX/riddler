/** Auto-replace links to blacklisted pages and domains. */
async function replaceLinks() {
  for (const a of $('a')) {
    const parsedUrl = new URL(a.href, window.location.href);
    const host = parsedUrl.hostname;
    if (host.endsWith('.wix.com')) {
      parsedUrl.hostname = host.replace(/[.]wix[.]com$/, '.wixsite.com');
      a.href = parsedUrl.href;
    }
    const [riddle, path] = await parseRiddleAndPath(parsedUrl.href);
    const blacklistEntry = riddle?.blacklistedPages?.find(
      entry => stripHtmlExtension(entry.path) === stripHtmlExtension(path)
    );
    if (blacklistEntry) {
      const rootPath = riddle.rootPath.replace(/[/][*]$/, '');
      a.href = `${rootPath}${blacklistEntry.nextPath}`;
    }
  }
}

async function parseRiddleAndPath(url) {
  const resp = await browser.runtime.sendMessage({
    name: 'parseRiddleAndPath',
    url: url,
  });
  return [resp.riddle, resp.path];
}

function stripHtmlExtension(path) {
  return path.replace(/[.]htm[l]?$/, '');
}

(async () => replaceLinks())();
