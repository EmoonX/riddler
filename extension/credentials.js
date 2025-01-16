let port = chrome.runtime.connect(
  { name: 'Communication with background.js' }
);
port.onMessage.addListener(async data => {
  if (! data.realm) {
    // Gambiarra
    return;
  }

  console.log('Connected to credentials.js...')
  const credentialsUrl = chrome.runtime.getURL('credentials.html');
  await fetch(credentialsUrl)
    .then(response => response.text())
    .then(html => {
      const box = $($.parseHTML(html));
      box.find('.realm').text(data.realm);
      document.write(box[0].outerHTML);
    });
});
