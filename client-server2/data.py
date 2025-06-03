import os
import re
import numpy as np
import matplotlib.pyplot as plt
import math # For math.ceil

CALIBRATION_DIR = os.path.join("client", "calibrations") # Changed line
FILENAME_PATTERN = re.compile(r"calibration_(\d+)x(\d+)\.npz")

def parse_resolution_from_filename(filename):
    """Extracts (width, height) from a filename like 'calibration_1920x1080.npz'."""
    match = FILENAME_PATTERN.match(filename)
    if match:
        width = int(match.group(1))
        height = int(match.group(2))
        return width, height
    return None

def load_calibration_data(directory):
    """Loads calibration data from .npz files in the specified directory."""
    calibration_params = []
    if not os.path.isdir(directory):
        print(f"Error: Directory '{directory}' not found.")
        return calibration_params

    for filename in sorted(os.listdir(directory)): # Sort for consistent plot order
        if filename.endswith(".npz"):
            resolution = parse_resolution_from_filename(filename)
            if resolution:
                filepath = os.path.join(directory, filename)
                try:
                    data = np.load(filepath)
                    if 'mtx' in data and 'dist' in data:
                        mtx = data['mtx']
                        dist = data['dist'].ravel() # Ensure it's a flat array
                        dist_coeffs = {
                            'k1': dist[0] if len(dist) > 0 else 0,
                            'k2': dist[1] if len(dist) > 1 else 0,
                            'p1': dist[2] if len(dist) > 2 else 0,
                            'p2': dist[3] if len(dist) > 3 else 0,
                            'k3': dist[4] if len(dist) > 4 else 0,
                        }
                        calibration_params.append({
                            "filename": filename,
                            "width": resolution[0],
                            "height": resolution[1],
                            "fx": mtx[0, 0],
                            "fy": mtx[1, 1],
                            "cx": mtx[0, 2],
                            "cy": mtx[1, 2],
                            **dist_coeffs
                        })
                    else:
                        print(f"Warning: 'mtx' or 'dist' not found in {filename}")
                except Exception as e:
                    print(f"Error loading or parsing {filename}: {e}")
            else:
                print(f"Warning: Could not parse resolution from {filename}")
    
    calibration_params.sort(key=lambda p: (p["width"], p["height"]))
    return calibration_params

