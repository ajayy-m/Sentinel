"""Live metric charts using pyqtgraph for real-time visualization."""
from __future__ import annotations

from collections import deque
from typing import Any

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from pyqtgraph import PlotWidget, mkPen
from pyqtgraph.Qt import QtCore


class MetricChartWidget(QWidget):
    """Live chart for a single metric over time."""

    def __init__(self, metric_name: str, max_samples: int = 60) -> None:
        super().__init__()
        self._metric_name = metric_name
        self._max_samples = max_samples
        self._values: deque[float] = deque(maxlen=max_samples)
        self._times: deque[int] = deque(maxlen=max_samples)
        self._timestamp_counter = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel(f"{metric_name} (last 60 samples)")
        layout.addWidget(label)

        self._plot = PlotWidget()
        self._plot.setLabel("bottom", "Time (samples)")
        self._plot.setLabel("left", "Value (%)")
        self._plot.setYRange(0, 100)
        self._plot.showGrid(True, True, alpha=0.2)
        self._plot.setBackground("#ffffff")
        self._plot.getPlotItem().setTitle(f"<span style='color:#000000'>{metric_name}</span>")

        self._line = self._plot.plot(pen=mkPen(color="#0a246a", width=2))
        layout.addWidget(self._plot)
        self.setLayout(layout)

    def add_sample(self, value: float) -> None:
        """Add a new metric sample."""
        self._values.append(max(0.0, min(100.0, float(value))))
        self._times.append(self._timestamp_counter)
        self._timestamp_counter += 1
        self._update_plot()

    def _update_plot(self) -> None:
        """Update the chart."""
        if self._values:
            self._line.setData(list(self._times), list(self._values))

    def clear(self) -> None:
        """Clear all data."""
        self._values.clear()
        self._times.clear()
        self._timestamp_counter = 0
        self._update_plot()


class FleetOverviewChart(QWidget):
    """Dashboard overview showing active nodes and health score trend."""

    def __init__(self, max_samples: int = 60) -> None:
        super().__init__()
        self._max_samples = max_samples
        self._active_nodes: deque[int] = deque(maxlen=max_samples)
        self._health_scores: deque[float] = deque(maxlen=max_samples)
        self._times: deque[int] = deque(maxlen=max_samples)
        self._timestamp_counter = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel("Fleet Health Trend (last 60 samples)")
        layout.addWidget(label)

        self._plot = PlotWidget()
        self._plot.setLabel("bottom", "Time (samples)")
        self._plot.setLabel("left", "Health Score / Node Count")
        self._plot.setYRange(0, 100)
        self._plot.showGrid(True, True, alpha=0.2)
        self._plot.setBackground("#ffffff")
        self._plot.getPlotItem().setTitle("<span style='color:#000000'>Fleet Health Trend</span>")

        self._health_line = self._plot.plot(name="Health Score", pen=mkPen(color="#0a246a", width=2))
        self._nodes_line = self._plot.plot(name="Active Nodes", pen=mkPen(color="#808080", width=2))
        self._plot.addLegend()

        layout.addWidget(self._plot)
        self.setLayout(layout)

    def add_sample(self, active_nodes: int, health_score: float) -> None:
        """Add a data point."""
        self._active_nodes.append(max(0, int(active_nodes)))
        self._health_scores.append(max(0.0, min(100.0, float(health_score))))
        self._times.append(self._timestamp_counter)
        self._timestamp_counter += 1
        self._update_plot()

    def _update_plot(self) -> None:
        """Update the chart."""
        if self._times:
            self._health_line.setData(list(self._times), list(self._health_scores))
            self._nodes_line.setData(list(self._times), list(self._active_nodes))

    def clear(self) -> None:
        """Clear all data."""
        self._active_nodes.clear()
        self._health_scores.clear()
        self._times.clear()
        self._timestamp_counter = 0
        self._update_plot()
