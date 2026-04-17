from pathlib import Path

from daily_podcast.email_parser import (
    extract_html_from_eml_bytes,
    extract_ranked_papers_from_html,
    select_top_ids,
)


def test_extract_ranked_ids_from_example_eml() -> None:
    eml_path = Path(__file__).resolve().parents[1] / "EXAMPLE_IARXIV.eml"
    eml_bytes = eml_path.read_bytes()
    html = extract_html_from_eml_bytes(eml_bytes)
    papers = extract_ranked_papers_from_html(html)

    assert len(papers) == 34
    assert papers[0].rank == 1
    assert papers[0].arxiv_id == "2604.14282"
    assert papers[1].rank == 2
    assert papers[1].arxiv_id == "2604.14284"


def test_select_top_ten_by_rank() -> None:
    eml_path = Path(__file__).resolve().parents[1] / "EXAMPLE_IARXIV.eml"
    html = extract_html_from_eml_bytes(eml_path.read_bytes())
    papers = extract_ranked_papers_from_html(html)
    top_ten = select_top_ids(papers, top_n=10)

    assert len(top_ten) == 10
    assert top_ten[0] == "2604.14282"
    assert top_ten[-1] == "2604.14688"
