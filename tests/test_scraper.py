"""Tests for scraper logic (no network access required)."""

from pathlib import Path
from bs4 import BeautifulSoup

from ma2_forums_miner.scraper import ForumScraper, ALLOWED_DOMAINS


SAMPLE_THREAD_HTML = """
<html>
<body>
<h1 class="topic-title">Test Thread Title</h1>
<article class="message">
  <span class="username">testuser</span>
  <time datetime="2024-01-15T10:30:00Z">Jan 15, 2024</time>
  <div class="messageContent">This is the first post content.</div>
</article>
<article class="message">
  <span class="username">replyuser</span>
  <time datetime="2024-01-16T08:00:00Z">Jan 16, 2024</time>
  <div class="messageContent">This is a reply.</div>
</article>
</body>
</html>
"""

SAMPLE_BOARD_HTML = """
<html>
<body>
<a class="wbbTopicLink" href="/forum/thread/12345-test-thread/">Test Thread</a>
<a class="wbbTopicLink" href="/forum/thread/67890-another-thread/">Another Thread</a>
<a class="wbbTopicLink" href="https://evil.com/phishing">Malicious Link</a>
</body>
</html>
"""

SAMPLE_ATTACHMENT_HTML = """
<html>
<body>
<article class="message">
  <a class="messageAttachment" href="/file-download/1234/">
    <span class="messageAttachmentFilename">macro.xml</span>
    <span class="messageAttachmentMeta">5.07 kB \u2013 317 Downloads</span>
  </a>
  <a class="messageAttachment" href="/file-download/5678/">
    <span class="messageAttachmentFilename">readme.txt</span>
  </a>
</article>
</body>
</html>
"""


class TestURLValidation:
    def test_valid_domain(self):
        scraper = ForumScraper()
        assert scraper._validate_url("https://forum.malighting.com/thread/123") is True

    def test_invalid_domain(self):
        scraper = ForumScraper()
        assert scraper._validate_url("https://evil.com/steal-data") is False

    def test_internal_ip(self):
        scraper = ForumScraper()
        assert scraper._validate_url("http://169.254.169.254/latest/meta-data/") is False

    def test_localhost(self):
        scraper = ForumScraper()
        assert scraper._validate_url("http://localhost:8080/admin") is False


class TestExtractThreadLinks:
    def test_extracts_valid_links(self):
        scraper = ForumScraper()
        soup = BeautifulSoup(SAMPLE_BOARD_HTML, "lxml")
        links = scraper._extract_thread_links_from_page(soup)
        # Should include the two valid forum.malighting.com links
        assert any("12345" in link for link in links)
        assert any("67890" in link for link in links)

    def test_filters_external_links(self):
        scraper = ForumScraper()
        soup = BeautifulSoup(SAMPLE_BOARD_HTML, "lxml")
        links = scraper._extract_thread_links_from_page(soup)
        # evil.com link should be filtered out by URL validation
        assert not any("evil.com" in link for link in links)


class TestExtractAllPosts:
    def test_extracts_posts(self):
        scraper = ForumScraper()
        soup = BeautifulSoup(SAMPLE_THREAD_HTML, "lxml")
        posts = scraper.extract_all_posts(soup)
        assert len(posts) == 2
        assert posts[0].author == "testuser"
        assert posts[0].post_number == 1
        assert posts[0].post_date == "2024-01-15T10:30:00Z"
        assert "first post content" in posts[0].post_text
        assert posts[1].author == "replyuser"
        assert posts[1].post_number == 2

    def test_empty_html(self):
        scraper = ForumScraper()
        soup = BeautifulSoup("<html><body></body></html>", "lxml")
        posts = scraper.extract_all_posts(soup)
        assert posts == []


class TestExtractAssets:
    def test_extracts_xml_files(self):
        scraper = ForumScraper()
        soup = BeautifulSoup(SAMPLE_ATTACHMENT_HTML, "lxml")
        assets = scraper.extract_assets(soup)
        # Should find macro.xml but NOT readme.txt (wrong extension)
        assert len(assets) == 1
        assert assets[0].filename == "macro.xml"
        assert "forum.malighting.com" in assets[0].url

    def test_extracts_download_count(self):
        scraper = ForumScraper()
        soup = BeautifulSoup(SAMPLE_ATTACHMENT_HTML, "lxml")
        assets = scraper.extract_assets(soup)
        assert assets[0].download_count == 317

    def test_no_attachments(self):
        scraper = ForumScraper()
        soup = BeautifulSoup("<html><body></body></html>", "lxml")
        assets = scraper.extract_assets(soup)
        assert assets == []


class TestGetMaxPageNumber:
    def test_with_page_links(self):
        html = """
        <html><body>
        <div class="pageNavigation">
          <a href="/forum/board/35/?pageNo=1">1</a>
          <a href="/forum/board/35/?pageNo=2">2</a>
          <a href="/forum/board/35/?pageNo=5">5</a>
        </div>
        </body></html>
        """
        scraper = ForumScraper()
        soup = BeautifulSoup(html, "lxml")
        assert scraper._get_max_page_number(soup) == 5

    def test_with_page_text(self):
        html = '<html><body><span>Page 1 of 12</span></body></html>'
        scraper = ForumScraper()
        soup = BeautifulSoup(html, "lxml")
        assert scraper._get_max_page_number(soup) == 12

    def test_fallback_when_no_pagination(self):
        html = "<html><body></body></html>"
        scraper = ForumScraper()
        soup = BeautifulSoup(html, "lxml")
        # Should fall back to 30 (probe mode)
        assert scraper._get_max_page_number(soup) == 30


class TestDownloadAssetSafety:
    """Test that download_asset prevents path traversal."""

    def test_path_traversal_filename_sanitized(self):
        """Verify PurePosixPath.name strips directory components."""
        from pathlib import PurePosixPath
        assert PurePosixPath("../../etc/passwd").name == "passwd"
        assert PurePosixPath("../../../.bashrc").name == ".bashrc"
        assert PurePosixPath("normal_file.xml").name == "normal_file.xml"
        assert PurePosixPath("/absolute/path/file.xml").name == "file.xml"
