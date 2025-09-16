import pandas as pd
import numpy as np
from scipy.optimize import curve_fit
from typing import List, Dict, Tuple
from enum import Enum

class DeclineModel(Enum):
    """Enumeration of available decline curve models."""
    EXPONENTIAL = "exponential"
    HYPERBOLIC = "hyperbolic"
    HARMONIC = "harmonic"

# === Decline Model Functions ===
def exponential_decline(t, q_i, D_i):
    """
    Exponential decline model.
    
    Parameters:
        t (array): Time points
        q_i (float): Initial rate
        D_i (float): Initial decline rate
    """
    return q_i * np.exp(-D_i * t)

def hyperbolic_decline(t, q_i, D_i, b):
    """
    Hyperbolic decline model.
    
    Parameters:
        t (array): Time points
        q_i (float): Initial rate
        D_i (float): Initial decline rate
        b (float): Hyperbolic exponent
    """
    safe_term = 1 + b * D_i * t
    return q_i / (safe_term)**(1/b)

def harmonic_decline(t, q_i, D_i):
    """
    Harmonic decline model (special case of hyperbolic where b=1).
    
    Parameters:
        t (array): Time points
        q_i (float): Initial rate
        D_i (float): Initial decline rate
    """
    return q_i / (1 + D_i * t)

# === Data Preprocessing Functions ===
def merge_production_data_from_memory(dataframes: List[pd.DataFrame]) -> pd.DataFrame:
    """Merge production data from multiple DataFrames in memory."""
    try:
        if len(dataframes) == 1:
            return dataframes[0]
        
        # Check column consistency
        base_columns = list(dataframes[0].columns)
        
        for i, df in enumerate(dataframes[1:], 1):
            if list(df.columns) != base_columns:
                print(f"Warning: Column names in DataFrame {i+1} don't match. Adjusting...")
                df.columns = base_columns
        
        merged_df = pd.concat(dataframes, ignore_index=True)
        return merged_df
        
    except Exception as e:
        raise Exception(f"Error merging production data: {str(e)}")

def identify_outliers(df: pd.DataFrame, columns: List[str], multiplier: float = 1.5) -> Dict[str, Dict[str, any]]:
    """
    Identify outliers using the IQR method for specified columns.
    
    Parameters:
        df (DataFrame): Input data
        columns (list): Columns to check for outliers
        multiplier (float): IQR multiplier for outlier detection
    """
    outlier_info = {}
    
    for col in columns:
        if col in df.columns:
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1
            
            lower_bound = Q1 - multiplier * IQR
            upper_bound = Q3 + multiplier * IQR
            
            outliers = df[(df[col] < lower_bound) | (df[col] > upper_bound)][col]
            
            outlier_info[col] = {
                'Q1': Q1, 'Q3': Q3, 'IQR': IQR,
                'lower_bound': lower_bound, 'upper_bound': upper_bound,
                'outliers': outliers
            }
    return outlier_info

def handle_outliers_programmatic(df: pd.DataFrame, columns: List[str], 
                                method: str = "remove", replacement: str = "mean") -> pd.DataFrame:
    """
    Handle outliers programmatically without user input.
    
    Parameters:
        df: DataFrame to process
        columns: List of columns to check for outliers
        method: "remove", "flag", or "replace"
        replacement: "mean" or "median" (used if method is "replace")
    """
    df = df.copy()
    outlier_info = identify_outliers(df, columns)
    
    for col, info in outlier_info.items():
        lower_bound = info['lower_bound']
        upper_bound = info['upper_bound']
        
        if method == "remove":
            # Remove outliers
            df = df[(df[col] >= lower_bound) & (df[col] <= upper_bound)]
        elif method == "flag":
            # Flag outliers
            df[f'{col}_is_outlier'] = (df[col] < lower_bound) | (df[col] > upper_bound)
        elif method == "replace":
            # Replace outliers with mean or median
            if replacement == "mean":
                replacement_value = df[col].mean()
            elif replacement == "median":
                replacement_value = df[col].median()
            else:
                raise ValueError("replacement must be 'mean' or 'median'")
            
            df.loc[df[col] < lower_bound, col] = replacement_value
            df.loc[df[col] > upper_bound, col] = replacement_value
    
    return df

def normalize_time(data: pd.DataFrame) -> pd.DataFrame:
    """Normalize production time by resetting month counter per well."""
    grouped = data.groupby('UWI', group_keys=False)

    def reset_time(group):
        group = group.copy()
        group['Month'] = np.nan
        active_production = group[group['Avg Dly Oil (m3/d)'] > 0]
        if len(active_production) > 0:
            active_production['Month'] = range(1, len(active_production) + 1)
            group.update(active_production)
        return group

    normalized_data = grouped.apply(reset_time)
    return normalized_data

