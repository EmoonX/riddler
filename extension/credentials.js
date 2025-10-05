const port = chrome.runtime.connect({ name: 'credentials.js' });

/** One-shot listener for prompting credentials. */
port.onMessage.addListener(data => {
  console.log('Received data from background.js...');
  port.disconnect();
  if (! data.realm) {
    // Not from an auth request; nothing to show
    return;
  }
  // Prompt user with auth box
  const box = $($.parseHTML(data.boxHTML));
  const credentials = data.unlockedCredentials;
  box.find('.realm').text(`"${data.realm}"`);
  if (credentials) {
    box.find('input[name="username"]').attr('value', credentials.username);
    box.find('input[name="password"]').attr('value', credentials.password);
  }
  $('head').append(`<style>${data.boxCSS}</style>`);
  $('body').append(box[0].outerHTML);
  $('input[name="username"]').trigger('focus');
  $('form.credentials').on('submit', embedCredentials);
});

/** Embed credentials (`un:pw@...`) into URL, replacing current page. */
function embedCredentials(e) {
  e.preventDefault(); // block GET-submit
  const parsedUrl = new URL(window.location.href);
  parsedUrl.username = $('input[name="username"]').val();
  parsedUrl.password = $('input[name="password"]').val();
  window.location.replace(parsedUrl.toString());
}
