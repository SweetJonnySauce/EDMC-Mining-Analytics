"""Exercise real version producers through EDMC hooks without a display/network."""

from contextlib import contextmanager
from dataclasses import dataclass
import logging
from threading import Event, Thread, get_ident
from types import SimpleNamespace

import pytest
import requests

from tests.harness_test_utils import DummyUI, harness_context


class RecordingRoot:
    def __init__(self, ui):
        self.ui = ui
        self.pending = {}
        self.history = {}
        self.serial = 0

    def after(self, delay, callback):
        self.ui.check_thread("after")
        self.serial += 1
        token = f"after-{self.serial}"
        self.pending[token] = callback
        self.history[token] = callback
        assert delay == 100
        return token

    def after_cancel(self, token):
        self.ui.check_thread("after_cancel")
        self.pending.pop(token, None)

    def winfo_exists(self):
        self.ui.check_thread("winfo_exists")
        return True

    def event_generate(self, *args, **kwargs):
        self.ui.check_thread("event_generate")

    def tick(self):
        self.ui.check_thread("tick")
        assert len(self.pending) == 1
        token, callback = next(iter(self.pending.items()))
        del self.pending[token]
        callback()


class RecordingUI(DummyUI):
    def __init__(self):
        self.main_thread = get_ident()
        self.violations = []
        self.operations = []
        self.labels = []
        self.attached = False
        self.root = RecordingRoot(self)

    def check_thread(self, operation):
        self.operations.append((operation, get_ident()))
        if get_ident() != self.main_thread:
            self.violations.append(operation)
            raise AssertionError(f"worker called Tk/UI operation: {operation}")

    def build(self, parent):
        self.check_thread("build")
        self.attached = True
        return parent

    def get_root(self):
        self.check_thread("get_root")
        return self.root if self.attached else None

    def update_version_label(self, *args):
        self.check_thread("update_version_label")
        self.labels.append(args)


@dataclass
class FakeResponse:
    payload: object
    status_code: int = 200

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)

    def json(self):
        return self.payload


class FakeHTTP:
    def __init__(self, version="v99.0.0", fallback=False):
        self.version = version
        self.fallback = fallback
        self.entered = Event()
        self.release = Event()
        self.calls = []

    def get(self, url, *, timeout):
        self.calls.append((url, timeout, get_ident()))
        self.entered.set()
        assert self.release.wait(2), "test did not release fake HTTP"
        if "/tags?" in url:
            return FakeResponse([{"ref": f"refs/tags/{self.version}"}])
        return FakeResponse({"tag_name": self.version}, 404 if self.fallback else 200)


class CapturedUpdateManager:
    def __init__(self, plugin_dir, *, on_update_ready):
        self.callback = on_update_ready

    def start(self):
        pass

    def stop(self):
        pass


def run_worker(callback, *args):
    errors = []

    def run():
        try:
            callback(*args)
        except Exception as exc:
            errors.append(exc)

    thread = Thread(target=run)
    thread.start()
    thread.join(2)
    assert not thread.is_alive()
    assert errors == []


@contextmanager
def version_context(monkeypatch, tmp_path, *, version="v99.0.0", fallback=False):
    with harness_context(start_plugin=False) as (_harness, load, _cfg):
        import edmc_mining_analytics.plugin as plugin_module

        plugin = load._plugin
        ui = RecordingUI()
        http = FakeHTTP(version, fallback)
        errors = []
        monkeypatch.setattr(plugin, "ui", ui)
        monkeypatch.setattr(plugin, "_ensure_version_check", plugin_module.MiningAnalyticsPlugin._ensure_version_check.__get__(plugin))
        monkeypatch.setattr(plugin_module, "UpdateManager", CapturedUpdateManager)
        monkeypatch.setattr(plugin_module, "get_shared_session", lambda: http)
        monkeypatch.setattr("threading.excepthook", lambda args: errors.append(args.exc_value))
        load.plugin_start3(str(tmp_path))
        assert http.entered.wait(2)
        thread = plugin._version_thread
        try:
            yield SimpleNamespace(load=load, plugin=plugin, ui=ui, http=http, thread=thread, errors=errors, module=plugin_module)
        finally:
            http.release.set()
            thread.join(2)
            assert not thread.is_alive()