# === Model Fitting Functions ===
def fit_decline_model(t_data: np.ndarray, q_data: np.ndarray, q_i: float, model: DeclineModel) -> Tuple[tuple, float]:
    """Fit decline curve model and return parameters and R² score."""
    try:
        if model == DeclineModel.EXPONENTIAL:
            bounds = ([0], [1])
            p0 = [0.1]
            popt, _ = curve_fit(
                lambda t, D_i: exponential_decline(t, q_i, D_i),
                t_data, q_data, p0=p0, bounds=bounds
            )
            predicted = exponential_decline(t_data, q_i, popt[0])
            params = (q_i, popt[0], None)
            
        elif model == DeclineModel.HYPERBOLIC:
            bounds = ([0, 0], [1, 1.5])
            p0 = [0.1, 0.5]
            popt, _ = curve_fit(
                lambda t, D_i, b: hyperbolic_decline(t, q_i, D_i, b),
                t_data, q_data, p0=p0, bounds=bounds
            )
            predicted = hyperbolic_decline(t_data, q_i, popt[0], popt[1])
            params = (q_i, popt[0], popt[1])
            
        else:  # HARMONIC
            bounds = ([0], [1])
            p0 = [0.1]
            popt, _ = curve_fit(
                lambda t, D_i: harmonic_decline(t, q_i, D_i),
                t_data, q_data, p0=p0, bounds=bounds
            )
            predicted = harmonic_decline(t_data, q_i, popt[0])
            params = (q_i, popt[0], 1.0)  # b=1 for harmonic
        
        # Calculate R² score
        r_squared = 1 - np.sum((q_data - predicted)**2) / np.sum((q_data - np.mean(q_data))**2)
        
        return params, r_squared
        
    except Exception as e:
        print(f"Error fitting {model.value} model: {e}")
        return None, -np.inf

