#!/usr/bin/env python3
"""
Yaw Angle Plotter
Plots relative_time vs yaw_angle and target_yaw for ADCS performance analysis
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import argparse
import os
from datetime import datetime

def plot_yaw_data(csv_file, output_file=None, show_plot=True):
    """
    Plot yaw angle data from CSV file
    
    Args:
        csv_file (str): Path to CSV file with columns: relative_time, yaw_angle, target_yaw
        output_file (str): Optional path to save the plot
        show_plot (bool): Whether to display the plot
    """
    
    # Read CSV data
    try:
        df = pd.read_csv(csv_file)
        print(f"Loaded {len(df)} data points from {csv_file}")
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return
    
    # Verify required columns exist
    required_cols = ['relative_time', 'yaw_angle', 'target_yaw']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"Error: Missing columns in CSV: {missing_cols}")
        print(f"Available columns: {list(df.columns)}")
        return
    
    # Calculate error
    df['yaw_error'] = df['yaw_angle'] - df['target_yaw']
    
    # Create figure with subplots
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10))
    fig.suptitle('Yaw Control Performance Analysis', fontsize=16, fontweight='bold')
    
    # Plot 1: Yaw angle vs target
    ax1.plot(df['relative_time'], df['yaw_angle'], 'b-', linewidth=2, label='Actual Yaw', alpha=0.8)
    ax1.plot(df['relative_time'], df['target_yaw'], 'r--', linewidth=2, label='Target Yaw', alpha=0.8)
    ax1.set_ylabel('Yaw Angle (°)', fontsize=12)
    ax1.set_title('Yaw Angle Tracking', fontsize=14)
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim(df['relative_time'].min(), df['relative_time'].max())
    
    # Plot 2: Yaw error over time
    ax2.plot(df['relative_time'], df['yaw_error'], 'g-', linewidth=2, label='Yaw Error', alpha=0.8)
    ax2.axhline(y=0, color='k', linestyle='-', alpha=0.5)
    ax2.set_ylabel('Yaw Error (°)', fontsize=12)
    ax2.set_title('Yaw Tracking Error', fontsize=14)
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim(df['relative_time'].min(), df['relative_time'].max())
    
    # Plot 3: Combined overlay with error bands
    ax3.plot(df['relative_time'], df['yaw_angle'], 'b-', linewidth=2, label='Actual Yaw', alpha=0.8)
    ax3.plot(df['relative_time'], df['target_yaw'], 'r--', linewidth=2, label='Target Yaw', alpha=0.8)
    
    # Add error tolerance bands (±1°, ±5°)
    ax3.fill_between(df['relative_time'], 
                     df['target_yaw'] - 1, df['target_yaw'] + 1, 
                     alpha=0.2, color='green', label='±1° tolerance')
    ax3.fill_between(df['relative_time'], 
                     df['target_yaw'] - 5, df['target_yaw'] + 5, 
                     alpha=0.1, color='orange', label='±5° tolerance')
    
    ax3.set_xlabel('Relative Time (s)', fontsize=12)
    ax3.set_ylabel('Yaw Angle (°)', fontsize=12)
    ax3.set_title('Yaw Control with Tolerance Bands', fontsize=14)
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    ax3.set_xlim(df['relative_time'].min(), df['relative_time'].max())
    
    # Adjust layout
    plt.tight_layout()
    
    # Calculate and display statistics
    rms_error = np.sqrt(np.mean(df['yaw_error']**2))
    max_error = np.abs(df['yaw_error']).max()
    mean_error = df['yaw_error'].mean()
    std_error = df['yaw_error'].std()
    
    # Add statistics text box
    stats_text = f"""Statistics:
