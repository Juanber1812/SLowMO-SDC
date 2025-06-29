#!/usr/bin/env python3
"""
Simple Yaw Plotter - Quick visualization of yaw control data
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

def quick_yaw_plot(csv_file):
    """
    Quick plot of yaw data - single function for immediate use
    
    Args:
        csv_file (str): Path to CSV with columns: relative_time, yaw_angle, target_yaw
    """
    
    # Read data
    df = pd.read_csv(csv_file)
    print(f"Loaded {len(df)} data points")
    
    # Calculate error
    df['error'] = df['yaw_angle'] - df['target_yaw']
    
    # Create plot
    plt.figure(figsize=(12, 8))
    
    # Main plot
    plt.subplot(2, 1, 1)
    plt.plot(df['relative_time'], df['yaw_angle'], 'b-', linewidth=2, label='Actual Yaw')
    plt.plot(df['relative_time'], df['target_yaw'], 'r--', linewidth=2, label='Target Yaw')
    plt.ylabel('Yaw Angle (°)')
    plt.title('Yaw Control Performance')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # Error plot
    plt.subplot(2, 1, 2)
    plt.plot(df['relative_time'], df['error'], 'g-', linewidth=2)
    plt.axhline(y=0, color='k', linestyle='-', alpha=0.5)
    plt.xlabel('Time (s)')
    plt.ylabel('Error (°)')
    plt.title('Yaw Error')
    plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # Print stats
    rms_error = np.sqrt(np.mean(df['error']**2))
    max_error = np.abs(df['error']).max()
    print(f"RMS Error: {rms_error:.2f}°")
    print(f"Max Error: {max_error:.2f}°")
    print(f"Duration: {df['relative_time'].max():.1f}s")
    
    plt.show()
    return df

# Example usage
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Use provided file
        csv_file = sys.argv[1]
        quick_yaw_plot(csv_file)
    else:
        # Look for yaw data files
        import os
        yaw_files = [f for f in os.listdir('.') if f.endswith('.csv')]
        
        if yaw_files:
            print("Available CSV files:")
            for i, f in enumerate(yaw_files):
                print(f"  {i+1}. {f}")
            
            try:
                choice = int(input("Select file number: ")) - 1
                if 0 <= choice < len(yaw_files):
                    quick_yaw_plot(yaw_files[choice])
            except:
                print("Invalid selection")
        else:
            print("No CSV files found. Usage: python yaw_plotter_simple.py <csv_file>")
