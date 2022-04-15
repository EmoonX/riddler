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
  const HOSTS_URL = 'https://riddler.app/get-riddle-hosts';
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
  const DATA_URL = 'https://riddler.app/get-current-riddle-data';
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
  const currentIcon = document.getElementById('current-icon');
  const currentName = document.getElementById('current-name');
  const currentLink = document.getElementById('current-link');
  const visitedLevel = document.getElementById('visited-level');
  const explorerURL = `https://riddler.app/${alias}/levels`;
  currentIcon.setAttribute('src', data['icon_url']);
  currentName.textContent = data['full_name'];
  currentLink.setAttribute('href', explorerURL);
  visitedLevel.textContent = `Level ${data['visited_level']}`;
});
