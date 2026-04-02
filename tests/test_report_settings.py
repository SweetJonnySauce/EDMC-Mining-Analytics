from edmc_mining_analytics.report_settings import (
    DEFAULT_COMPARE_SETTINGS,
    DEFAULT_INDEX_SETTINGS,
    sanitize_compare_report_settings,
    sanitize_index_report_settings,
)


def test_sanitize_index_report_settings_defaults_to_all_mode() -> None:
    settings = sanitize_index_report_settings({})
    assert settings["selectedYieldPopulationMode"] == "all"


def test_sanitize_index_report_settings_accepts_present_mode() -> None:
    settings = sanitize_index_report_settings({"selectedYieldPopulationMode": "present"})
    assert settings["selectedYieldPopulationMode"] == "present"


def test_sanitize_index_report_settings_rejects_invalid_mode() -> None:
    settings = sanitize_index_report_settings({"selectedYieldPopulationMode": "invalid"})
    assert settings["selectedYieldPopulationMode"] == DEFAULT_INDEX_SETTINGS["selectedYieldPopulationMode"]


def test_sanitize_compare_report_settings_defaults_theme() -> None:
    settings = sanitize_compare_report_settings({})
    assert settings["compareThemeId"] == DEFAULT_COMPARE_SETTINGS["compareThemeId"]


def test_sanitize_compare_report_settings_accepts_valid_theme() -> None:
    settings = sanitize_compare_report_settings({"compareThemeId": "blue-dark"})
    assert settings["compareThemeId"] == "blue-dark"


def test_sanitize_compare_report_settings_rejects_invalid_theme() -> None:
    settings = sanitize_compare_report_settings({"compareThemeId": "invalid-theme"})
    assert settings["compareThemeId"] == DEFAULT_COMPARE_SETTINGS["compareThemeId"]
