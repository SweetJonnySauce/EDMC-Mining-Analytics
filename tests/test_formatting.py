from edmc_mining_analytics.formatting import format_compact_number


def test_format_compact_number_basic() -> None:
    assert format_compact_number(None) == "--"
    assert format_compact_number(0) == "0"
    assert format_compact_number(999) == "999"
    assert format_compact_number(1000) == "1K"
    assert format_compact_number(1500) == "1.5K"
    assert format_compact_number(100_000) == "100K"
    assert format_compact_number(1_000_000) == "1M"
    assert format_compact_number(4_300_000) == "4.3M"
    assert format_compact_number(1_200_000_000) == "1.2B"
    assert format_compact_number(-1250) == "-1.2K"
