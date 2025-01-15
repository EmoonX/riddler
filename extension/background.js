import { updateRiddleData } from './explorer.js';

/** Wildcard URLs to be matched. */
const filter = {
  urls: ['*://*/*']
};

/** Time of last login request. */
var t0;

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
        const data = await response.json();
        console.log(
          `[${data.riddle}] Page "${data.path}" (${data.levelName}) found`
        );
        await updateRiddleData(data.riddle, data.setName, data.levelName);
      }
    })
}

chrome.webRequest.onHeadersReceived.addListener(async details => {
  // Send a process request to server whenever response is received
  if (details.url.includes('emoon.dev')) {
    return;
  }
  console.log(details.url, details.statusCode);
  if ([200, 404].indexOf(details.statusCode) !== -1) { 
    await sendToProcess(details.url, details.statusCode);
  }  
}, filter);
