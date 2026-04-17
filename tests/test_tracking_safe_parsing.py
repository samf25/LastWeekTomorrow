from daily_podcast.email_parser import extract_ranked_papers_from_html


def test_parser_uses_visible_ranked_row_text_even_if_href_changes() -> None:
    html = """
    <span>[1] <a href="https://iarxiv.org/paper/opaque-token">2604.14282</a> (hep-ph) [score: 0.72]</span>
    <span>[2] <a href="https://example.invalid/whatever">2604.14284</a> (hep-ph) [score: 0.61]</span>
    """
    papers = extract_ranked_papers_from_html(html)
    assert [p.arxiv_id for p in papers] == ["2604.14282", "2604.14284"]
