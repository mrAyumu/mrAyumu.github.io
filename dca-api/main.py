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

# Import your existing DCA functions
from dca_engine import (
    merge_production_data_from_memory,
    handle_outliers_programmatic,
    normalize_time,
    compute_decline_rate,
    perform_multi_wave_analysis
)

app = FastAPI(
    title="Decline Curve Analysis API",
    description="An intelligent petroleum engineering tool for decline curve analysis",
    version="1.0.0"
)

# CORS middleware to allow frontend connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global storage for analysis results (in production, use a database)
analysis_sessions = {}

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "DCA API is running", "version": "1.0.0"}

@app.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """
    Upload and validate CSV files for DCA analysis
    """
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
            # Read CSV content
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
        
        # Create session ID for this upload
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        # Store data in session (in production, use proper storage)
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
    """
    Run decline curve analysis on uploaded data
    """
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
        
        # Step 1: Handle outliers
        columns_to_check = ['Avg Dly Oil (m3/d)']
        production_data = handle_outliers_programmatic(
            production_data, 
            columns_to_check, 
            method=outlier_method,
            replacement=replacement_method
        )
        
        # Step 2: Normalize time
        production_data_normalized = normalize_time(production_data)
        production_data_normalized = production_data_normalized.dropna(subset=['Month'])
        production_data_normalized['Month'] = production_data_normalized['Month'].astype(int)
        
        # Step 3: Initial decline curve analysis
        decline_constants, detailed_results = compute_decline_rate(production_data_normalized)
        
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
        
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.get("/results/{session_id}")
async def get_results(session_id: str):
    """
    Get analysis results for a session
    """
    try:
        if session_id not in analysis_sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session = analysis_sessions[session_id]
        
        if session["status"] != "completed":
            raise HTTPException(status_code=400, detail="Analysis not completed")
        
        # Convert DataFrames to JSON-serializable format
        decline_constants = session["decline_constants"]
        detailed_results = session["detailed_results"]
        
        # Sample wells for preview (limit to avoid large responses)
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
    """
    Download analysis results in various formats
    """
    try:
        if session_id not in analysis_sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session = analysis_sessions[session_id]
        
        if session["status"] != "completed":
            raise HTTPException(status_code=400, detail="Analysis not completed")
        
        decline_constants = session["decline_constants"]
        detailed_results = session["detailed_results"]
        
        if file_type == "constants":
            # Download decline constants
            output = io.StringIO()
            decline_constants.to_csv(output, index=False)
            output.seek(0)
            
            return StreamingResponse(
                io.BytesIO(output.getvalue().encode('utf-8')),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=decline_constants.csv"}
            )
            
        elif file_type == "detailed":
            # Download detailed results
            output = io.StringIO()
            detailed_results.to_csv(output, index=False)
            output.seek(0)
            
            return StreamingResponse(
                io.BytesIO(output.getvalue().encode('utf-8')),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=detailed_results.csv"}
            )
            
        elif file_type == "summary":
            # Download summary statistics
            summary_df = pd.DataFrame([session["summary_stats"]])
            output = io.StringIO()
            summary_df.to_csv(output, index=False)
            output.seek(0)
            
            return StreamingResponse(
                io.BytesIO(output.getvalue().encode('utf-8')),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=analysis_summary.csv"}
            )
            
        elif file_type == "all":
            # Download all files in a ZIP
            zip_buffer = io.BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # Add decline constants
                constants_csv = decline_constants.to_csv(index=False)
                zip_file.writestr("decline_constants.csv", constants_csv)
                
                # Add detailed results
                detailed_csv = detailed_results.to_csv(index=False)
                zip_file.writestr("detailed_results.csv", detailed_csv)
                
                # Add summary
                summary_df = pd.DataFrame([session["summary_stats"]])
                summary_csv = summary_df.to_csv(index=False)
                zip_file.writestr("analysis_summary.csv", summary_csv)
                
                # Add README
                readme_content = generate_readme(session)
                zip_file.writestr("README.txt", readme_content)
            
            zip_buffer.seek(0)
            
            return StreamingResponse(
                io.BytesIO(zip_buffer.getvalue()),
                media_type="application/zip",
                headers={"Content-Disposition": f"attachment; filename=dca_results_{session_id}.zip"}
            )
            
        else:
            raise HTTPException(status_code=400, detail="Invalid file type")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """
    Delete a session and its data
    """
    try:
        if session_id not in analysis_sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        del analysis_sessions[session_id]
        
        return {"message": f"Session {session_id} deleted successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")

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

def generate_readme(session: dict) -> str:
    """Generate README content for downloaded results"""
    
    analysis_time = session.get("analysis_end", datetime.now())
    config = session.get("analysis_config", {})
    
    readme = f"""Decline Curve Analysis Results
============================

Analysis Date: {analysis_time.strftime('%Y-%m-%d %H:%M:%S')}
Session ID: {session.get('session_id', 'N/A')}

Analysis Configuration:
- Outlier Handling: {config.get('outlier_method', 'N/A')}
- Replacement Method: {config.get('replacement_method', 'N/A')}
- Multi-Wave Analysis: {config.get('multi_wave', 'N/A')}
- R² Threshold: {config.get('r2_threshold', 'N/A')}

Files in this archive:

1. decline_constants.csv
   - Contains the best-fit decline curve parameters for each well
   - Includes model type selection and goodness of fit metrics

2. detailed_results.csv
   - Contains month-by-month actual and predicted production rates
   - Includes time-varying decline rates for each well

3. analysis_summary.csv
   - Contains statistical summary of model performance
   - Shows R² score distribution for each model type

Generated by DCA API v1.0.0
"""
    
    return readme

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)