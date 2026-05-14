from __future__ import annotations

import json
import logging
import socket
import subprocess
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QRect, QTimer, Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QProgressBar,
    QSizePolicy,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from sentinel.actions.gate import ApprovalGate
from sentinel.core.execution import ActionExecutionPlanner
from sentinel.core.storage import Storage
from sentinel.ui.charts import FleetOverviewChart, MetricChartWidget

LOGGER = logging.getLogger(__name__)


class AnimatedPushButton(QPushButton):
    def __init__(self, text: str) -> None:
        super().__init__(text)
        self._geometry_animation = QPropertyAnimation(self, b"geometry", self)
        self._geometry_animation.setDuration(90)
        self._geometry_animation.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._base_geometry: QRect | None = None
        self.pressed.connect(self._animate_pressed)
        self.released.connect(self._animate_released)

    def _animate_pressed(self) -> None:
        current = QRect(self.geometry())
        self._base_geometry = QRect(current)
        pressed = current.adjusted(1, 1, -1, -1)
        self._geometry_animation.stop()
        self._geometry_animation.setStartValue(current)
        self._geometry_animation.setEndValue(pressed)
        self._geometry_animation.start()

    def _animate_released(self) -> None:
        if self._base_geometry is None:
            return
        current = QRect(self.geometry())
        self._geometry_animation.stop()
        self._geometry_animation.setStartValue(current)
        self._geometry_animation.setEndValue(self._base_geometry)
        self._geometry_animation.start()


