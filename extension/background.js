import { initExplorer } from './explorer.js';

import {
  clearRiddleData,
  findContainingPath,
  isPathSensitive,
  parseRiddleAndPath,
  refreshRiddleData,
  riddles,
  sendMessageToPopup,
  SERVER_HOST,
  updateCurrentRiddleAndLevel,
} from './riddle.js';

/** Wildcard URLs to be matched. */
const filter = { urls: ['<all_urls>'] };

/** Time of last login request. */
// let t0;

const staleNativeAuthTabs = new Set();

/** Sends user-visited URL and request data to the `/process` endpoint. */
async function sendToProcess(details) {

  // Build request params; look out for specific useful headers
  const params = {
    method: "post",
    headers: {
      'Statuscode': details.statusCode,
    },
    contentType: 'text/uri-list',
    body: details.url,
  };
  for (const name of ['Content-Location', 'Location']) {
    const header = details.responseHeaders.find(
      _header => _header.name.toLowerCase() === name.toLowerCase()
    );
    if (header) {
      params.headers[name] = header.value;
    }
  }
  console.log(details.url, details.statusCode);

  // Send request to processing endpoint; retrieve response data
  const response = await fetch(`${SERVER_HOST}/process`, params);
  if (response.status === 401) {
    // // If current login request is less than 5 seconds
    // // after marked one, don't open a new login tab.
    // const tNow = new Date();
    // const dt = tNow - t0;
    // if (t0 && dt < 5000) {
    //   return;
    // }
    // t0 = tNow;
    // if (response.text() == 'Not logged in') {
    //   // Not logged in, so open Discord auth page on new tab
    //   chrome.tabs.create({url: `${SERVER_HOST}/login`});
    // }

    // Logged out, so possibly clear riddle data
    clearRiddleData();
    return;
  }
  const data = await response.json();
  const alias = data.riddle;
  const riddle = riddles[alias];

  // Missing auth procedures
  if (response.status === 403 && data.realm) {
    if (details.statusCode !== 401) {
      // Player is navigating inside a protected path but still haven't unlocked
      // credentials for it; force-trigger auth box as fallback
      if (! riddle.missingAuthPaths.has(data.credentialsPath)) {
        riddle.missingAuthPaths.set(data.credentialsPath, data.realm);
        chrome.tabs.get(details.tabId, tab => {
          if (chrome.runtime.lastError) {
            return;
          }
          const url = tab.url.replace(/^view-source:/, '');
          chrome.tabs.update(tab.id, { active: true, url: url });
        });
      }
    }
  } else {
    if (riddle.missingAuthPaths.has(details.credentialsPath)) {
      // Fallback auth was successful and player credentials unlocked;
      // Clear persistent box for the given protected path
      riddle.missingAuthPaths.delete(details.credentialsPath);
      chrome.tabs.get(details.tabId, tab => {
        if (chrome.runtime.lastError) {
          return;
        }
        chrome.tabs.update(tab.id, { active: true, url: tab.url });
      });
    }
  }

  if (response.ok && data.path) {
    console.log(`[${alias}] Received page "${data.path}" (${data.levelName})`);
  }
  await refreshRiddleData(alias, data);
}

