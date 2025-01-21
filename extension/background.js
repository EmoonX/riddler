import { updateRiddleData } from './explorer.js';

/** Wildcard URLs to be matched. */
const filter = {
  urls: ['<all_urls>'],
};

/** Time of last login request. */
let t0;

/** Sends user-visited URL and its status code to `/process` endpoint. */
async function sendToProcess(visitedUrl, statusCode) {
  const SERVER_URL = 'https://emoon.dev';
  const url = `${SERVER_URL}/process`;
  const params = {
    method: "post",
    headers: {
      'Statuscode': statusCode,
    },
    contentType: 'text/uri-list',
    body: visitedUrl,
  };
  let data;
  await fetch(url, params)
    .then(async response => {
      // Callbacks on successful and failed responses
      if (response.status == 401) {
        // If current login request is less than 5 seconds
        // after marked one, don't open a new login tab.
        const tNow = new Date();
        const dt = tNow - t0;
        if (t0 && dt < 5000) {
          return;
        }
        t0 = tNow;

        if (response.text() == 'Not logged in') {
          // Not logged in, so open Discord auth page on new tab
          chrome.tabs.create({url: `${SERVER_URL}/login`});
        }
        return
      }
      if (response.ok) {
        data = await response.json();
        console.log(
          `[${data.riddle}] Page "${data.path}" (${data.levelName}) found`
        );
        await updateRiddleData(data.riddle, data.setName, data.levelName);
      }
    });
  return data;
}

let credentialsHandler = null;

/** Handle riddle auth attempts, prompting user with custom auth box. */
chrome.webRequest.onAuthRequired.addListener((details, asyncCallback) => {
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
      sendToProcess(details.url, 401)
        .then(data => {
          port.postMessage({
            realm: details.realm,
            unlockedCredentials: data.unlockedCredentials
          });
        });
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

/** Send a process request to server whenever response is received. */
chrome.webRequest.onHeadersReceived.addListener(async details => {
  const parsedUrl = new URL(details.url);
  if (parsedUrl.hostname === 'emoon.dev') {
    return;
  }
  console.log(details.url, details.statusCode);
  if ([200, 404].indexOf(details.statusCode) !== -1) { 
    await sendToProcess(details.url, details.statusCode);
  }  
}, filter);
