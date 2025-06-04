# -*- coding: utf-8 -*-
"""
Dark Sci-Fi Green Theme
Hacking-style monospaced font, neon green accents
"""

# === Background Colors ===
BACKGROUND         = "#0D110D"  # Very dark green-black
BOX_BACKGROUND     = "#131A13"  # Slightly lighter panel
PLOT_BACKGROUND    = BACKGROUND
STREAM_BACKGROUND  = "#080C08"  # Deepest black-green
SECOND_COLUMN      = "#1A211A"  # Sidebar panel

# === Text Colors ===
TEXT_COLOR         = "#00FF7F"  # Neon spring green
TEXT_SECONDARY     = "#33CC99"  # Muted teal
BOX_TITLE_COLOR    = "#00FF7F"  # Same neon green
LABEL_COLOR        = "#33CC99"  # Muted teal for labels

# === Button Colors ===
BUTTON_COLOR       = "#0A2F0A"  # Dark forest green
BUTTON_HOVER       = "#117711"  # Bright green hover
BUTTON_DISABLED    = "#073007"  # Very dark for disabled
BUTTON_TEXT        = "#00FF7F"  # Neon green text

# === Plot Styling ===
GRID_COLOR         = "#0A1A0A"  # Very dark grid
TICK_COLOR         = "#009933"  # Dark green ticks
PLOT_LINE_PRIMARY  = "#00FF00"  # Pure neon green
PLOT_LINE_SECONDARY= "#33FF99"  # Light mint
PLOT_LINE_ALT      = "#00CC66"  # Teal-green

# === Borders ===
BORDER_COLOR       = "#00CC66"  # Teal border
BORDER_ERROR       = "#FF5555"  # Bright red
BORDER_HIGHLIGHT   = "#00FF00"  # Neon green

# === Fonts ===
FONT_FAMILY        = "Consolas, 'Courier New', monospace"
FONT_SIZE_NORMAL   = 10
FONT_SIZE_LABEL    = 9
FONT_SIZE_TITLE    = 11

# === Semantic Colors ===
ERROR_COLOR        = BORDER_ERROR
SUCCESS_COLOR      = PLOT_LINE_ALT
WARNING_COLOR      = "#CCCC00"  # Amber-yellow

# === Graph Mode Colors ===
GRAPH_MODE_COLORS = {
    "DISTANCE MEASURING MODE":  "#00FF00",  # Neon green
    "SCANNING MODE":     "#33FF99",  # Mint
    "SPIN MODE":   "#00CC66",  # Teal
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
