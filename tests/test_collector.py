"""Коллектор без сети: разбор ссылок и маппинг фейковых сообщений Telethon."""

from types import SimpleNamespace

import pytest

from adreport.core.collector import (
    PostLinkError,
    album_caption,
    media_type_of,
    parse_post_link,
    pick_album_anchor,
    reactions_of,
)


class TestParsePostLink:
    @pytest.mark.parametrize(
        "link",
        [
            "https://t.me/naukaprosto/1482",
            "http://t.me/naukaprosto/1482",
            "t.me/naukaprosto/1482",
            "telegram.me/naukaprosto/1482",
            "https://t.me/naukaprosto/1482?single",
            "https://t.me/naukaprosto/1482/",
        ],
    )
    def test_valid_variants(self, link):
        assert parse_post_link(link) == ("naukaprosto", 1482)

    @pytest.mark.parametrize(
        "link",
        [
            "https://t.me/naukaprosto",  # канал без поста
            "https://example.com/naukaprosto/1482",
            "просто текст",
            "https://t.me/ab/12",  # username короче 4 символов
        ],
    )
    def test_invalid(self, link):
        with pytest.raises(PostLinkError):
            parse_post_link(link)

    def test_private_channel_link_gets_dedicated_message(self):
        with pytest.raises(PostLinkError, match="приватный"):
            parse_post_link("https://t.me/c/1234567/89")


def _reaction(emoticon, count):
    return SimpleNamespace(reaction=SimpleNamespace(emoticon=emoticon), count=count)


def _custom_reaction(count):
    # у ReactionCustomEmoji нет атрибута emoticon
    return SimpleNamespace(reaction=SimpleNamespace(document_id=42), count=count)


class TestReactionsOf:
    def test_plain_emoji(self):
        message = SimpleNamespace(
            reactions=SimpleNamespace(results=[_reaction("👍", 10), _reaction("❤", 5)])
        )
        assert reactions_of(message) == [
            {"emoji": "👍", "count": 10},
            {"emoji": "❤", "count": 5},
        ]

    def test_custom_emoji_aggregated(self):
        message = SimpleNamespace(
            reactions=SimpleNamespace(
                results=[_reaction("👍", 10), _custom_reaction(3), _custom_reaction(4)]
            )
        )
        assert reactions_of(message) == [
            {"emoji": "👍", "count": 10},
            {"emoji": "…", "count": 7},
        ]

    def test_no_reactions(self):
        assert reactions_of(SimpleNamespace(reactions=None)) == []


class TestAlbum:
    def test_anchor_is_min_id(self):
        messages = [SimpleNamespace(id=7), SimpleNamespace(id=5), SimpleNamespace(id=6)]
        assert pick_album_anchor(messages).id == 5

    def test_caption_taken_from_message_with_text(self):
        messages = [
            SimpleNamespace(id=5, message=""),
            SimpleNamespace(id=6, message="подпись альбома"),
        ]
        assert album_caption(messages) == "подпись альбома"

    def test_caption_empty_when_no_text(self):
        assert album_caption([SimpleNamespace(id=5, message="")]) == ""


class TestMediaType:
    def test_album(self):
        assert media_type_of(SimpleNamespace(grouped_id=1, photo=None)) == "album"

    def test_photo(self):
        message = SimpleNamespace(grouped_id=None, photo=object(), video=None)
        assert media_type_of(message) == "photo"

    def test_text_only(self):
        message = SimpleNamespace(grouped_id=None, photo=None, video=None, media=None)
        assert media_type_of(message) is None
