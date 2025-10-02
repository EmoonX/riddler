const port = chrome.runtime.connect({ name: 'credentials.js' });

/** One-shot listener for prompting/embedding credentials. */
const credentialsListener = (data => {
  console.log('Received data from background.js...');
  port.onMessage.removeListener(credentialsListener);

  if (data.username && data.password) {
    // Embed auth box's un/pw into URL and redirect
    const parsedUrl = new URL(data.url);
    parsedUrl.username = data.username;
    parsedUrl.password = data.password;
    parsedUrl.searchParams.delete('username');
    parsedUrl.searchParams.delete('password');
    window.location.href = parsedUrl.toString();
  }
  if (data.boxHtml) {
    // Prompt user with auth box
    const box = $($.parseHTML(data.boxHtml));
    const credentials = data.unlockedCredentials;
    box.find('.realm').text(`"${data.realm}"`);
    if (credentials) {
      box.find('[name="username"]').attr('value', credentials.username);
      box.find('[name="password"]').attr('value', credentials.password);
    }
    $('head').append(`<style>${data.boxCss}</style>`);
    $('body').append(box[0].outerHTML);
    $('[name="username"]').trigger('focus');
  }
});
port.onMessage.addListener(credentialsListener);
