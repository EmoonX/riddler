# F.A.Q.

#### The extension is stuck or doesn't seem to be working.

1. Make sure you're indeed [logged in](/login?redirect_url=/faq);
2. Make sure you're running the latest extension's version (as shown [here](https://chromewebstore.google.com/detail/riddler/pipfgmnooemfjelejnboacpkgodhbddh));
3. Visit (or reload) an actual level page;
4. If somehow the extension's menu is still stuck/broken, then usually just closing the browser and opening it again does the trick.

#### I had progress in some riddle(s) before I started using R. Do I need to retrace my steps from level 1?

Thankfully, you don't. It used to be that way in the past; however, starting from circa version 0.5, you can now _unlock_ any level at any time, and _solve any unlocked level_ at any time. This is supposed to give players more flexibility, as everyone has their own goals and pace.

You won't, of course:
- get points for any of the previous unsolved levels;
- be able to have a riddle/set marked as `completed` until solving all of the (obligatory) levels up to and including the final one (if any).

#### Do I keep track of my progress when changing browsers/PCs?

Absolutely. All your user data is safely stored in our databases on [https://riddler.app]([https://riddler.app). That goes for your unlocked/solved levels, recorded pages, credentials, achievements, and even the last riddle & level you visited. No local data is saved in your browser except for cache stuff.

If you _do need_ a backup of your progress, don't forget to export your account data through the [settings page](https://riddler.app/settings).

---

## Credentials

For info about the workings and rationale behind R's custom credentials box, please refer to [this section of the privacy policy](https://riddler.app/privacy-policy#riddle-credentials).

#### I am not able to record progress for a password-protected page.

Almost certainly, you haven't recorded the _credentials_ for that specific folder/path yet. This usually happens post-extension install when you're navigating with previous session/cache data. To amend it:
- Press `Ctrl+F5` to trigger a hard-refresh (close/open browser if it doesn't work at first). This should bring the credentials box, and then you can just input the correct username/password as usual;
- If all else fails, directly embedding the credentials into the URL (`https://user:pass@riddledomain.com/folder/page.htm`) also works.

#### The password field is explicitly showing the password without the ●●●●●.

That's intentional. Folder-specific credentials contain no sensitive info; so there's no point in hiding it either. Using a `type="password"` input field makes the user too prone to commit spelling mistakes (an extra letter, a wrong one, etc), which tends to happen all the time. Therefore, the plain `type="text"` password is, riddle-wise, also an improvement over the native browser box UI.

---

## Bot

#### The bot isn't sending me DMs on level solve / achievement unlock.

Due to the way Discord works, you need to share a common server with a bot for it to be able to send messages to you. If you aren't receiving any, that means you're probably not in Wonderland yet. Just [join the server](https://discord.gg/ktaPPtnPSn) and you should start receiving DMs.

#### I get an _Unknown Integration_ error when trying to run a command.

This can rarely happen, usually after the bot had to be restarted for an update. To fix it, simply restart the Discord client (by closing _from the tray icon_ on PC, or hard-closing the app on mobile; then opening it again).

---

## Content

#### What is a `hidden` page? What about `alias`es/`removed`?

Pages are marked `hidden` when, even though valid and non-404, they are essentially unimportant or irrelevant by themselves. As such, those usually aren't viewable through the explorer, nor they increment any page counters (including [the global one here](/)).

- an `alias` functions as a copy of a canonical page. Let's say you have two pages, `morse.htm` and `morsecode.htm`, both with identical content. `morsecode.htm` (hidden) is marked as an alias of `morse.htm`. Thus, when you visit `morsecode.htm`, the system _**also**_ registers an access for `morse.htm`. Therefore, aliases are used to prevent players from having to find superfluous/duplicated pages, and also avoids those polluting the explorer. 
- a `removed` flag usually means that the page _used to be part of the level_, but not anymore. It can either be about a changed answer, an unreachable leftover, or just a plain 404.

Besides the aforementioned cases, a page can also be a raw `hidden` instance, which usually means that it is (at least) one of the following:
- not even remotely interesting;
- requires the player to get something wrong by chance (e.g eggs for correcting spelling mistakes);
- made of randomized/repeated stuff (e.g a certain maze in Cipher's level 50);
- an alias-like redirect (which then doesn't need to marked as an `alias`);
- a trivial redirect (like the countless `/folder/index.htm ➜ /folder/xyz.htm` ones).

#### I've found a missing page. Do I need to report it?

Generally, you don't. Any missing pages are added to the system as soon as someone finds them. Then, we (hopefully sooner than later) catalog those as part of their respective levels.

If you do have a batch that you want to see cataloged ASAP, just reach one of our admins in [Wonderland](https://discord.gg/ktaPPtnPSn); they should be able to get things up-to-date for everyone.

#### I want to see riddle X on R!

Likewise, just reach one of the admins. Be it if you just want to suggest a nice contender, or if you do have _finished_ said riddle at some point, we'd love to have your contribution. It's easier than one might think, and you'll be credited accordingly &mdash; if you wish so.

---

## Beginnings

Around early 2020, two brewed ideas started being applied for _Cipher: Crack the Code_: a **Discord bot**, and a **dynamic website overhaul**.
- [the bot](/static/old/bot.py) was born as a way to make the Cipher Discord server _riddle-aware_, by automatically setting up channels + roles and allowing players to run a `/unlock` command to get access to private level help channels, based on how far they were in the riddle.
- [the beta website](/static/old/cipher-beta.png) ran on a VPS and thus allowed stuff not available to simple static hosting: automated progress tracking, leaderboards, and so on. Some backend procedures were applied on every single level page access.

The beta website never became a finished product (you can, however, still find traces of it in [Cipher's stylesheet](http://gamemastertips.com/cipher/style-new.css)). The bot, on the other hand, became a staple around, and was later adapted to become the late RNS Riddle's server one (with no modifications bar name and avatar).

One day, a simple idea came to mind: [what about expanding the bot to other Discord servers](/static/old/birth-bot.png)? And what if we could apply whatever had been done for the Cipher's beta, but for _any suitable riddle_? Of course, we can't expect every riddle maker out there to simply remake their own webservers to implement the same funcionalities (can we...?). So there was probably a missing link to be found...

The missing link, of course, [was a browser extension](/static/old/birth-extension.png). And the rest is history.

#### What were the main inspirations?

One of the main ones &mdash; as random as it might sound at first &mdash; was a certain project called [RetroAchievements](https://retroachievements.org); which, as the name implies, deals with adding achievements for old (console) games.

Some of the similarities are pretty straightforward:
- Both have achievements (!);
- Both work by essentially setting up a shell over the third-party content itself (emulator module = extension) without having to toy with it directly (which would be impossible in most cases anyway);
- Both aim to revitalize an old format by creating an ecosystem/platform around it, and giving people new reasons to play (especially the most obscure entries).

---

#### When will version 1.0 finally arrive?

Whenever the project is stable and mature enough for it to be considered a _finished product_. As loosely stated at some point, this isn't an endeavor supposed to go on forever, and `1.0` is a good place for it to be labeled as _**done**_. Once that happens, the updates won't just cease &mdash; but rather, we will be able to take our time and focus primarily on content, quality-of-life enhancements and new tools.

Until then, there are still several bugs in need of fixing and several important features waiting to see the light of the day. As of the time of the writing:
- profile pages;
- mobile-responsive website;
- a settings/tools tab for the extension;
- a riddles tab for moving across them directly from the extension (talk about way due);
- handy link lists containing all the unlocked pages in a single place (and a multi-export for all riddles as a `.zip`);
- [REDACTED]

[The current codebase](https://github.com/EmoonX/riddler), with `>13k` lines of code and `>1k` commits, is now robust enough in a way that we're **_much, much closer_** to the end of the journey than wherever we were at the beginning. And, while giving dates is always a messy subject... it should happen around _early 2026_ or so.

And then the boat should float by itself as a bastion for the years to come.

#### Why does this website overall look so eerily similar to [Cipher's](http://gamemastertips.com/cipher/cipher.htm)?

Because both were designed by the same person.

---

