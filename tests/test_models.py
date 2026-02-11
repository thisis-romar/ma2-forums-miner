"""Tests for data models."""

from ma2_forums_miner.models import Post, Asset, ThreadMetadata


class TestPost:
    def test_defaults(self):
        post = Post(author="alice")
        assert post.author == "alice"
        assert post.post_date is None
        assert post.post_text == ""
        assert post.post_number == 1

    def test_to_dict(self):
        post = Post(author="bob", post_text="hello", post_number=3)
        d = post.to_dict()
        assert d["author"] == "bob"
        assert d["post_text"] == "hello"
        assert d["post_number"] == 3


class TestAsset:
    def test_defaults(self):
        asset = Asset(filename="macro.xml", url="https://example.com/file")
        assert asset.size is None
        assert asset.checksum is None
        assert asset.download_count is None
        assert asset.post_number is None

    def test_file_type(self):
        assert Asset(filename="macro.xml", url="u").file_type == ".xml"
        assert Asset(filename="show.GZ", url="u").file_type == ".gz"
        assert Asset(filename="noext", url="u").file_type == ""

    def test_to_dict_includes_file_type(self):
        asset = Asset(filename="test.zip", url="https://x.com/f", size=1024)
        d = asset.to_dict()
        assert d["filename"] == "test.zip"
        assert d["size"] == 1024
        assert d["file_type"] == ".zip"


class TestThreadMetadata:
    def test_defaults(self):
        meta = ThreadMetadata(
            thread_id="123", title="Test", url="https://x.com", author="alice"
        )
        assert meta.posts == []
        assert meta.assets == []
        assert meta.replies == 0
        assert meta.views == 0
        assert meta.asset_types == []

    def test_asset_types_single(self):
        meta = ThreadMetadata(
            thread_id="1", title="T", url="u", author="a",
            assets=[Asset(filename="a.xml", url="u"), Asset(filename="b.xml", url="u")]
        )
        assert meta.asset_types == [".xml"]

    def test_asset_types_multiple(self):
        meta = ThreadMetadata(
            thread_id="1", title="T", url="u", author="a",
            assets=[
                Asset(filename="a.xml", url="u"),
                Asset(filename="b.zip", url="u"),
                Asset(filename="c.xml", url="u"),
            ]
        )
        assert meta.asset_types == [".xml", ".zip"]

    def test_asset_type_category_no_assets(self):
        meta = ThreadMetadata(thread_id="1", title="T", url="u", author="a")
        assert meta.asset_type_category == "no_assets"

    def test_asset_type_category_single(self):
        meta = ThreadMetadata(
            thread_id="1", title="T", url="u", author="a",
            assets=[Asset(filename="a.xml", url="u")]
        )
        assert meta.asset_type_category == "xml"

    def test_asset_type_category_mixed(self):
        meta = ThreadMetadata(
            thread_id="1", title="T", url="u", author="a",
            assets=[Asset(filename="a.xml", url="u"), Asset(filename="b.zip", url="u")]
        )
        assert meta.asset_type_category == "mixed"

    def test_to_dict_nested(self):
        post = Post(author="alice", post_text="hi", post_number=1)
        asset = Asset(filename="f.xml", url="https://x.com/f")
        meta = ThreadMetadata(
            thread_id="1", title="T", url="https://x.com",
            author="alice", posts=[post], assets=[asset]
        )
        d = meta.to_dict()
        assert len(d["posts"]) == 1
        assert d["posts"][0]["author"] == "alice"
        assert len(d["assets"]) == 1
        assert d["assets"][0]["filename"] == "f.xml"
        assert d["assets"][0]["file_type"] == ".xml"
        assert d["asset_types"] == [".xml"]
        assert d["asset_type_category"] == "xml"
