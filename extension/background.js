import { initExplorer } from './explorer.js';

/** Wildcard URLs to be matched. */
const filter = {
  urls: ['*://*/*']
};

/** Time of last login request. */
var t0;

/** Sends user-visited URL and its status code to `/process` endpoint. */
function sendToProcess(visitedUrl, statusCode) {
  const SERVER_URL = 'https://riddler.app';
  const url = SERVER_URL + '/process';
  $.ajax(url, {
    // Request parameters
    type: 'POST',
    contentType: 'text/uri-list',
    headers: {
      'Statuscode': statusCode,
    },
    data: visitedUrl,

    // Callbacks on successful and failed responses
    success: text => {
      console.log(`[${text}] Valid page found`);
    },
    error: xhr => {
      console.log(`[${xhr.status}] ${xhr.responseText}`);
      if (xhr.status == 401) {
        // If current login request is less than 5 seconds
        // after marked one, don't open a new login tab.
        const tNow = new Date();
        const dt = tNow - t0;
        if (t0 && dt < 5000) {
          return;
        }
        t0 = tNow;

        if (xhr.responseText == 'Not logged in') {
          // Not logged in, so open Discord auth page on new tab
          const login = SERVER_URL + '/login';
          chrome.tabs.create({url: login});
        }
      }
    },
  });
}

chrome.webRequest.onHeadersReceived.addListener(details => {
  // Send a process request to server whenever response is received
  if (details.url.includes('riddler.app')) {
    return;
  }
  console.log(details.url, details.statusCode);
  if ([200, 404].indexOf(details.statusCode) !== -1) { 
    sendToProcess(details.url, details.statusCode);
  }  
}, filter);

$(_ => {
  initExplorer((riddles, currentRiddle) => {
    // Send riddle data to popup.js
    chrome.extension.onConnect.addListener(port => {
      console.log('Connected to popup.js...');
      port.postMessage({
        riddles: riddles,
        currentRiddle: currentRiddle,
      });
    });
  });
});