class SentinelMainWindow(QMainWindow):
    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__()
        self._config = config
        collector_cfg = config.get("collector", {})
        ui_cfg = config.get("ui", {})
        api_cfg = config.get("integration", {}).get("api", {})
        self._sqlite_path = str(collector_cfg.get("sqlite_path", "./data/sentinel.db"))
        self._refresh_ms = int(ui_cfg.get("refresh_interval_ms", 2000))
        self._max_rows = int(ui_cfg.get("max_rows", 10))
        self._api_url = f"http://{api_cfg.get('host', '127.0.0.1')}:{api_cfg.get('port', 8085)}"
        self._storage = Storage(self._sqlite_path)
        self._gate = ApprovalGate.from_config(config)
        self._execution_planner = ActionExecutionPlanner.from_config(config)
        self._current_recommendations: dict[int, dict[str, Any]] = {}
        self._current_requests: dict[int, dict[str, Any]] = {}
        
        # Initialize chart widgets
        self._fleet_chart = FleetOverviewChart(max_samples=60)
        self._cpu_chart = MetricChartWidget("CPU Usage", max_samples=60)
        self._gpu_chart = MetricChartWidget("GPU Usage", max_samples=60)
        self._memory_chart = MetricChartWidget("Memory Usage", max_samples=60)
        self._disk_chart = MetricChartWidget("Disk Usage", max_samples=60)

        self.setWindowTitle(str(ui_cfg.get("window_title", "Sentinel Control Center")))
        self.resize(int(ui_cfg.get("window_width", 1440)), int(ui_cfg.get("window_height", 900)))

        self._summary_labels: dict[str, QLabel] = {}
        self._summary_bars: dict[str, QProgressBar] = {}
        self._status_bar = self.statusBar()

        central = QWidget()
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        # Header with refresh button
        header_layout = QHBoxLayout()
        header = QLabel("Sentinel Control Center")
        header.setObjectName("sentinelHeader")
        header.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(header, 1)
        
        refresh_btn = AnimatedPushButton("Refresh")
        refresh_btn.setMinimumWidth(88)
        refresh_btn.setMinimumHeight(30)
        refresh_btn.clicked.connect(self.refresh)
        header_layout.addWidget(refresh_btn, 0)
        
        root_layout.addLayout(header_layout)

        subtitle = QLabel("Live summaries, anomaly signals, root-cause hints, and action review")
        subtitle.setObjectName("sentinelSubtitle")
        root_layout.addWidget(subtitle)

        overview_box = QGroupBox("Fleet Overview")
        overview_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        overview_layout = QGridLayout(overview_box)
        overview_layout.setContentsMargins(8, 8, 8, 8)
        overview_layout.setHorizontalSpacing(12)
        overview_layout.setVerticalSpacing(8)

        overview_fields = [
            ("active_nodes", "Active Nodes"),
            ("latest_status", "Latest Health"),
            ("latest_score", "Latest Score"),
            ("latest_alerts", "Recent Alerts"),
            ("latest_hints", "Root-Cause Hints"),
            ("latest_recommendations", "Recommendations"),
            ("latest_requests", "Action Requests"),
            ("latest_decisions", "Approvals"),
        ]
        for index, (key, title) in enumerate(overview_fields):
            tile = self._build_metric_tile(key, title)
            overview_layout.addWidget(tile, index // 4, index % 4)

        root_layout.addWidget(overview_box)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_tabs = QTabWidget()
        self._health_table = self._build_table(["Node", "Status", "Score", "Timestamp", "Reasons"])
        self._alerts_table = self._build_table(["Node", "Severity", "Category", "Message", "Timestamp"])
        self._hints_table = self._build_table(["Node", "Category", "Confidence", "Message", "Timestamp"])
        self._recommendations_table = self._build_table(
            ["Node", "Priority", "Category", "Title", "Timestamp"]
        )
        self._discovered_table = self._build_table(["Node ID", "Hostname", "OS", "Platform", "Timestamp"])
        self._requests_table = self._build_table(["ID", "Node", "Action", "Risk", "Status", "Title"])
        self._decisions_table = self._build_table(["Request ID", "Actor", "Approved", "Rationale", "Timestamp"])

        left_tabs.addTab(self._health_table, "Health")
        left_tabs.addTab(self._discovered_table, "Discovered Nodes")
        left_tabs.addTab(self._alerts_table, "Alerts")
        left_tabs.addTab(self._hints_table, "Root Cause")
        left_tabs.addTab(self._recommendations_table, "Recommendations")
        left_tabs.addTab(self._requests_table, "Action Queue")
        left_tabs.addTab(self._decisions_table, "Decision Log")
        
        # Add Preflight Status tab
        self._preflight_widget = self._build_preflight_panel()
        left_tabs.addTab(self._preflight_widget, "Preflight Status")
        
        left_tabs.addTab(self._fleet_chart, "Fleet Trend")
        left_tabs.addTab(self._cpu_chart, "CPU")
        left_tabs.addTab(self._gpu_chart, "GPU")
        left_tabs.addTab(self._memory_chart, "Memory")
        left_tabs.addTab(self._disk_chart, "Disk")

        # Enable context menus for approval gate workflow
        self._recommendations_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._recommendations_table.customContextMenuRequested.connect(self._on_recommendation_context_menu)
        self._requests_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._requests_table.customContextMenuRequested.connect(self._on_request_context_menu)

        # LLM Query Panel (right side)
        right_box = QGroupBox("Ask the LLM")
        right_layout = QVBoxLayout(right_box)
        right_layout.setSpacing(8)
        
        # Question input
        input_label = QLabel("Your question:")
        input_label.setStyleSheet("font-weight: bold;")
        right_layout.addWidget(input_label)
        
        self._llm_question_input = QLineEdit()
        self._llm_question_input.setPlaceholderText("e.g., 'Which node is struggling?' or 'What's causing the CPU spike?'")
        self._llm_question_input.returnPressed.connect(self._send_llm_query)
        right_layout.addWidget(self._llm_question_input)
        
        # Send button
        send_btn = AnimatedPushButton("Ask LLM")
        send_btn.clicked.connect(self._send_llm_query)
        right_layout.addWidget(send_btn)
        
        # Response display
        response_label = QLabel("Response:")
        response_label.setStyleSheet("font-weight: bold; margin-top: 12px;")
        right_layout.addWidget(response_label)
        
        self._llm_response = QPlainTextEdit()
        self._llm_response.setReadOnly(True)
        self._llm_response.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self._llm_response.setPlaceholderText("LLM responses will appear here...")
        self._llm_response.setMinimumHeight(104)
        self._llm_response.setMaximumHeight(136)
        self._llm_response.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        right_layout.addWidget(self._llm_response)

        # Snapshot summary
        snapshot_label = QLabel("Current Snapshot:")
        snapshot_label.setStyleSheet("font-weight: bold; margin-top: 12px;")
        right_layout.addWidget(snapshot_label)

        self._latest_json = QPlainTextEdit()
        self._latest_json.setReadOnly(True)
        self._latest_json.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self._latest_json.setPlaceholderText("Latest fleet snapshot will appear here...")
        self._latest_json.setMinimumHeight(104)
        self._latest_json.setMaximumHeight(156)
        self._latest_json.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        right_layout.addWidget(self._latest_json)

        # LLM History table
        history_label = QLabel("History:")
        history_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        right_layout.addWidget(history_label)

        self._llm_history_table = QTableWidget(0, 3)
        self._llm_history_table.setHorizontalHeaderLabels(["Question", "Response (summary)", "Timestamp"])
        self._llm_history_table.verticalHeader().setVisible(False)
        self._llm_history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._llm_history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._llm_history_table.setMinimumHeight(180)
        # Context menu for feedback and actions
        self._llm_history_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._llm_history_table.customContextMenuRequested.connect(self._on_llm_history_context_menu)
        right_layout.addWidget(self._llm_history_table)

        # Re-run selected query button
        rerun_btn = QPushButton("Re-run Selected")
        rerun_btn.clicked.connect(self._rerun_selected_llm_query)
        right_layout.addWidget(rerun_btn)

        splitter.addWidget(left_tabs)
        splitter.addWidget(right_box)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([1050, 450])

        root_layout.addWidget(splitter)
        self.setCentralWidget(central)

        self._timer = QTimer(self)
        self._timer.setInterval(self._refresh_ms)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()

        self.refresh()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._storage.close()
        super().closeEvent(event)

    def refresh(self) -> None:
        try:
            active_nodes = self._storage.get_active_node_count()
            health = self._storage.get_recent_health_summaries(limit=1)
            alerts = self._storage.get_recent_alerts(limit=self._max_rows)
            hints = self._storage.get_recent_root_cause_hints(limit=self._max_rows)
            recommendations = self._storage.get_recent_action_recommendations(limit=self._max_rows)
            requests = self._storage.get_recent_action_requests(limit=self._max_rows)
            decisions = self._storage.get_recent_approval_decisions(limit=self._max_rows)
            payloads = self._storage.get_recent_payloads(limit=1)

            summary = {
                "active_nodes": active_nodes,
                "latest_health": health[0] if health else None,
                "latest_payload": payloads[0] if payloads else None,
                "latest_alert": alerts[0] if alerts else None,
                "latest_hint": hints[0] if hints else None,
                "latest_recommendation": recommendations[0] if recommendations else None,
                "latest_request": requests[0] if requests else None,
                "latest_decision": decisions[0] if decisions else None,
            }
            self._latest_json.setPlainText(json.dumps(summary, indent=2, sort_keys=True))

            latest_status = health[0]["status"] if health else "unknown"
            latest_score = str(health[0]["score"] if health else "n/a")
            latest_score_value = int(health[0]["score"] if health else 0)

            self._set_metric_tile("active_nodes", str(active_nodes), min(active_nodes, 100))
            self._set_metric_tile(
                "latest_status",
                latest_status,
                100 if latest_status == "healthy" else 65 if latest_status == "warning" else 30,
            )
            self._set_metric_tile("latest_score", latest_score, latest_score_value)
            self._set_metric_tile("latest_alerts", str(len(alerts)), min(len(alerts), 100))
            self._set_metric_tile("latest_hints", str(len(hints)), min(len(hints), 100))
            self._set_metric_tile(
                "latest_recommendations", str(len(recommendations)), min(len(recommendations), 100)
            )
            self._set_metric_tile("latest_requests", str(len(requests)), min(len(requests), 100))
            self._set_metric_tile("latest_decisions", str(len(decisions)), min(len(decisions), 100))

            self._populate_health(health)
            self._populate_alerts(alerts)
            self._populate_hints(hints)
            self._populate_recommendations(recommendations)
            self._populate_requests(requests)
            self._populate_decisions(decisions)
            # Populate LLM query history
            try:
                llm_history = self._storage.get_recent_llm_queries(limit=self._max_rows)
            except Exception:
                llm_history = []
            self._populate_llm_history(llm_history)
            # Discovered nodes (agents found on the LAN but not necessarily sending payloads)
            try:
                discovered = self._storage.get_discovered_nodes(limit=self._max_rows)
            except Exception:
                discovered = []
            self._populate_discovered_nodes(discovered)

            # Update charts with latest data
            latest_score_value = int(health[0]["score"] if health else 0)
            self._fleet_chart.add_sample(active_nodes, latest_score_value)
            
            # Extract latest metric values from payloads for per-metric charts
            if payloads:
                payload = payloads[0]
                metrics = payload.get("metrics", {})
                cpu = metrics.get("cpu", {}) if isinstance(metrics, dict) else {}
                gpu = metrics.get("gpu", {}) if isinstance(metrics, dict) else {}
                memory = metrics.get("memory", {}) if isinstance(metrics, dict) else {}
                disk = metrics.get("disk", {}) if isinstance(metrics, dict) else {}

                if isinstance(cpu, dict):
                    self._cpu_chart.add_sample(float(cpu.get("usage_percent", 0.0)))
                if isinstance(gpu, dict) and float(gpu.get("usage_percent", -1.0)) >= 0:
                    self._gpu_chart.add_sample(float(gpu.get("usage_percent", 0.0)))
                if isinstance(memory, dict):
                    self._memory_chart.add_sample(float(memory.get("usage_percent", 0.0)))
                if isinstance(disk, dict):
                    self._disk_chart.add_sample(float(disk.get("root_usage_percent", 0.0)))

            self._status_bar.showMessage(
                f"SQLite: {self._sqlite_path} | Active nodes: {active_nodes} | Latest status: {latest_status} | Latest score: {latest_score}"
            )
        except Exception as exc:  # pragma: no cover - UI safety net
            self._status_bar.showMessage(f"Refresh error: {exc}")

    def _build_metric_tile(self, key: str, title: str) -> QWidget:
        tile = QGroupBox(title)
        tile.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        tile.setMinimumHeight(86)
        tile.setMaximumHeight(86)
        layout = QVBoxLayout(tile)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(4)
        label = QLabel("--")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setObjectName("metricValue")
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setTextVisible(False)
        bar.setFixedHeight(14)
        layout.addWidget(label)
        layout.addWidget(bar)
        self._summary_labels[key] = label
        self._summary_bars[key] = bar
        return tile

    def _build_table(self, headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(30)
        table.horizontalHeader().setMinimumSectionSize(90)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setWordWrap(True)
        table.setFont(QFont("Tahoma", 10))
        table.horizontalHeader().setFont(QFont("Tahoma", 10))
        return table

    def _build_preflight_panel(self) -> QWidget:
        """Build a preflight status panel showing startup checks."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("System Preflight Checks")
        title.setObjectName("preflightTitle")
        title.setStyleSheet("font-weight: bold; font-size: 12pt;")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(4, 4, 4, 4)
        content_layout.setSpacing(6)

        self._preflight_items: list[tuple[QLabel, QLabel]] = []
        preflight_results = self._run_preflight_checks()
        
        for severity, message in preflight_results:
            result_layout = self._create_preflight_item(severity, message)
            content_layout.addLayout(result_layout)

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

        return container

    def _create_preflight_item(self, severity: str, message: str) -> QVBoxLayout:
        """Create a preflight check result item with colored indicator."""
        item_layout = QVBoxLayout()
        item_layout.setContentsMargins(8, 4, 8, 4)
        item_layout.setSpacing(2)

        row_layout = QGridLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        # Color indicator based on severity
        indicator = QLabel("●")
        if severity == "critical":
            indicator.setStyleSheet("color: red; font-size: 14pt;")
            status = "CRITICAL"
        elif severity == "warning":
            indicator.setStyleSheet("color: orange; font-size: 14pt;")
            status = "WARNING"
        else:
            indicator.setStyleSheet("color: green; font-size: 14pt;")
            status = "INFO"

        severity_label = QLabel(status)
        severity_label.setStyleSheet("font-weight: bold; min-width: 70px;")
        message_label = QLabel(message)
        message_label.setWordWrap(True)
        message_label.setStyleSheet("color: #333333;")

        row_layout.addWidget(indicator, 0, 0)
        row_layout.addWidget(severity_label, 0, 1)
        row_layout.addWidget(message_label, 0, 2, 1, -1)

        row_layout.setColumnStretch(2, 1)

        item_layout.addLayout(row_layout)
        return item_layout

    def _run_preflight_checks(self) -> list[tuple[str, str]]:
        """Run preflight checks and return results as (severity, message) tuples."""
        results: list[tuple[str, str]] = []
        
        collector_cfg = self._config.get("collector", {})
        transport_cfg = self._config.get("transport", {})
        sqlite_path = str(collector_cfg.get("sqlite_path", "./data/sentinel.db"))
        data_dir = str(Path(sqlite_path).parent)
        log_dir = "./logs"

        # Check writable directories
        try:
            Path(data_dir).mkdir(parents=True, exist_ok=True)
            test_file = Path(data_dir) / ".sentinel_test"
            test_file.write_text("test")
            test_file.unlink()
            results.append(("info", f"✓ Data directory writable: {data_dir}"))
        except Exception as e:
            results.append(("critical", f"✗ Data directory not writable: {data_dir} ({e})"))

        try:
            Path(log_dir).mkdir(parents=True, exist_ok=True)
            test_file = Path(log_dir) / ".sentinel_test"
            test_file.write_text("test")
            test_file.unlink()
            results.append(("info", f"✓ Log directory writable: {log_dir}"))
        except Exception as e:
            results.append(("critical", f"✗ Log directory not writable: {log_dir} ({e})"))

        # Check dependencies
        for module, package in [("zmq", "pyzmq"), ("msgpack", "msgpack"), ("psutil", "psutil"), ("yaml", "pyyaml")]:
            try:
                __import__(module)
                results.append(("info", f"✓ Module available: {module}"))
            except ImportError:
                results.append(("critical", f"✗ Module not found: {module} (install: pip install {package})"))

        # Check optional capabilities
        def probe_pyqt6() -> str:
            __import__("PyQt6.QtWidgets")
            return "PyQt6 available"
        
        def probe_nvidia() -> str:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            if len(lines) == 1:
                return lines[0]
            return f"{len(lines)} GPUs detected"
        
        def probe_ollama() -> str:
            sock = socket.create_connection(("localhost", 11434), timeout=1)
            sock.close()
            return "Ollama at localhost:11434 reachable"

        for name, probe_fn in [
            ("PyQt6 UI", probe_pyqt6),
            ("NVIDIA GPU", probe_nvidia),
            ("Ollama LLM", probe_ollama),
        ]:
            try:
                result_msg = probe_fn()
                results.append(("info", f"✓ {name}: {result_msg}"))
            except Exception as e:
                results.append(("warning", f"⊘ {name}: not available ({e})"))

        return results

    def _populate_health(self, rows: list[dict[str, Any]]) -> None:
        self._set_table_rows(
            self._health_table,
            [
                [
                    row.get("node_id", "unknown"),
                    row.get("status", "unknown"),
                    str(row.get("score", "")),
                    row.get("timestamp_utc", "unknown"),
                    "; ".join(row.get("reasons", [])),
                ]
                for row in rows
            ],
        )

    def _populate_alerts(self, rows: list[dict[str, Any]]) -> None:
        self._set_table_rows(
            self._alerts_table,
            [
                [
                    row.get("node_id", "unknown"),
                    row.get("severity", "unknown"),
                    row.get("category", "unknown"),
                    row.get("message", ""),
                    row.get("timestamp_utc", "unknown"),
                ]
                for row in rows
            ],
        )

    def _populate_hints(self, rows: list[dict[str, Any]]) -> None:
        self._set_table_rows(
            self._hints_table,
            [
                [
                    row.get("node_id", "unknown"),
                    row.get("category", "unknown"),
                    row.get("confidence", "unknown"),
                    row.get("message", ""),
                    row.get("timestamp_utc", "unknown"),
                ]
                for row in rows
            ],
        )

    def _populate_recommendations(self, rows: list[dict[str, Any]]) -> None:
        self._set_table_rows(
            self._recommendations_table,
            [
                [
                    row.get("node_id", "unknown"),
                    row.get("priority", "unknown"),
                    row.get("category", "unknown"),
                    row.get("title", ""),
                    row.get("timestamp_utc", "unknown"),
                ]
                for row in rows
            ],
        )

    def _populate_requests(self, rows: list[dict[str, Any]]) -> None:
        self._set_table_rows(
            self._requests_table,
            [
                [
                    str(row.get("request_id", "")),
                    row.get("node_id", "unknown"),
                    row.get("action_type", "unknown"),
                    row.get("risk_level", "unknown"),
                    row.get("status", "unknown"),
                    row.get("title", ""),
                ]
                for row in rows
            ],
        )

    def _populate_decisions(self, rows: list[dict[str, Any]]) -> None:
        self._set_table_rows(
            self._decisions_table,
            [
                [
                    str(row.get("request_id", "")),
                    row.get("actor", "unknown"),
                    "yes" if row.get("approved") else "no",
                    row.get("rationale", ""),
                    row.get("timestamp_utc", "unknown"),
                ]
                for row in rows
            ],
        )

    def _populate_discovered_nodes(self, rows: list[dict[str, Any]]) -> None:
        self._set_table_rows(
            self._discovered_table,
            [
                [
                    row.get("node_id", "unknown"),
                    row.get("hostname", "unknown"),
                    row.get("os_name", "unknown"),
                    row.get("platform", "unknown"),
                    row.get("timestamp_utc", "unknown"),
                ]
                for row in rows
            ],
        )

    def _populate_llm_history(self, rows: list[dict[str, Any]]) -> None:
        # Show recent LLM queries with a short response summary
        table = self._llm_history_table
        table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            q = row.get("question", "")
            r = (row.get("response") or "").replace("\n", " ")[:120]
            ts = row.get("timestamp_utc", "")
            table.setItem(i, 0, QTableWidgetItem(q))
            table.setItem(i, 1, QTableWidgetItem(r))
            table.setItem(i, 2, QTableWidgetItem(ts))
        table.resizeColumnsToContents()

    def _rerun_selected_llm_query(self) -> None:
        try:
            sel = self._llm_history_table.selectionModel().selectedRows()
            if not sel:
                self._status_bar.showMessage("No history row selected to re-run")
                return
            row = sel[0].row()
            question_item = self._llm_history_table.item(row, 0)
            if question_item is None:
                self._status_bar.showMessage("Selected row has no question")
                return
            question = question_item.text()
            self._llm_question_input.setText(question)
            self._send_llm_query()
        except Exception as exc:
            self._status_bar.showMessage(f"Re-run error: {exc}")

    def _on_llm_history_context_menu(self, pos: Any) -> None:
        row = self._llm_history_table.rowAt(pos.y())
        if row < 0:
            return
        menu = QMenu(self)
        mark_helpful = menu.addAction("Mark Helpful")
        save_hint = menu.addAction("Save as Root-Cause Hint")
        promote_rec = menu.addAction("Promote to Recommendation")
        action = menu.exec(self._llm_history_table.mapToGlobal(pos))
        if action == mark_helpful:
            self._mark_llm_helpful(row)
        elif action == save_hint:
            self._save_llm_as_hint(row)
        elif action == promote_rec:
            self._promote_llm_to_recommendation(row)

    def _mark_llm_helpful(self, row: int) -> None:
        try:
            q_item = self._llm_history_table.item(row, 0)
            if q_item is None:
                self._status_bar.showMessage("No question found to mark helpful")
                return
            question = q_item.text()
            # Find the query id from storage matching question+timestamp roughly
            history = self._storage.get_recent_llm_queries(limit=200)
            matched = None
            for h in history:
                if h.get("question") == question:
                    matched = h
                    break
            if not matched:
                self._status_bar.showMessage("Could not find query in history to mark")
                return
            self._storage.store_llm_feedback(query_id=matched.get("id"), helpful=True, note="marked helpful", actor="ui")
            self._status_bar.showMessage("Marked query helpful")
            self.refresh()
        except Exception as exc:
            self._status_bar.showMessage(f"Mark helpful error: {exc}")

    def _save_llm_as_hint(self, row: int) -> None:
        try:
            q_item = self._llm_history_table.item(row, 0)
            r_item = self._llm_history_table.item(row, 1)
            if q_item is None or r_item is None:
                self._status_bar.showMessage("Selected row incomplete")
                return
            question = q_item.text()
            response = r_item.text()
            history = self._storage.get_recent_llm_queries(limit=200)
            matched = None
            for h in history:
                if h.get("question") == question:
                    matched = h
                    break
            if not matched:
                self._status_bar.showMessage("Could not find query in history to save")
                return
            hint = {
                "node_id": matched.get("node_id") or "sentinel-llm",
                "category": "llm_saved",
                "confidence": "medium",
                "timestamp_utc": matched.get("timestamp_utc") or "unknown",
                "message": matched.get("response") or response,
                "evidence": {"question": matched.get("question"), "metadata": matched.get("metadata", {})},
            }
            self._storage.store_root_cause_hint(hint)
            self._status_bar.showMessage("Saved LLM response as root-cause hint")
            self.refresh()
        except Exception as exc:
            self._status_bar.showMessage(f"Save hint error: {exc}")

    def _promote_llm_to_recommendation(self, row: int) -> None:
        try:
            q_item = self._llm_history_table.item(row, 0)
            r_item = self._llm_history_table.item(row, 1)
            if q_item is None or r_item is None:
                self._status_bar.showMessage("Selected row incomplete for promotion")
                return
            question = q_item.text()
            response = r_item.text()
            history = self._storage.get_recent_llm_queries(limit=200)
            matched = None
            for h in history:
                if h.get("question") == question:
                    matched = h
                    break
            if not matched:
                self._status_bar.showMessage("Could not find query in history to promote")
                return
            rec = {
                "node_id": matched.get("node_id") or "sentinel-llm",
                "category": "operator_promoted",
                "priority": "medium",
                "timestamp_utc": matched.get("timestamp_utc") or "unknown",
                "title": f"LLM: {matched.get('question')[:80]}",
                "rationale": matched.get("response") or response,
                "suggested_actions": [],
                "evidence": {"question": matched.get("question"), "metadata": matched.get("metadata", {})},
                "execution_mode": "recommendation_only",
            }
            self._storage.store_action_recommendation(rec)
            self._status_bar.showMessage("Promoted LLM response to recommendation")
            self.refresh()
        except Exception as exc:
            self._status_bar.showMessage(f"Promote error: {exc}")

    def _set_table_rows(self, table: QTableWidget, rows: list[list[str]]) -> None:
        table.setRowCount(len(rows))
        for row_index, row_values in enumerate(rows):
            for col_index, value in enumerate(row_values):
                item = QTableWidgetItem(str(value))
                table.setItem(row_index, col_index, item)
        table.resizeColumnsToContents()

    def _set_metric_tile(self, key: str, text: str, value: int) -> None:
        label = self._summary_labels.get(key)
        bar = self._summary_bars.get(key)
        if label is not None:
            label.setText(text)
        if bar is not None:
            bar.setValue(max(0, min(100, int(value))))

    def _on_recommendation_context_menu(self, pos: Any) -> None:
        row = self._recommendations_table.rowAt(pos.y())
        if row < 0:
            return
        menu = QMenu(self)
        action = menu.addAction("Promote to Action Request")
        result = menu.exec(self._recommendations_table.mapToGlobal(pos))
        if result == action:
            self._promote_recommendation(row)

    def _on_request_context_menu(self, pos: Any) -> None:
        row = self._requests_table.rowAt(pos.y())
        if row < 0:
            return
        menu = QMenu(self)
        approve_action = menu.addAction("Approve")
        reject_action = menu.addAction("Reject")
        result = menu.exec(self._requests_table.mapToGlobal(pos))
        if result == approve_action:
            self._approve_request(row, approved=True)
        elif result == reject_action:
            self._approve_request(row, approved=False)

    def _promote_recommendation(self, row: int) -> None:
        try:
            recommendations = self._storage.get_recent_action_recommendations(limit=100)
            if row >= len(recommendations):
                self._status_bar.showMessage("Recommendation not found")
                return

            rec = recommendations[row]
            dialog = PromoteRecommendationDialog(self, rec)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                action_req = self._gate.build_request_from_recommendation(
                    rec,
                    command=dialog.get_command(),
                    action_type=dialog.get_action_type(),
                    risk_level=dialog.get_risk_level(),
                )
                if action_req is None:
                    self._status_bar.showMessage(f"Request rejected (cooldown active for {rec['node_id']})")
                    return

                self._storage.create_action_request(self._gate.to_record(action_req))
                self._status_bar.showMessage(f"Promoted recommendation to action request")
                self.refresh()
        except Exception as exc:  # pragma: no cover
            self._status_bar.showMessage(f"Promotion error: {exc}")

    def _approve_request(self, row: int, approved: bool) -> None:
        try:
            requests = self._storage.get_recent_action_requests(limit=100)
            if row >= len(requests):
                self._status_bar.showMessage("Request not found")
                return

            req = requests[row]
            req_id = req.get("request_id", 0)
            dialog = DecisionDialog(self, req, approved)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                decision = self._gate.approve(
                    req_id, actor=dialog.get_actor(), rationale=dialog.get_rationale()
                ) if approved else self._gate.reject(
                    req_id, actor=dialog.get_actor(), rationale=dialog.get_rationale()
                )
                self._storage.store_approval_decision({
                    "request_id": decision.request_id,
                    "approved": decision.approved,
                    "actor": decision.actor,
                    "timestamp_utc": decision.timestamp_utc,
                    "rationale": decision.rationale,
                })
                execution_record = self._execution_planner.plan_from_request(req, {
                    "approved": decision.approved,
                    "actor": decision.actor,
                    "rationale": decision.rationale,
                })
                if execution_record is not None:
                    self._status_bar.showMessage(
                        f"Request {req_id} {'approved' if approved else 'rejected'}; execution plan queued"
                    )
                else:
                    self._status_bar.showMessage(
                        f"Request {req_id} {'approved' if approved else 'rejected'}"
                    )
                self.refresh()
        except Exception as exc:  # pragma: no cover
            self._status_bar.showMessage(f"Decision error: {exc}")

    def _send_llm_query(self) -> None:
        """Send a question to the LLM query endpoint and display response."""
        question = self._llm_question_input.text().strip()
        if not question:
            self._llm_response.setPlainText("Please enter a question.")
            return

        self._llm_response.setPlainText("Querying LLM...")
        self._llm_question_input.setEnabled(False)

        try:
            # Build request to API
            query_data = json.dumps({"question": question}).encode("utf-8")
            request = Request(
                f"{self._api_url}/llm/query",
                data=query_data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            
            with urlopen(request, timeout=30) as response:
                response_data = json.loads(response.read().decode("utf-8"))
                if response.status == 200:
                    response_text = response_data.get("response", "").strip()
                    if response_text:
                        self._llm_response.setPlainText(response_text)
                    else:
                        self._llm_response.setPlainText(
                            response_data.get(
                                "error",
                                "LLM returned an empty response. Check the configured Ollama model.",
                            )
                        )
                    self._llm_question_input.clear()
                else:
                    self._llm_response.setPlainText(f"API error: {response_data.get('error', 'unknown')}")
        except HTTPError as exc:
            try:
                error_body = exc.read().decode("utf-8")
                error_data = json.loads(error_body)
                self._llm_response.setPlainText(
                    error_data.get("error", f"HTTP {exc.code}: {exc.reason}")
                )
            except Exception:
                self._llm_response.setPlainText(f"HTTP error querying LLM: {exc}")
        except Exception as exc:
            self._llm_response.setPlainText(f"Error querying LLM: {exc}")
            LOGGER.exception("LLM query error: %s", exc)
        finally:
            self._llm_question_input.setEnabled(True)


class PromoteRecommendationDialog(QDialog):
    def __init__(self, parent: Any, recommendation: dict[str, Any]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Promote Recommendation to Action Request")
        self.setGeometry(100, 100, 600, 300)
        self._recommendation = recommendation

        layout = QVBoxLayout(self)

        info_text = f"""
Node: {recommendation.get('node_id', 'unknown')}
Category: {recommendation.get('category', 'unknown')}
Title: {recommendation.get('title', 'unknown')}
Rationale: {recommendation.get('rationale', 'unknown')}
        """.strip()
        layout.addWidget(QLabel(info_text))

        layout.addWidget(QLabel("Action Type:"))
        self._action_type_edit = QLineEdit()
        self._action_type_edit.setText("check_service")
        layout.addWidget(self._action_type_edit)

        layout.addWidget(QLabel("Command (will be reviewed before execution):"))
        self._command_edit = QTextEdit()
        self._command_edit.setPlainText("# Enter command here")
        layout.addWidget(self._command_edit)

        layout.addWidget(QLabel("Risk Level:"))
        self._risk_level_edit = QLineEdit()
        self._risk_level_edit.setText("medium")
        layout.addWidget(self._risk_level_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_action_type(self) -> str:
        return self._action_type_edit.text().strip()

    def get_command(self) -> str:
        return self._command_edit.toPlainText().strip()

    def get_risk_level(self) -> str:
        return self._risk_level_edit.text().strip()


class DecisionDialog(QDialog):
    def __init__(self, parent: Any, request: dict[str, Any], approved: bool) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{'Approve' if approved else 'Reject'} Action Request")
        self.setGeometry(100, 100, 600, 400)
        self._request = request
        self._approved = approved

        layout = QVBoxLayout(self)

        info_text = f"""
Request ID: {request.get('request_id', 'unknown')}
Node: {request.get('node_id', 'unknown')}
Action: {request.get('action_type', 'unknown')}
Risk: {request.get('risk_level', 'unknown')}
Title: {request.get('title', 'unknown')}
Description: {request.get('description', 'unknown')}

Command to {"execute" if approved else "reject"}:
{request.get('command', 'N/A')}
        """.strip()
        layout.addWidget(QLabel(info_text))

        layout.addWidget(QLabel(f"{'Approval' if approved else 'Rejection'} Rationale:"))
        self._rationale_edit = QTextEdit()
        self._rationale_edit.setPlainText("")
        layout.addWidget(self._rationale_edit)

        layout.addWidget(QLabel("Your Name/ID:"))
        self._actor_edit = QLineEdit()
        self._actor_edit.setText("user")
        layout.addWidget(self._actor_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_rationale(self) -> str:
        return self._rationale_edit.toPlainText().strip()

    def get_actor(self) -> str:
        return self._actor_edit.text().strip()


if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    from pathlib import Path
    import yaml

    app = QApplication(sys.argv)
    
    # Load config
    config_path = Path("config/pilot.config.yaml")
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f)
        # Interpolate environment variable placeholders manually
        collector_cfg = config.get("collector", {})
        sqlite_path = collector_cfg.get("sqlite_path", "./data/sentinel-pilot.db")
        # Handle template variable format: ${VAR:default}
        if isinstance(sqlite_path, str) and sqlite_path.startswith("${"):
            # Extract default value from template
            if ":" in sqlite_path:
                default = sqlite_path.split(":")[-1].rstrip("}")
                sqlite_path = default
        collector_cfg["sqlite_path"] = sqlite_path
    else:
        config = {}
    
    window = SentinelMainWindow(config)
    window.show()
    sys.exit(app.exec())
