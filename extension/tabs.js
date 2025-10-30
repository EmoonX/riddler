import { parseRiddleAndPath } from './riddle.js';

/** Create window-aware tab (account for e.g. private windows).*/
export async function createTab(url, params) {
  const currentWindow = await chrome.windows.getCurrent({ populate: false });
  const tab = await chrome.tabs.create({
    url: url,
    windowId: currentWindow.id,
    ...params,
  });
  return tab;
}

/** Replace blacklisted pages on tab load start. */
chrome.tabs.onUpdated.addListener((_, changeInfo, tab) => {
  function stripHtmlExtension(path) {
    return path.replace(/[.]htm[l]?$/, '');
  }

  if (changeInfo.status === 'loading') {
    const [riddle, path] = parseRiddleAndPath(tab.url);
    const blacklistEntry = riddle?.blacklistedPages.find(
      entry => stripHtmlExtension(entry.path) === stripHtmlExtension(path)
    );
    if (blacklistEntry) {
      const rootPath = riddle.rootPath.replace(/[/][*]$/, '');
      const nextUrl = `${rootPath}${blacklistEntry.nextPath}`;
      chrome.tabs.remove(tab.id, () => {
        createTab(nextUrl, { active: tab.active });
      });
    }
  }
});
