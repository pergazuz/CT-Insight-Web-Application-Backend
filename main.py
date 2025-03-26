from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import tempfile
import shutil
import pydicom
from pydicom.errors import InvalidDicomError
import os
import time

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/process-dicom")
async def process_dicom_files(dicomFiles: List[UploadFile] = File(...)):

    temp_dir = os.getcwd() + '/temp'
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    
    try:
        saved_files = []
        for file in dicomFiles:
            filename = os.path.basename(file.filename)
            file_path = os.path.join(temp_dir, filename)
            if not filename.lower().endswith('.dcm'):
                raise HTTPException(status_code=400, detail=f"Invalid file type: {filename}")
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            try:
                ds = pydicom.dcmread(file_path)
                if not hasattr(ds, 'StudyInstanceUID'):
                    raise HTTPException(status_code=400, detail=f"Invalid DICOM file: {filename}")
                
                # Store relevant metadata
                saved_files.append({
                    "filename": filename,  # Use sanitized filename
                    "study_uid": ds.StudyInstanceUID,
                    "patient_id": getattr(ds, 'PatientID', 'N/A'),
                    "patient_name": getattr(ds, 'PatientName', 'N/A'),
                    "modality": getattr(ds, 'Modality', 'N/A')
                })
            except InvalidDicomError:
                raise HTTPException(status_code=400, detail=f"Invalid DICOM file: {filename}")

        time.sleep(2)
        return {
            "status": "success",
            "message": f"Processed {len(saved_files)} DICOM files",
            "study_uid": saved_files[0]['study_uid'] if saved_files else None,
            "patient_info": {
                "id": saved_files[0]['patient_id'] if saved_files else None,
                "name": saved_files[0]['patient_name'] if saved_files else None
            },
            "files_processed": len(saved_files)
        }
    
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)