/** Handle riddle auth attempts, triggering custom auth box when suitable. */
function promptCustomAuth(details, asyncCallback) {

  const [riddle, path] = parseRiddleAndPath(details.url);
  if (!riddle || isPathSensitive(riddle, path)) {
    // Fallback to browser's native auth box
    // when outside riddle domains and/or real auth is involved
    asyncCallback({ cancel: false });
    staleNativeAuthTabs.add(details.tabId);
    return;
  }
  if (staleNativeAuthTabs.has(details.tabId)) {
    // Native auth has been triggered before in this tab (i.e network context);
    // employ tab replacement trick to circumvent persistent native dialog
    chrome.tabs.duplicate(details.tabId, dupTab => {
      chrome.tabs.update(dupTab.id,{ active: false, url: details.url });
      chrome.tabs.remove(details.tabId);
    });
    staleNativeAuthTabs.delete(details.tabId);
    return;
  }
  chrome.tabs.get(details.tabId, tab => {
    if (tab.pendingUrl?.startsWith('view-source:')) {
      // Source code browsing doesn't count as actual content pages;
      // update tab with real URL to allow prompting custom box
      chrome.tabs.update(tab.id, { active: true, url: details.url });
    }
  });

  // Save this function so we can unlisten it later
  const credentialsHandler = (port => {
    console.log('Connected to credentials.js...');
    (async () => {
      // Request auth box with given (explicit) realm message
      const message = {
        realm: details.realm,
        boxHTML: await fetch(chrome.runtime.getURL('credentials.html'))
          .then(response => response.text()),
        boxCSS: await fetch(chrome.runtime.getURL('credentials.css'))
          .then(response => response.text()),
      };
      const containingPath = findContainingPath(path, riddle.pagesByPath);
      const pageNode = riddle.pagesByPath.get(containingPath);
      if (pageNode?.username && pageNode?.password) {
        // Logged in and credentials previously unlocked; autocomplete them
        message.unlockedCredentials = {
          username: pageNode.username,
          password: pageNode.password,
        };
      }
      port.postMessage(message);
    })();
    chrome.runtime.onConnect.removeListener(credentialsHandler);
  });
  chrome.runtime.onConnect.addListener(credentialsHandler);
  
  // Block browser's native auth dialog
  if (asyncCallback) {
    asyncCallback({ cancel: true });
  }
}
chrome.webRequest.onAuthRequired.addListener(
  promptCustomAuth, filter, ['asyncBlocking']
);

/** Parse and (possibly) send intercepted HTTP responses to processing. */
function responseHandler(details) {
  const [riddle, path] = parseRiddleAndPath(details.url);
  if (! riddle) {
    // Completely ignore pages outside riddle domains
    return;
  }
  updateCurrentRiddleAndLevel(riddle, path);

  details.path = path;
  details.credentialsPath = findContainingPath(path, riddle.missingAuthPaths);
  if (details.credentialsPath) {
    // Missing unlocked credentials for path; prompt auth box straight away
    details.realm = riddle.missingAuthPaths.get(details.credentialsPath);
    chrome.tabs.get(details.tabId, tab => {
      if (tab.url.startsWith('view-source')) {
        const url = tab.url.replace(/^view-source:/, '');
        chrome.tabs.update(tab.id, { active: true, url: url });
      }
    });
    promptCustomAuth(details);
  }
  if (details.statusCode === 401 || isPathSensitive(riddle, path)) {
    // Pluck wrong credentials from 401s and special cases;
    // avoid possibly sending mistakenly entered personal info
    const parsedUrl = new URL(details.url);
    parsedUrl.username = parsedUrl.password = '';
    details.url = parsedUrl.toString();
  }
  if (Object.keys(riddles).length === 0) {
    // Fallback for when user logs in *after* the extension is loaded
    initExplorer(() => {
      sendToProcess(details)
    });
    return;
  }
  sendToProcess(details);
};
chrome.webRequest.onBeforeRedirect.addListener(
  // Explicitly handle 30x (redirect) responses
  responseHandler, filter, ['responseHeaders']
);
chrome.webRequest.onCompleted.addListener(
  // Handle all completed responses; filter out premature 401s
  responseHandler, filter, ['responseHeaders']
);

/** Send regular pings to avoid service worker becoming inactive. */
chrome.runtime.onConnect.addListener(port => {
  const pingInterval = setInterval(() => {
    port.postMessage({ status: "ping" });
  }, 10000);
  port.onDisconnect.addListener(_ => {
    clearInterval(pingInterval);
  });
});

(async () => {
  initExplorer();

  /** Communication with popup.js. */
  chrome.runtime.onConnect.addListener(port => {
    if (port.name != 'popup.js') {
      return;
    }
    console.log('Connected to popup.js...');
    if (Object.keys(riddles).length === 0) {
      // Fallback for when user logs in *after* extension is loaded
      initExplorer(() => {
        sendMessageToPopup(port);
      });
      return;
    }
    sendMessageToPopup(port);
  });
})();
