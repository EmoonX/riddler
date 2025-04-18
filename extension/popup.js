import {  
  changeLevel,
  changeLevelSet,
  clickFile,
  doubleClickFile,
  insertFiles,
  SERVER_URL,
  updateStateInPopup,
} from './explorer.js';

/** Updates host permissions on button click. */
async function updateHosts() {
  console.log('Updating hosts...');
  await fetch(`${SERVER_URL}/get-riddle-hosts`)
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

$(() => {
  // Set explorer events
  $('#level').on('click', '#previous-set:not(.disabled)', changeLevelSet);
  $('#level').on('click', '#next-set:not(.disabled)', changeLevelSet);
  $('#level').on('click', '#previous-level:not(.disabled)', changeLevel);
  $('#level').on('click', '#next-level:not(.disabled)', changeLevel);
  $('.page-explorer').on('click', 'figure.file', clickFile);
  $('.page-explorer').on('dblclick', 'figure.file', doubleClickFile);

  // Set button click events
  $('[name=login]').on('click', () => {
    window.open(`${SERVER_URL}/login`, '_blank');
  });
  $('[name=update-hosts]').on('click', updateHosts);

  // Get message data from background.js
  let port = chrome.runtime.connect(
    { name: 'popup.js' }
  );
  port.onMessage.addListener(data => {
    console.log('Received data from background.js...');
    const alias = data.currentRiddle;
    if (alias) {
      // Update explorer.js members
      const riddles = data.riddles;
      updateStateInPopup(riddles, alias);

      // Toggle logged in riddle data
      $('#currently-playing').toggle(true);
      $('[name=login]').toggle(false);

      // Show current riddle info in extension's popup
      const riddle = riddles[alias];
      const setName = riddle.lastVisitedSet;
      const levelName = riddle.lastVisitedLevel;
      const level = riddle.levels[setName][levelName];
      const explorerURL = `${SERVER_URL}/${alias}/levels`;
      $('#riddle > .icons img.current').attr('src', riddle.iconUrl);
      $('#riddle > .full-name').text(riddle.fullName);
      $('#riddle a').attr('href', explorerURL);
      $('#level > var#current-level').text(levelName);
      if (level.previousSet) {
        $('#level > #previous-set').removeClass('disabled');
      }
      if (level.previousLevel) {
        $('#level > #previous-level').removeClass('disabled');
      }
      if (level.nextLevel) {
        $('#level > #next-level').removeClass('disabled');
      }
      if (level.nextSet) {
        $('#level > #next-set').removeClass('disabled');
      }
      // Build HTML for list of files of currently visited level
      insertFiles($('.page-explorer'), level.pages['/'], -1, '');
    }
  });
});
