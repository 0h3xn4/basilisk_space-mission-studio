#
#  SpaceMissionStudio
#
#  Licensor: 0h3xn4 (https://github.com/0h3xn4)
#
#  Licensed under the EUPL
#
#  SPDX-License-Identifier: EUPL-1.2
#
#  The European Union Public Licence v. 1.2 is in the files LICENSE
#  (English) and LICENSE.de (German) of the SpaceMissionStudio folder and
#  of every package. Third-party components, each under its own licence,
#  are listed in THIRD_PARTY_NOTICES.
#
#
#
#
"""A run shown as it is computed: one scene, one feed, for the globe and
the 2D map (2.12.0, ``docs/developer/windows-views-design.md`` section 3,
decision "Ground tracks, stations and the live map").

:class:`LiveScene` is the one consumer of a run's ``engine.live_view.LiveFeed``
(its ``drain`` removes what it returns, so a second consumer would miss
samples). A timer drains the feed 20 times a second, a few hundred
samples at most each time. One serial worker then does the work of a
tick, off the GUI thread:

* the first samples build the scene (``mission_view_widget.live_scene``:
  the spacecraft's models, the stations) and the page's ``MV.load`` data;
* later samples extend it (``mission_view_widget.live_frames``, that is
  ``engine.scene3d.extend_scene``: the Earth rotation, the Sun, the Moon,
  the altitudes, the ground tracks and the stations' line of sight) and
  make the page's ``MV.append`` data for the new frames.

The worker extends a shallow copy of the scene: ``extend_scene`` puts new
arrays in place of the old ones and changes none, so the scene the GUI
thread holds stays whole while the next one is made. :attr:`started` and
:attr:`extended` carry each new scene to the GUI thread, where the globe
sends the JSON to its page and the map paints the new segments in its
own worker. Neither does the scene's work again, and the GUI thread only
takes signals and paints (CLAUDE.md "Never freeze").
"""

from __future__ import annotations

import copy
import json

from PySide6.QtCore import QObject, QThreadPool, QTimer, Signal

from ..engine import live_view, scene3d

LIVE_TICK_MS = 50  # [ms] the feed is drained this often (20 times a second)
LIVE_BATCH = 400  # [-] at most this many samples drained, and frames made, per tick
LIVE_BATCH_STATES = 2400  # [-] and at most this many spacecraft states (a tick's work stays a few ms)


def live_batch(feed: live_view.LiveFeed | None) -> int:
    """Samples a tick takes: ``LIVE_BATCH``, fewer with many spacecraft."""
    crafts = len(feed.names) if feed is not None and feed.names else 1
    return max(20, min(LIVE_BATCH, LIVE_BATCH_STATES // crafts))


def snapshot(scene: scene3d.Scene) -> scene3d.Scene:
    """A copy of ``scene`` that shares its arrays: ``extend_scene`` on it
    leaves ``scene`` as it is (it puts new arrays in place of the old)."""
    copied = copy.copy(scene)
    copied.crafts = [copy.copy(craft) for craft in scene.crafts]
    return copied


class LiveScene(QObject):
    """One live run's scene, made and extended in a worker.

    ``started(scene, payload)``: the first scene and its ``MV.load`` JSON;
    ``extended(scene, start, stop, frames)``: the scene with frames
    ``start`` to ``stop`` added, and their ``MV.append`` JSON;
    ``failed(message)``: the scene could not be made."""

    started = Signal(object, str)
    extended = Signal(object, int, int, str)
    failed = Signal(str)
    _built = Signal(object, str)  # from the worker (queued to the GUI thread): the scene, its JSON
    _grown = Signal(object, int, int, str)
    _broken = Signal(str)

    def __init__(self, scenario, feed: live_view.LiveFeed, base_dir=None, trail_frames: int = 2,
                 parent: QObject | None = None):
        super().__init__(parent)
        self.feed = feed
        self.scene: scene3d.Scene | None = None
        self._scenario, self._base_dir, self._trail_frames = scenario, base_dir, trail_frames
        self._busy = False  # a job is in the worker
        self._stopped = False
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)  # one job after another: the scene grows in order
        self._timer = QTimer(self)
        self._timer.setInterval(LIVE_TICK_MS)
        self._timer.timeout.connect(self.tick)
        self._built.connect(self._on_built)
        self._grown.connect(self._on_grown)
        self._broken.connect(self._on_broken)

    # -- the GUI thread ---------------------------------------------------------------
    def start(self) -> None:
        self._timer.start()

    def stop(self) -> None:
        """No more draining; a job still running is let finish, its result dropped."""
        self._stopped = True
        self._timer.stop()

    def is_active(self) -> bool:
        return not self._stopped

    def is_idle(self) -> bool:
        """No job in the worker (a stopped scene can still have one)."""
        return not self._busy and self._pool.activeThreadCount() == 0

    def wait(self) -> None:
        """Until the worker is idle (closing the window)."""
        self._pool.waitForDone()

    def frames(self) -> int:
        """Frames of the scene so far."""
        return 0 if self.scene is None else len(self.scene.times_s)

    def tick(self) -> None:
        """Drain the feed into the next job, unless one is still running
        (its samples wait in the feed for the next tick)."""
        if self._stopped or self._busy:
            return
        feed = self.feed
        if self.scene is None:
            if not feed.pending():
                return
            samples = feed.drain(live_batch(feed))
            self._busy = True
            self._pool.start(lambda: self._build(samples))
            return
        samples = feed.drain(live_batch(feed))
        if samples is None:
            return
        self._busy = True
        scene = self.scene
        self._pool.start(lambda: self._grow(scene, samples))

    def _on_built(self, scene, payload: str) -> None:
        self._busy = False
        if self._stopped:
            return
        self.scene = scene
        self.started.emit(scene, payload)

    def _on_grown(self, scene, start: int, stop: int, frames: str) -> None:
        self._busy = False
        if self._stopped:
            return
        self.scene = scene
        self.extended.emit(scene, start, stop, frames)

    def _on_broken(self, message: str) -> None:
        self._busy = False
        if self._stopped:
            return
        self.stop()
        self.failed.emit(message)

    # -- the worker -------------------------------------------------------------------
    def _build(self, samples) -> None:
        from .mission_view_widget import live_scene, scene_payload

        try:
            scene = live_scene(self._scenario, self.feed, samples, self._base_dir)
            payload = scene_payload(scene)
            payload["trail_frames"] = self._trail_frames
            text = json.dumps(payload, separators=(",", ":"))
        except Exception as exc:  # noqa: BLE001 -- shown in the view; the run itself is not affected
            self._send(self._broken, str(exc))
            return
        self._send(self._built, scene, text)

    def _grow(self, scene, samples) -> None:
        from .mission_view_widget import frames_payload, live_frames

        try:
            start = len(scene.times_s)
            grown = live_frames(snapshot(scene), self.feed, samples)
            stop = len(grown.times_s)
            text = json.dumps(frames_payload(grown, start, stop), separators=(",", ":"))
        except Exception as exc:  # noqa: BLE001 -- shown in the view; the run itself is not affected
            self._send(self._broken, str(exc))
            return
        self._send(self._grown, grown, start, stop, text)

    @staticmethod
    def _send(signal, *values) -> None:
        try:
            signal.emit(*values)
        except RuntimeError:  # the view was closed meanwhile: nobody waits for it
            pass