def plot_trends(params):
    """Plots trends of calibration parameters against resolution width.
    Similar parameters are grouped into the same plot."""
    if not params:
        print("No calibration data to plot.")
        return

    widths = np.array([p["width"] for p in params])
    heights = np.array([p["height"] for p in params]) 

    # Prepare all data, including normalized values
    plot_data = {key: np.array([p[key] for p in params]) for key in params[0] if key not in ['filename', 'width', 'height']}
    plot_data["cx_normalized"] = plot_data["cx"] / widths
    plot_data["cy_normalized"] = plot_data["cy"] / heights

    # Define how parameters are grouped into plots
    # Each dict defines one plot:
    #   - keys: list of parameter names (from plot_data) to include in this plot
    #   - title_suffix: string to append to "Trend for ... vs. Image Width"
    #   - ylabel: label for the y-axis
    plot_definitions = [
        {"keys": ["fx", "fy"], "title_suffix": "Focal Lengths (fx, fy)", "ylabel": "Focal Length (pixels)"},
        {"keys": ["cx", "cy"], "title_suffix": "Principal Point (cx, cy)", "ylabel": "Principal Point (pixels)"},
        {"keys": ["cx_normalized", "cy_normalized"], "title_suffix": "Normalized Principal Point", "ylabel": "Normalized Value (coord/dimension)"},
        {"keys": ["k1", "k2", "k3"], "title_suffix": "Radial Distortion (k1, k2, k3)", "ylabel": "Distortion Coefficient"},
        {"keys": ["p1", "p2"], "title_suffix": "Tangential Distortion (p1, p2)", "ylabel": "Distortion Coefficient"}
    ]

    individual_fig_width_inches = 9
    individual_fig_height_inches = 6
    
    # Colors for lines within the same plot (up to 10 lines)
    # If a group has more keys, this color list would need to be extended or use a colormap.
    intra_plot_colors = plt.cm.get_cmap('tab10').colors 

    for definition_idx, definition in enumerate(plot_definitions):
        fig, ax = plt.subplots(figsize=(individual_fig_width_inches, individual_fig_height_inches))
        
        fig.suptitle(f"Trend for {definition['title_suffix']} vs. Image Width", fontsize=16)
        ax.set_xlabel("Image Width (pixels)", fontsize=13)
        ax.set_ylabel(definition['ylabel'], fontsize=13)
        ax.grid(True, linestyle=':', alpha=0.7)
        ax.tick_params(axis='both', which='major', labelsize=12)

        # Store min/max y values for potential ylim adjustment (e.g., for normalized plots)
        current_plot_y_min = float('inf')
        current_plot_y_max = float('-inf')
        is_normalized_plot = False

        for key_idx, key in enumerate(definition['keys']):
            if key not in plot_data:
                print(f"Warning: Key '{key}' not found in plot_data. Skipping.")
                continue

            y_values = plot_data[key]
            current_line_color = intra_plot_colors[key_idx % len(intra_plot_colors)]

            ax.scatter(widths, y_values, label=key, color=current_line_color, s=70, alpha=0.8, edgecolors='k', linewidth=0.5)

            # Update min/max for ylim adjustment
            current_plot_y_min = min(current_plot_y_min, np.min(y_values))
            current_plot_y_max = max(current_plot_y_max, np.max(y_values))

            # Annotate points for the current line
            for j, p_item in enumerate(params):
                ax.annotate(f"{p_item['width']}x{p_item['height']}", (widths[j], y_values[j]), 
                            textcoords="offset points", xytext=(0,10), ha='center', fontsize=9, alpha=0.85,
                            bbox=dict(boxstyle="round,pad=0.3", fc=current_line_color, alpha=0.2, ec='none'))

            # Special lines or y-limits based on the key
            if key == "cx":
                ax.plot(widths, widths / 2, color='dimgray', linestyle='--', alpha=0.7, label="W/2 (ideal for cx)" if key_idx == 0 else "_nolegend_")
            elif key == "cy": # Assuming ideal cy is H/2, which is not directly plotted against widths.
                pass # No special line for cy vs width directly, unless H is constant or related to W.
            elif key == "cx_normalized" or key == "cy_normalized":
                is_normalized_plot = True
                ax.axhline(0.5, color='dimgray', linestyle='--', alpha=0.7, label="Ideal 0.5" if key_idx == 0 else "_nolegend_")
        
        if is_normalized_plot:
            padding = 0.2 * (current_plot_y_max - current_plot_y_min) if (current_plot_y_max - current_plot_y_min) > 0.01 else 0.15
            ax.set_ylim(min(0.0, current_plot_y_min - padding) - 0.05, max(1.0, current_plot_y_max + padding) + 0.05)

        ax.legend(fontsize=11)
        plt.tight_layout(rect=[0, 0, 1, 0.95]) # Adjust rect to make space for suptitle

    plt.show()

if __name__ == "__main__":
    print(f"Looking for calibration files in ./{CALIBRATION_DIR}")
    calibration_data = load_calibration_data(CALIBRATION_DIR)
    if calibration_data:
        print(f"Found and processed {len(calibration_data)} calibration files.")
        for param_set in calibration_data:
            details = [f"{k}={v:.3f}" for k, v in param_set.items() if k not in ['filename', 'width', 'height']]
            print(f"  {param_set['filename']}: W={param_set['width']}, H={param_set['height']}, " + ", ".join(details))
        plot_trends(calibration_data)
    else:
        print("No valid calibration files found or processed.")
