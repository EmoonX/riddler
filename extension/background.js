import { initExplorer } from './explorer.js';

import {
  clearRiddleData,
  findContainingPath,
  getPageNode,
  isPathSensitive,
  parseRiddleAndPath,
  riddles,
  sendMessageToPopup,
  SERVER_HOST,
  updateRiddleData,
} from './riddle.js';

/** Wildcard URLs to be matched. */
const filter = { urls: ['<all_urls>'] };

/** Time of last login request. */
// let t0;

const missingAuthPaths = new Map();
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

  // Send request to processing endpoint
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
  if (response.status === 403) {
    if (data.realm && details.statusCode != 401) {
      // Player is navigating inside a protected path but still haven't unlocked
      // credentials for it; force-trigger auth box as fallback
      chrome.tabs.get(details.tabId, tab => {
        if (chrome.runtime.lastError) {
          return;
        }
        if (missingAuthPaths.has(data.credentialsPath)) {
          return;
        }
        if (tab.url === details.url) {
          details.realm = data.realm;
          promptCustomAuth(details);
          chrome.tabs.update(tab.id, { active: true, url: details.url });
          missingAuthPaths.set(data.credentialsPath, data.realm);
        }
      });
    }
  }
  if ([401, 403].indexOf(response.status) === -1) {
    if (missingAuthPaths.has(details.credentialsPath)) {
      // Fallback auth was successful and player credentials unlocked;
      // Clear persistent box for the given protected path
      chrome.tabs.get(details.tabId, tab => {
        if (chrome.runtime.lastError) {
          return;
        }
        if (tab.url === details.url) {
          chrome.tabs.update(tab.id, { active: true, url: details.url });
          missingAuthPaths.delete(details.credentialsPath);
        }
      });
    }
  }
  if (response.ok) {
        console.log(
          `[${data.riddle}] Page "${data.path}" (${data.levelName}) found`
        );
      }
      await updateRiddleData(data.riddle, data.setName, data.levelName);
}

/** Handle riddle auth attempts, triggering custom auth box when suitable. */
function promptCustomAuth(details) {

  const [riddle, path] = parseRiddleAndPath(details.url);
  if (!riddle || isPathSensitive(riddle, path)) {
    // Fallback to browser's native auth box
    // when outside riddle domains and/or real auth is involved
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
      let pageNode = getPageNode(details.url);
      while (!pageNode) {
        details.url = details.url.split('/').slice(0, -1).join('/');
        if (details.url.indexOf('://') === -1) {
          // Page not in tree
          break;
        }
        pageNode = getPageNode(details.url);
      }
      if (pageNode && pageNode.username && pageNode.password) {
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
}

chrome.webRequest.onHeadersReceived.addListener(async details => {
  const [riddle, path] = parseRiddleAndPath(details.url);
  if (!riddle || isPathSensitive(riddle, path)) {
    // Completely ignore pages outside riddle domains
    return;
  }
  console.log(details.url, details.statusCode);
  console.log(details);
  if (details.statusCode === 401) {
    const headers = details.responseHeaders;
    console.log(headers);
    const idx = headers.findIndex(
      header => header.name.toLowerCase() === 'www-authenticate'
    );
    if (idx !== -1) {
      const authHeader = headers[idx];
      console.log(authHeader);
      details.realm = authHeader.value.match(/realm="(.*?)"/)?.[1];
      console.log(details.realm);
    }
    const parsedUrl = new URL(details.url);
    if (details.realm) {
      if (! (parsedUrl.username && parsedUrl.password)) {
        headers.splice(idx, 1);
        promptCustomAuth(details);
        return { responseHeaders: headers };
      } else {
        setTimeout(() => {
          console.log(responseHandler.authRequests);
          console.log(details.requestId);
          if (! responseHandler.authRequests.has(details.requestId)) {
            staleNativeAuthTabs.add(details.tabId);
            parsedUrl.username = parsedUrl.password = '';
            details.url = parsedUrl.toString();
            promptCustomAuth(details);
          }
        }, 25);
      }
    }
  }
  return { cancel: false };
}, filter, ['blocking', 'responseHeaders']);

/** Parse and (possibly) send intercepted HTTP responses to processing. */
async function responseHandler(details) {
  const [riddle, path] = parseRiddleAndPath(details.url);
  if (! riddle) {
    // Completely ignore pages outside riddle domains
    return;
  }
  if (details.statusCode === 401) {
    responseHandler.authRequests.add(details.requestId);
  }
  console.log('completed ->', details.url, details.statusCode);
  console.log(details);
  details.path = path;
  details.credentialsPath = findContainingPath(path, missingAuthPaths);
  if (details.credentialsPath) {
    details.realm = missingAuthPaths.get(details.credentialsPath),
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
responseHandler.authRequests = new Set();

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
