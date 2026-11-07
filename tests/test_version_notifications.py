"""Data-only version mailbox contracts."""

from threading import Event, Thread

from edmc_mining_analytics.version_notifications import (
    LatestVersion,
    UpdateReady,
    VersionMailbox,
)


def test_publish_and_drain_preserves_message_order():
    mailbox = VersionMailbox()
    messages = [LatestVersion("v2.0.0"), UpdateReady("2.0.0"), LatestVersion("3.0.0")]
    for message in messages:
        assert mailbox.publish(message) is True
    assert mailbox.drain() == messages
    assert mailbox.drain() == []


def test_close_discards_pending_and_rejects_late_publication():
    mailbox = VersionMailbox()
    assert mailbox.publish(LatestVersion("2.0.0"))
    mailbox.close()
    mailbox.close()
    assert mailbox.drain() == []
    assert mailbox.publish(UpdateReady("2.0.0")) is False
    assert mailbox.drain() == []


def test_real_publisher_thread_retains_results_until_draining():
    mailbox = VersionMailbox()
    published = Event()
    release = Event()
    outcomes = []

    def publish():
        outcomes.append(mailbox.publish(LatestVersion("2.0.0")))
        published.set()
        assert release.wait(2)
        outcomes.append(mailbox.publish(UpdateReady("2.0.0")))

    thread = Thread(target=publish)
    thread.start()
    try:
        assert published.wait(2)
        assert mailbox.drain() == [LatestVersion("2.0.0")]
        mailbox.close()
    finally:
        release.set()
        thread.join(2)
    assert not thread.is_alive()
    assert outcomes == [True, False]
    assert mailbox.drain() == []


def test_multiple_publishers_preserve_order_across_closure():
    mailbox = VersionMailbox()
    first_published = Event()
    second_published = Event()
    closed = Event()
    outcomes = []

    def first_publisher():
        outcomes.append(mailbox.publish(LatestVersion("2.0.0")))
        first_published.set()
        assert closed.wait(2)
        outcomes.append(mailbox.publish(LatestVersion("4.0.0")))

    def second_publisher():
        assert first_published.wait(2)
        outcomes.append(mailbox.publish(UpdateReady("2.0.0")))
        second_published.set()
        assert closed.wait(2)
        outcomes.append(mailbox.publish(UpdateReady("4.0.0")))

    threads = [Thread(target=first_publisher), Thread(target=second_publisher)]
    for thread in threads:
        thread.start()
    try:
        assert second_published.wait(2)
        assert mailbox.drain() == [LatestVersion("2.0.0"), UpdateReady("2.0.0")]
        assert mailbox.publish(LatestVersion("3.0.0"))
        mailbox.close()
    finally:
        closed.set()
        for thread in threads:
            thread.join(2)
    assert all(not thread.is_alive() for thread in threads)
    assert outcomes == [True, True, False, False]
    assert mailbox.drain() == []
