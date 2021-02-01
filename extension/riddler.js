const SERVER_URL = 'http://74.208.183.127/process/'

// Get absolute path (without domain) of current page
const url = document.location.href;

const params = {
  method: 'POST',
  mode: 'cors',
  headers: {
    'Content-Type': 'text/plain'
  },
  body: url
};

// Open and send request to server containing URL text
fetch(SERVER_URL, params)
    .then(res => {console.log(res)})
    .then(error => {console.log(error)});
