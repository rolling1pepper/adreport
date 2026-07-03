"""Бот без сети: whitelist-миддлварь и извлечение поста из апдейта."""

import asyncio
from types import SimpleNamespace

from adreport.bot import WhitelistMiddleware, extract_post_ref
from adreport.core.collector import find_post_link


def _message(**kwargs) -> SimpleNamespace:
    defaults = {"forward_origin": None, "text": None, "caption": None}
    return SimpleNamespace(**{**defaults, **kwargs})


class TestWhitelist:
    def _run(self, allowed, user_id):
        middleware = WhitelistMiddleware(allowed)
        called = []

        async def handler(event, data):
            called.append(event)
            return "handled"

        user = SimpleNamespace(id=user_id) if user_id else None
        result = asyncio.run(middleware(handler, "event", {"event_from_user": user}))
        return result, called

    def test_allowed_passes(self):
        result, called = self._run((80068,), 80068)
        assert result == "handled"
        assert called

    def test_stranger_ignored_silently(self):
        result, called = self._run((80068,), 99999)
        assert result is None
        assert not called

    def test_update_without_user_ignored(self):
        result, called = self._run((80068,), None)
        assert result is None
        assert not called


class TestExtractPostRef:
    def test_forward_from_public_channel(self):
        message = _message(
            forward_origin=SimpleNamespace(
                chat=SimpleNamespace(type="channel", username="naukaprosto"),
                message_id=1482,
            )
        )
        assert extract_post_ref(message) == ("naukaprosto", 1482)

    def test_forward_from_channel_without_username_asks_for_link(self):
        message = _message(
            forward_origin=SimpleNamespace(
                chat=SimpleNamespace(type="channel", username=None),
                message_id=5,
            )
        )
        assert "ссылку" in extract_post_ref(message)

    def test_hidden_forward_origin_asks_for_link(self):
        # MessageOriginHiddenUser: ни chat, ни message_id
        message = _message(forward_origin=SimpleNamespace(sender_user_name="х"))
        assert "скрыт" in extract_post_ref(message)

    def test_link_inside_text(self):
        message = _message(text="глянь https://t.me/naukaprosto/1482 интересно")
        assert extract_post_ref(message) == ("naukaprosto", 1482)

    def test_link_inside_caption(self):
        message = _message(caption="t.me/naukaprosto/1482")
        assert extract_post_ref(message) == ("naukaprosto", 1482)

    def test_plain_text_gets_help(self):
        assert "Перешлите пост" in extract_post_ref(_message(text="привет"))


class TestFindPostLink:
    def test_finds_first_link(self):
        assert find_post_link("а вот t.me/abcd/1 и t.me/efgh/2") == ("abcd", 1)

    def test_none_when_absent(self):
        assert find_post_link("без ссылок") is None
        assert find_post_link(None) is None
