import {  
  changeLevel,
  changeLevelSet,
  clickFile,
  doubleClickFile,
  insertFiles,
  updateStateInPopup,
} from './explorer.js';

/** Updates host permissions on button click. */
async function updateHosts() {
  console.log('Updating hosts...');
  const SERVER_URL = 'https://emoon.dev';
  const url = `${SERVER_URL}/get-riddle-hosts`;
  await fetch(url)
    .then(response => response.json())
    .then(hosts => {
      console.log(`Hosts found:`);
      console.log(Object.keys(hosts));
      chrome.permissions.request(
        { origins: Object.keys(hosts)},
        granted => {
          if (granted) {
            console.log('Optional host permissions granted.');
          } else {
            console.log('Couldn\'t grant optional host permissions.');
            console.log(chrome.runtime.lastError);
          }
        }
      );
    });
}

$(_ => {
  // Set "Update hosts" button click event
  $('[name=update-hosts]').on('click', updateHosts);

  // Set explorer events
  $('#level').on('click', '#previous-set:not(.disabled)', changeLevelSet);
  $('#level').on('click', '#next-set:not(.disabled)', changeLevelSet);
  $('#level').on('click', '#previous-level:not(.disabled)', changeLevel);
  $('#level').on('click', '#next-level:not(.disabled)', changeLevel);
  $('.page-explorer').on('click', 'figure.file', clickFile);
  $('.page-explorer').on('dblclick', 'figure.file', doubleClickFile);

  // Get message data from background.js
  let port = chrome.runtime.connect(
    { name: 'Communication with background.js' }
  );
  port.onMessage.addListener(data => {
    console.log('Received data from background.js...');
    const alias = data.currentRiddle;
    if (alias) {
      // Update explorer.js members
      const riddles = data.riddles;
      updateStateInPopup(riddles, alias);

      // Show current riddle info in extension's popup
      const riddle = riddles[alias];
      const setName = riddle.lastVisitedSet;
      const levelName = riddle.lastVisitedLevel;
      const level = riddle.levels[setName][levelName];
      const explorerURL = `https://emoon.dev/${alias}/levels`;
      $('#riddle > .icons img.current').attr('src', riddle.iconUrl);
      $('#riddle > .full-name').text(riddle.fullName);
      $('#riddle a').attr('href', explorerURL);
      $('#level > var#current-level').text(levelName);
      if (!level.previousSet) {
        $('#level > #previous-set').addClass('disabled');
      }
      if (!level.previousLevel) {
        $('#level > #previous-level').addClass('disabled');
      }
      if (!level.nextLevel) {
        $('#level > #next-level').addClass('disabled');
      }
      if (!level.nextSet) {
        $('#level > #next-set').addClass('disabled');
      }
      // Build HTML for list of files of currently visited level
      const levelPages = level.pages['/'];
      insertFiles($('.page-explorer'), levelPages, -1);
    }
  });
});