RMS Error: {rms_error:.2f}°
Max Error: {max_error:.2f}°
Mean Error: {mean_error:.2f}°
Std Error: {std_error:.2f}°
Data Points: {len(df)}
Duration: {df['relative_time'].max():.1f}s"""
    
    fig.text(0.02, 0.02, stats_text, fontsize=10, 
             bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgray", alpha=0.8))
    
    # Save plot if requested
    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Plot saved to: {output_file}")
    
    # Show plot if requested
    if show_plot:
        plt.show()
    
    # Print statistics
    print("\n" + "="*50)
    print("YAW CONTROL PERFORMANCE STATISTICS")
    print("="*50)
    print(f"RMS Error:      {rms_error:.3f}°")
    print(f"Max Error:      {max_error:.3f}°")
    print(f"Mean Error:     {mean_error:.3f}°")
    print(f"Std Error:      {std_error:.3f}°")
    print(f"Data Points:    {len(df)}")
    print(f"Duration:       {df['relative_time'].max():.1f}s")
    print(f"Sample Rate:    {len(df)/df['relative_time'].max():.1f} Hz")
    
    # Settling time analysis (time to reach ±1° tolerance)
    within_1deg = np.abs(df['yaw_error']) <= 1.0
    if within_1deg.any():
        first_within_1deg = df[within_1deg]['relative_time'].iloc[0]
        print(f"Settling Time:  {first_within_1deg:.1f}s (±1° tolerance)")
    else:
        print("Settling Time:  Not achieved (±1° tolerance)")
    
    return df

def plot_live_yaw_data(csv_file, update_interval=1.0):
    """
    Plot yaw data with live updates as new data is added to CSV
    
    Args:
        csv_file (str): Path to CSV file to monitor
        update_interval (float): Update interval in seconds
    """
    plt.ion()  # Turn on interactive mode
    fig, ax = plt.subplots(figsize=(12, 6))
    
    last_size = 0
    
    while True:
        try:
            # Check if file exists and has new data
            if os.path.exists(csv_file):
                current_size = os.path.getsize(csv_file)
                if current_size != last_size:
                    # Read updated data
                    df = pd.read_csv(csv_file)
                    
                    # Clear and replot
                    ax.clear()
                    ax.plot(df['relative_time'], df['yaw_angle'], 'b-', 
                           linewidth=2, label='Actual Yaw', alpha=0.8)
                    ax.plot(df['relative_time'], df['target_yaw'], 'r--', 
                           linewidth=2, label='Target Yaw', alpha=0.8)
                    
                    ax.set_xlabel('Relative Time (s)')
                    ax.set_ylabel('Yaw Angle (°)')
                    ax.set_title(f'Live Yaw Tracking ({len(df)} points)')
                    ax.legend()
                    ax.grid(True, alpha=0.3)
                    
                    plt.draw()
                    plt.pause(0.1)
                    last_size = current_size
            
            plt.pause(update_interval)
            
        except KeyboardInterrupt:
            print("\nLive plotting stopped.")
            break
        except Exception as e:
            print(f"Error in live plotting: {e}")
            plt.pause(update_interval)
    
    plt.ioff()

def main():
    parser = argparse.ArgumentParser(description='Plot yaw angle data from CSV file')
    parser.add_argument('csv_file', help='Path to CSV file with yaw data')
    parser.add_argument('--output', '-o', help='Output file for saving plot')
    parser.add_argument('--no-show', action='store_true', help='Don\'t display plot')
    parser.add_argument('--live', action='store_true', help='Live plotting mode')
    parser.add_argument('--update-interval', type=float, default=1.0, 
                       help='Update interval for live mode (seconds)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.csv_file):
        print(f"Error: CSV file not found: {args.csv_file}")
        return
    
    if args.live:
        print(f"Starting live plotting of {args.csv_file}")
        print("Press Ctrl+C to stop...")
        plot_live_yaw_data(args.csv_file, args.update_interval)
    else:
        plot_yaw_data(args.csv_file, args.output, not args.no_show)

if __name__ == "__main__":
    # If run without arguments, look for yaw data files in current directory
    import sys
    if len(sys.argv) == 1:
        # Look for CSV files with yaw data
        yaw_files = []
        for file in os.listdir('.'):
            if file.endswith('.csv'):
                try:
                    df = pd.read_csv(file, nrows=1)
                    if all(col in df.columns for col in ['relative_time', 'yaw_angle', 'target_yaw']):
                        yaw_files.append(file)
                except:
                    continue
        
        if yaw_files:
            print("Found yaw data files:")
            for i, file in enumerate(yaw_files):
                print(f"  {i+1}. {file}")
            
            try:
                choice = int(input(f"\nSelect file (1-{len(yaw_files)}): ")) - 1
                if 0 <= choice < len(yaw_files):
                    plot_yaw_data(yaw_files[choice])
                else:
                    print("Invalid selection")
            except (ValueError, KeyboardInterrupt):
                print("\nExiting...")
        else:
            print("No CSV files with yaw data found in current directory.")
            print(f"Usage: python {sys.argv[0]} <csv_file>")
    else:
        main()
