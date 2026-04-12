import {
  parseRiddleAndPath,
  updateActionIcon,
} from './riddle.js';

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

/** Handle tab switching. */
chrome.tabs.onActivated.addListener(() => {
  updateActionIcon();
});

/** Handle tab creation and navigation. */
chrome.tabs.onUpdated.addListener((_, changeInfo, tab) => {
  if (changeInfo.status === 'loading') {
    updateActionIcon();

    const [riddle, path] = parseRiddleAndPath(tab.url);
    const blacklistEntry = riddle?.blacklistedPages?.find(
      entry => stripHtmlExtension(entry.path) === stripHtmlExtension(path)
    );
    if (blacklistEntry) {
      // Replace blacklisted pages
      const rootPath = riddle.rootPath.replace(/[/][*]$/, '');
      let nextUrl = `${rootPath}${blacklistEntry.nextPath}`;
      if (tab.url.startsWith('view-source:')) {
        nextUrl = `view-source:${nextUrl}`;
      }
      chrome.tabs.remove(tab.id, () => {
        createTab(nextUrl, { active: tab.active });
      });
    }
  }
});

function stripHtmlExtension(path) {
  return path.replace(/[.]htm[l]?$/, '');
}
