// URL to where request will be sent to
const SERVER_URL = 'http://riddler.emoon.dev/process/'

// Get URL of current page
const url_from = document.location.href;

// Request parameters
const params = {
  method: 'POST',
  mode: 'cors',
  headers: {
    'Content-Type': 'text/uri-list'
  },
  body: url_from
};

var url_to = SERVER_URL;
chrome.storage.local.get('player_id', function (result) {
  // Set URL containing player's ID
  url_to += result.player_id;

  // Send request to server containing URL text
  console.log(url_to);
  fetch(url_to, params)
    .then(res => {
      res.json().then(data => {
        console.log(data.path);
      });
    })
    .then(error => {console.log(error)});
});
