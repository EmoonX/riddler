// URL to where request will be sent to
const SERVER_URL = 'https://riddler.emoon.dev/process/';

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

// Send request to server containing URL text
fetch(SERVER_URL, params)
  .then(res => {
    res.json().then(data => {
      console.log(data.path);
    });
  })
  .then(error => {console.log(error)});
