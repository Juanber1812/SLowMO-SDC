# ui/ui_styles.py
from PyQt6.QtWidgets import QGroupBox

def apply_group_styles(main_window):
    border = "1px solid"
    radius = "8px"
    bg = "#222"

    style_template = f"""
        QGroupBox {{
            border: {border} #888;
            border-radius: {radius};
            margin-top: 10px;
            background: {bg};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 3px 0 3px;
        }}
    """

    for child in main_window.findChildren(QGroupBox):
        child.setStyleSheet(style_template)
