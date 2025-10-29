import { parseRiddleAndPath} from "./riddle.js";

/** Replace blacklisted pages on tab load start. */
chrome.tabs.onUpdated.addListener((_, changeInfo, tab) => {
  if (changeInfo.status === 'loading') {
    const [riddle, path] = parseRiddleAndPath(tab.url);
    const blacklistEntry = riddle?.blacklistedPages.find(
      entry => stripHtmlExtension(entry.path) === stripHtmlExtension(path)
    );
    if (blacklistEntry) {
      const rootPath = riddle.rootPath.replace(/[/][*]$/, '');
      const nextUrl = `${rootPath}${blacklistEntry.nextPath}`;
      chrome.tabs.remove(tab.id, () => {
        chrome.tabs.create({ url: nextUrl });
      });
    }
  }
});

function stripHtmlExtension(path) {
  return path.replace(/[.]htm[l]?$/, '');
}
