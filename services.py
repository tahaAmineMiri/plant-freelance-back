# services.py
import pandas as pd
import os
import uuid
from typing import Dict, List, Any, Optional
from PIL import Image
from pathlib import Path
from datetime import datetime
import re

from models import ExcelPreview, ImageInfo, Plant, PlantDatabase, PlantDatabaseMetadata


class ExcelProcessor:
    def __init__(self):
        pass

    def preview_excel(self, file_path: str, max_preview_rows: int = 10) -> ExcelPreview:
        """Preview Excel file structure to help user identify data start position"""
        try:
            # Read all sheets
            excel_file = pd.ExcelFile(file_path)
            sheet_names = excel_file.sheet_names

            preview_data = {}
            total_rows = {}
            total_cols = {}

            for sheet_name in sheet_names:
                df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)

                # Get basic info
                total_rows[sheet_name] = len(df)
                total_cols[sheet_name] = len(df.columns)

                # Get preview data (first 10 rows)
                preview_rows = []
                for i in range(min(max_preview_rows, len(df))):
                    row = []
                    for j in range(len(df.columns)):
                        cell_value = df.iloc[i, j]
                        if pd.isna(cell_value):
                            row.append("")
                        else:
                            row.append(str(cell_value))
                    preview_rows.append(row)

                preview_data[sheet_name] = preview_rows

            return ExcelPreview(
                sheet_names=sheet_names,
                preview_data=preview_data,
                total_rows=total_rows,
                total_cols=total_cols
            )

        except Exception as e:
            raise Exception(f"Error reading Excel file: {str(e)}")

    def process_excel(self, file_path: str, start_row: int, start_col: int, sheet_name: str = None) -> pd.DataFrame:
        """Process Excel data starting from specified row and column"""
        try:
            # Read the Excel file
            if sheet_name:
                df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
            else:
                df = pd.read_excel(file_path, header=None)

            # Extract data starting from specified position
            data_df = df.iloc[start_row:, start_col:]

            # Use first row as headers
            headers = data_df.iloc[0].values
            data_df = data_df[1:].copy()
            data_df.columns = headers

            # Clean up headers (remove NaN, strip whitespace)
            clean_headers = []
            for header in data_df.columns:
                if pd.isna(header):
                    clean_headers.append(f"Column_{len(clean_headers)}")
                else:
                    clean_headers.append(str(header).strip())

            data_df.columns = clean_headers

            # Reset index
            data_df.reset_index(drop=True, inplace=True)

            return data_df

        except Exception as e:
            raise Exception(f"Error processing Excel data: {str(e)}")


class ImageProcessor:
    def __init__(self):
        self.supported_formats = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}

    def process_images(self, image_dir: str) -> Dict[str, ImageInfo]:
        """Process all images in a directory and return metadata"""
        image_data = {}

        if not os.path.exists(image_dir):
            return image_data

        for filename in os.listdir(image_dir):
            file_path = os.path.join(image_dir, filename)

            if not os.path.isfile(file_path):
                continue

            file_ext = Path(filename).suffix.lower()
            if file_ext not in self.supported_formats:
                continue

            try:
                with Image.open(file_path) as img:
                    # Get image info
                    dimensions = img.size  # (width, height)
                    format_type = img.format

                # Get file size in MB
                file_size = os.path.getsize(file_path) / (1024 * 1024)

                image_info = ImageInfo(
                    filename=filename,
                    size_mb=round(file_size, 2),
                    dimensions=dimensions,
                    format=format_type or file_ext[1:].upper()
                )

                image_data[filename] = image_info

            except Exception as e:
                print(f"Error processing image {filename}: {str(e)}")
                continue

        return image_data


