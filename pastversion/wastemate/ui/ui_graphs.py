# ui/ui_graphs.py

from PyQt6.QtWidgets import (
    QVBoxLayout, QGroupBox, QPushButton, QWidget,
    QHBoxLayout, QComboBox, QLabel
)
from PyQt6.QtCore import Qt

from payload.distance import RelativeDistancePlotter
from payload.relative_angle import RelativeAnglePlotter
from payload.spin import AngularPositionPlotter

def create_graph_section(main_window, graph_modes):
    layout = QVBoxLayout()

    # === Detector Output Group ===
    detector_group = QGroupBox("Detector Output")
    detector_layout = QVBoxLayout()
    main_window.analysed_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
    main_window.analysed_label.setFixedSize(384, 216)
    main_window.analysed_label.setStyleSheet("background: #222; border: 1px solid #888;")
    detector_layout.addWidget(main_window.analysed_label)
    detector_group.setLayout(detector_layout)
    layout.addWidget(detector_group)

    # === Detector Control Button ===
    detector_btn_group = QGroupBox("Detection Control")
    detector_btn_layout = QVBoxLayout()
    main_window.detector_btn = QPushButton("Start Detector")
    main_window.detector_btn.setEnabled(True)
    main_window.detector_btn.clicked.connect(main_window.toggle_detector)
    detector_btn_layout.addWidget(main_window.detector_btn)
    detector_btn_group.setLayout(detector_btn_layout)
    layout.addWidget(detector_btn_group)

    # === Graph Display Section ===
    main_window.graph_display_group = QGroupBox("Graph Display")
    main_window.graph_display_layout = QVBoxLayout()
    main_window.graph_display_placeholder = QWidget()
    placeholder_layout = QVBoxLayout(main_window.graph_display_placeholder)
    placeholder_layout.setContentsMargins(10, 10, 10, 10)
    placeholder_layout.setSpacing(15)

    main_window.select_buttons = {}

    for mode in graph_modes:
        btn = QPushButton(mode)
        btn.setMinimumHeight(60)
        btn.setStyleSheet("""
            QPushButton {
                font-size: 16px;
                background-color: #444;
                color: white;
                border: 2px solid #888;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #666;
            }
        """)
        btn.clicked.connect(lambda _, m=mode: load_graph(main_window, m))
        placeholder_layout.addWidget(btn)
        main_window.select_buttons[mode] = btn

    main_window.graph_display_layout.addWidget(main_window.graph_display_placeholder)
    main_window.graph_display_group.setLayout(main_window.graph_display_layout)
    layout.addWidget(main_window.graph_display_group)

    return layout



def load_graph(main_window, mode):
    main_window.graph_display_placeholder.setParent(None)

    if mode == "Relative Distance":
        graph_widget = RelativeDistancePlotter()
    elif mode == "Relative Angle":
        graph_widget = RelativeAnglePlotter()
    elif mode == "Angular Position":
        graph_widget = AngularPositionPlotter()
    else:
        return

    main_window.shared_start_time = graph_widget.start_time = graph_widget.start_time = main_window.shared_start_time or graph_widget.start_time
    graph_widget.setFixedHeight(230)

    main_window.graph_widget = graph_widget
    main_window.detector_worker.graph_widget = graph_widget
    main_window.graph_display_layout.addWidget(graph_widget)

    # === Control Buttons ===
    btn_layout = QHBoxLayout()

    main_window.record_btn = QPushButton("Record")
    main_window.record_btn.setEnabled(False)

    main_window.duration_dropdown = QComboBox()
    main_window.duration_dropdown.addItems(["5s", "10s", "30s", "60s"])

    btn_layout.addWidget(main_window.record_btn)
    btn_layout.addWidget(main_window.duration_dropdown)

    main_window.exit_graph_btn = QPushButton("← Back")
    main_window.exit_graph_btn.setStyleSheet("""
        QPushButton {
            font-size: 9pt;
            background-color: #222;
            color: white;
            border: 1px solid #888;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #444;
        }
    """)
    main_window.exit_graph_btn.clicked.connect(lambda: exit_graph(main_window))
    btn_layout.addWidget(main_window.exit_graph_btn)

    main_window.graph_display_layout.addLayout(btn_layout)


def exit_graph(main_window):
    if main_window.graph_widget:
        main_window.graph_widget.setParent(None)
        main_window.graph_widget = None

    if main_window.exit_graph_btn:
        main_window.exit_graph_btn.setParent(None)
    if main_window.record_btn:
        main_window.record_btn.setParent(None)
    if main_window.duration_dropdown:
        main_window.duration_dropdown.setParent(None)

    main_window.graph_display_layout.addWidget(main_window.graph_display_placeholder)
