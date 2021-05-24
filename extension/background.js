// Time of last login request
var t0;

function sendToServer(url) {
  // Base URL to where requests will be sent to
  const SERVER_URL = 'https://riddler.emoon.dev';

  // Get session cookie from browser storage
  const details = {
    url: SERVER_URL,
    name: 'session'
  };
  chrome.cookies.get(details, cookie => {
    // Request parameters
    const params = {
      method: 'POST',
      mode: 'cors',
      credentials: 'include',
      headers: {
        'Content-Type': 'text/uri-list',
        'Cookie': cookie.name + '=' + cookie.value
      },
      body: url
    };
    // Send request to server containing URL text
    const urlTo = SERVER_URL + '/process-beta';
    fetch(urlTo, params)
      .then(res => {
        console.log(res);
        if (res.status == 401) {
          res.text().then(text => {
            if (text == 'Not logged in') {
              console.log('401: Not logged in');
              tNow = new Date();
              dt = tNow - t0;
              if (t0 && dt < 5000) {
                // If current login request is less than 5 seconds
                // after marked one, don't open a new login tab
                return;
              }          
              // Not logged in, so open Discord auth page on new tab
              const login = SERVER_URL + '/login';
              chrome.tabs.create({url: login});

              // Mark time of current login request
              t0 = tNow;
            } else {
              console.log('401: Not member of guild');
              const invite = 'https://discord.gg/' + text;
              chrome.tabs.create({url: invite});
            }
          });
        }
      })
      .then(error => {console.log(error)})
    ;
  });
}

const filter = {
  urls: [
    '*://*/*'
  ]
};

chrome.webRequest.onHeadersReceived.addListener(function (details) {
  // Send a process request to server whenever response is received
  if (details.url.includes('riddler.emoon.dev')) {
    return;
  }
  console.log(details.url, details.statusCode);
  if (details.statusCode == 200) { 
    sendToServer(details.url);
  }  
}, filter);
