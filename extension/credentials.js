let port = chrome.runtime.connect(
  { name: 'Communication with background.js' }
);

/** Listener for whenever credentials are needed. */
port.onMessage.addListener(async data => {
  console.log('Received data from background.js...')
  if (data.username && data.password) {
    // Embed auth box's un/pw into URL and redirect
    const url = data.parsedUrl;
    window.location.href =
      `${url.protocol}//` +
      `${url.username}:${url.password}@` +
      `${url.hostname}${url.pathname}`;
  }
  if (! data.realm) {
    // Gambiarra
    return;
  }
  const credentialsUrl = chrome.runtime.getURL('credentials.html');
  await fetch(credentialsUrl)
    .then(response => response.text())
    .then(html => {
      // Prompt user with auth box
      const box = $($.parseHTML(html));
      const boxCss = chrome.runtime.getURL('credentials.css');
      box.find('.realm').text(`"${data.realm}"`);
      $('head').append(`<link rel="stylesheet" href="${boxCss}">`)
      $('body').append(box[0].outerHTML);
    });
});
