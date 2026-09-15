"""Reusable interface components."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.models import FaceObservation, FramePacket
from app.utils.image_utils import numpy_to_qimage

PALETTE = ("#43d6a3", "#55a9ff", "#a987ff", "#f6ba58", "#ff7d8f", "#31c8d8")


def initials(name: str) -> str:
    clean = name.strip()
    if not clean:
        return "?"
    if any("\u4e00" <= char <= "\u9fff" for char in clean):
        return clean[-2:] if len(clean) > 1 else clean
    parts = [part for part in clean.split() if part]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return clean[:2].upper()


class Card(QFrame):
    def __init__(self, parent: QWidget | None = None, soft: bool = False):
        super().__init__(parent)
        self.setProperty("card", "soft" if soft else "true")


class AvatarWidget(QWidget):
    def __init__(self, name: str = "?", size: int = 44, parent: QWidget | None = None):
        super().__init__(parent)
        self._name = name
        self._size = size
        self.setFixedSize(size, size)

    def set_name(self, name: str) -> None:
        self._name = name
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(self._size, self._size)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        digest = hashlib.sha1(self._name.encode("utf-8")).hexdigest()
        color = QColor(PALETTE[int(digest[:2], 16) % len(PALETTE)])
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(self.rect().adjusted(1, 1, -1, -1))
        painter.setPen(QColor("#07130f"))
        painter.setFont(
            QFont("Microsoft YaHei UI", max(9, self._size // 4), QFont.Bold)
        )
        painter.drawText(self.rect(), Qt.AlignCenter, initials(self._name))


class StatusPill(QLabel):
    def __init__(
        self, text: str = "离线", online: bool = False, parent: QWidget | None = None
    ):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(28)
        self.setMinimumWidth(78)
        self.set_state(online, text)

    def set_state(self, online: bool, text: str | None = None) -> None:
        if text is not None:
            self.setText(text)
        if online:
            self.setStyleSheet(
                "QLabel { color:#43d6a3; background:#43d6a31f; border:1px solid #43d6a355; border-radius:14px; padding:2px 10px; font-weight:650; }"
            )
        else:
            self.setStyleSheet(
                "QLabel { color:#8d9caf; background:#8d9caf16; border:1px solid #8d9caf44; border-radius:14px; padding:2px 10px; font-weight:650; }"
            )


class StatCard(Card):
    def __init__(
        self, title: str, value: str, hint: str, accent: str = "#43d6a3", parent=None
    ):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(5)
        top = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setProperty("role", "muted")
        badge = QLabel("●")
        badge.setStyleSheet(f"color:{accent}; font-size:13px;")
        top.addWidget(title_label)
        top.addStretch()
        top.addWidget(badge)
        self.value_label = QLabel(value)
        self.value_label.setProperty("role", "metric")
        self.hint_label = QLabel(hint)
        self.hint_label.setProperty("role", "muted")
        layout.addLayout(top)
        layout.addWidget(self.value_label)
        layout.addWidget(self.hint_label)

    def set_value(self, value: str, hint: str | None = None) -> None:
        self.value_label.setText(value)
        if hint is not None:
            self.hint_label.setText(hint)


class CameraCanvas(QWidget):
    def __init__(self, parent: QWidget | None = None, compact: bool = False):
        super().__init__(parent)
        self._image: QImage | None = None
        self._observations: list[FaceObservation] = []
        self._placeholder = "摄像头已关闭"
        self._subtitle = "点击“开启摄像头”后才会采集画面"
        self._compact = compact
        self._fps = 0.0
        self._processing_ms = 0.0
        self.setMinimumSize(420, 250 if compact else 340)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def sizeHint(self) -> QSize:
        return QSize(760, 430) if not self._compact else QSize(520, 260)

    def set_packet(self, packet: FramePacket) -> None:
        self._image = numpy_to_qimage(packet.frame)
        self._observations = list(packet.observations)
        self._fps = packet.fps
        self._processing_ms = packet.processing_ms
        self.update()

    def clear_frame(self, reason: str = "摄像头已关闭") -> None:
        self._image = None
        self._observations = []
        self._placeholder = reason
        self._subtitle = "摄像头释放后不会再接收画面"
        self.update()

    def _target_rect(self) -> QRectF:
        if self._image is None:
            return QRectF(self.rect()).adjusted(8, 8, -8, -8)
        available = QRectF(self.rect()).adjusted(8, 8, -8, -8)
        image_ratio = self._image.width() / max(1, self._image.height())
        target_ratio = available.width() / max(1.0, available.height())
        if image_ratio >= target_ratio:
            width = available.width()
            height = width / image_ratio
            top = available.top() + (available.height() - height) / 2
            return QRectF(available.left(), top, width, height)
        height = available.height()
        width = height * image_ratio
        left = available.left() + (available.width() - width) / 2
        return QRectF(left, available.top(), width, height)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        background = QPainterPath()
        background.addRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 14, 14)
        painter.fillPath(background, QColor("#05090d"))

        target = self._target_rect()
        if self._image is None:
            painter.setPen(QColor("#8d9caf"))
            painter.setFont(
                QFont(
                    "Microsoft YaHei UI",
                    14 if not self._compact else 12,
                    QFont.DemiBold,
                )
            )
            painter.drawText(target, Qt.AlignCenter, self._placeholder)
            painter.setPen(QColor("#5d6b7e"))
            painter.setFont(QFont("Microsoft YaHei UI", 10))
            painter.drawText(
                target.adjusted(0, 30, 0, 30), Qt.AlignCenter, self._subtitle
            )
            return

        painter.drawImage(target, self._image)
        x_scale = target.width() / self._image.width()
        y_scale = target.height() / self._image.height()
        for observation in self._observations:
            x, y, width, height = observation.bbox
            rect = QRectF(
                target.left() + x * x_scale,
                target.top() + y * y_scale,
                width * x_scale,
                height * y_scale,
            )
            if observation.recognized and observation.stable:
                color = QColor("#43d6a3")
            elif observation.stable:
                color = QColor("#f6ba58")
            else:
                color = QColor("#55a9ff")
            painter.setPen(QPen(color, 2.2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect, 8, 8)

            label = observation.name if observation.stable else "确认中"
            if (
                observation.stable
                and observation.recognized
                and observation.similarity is not None
            ):
                label = f"{label}  {observation.similarity:.2f}"
            elif observation.stable and not observation.recognized:
                label = "Unknown"
            painter.setFont(QFont("Microsoft YaHei UI", 9, QFont.DemiBold))
            metrics = painter.fontMetrics()
            text_width = metrics.horizontalAdvance(label) + 16
            text_height = metrics.height() + 8
            label_rect = QRectF(
                rect.left(),
                max(target.top(), rect.top() - text_height - 2),
                text_width,
                text_height,
            )
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(5, 9, 13, 220))
            painter.drawRoundedRect(label_rect, 6, 6)
            painter.setPen(color)
            painter.drawText(label_rect, Qt.AlignCenter, label)

        if not self._compact:
            perf = f"FPS {self._fps:04.1f}   ·   处理 {self._processing_ms:05.1f} ms"
            painter.setPen(QColor(240, 246, 251, 230))
            painter.setFont(QFont("Microsoft YaHei UI", 9, QFont.DemiBold))
            painter.drawText(
                target.adjusted(12, 10, -12, -10), Qt.AlignTop | Qt.AlignRight, perf
            )


class FaceResultCard(Card):
    def __init__(self, observation: FaceObservation | None = None, parent=None):
        super().__init__(parent, soft=True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        self.avatar = AvatarWidget("?", 38)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(1)
        self.name_label = QLabel("等待检测")
        self.name_label.setProperty("role", "section")
        self.detail_label = QLabel("画面中暂无人脸")
        self.detail_label.setProperty("role", "muted")
        text_layout.addWidget(self.name_label)
        text_layout.addWidget(self.detail_label)
        layout.addWidget(self.avatar)
        layout.addLayout(text_layout, 1)
        self.confidence = QLabel("")
        self.confidence.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.confidence)
        self.set_observation(observation)

    def set_observation(self, observation: FaceObservation | None) -> None:
        if observation is None:
            self.avatar.set_name("?")
            self.name_label.setText("等待检测")
            self.detail_label.setText("画面中暂无人脸")
            self.confidence.setText("")
            return
        self.avatar.set_name(observation.name)
        if not observation.stable:
            self.name_label.setText("正在确认")
            self.name_label.setStyleSheet("color:#55a9ff;")
            self.detail_label.setText("避免快速移动，连续多帧一致后更新")
            self.confidence.setText("stabilizing…")
        elif observation.recognized:
            self.name_label.setText(observation.name)
            self.name_label.setStyleSheet("color:#43d6a3;")
            similarity = (
                observation.similarity if observation.similarity is not None else 0.0
            )
            self.detail_label.setText("Recognized · 本地已登记")
            self.confidence.setText(f"Similarity\n{similarity:.2f}")
            self.confidence.setStyleSheet("color:#43d6a3; font-weight:700;")
        else:
            self.name_label.setText("Unknown")
            self.name_label.setStyleSheet("color:#f6ba58;")
            self.detail_label.setText("未登记 · 不会自动建档")
            similarity = observation.similarity
            self.confidence.setText(
                f"Similarity\n{similarity:.2f}"
                if similarity is not None
                else "Not Registered"
            )
            self.confidence.setStyleSheet("color:#f6ba58; font-weight:700;")


class FaceSummaryPanel(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(10)
        header = QHBoxLayout()
        title = QLabel("当前人脸")
        title.setProperty("role", "section")
        self.count_label = QLabel("0 张")
        self.count_label.setProperty("role", "muted")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.count_label)
        self._layout.addLayout(header)
        self.cards: list[FaceResultCard] = []
        self.empty = QLabel("检测到人脸后，这里会显示每个人脸独立结果。")
        self.empty.setWordWrap(True)
        self.empty.setProperty("role", "muted")
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setMinimumHeight(110)
        self._layout.addWidget(self.empty)
        self._layout.addStretch()

    def set_observations(self, observations: Iterable[FaceObservation]) -> None:
        items = list(observations)
        self.count_label.setText(f"{len(items)} 张")
        while len(self.cards) < len(items):
            card = FaceResultCard()
            self.cards.append(card)
            self._layout.insertWidget(self._layout.count() - 2, card)
        for index, card in enumerate(self.cards):
            visible = index < len(items)
            card.setVisible(visible)
            card.set_observation(items[index] if visible else None)
        self.empty.setVisible(not items)


class PageHeader(QWidget):
    def __init__(self, title: str, subtitle: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        title_label = QLabel(title)
        title_label.setProperty("role", "title")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setProperty("role", "muted")
        subtitle_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