class DataMapper:
    def __init__(self):
        pass

    def normalize_filename(self, filename: str) -> str:
        """Normalize filename for comparison (remove extension, clean special chars)"""
        # Remove extension
        base_name = Path(filename).stem

        # Clean special characters, keep only alphanumeric and common separators
        clean_name = re.sub(r'[^\w\-_.]', '', base_name)

        return clean_name.lower()

    def find_matching_image(self, ref_photo: str, image_data: Dict[str, ImageInfo]) -> Optional[str]:
        """Find matching image for a reference photo entry"""
        if pd.isna(ref_photo) or not ref_photo:
            return None

        ref_clean = self.normalize_filename(str(ref_photo))

        # Try exact match first
        for image_filename in image_data.keys():
            if self.normalize_filename(image_filename) == ref_clean:
                return image_filename

        # Try partial match (ref_photo contained in image filename)
        for image_filename in image_data.keys():
            image_clean = self.normalize_filename(image_filename)
            if ref_clean in image_clean or image_clean in ref_clean:
                return image_filename

        # Try matching without common prefixes/suffixes
        ref_core = re.sub(r'^(img|image|photo|pic)_?', '', ref_clean)
        ref_core = re.sub(r'_?(img|image|photo|pic)$', '', ref_core)

        for image_filename in image_data.keys():
            image_clean = self.normalize_filename(image_filename)
            image_core = re.sub(r'^(img|image|photo|pic)_?', '', image_clean)
            image_core = re.sub(r'_?(img|image|photo|pic)$', '', image_core)

            if ref_core and image_core and (ref_core in image_core or image_core in ref_core):
                return image_filename

        return None

    def map_data(self, excel_data: pd.DataFrame, image_data: Dict[str, ImageInfo],
                 ref_photo_column: str, session_id: str) -> PlantDatabase:
        """Map Excel data with images to create plant database"""
        plants = []
        families = set()
        successful_mappings = 0

        # Check if ref_photo_column exists
        if ref_photo_column not in excel_data.columns:
            available_columns = list(excel_data.columns)
            raise Exception(
                f"Reference photo column '{ref_photo_column}' not found. Available columns: {available_columns}")

        for index, row in excel_data.iterrows():
            try:
                # Get reference photo value
                ref_photo = row[ref_photo_column]

                # Find matching image
                matching_image = self.find_matching_image(ref_photo, image_data)

                if not matching_image:
                    print(f"No matching image found for reference: {ref_photo}")
                    continue

                # Extract plant data with fallbacks
                plant_data = {
                    'id': str(uuid.uuid4()),
                    'refPhoto': str(ref_photo) if not pd.isna(ref_photo) else f"ref_{index}",
                    'yProj': self._safe_float_convert(
                        row.get('Y_Proj', row.get('yProj', row.get('Y', row.get('Latitude', 0))))),
                    'xProj': self._safe_float_convert(
                        row.get('X_Proj', row.get('xProj', row.get('X', row.get('Longitude', 0))))),
                    'speciesName': str(row.get('Species Name', row.get('speciesName', row.get('Species', row.get('Name',
                                                                                                                 'Unknown Species'))))),
                    'family': str(row.get('Family', row.get('family', 'Unknown Family'))),
                    'formation': str(
                        row.get('Formation', row.get('formation', row.get('Habitat', 'Unknown Formation')))),
                    'slope': self._safe_float_convert(row.get('Slope', row.get('slope', None))),
                    'exposure': str(row.get('Exposure', row.get('exposure', row.get('Aspect', 'Unknown')))),
                    'altitude': self._safe_float_convert(
                        row.get('Altitude', row.get('altitude', row.get('Elevation', 0)))),
                    'imagePath': f"{session_id}/{matching_image}",
                    'imageSize': image_data[matching_image].size_mb
                }

                plant = Plant(**plant_data)
                plants.append(plant)
                families.add(plant.family)
                successful_mappings += 1

            except Exception as e:
                print(f"Error processing row {index}: {str(e)}")
                continue

        # Create metadata
        metadata = PlantDatabaseMetadata(
            totalPlants=len(plants),
            totalImages=len(image_data),
            successfullyMapped=successful_mappings,
            processingDate=datetime.now().isoformat(),
            dataSource=f"Excel upload - Session {session_id}",
            sessionId=session_id
        )

        return PlantDatabase(
            metadata=metadata,
            families=sorted(list(families)),
            plants=plants
        )

    def _safe_float_convert(self, value) -> Optional[float]:
        """Safely convert value to float"""
        if pd.isna(value) or value == '':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None