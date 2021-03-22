window.onload = (_ => {
  // Build list of permitted host URLs
  const hostsURL = 'https://riddler.emoon.dev/get-riddle-hosts';
  var riddleHosts = [];
  fetch(hostsURL)
    .then(response => response.text())
    .then(data => {
      console.log(data);
      const hosts = data.split(' ');
      chrome.permissions.request({
        permissions: hosts,
      }, function(granted) {
        if (granted) {
          console.log('OK!');
        } else {
          console.log('NO :(');
        }
      });
    })
    .catch(error => {
      console.log(error);
    })
  ;
});
