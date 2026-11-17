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
"""The plan's Gantt chart (Run › Plan; design 2.9): per spacecraft its
activities (the slew before each drawn as a thin bar), its eclipses, its
state of charge and its memory; per station its passes (pale) and the
contacts planned in them (solid, with the spacecraft's name).

The time axis, zoom and pan are the Timeline's (:class:`gui.event_timeline_widget.GanttView`):
the wheel zooms around the pointer, Shift+wheel or a right-button drag
pans, 0 or Home fits the horizon. A click on an activity selects it
(``activity_selected``); a drag of the selected activity moves it, held
within its window or pass (``activity_moved`` when the button is let go).
A click elsewhere sets the shared time cursor (``time_picked``).

Colours are the theme's: activity kinds take the categorical slots in
:data:`ACTIVITY_KINDS` order, a locked activity has a strong outline, the
selected one the focus colour.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QToolTip

from ..schema.operations import ACTIVITY_KINDS
from .event_timeline_widget import _AXIS_HEIGHT, GanttView, _duration_text
from .theme import PALETTE, SERIES_COLORS

_BAR_ROW_PX = 22  # [px] a row of bars
_STRIP_ROW_PX = 40  # [px] a state-of-charge or memory strip
_MIN_BAR_PX = 2  # [px]
_SLEW_PX = 4  # [px] the slew bar's height


def kind_colour(kind: str) -> str:
    """The colour of an activity kind in the theme in use."""
    slot = ACTIVITY_KINDS.index(kind) if kind in ACTIVITY_KINDS else len(ACTIVITY_KINDS)
    return SERIES_COLORS[slot % len(SERIES_COLORS)]


@dataclass
class GanttRow:
    """One row: ``kind`` is "activities", "eclipse", "soc", "memory" or "station"."""

    label: str
    kind: str
    name: str  # the spacecraft's, or the station's

    @property
    def height(self) -> int:
        return _STRIP_ROW_PX if self.kind in ("soc", "memory") else _BAR_ROW_PX


@dataclass
class GanttBar:
    """One bar: an activity (``activity`` its id), a pass or an eclipse."""

    row: int
    start_s: float  # [s]
    end_s: float  # [s]
    kind: str  # an activity kind, "pass" or "eclipse"
    text: str
    activity: str = ""
    locked: bool = False
    slew_from_s: float | None = None  # [s] when the slew before it starts
    low: float = 0.0  # [s] a drag keeps the start at or after this
    high: float = 0.0  # [s] ... and at or before this


class PlanGantt(GanttView):
    """The plan's Gantt chart (module docstring)."""

    activity_selected = Signal(str)  # the activity's id ("" when none)
    activity_moved = Signal(str, float)  # the activity's id, its new start [s]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.plan = None
        self.gantt_rows: list[GanttRow] = []
        self.bars: list[GanttBar] = []
        self.profiles: dict = {}  # spacecraft -> resources dict of the plan
        self.floors: dict = {}  # spacecraft -> the planned lowest state of charge [-]
        self.selected = ""
        self.horizon = (0.0, 1.0)  # [s]
        self._drag: tuple | None = None  # (bar, x at press [px], start at press [s])
        self._dragged_to: float | None = None

    # -- data ---------------------------------------------------------------

    def set_plan(self, plan, opportunities=None, epoch_utc: str | None = None, floors: dict | None = None) -> None:
        """Show ``plan`` (operations.plan.Plan) with the passes and eclipses
        of ``opportunities``; None clears the chart."""
        self.plan, self.selected, self._drag = plan, "", None
        self.gantt_rows, self.bars, self.profiles = [], [], {}
        self.floors = dict(floors or {})
        if plan is None:
            self.rows = []
            self.update()
            return
        self.horizon = (plan.start_s, max(plan.end_s, plan.start_s + 1.0))
        spacecraft = list(dict.fromkeys([a.spacecraft for a in plan.activities] + list(plan.resources)))
        stations = sorted({a.station for a in plan.activities if a.station}
                          | ({p.station for p in opportunities.passes} if opportunities is not None else set()))
        index = {}
        for name in spacecraft:
            for kind, label in (("activities", name), ("eclipse", f"{name} eclipse"),
                                ("soc", f"{name} state of charge"), ("memory", f"{name} memory")):
                if kind in ("soc", "memory") and name not in plan.resources:
                    continue
                index[(kind, name)] = len(self.gantt_rows)
                self.gantt_rows.append(GanttRow(label, kind, name))
        for name in stations:
            index[("station", name)] = len(self.gantt_rows)
            self.gantt_rows.append(GanttRow(name, "station", name))
        self.profiles = {name: plan.resources[name] for name in spacecraft if name in plan.resources}
        if opportunities is not None:
            for name in spacecraft:
                for start, end in opportunities.eclipses.get(name, []):
                    self.bars.append(GanttBar(index[("eclipse", name)], start, end, "eclipse", "eclipse"))
            for item in opportunities.passes:
                if ("station", item.station) in index:
                    self.bars.append(GanttBar(index[("station", item.station)], item.aos_s, item.los_s, "pass",
                                              f"pass of {item.spacecraft}, max elevation "
                                              f"{item.max_elevation_deg:.1f} deg"))
        for activity in plan.activities:
            low, high = self._range(activity, opportunities)
            slew_s = activity.predicted.get("slew_s") or 0.0
            text = activity.type + (f" of {activity.target}" if activity.target else "") + \
                (f" via {activity.station}" if activity.station else "")
            bar = GanttBar(index[("activities", activity.spacecraft)], activity.start_s, activity.end_s,
                           activity.kind, f"{activity.id}: {text}", activity.id, activity.locked,
                           activity.occupied[0] - slew_s if slew_s > 0.0 else None, low, high)
            self.bars.append(bar)
            if activity.station and ("station", activity.station) in index:
                self.bars.append(GanttBar(index[("station", activity.station)], activity.start_s, activity.end_s,
                                          activity.kind, f"{activity.id}: {activity.spacecraft}", activity.id,
                                          activity.locked, None, low, high))
        self.rows = [row.label for row in self.gantt_rows]
        self.run_end_s = self.horizon[1]
        self.epoch_utc = epoch_utc
        self._utc_span = None
        if epoch_utc:
            from ..engine import time_system

            try:
                self._utc_span = tuple(time_system.elapsed_to_utc(epoch_utc, [0.0, self.run_end_s]))
            except ValueError:
                self._utc_span = None
        self.setMinimumHeight(_AXIS_HEIGHT + sum(row.height for row in self.gantt_rows) + 4)
        self.fit()

    @staticmethod
    def _range(activity, opportunities) -> tuple[float, float]:
        """Where a drag may put the activity's start: within its window or
        pass, else where it is."""
        duration = activity.duration_s
        if opportunities is not None and activity.target:
            for window in opportunities.windows_of(activity.target, activity.spacecraft):
                if window.start_s - 1e-6 <= activity.start_s <= window.end_s + 1e-6:
                    return window.start_s, max(window.start_s, window.end_s - duration)
        if opportunities is not None and activity.station:
            for item in opportunities.passes_of(activity.spacecraft, activity.station):
                if item.aos_s - 1e-6 <= activity.start_s <= item.los_s + 1e-6:
                    return item.aos_s, max(item.aos_s, item.los_s - duration)
        return activity.start_s, activity.start_s

    def select(self, activity_id: str) -> None:
        self.selected = activity_id or ""
        self.update()

    # -- the view -------------------------------------------------------------

    def fit(self) -> None:
        self.view = self.horizon
        self.update()

    def _show(self, start: float, width: float) -> None:
        low, high = self.horizon
        width = min(max(width, 1.0), high - low)
        start = min(max(start, low), high - width)
        self.view = (start, start + width)
        self.update()

    def _row_top(self, row: int) -> int:
        return sum(r.height for r in self.gantt_rows[:row])

    def _row_at(self, y: float) -> int:
        top = 0
        for index, row in enumerate(self.gantt_rows):
            if top <= y < top + row.height:
                return index
            top += row.height
        return -1

    def bar_at(self, point: QPointF) -> GanttBar | None:
        """The bar under ``point``, activities first."""
        row = self._row_at(point.y())
        if row < 0 or point.x() < self._plot_rect().left():
            return None
        time_s = self.time_at(point.x())
        tolerance_s = (self.view[1] - self.view[0]) / max(self._plot_rect().width(), 1.0) * 3  # [s] 3 px
        hits = [b for b in self.bars if b.row == row and b.start_s - tolerance_s <= time_s <= b.end_s + tolerance_s]
        return next((b for b in hits if b.activity), hits[0] if hits else None)

    def event_at(self, point: QPointF):
        return None  # the Timeline's tooltips: this view shows its own

    # -- painting -------------------------------------------------------------

    def paintEvent(self, _event):  # noqa: N802 -- Qt API name
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(PALETTE["surface"]))
        rect = self._plot_rect()
        muted, grid = QColor(PALETTE["text_muted"]), QColor(PALETTE["border"])
        if not self.gantt_rows:
            painter.setPen(muted)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No plan yet: press Plan.")
            return
        for index, row in enumerate(self.gantt_rows):
            top = self._row_top(index)
            painter.setPen(QColor(PALETTE["text"] if row.kind in ("activities", "station") else PALETTE["text_muted"]))
            painter.drawText(QRectF(4, top, rect.left() - 8, row.height),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, row.label)
            painter.setPen(grid)
            painter.drawLine(QPointF(rect.left(), top + row.height), QPointF(rect.right(), top + row.height))
        self._paint_axis(painter, rect, muted, grid)
        painter.setClipRect(rect)
        for index, row in enumerate(self.gantt_rows):
            if row.kind in ("soc", "memory"):
                self._paint_strip(painter, index, row, rect)
        for bar in sorted(self.bars, key=lambda b: (b.kind != "pass", b.activity == self.selected)):
            self._paint_bar(painter, bar, rect)
        painter.setClipping(False)
        start, end = self.view
        if self.cursor_s is not None and start <= self.cursor_s <= end:
            x = self.x_of(self.cursor_s)
            painter.setPen(QPen(QColor(PALETTE["accent"]), 2))
            painter.drawLine(QPointF(x, 0), QPointF(x, rect.bottom()))

    def _bar_start(self, bar: GanttBar) -> float:
        if self._drag is not None and self._dragged_to is not None and bar.activity == self._drag[0].activity:
            return self._dragged_to
        return bar.start_s

    def _paint_bar(self, painter: QPainter, bar: GanttBar, rect: QRectF) -> None:
        start_s = self._bar_start(bar)
        end_s = start_s + (bar.end_s - bar.start_s)
        start, end = self.view
        if end_s < start or start_s > end:
            return
        top = self._row_top(bar.row) + 4
        height = self.gantt_rows[bar.row].height - 8
        x0 = self.x_of(max(start_s, start))
        x1 = max(self.x_of(min(end_s, end)), x0 + _MIN_BAR_PX)
        if bar.kind == "pass":
            colour = QColor(PALETTE["border_strong"])
        elif bar.kind == "eclipse":
            colour = QColor(PALETTE["text_faint"])
        else:
            colour = QColor(kind_colour(bar.kind))
        if bar.slew_from_s is not None:
            slew_x0 = self.x_of(max(bar.slew_from_s + start_s - bar.start_s, start))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(PALETTE["text_muted"]))
            painter.drawRect(QRectF(slew_x0, top + height / 2 - _SLEW_PX / 2, max(x0 - slew_x0, 0.0), _SLEW_PX))
        painter.setBrush(colour)
        if bar.activity and bar.activity == self.selected:
            painter.setPen(QPen(QColor(PALETTE["focus"]), 3))
        elif bar.locked:
            painter.setPen(QPen(QColor(PALETTE["text"]), 2))
        else:
            painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(x0, top, x1 - x0, height), 2, 2)

    def _paint_strip(self, painter: QPainter, index: int, row: GanttRow, rect: QRectF) -> None:
        resources = self.profiles.get(row.name)
        if not resources or not resources.get("time_s"):
            return
        top = self._row_top(index) + 3
        height = row.height - 6
        if row.kind == "soc":
            values, full = resources["soc"], 1.0
            floor = self.floors.get(row.name)
        else:
            values = resources["memory_bit"]
            full = resources.get("capacity_bit") or max(max(values), 1.0)
            floor = None
        start, end = self.view
        path = QPainterPath()
        first = True
        for t, value in zip(resources["time_s"], values):
            if t < start - (end - start) * 0.01 or t > end + (end - start) * 0.01:
                continue
            point = QPointF(self.x_of(t), top + height * (1.0 - min(max(value / full, 0.0), 1.0)))
            if first:
                path.moveTo(point)
                first = False
            else:
                path.lineTo(point)
        if floor is not None:
            y = top + height * (1.0 - floor)
            painter.setPen(QPen(QColor(PALETTE["danger"]), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(PALETTE["accent"]), 1.5))
        painter.drawPath(path)

    # -- mouse ----------------------------------------------------------------

    def mousePressEvent(self, event):  # noqa: N802 -- Qt API name
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        bar = self.bar_at(event.position())
        if bar is not None and bar.activity:
            if bar.activity != self.selected:
                self.select(bar.activity)
                self.activity_selected.emit(bar.activity)
            if bar.high > bar.low:
                self._drag, self._dragged_to = (bar, event.position().x(), bar.start_s), None
            return
        if event.position().x() >= self._plot_rect().left():
            if self.selected:
                self.select("")
                self.activity_selected.emit("")
            self.time_picked.emit(self.time_at(event.position().x()))

    def mouseMoveEvent(self, event):  # noqa: N802 -- Qt API name
        if self._drag is not None:
            bar, x, start = self._drag
            per_px = (self.view[1] - self.view[0]) / max(self._plot_rect().width(), 1.0)  # [s/px]
            self._dragged_to = min(max(start + (event.position().x() - x) * per_px, bar.low), bar.high)
            self.update()
            return
        if self._pan_from is not None or event.buttons() & Qt.MouseButton.LeftButton:
            super().mouseMoveEvent(event)
            return
        bar = self.bar_at(event.position())
        if bar is None:
            QToolTip.hideText()
            return
        text = f"{bar.text}\n{_duration_text(bar.end_s - bar.start_s)}" + ("\nlocked" if bar.locked else "")
        if bar.activity and bar.high > bar.low:
            text += "\ndrag to move it within its window"
        QToolTip.showText(event.globalPosition().toPoint(), text, self)

    def mouseReleaseEvent(self, event):  # noqa: N802 -- Qt API name
        if self._drag is not None:
            bar, _x, start = self._drag
            moved = self._dragged_to
            self._drag, self._dragged_to = None, None
            self.update()
            if moved is not None and abs(moved - start) > 1e-3:
                self.activity_moved.emit(bar.activity, float(moved))
            return
        super().mouseReleaseEvent(event)
