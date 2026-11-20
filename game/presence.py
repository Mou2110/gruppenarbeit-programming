"""Who is online right now, and invitations from friends into a lobby.

Everything here lives only in memory: after a server restart nobody is online until they open a page again.
A player counts as online as long as at least one page of the game is open in their browser.
The user interface registers each open page with connect() and a function that shows the invitation popup.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

INVITE_GAP = 10.0  # seconds before the same friend can be invited again (no spam)


class InviteError(Exception):
    """The invitation cannot be sent (the text is shown to the player)."""


@dataclass
class Invite:
    sender_name: str
    code: str


class Presence:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self.clock = clock
        self.pages: dict[object, tuple[str, Callable[[Invite], None]]] = {}  # open page -> (account, show popup)
        self.last_invite: dict[tuple[str, str], float] = {}                  # (sender, friend) -> time

    def connect(self, page: object, account: str, on_invite: Callable[[Invite], None]) -> None:
        self.pages[page] = (account, on_invite)

    def disconnect(self, page: object) -> None:
        self.pages.pop(page, None)

    def is_online(self, account: str) -> bool:
        return any(owner == account for owner, _ in self.pages.values())

    def invite(self, sender: str, sender_name: str, friend: str, code: str) -> int:
        """Show the invitation on every open page of the friend. Returns on how many pages it appeared."""
        if friend == sender:
            raise InviteError('You cannot invite yourself.')
        if not self.is_online(friend):
            raise InviteError('Your friend is not online any more.')
        now = self.clock()
        if now - self.last_invite.get((sender, friend), -INVITE_GAP) < INVITE_GAP:
            raise InviteError('You just invited them. Give them a moment.')
        self.last_invite[(sender, friend)] = now
        shown = 0
        for page, (owner, on_invite) in list(self.pages.items()):
            if owner != friend:
                continue
            try:
                on_invite(Invite(sender_name, code))
                shown += 1
            except Exception:  # page no longer exists
                self.pages.pop(page, None)
        return shown


presence = Presence()
