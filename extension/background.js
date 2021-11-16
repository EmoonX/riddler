// Time of last login request
var t0;

function sendToServer(url, statusCode) {
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
        'Cookie': cookie.name + '=' + cookie.value,
        'Statuscode': statusCode,
      },
      body: url
    };
    // Send request to server containing URL text
    const urlTo = SERVER_URL + '/process';
    fetch(urlTo, params)
      .then(res => {
        console.log(res);
        res.text().then(text => {
          if (res.status == 200) {
            console.log(text);
          } 
          else if (res.statys == 401) {
            // If current login request is less than 5 seconds
            // after marked one, don't open a new login tab.
            tNow = new Date();
            dt = tNow - t0;
            if (t0 && dt < 5000) {
              return;
            }
            // Mark time of current login request
            t0 = tNow;

            if (text == 'Not logged in') {         
              // Not logged in, so open Discord auth page on new tab
              console.log('401: Not logged in');
              const login = SERVER_URL + '/login';
              chrome.tabs.create({url: login});
            } else {
              // Not emmber of guild, so open Discord guild invite
              console.log('401: Not member of Wonderland');
              const invite = 'https://discord.gg/' + text;
              chrome.tabs.create({url: invite});
            }
          }
        });
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
  if ([200, 404].indexOf(details.statusCode) !== -1) { 
    sendToServer(details.url, details.statusCode);
  }  
}, filter);
