// Get absolute path (without domain) of current page
var url = document.location.href;

// Define a HTTP request
var req = new XMLHttpRequest();

req.addEventListener('readystatechange', function (evt) {
  // Triggers when request state changes
  if (req.readyState === 4) {
    if (req.status === 200) {
      alert('Saved !');
    } else {
      alert('ERROR: status ' + req.status);
    }
  }
});
// Open and send request to server containing URL text
req.open('POST', 'http://74.208.183.127/process/', true);
req.setRequestHeader('X-PINGOTHER', 'pingpong');
req.setRequestHeader('Content-Type', 'text/uri-list');
req.send('url=' + encodeURIComponent(url));
