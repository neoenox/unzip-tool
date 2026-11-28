"""Owned worker processes. Only the parent may publish an extraction result."""
from __future__ import annotations

import multiprocessing as mp
import os
import queue
import subprocess
import tempfile
import threading
import time
from types import SimpleNamespace
from pathlib import Path

from unzipper import (
    PasswordRequiredError, _extract_into, archive_needs_password,
    clean_staging, error_message, list_contents, publish_staging,
)

TERMINAL_EVENTS = frozenset({'done', 'error', 'password'})
UNEXPECTED_EXIT_MESSAGE = '処理が予期せず終了しました。もう一度お試しください。'


def _make_staging(dest) -> Path:
    """保存先と同じ場所に、公開前の書き込み先を作る。"""
    parent = Path(dest).absolute().parent
    parent.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix='.kantan-', dir=parent))


class _OwnedTask:
    """停止待ちと後始末の共通部分。結果の公開 (rename) は親 (poll) だけが行う。"""

    def __init__(self, operation, dest):
        self.operation = operation
        self.dest = dest
        self.staging = None
        self.finished = False
        self._stopped = threading.Event()
        self._stopped.set()  # 停止処理は走っていない
        if operation == 'extract':
            self.staging = _make_staging(dest)
            self._stopped.clear()  # 公開か後始末が終わるまで待たせる

    def _clean_staging(self):
        if self.staging is None:
            return
        try:
            clean_staging(self.staging)
        except OSError:
            pass  # 公開済みの結果をクリーンアップ失敗で壊さない

    def wait_stopped(self, timeout=None) -> bool:
        """停止処理と後始末が終わるまで待つ (UI スレッドでは短い timeout で)。"""
        return self._stopped.wait(timeout)


class ThreadTask(_OwnedTask):
    """子プロセスを作れない環境向けの BackgroundTask 互換ワーカー。

    解凍も BackgroundTask と同じ手順を守る: スレッドは一時フォルダへ書き、
    保存先への公開 (rename) は poll() を呼ぶ親 (UI) だけが行う。
    """

    def __init__(self, operation, archive, password=None, dest=None):
        super().__init__(operation, dest)
        self._cancelled = threading.Event()
        self._events = queue.Queue()
        connection = SimpleNamespace(send=self._events.put, close=lambda: None)
        self._thread = threading.Thread(
            target=self._run,
            args=(connection, operation, archive, password, self.staging),
            daemon=True,
        )
        self._thread.start()

    def _run(self, connection, *args):
        try:
            _work(connection, *args)
        finally:
            self.finished = True
            if self._cancelled.is_set():
                # 書き込みが止まった後で片付ける (書き込み中に消さない)。
                self._clean_staging()
                self._stopped.set()

    def poll(self):
        if self._cancelled.is_set():
            return []
        events = []
        while len(events) < 100:
            try:
                kind, payload = self._events.get_nowait()
            except queue.Empty:
                break
            if kind in TERMINAL_EVENTS:
                events.append(_publish(self, kind, payload))
                self.finished = True
                self._clean_staging()
                self._stopped.set()
                return events
            events.append((kind, payload))
        return events

    def cancel(self):
        self._cancelled.set()
        if self.finished:
            # 終了直後で、まだ poll されていない未公開の結果を片付ける。
            self._clean_staging()
            self._stopped.set()
            return
        self.finished = True
        # スレッドは強制終了できない。終了後の片付けは _run が行うため、ここでは待たない。


def _publish(task, kind, payload):
    """結果の公開 (rename) は親だけが行う。ワーカーの done を結果パスに変える。"""
    if kind != 'done' or task.operation != 'extract':
        return kind, payload
    try:
        return kind, str(publish_staging(task.staging, task.dest))
    except Exception as error:
        return 'error', error_message(error)


def _work(connection, operation, archive, password, staging):
    try:
        if operation == 'update':
            from updates import check_latest
            connection.send(('done', check_latest()))
        elif operation == 'download':
            from updates import download_update
            connection.send(('done', download_update(
                archive, on_progress=lambda done, total: connection.send(('bytes', (done, total))))))
        elif operation == 'list':
            entries = list_contents(archive, password)
            connection.send(('done', (entries, archive_needs_password(archive))))
        else:
            last_sent = 0
            def byte_progress(done, total):
                nonlocal last_sent
                now = time.monotonic()
                if now - last_sent >= .1 or done == total:
                    connection.send(('bytes', (done, total)))
                    last_sent = now
            _extract_into(
                archive, Path(staging),
                on_progress=lambda done, total: connection.send(('progress', (done, total))),
                password=password,
                on_file=lambda name: connection.send(('file', name)),
                on_bytes=byte_progress,
            )
            connection.send(('done', None))
    except PasswordRequiredError as error:
        connection.send(('password', str(error)))
    except Exception as error:
        connection.send(('error', error_message(error)))
    finally:
        connection.close()


class BackgroundTask(_OwnedTask):
    def __init__(self, operation, archive, password=None, dest=None):
        super().__init__(operation, dest)
        context = mp.get_context('spawn')
        self.connection, child = context.Pipe(duplex=False)
        self.process = context.Process(
            target=_work, args=(child, operation,
                                archive if operation == 'download' else str(archive),
                                password, self.staging),
            daemon=True,
        )
        try:
            self.process.start()
        except Exception:
            self.connection.close()
            self._clean_staging()
            raise
        finally:
            child.close()

    def poll(self):
        if self.finished:
            return []
        events = []
        if not self.process.is_alive() and not self.connection.poll():
            self.finished = True
            self.connection.close()
            self._clean_staging()
            self._stopped.set()
            return [('error', UNEXPECTED_EXIT_MESSAGE)]
        # Bound work per Tk tick so huge archives cannot starve the GUI.
        for _ in range(100):
            if not self.connection.poll():
                break
            try:
                kind, payload = self.connection.recv()
            except (EOFError, OSError):
                kind, payload = 'error', UNEXPECTED_EXIT_MESSAGE
            if kind in TERMINAL_EVENTS:
                self.process.join(1)
                events.append(_publish(self, kind, payload))
                self.finished = True
                self.connection.close()
                self._clean_staging()
                self._stopped.set()
                return events
            events.append((kind, payload))
        return events

    def cancel(self):
        if self.finished:
            self._stopped.set()
            return
        self.finished = True
        # 停止 (taskkill の待ち合わせを含む) と後始末は UI スレッドで待たない。
        # 子プロセスが実際に終わってから片付ける。
        self._stopped.clear()
        threading.Thread(target=self._stop_and_clean, name='kantan-cancel', daemon=True).start()

    def _stop_and_clean(self):
        try:
            self._stop_process()
        except Exception:
            pass  # 停止に失敗しても、パイプと一時フォルダは必ず片付ける
        finally:
            try:
                self.connection.close()
            except Exception:
                pass
            self._clean_staging()
            self._stopped.set()

    def _stop_process(self):
        if not self.process.is_alive():
            return
        # UnRAR can own a subprocess; stop this task's entire process tree.
        if os.name == 'nt':
            try:
                subprocess.run(
                    ['taskkill', '/PID', str(self.process.pid), '/T', '/F'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW, timeout=10,
                )
            except (OSError, subprocess.SubprocessError):
                # taskkill hung or is unavailable; at least stop the worker itself.
                self.process.terminate()
        else:
            self.process.terminate()
        self.process.join(5)
        if self.process.is_alive():
            self.process.kill()
            self.process.join(5)
