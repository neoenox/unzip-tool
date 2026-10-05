"""Owned worker processes. Only the parent may publish an extraction result."""
from __future__ import annotations

import multiprocessing as mp
import os
import subprocess
import tempfile
from pathlib import Path

from unzipper import (
    PasswordRequiredError, _extract_into, archive_needs_password,
    clean_staging, error_message, list_contents, publish_staging,
)


def _work(connection, operation, archive, password, staging):
    try:
        if operation == 'list':
            entries = list_contents(archive, password)
            connection.send(('done', (entries, archive_needs_password(archive))))
        else:
            _extract_into(
                archive, Path(staging),
                on_progress=lambda done, total: connection.send(('progress', (done, total))),
                password=password,
                on_file=lambda name: connection.send(('file', name)),
            )
            connection.send(('done', None))
    except PasswordRequiredError as error:
        connection.send(('password', str(error)))
    except Exception as error:
        connection.send(('error', error_message(error)))
    finally:
        connection.close()


class BackgroundTask:
    def __init__(self, operation, archive, password=None, dest=None):
        self.operation = operation
        self.dest = dest
        self.staging = None
        self.finished = False
        if operation == 'extract':
            parent = Path(dest).absolute().parent
            parent.mkdir(parents=True, exist_ok=True)
            self.staging = Path(tempfile.mkdtemp(prefix='.kantan-', dir=parent))
        context = mp.get_context('spawn')
        self.connection, child = context.Pipe(duplex=False)
        self.process = context.Process(
            target=_work, args=(child, operation, str(archive), password, self.staging),
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

    def _clean_staging(self):
        if self.staging is not None:
            clean_staging(self.staging)

    def poll(self):
        if self.finished:
            return []
        events = []
        if not self.process.is_alive() and not self.connection.poll():
            self.finished = True
            self.connection.close()
            self._clean_staging()
            return [('error', '処理が予期せず終了しました。もう一度お試しください。')]
        # Bound work per Tk tick so huge archives cannot starve the GUI.
        for _ in range(100):
            if not self.connection.poll():
                break
            try:
                kind, payload = self.connection.recv()
            except (EOFError, OSError):
                kind, payload = 'error', '処理が予期せず終了しました。もう一度お試しください。'
            if kind in ('done', 'error', 'password'):
                self.process.join(1)
                if kind == 'done' and self.operation == 'extract':
                    try:
                        payload = str(publish_staging(self.staging, self.dest))
                    except Exception as error:
                        kind, payload = 'error', error_message(error)
                self.finished = True
                self.connection.close()
                self._clean_staging()
                events.append((kind, payload))
                return events
            events.append((kind, payload))
        return events

    def cancel(self):
        if self.finished:
            return
        self.finished = True
        try:
            self._stop_process()
        finally:
            # Always release the pipe and the staging folder, even if stopping failed.
            self.connection.close()
            self._clean_staging()

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
