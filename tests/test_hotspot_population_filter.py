from edmc_mining_analytics.mining_ui.hotspot_search_window import HotspotSearchWindow


def test_format_population_uses_grouped_numbers_and_blank_unknown() -> None:
    assert HotspotSearchWindow._format_population(None) == ""
    assert HotspotSearchWindow._format_population(0) == "0"
    assert HotspotSearchWindow._format_population(1234567) == "1,234,567"


def test_population_warning_shows_only_when_changing_from_any_to_filter() -> None:
    assert HotspotSearchWindow._should_show_population_warning("any", "none", False) is True
    assert HotspotSearchWindow._should_show_population_warning("Any", "Below 10,000", False) is True
    assert HotspotSearchWindow._should_show_population_warning("none", "below_10000", False) is False
    assert HotspotSearchWindow._should_show_population_warning("any", "any", False) is False
    assert HotspotSearchWindow._should_show_population_warning("any", "none", True) is False