def compute_decline_rate(data: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Compute decline rates for each well using all models and selecting the best fit.
    Returns summary DataFrame and detailed prediction results.
    """
    decline_results = []
    prediction_results = []

    for well_id, well_data in data.groupby('UWI'):
        if len(well_data) < 12:  # Skip wells with insufficient data (less than 1 year)
            print(f"Well {well_id}: Insufficient data points (minimum 12 required)")
            continue
            
        t_data = well_data['Month'].values
        q_data = well_data['Avg Dly Oil (m3/d)'].values
        q_i = well_data.loc[well_data['Month'] == 1, 'Avg Dly Oil (m3/d)'].values[0]
        
        # Try all decline models for every well
        model_results = {}
        for model in DeclineModel:
            params, r_squared = fit_decline_model(t_data, q_data, q_i, model)
            if params is not None:  # Store results if fitting was successful
                model_results[model] = {
                    'params': params,
                    'r_squared': r_squared
                }
        
        if not model_results:  # Skip well if no models could be fitted
            print(f"Well {well_id}: Unable to fit any decline models")
            continue
            
        # Select best model based on R² score
        best_model = max(model_results.items(), key=lambda x: x[1]['r_squared'])[0]
        best_params = model_results[best_model]['params']
        best_r_squared = model_results[best_model]['r_squared']
        
        q_i, D_i, b = best_params
        
        # Store results for the well
        decline_results.append({
            'UWI': well_id,
            'Initial_Rate': q_i,
            'Decline_Rate': D_i,
            'b_factor': b if b is not None else 0,
            'Model_Type': best_model.value,
            'R_squared': best_r_squared,
            'Model_Attempts': len(model_results),
            'All_R2_Scores': {model.value: results['r_squared'] 
                             for model, results in model_results.items()}
        })
        
        # Calculate predictions using best-fit model
        if best_model == DeclineModel.EXPONENTIAL:
            predicted = exponential_decline(t_data, q_i, D_i)
            D_t = D_i * np.ones_like(t_data)
        elif best_model == DeclineModel.HYPERBOLIC:
            predicted = hyperbolic_decline(t_data, q_i, D_i, b)
            D_t = D_i / (1 + b * D_i * t_data)
        else:  # HARMONIC
            predicted = harmonic_decline(t_data, q_i, D_i)
            D_t = D_i / (1 + D_i * t_data)
            
        # Store detailed predictions
        for t, q_actual, q_pred, d_t in zip(t_data, q_data, predicted, D_t):
            prediction_results.append({
                'UWI': well_id,
                'Month': t,
                'Actual_Rate': q_actual,
                'Predicted_Rate': q_pred,
                'D(t)': d_t,
                'Model_Type': best_model.value,
                'R_squared': best_r_squared,
                'Actual_Cumulative': np.sum(q_data[:int(t)]),
                'Predicted_Cumulative': np.sum(predicted[:int(t)])
            })
            
    summary_df = pd.DataFrame(decline_results)
    detailed_df = pd.DataFrame(prediction_results)
    
    return summary_df, detailed_df

def perform_multi_wave_analysis(data: pd.DataFrame, initial_results: pd.DataFrame, 
                              detailed_results: pd.DataFrame, r2_threshold: float = 0.75,
                              min_improvement: float = 0.0001) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Perform multiple waves of decline curve analysis on wells with poor R² scores.
    Each wave starts the analysis 12 months later than the previous wave.
    """
    # Initialize results with the initial analysis
    final_constants = initial_results.copy()
    final_detailed = detailed_results.copy()
    
    # Track improvements across waves
    improvement_stats = {
        'wave': [],
        'wells_analyzed': [],
        'avg_r2_before': [],
        'avg_r2_after': [],
        'wells_improved': []
    }
    
    for wave in range(1, 11):  # 10 waves maximum
        print(f"\nStarting Wave {wave} of improvement analysis...")
        
        # === STOPPING CONDITION 1: No poor wells left ===
        poor_wells = final_constants[final_constants['R_squared'] < r2_threshold]['UWI'].unique()
        if len(poor_wells) == 0:
            print(f"Stopping: All wells now have R² scores above {r2_threshold}")
            break
            
        print(f"Found {len(poor_wells)} wells with R² score below {r2_threshold}")
        
        # Store original R² scores for comparison
        original_r2_scores = final_constants[final_constants['UWI'].isin(poor_wells)].set_index('UWI')['R_squared']
        
        # Create filtered dataset for poor wells with shifted start time
        shifted_data = []
        insufficient_data_wells = []
        
        for well in poor_wells:
            well_data = data[data['UWI'] == well].copy()
            # Check for sufficient data after shifting
            if len(well_data) <= (12 * wave):
                insufficient_data_wells.append(well)
                continue
                
            # Shift the start time forward by 12 months × wave number
            well_data = well_data.iloc[12 * wave:].copy()
            well_data['Month'] = range(1, len(well_data) + 1)  # Renumber months
            shifted_data.append(well_data)
        
        # === STOPPING CONDITION 2: Insufficient data ===
        if not shifted_data:
            print(f"Stopping: No wells have sufficient data after {12 * wave} month shift")
            break
            
        shifted_df = pd.concat(shifted_data, ignore_index=True)
        
        # Perform new analysis on shifted data
        print(f"Analyzing {len(shifted_data)} wells with {12 * wave} month shift...")
        new_constants, new_detailed = compute_decline_rate(shifted_df)
        
        # === STOPPING CONDITION 3: No successful fits ===
        if new_constants.empty:
            print("Stopping: No successful fits achieved in this wave")
            break
            
        # Track improvements
        improved_wells = 0
        total_r2_improvement = 0
        
        # Compare results and keep better fits
        for well in new_constants['UWI'].unique():
            new_well_data = new_constants[new_constants['UWI'] == well]
            old_well_data = final_constants[final_constants['UWI'] == well]
            
            if not new_well_data.empty and not old_well_data.empty:
                new_r2 = new_well_data['R_squared'].iloc[0]
                old_r2 = old_well_data['R_squared'].iloc[0]
                
                if new_r2 > old_r2:
                    improved_wells += 1
                    total_r2_improvement += (new_r2 - old_r2)
                    
                    # Update final results
                    final_constants = pd.concat([
                        final_constants[final_constants['UWI'] != well],
                        new_well_data
                    ]).reset_index(drop=True)
                    
                    # Update detailed results
                    final_detailed = pd.concat([
                        final_detailed[final_detailed['UWI'] != well],
                        new_detailed[new_detailed['UWI'] == well]
                    ]).reset_index(drop=True)
        
        # Calculate improvement statistics
        wells_analyzed = len(shifted_data)
        avg_r2_before = original_r2_scores.mean()
        current_r2_scores = final_constants[final_constants['UWI'].isin(poor_wells)]['R_squared']
        avg_r2_after = current_r2_scores.mean()
        avg_improvement = total_r2_improvement / len(poor_wells) if poor_wells.size > 0 else 0
        
        # Store improvement statistics
        improvement_stats['wave'].append(wave)
        improvement_stats['wells_analyzed'].append(wells_analyzed)
        improvement_stats['avg_r2_before'].append(avg_r2_before)
        improvement_stats['avg_r2_after'].append(avg_r2_after)
        improvement_stats['wells_improved'].append(improved_wells)
        
        # Print wave summary
        print(f"\nWave {wave} Summary:")
        print(f"Wells analyzed: {wells_analyzed}")
        print(f"Wells improved: {improved_wells}")
        print(f"Average R² before: {avg_r2_before:.3f}")
        print(f"Average R² after: {avg_r2_after:.3f}")
        print(f"Average R² improvement: {avg_improvement:.3f}")
        
        # === STOPPING CONDITION 4: Insufficient improvement ===
        if avg_improvement < min_improvement:
            print(f"\nStopping: Average R² improvement ({avg_improvement:.3f}) below minimum threshold ({min_improvement})")
            break
    
    # Print final improvement summary
    print("\nFinal Multi-Wave Analysis Results:")
    print(f"Total waves completed: {len(improvement_stats['wave'])}")
    if improvement_stats['wells_improved']:
        print(f"Total wells improved: {sum(improvement_stats['wells_improved'])}")
        print(f"Final average R²: {improvement_stats['avg_r2_after'][-1]:.3f}")
    
    return final_constants, final_detailed