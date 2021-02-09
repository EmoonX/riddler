function sendToServer(url_list) {
  // URL to where request will be sent to
  const SERVER_URL = 'https://riddler.emoon.dev';

  // Payload message
  const message = {
    action: 'getCookies',
    url: 'https://riddler.emoon.dev',
    cookieName: 'session'
  };

  // Retrieve cookie from background
  chrome.runtime.sendMessage(message, cookie => {
    // Request parameters
    const params = {
      method: 'POST',
      mode: 'cors',
      credentials: 'include',
      headers: {
        'Content-Type': 'text/uri-list',
        'Cookie': cookie.name + '=' + cookie.value
      },
      body: url_list
    };
    // Send request to server containing URL text
    const url_to = SERVER_URL + '/process/';
    fetch(url_to, params)
      .then(res => {
        console.log(res);
        if (res.status == 401) {
          // Unauthorized, so open Discord auth page on new tab
          const url_login = SERVER_URL + '/login/';
          window.open(url_login,'_blank');
        }
      })
      .then(error => {console.log(error)})
    ;
  });
}

// Get document resources URLs and send them in concatenated string form
window.onload = function () {
  const resources = performance.getEntriesByType("resource");
  var url_list = location.href + '\n';
  resources.forEach(resource => {
    url_list += resource.name + '\n';
  });
  console.log(url_list);
  sendToServer(url_list);
}
