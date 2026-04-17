import pytest

from daily_podcast.downloader import ensure_allowed_download_url, make_pdf_url


def test_pdf_url_builder_uses_arxiv_pdf_pattern() -> None:
    url = make_pdf_url("2604.14282", "https://arxiv.org/pdf")
    assert url == "https://arxiv.org/pdf/2604.14282.pdf"
    assert "iarxiv.org" not in url


def test_rejects_non_arxiv_hosts() -> None:
    with pytest.raises(ValueError):
        ensure_allowed_download_url("https://iarxiv.org/paper/anything")


def test_rejects_non_https() -> None:
    with pytest.raises(ValueError):
        ensure_allowed_download_url("http://arxiv.org/pdf/2604.14282.pdf")
