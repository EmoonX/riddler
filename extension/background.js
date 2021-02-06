chrome.runtime.onMessage.addListener(
  function(request, sender, sendResponse) {
    if (request.action == "getCookies") {
      // Return cookie from given URL and name
      const details = {
        url: request.url,
        name: request.cookieName
      };
      // Get cookie from browser storage
      chrome.cookies.get(details, cookie => {
        // Send response back to content
        sendResponse({
          name: request.cookieName,
          value: cookie && cookie.value
        });
      });
      // Obligatory return for async event handler
      return true;
    }
  }
);
