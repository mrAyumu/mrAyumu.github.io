from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import pandas as pd
import numpy as np
import io
import zipfile
import json
from datetime import datetime
import tempfile
import os
from scipy.optimize import curve_fit
from enum import Enum

# === DCA Engine Code (moved from dca_engine.py) ===

class DeclineModel(Enum):
    """Enumeration of available decline curve models."""
    EXPONENTIAL = "exponential"
    HYPERBOLIC = "hyperbolic"
    HARMONIC = "harmonic"

def exponential_decline(t, q_i, D_i):
    """Exponential decline model."""
    return q_i * np.exp(-D_i * t)

def hyperbolic_decline(t, q_i, D_i, b):
    """Hyperbolic decline model."""
    safe_term = 1 + b * D_i * t
    return q_i / (safe_term)**(1/b)

def harmonic_decline(t, q_i, D_i):
    """Harmonic decline model (special case of hyperbolic where b=1)."""
    return q_i / (1 + D_i * t)

def merge_production_data_from_memory(dataframes: List[pd.DataFrame]) -> pd.DataFrame:
    """Merge production data from multiple DataFrames in memory."""
    try:
        if len(dataframes) == 1:
            return dataframes[0]
        
        base_columns = list(dataframes[0].columns)
        
        for i, df in enumerate(dataframes[1:], 1):
            if list(df.columns) != base_columns:
                print(f"Warning: Column names in DataFrame {i+1} don't match. Adjusting...")
                df.columns = base_columns
        
        merged_df = pd.concat(dataframes, ignore_index=True)
        return merged_df
        
    except Exception as e:
        raise Exception(f"Error merging production data: {str(e)}")

def identify_outliers(df: pd.DataFrame, columns: List[str], multiplier: float = 1.5):
    """Identify outliers using the IQR method for specified columns."""
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
    """Handle outliers programmatically without user input."""
    df = df.copy()
    outlier_info = identify_outliers(df, columns)
    
    for col, info in outlier_info.items():
        lower_bound = info['lower_bound']
        upper_bound = info['upper_bound']
        
        if method == "remove":
            df = df[(df[col] >= lower_bound) & (df[col] <= upper_bound)]
        elif method == "flag":
            df[f'{col}_is_outlier'] = (df[col] < lower_bound) | (df[col] > upper_bound)
        elif method == "replace":
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

def fit_decline_model(t_data: np.ndarray, q_data: np.ndarray, q_i: float, model: DeclineModel):
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

def compute_decline_rate(data: pd.DataFrame):
    """Compute decline rates for each well using all models and selecting the best fit."""
    decline_results = []
    prediction_results = []

    for well_id, well_data in data.groupby('UWI'):
        if len(well_data) < 12:  # Skip wells with insufficient data
            print(f"Well {well_id}: Insufficient data points (minimum 12 required)")
            continue
            
        t_data = well_data['Month'].values
        q_data = well_data['Avg Dly Oil (m3/d)'].values
        q_i = well_data.loc[well_data['Month'] == 1, 'Avg Dly Oil (m3/d)'].values[0]
        
        # Try all decline models for every well
        model_results = {}
        for model in DeclineModel:
            params, r_squared = fit_decline_model(t_data, q_data, q_i, model)
            if params is not None:
                model_results[model] = {
                    'params': params,
                    'r_squared': r_squared
                }
        
        if not model_results:
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
                              detailed_results: pd.DataFrame, r2_threshold: float = 0.75):
    """Perform multiple waves of decline curve analysis on wells with poor R² scores."""
    
    # For simplicity, let's do a basic version without all the complex logic
    # This can be enhanced later
    print(f"Running multi-wave analysis with R² threshold: {r2_threshold}")
    
    # Just return the initial results for now - we can enhance this later
    return initial_results, detailed_results

# === FastAPI Application ===

app = FastAPI(
    title="Decline Curve Analysis API",
    description="An intelligent petroleum engineering tool for decline curve analysis",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global storage for analysis results
analysis_sessions = {}

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "DCA API is running", "version": "1.0.0"}

