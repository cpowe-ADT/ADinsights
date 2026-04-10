"""Tests for MetaPost thumbnail_url extraction and serialization."""

from __future__ import annotations

from django.utils import timezone

from integrations.meta_page_serializers import MetaPostsItemSerializer
from integrations.tasks import _extract_thumbnail_url


class TestExtractThumbnailUrl:
    """Unit tests for _extract_thumbnail_url helper."""

    def test_returns_empty_when_no_attachments(self):
        assert _extract_thumbnail_url({}) == ""

    def test_returns_empty_when_attachments_data_empty(self):
        row = {"attachments": {"data": []}}
        assert _extract_thumbnail_url(row) == ""

    def test_extracts_picture_field(self):
        row = {
            "attachments": {
                "data": [
                    {
                        "media_type": "photo",
                        "picture": "https://scontent.xx.fbcdn.net/v/thumb.jpg",
                    }
                ]
            }
        }
        assert _extract_thumbnail_url(row) == "https://scontent.xx.fbcdn.net/v/thumb.jpg"

    def test_falls_back_to_media_image_src(self):
        row = {
            "attachments": {
                "data": [
                    {
                        "media_type": "video",
                        "media": {
                            "image": {
                                "src": "https://scontent.xx.fbcdn.net/v/video_thumb.jpg",
                                "height": 720,
                                "width": 1280,
                            }
                        },
                    }
                ]
            }
        }
        assert _extract_thumbnail_url(row) == "https://scontent.xx.fbcdn.net/v/video_thumb.jpg"

    def test_picture_takes_priority_over_media_image(self):
        row = {
            "attachments": {
                "data": [
                    {
                        "picture": "https://example.com/picture.jpg",
                        "media": {"image": {"src": "https://example.com/media.jpg"}},
                    }
                ]
            }
        }
        assert _extract_thumbnail_url(row) == "https://example.com/picture.jpg"

    def test_returns_empty_for_non_dict_attachments(self):
        assert _extract_thumbnail_url({"attachments": "invalid"}) == ""

    def test_truncates_url_to_500_chars(self):
        long_url = "https://example.com/" + "a" * 500
        row = {"attachments": {"data": [{"picture": long_url}]}}
        result = _extract_thumbnail_url(row)
        assert len(result) <= 500


class TestMetaPostsItemSerializerThumbnail:
    """Verify MetaPostsItemSerializer includes thumbnail_url."""

    def test_includes_thumbnail_url(self):
        data = {
            "post_id": "12345_67890",
            "created_time": timezone.now().isoformat(),
            "permalink_url": "https://www.facebook.com/12345/posts/67890",
            "message": "Test post",
            "thumbnail_url": "https://scontent.xx.fbcdn.net/v/thumb.jpg",
            "metrics": {"post_reactions_like_total": 42},
        }
        serializer = MetaPostsItemSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["thumbnail_url"] == "https://scontent.xx.fbcdn.net/v/thumb.jpg"

    def test_thumbnail_url_defaults_to_empty(self):
        data = {
            "post_id": "12345_67890",
            "created_time": timezone.now().isoformat(),
            "permalink_url": "https://www.facebook.com/12345/posts/67890",
            "message": "Test post",
            "metrics": {},
        }
        serializer = MetaPostsItemSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["thumbnail_url"] == ""

    def test_thumbnail_url_in_output(self):
        data = {
            "post_id": "12345_67890",
            "created_time": None,
            "permalink_url": "",
            "message": "",
            "thumbnail_url": "https://example.com/thumb.jpg",
            "metrics": {},
        }
        serializer = MetaPostsItemSerializer(data)
        output = serializer.data
        assert output["thumbnail_url"] == "https://example.com/thumb.jpg"
