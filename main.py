from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict
import tempfile
import shutil
import pydicom
from pydicom.errors import InvalidDicomError
import os
import time
from fastapi.staticfiles import StaticFiles

app = FastAPI()

temp_dir = os.path.join(os.getcwd(), 'temp')
if not os.path.exists(temp_dir):
    os.makedirs(temp_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory="temp"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_dicom_metadata(ds) -> Dict:
    """Extract relevant DICOM metadata for display"""
    return {
        "window_center": getattr(ds, 'WindowCenter', 500),
        "window_width": getattr(ds, 'WindowWidth', 3000),
        "slice_thickness": getattr(ds, 'SliceThickness', 1),
        "series_description": getattr(ds, 'SeriesDescription', 'N/A'),
        "image_position": list(map(float, getattr(ds, 'ImagePositionPatient', [0, 0, 0]))),
        "pixel_spacing": list(map(float, getattr(ds, 'PixelSpacing', [1, 1]))),
        "rows": ds.Rows,
        "columns": ds.Columns,
        "instance_number": getattr(ds, 'InstanceNumber', 0)
    }

@app.post("/process-dicom")
async def process_dicom_files(dicomFiles: List[UploadFile] = File(...)):
    temp_dir = os.path.join(os.getcwd(), 'temp')
    os.makedirs(temp_dir, exist_ok=True)

    try:
        processed_files = []
        for file in dicomFiles:
            filename = os.path.basename(file.filename)
            file_path = os.path.join(temp_dir, filename)
            
            if not filename.lower().endswith('.dcm'):
                raise HTTPException(status_code=400, detail=f"Invalid file type: {filename}")

            # Save and validate file
            try:
                # Save file to temp directory
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)

                # Validate DICOM P10 header
                with open(file_path, "rb") as f:
                    f.seek(128)
                    prefix = f.read(4)
                    if prefix != b'DICM':
                        raise HTTPException(status_code=400, 
                            detail=f"Invalid DICOM P10 header in: {filename}")

                # Read DICOM file
                ds = pydicom.dcmread(file_path)
                if not hasattr(ds, 'StudyInstanceUID'):
                    raise HTTPException(status_code=400, 
                        detail=f"Missing DICOM Study Instance UID in: {filename}")

                # Create file data for frontend
                file_data = {
                    "filename": filename,
                    "url": f"/static/{filename}",
                    "metadata": get_dicom_metadata(ds),
                    "patient_info": {
                        "id": getattr(ds, 'PatientID', 'N/A'),
                        "name": getattr(ds, 'PatientName', 'N/A')
                    },
                    "study_info": {
                        "uid": ds.StudyInstanceUID,
                        "modality": getattr(ds, 'Modality', 'N/A')
                    }
                }
                processed_files.append(file_data)
                
            except InvalidDicomError:
                raise HTTPException(status_code=400, 
                    detail=f"Invalid DICOM file structure: {filename}")
            except Exception as e:
                raise HTTPException(status_code=400, 
                    detail=f"Error processing {filename}: {str(e)}")
    finally:
        # Only clean up if you want to remove files after processing
        # shutil.rmtree(temp_dir, ignore_errors=True)
        pass  # Remove this line if you want to keep files for display



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)