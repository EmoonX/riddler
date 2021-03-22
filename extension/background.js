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
    const urlTo = SERVER_URL + '/process';
    fetch(urlTo, params)
      .then(res => {
        console.log(res);
        if (res.status == 401) {
          // Unauthorized, so open Discord auth page on new tab
          const login = SERVER_URL + '/login';
          chrome.tabs.create({url: login});
        }
      })
      .then(error => {console.log(error)})
    ;
  });
}

chrome.webRequest.onHeadersReceived.addListener(function (details) {
  // Send a process request to server whenever response is received
  console.log(details.url, details.statusCode);
  if (details.statusCode == 200) { 
    sendToServer(details.url);
  }  
}, filter);
