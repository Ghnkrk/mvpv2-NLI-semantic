import os
import shutil
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uuid
from engine.service import ComplianceService
from pydantic import BaseModel
from typing import List

app = FastAPI(title="NABH Compliance Auditor Suite API")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directories
UPLOAD_DIR = "uploads"
REPORT_DIR = "reports"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)

# Service
service = ComplianceService()

class AnalysisResult(BaseModel):
    filename: str
    report_data: dict
    json_url: str
    pdf_url: str

@app.post("/analyze", response_model=List[AnalysisResult])
async def analyze_documents(files: List[UploadFile] = File(...)):
    results = []
    for file in files:
        # Save uploaded file
        file_id = str(uuid.uuid4())
        ext = os.path.splitext(file.filename)[1]
        temp_path = os.path.join(UPLOAD_DIR, f"{file_id}{ext}")
        
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        try:
            # Run analysis
            res = service.analyze_document(temp_path, output_folder=REPORT_DIR)
            
            if "error" in res:
                # Cleanup and skip
                os.remove(temp_path)
                continue
                
            results.append(AnalysisResult(
                filename=file.filename,
                report_data=res["report_data"],
                json_url=f"/reports/{os.path.basename(res['json_path'])}",
                pdf_url=f"/reports/{os.path.basename(res['pdf_path'])}"
            ))
            
            # Cleanup source doc after analysis
            os.remove(temp_path)
            
        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise HTTPException(status_code=500, detail=f"Analysis failed for {file.filename}: {str(e)}")
            
    return results

@app.get("/")
async def root():
    return FileResponse("frontend/index.html")

# Serve reports as static files
app.mount("/reports", StaticFiles(directory=REPORT_DIR), name="reports")
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")
