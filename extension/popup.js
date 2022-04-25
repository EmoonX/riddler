import { update, insertFiles } from './explorer.js';

/** Updates host permissions on button click. */
function updateHosts() {
  const HOSTS_URL = 'https://riddler.app/get-riddle-hosts';
  $.get(HOSTS_URL, data => {
    const hosts = data.split(' ');
    chrome.permissions.request(
      { origins: hosts },
      granted => {
        if (granted) {
          console.log('OK!');
        } else {
          console.log('NO :(');
        }
      }
    );
  });
}

$(_ => {
  // Set "Update hosts" button click event
  $('[name=update-hosts]').on('click', updateHosts);

  // Get message data from background.js
  let port = chrome.extension.connect(
    { name: 'Communication with background.js' }
  );
  port.onMessage.addListener(data => {
    console.log('Received data from background.js...');
    console.log(data);
    const alias = data.currentRiddle;
    if (alias) {
      // Update explorer.js members
      const riddles = data.riddles;
      update(riddles, alias);

      // Show current riddle info in extension's popup
      const riddle = riddles[alias];
      const levelName = riddle.visitedLevel;
      const explorerURL = `https://riddler.app/${alias}/levels`;
      $('#current-icon').attr('src', riddle.iconUrl);
      $('#current-name').text(riddle.fullName);
      $('#current-link').attr('href', explorerURL);
      $('#visited-level').text(`Level ${levelName}`);

      // Build HTML for list of files of currently visited level
      insertFiles($('.page-explorer'), riddle.pages['/'], -1);
    }
  });
});
