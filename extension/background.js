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

const filter = {
  urls: [
    '*://*/*'
  ]
};

chrome.webRequest.onHeadersReceived.addListener(function (details) {
  // Send a process request to server whenever response is received
  console.log(details.url, details.statusCode);
  if (details.statusCode == 200) { 
    sendToServer(details.url);
  }  
}, filter);

// Set up context menu tree at install time.
chrome.runtime.onConnect.addListener(function() {
  // Create one test item for each context type.
  var contexts = ["page","selection","link","editable","image","video",
                  "audio"];
  for (var i = 0; i < contexts.length; i++) {
    var context = contexts[i];
    var title = "Test '" + context + "' menu item";
    var id = chrome.contextMenus.create({"title": title, "contexts":[context],
                                         "id": "context" + context});
    console.log("'" + context + "' item:" + id);
  }

  // Create a parent item and two children.
  chrome.contextMenus.create({"title": "Test parent item", "id": "parent"});
  chrome.contextMenus.create(
      {"title": "Child 1", "parentId": "parent", "id": "child1"});
  chrome.contextMenus.create(
      {"title": "Child 2", "parentId": "parent", "id": "child2"});
  console.log("parent child1 child2");

  // Create some radio items.
  chrome.contextMenus.create({"title": "Radio 1", "type": "radio",
                              "id": "radio1"});
  chrome.contextMenus.create({"title": "Radio 2", "type": "radio",
                              "id": "radio2"});
  console.log("radio1 radio2");

  // Create some checkbox items.
  chrome.contextMenus.create(
      {"title": "Checkbox1", "type": "checkbox", "id": "checkbox1"});
  chrome.contextMenus.create(
      {"title": "Checkbox2", "type": "checkbox", "id": "checkbox2"});
  console.log("checkbox1 checkbox2");
});
