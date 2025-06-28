#!/usr/bin/env python3
"""
IMU Drift Analysis Tool
Analyzes CSV log files from the MPU6050 to calculate drift rates and stability
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import argparse
import os
from datetime import datetime

class DriftAnalyzer:
    def __init__(self, csv_file):
        self.csv_file = csv_file
        self.data = None
        
    def load_data(self):
        """Load CSV data and process timestamps"""
        try:
            self.data = pd.read_csv(self.csv_file)
            self.data['timestamp'] = pd.to_datetime(self.data['timestamp'])
            
            # Calculate time differences from start
            start_time = self.data['timestamp'].iloc[0]
            self.data['elapsed_seconds'] = (self.data['timestamp'] - start_time).dt.total_seconds()
            
            print(f"Loaded {len(self.data)} data points")
            print(f"Data collection period: {self.data['elapsed_seconds'].iloc[-1]:.1f} seconds")
            print(f"Average sample rate: {len(self.data) / self.data['elapsed_seconds'].iloc[-1]:.1f} Hz")
            
            return True
            
        except Exception as e:
            print(f"Error loading data: {e}")
            return False
    
    def calculate_drift_rates(self):
        """Calculate drift rates for each axis"""
        if self.data is None:
            print("No data loaded!")
            return None
        
        # Use linear regression to find drift rates (degrees per second)
        time_seconds = self.data['elapsed_seconds'].values
        
        results = {}
        
        for axis in ['pitch', 'roll', 'yaw']:
            angles = self.data[axis].values
            
            # Linear regression: angle = drift_rate * time + initial_angle
            coeffs = np.polyfit(time_seconds, angles, 1)
            drift_rate = coeffs[0]  # degrees per second
            initial_angle = coeffs[1]  # y-intercept
            
            # Calculate R-squared for goodness of fit
            predicted = np.polyval(coeffs, time_seconds)
            ss_res = np.sum((angles - predicted) ** 2)
            ss_tot = np.sum((angles - np.mean(angles)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
            
            # Calculate standard deviation of residuals (stability)
            residuals = angles - predicted
            stability = np.std(residuals)
            
            results[axis] = {
                'drift_rate_deg_per_sec': drift_rate,
                'drift_rate_deg_per_min': drift_rate * 60,
                'drift_rate_deg_per_hour': drift_rate * 3600,
                'initial_angle': initial_angle,
                'r_squared': r_squared,
                'stability_std_dev': stability,
                'angle_range': np.max(angles) - np.min(angles)
            }
            
        return results
    
    def print_analysis(self, results):
        """Print detailed drift analysis"""
        print("\n" + "=" * 80)
        print("IMU DRIFT ANALYSIS RESULTS")
        print("=" * 80)
        
        for axis, data in results.items():
            print(f"\n{axis.upper()} AXIS:")
            print(f"  Drift Rate: {data['drift_rate_deg_per_sec']:.6f} °/sec")
            print(f"              {data['drift_rate_deg_per_min']:.4f} °/min")
            print(f"              {data['drift_rate_deg_per_hour']:.2f} °/hour")
            print(f"  Initial Angle: {data['initial_angle']:.3f}°")
            print(f"  Angle Range: {data['angle_range']:.3f}° (min to max)")
            print(f"  Stability (σ): {data['stability_std_dev']:.3f}° (standard deviation)")
            print(f"  Linearity (R²): {data['r_squared']:.4f} (1.0 = perfect linear drift)")
            
            # Interpret the results
            if abs(data['drift_rate_deg_per_hour']) < 0.5:
                print(f"  Assessment: EXCELLENT drift performance")
            elif abs(data['drift_rate_deg_per_hour']) < 2.0:
                print(f"  Assessment: GOOD drift performance")
            elif abs(data['drift_rate_deg_per_hour']) < 10.0:
                print(f"  Assessment: MODERATE drift (may need compensation)")
            else:
                print(f"  Assessment: HIGH drift (compensation recommended)")
    
    def plot_data(self, results, save_plot=False):
        """Plot the IMU data with drift analysis"""
        if self.data is None:
            print("No data to plot!")
            return
        
        fig, axes = plt.subplots(3, 1, figsize=(12, 10))
        fig.suptitle(f'IMU Drift Analysis - {os.path.basename(self.csv_file)}', fontsize=14)
        
        axes_names = ['pitch', 'roll', 'yaw']
        colors = ['red', 'green', 'blue']
        
        for i, (axis, color) in enumerate(zip(axes_names, colors)):
            ax = axes[i]
            
            # Plot raw data
            ax.plot(self.data['elapsed_seconds'], self.data[axis], 
                   color=color, alpha=0.7, linewidth=1, label=f'{axis.title()} Data')
            
            # Plot drift line
            time_seconds = self.data['elapsed_seconds'].values
            drift_rate = results[axis]['drift_rate_deg_per_sec']
            initial_angle = results[axis]['initial_angle']
            drift_line = drift_rate * time_seconds + initial_angle
            
            ax.plot(time_seconds, drift_line, 
                   color='black', linewidth=2, linestyle='--', 
                   label=f'Drift: {results[axis]["drift_rate_deg_per_hour"]:.2f} °/h')
            
            ax.set_ylabel(f'{axis.title()} (degrees)')
            ax.set_xlabel('Time (seconds)' if i == 2 else '')
            ax.grid(True, alpha=0.3)
            ax.legend()
            
            # Add text box with drift info
            textstr = f'Drift: {results[axis]["drift_rate_deg_per_hour"]:.2f} °/h\nStability: ±{results[axis]["stability_std_dev"]:.3f}°'
            props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
            ax.text(0.02, 0.98, textstr, transform=ax.transAxes, fontsize=9,
                   verticalalignment='top', bbox=props)
        
        plt.tight_layout()
        
        if save_plot:
            plot_filename = self.csv_file.replace('.csv', '_drift_analysis.png')
            plt.savefig(plot_filename, dpi=300, bbox_inches='tight')
            print(f"\nPlot saved as: {plot_filename}")
        
        plt.show()
    
    def analyze(self, show_plot=True, save_plot=False):
        """Complete analysis workflow"""
        if not self.load_data():
            return False
        
        results = self.calculate_drift_rates()
        if results is None:
            return False
        
        self.print_analysis(results)
        
        if show_plot:
            try:
                self.plot_data(results, save_plot)
            except ImportError:
                print("\nNote: matplotlib not available for plotting")
            except Exception as e:
                print(f"\nError creating plot: {e}")
        
        return True

def main():
    parser = argparse.ArgumentParser(description='Analyze IMU drift from CSV log files')
    parser.add_argument('csv_file', help='Path to CSV file from MPU6050 logging')
    parser.add_argument('--no-plot', action='store_true', help='Skip plotting (text analysis only)')
    parser.add_argument('--save-plot', action='store_true', help='Save plot as PNG file')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.csv_file):
        print(f"Error: File '{args.csv_file}' not found!")
        return 1
    
    analyzer = DriftAnalyzer(args.csv_file)
    success = analyzer.analyze(show_plot=not args.no_plot, save_plot=args.save_plot)
    
    return 0 if success else 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
