from edmc_mining_analytics.capabilities.providers.browser_common import BrowserWindowInfo, select_browser_window_id


def test_select_browser_window_prefers_matching_title_hint() -> None:
    windows = [
        BrowserWindowInfo(window_id="0x001", window_class="firefox.firefox", title="Mail - Mozilla Firefox"),
        BrowserWindowInfo(
            window_id="0x002",
            window_class="firefox.firefox",
            title="EDMC Mining Analytics Web Page - Mozilla Firefox",
        ),
    ]

    selected = select_browser_window_id(
        windows,
        target_url="http://127.0.0.1:8765/web/index.html",
        title_hints=("EDMC Mining Analytics Web Page",),
        preexisting_window_titles={
            "0x001": "Mail - Mozilla Firefox",
            "0x002": "Docs - Mozilla Firefox",
        },
    )

    assert selected == "0x002"


def test_select_browser_window_prefers_new_window_when_titles_do_not_match() -> None:
    windows = [
        BrowserWindowInfo(window_id="0x010", window_class="google-chrome.google-chrome", title="Docs - Chrome"),
        BrowserWindowInfo(window_id="0x011", window_class="google-chrome.google-chrome", title="New Tab - Chrome"),
    ]

    selected = select_browser_window_id(
        windows,
        target_url="http://127.0.0.1:8765/web/index.html",
        title_hints=("unrelated hint",),
        preexisting_window_titles={"0x010": "Docs - Chrome"},
    )

    assert selected == "0x011"


def test_select_browser_window_avoids_stale_matching_window() -> None:
    windows = [
        BrowserWindowInfo(
            window_id="0x021",
            window_class="firefox.firefox",
            title="EDMC Mining Analytics Web Page - Mozilla Firefox",
        ),
        BrowserWindowInfo(
            window_id="0x022",
            window_class="firefox.firefox",
            title="EDMC Mining Analytics Web Page - Mozilla Firefox",
        ),
    ]

    selected = select_browser_window_id(
        windows,
        target_url="http://127.0.0.1:8765/web/index.html",
        title_hints=("EDMC Mining Analytics Web Page",),
        preexisting_window_titles={
            "0x021": "EDMC Mining Analytics Web Page - Mozilla Firefox",
            "0x022": "New Tab - Mozilla Firefox",
        },
    )

    # Prefer the window that changed into the analysis title, not the stale one.
    assert selected == "0x022"
