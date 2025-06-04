import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Set up plotting style
plt.style.use('default')
sns.set_palette("husl")

def load_and_analyze_benchmark_data():
    """
    Load and analyze benchmark results from CSV file
    """
    # Load your results CSV - adjust the filename to match your actual file
    csv_file = "results/benchmark_results_full_suite_plus_sustained_v2_extended_20250604_215833.csv"
    
    try:
        df = pd.read_csv(csv_file)
        print(f"Successfully loaded {len(df)} records from {csv_file}")
    except FileNotFoundError:
        print(f"Results CSV not found at {csv_file}. Make sure the file exists.")
        return None
    except Exception as e:
        print(f"Error loading CSV: {e}")
        return None
    
    print("\n=== DATASET OVERVIEW ===")
    print("DataFrame Head:")
    print(df.head())
    print("\nDataFrame Info:")
    df.info()
    print(f"\nDataset shape: {df.shape}")
    print(f"Columns: {list(df.columns)}")
    
    # Check for missing values
    print("\nMissing values per column:")
    missing_data = df.isnull().sum()
    print(missing_data[missing_data > 0])
    
    # Filter out any rows that had critical errors during collection
    df_successful = df[df['status'] == 'Success'].copy()
    print(f"\nSuccessful transactions: {len(df_successful)} out of {len(df)} total")
    
    if len(df_successful) == 0:
        print("No successful transactions found. Cannot perform analysis.")
        return None
    
    # Convert relevant columns to numeric
    numeric_cols = ['nonce', 'block_number', 'gas_used', 
                   'configured_gas_price_gwei', 'effective_gas_price_gwei', 
                   'fee_paid_eth', 'confirmation_time_sec', 
                   'l1_fee_wei', 'l1_fee_eth', 'l1_gas_used', 'l1_gas_price_gwei', 'l1_fee_scalar']
    
    for col in numeric_cols:
        if col in df_successful.columns:
            df_successful[col] = pd.to_numeric(df_successful[col], errors='coerce')
    
    return df_successful

def analyze_by_action_type(df):
    """
    Perform detailed analysis grouped by action type
    """
    print("\n=== ANALYSIS BY ACTION TYPE ===")
    
    if 'action' not in df.columns:
        print("Column 'action' not found in DataFrame. Cannot perform grouped analysis.")
        return
    
    # Get unique action types
    action_types = df['action'].unique()
    print(f"Action types found: {list(action_types)}")
    
    # Comprehensive analysis by action type
    analysis = df.groupby('action').agg({
        'tx_hash': 'count',
        'confirmation_time_sec': ['mean', 'median', 'std', 'min', 'max'],
        'gas_used': ['mean', 'median', 'std', 'min', 'max'],
        'fee_paid_eth': ['mean', 'median', 'std', 'min', 'max'],
        'l1_fee_eth': ['mean', 'median', 'std', 'min', 'max'],
        'l1_gas_used': ['mean', 'median', 'std', 'min', 'max'],
        'effective_gas_price_gwei': ['mean', 'median']
    }).round(6)
    
    # Flatten column names
    analysis.columns = ['_'.join(col).strip() for col in analysis.columns.values]
    analysis = analysis.reset_index()
    
    print("\n--- Comprehensive Statistics per Action Type ---")
    print(analysis.to_string(index=False))
    
    return analysis

def analyze_sustained_load(df):
    """
    Specific analysis for sustained load testing
    """
    print("\n=== SUSTAINED LOAD ANALYSIS ===")
    
    # Look for sustained transactions (could be various patterns)
    sustained_patterns = ['sustained', 'load', 'stress']
    sustained_df = df[df['action'].str.contains('|'.join(sustained_patterns), case=False, na=False)]
    
    if sustained_df.empty:
        print("No sustained load transactions found.")
        return
    
    print(f"Total Sustained Transactions: {len(sustained_df)}")
    
    if 'confirmation_time_sec' in sustained_df.columns:
        conf_times = sustained_df['confirmation_time_sec'].dropna()
        if not conf_times.empty:
            print(f"Average Confirmation Time: {conf_times.mean():.4f}s")
            print(f"Median Confirmation Time: {conf_times.median():.4f}s")
            print(f"95th Percentile Confirmation Time: {conf_times.quantile(0.95):.4f}s")
            print(f"Max Confirmation Time: {conf_times.max():.4f}s")
    
    if 'fee_paid_eth' in sustained_df.columns:
        fees = sustained_df['fee_paid_eth'].dropna()
        if not fees.empty:
            print(f"Average Fee (ETH): {fees.mean():.8f}")
            print(f"Median Fee (ETH): {fees.median():.8f}")
            print(f"Total Fees (ETH): {fees.sum():.8f}")
    
    if 'l1_fee_eth' in sustained_df.columns:
        l1_fees = sustained_df['l1_fee_eth'].dropna()
        if not l1_fees.empty:
            print(f"Average L1 Fee (ETH): {l1_fees.mean():.8f}")
            print(f"Total L1 Fees (ETH): {l1_fees.sum():.8f}")