def finish_version(context):
    context.http.release.set()
    context.thread.join(2)
    assert not context.thread.is_alive()
    assert context.ui.violations == [], f"worker reached Tk/UI: {context.ui.violations}"
    assert context.errors == []


@pytest.mark.parametrize("fallback", [False, True], ids=["release", "tag-fallback"])
def test_real_version_worker_never_calls_tk(monkeypatch, tmp_path, fallback):
    with version_context(monkeypatch, tmp_path, fallback=fallback) as context:
        context.load.plugin_app(object())
        before = list(context.ui.labels)
        finish_version(context)
        assert context.plugin._latest_version is None
        assert context.ui.labels == before
        context.ui.root.tick()
        assert context.plugin._latest_version == "99.0.0"
        assert context.ui.labels[-1] == (context.module.PLUGIN_VERSION, "99.0.0", False)
        assert [call[0] for call in context.http.calls] == [
            context.module.GITHUB_RELEASES_API,
            *([context.module.GITHUB_TAGS_API] if fallback else []),
        ]
        assert all(call[1] == 5 and call[2] != context.ui.main_thread for call in context.http.calls)


def test_actual_update_ready_callback_never_calls_tk(monkeypatch, tmp_path):
    with version_context(monkeypatch, tmp_path) as context:
        context.load.plugin_app(object())
        before = list(context.ui.labels)
        run_worker(context.plugin.update_manager.callback, "v99.0.0")
        assert context.plugin._latest_version is None
        assert context.plugin._update_ready_version is None
        assert context.ui.labels == before
        context.ui.root.tick()
        assert context.ui.labels[-1] == (context.module.PLUGIN_VERSION, "99.0.0", True)


def test_result_before_app_is_retained(monkeypatch, tmp_path):
    with version_context(monkeypatch, tmp_path) as context:
        finish_version(context)
        assert context.plugin._latest_version is None
        assert context.ui.labels == []
        assert context.ui.operations == []
        context.load.plugin_app(object())
        assert context.ui.labels[-1] == (context.module.PLUGIN_VERSION, "99.0.0", False)
        assert len(context.ui.root.pending) == 1


@pytest.mark.parametrize("version,expected", [("v0.0.0", "0.0.0"), (None, None), ("v99.0.0", "99.0.0")])
def test_older_equal_newer_versions(monkeypatch, tmp_path, version, expected):
    with version_context(monkeypatch, tmp_path) as context:
        context.http.version = version or context.module.PLUGIN_VERSION
        expected = expected or context.module.PLUGIN_VERSION
        finish_version(context)
        context.load.plugin_app(object())
        assert context.ui.labels[-1] == (context.module.PLUGIN_VERSION, expected, False)


@pytest.mark.parametrize("ready_first", [False, True])
@pytest.mark.parametrize("ready_version,expected_latest,ready", [
    ("v99.0.0", "99.0.0", True),
    ("v100.0.0", "100.0.0", True),
    ("v98.0.0", "99.0.0", True),
])
def test_arrival_order_preserves_existing_merge_rules(monkeypatch, tmp_path, ready_first, ready_version, expected_latest, ready):
    with version_context(monkeypatch, tmp_path) as context:
        if ready_first:
            run_worker(context.plugin.update_manager.callback, ready_version)
            finish_version(context)
            expected_latest, ready = "99.0.0", ready_version == "v99.0.0"
        else:
            finish_version(context)
            run_worker(context.plugin.update_manager.callback, ready_version)
        context.load.plugin_app(object())
        assert context.ui.labels[-1] == (context.module.PLUGIN_VERSION, expected_latest, ready)


