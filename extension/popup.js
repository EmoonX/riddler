function getRiddleHosts() {
  // Send synchronous GET request to retrieve riddle host domains
  const hostsURL = 'https://riddler.emoon.dev/get-riddle-hosts';
  const request = new XMLHttpRequest();
  request.open('GET', hostsURL, false);
  request.send(null);
  if (request.status === 200) {
    const data = request.responseText;
    const hosts = data.split(' ');
    return hosts;
  }
}

function updateHosts() {
  // Update host permissions on button click
  const hosts = getRiddleHosts();
  console.log(hosts);
  chrome.permissions.request({
    origins: hosts,
  }, function(granted) {
    if (granted) {
      console.log('OK!');
    } else {
      console.log('NO :(');
    }
  });
}

window.onload = (_ => {
  document.getElementsByName('update-hosts')[0]
      .addEventListener('click', updateHosts);
});
