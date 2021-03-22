// Build list of permitted host URLs
const hostsURL = 'https://riddler.emoon.dev/get-riddle-hosts';
var riddleHosts = [];
fetch(hostsURL)
  .then(response => response.text())
  .then(data => console.log(data))
  .catch(error => {
    console.log(error);
  })
;
