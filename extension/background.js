import {
  clearRiddleData,
  getPageNode,
  initExplorer,
  parseRiddleAndPath,
  riddles,
  sendMessageToPopup,
  SERVER_URL,
  updateRiddleData,
} from './explorer.js';

/** Wildcard URLs to be matched. */
const filter = {
  urls: ['<all_urls>'],
};

/** Time of last login request. */
let t0;

/** Sends user-visited URL and its status code to `/process` endpoint. */
async function sendToProcess(visitedUrl, statusCode) {
  const params = {
    method: "post",
    headers: {
      'Statuscode': statusCode,
    },
    contentType: 'text/uri-list',
    body: visitedUrl,
  };
  let data;
  await fetch(`${SERVER_URL}/process`, params)
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
        //   chrome.tabs.create({url: `${SERVER_URL}/login`});
        // }

        // Logged out, so possibly clear riddle data
        clearRiddleData();
        return;
      }
      data = await response.json();
      if (response.ok) {
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
  if (riddle && riddle.alias === 'notpron' && path.indexOf('/jerk2') === 0) {
    // Fallback to browser's auth box when real auth is involved
    // (no, pr0ners, I am NOT interested in hoarding your personal user data)
    asyncCallback({cancel: false});
    return;
  }
  const parsedUrl = new URL(details.url);
  let username = parsedUrl.searchParams.get('username');
  let password = parsedUrl.searchParams.get('password');

  // Save this function so we can unlisten it later
  credentialsHandler = (async port => {
    console.log('Connected to credentials.js...');
    if (username && password) {
      // Query '?username=...&password=...' found, send to redirect
      port.postMessage({
        url: details.url,
        username: username,
        password: password,
      });
    } else {
      // Request auth box with given (explicit) realm message
      // and autocompleted credentials (if logged in and unlocked beforehand)
      const message = {realm: details.realm};
      if (riddle) {
        let pageNode = getPageNode(details.url);
        while (! pageNode) {
          details.url = details.url.split('/').slice(0, -1).join('/');
          if (details.url.indexOf('https://') === -1) {
            // Page not in tree
            break;
          }
          pageNode = getPageNode(details.url);
        }
        if (pageNode && pageNode.username) {
          message.unlockedCredentials = {
            username: pageNode.username,
            password: pageNode.password,
          };
        }
      }
      port.postMessage(message);
    }
    port.onMessage.addListener(async data => {
      if (data.disconnect) {
        chrome.runtime.onConnect.removeListener(credentialsHandler);
      }
    })
  });
  chrome.runtime.onConnect.addListener(credentialsHandler);
  
  // Block browser's native auth dialog
  asyncCallback({cancel: true});
}, filter, ['asyncBlocking']);

chrome.webRequest.onBeforeSendHeaders.addListener(async details => {
  if (details.url.indexOf('.htm') !== -1) {
    console.log(details);
  }
}, filter, ['requestHeaders']);

/** Send a process request to server whenever response is received. */
chrome.webRequest.onHeadersReceived.addListener(async details => {
  const parsedUrl = new URL(details.url);
  if (parsedUrl.origin === SERVER_URL) {
    return;
  }
  console.log(details.url, details.statusCode);
  if (details.statusCode === 301) {
    // Avoid trivial redirects (301) pollution
    return;
  }
  if (details.statusCode === 401) {
    // Pluck wrong credentials from 401s,
    // to avoid sending possibly mistakenly entered personal info
    details.url = `${parsedUrl.origin}${parsedUrl.pathname}`;
  }
  if (Object.keys(riddles).length === 0) {
    // Fallback for when user logs in *after* the extension is loaded
    initExplorer(() => {
      sendToProcess(details.url, details.statusCode)
    });
    return;
  }
  sendToProcess(details.url, details.statusCode);
}, filter);

/** Send regular pings to avoid service worker becoming inactive. */
chrome.runtime.onConnect.addListener(port => {
  const pingInterval = setInterval(() => {
    port.postMessage({
      status: "ping",
    });
  }, 10000);
  port.onDisconnect.addListener(_ => {
    clearInterval(pingInterval);
  });
});

(() => {
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
