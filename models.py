# models.py
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class Plant(BaseModel):
    id: str
    refPhoto: str
    yProj: float
    xProj: float
    speciesName: str
    family: str
    formation: str
    slope: Optional[float]
    exposure: str
    altitude: float
    imagePath: str
    imageSize: float

class PlantDatabaseMetadata(BaseModel):
    totalPlants: int
    totalImages: int
    successfullyMapped: int
    processingDate: str
    dataSource: str
    sessionId: str

class PlantDatabase(BaseModel):
    metadata: PlantDatabaseMetadata
    families: List[str]
    plants: List[Plant]

class ProcessingStatus(BaseModel):
    session_id: str
    excel_uploaded: bool = False
    excel_filename: Optional[str] = None
    excel_path: Optional[str] = None
    images_uploaded: bool = False
    image_count: int = 0
    uploaded_images: List[str] = []
    processing_complete: bool = False
    output_path: Optional[str] = None
    mapped_plants: int = 0
    created_at: datetime = datetime.now()

class ExcelPreview(BaseModel):
    sheet_names: List[str]
    preview_data: Dict[str, List[List[Any]]]  # sheet_name -> rows
    total_rows: Dict[str, int]
    total_cols: Dict[str, int]

class ImageInfo(BaseModel):
    filename: str
    size_mb: float
    dimensions: tuple
    format: str