// URL to where request will be sent to
const SERVER_URL = 'http://74.208.183.127/process/'

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

// Set URL containing player's ID to send request
var url_to = SERVER_URL
let getting = browser.storage.local.get('player_id');
getting.then(function (result) {
  // Open and send request to server containing URL text
  url_to += result.player_id;
  console.log(url_to);
  fetch(url_to, params)
    .then(res => {
      res.json().then(data => {
        console.log(data.path);
      });
    })
    .then(error => {console.log(error)});
});
