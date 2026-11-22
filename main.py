"""App entry point: starts the NiceGUI web server."""
import os
from contextlib import contextmanager
from pathlib import Path

from nicegui import app, ui

from game.lobby import registry
from game.persistence import make_store
from views.common import BrowserGone
from views.invites import watch_invites
from views.leaderboard import leaderboard_page, profile_page
from views.lobby import lobby_page
from views.start import start_page
from views.stats import friends_page, stats_page

BASE = Path(__file__).parent
# This number changes when the CSS file changes, ensuring the browser loads the new version.
CSS_VERSION = int((BASE / 'static' / 'styles.css').stat().st_mtime)

# Mobile keyboard: it should overlay the game instead of pushing the table upward.
# Only the chat bar (and floating messages) move above the keyboard.
KEYBOARD_SCRIPT = """<script>
(function () {
  const vv = window.visualViewport;
  if (!vv) return;
  function place() {
    const keyboard = Math.max(0, window.innerHeight - vv.height - vv.offsetTop);
    document.querySelectorAll('.chatbar, .chatfloat').forEach(el => {
      el.style.transform = keyboard > 0 ? 'translateY(' + (-keyboard) + 'px)' : '';
    });
  }
  vv.addEventListener('resize', place);
  vv.addEventListener('scroll', place);
  document.addEventListener('focusin', event => {
    const inChat = event.target.closest && event.target.closest('.chatbar');
    if (inChat && document.querySelector('.board')) {
      [50, 300].forEach(ms => setTimeout(() => { window.scrollTo(0, 0); place(); }, ms));
    }
  });
  document.addEventListener('focusout', () => setTimeout(place, 50));
})();
</script>"""

# Load the CSS file and fonts once for all pages.
# max_cache_age=0: The browser always reloads the CSS file so design changes appear immediately.
app.add_static_files('/static', BASE / 'static', max_cache_age=0)
ui.add_head_html(
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=DM+Serif+Display'
    '&family=Inter:wght@500;600;700&display=swap">'
    f'<link rel="stylesheet" href="/static/styles.css?v={CSS_VERSION}">' + KEYBOARD_SCRIPT,
    shared=True,
)


@contextmanager
def ignore_gone_browser():
    """Pages need a connected browser. Link previews (e.g. WhatsApp, iMessage) never connect –
    then the page is simply not built, instead of logging an error."""
    try:
        yield
    except BrowserGone:
        pass


@ui.page('/')
async def index() -> None:
    with ignore_gone_browser():
        await start_page()
        await watch_invites()   # signed in: counts as online and sees invites from friends


@ui.page('/stats')
async def stats() -> None:
    with ignore_gone_browser():
        await stats_page()
        await watch_invites()   # signed in: counts as online and sees invites from friends


@ui.page('/friends')
async def friends(back: str = '') -> None:
    with ignore_gone_browser():
        await friends_page(back)
        await watch_invites()   # signed in: counts as online and sees invites from friends


@ui.page('/leaderboard')
async def leaderboard(sort: str = '') -> None:
    with ignore_gone_browser():
        await leaderboard_page(sort)
        await watch_invites()   # signed in: counts as online and sees invites from friends


@ui.page('/players/{username}')
async def player_profile(username: str) -> None:
    with ignore_gone_browser():
        await profile_page(username)
        await watch_invites()   # signed in: counts as online and sees invites from friends


@ui.page('/lobby/{code}')
async def lobby(code: str) -> None:
    with ignore_gone_browser():
        await lobby_page(code)
        await watch_invites()   # signed in: counts as online and sees invites from friends


# Persist game state: online in the database (DATABASE_URL), locally in data/prophecy.db.
store = make_store(BASE)
app.on_startup(lambda: registry.attach_store(store))
# lambda: NiceGUI would otherwise pass the app itself as the first argument (the timeout).
app.on_shutdown(lambda: store.flush())

# Advance all lobbies regularly (bots take turns, pauses end) and save changes.
app.timer(0.25, registry.tick_all)

# NiceGUI requires this condition so the server starts correctly on reload.
# Online (on Render), the host sets the RENDER variable and specifies the port.
# In that case: externally accessible, no automatic reload, and no browser window opened.
ONLINE = 'RENDER' in os.environ

if __name__ in {'__main__', '__mp_main__'}:
    ui.run(
        title='Prophecy',
        host='0.0.0.0' if ONLINE else '127.0.0.1',
        port=int(os.environ.get('PORT', 8080)),
        reload=not ONLINE,
        show=not ONLINE,
        # overlays-content: The mobile keyboard overlays the page instead of pushing it up.
        viewport='width=device-width, initial-scale=1, interactive-widget=overlays-content',
    )
