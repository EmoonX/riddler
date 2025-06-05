let port = chrome.runtime.connect(
  { name: `credentials.js` }
);

port.postMessage({'disconnect': true});

/** Listener for whenever credentials are needed. */
port.onMessage.addListener(async data => {
  console.log('Received data from background.js...');
  if (data.username && data.password) {
    // Embed auth box's un/pw into URL and redirect
    const parsedUrl = new URL(data.url);
    let href =
      `${parsedUrl.protocol}//` +
      `${parsedUrl.hostname}${parsedUrl.pathname}`;
    if (href !== window.location.href) {
      href = href.replace('://', `://${data.username}:${data.password}@`);
      window.location.href = href;
    }
    return
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
      const credentials = data.unlockedCredentials;
      box.find('.realm').text(`"${data.realm}"`);
      if (credentials) {
        box.find('[name="username"]').attr('value', credentials.username);
        box.find('[name="password"]').attr('value', credentials.password);
      }
      $('head').append(`<link rel="stylesheet" href="${boxCss}">`)
      $('body').append(box[0].outerHTML);
      $('[name="username"]').trigger('focus');
    });
});