def test_duplicate_attachment_and_basic_stop(monkeypatch, tmp_path):
    with version_context(monkeypatch, tmp_path) as context:
        finish_version(context)
        context.load.plugin_app(object())
        context.load.plugin_app(object())
        assert len(context.ui.root.pending) == 1
        context.load.plugin_stop()
        assert context.ui.root.pending == {}
        labels = list(context.ui.labels)
        run_worker(context.plugin.update_manager.callback, "100.0.0")
        assert context.ui.labels == labels
        context.load.plugin_stop()


def test_stop_before_app_discards_pending_and_late_results(monkeypatch, tmp_path):
    from edmc_mining_analytics.version_notifications import LatestVersion

    with version_context(monkeypatch, tmp_path) as context:
        finish_version(context)
        callback = context.plugin.update_manager.callback
        run_worker(callback, "v100.0.0")
        mailbox = context.plugin._version_mailbox
        context.load.plugin_stop()
        context.load.plugin_stop()
        assert context.plugin._version_mailbox is None
        assert mailbox.drain() == []
        assert mailbox.publish(LatestVersion("101.0.0")) is False
        run_worker(callback, "v102.0.0")
        assert mailbox.drain() == []
        assert context.plugin._latest_version is None
        assert context.plugin._update_ready_version is None
        assert context.ui.operations == []
        assert context.ui.root.pending == {}


def test_stop_closes_and_cancels_before_worker_waits(monkeypatch, tmp_path):
    from edmc_mining_analytics.version_notifications import LatestVersion

    with version_context(monkeypatch, tmp_path) as context:
        context.load.plugin_app(object())
        mailbox = context.plugin._version_mailbox
        callback = context.plugin.update_manager.callback
        stale_timer = next(iter(context.ui.root.history.values()))
        before = list(context.ui.labels)
        waits = []

        def check_closed():
            assert context.plugin._is_stopping
            assert context.plugin._version_mailbox is None
            assert context.plugin._version_poll_job is None
            assert context.plugin._version_poll_root is None
            assert context.ui.root.pending == {}
            assert mailbox.publish(LatestVersion("101.0.0")) is False

        def stop_updater():
            check_closed()
            waits.append("updater")
            run_worker(callback, "v100.0.0")
            # The real version worker completes inside stop's wait phase.
            finish_version(context)
            stale_timer()

        original_wait = context.plugin._wait_for_version_thread

        def wait_version():
            check_closed()
            waits.append("version")
            original_wait(timeout=0)

        monkeypatch.setattr(context.plugin.update_manager, "stop", stop_updater)
        monkeypatch.setattr(context.plugin, "_wait_for_version_thread", wait_version)
        context.load.plugin_stop()
        assert waits == ["updater", "version"]
        assert mailbox.drain() == []
        assert context.plugin._latest_version is None
        assert context.plugin._update_ready_version is None
        assert context.ui.labels == before
        # Also invoke retained callbacks after stop has fully returned.
        run_worker(callback, "v102.0.0")
        stale_timer()
        assert context.ui.labels == before
        assert context.ui.root.pending == {}


