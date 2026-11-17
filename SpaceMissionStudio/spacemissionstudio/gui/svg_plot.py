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
"""A plot made as SVG text, shown without ever being stretched (decision
T-40).

``QSvgWidget`` paints an SVG into its whole rectangle, so x and y scale
differently and text and legends skew when the view is wider or shorter
than the picture. :class:`SvgPlotView` draws the picture in a rectangle
of the picture's own aspect ratio, centred (:meth:`SvgPlotView.target_rect`).
Its owner makes the picture at the view's size, in a worker
(:func:`render_image`), when :attr:`SvgPlotView.size_settled` says the
size has held still for :data:`SETTLE_MS`; until the new picture
arrives, the last one is drawn smaller or larger, never skewed."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, QSize, QSizeF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QSizePolicy, QWidget

from .theme import TOKENS, on_change, ui_font

SETTLE_MS = 250  # [ms] a resize is over when the size holds still this long
MIN_RENDER_SIZE = QSize(480, 240)  # [px] smaller views get this picture, drawn smaller (text stays readable)
MIN_HEIGHT_PX = 160  # [px] the view's least height in a layout (the window still fits a short screen)


def render_image(svg: str, size: QSize, device_pixel_ratio: float, background: str) -> QImage:
    """``svg`` drawn into an image of ``size`` (logical pixels) at
    ``device_pixel_ratio``, on ``background`` (``#RRGGBB``). Safe off the
    GUI thread: it paints into a ``QImage``."""
    ratio = max(float(device_pixel_ratio), 1.0)
    image = QImage(max(1, round(size.width() * ratio)), max(1, round(size.height() * ratio)),
                   QImage.Format.Format_ARGB32_Premultiplied)
    image.setDevicePixelRatio(ratio)
    image.fill(QColor(background))
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0.0, 0.0, size.width(), size.height()))
    painter.end()
    return image


def render_size(view_size: QSize) -> QSize:
    """The picture's size for a view of ``view_size``: the view's own,
    but at least :data:`MIN_RENDER_SIZE` each way."""
    return QSize(max(view_size.width(), MIN_RENDER_SIZE.width()), max(view_size.height(), MIN_RENDER_SIZE.height()))


def fitted_rect(picture: QSizeF, area: QRectF) -> QRectF:
    """The largest rectangle of ``picture``'s aspect ratio inside ``area``,
    centred in it."""
    if picture.width() <= 0 or picture.height() <= 0 or area.width() <= 0 or area.height() <= 0:
        return QRectF()
    scale = min(area.width() / picture.width(), area.height() / picture.height())
    width, height = picture.width() * scale, picture.height() * scale
    return QRectF(area.x() + (area.width() - width) / 2.0, area.y() + (area.height() - height) / 2.0, width, height)


class SvgPlotView(QWidget):
    """An SVG plot at its own aspect ratio. :meth:`set_image` shows a
    picture made for the view (:func:`render_image`); :meth:`load` shows
    SVG text drawn by Qt here (small pictures only: it renders on the GUI
    thread). The text of the picture shown is :meth:`svg`."""

    size_settled = Signal()  # the view's size held still (or it was shown at a new size): time for a new picture

    def __init__(self, name: str = "", waiting: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._svg = ""
        self._image: QImage | None = None
        self._renderer: QSvgRenderer | None = None
        self.waiting = waiting  # said while there is no picture
        self.setAccessibleName(name)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(MIN_HEIGHT_PX)
        self._settle = QTimer(self)
        self._settle.setSingleShot(True)
        self._settle.setInterval(SETTLE_MS)
        self._settle.timeout.connect(self.size_settled.emit)
        on_change(self._on_theme_changed)

    # -- what is shown ------------------------------------------------------------
    def svg(self) -> str:
        """The SVG text of the picture shown ("" for none)."""
        return self._svg

    def set_image(self, svg: str, image: QImage) -> None:
        """Show ``image``, the picture of ``svg`` made for this view."""
        self._svg, self._image, self._renderer = svg, image, None
        self.update()

    def load(self, svg: str | bytes | QByteArray) -> None:
        """Show ``svg``, drawn here at its own aspect ratio."""
        data = svg if isinstance(svg, QByteArray) else QByteArray(svg.encode("utf-8") if isinstance(svg, str)
                                                                   else bytes(svg))
        self._svg = bytes(data.data()).decode("utf-8")
        self._renderer = QSvgRenderer(data, self)
        self._image = None
        self.update()

    def clear(self) -> None:
        self._svg, self._image, self._renderer = "", None, None
        self.update()

    def has_picture(self) -> bool:
        return self._image is not None or (self._renderer is not None and self._renderer.isValid())

    def picture_size(self) -> QSizeF:
        """The picture's size in logical pixels (empty without one)."""
        if self._image is not None:
            ratio = self._image.devicePixelRatio()
            return QSizeF(self._image.width() / ratio, self._image.height() / ratio)
        if self._renderer is not None and self._renderer.isValid():
            return QSizeF(self._renderer.defaultSize())
        return QSizeF()

    def target_rect(self) -> QRectF:
        """Where the picture is drawn: centred, at its own aspect ratio."""
        return fitted_rect(self.picture_size(), QRectF(self.rect()))

    def needs_picture(self) -> bool:
        """The picture was not made for the view's present size."""
        if self._image is None:
            return True
        return self.picture_size().toSize() != render_size(self.size())

    # -- Qt ---------------------------------------------------------------------
    def paintEvent(self, _event) -> None:  # noqa: N802 -- Qt's name
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        target = self.target_rect()
        if self._image is not None and not target.isEmpty():
            painter.drawImage(target, self._image)
        elif self._renderer is not None and self._renderer.isValid() and not target.isEmpty():
            self._renderer.render(painter, target)
        elif self.waiting:
            painter.setFont(ui_font("body"))
            painter.setPen(QColor(TOKENS["text.secondary"]))
            painter.drawText(QRectF(self.rect()), int(Qt.AlignmentFlag.AlignCenter), self.waiting)
        painter.end()

    def resizeEvent(self, event) -> None:  # noqa: N802 -- Qt's name
        super().resizeEvent(event)
        self._settle.start()

    def showEvent(self, event) -> None:  # noqa: N802 -- Qt's name
        super().showEvent(event)
        if self.needs_picture():
            self._settle.start()

    def _on_theme_changed(self, _mode: str) -> None:
        self.update()  # the waiting text's colour; the owner makes a new picture
