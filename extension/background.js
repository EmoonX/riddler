import { initExplorer } from './explorer.js';

import {
  clearRiddleData,
  getPageNode,
  isPathSensitive,
  parseRiddleAndPath,
  riddles,
  sendMessageToPopup,
  SERVER_HOST,
  updateRiddleData,
} from './riddle.js';

/** Wildcard URLs to be matched. */
const filter = {
  urls: ['<all_urls>'],
};

/** Time of last login request. */
// let t0;

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
    const header = details.responseHeaders
      .find(_header => _header.name.toLowerCase() === name.toLowerCase());
    if (header) {
      params.headers[name] = header.value;
    }
  }
  console.log(details.url, details.statusCode);

  let data;
  await fetch(`${SERVER_HOST}/process`, params)
    .then(async response => {
      // Callbacks on successful and failed responses
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
      data = await response.json();
      if (response.ok && data.path) {
        console.log(
          `[${data.riddle}] Page "${data.path}" (${data.levelName}) found`
        );
      }
      await updateRiddleData(data.riddle, data.setName, data.levelName);
    });

  return data;
}

let credentialsHandler = null;

/** Handle riddle auth attempts, prompting user with custom auth box. */
chrome.webRequest.onAuthRequired.addListener((details, asyncCallback) => {
  const [riddle, path] = parseRiddleAndPath(details.url);
  if (!riddle || isPathSensitive(riddle, path)) {
    // Fallback to browser's native auth box
    // when outside riddle domains and/or real auth is involved
    asyncCallback({ cancel: false });
    return;
  }

  // Save this function so we can unlisten it later
  const credentialsHandler = (port => {
    console.log('Connected to credentials.js...');

    const parsedUrl = new URL(details.url);
    const username = parsedUrl.searchParams.get('username');
    const password = parsedUrl.searchParams.get('password');
    if (username && password) {
      // Query '?username=...&password=...' found, send to redirect
      port.postMessage({
        url: details.url,
        username: username,
        password: password,
      });
    } else (async () => {
      // Request auth box with given (explicit) realm message
      // and autocompleted credentials (if logged in and unlocked beforehand)
      const message = {
        realm: details.realm,
        boxHtml:await fetch(chrome.runtime.getURL('credentials.html'))
          .then(response => response.text()),
        boxCss: await fetch(chrome.runtime.getURL('credentials.css'))
          .then(response => response.text()),
      };
      if (riddle) {
        let pageNode = getPageNode(details.url);
        while (! pageNode) {
          details.url = details.url.split('/').slice(0, -1).join('/');
          if (details.url.indexOf('://') === -1) {
            // Page not in tree
            break;
          }
          pageNode = getPageNode(details.url);
        }
        if (pageNode && pageNode.username && pageNode.password) {
          message.unlockedCredentials = {
            username: pageNode.username,
            password: pageNode.password,
          };
        }
      }
      port.postMessage(message);
    })();
        chrome.runtime.onConnect.removeListener(credentialsHandler);
  });
  chrome.runtime.onConnect.addListener(credentialsHandler);
  
  // Block browser's native auth dialog
  asyncCallback({cancel: true});
}, filter, ['asyncBlocking']);

/** Send a process request to server whenever response is received. */
chrome.webRequest.onHeadersReceived.addListener(async details => {
  const [riddle, path] = parseRiddleAndPath(details.url);
  if (! riddle) {
    // Completely ignore pages outside riddle domains
    return;
  }

  if (details.statusCode === 401 || isPathSensitive(riddle, path)) {
    // Pluck wrong credentials from 401s and special cases,
    // to avoid possibly sending mistakenly entered personal info
    const parsedUrl = new URL(details.url);
    parsedUrl.username = '';
    parsedUrl.password = '';
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
}, filter, ['responseHeaders']);

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