def test_timed_out_old_worker_and_callbacks_cannot_affect_restart(monkeypatch, tmp_path):
    with version_context(monkeypatch, tmp_path) as context:
        context.load.plugin_app(object())
        old_mailbox = context.plugin._version_mailbox
        old_callback = context.plugin.update_manager.callback
        old_timer = next(iter(context.ui.root.history.values()))
        original_wait = context.plugin._wait_for_version_thread
        monkeypatch.setattr(context.plugin, "_wait_for_version_thread", lambda: original_wait(timeout=0))
        context.load.plugin_stop()
        assert context.thread.is_alive(), "old worker must survive the bounded stop join"
        assert context.plugin._version_thread is context.thread

        current_http = FakeHTTP("v101.0.0")
        current_thread = None
        monkeypatch.setattr(context.module, "get_shared_session", lambda: current_http)
        try:
            context.load.plugin_start3(str(tmp_path))
            assert current_http.entered.wait(2)
            current_thread = context.plugin._version_thread
            assert current_thread is not context.thread
            assert current_thread.is_alive()
            assert context.plugin._version_mailbox is not old_mailbox
            context.load.plugin_app(object())
            owned_job = context.plugin._version_poll_job
            owned_root = context.plugin._version_poll_root
            before = list(context.ui.labels)
            finish_version(context)
            run_worker(old_callback, "v102.0.0")
            old_timer()
            assert context.plugin._version_thread is current_thread
            assert current_thread.is_alive()
            assert context.plugin._version_poll_job == owned_job
            assert context.plugin._version_poll_root is owned_root
            assert list(context.ui.root.pending) == [owned_job]
            assert old_mailbox.drain() == []
            assert context.plugin._latest_version is None
            assert context.plugin._update_ready_version is None
            assert context.ui.labels == before
            context.ui.root.tick()
            assert context.ui.labels == before

            current_http.release.set()
            current_thread.join(2)
            assert not current_thread.is_alive()
            context.ui.root.tick()
            assert context.ui.labels[-1] == (context.module.PLUGIN_VERSION, "101.0.0", False)
            run_worker(context.plugin.update_manager.callback, "v101.0.0")
            context.ui.root.tick()
            assert context.ui.labels[-1] == (context.module.PLUGIN_VERSION, "101.0.0", True)
            assert context.ui.violations == []
            assert context.errors == []
        finally:
            current_http.release.set()
            if current_thread is not None:
                current_thread.join(2)
                assert not current_thread.is_alive()


def test_duplicate_attachment_cancels_on_original_scheduling_root(monkeypatch, tmp_path):
    with version_context(monkeypatch, tmp_path) as context:
        finish_version(context)
        context.load.plugin_app(object())
        original_root = context.ui.root
        owned_job = context.plugin._version_poll_job
        replacement_root = RecordingRoot(context.ui)
        context.ui.root = replacement_root
        context.load.plugin_app(object())
        assert list(original_root.pending) == [owned_job]
        assert replacement_root.pending == {}
        assert context.plugin._version_poll_root is original_root
        context.load.plugin_stop()
        assert original_root.pending == {}
        assert replacement_root.pending == {}
        assert context.plugin._version_poll_job is None
        context.plugin._stop_version_notifications()


def test_unexpected_consumer_error_logs_traceback_and_continues(monkeypatch, tmp_path, caplog):
    with version_context(monkeypatch, tmp_path) as context:
        finish_version(context)
        callback = context.plugin.update_manager.callback
        run_worker(callback, "v99.0.0")
        run_worker(callback, "v100.0.0")
        ready_versions = []
        original_ready = context.plugin._handle_update_ready

        def fail_latest(version):
            raise ValueError("intentional consumer probe")

        def handle_ready(version):
            ready_versions.append(version)
            original_ready(version)

        monkeypatch.setattr(context.plugin, "_handle_latest_version", fail_latest)
        monkeypatch.setattr(context.plugin, "_handle_update_ready", handle_ready)
        with caplog.at_level(logging.ERROR, logger=context.module._log.name):
            context.load.plugin_app(object())
        errors = [record for record in caplog.records if record.message == "Failed to deliver version notification"]
        assert len(errors) == 1
        assert errors[0].exc_info[0] is ValueError
        assert str(errors[0].exc_info[1]) == "intentional consumer probe"
        assert ready_versions == ["v99.0.0", "v100.0.0"]
        assert context.ui.labels[-1] == (context.module.PLUGIN_VERSION, "100.0.0", True)
        assert len(context.ui.root.pending) == 1


