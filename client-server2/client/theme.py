# === Status Box Colors ===
STATUS_NOMINAL_COLOR   = "#00FF66"  # Bright Green for Nominal
STATUS_WARNING_COLOR   = "#FFD700"  # Gold/Yellow for Warning
STATUS_ERROR_COLOR     = "#FF3333"  # Bright Red for Error
# -*- coding: utf-8 -*-
"""
Electric Blue / Cyber UI Theme
Intense electric blues, black backgrounds, high contrast, energetic.
Inspired by Tron or cyberpunk games.
"""

# === Background Colors ===
BACKGROUND         = "#000000"  # Pure Black
BOX_BACKGROUND     = "#050A1F"  # Very Dark Blue
PLOT_BACKGROUND    = BACKGROUND
STREAM_BACKGROUND  = "#000510"  # Deepest Blue-Black
SECOND_COLUMN      = "#1E2130"  # Dark Blue for sidebars

# === Text Colors ===
TEXT_COLOR         = "#00FFFF"  # Electric Cyan
TEXT_SECONDARY     = "#FFFFFF"  # Lighter Sky Blue
BOX_TITLE_COLOR    = "#00FFFF"  # Electric Cyan
LABEL_COLOR        = "#FFFFFF"  # Lighter Sky Blue for labels

# === Button Colors ===
BUTTON_COLOR       = "#00224D"  # Dark Navy Blue
BUTTON_HOVER       = "#00BFFF"  # Deep Sky Blue (Bright Blue Hover)
BUTTON_DISABLED    = "#001126"  # Very Dark Blue for disabled
BUTTON_TEXT        = "#FFFFFF"  # White text for contrast on dark buttons

# === Plot Styling ===
GRID_COLOR         = "#001A33"  # Very Dark Blue Grid
TICK_COLOR         = "#007FFF"  # Azure Blue Ticks
PLOT_LINE_PRIMARY  = "#00FFFF"  # Electric Cyan
PLOT_LINE_SECONDARY= "#007FFF"  # Azure Blue
PLOT_LINE_ALT      = "#33FFDD"  # Bright Turquoise

# === Borders ===
BORDER_COLOR       = "#007FFF"  # Azure Blue Border
BORDER_ERROR       = "#FF3333"  # Bright Red (Standard for error)
BORDER_HIGHLIGHT   = "#00FFFF"  # Electric Cyan Highlight

# === Fonts ===
FONT_FAMILY        = "Consolas, 'Courier New', monospace" # Keeping font for cyber feel
FONT_SIZE_NORMAL   = 8
FONT_SIZE_LABEL    = 9
FONT_SIZE_TITLE    = 11

# === Semantic Colors ===
ERROR_COLOR        = BORDER_ERROR
SUCCESS_COLOR      = PLOT_LINE_ALT  # Bright Turquoise
WARNING_COLOR      = "#FFD700"  # Gold / Bright Yellow for warning

# === Graph Mode Colors ===
GRAPH_MODE_COLORS = {
    "DISTANCE MEASURING MODE":  "#00FFFF",  # Electric Cyan
    "SCANNING MODE":     "#00BFFF",  # Deep Sky Blue
    "SPIN MODE":   "#33FFDD",  # Bright Turquoise
}

# === Layout & Border Metrics ===
BORDER_WIDTH       = 1
BORDER_RADIUS      = 4
WIDGET_SPACING     = 6
WIDGET_MARGIN      = 8

PADDING_SMALL      = 4
PADDING_NORMAL     = 8
PADDING_LARGE      = 12

BUTTON_HEIGHT      = 32
STREAM_ASPECT_RATIO= (16, 9)
STREAM_WIDTH       = 640
STREAM_HEIGHT      = 360
