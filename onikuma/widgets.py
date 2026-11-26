"""
Custom Interactive PySide6 Widgets for Onikuma CW935
====================================================
Includes:
- MousePreviewWidget: Vector-painted interactive gaming mouse with live RGB
  lighting simulation and clickable button hotspots.
- BatteryBadgeWidget: Sleek custom-painted battery level pill.
- EffectCard: Clickable RGB effect card with animated swatch indicator.
- ToastNotification: Non-blocking floating feedback banner.
"""

import math
from typing import Optional

from PySide6.QtCore import Qt, QTimer, QRectF, QPointF, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QLinearGradient, QRadialGradient,
    QPainterPath, QFont
)
from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QHBoxLayout, QVBoxLayout, QGraphicsOpacityEffect
)

from .theme import (
    BG_CARD_ELEVATED, BG_INPUT, BORDER_SUBTLE, ACCENT_PRIMARY, ACCENT_GLOW,
    TEXT_MAIN, TEXT_SECONDARY, TEXT_MUTED, SUCCESS, WARNING, ERROR
)


class BatteryBadgeWidget(QWidget):
    """Custom-painted battery status pill with dynamic fill bar and charging bolt."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._percentage: Optional[int] = None
        self._charging: bool = False
        self.setFixedSize(118, 34)

    def set_battery(self, percentage: Optional[int], charging: bool = False):
        self._percentage = percentage
        self._charging = charging
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Pill background
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        painter.setPen(QPen(QColor(BORDER_SUBTLE), 1))
        painter.setBrush(QColor(BG_INPUT))
        painter.drawRoundedRect(rect, 10, 10)

        # Battery icon body
        bat_x, bat_y, bat_w, bat_h = 12, 10, 22, 14
        painter.setPen(QPen(QColor(TEXT_SECONDARY), 1.4))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(QRectF(bat_x, bat_y, bat_w, bat_h), 3, 3)
        # Battery terminal nub
        painter.setBrush(QColor(TEXT_SECONDARY))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(QRectF(bat_x + bat_w + 1, bat_y + 4, 2.5, 6), 1, 1)

        # Fill level
        pct = self._percentage
        if pct is not None:
            clamped = max(0, min(100, pct))
            fill_w = max(2.0, (bat_w - 4) * (clamped / 100.0))
            if self._charging:
                fill_color = QColor(ACCENT_GLOW)
            elif clamped <= 20:
                fill_color = QColor(ERROR)
            elif clamped <= 45:
                fill_color = QColor(WARNING)
            else:
                fill_color = QColor(SUCCESS)
            painter.setBrush(fill_color)
            painter.drawRoundedRect(QRectF(bat_x + 2, bat_y + 2, fill_w, bat_h - 4), 1.5, 1.5)
            label_text = f"{clamped}%" + (" ⚡" if self._charging else "")
            text_color = QColor(TEXT_MAIN)
        else:
            label_text = "--%"
            text_color = QColor(TEXT_MUTED)

        painter.setPen(text_color)
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        painter.drawText(QRectF(42, 0, self.width() - 48, self.height()), Qt.AlignVCenter | Qt.AlignLeft, label_text)


class MousePreviewWidget(QWidget):
    """
    Interactive vector-drawn Onikuma CW935 gaming mouse silhouette.
    - Animates live RGB lighting (modes 0..6) around the base ring, scroll wheel, and logo.
    - Supports clickable & hoverable button zones (0..5) when interactive=True.
    """

    buttonClicked = Signal(int)
    buttonHovered = Signal(int)  # -1 when not hovering any button

    BUTTON_NAMES = [
        "1. Left Click",
        "2. Right Click",
        "3. Middle Click",
        "4. Back (Side)",
        "5. Forward (Side)",
        "6. DPI Button",
    ]

    def __init__(self, interactive: bool = True, parent=None):
        super().__init__(parent)
        self._interactive = interactive
        self._light_mode = 0
        self._dpi_color = QColor("#3B82F6")
        self._phase = 0.0
        self._selected_button = -1
        self._hovered_button = -1
        self._zone_paths: dict[int, QPainterPath] = {}

        self.setMinimumSize(240, 340)
        if interactive:
            self.setMouseTracking(True)
            self.setCursor(Qt.PointingHandCursor)

        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._tick_animation)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._anim_timer.isActive():
            self._anim_timer.start(33)  # ~30 FPS only while visible

    def hideEvent(self, event):
        if self._anim_timer.isActive():
            self._anim_timer.stop()
        super().hideEvent(event)

    def set_light_mode(self, mode: int):
        self._light_mode = mode
        self.update()

    def set_dpi_color(self, hex_color: str):
        self._dpi_color = QColor(hex_color)
        self.update()

    def set_selected_button(self, idx: int):
        self._selected_button = idx
        self.update()

    def _tick_animation(self):
        if self._light_mode != 6:  # Skip phase advance when LEDs are off
            self._phase = (self._phase + 0.06) % (2 * math.pi * 10)
            self.update()

    def _compute_rgb_colors(self) -> tuple[QColor, QColor, float]:
        """Return (primary_rgb, secondary_rgb, intensity 0..1) for current light_mode."""
        mode = self._light_mode
        t = self._phase

        if mode == 6:  # Off
            return QColor("#1E2436"), QColor("#1E2436"), 0.0
        elif mode == 0:  # Wave
            c1 = QColor.fromHsvF((t * 0.12) % 1.0, 0.85, 1.0)
            c2 = QColor.fromHsvF(((t * 0.12) + 0.35) % 1.0, 0.85, 1.0)
            return c1, c2, 0.95
        elif mode == 1:  # Neon
            c1 = QColor.fromHsvF((t * 0.06) % 1.0, 0.95, 1.0)
            return c1, c1, 0.9
        elif mode == 2:  # Touring Flash
            pulse = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(t * 2.2))
            c1 = QColor.fromHsvF((t * 0.18) % 1.0, 0.9, 1.0)
            return c1, self._dpi_color, pulse
        elif mode == 3:  # YOYO Ball
            swing = 0.5 + 0.5 * math.sin(t * 1.8)
            c1 = QColor.fromHsvF((0.55 + 0.3 * swing) % 1.0, 0.9, 1.0)
            c2 = QColor.fromHsvF((0.85 - 0.3 * swing) % 1.0, 0.9, 1.0)
            return c1, c2, 0.9
        elif mode == 4:  # Unidirectional Flashing
            flash = 1.0 if math.sin(t * 3.0) > 0 else 0.18
            return self._dpi_color, QColor(ACCENT_GLOW), flash
        elif mode == 5:  # Circular Breathing
            breath = 0.15 + 0.85 * (0.5 + 0.5 * math.sin(t * 1.1))
            return self._dpi_color, self._dpi_color, breath
        return QColor(ACCENT_PRIMARY), QColor(ACCENT_GLOW), 0.8

    def _hit_test(self, pos: QPointF) -> int:
        for idx, path in self._zone_paths.items():
            if path.contains(pos):
                return idx
        return -1

    def mouseMoveEvent(self, event):
        if not self._interactive:
            return
        hit = self._hit_test(event.position())
        if hit != self._hovered_button:
            self._hovered_button = hit
            self.buttonHovered.emit(hit)
            self.setCursor(Qt.PointingHandCursor if hit >= 0 else Qt.ArrowCursor)
            self.update()

    def leaveEvent(self, event):
        if self._interactive and self._hovered_button != -1:
            self._hovered_button = -1
            self.buttonHovered.emit(-1)
            self.update()

    def mousePressEvent(self, event):
        if not self._interactive:
            return
        if event.button() == Qt.LeftButton:
            hit = self._hit_test(event.position())
            if hit >= 0:
                self._selected_button = hit
                self.buttonClicked.emit(hit)
                self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        cx = w / 2.0
        scale = min((w - 40) / 180.0, (h - 50) / 290.0)
        scale = max(0.65, min(1.35, scale))

        mw = 156.0 * scale
        mh = 264.0 * scale
        mx = cx - mw / 2.0
        my = (h - mh) / 2.0 - 6.0

        c1, c2, intensity = self._compute_rgb_colors()

        # Ambient RGB underglow
        if intensity > 0.05:
            glow_grad = QRadialGradient(cx, my + mh * 0.58, mw * 0.85)
            glow_c = QColor(c1)
            glow_c.setAlphaF(0.28 * intensity)
            glow_grad.setColorAt(0.0, glow_c)
            glow_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.setBrush(glow_grad)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(cx, my + mh * 0.55), mw * 0.85, mh * 0.58)

        # Mouse outer body path
        body = QPainterPath()
        body.moveTo(cx, my)
        body.cubicTo(mx + mw * 0.92, my, mx + mw, my + mh * 0.22, mx + mw * 0.96, my + mh * 0.62)
        body.cubicTo(mx + mw * 0.93, my + mh * 0.88, mx + mw * 0.72, my + mh, cx, my + mh)
        body.cubicTo(mx + mw * 0.28, my + mh, mx + mw * 0.07, my + mh * 0.88, mx + mw * 0.04, my + mh * 0.62)
        body.cubicTo(mx, my + mh * 0.22, mx + mw * 0.08, my, cx, my)

        # Body metallic dark gradient
        body_grad = QLinearGradient(mx, my, mx + mw, my + mh)
        body_grad.setColorAt(0.0, QColor("#22283A"))
        body_grad.setColorAt(0.5, QColor("#171C2B"))
        body_grad.setColorAt(1.0, QColor("#10141F"))
        painter.setBrush(body_grad)

        # RGB rim strip around mouse body
        rim_grad = QLinearGradient(mx, my, mx + mw, my + mh)
        rc1 = QColor(c1)
        rc2 = QColor(c2)
        rc1.setAlphaF(0.25 + 0.75 * intensity)
        rc2.setAlphaF(0.25 + 0.75 * intensity)
        rim_grad.setColorAt(0.0, rc1)
        rim_grad.setColorAt(1.0, rc2)
        painter.setPen(QPen(QBrush(rim_grad), 2.5))
        painter.drawPath(body)

        # Build clickable button zone paths
        self._zone_paths.clear()

        # 0: Left Click
        left_btn = QPainterPath()
        left_btn.moveTo(cx - 2 * scale, my + 4 * scale)
        left_btn.lineTo(cx - 2 * scale, my + mh * 0.37)
        left_btn.lineTo(mx + mw * 0.06, my + mh * 0.37)
        left_btn.cubicTo(mx + mw * 0.03, my + mh * 0.18, mx + mw * 0.14, my + 4 * scale, cx - 2 * scale, my + 4 * scale)
        self._zone_paths[0] = left_btn

        # 1: Right Click
        right_btn = QPainterPath()
        right_btn.moveTo(cx + 2 * scale, my + 4 * scale)
        right_btn.cubicTo(mx + mw * 0.86, my + 4 * scale, mx + mw * 0.97, my + mh * 0.18, mx + mw * 0.94, my + mh * 0.37)
        right_btn.lineTo(cx + 2 * scale, my + mh * 0.37)
        right_btn.closeSubpath()
        self._zone_paths[1] = right_btn

        # 2: Scroll Wheel / Middle Click
        wheel_rect = QRectF(cx - 9 * scale, my + 24 * scale, 18 * scale, 42 * scale)
        wheel_path = QPainterPath()
        wheel_path.addRoundedRect(wheel_rect, 6 * scale, 6 * scale)
        self._zone_paths[2] = wheel_path

        # 5: DPI Button (below scroll wheel)
        dpi_rect = QRectF(cx - 7 * scale, my + 74 * scale, 14 * scale, 22 * scale)
        dpi_path = QPainterPath()
        dpi_path.addRoundedRect(dpi_rect, 4 * scale, 4 * scale)
        self._zone_paths[5] = dpi_path

        # 4: Forward Side Button (upper left thumb)
        fwd_rect = QRectF(mx - 4 * scale, my + mh * 0.34, 13 * scale, 34 * scale)
        fwd_path = QPainterPath()
        fwd_path.addRoundedRect(fwd_rect, 4 * scale, 4 * scale)
        self._zone_paths[4] = fwd_path

        # 3: Back Side Button (lower left thumb)
        back_rect = QRectF(mx - 4 * scale, my + mh * 0.49, 13 * scale, 34 * scale)
        back_path = QPainterPath()
        back_path.addRoundedRect(back_rect, 4 * scale, 4 * scale)
        self._zone_paths[3] = back_path

        # Draw each button zone with hover / selected highlight
        for idx, path in self._zone_paths.items():
            is_sel = idx == self._selected_button
            is_hov = idx == self._hovered_button

            if idx in (0, 1):
                fill = QColor(ACCENT_PRIMARY) if is_sel else (QColor("#29324A") if is_hov else QColor("#1D2335"))
                if is_sel:
                    fill.setAlphaF(0.42)
                pen_col = QColor(ACCENT_GLOW) if (is_sel or is_hov) else QColor("#2D3652")
                painter.setBrush(fill)
                painter.setPen(QPen(pen_col, 1.8 if (is_sel or is_hov) else 1.0))
                painter.drawPath(path)
            elif idx == 2:
                # Scroll wheel with RGB core
                painter.setBrush(QColor("#0D1018"))
                painter.setPen(QPen(QColor(ACCENT_GLOW) if (is_sel or is_hov) else c1, 2.0))
                painter.drawPath(path)
                # Wheel tread lines
                painter.setPen(QPen(c1 if intensity > 0.1 else QColor("#3A4460"), 1.5))
                for step in range(4):
                    ly = wheel_rect.top() + (8 + step * 8) * scale
                    painter.drawLine(QPointF(wheel_rect.left() + 4 * scale, ly), QPointF(wheel_rect.right() - 4 * scale, ly))
            elif idx == 5:
                # DPI button
                dpi_fill = QColor(self._dpi_color)
                if not (is_sel or is_hov):
                    dpi_fill.setAlphaF(0.55)
                painter.setBrush(dpi_fill)
                painter.setPen(QPen(QColor("#FFFFFF") if (is_sel or is_hov) else QColor("#334155"), 1.5))
                painter.drawPath(path)
            else:
                # Side buttons
                side_fill = QColor(ACCENT_PRIMARY) if is_sel else (QColor("#3B476B") if is_hov else QColor("#262F47"))
                painter.setBrush(side_fill)
                painter.setPen(QPen(QColor(ACCENT_GLOW) if (is_sel or is_hov) else QColor("#3D496B"), 1.5))
                painter.drawPath(path)

        # Onikuma Palm Logo / Emblem Glow
        logo_center = QPointF(cx, my + mh * 0.72)
        logo_color = QColor(c2)
        logo_color.setAlphaF(0.15 + 0.85 * intensity)
        painter.setPen(QPen(logo_color, 2.2))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(logo_center, 15 * scale, 15 * scale)
        painter.setFont(QFont("Segoe UI", int(9 * scale), QFont.Bold))
        painter.drawText(
            QRectF(cx - 18 * scale, logo_center.y() - 10 * scale, 36 * scale, 20 * scale),
            Qt.AlignCenter, "CW"
        )

        # Active hover/selection caption at bottom
        active_idx = self._hovered_button if self._hovered_button >= 0 else self._selected_button
        if self._interactive and active_idx >= 0:
            caption = self.BUTTON_NAMES[active_idx]
            painter.setPen(QColor(ACCENT_GLOW))
            painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
            painter.drawText(QRectF(0, h - 26, w, 22), Qt.AlignCenter, caption)
        elif self._interactive:
            painter.setPen(QColor(TEXT_MUTED))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(QRectF(0, h - 26, w, 22), Qt.AlignCenter, "Click any button on the mouse to highlight")


class EffectCard(QFrame):
    """Interactive RGB lighting mode card with custom color swatch and selection state."""

    clicked = Signal(int)

    def __init__(self, mode_id: int, title: str, subtitle: str, swatch_colors: list[str], parent=None):
        super().__init__(parent)
        self.mode_id = mode_id
        self._selected = False
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("EffectCard")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(12)

        # Color swatch badge
        self.swatch = _SwatchDot(swatch_colors)
        layout.addWidget(self.swatch)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet(f"color: {TEXT_MAIN}; font-size: 13px; font-weight: 700; border: none;")
        self.lbl_sub = QLabel(subtitle)
        self.lbl_sub.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px; border: none;")
        text_col.addWidget(self.lbl_title)
        text_col.addWidget(self.lbl_sub)
        layout.addLayout(text_col, 1)

        self.lbl_badge = QLabel("ACTIVE")
        self.lbl_badge.setStyleSheet(
            f"background-color: {ACCENT_PRIMARY}; color: #FFFFFF; border-radius: 6px; "
            f"padding: 2px 8px; font-size: 10px; font-weight: 700; border: none;"
        )
        self.lbl_badge.setVisible(False)
        layout.addWidget(self.lbl_badge)

        self._apply_style()

    def set_selected(self, selected: bool):
        self._selected = selected
        self.lbl_badge.setVisible(selected)
        self._apply_style()

    def _apply_style(self):
        if self._selected:
            self.setStyleSheet(
                f"QFrame#EffectCard {{ background-color: rgba(46, 107, 255, 0.14); "
                f"border: 1px solid {ACCENT_PRIMARY}; border-radius: 12px; }}"
            )
        else:
            self.setStyleSheet(
                f"QFrame#EffectCard {{ background-color: {BG_CARD_ELEVATED}; "
                f"border: 1px solid {BORDER_SUBTLE}; border-radius: 12px; }}"
                f"QFrame#EffectCard:hover {{ border-color: #3B476B; background-color: #202740; }}"
            )

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.mode_id)


class _SwatchDot(QWidget):
    def __init__(self, colors: list[str], parent=None):
        super().__init__(parent)
        self._colors = colors
        self.setFixedSize(28, 28)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if len(self._colors) >= 2:
            grad = QLinearGradient(0, 0, self.width(), self.height())
            for idx, col in enumerate(self._colors):
                grad.setColorAt(idx / (len(self._colors) - 1), QColor(col))
            painter.setBrush(grad)
        else:
            painter.setBrush(QColor(self._colors[0]))
        painter.setPen(QPen(QColor("#334155"), 1))
        painter.drawEllipse(2, 2, 24, 24)


class ToastNotification(QFrame):
    """Non-blocking floating toast notification anchored inside the main window."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVisible(False)
        self.setFixedHeight(42)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        self.label = QLabel("")
        self.label.setStyleSheet("color: #FFFFFF; font-weight: 600; font-size: 13px; border: none;")
        layout.addWidget(self.label)

        self._opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity)

        self._fade_anim = QPropertyAnimation(self._opacity, b"opacity", self)
        self._fade_anim.setDuration(260)
        self._fade_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._fade_anim.finished.connect(self._on_anim_finished)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._start_fade_out)
        self._fading_out = False

    def show_message(self, message: str, kind: str = "success", duration_ms: int = 2600):
        colors = {
            "success": ("#065F46", "#10B981"),
            "warning": ("#78350F", "#F59E0B"),
            "error": ("#7F1D1D", "#EF4444"),
            "info": ("#1E3A8A", "#3B82F6"),
        }
        bg, border = colors.get(kind, colors["info"])
        self.setStyleSheet(
            f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 10px; }}"
        )
        self.label.setText(message)
        self.adjustSize()
        self._reposition()

        self._fading_out = False
        self._fade_anim.stop()
        self._opacity.setOpacity(1.0)
        self.setVisible(True)
        self.raise_()
        self._hide_timer.start(duration_ms)

    def _reposition(self):
        if self.parentWidget():
            pw = self.parentWidget().width()
            ph = self.parentWidget().height()
            self.move(pw - self.width() - 24, ph - self.height() - 24)

    def _start_fade_out(self):
        self._fading_out = True
        self._fade_anim.setStartValue(1.0)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.start()

    def _on_anim_finished(self):
        if self._fading_out:
            self.setVisible(False)
            self._fading_out = False