def test_publisher_can_complete_during_application_callback(monkeypatch, tmp_path):
    with version_context(monkeypatch, tmp_path) as context:
        context.load.plugin_app(object())
        finish_version(context)
        handler_entered = Event()
        published = Event()
        errors = []
        callback = context.plugin.update_manager.callback
        original_latest = context.plugin._handle_latest_version

        def publish_during_handler():
            try:
                assert handler_entered.wait(2)
                callback("v100.0.0")
            except Exception as exc:
                errors.append(exc)
            finally:
                published.set()

        def handle_latest(version):
            handler_entered.set()
            assert published.wait(2), "application callback held the mailbox lock"
            assert errors == []
            original_latest(version)

        monkeypatch.setattr(context.plugin, "_handle_latest_version", handle_latest)
        publisher = Thread(target=publish_during_handler)
        publisher.start()
        try:
            context.ui.root.tick()
            assert context.ui.labels[-1] == (context.module.PLUGIN_VERSION, "99.0.0", False)
            context.ui.root.tick()
            assert context.ui.labels[-1] == (context.module.PLUGIN_VERSION, "100.0.0", True)
        finally:
            handler_entered.set()
            publisher.join(2)
        assert not publisher.is_alive()
        assert errors == []
        assert context.ui.violations == []


def test_destroyed_root_during_timer_creation_leaves_no_ownership(monkeypatch, tmp_path):
    with version_context(monkeypatch, tmp_path) as context:
        finish_version(context)

        def destroyed_after(delay, callback):
            context.ui.check_thread("after")
            raise context.module.tk.TclError("root destroyed")

        monkeypatch.setattr(context.ui.root, "after", destroyed_after)
        context.load.plugin_app(object())
        assert context.plugin._version_poll_job is None
        assert context.plugin._version_poll_root is None
        assert context.ui.root.pending == {}


def test_destroyed_root_during_cancellation_clears_ownership(monkeypatch, tmp_path):
    with version_context(monkeypatch, tmp_path) as context:
        finish_version(context)
        context.load.plugin_app(object())
        cancelled = []
        owned_job = context.plugin._version_poll_job

        def destroyed_cancel(token):
            context.ui.check_thread("after_cancel")
            cancelled.append(token)
            context.ui.root.pending.pop(token, None)
            raise context.module.tk.TclError("root destroyed")

        monkeypatch.setattr(context.ui.root, "after_cancel", destroyed_cancel)
        context.load.plugin_stop()
        context.load.plugin_stop()
        assert cancelled == [owned_job]
        assert context.plugin._version_poll_job is None
        assert context.plugin._version_poll_root is None
        assert context.ui.root.pending == {}


def test_destroyed_label_does_not_discard_remaining_notifications(monkeypatch, tmp_path):
    with version_context(monkeypatch, tmp_path) as context:
        context.load.plugin_app(object())
        finish_version(context)
        run_worker(context.plugin.update_manager.callback, "v100.0.0")
        original_render = context.ui.update_version_label
        attempts = []

        def render(*args):
            context.ui.check_thread("update_version_label")
            attempts.append(args)
            if len(attempts) == 1:
                raise context.module.tk.TclError("label destroyed")
            original_render(*args)

        monkeypatch.setattr(context.ui, "update_version_label", render)
        context.ui.root.tick()
        assert len(attempts) == 2
        assert context.ui.labels[-1] == (context.module.PLUGIN_VERSION, "100.0.0", True)
        assert len(context.ui.root.pending) == 1


def test_unexpected_timer_error_is_not_hidden_as_tk_destruction(monkeypatch, tmp_path):
    with version_context(monkeypatch, tmp_path) as context:
        finish_version(context)

        def unexpected_after(delay, callback):
            context.ui.check_thread("after")
            raise RuntimeError("unexpected scheduler failure")

        monkeypatch.setattr(context.ui.root, "after", unexpected_after)
        with pytest.raises(RuntimeError, match="unexpected scheduler failure"):
            context.load.plugin_app(object())
        assert context.plugin._version_poll_job is None
        assert context.plugin._version_poll_root is None