@app.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """Upload and validate CSV files for DCA analysis"""
    try:
        if len(files) < 1:
            raise HTTPException(status_code=400, detail="At least one CSV file is required")
        
        # Validate file types
        for file in files:
            if not file.filename.endswith('.csv'):
                raise HTTPException(status_code=400, detail=f"File {file.filename} is not a CSV file")
        
        # Read and validate CSV files
        dataframes = []
        file_info = []
        
        for file in files:
            content = await file.read()
            df = pd.read_csv(io.StringIO(content.decode('utf-8')))
            
            # Basic validation
            required_columns = ['UWI', 'Avg Dly Oil (m3/d)']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                raise HTTPException(
                    status_code=400, 
                    detail=f"File {file.filename} missing required columns: {missing_columns}"
                )
            
            dataframes.append(df)
            file_info.append({
                "filename": file.filename,
                "rows": len(df),
                "columns": list(df.columns),
                "wells": df['UWI'].nunique() if 'UWI' in df.columns else 0
            })
        
        # Merge dataframes
        merged_df = merge_production_data_from_memory(dataframes)
        
        # Create session ID
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        # Store data in session
        analysis_sessions[session_id] = {
            "raw_data": merged_df,
            "file_info": file_info,
            "upload_time": datetime.now(),
            "status": "uploaded"
        }
        
        # Return preview data
        preview_data = merged_df.head(10).to_dict('records')
        
        return {
            "session_id": session_id,
            "status": "success",
            "message": f"Successfully uploaded {len(files)} files",
            "file_info": file_info,
            "total_rows": len(merged_df),
            "total_wells": merged_df['UWI'].nunique() if 'UWI' in merged_df.columns else 0,
            "columns": list(merged_df.columns),
            "preview_data": preview_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.post("/analyze")
async def run_analysis(
    session_id: str = Form(...),
    outlier_method: str = Form("remove"),
    replacement_method: str = Form("mean"),
    multi_wave: bool = Form(True),
    r2_threshold: float = Form(0.75)
):
    """Run decline curve analysis on uploaded data"""
    try:
        # Validate session
        if session_id not in analysis_sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session = analysis_sessions[session_id]
        
        if session["status"] != "uploaded":
            raise HTTPException(status_code=400, detail="Data not ready for analysis")
        
        # Get the data
        production_data = session["raw_data"].copy()
        
        # Update session status
        session["status"] = "processing"
        session["analysis_start"] = datetime.now()
        
        print(f"Starting analysis for session {session_id}")
        print(f"Data shape: {production_data.shape}")
        
        # Step 1: Handle outliers
        columns_to_check = ['Avg Dly Oil (m3/d)']
        production_data = handle_outliers_programmatic(
            production_data, 
            columns_to_check, 
            method=outlier_method,
            replacement=replacement_method
        )
        print(f"After outlier handling: {production_data.shape}")
        
        # Step 2: Normalize time
        production_data_normalized = normalize_time(production_data)
        production_data_normalized = production_data_normalized.dropna(subset=['Month'])
        production_data_normalized['Month'] = production_data_normalized['Month'].astype(int)
        print(f"After normalization: {production_data_normalized.shape}")
        
        # Step 3: Initial decline curve analysis
        decline_constants, detailed_results = compute_decline_rate(production_data_normalized)
        print(f"Analysis complete. Wells analyzed: {len(decline_constants)}")
        
        # Step 4: Multi-wave analysis (if enabled)
        if multi_wave and not decline_constants.empty:
            decline_constants, detailed_results = perform_multi_wave_analysis(
                production_data_normalized,
                decline_constants,
                detailed_results,
                r2_threshold=r2_threshold
            )
        
        # Generate summary statistics
        summary_stats = generate_summary_statistics(decline_constants)
        
        # Store results in session
        session.update({
            "status": "completed",
            "analysis_end": datetime.now(),
            "decline_constants": decline_constants,
            "detailed_results": detailed_results,
            "summary_stats": summary_stats,
            "analysis_config": {
                "outlier_method": outlier_method,
                "replacement_method": replacement_method,
                "multi_wave": multi_wave,
                "r2_threshold": r2_threshold
            }
        })
        
        return {
            "session_id": session_id,
            "status": "success",
            "message": "Analysis completed successfully",
            "summary": summary_stats,
            "processing_time": (session["analysis_end"] - session["analysis_start"]).total_seconds()
        }
        
    except Exception as e:
        # Update session status on error
        if session_id in analysis_sessions:
            analysis_sessions[session_id]["status"] = "error"
            analysis_sessions[session_id]["error"] = str(e)
        
        print(f"Analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.get("/results/{session_id}")
async def get_results(session_id: str):
    """Get analysis results for a session"""
    try:
        if session_id not in analysis_sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session = analysis_sessions[session_id]
        
        if session["status"] != "completed":
            raise HTTPException(status_code=400, detail="Analysis not completed")
        
        decline_constants = session["decline_constants"]
        
        # Sample wells for preview
        sample_wells = decline_constants.head(10).to_dict('records')
        
        return {
            "session_id": session_id,
            "summary": session["summary_stats"],
            "sample_wells": sample_wells,
            "total_wells": len(decline_constants),
            "analysis_config": session["analysis_config"],
            "processing_time": (session["analysis_end"] - session["analysis_start"]).total_seconds()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve results: {str(e)}")

@app.get("/download/{session_id}/{file_type}")
async def download_results(session_id: str, file_type: str):
    """Download analysis results in various formats"""
    try:
        if session_id not in analysis_sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session = analysis_sessions[session_id]
        
        if session["status"] != "completed":
            raise HTTPException(status_code=400, detail="Analysis not completed")
        
        decline_constants = session["decline_constants"]
        detailed_results = session["detailed_results"]
        
        if file_type == "constants":
            output = io.StringIO()
            decline_constants.to_csv(output, index=False)
            output.seek(0)
            
            return StreamingResponse(
                io.BytesIO(output.getvalue().encode('utf-8')),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=decline_constants.csv"}
            )
            
        elif file_type == "detailed":
            output = io.StringIO()
            detailed_results.to_csv(output, index=False)
            output.seek(0)
            
            return StreamingResponse(
                io.BytesIO(output.getvalue().encode('utf-8')),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=detailed_results.csv"}
            )
            
        elif file_type == "summary":
            summary_df = pd.DataFrame([session["summary_stats"]])
            output = io.StringIO()
            summary_df.to_csv(output, index=False)
            output.seek(0)
            
            return StreamingResponse(
                io.BytesIO(output.getvalue().encode('utf-8')),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=analysis_summary.csv"}
            )
            
        else:
            raise HTTPException(status_code=400, detail="Invalid file type")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

def generate_summary_statistics(decline_constants: pd.DataFrame) -> dict:
    """Generate summary statistics from decline curve analysis results"""
    
    if decline_constants.empty:
        return {
            "total_wells": 0,
            "avg_r2": 0,
            "model_distribution": {},
            "r2_distribution": {}
        }
    
    # Model distribution
    model_dist = decline_constants['Model_Type'].value_counts().to_dict()
    
    # R² statistics
    r2_stats = {
        "mean": float(decline_constants['R_squared'].mean()),
        "median": float(decline_constants['R_squared'].median()),
        "min": float(decline_constants['R_squared'].min()),
        "max": float(decline_constants['R_squared'].max()),
        "std": float(decline_constants['R_squared'].std())
    }
    
    # R² distribution
    r2_dist = {
        "above_0.9": int(len(decline_constants[decline_constants['R_squared'] > 0.9])),
        "above_0.8": int(len(decline_constants[decline_constants['R_squared'] > 0.8])),
        "above_0.7": int(len(decline_constants[decline_constants['R_squared'] > 0.7])),
        "below_0.7": int(len(decline_constants[decline_constants['R_squared'] <= 0.7]))
    }
    
    return {
        "total_wells": int(len(decline_constants)),
        "avg_r2": float(decline_constants['R_squared'].mean()),
        "model_distribution": model_dist,
        "r2_statistics": r2_stats,
        "r2_distribution": r2_dist
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
