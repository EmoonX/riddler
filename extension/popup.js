import {
  initExplorer
}
  from './explorer.js';

/** Current riddle being played. */
var currentRiddle;

/** Send synchronous GET request to target URL and return response text. */
function request(url) {
  const request = new XMLHttpRequest();
  request.open('GET', url, false);
  request.send(null);
  if (request.status === 200) {
    const data = request.responseText;
    return data;
  }
}

/** Retrieve riddle host domains. */
function getRiddleHosts() {
  const HOSTS_URL = 'https://riddler.app/get-riddle-hosts';
  const data = request(HOSTS_URL);
  const hosts = data.split(" ");
  return hosts;
}

/** Update host permissions on button click. */
function updateHosts() {
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

/** Retrieve current riddle data for authenticated user. */
function getCurrentRiddleData() {
  const DATA_URL = 'https://riddler.app/get-current-riddle-data';
  const data = request(DATA_URL);
  return data;
}

function getCurrentLevelPages(riddle, level_name) {
  const PAGES_URL =
    `https://riddler.app/${riddle}/levels/get-pages/${level_name}`;
  const pages = request(PAGES_URL);
  return pages;
}

window.onload = (_ => {
  // Set "Update hosts" button click event
  document.getElementsByName('update-hosts')[0]
    .addEventListener('click', updateHosts);
  
  // Show current riddle info in extension's popup
  const text = getCurrentRiddleData();
  const data = JSON.parse(text);
  const alias = data['alias'];
  const levelName = data['visited_level'];
  const currentIcon = document.getElementById('current-icon');
  const currentName = document.getElementById('current-name');
  const currentLink = document.getElementById('current-link');
  const visitedLevel = document.getElementById('visited-level');
  const explorerURL = `https://riddler.app/${alias}/levels`;
  currentIcon.setAttribute('src', data['icon_url']);
  currentName.textContent = data['full_name'];
  currentLink.setAttribute('href', explorerURL);
  visitedLevel.innerHTML = `Level <strong>${levelName}</strong>`;

  // Build page explorer
  const pagesData = getCurrentLevelPages(alias, levelName);
  initExplorer(pagesData, levelName);
});
