"""Tests for FitFindr tools."""

from unittest.mock import MagicMock, patch

from tools import search_listings, suggest_outfit, create_fit_card


# ── search_listings tests ────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter():
    results = search_listings("vintage tee", size="M")
    for item in results:
        assert "m" in item["size"].lower()


def test_search_no_zero_score():
    results = search_listings("leather boots")
    for item in results:
        searchable = " ".join([
            item["title"],
            item["description"],
            item["category"],
            " ".join(item.get("style_tags", [])),
            " ".join(item.get("colors", [])),
            item.get("brand") or "",
        ]).lower()
        keywords = ["leather", "boots"]
        assert any(kw in searchable for kw in keywords)


# ── suggest_outfit tests (mocked LLM) ────────────────────────────────────────

def _mock_groq_client(response_text="Mocked outfit suggestion"):
    mock_client = MagicMock()
    mock_message = MagicMock()
    mock_message.content = response_text
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


SAMPLE_ITEM = {
    "id": "lst_006",
    "title": "Graphic Tee — 2003 Tour Bootleg Style",
    "description": "Vintage-style bootleg tee with faded graphic.",
    "category": "tops",
    "style_tags": ["graphic tee", "vintage", "grunge"],
    "size": "L",
    "condition": "good",
    "price": 24.00,
    "colors": ["black"],
    "brand": None,
    "platform": "depop",
}

EXAMPLE_WARDROBE = {
    "items": [
        {
            "id": "w_001",
            "name": "Baggy straight-leg jeans, dark wash",
            "category": "bottoms",
            "colors": ["dark blue", "indigo"],
            "style_tags": ["denim", "streetwear", "baggy"],
        },
        {
            "id": "w_007",
            "name": "Chunky white sneakers",
            "category": "shoes",
            "colors": ["white"],
            "style_tags": ["sneakers", "chunky", "streetwear"],
        },
    ]
}

EMPTY_WARDROBE = {"items": []}


@patch("tools._get_groq_client")
def test_suggest_outfit_empty_wardrobe(mock_get_client):
    mock_get_client.return_value = _mock_groq_client("General styling advice here")
    result = suggest_outfit(SAMPLE_ITEM, EMPTY_WARDROBE)
    assert isinstance(result, str)
    assert len(result) > 0


@patch("tools._get_groq_client")
def test_suggest_outfit_with_wardrobe(mock_get_client):
    mock_get_client.return_value = _mock_groq_client("Pair the tee with baggy jeans and chunky sneakers")
    result = suggest_outfit(SAMPLE_ITEM, EXAMPLE_WARDROBE)
    assert isinstance(result, str)
    assert len(result) > 0


@patch("tools._get_groq_client")
def test_suggest_outfit_returns_string(mock_get_client):
    mock_get_client.return_value = _mock_groq_client()
    result = suggest_outfit(SAMPLE_ITEM, EXAMPLE_WARDROBE)
    assert isinstance(result, str)


# ── create_fit_card tests (mocked LLM) ───────────────────────────────────────

def test_fit_card_empty_outfit():
    result = create_fit_card("", SAMPLE_ITEM)
    assert isinstance(result, str)
    assert "error" in result.lower()


def test_fit_card_whitespace_outfit():
    result = create_fit_card("   \n\t  ", SAMPLE_ITEM)
    assert isinstance(result, str)
    assert "error" in result.lower()


@patch("tools._get_groq_client")
def test_fit_card_returns_string(mock_get_client):
    mock_get_client.return_value = _mock_groq_client("Just thrifted this sick tee for $24 on depop.")
    result = create_fit_card("Graphic tee with baggy jeans and chunky sneakers", SAMPLE_ITEM)
    assert isinstance(result, str)
    assert len(result) > 0
