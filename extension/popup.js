// Current riddle being played
var currentRiddle;

function request(url) {
  // Send synchronous GET request to
  // target URL and return response text
  const request = new XMLHttpRequest();
  request.open('GET', url, false);
  request.send(null);
  if (request.status === 200) {
    const data = request.responseText;
    return data;
  }
}

function getRiddleHosts() {
  // Retrieve riddle host domains
  const HOSTS_URL = 'https://riddler.emoon.dev/get-riddle-hosts';
  const data = request(HOSTS_URL);
  const hosts = data.split(" ");
  return hosts;
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

function getCurrentRiddleData() {
  // Retrieve current riddle data for authenticated user
  const DATA_URL = 'https://riddler.emoon.dev/get-current-riddle-data';
  const data = request(DATA_URL);
  return data;
}

window.onload = (_ => {
  // Set "Update hosts" button click event
  document.getElementsByName('update-hosts')[0]
    .addEventListener('click', updateHosts);
  
  // Show current riddle info in extension's popup
  const text = getCurrentRiddleData();
  const data = JSON.parse(text);
  const alias = data['alias'];
  const currentIconTag = document.getElementById('current-icon');
  const currentNameTag = document.getElementById('current-name');
  const currentLinkTag = document.getElementById('current-link');
  const explorerURL = `https://riddler.emoon.dev/${alias}/levels`;
  currentIconTag.setAttribute('src', data['icon_url']);
  currentNameTag.textContent = data['full_name'];
  currentLinkTag.setAttribute('href', explorerURL);
});
