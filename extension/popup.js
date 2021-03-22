function getRiddleHosts() {
  // Build list of permitted host URLs
  const hostsURL = 'https://riddler.emoon.dev/get-riddle-hosts';
  fetch(hostsURL)
    .then(response => response.text())
    .then(data => {
      console.log(data);
      const hosts = data.split(' ');
      chrome.permissions.request({
        origins: hosts,
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
}

window.onload = (_ => {
  document.getElementsByName('update-hosts')[0]
    .addEventListener('click', getRiddleHosts);
});
