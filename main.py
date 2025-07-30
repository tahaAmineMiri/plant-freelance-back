# main.py
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import pandas as pd
import os
import json
import shutil
import zipfile
from pathlib import Path
from typing import List, Optional
import uuid
from PIL import Image
import aiofiles
from datetime import datetime

from models import PlantDatabase, Plant, ProcessingStatus
from services import ExcelProcessor, ImageProcessor, DataMapper

app = FastAPI(title="Plant Database API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create directories
os.makedirs("uploads/excel", exist_ok=True)
os.makedirs("uploads/images", exist_ok=True)
os.makedirs("processed_data", exist_ok=True)
os.makedirs("static/images", exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Global storage for processing status
processing_status = {}


@app.get("/")
async def root():
    return {"message": "Plant Database API", "version": "1.0.0"}


@app.post("/upload/excel")
async def upload_excel(
        file: UploadFile = File(...),
        session_id: str = Form(...)
):
    """Upload Excel file containing plant data"""
    if not file.filename.endswith(('.xlsx', '.xls', '.ods')):
        raise HTTPException(status_code=400, detail="Only Excel files are supported")

    session_dir = f"uploads/excel/{session_id}"
    os.makedirs(session_dir, exist_ok=True)

    file_path = f"{session_dir}/{file.filename}"

    async with aiofiles.open(file_path, 'wb') as f:
        content = await file.read()
        await f.write(content)

    # Initialize processing status
    processing_status[session_id] = ProcessingStatus(
        session_id=session_id,
        excel_uploaded=True,
        excel_filename=file.filename,
        excel_path=file_path
    )

    return {"message": "Excel file uploaded successfully", "session_id": session_id}


@app.post("/upload/images")
async def upload_images(
        files: List[UploadFile] = File(...),
        session_id: str = Form(...)
):
    """Upload multiple image files"""
    if session_id not in processing_status:
        raise HTTPException(status_code=400, detail="Session not found. Upload Excel file first.")

    session_dir = f"uploads/images/{session_id}"
    os.makedirs(session_dir, exist_ok=True)

    uploaded_files = []
    print(f"Uploading {len(files)} files to {session_dir}")

    for file in files:
        print(f"Processing file: {file.filename}, content_type: {file.content_type}")

        if not file.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif')):
            print(f"Skipping non-image file: {file.filename}")
            continue

        file_path = f"{session_dir}/{file.filename}"
        print(f"Saving to: {file_path}")

        try:
            async with aiofiles.open(file_path, 'wb') as f:
                content = await file.read()
                await f.write(content)

            # Verify file was saved
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                print(f"File saved successfully: {file_path} ({file_size} bytes)")
                uploaded_files.append(file.filename)
            else:
                print(f"Error: File was not saved: {file_path}")

        except Exception as e:
            print(f"Error saving file {file.filename}: {str(e)}")
            continue

    print(f"Successfully uploaded {len(uploaded_files)} files: {uploaded_files}")

    # Update processing status
    processing_status[session_id].images_uploaded = True
    processing_status[session_id].image_count = len(uploaded_files)
    processing_status[session_id].uploaded_images = uploaded_files

    return {
        "message": f"Successfully uploaded {len(uploaded_files)} images",
        "uploaded_files": uploaded_files,
        "session_id": session_id
    }

@app.post("/upload/images-zip")
async def upload_images_zip(
        file: UploadFile = File(...),
        session_id: str = Form(...)
):
    """Upload a ZIP file containing images"""
    if session_id not in processing_status:
        raise HTTPException(status_code=400, detail="Session not found. Upload Excel file first.")

    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Only ZIP files are supported")

    session_dir = f"uploads/images/{session_id}"
    os.makedirs(session_dir, exist_ok=True)

    zip_path = f"{session_dir}/{file.filename}"

    # Save ZIP file
    async with aiofiles.open(zip_path, 'wb') as f:
        content = await file.read()
        await f.write(content)

    print(f"ZIP file saved to: {zip_path}")
    print(f"ZIP file size: {os.path.getsize(zip_path)} bytes")

    # Extract ZIP file
    extracted_files = []
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            print(f"ZIP contents: {zip_ref.namelist()}")

            for member in zip_ref.namelist():
                print(f"Processing ZIP member: {member}")

                # Skip directories and system files
                if member.endswith('/') or member.startswith('__MACOSX/') or member.startswith('.'):
                    print(f"Skipping: {member}")
                    continue

                # Check if it's an image file
                member_lower = member.lower()
                if any(member_lower.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif']):
                    try:
                        # Extract the file
                        zip_ref.extract(member, session_dir)

                        # Get just the filename (in case it was in a subfolder)
                        filename = os.path.basename(member)

                        # If the file was extracted to a subfolder, move it to the root
                        extracted_path = os.path.join(session_dir, member)
                        target_path = os.path.join(session_dir, filename)

                        if extracted_path != target_path:
                            # Move file to root of session directory
                            os.makedirs(os.path.dirname(target_path), exist_ok=True)
                            shutil.move(extracted_path, target_path)

                            # Clean up empty directories
                            try:
                                parent_dir = os.path.dirname(extracted_path)
                                if parent_dir != session_dir:
                                    os.rmdir(parent_dir)
                            except:
                                pass

                        extracted_files.append(filename)
                        print(f"Extracted image: {filename}")

                    except Exception as e:
                        print(f"Error extracting {member}: {str(e)}")
                        continue
                else:
                    print(f"Not an image file: {member}")

    except zipfile.BadZipFile as e:
        print(f"Bad ZIP file: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid ZIP file")
    except Exception as e:
        print(f"Error processing ZIP: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing ZIP file: {str(e)}")

    # Remove ZIP file after extraction
    try:
        os.remove(zip_path)
        print(f"Removed ZIP file: {zip_path}")
    except Exception as e:
        print(f"Warning: Could not remove ZIP file: {str(e)}")

    print(f"Successfully extracted {len(extracted_files)} images: {extracted_files}")

    # Verify files exist
    actual_files = []
    for filename in extracted_files:
        file_path = os.path.join(session_dir, filename)
        if os.path.exists(file_path):
            actual_files.append(filename)
            print(f"Verified file exists: {file_path}")
        else:
            print(f"Warning: File not found after extraction: {file_path}")

    # Update processing status
    processing_status[session_id].images_uploaded = True
    processing_status[session_id].image_count = len(actual_files)
    processing_status[session_id].uploaded_images = actual_files

    return {
        "message": f"Successfully extracted {len(actual_files)} images from ZIP",
        "extracted_files": actual_files,
        "session_id": session_id
    }

@app.get("/preview/excel/{session_id}")
async def preview_excel(session_id: str):
    """Preview Excel file structure to help user identify data start position"""
    if session_id not in processing_status:
        raise HTTPException(status_code=404, detail="Session not found")

    status = processing_status[session_id]
    if not status.excel_uploaded:
        raise HTTPException(status_code=400, detail="Excel file not uploaded")

    try:
        processor = ExcelProcessor()
        preview_data = processor.preview_excel(status.excel_path)
        return preview_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error previewing Excel: {str(e)}")


# main.py - Updated process/data endpoint
@app.post("/process/data")
async def process_data(
        session_id: str = Form(...),
        start_row: int = Form(...),
        start_col: int = Form(...),
        ref_photo_column: str = Form(...)
):
    """Process Excel data and map with images"""
    if session_id not in processing_status:
        raise HTTPException(status_code=404, detail="Session not found")

    status = processing_status[session_id]
    if not status.excel_uploaded or not status.images_uploaded:
        raise HTTPException(status_code=400, detail="Both Excel and images must be uploaded first")

    try:
        print(f"Processing data for session {session_id}")
        print(f"Parameters: start_row={start_row}, start_col={start_col}, ref_photo_column='{ref_photo_column}'")

        # Initialize processors
        excel_processor = ExcelProcessor()
        image_processor = ImageProcessor()
        data_mapper = DataMapper()

        # Process Excel data
        print(f"Processing Excel file: {status.excel_path}")
        excel_data = excel_processor.process_excel(
            status.excel_path,
            start_row,
            start_col
        )

        print(f"Excel data processed successfully. Shape: {excel_data.shape}")
        print(f"Columns: {list(excel_data.columns)}")

        # Process images
        image_dir = f"uploads/images/{session_id}"
        print(f"Processing images from: {image_dir}")
        image_data = image_processor.process_images(image_dir)
        print(f"Found {len(image_data)} images")

        # Map data
        print(f"Mapping data with ref_photo_column: '{ref_photo_column}'")
        plant_database = data_mapper.map_data(
            excel_data,
            image_data,
            ref_photo_column,
            session_id
        )

        print(f"Data mapping completed. {len(plant_database.plants)} plants mapped")

        # Save processed data
        output_path = f"processed_data/{session_id}_plant_database.json"
        with open(output_path, 'w') as f:
            json.dump(plant_database.dict(), f, indent=2, ensure_ascii=False)

        # Copy images to static directory for serving
        static_session_dir = f"static/images/{session_id}"
        os.makedirs(static_session_dir, exist_ok=True)

        for image_file in os.listdir(image_dir):
            if image_file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.tiff')):
                shutil.copy2(
                    os.path.join(image_dir, image_file),
                    os.path.join(static_session_dir, image_file)
                )

        # Update processing status
        processing_status[session_id].processing_complete = True
        processing_status[session_id].output_path = output_path
        processing_status[session_id].mapped_plants = len(plant_database.plants)

        return {
            "message": "Data processed successfully",
            "database": plant_database.dict(),
            "session_id": session_id
        }

    except Exception as e:
        print(f"Error processing data: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error processing data: {str(e)}")

@app.get("/data/{session_id}")
async def get_plant_data(session_id: str):
    """Get processed plant database for a session"""
    if session_id not in processing_status:
        raise HTTPException(status_code=404, detail="Session not found")

    status = processing_status[session_id]
    if not status.processing_complete:
        raise HTTPException(status_code=400, detail="Data processing not complete")

    try:
        with open(status.output_path, 'r') as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Processed data not found")


@app.get("/status/{session_id}")
async def get_status(session_id: str):
    """Get processing status for a session"""
    if session_id not in processing_status:
        raise HTTPException(status_code=404, detail="Session not found")

    return processing_status[session_id].dict()


@app.get("/image/{session_id}/{filename}")
async def get_image(session_id: str, filename: str):
    """Serve image files"""
    image_path = f"static/images/{session_id}/{filename}"

    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(image_path)


@app.delete("/session/{session_id}")
async def cleanup_session(session_id: str):
    """Clean up session data"""
    if session_id not in processing_status:
        raise HTTPException(status_code=404, detail="Session not found")

    # Remove uploaded files
    excel_dir = f"uploads/excel/{session_id}"
    images_dir = f"uploads/images/{session_id}"
    static_dir = f"static/images/{session_id}"
    processed_file = f"processed_data/{session_id}_plant_database.json"

    for directory in [excel_dir, images_dir, static_dir]:
        if os.path.exists(directory):
            shutil.rmtree(directory)

    if os.path.exists(processed_file):
        os.remove(processed_file)

    # Remove from processing status
    del processing_status[session_id]

    return {"message": "Session cleaned up successfully"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)