def analyze_transaction_performance(df):
    """
    Analyze overall transaction performance metrics
    """
    print("\n=== TRANSACTION PERFORMANCE ANALYSIS ===")
    
    # Overall statistics
    print("--- Overall Performance Metrics ---")
    
    if 'confirmation_time_sec' in df.columns:
        conf_times = df['confirmation_time_sec'].dropna()
        if not conf_times.empty:
            print(f"Total Transactions Analyzed: {len(conf_times)}")
            print(f"Average Confirmation Time: {conf_times.mean():.4f}s")
            print(f"Median Confirmation Time: {conf_times.median():.4f}s")
            print(f"95th Percentile: {conf_times.quantile(0.95):.4f}s")
            print(f"99th Percentile: {conf_times.quantile(0.99):.4f}s")
            print(f"Standard Deviation: {conf_times.std():.4f}s")
    
    # Gas usage analysis
    if 'gas_used' in df.columns:
        gas_used = df['gas_used'].dropna()
        if not gas_used.empty:
            print(f"\n--- Gas Usage Statistics ---")
            print(f"Average Gas Used: {gas_used.mean():.0f}")
            print(f"Median Gas Used: {gas_used.median():.0f}")
            print(f"Total Gas Used: {gas_used.sum():.0f}")
    
    # Fee analysis
    if 'fee_paid_eth' in df.columns:
        fees = df['fee_paid_eth'].dropna()
        if not fees.empty:
            print(f"\n--- Fee Analysis ---")
            print(f"Average Fee (ETH): {fees.mean():.8f}")
            print(f"Median Fee (ETH): {fees.median():.8f}")
            print(f"Total Fees Paid (ETH): {fees.sum():.8f}")
    
    # L1 Fee analysis (new data)
    if 'l1_fee_eth' in df.columns:
        l1_fees = df['l1_fee_eth'].dropna()
        if not l1_fees.empty:
            print(f"\n--- L1 Fee Analysis ---")
            print(f"Average L1 Fee (ETH): {l1_fees.mean():.8f}")
            print(f"Median L1 Fee (ETH): {l1_fees.median():.8f}")
            print(f"Total L1 Fees (ETH): {l1_fees.sum():.8f}")
            
            # L1 vs L2 fee comparison
            if 'fee_paid_eth' in df.columns:
                total_fees = df['fee_paid_eth'].dropna()
                if not total_fees.empty:
                    l1_percentage = (l1_fees.sum() / total_fees.sum()) * 100
                    print(f"L1 Fees as % of Total Fees: {l1_percentage:.2f}%")

def create_visualizations(df):
    """
    Create basic visualizations of the data
    """
    print("\n=== CREATING VISUALIZATIONS ===")
    
    # Create output directory for plots
    Path("analysis_plots").mkdir(exist_ok=True)
    
    # 1. Confirmation time distribution by action type
    if 'action' in df.columns and 'confirmation_time_sec' in df.columns:
        plt.figure(figsize=(12, 6))
        df_plot = df.dropna(subset=['confirmation_time_sec'])
        if not df_plot.empty:
            sns.boxplot(data=df_plot, x='action', y='confirmation_time_sec')
            plt.xticks(rotation=45, ha='right')
            plt.title('Confirmation Time Distribution by Action Type')
            plt.ylabel('Confirmation Time (seconds)')
            plt.tight_layout()
            plt.savefig('analysis_plots/confirmation_time_by_action.png', dpi=300, bbox_inches='tight')
            plt.show()
    
    # 2. Gas usage comparison
    if 'action' in df.columns and 'gas_used' in df.columns:
        plt.figure(figsize=(12, 6))
        df_plot = df.dropna(subset=['gas_used'])
        if not df_plot.empty:
            sns.barplot(data=df_plot, x='action', y='gas_used', estimator=np.mean)
            plt.xticks(rotation=45, ha='right')
            plt.title('Average Gas Usage by Action Type')
            plt.ylabel('Gas Used')
            plt.tight_layout()
            plt.savefig('analysis_plots/gas_usage_by_action.png', dpi=300, bbox_inches='tight')
            plt.show()
    
    # 3. Fee comparison (L1 vs Total)
    if 'l1_fee_eth' in df.columns and 'fee_paid_eth' in df.columns:
        plt.figure(figsize=(10, 6))
        df_fees = df[['l1_fee_eth', 'fee_paid_eth']].dropna()
        if not df_fees.empty:
            df_fees['l2_fee_eth'] = df_fees['fee_paid_eth'] - df_fees['l1_fee_eth']
            
            # Create stacked bar chart
            action_fees = df.groupby('action')[['l1_fee_eth', 'fee_paid_eth']].mean()
            action_fees['l2_fee_eth'] = action_fees['fee_paid_eth'] - action_fees['l1_fee_eth']
            
            action_fees[['l1_fee_eth', 'l2_fee_eth']].plot(kind='bar', stacked=True, figsize=(12, 6))
            plt.title('Average L1 vs L2 Fees by Action Type')
            plt.ylabel('Fee (ETH)')
            plt.xticks(rotation=45, ha='right')
            plt.legend(['L1 Fee', 'L2 Fee'])
            plt.tight_layout()
            plt.savefig('analysis_plots/l1_vs_l2_fees.png', dpi=300, bbox_inches='tight')
            plt.show()
    
    print("Visualizations saved to 'analysis_plots/' directory")

def main():
    """
    Main analysis function
    """
    print("=== BENCHMARK RESULTS ANALYSIS ===")
    print("Loading and analyzing benchmark data...\n")
    
    # Load data
    df = load_and_analyze_benchmark_data()
    if df is None:
        return
    
    # Perform various analyses
    analyze_by_action_type(df)
    analyze_sustained_load(df)
    analyze_transaction_performance(df)
    
    # Create visualizations
    try:
        create_visualizations(df)
    except Exception as e:
        print(f"Error creating visualizations: {e}")
        print("Continuing with text-based analysis...")
    
    print("\n=== ANALYSIS COMPLETE ===")
    print("Check the 'analysis_plots/' directory for generated visualizations.")

if __name__ == "__main__":
    main()