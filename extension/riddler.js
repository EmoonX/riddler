// URL to where request will be sent to
const SERVER_URL = 'http://74.208.183.127/process/'

// Get URL of current page
const url = document.location.href;

// Request parameters
const params = {
  method: 'POST',
  mode: 'cors',
  headers: {
    'Content-Type': 'text/uri-list'
  },
  body: url
};

// Open and send request to server containing URL text
fetch(SERVER_URL, params)
    .then(res => {
      res.json().then(data => {
        console.log(data.url);
      });
    })
    .then(error => {console.log(error)});
