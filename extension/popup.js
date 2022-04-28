import { updateStateInPopup, insertFiles } from './explorer.js';

/** Updates host permissions on button click. */
function updateHosts() {
  const HOSTS_URL = 'https://riddler.app/get-riddle-hosts';
  let hosts;
  $.get({
    // Async request because Firefox got... issues
    url: HOSTS_URL,
    async: false,
    success: data => {
      hosts = data.split(' ');
      console.log(hosts);
    },
  });
  chrome.permissions.request(
    { origins: hosts },
    granted => {
      if (granted) {
        console.log('OK!');
      } else {
        console.log('NO :(');
        console.log(chrome.runtime.lastError);
      }
    }
  );
}

$(_ => {
  // Set "Update hosts" button click event
  $('[name=update-hosts]').on('click', updateHosts);

  // Get message data from background.js
  let port = chrome.runtime.connect(
    { name: 'Communication with background.js' }
  );
  port.onMessage.addListener(data => {
    console.log('Received data from background.js...');
    console.log(data);
    const alias = data.currentRiddle;
    if (alias) {
      // Update explorer.js members
      const riddles = data.riddles;
      updateStateInPopup(riddles, alias);

      // Show current riddle info in extension's popup
      const riddle = riddles[alias];
      const levelName = riddle.visitedLevel;
      const level = riddle.levels[levelName];
      const explorerURL = `https://riddler.app/${alias}/levels`;
      $('#riddle > .icons img.current').attr('src', riddle.iconUrl);
      $('#riddle > .full-name').text(riddle.fullName);
      $('#riddle a').attr('href', explorerURL);
      $('#level > var.current').text(levelName);
      if (!level.previous) {
        $('#level > .previous').addClass('disabled');
      }
      if (!level.next) {
        $('#level > .next').addClass('disabled');
      }
      // Build HTML for list of files of currently visited level
      const levelPages = level.pages['/'];
      insertFiles($('.page-explorer'), levelPages, -1);
    }
  });
});
