# services.py - Updated process_excel method
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

    def preview_excel(self, file_path: str, max_preview_rows: int = 15) -> ExcelPreview:
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

                # Get preview data (first rows)
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
            print(f"Processing Excel: start_row={start_row}, start_col={start_col}, sheet={sheet_name}")

            # Read the Excel file
            if sheet_name:
                df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
            else:
                df = pd.read_excel(file_path, header=None)

            print(f"Excel shape: {df.shape}")
            print(
                f"Row {start_row} content: {df.iloc[start_row].tolist() if start_row < len(df) else 'Row out of bounds'}")

            # Validate start position
            if start_row >= len(df):
                raise Exception(f"Start row {start_row} is beyond the data range. Excel has {len(df)} rows.")

            if start_col >= len(df.columns):
                raise Exception(
                    f"Start column {start_col} is beyond the data range. Excel has {len(df.columns)} columns.")

            # Extract headers from the start row
            header_row = df.iloc[start_row, start_col:].values
            print(f"Header row extracted: {header_row}")

            # Extract data starting from the next row
            if start_row + 1 >= len(df):
                raise Exception(f"No data rows found after header row {start_row}")

            data_df = df.iloc[start_row + 1:, start_col:].copy()
            print(f"Data shape after extraction: {data_df.shape}")

            # Clean up headers (remove NaN, strip whitespace)
            clean_headers = []
            for i, header in enumerate(header_row):
                if pd.isna(header) or str(header).strip() == '':
                    clean_headers.append(f"Column_{start_col + i}")
                else:
                    clean_headers.append(str(header).strip())

            print(f"Clean headers: {clean_headers}")

            # Set column names
            data_df.columns = clean_headers[:len(data_df.columns)]

            # Reset index
            data_df.reset_index(drop=True, inplace=True)

            print(f"Final DataFrame columns: {list(data_df.columns)}")
            print(f"First few rows: {data_df.head().to_dict('records')}")

            return data_df

        except Exception as e:
            print(f"Error in process_excel: {str(e)}")
            raise Exception(f"Error processing Excel data: {str(e)}")


class ImageProcessor:
    def __init__(self):
        self.supported_formats = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}

    def process_images(self, image_dir: str) -> Dict[str, ImageInfo]:
        """Process all images in a directory and return metadata"""
        image_data = {}

        print(f"Processing images in directory: {image_dir}")

        if not os.path.exists(image_dir):
            print(f"Image directory does not exist: {image_dir}")
            return image_data

        # List all files in directory
        try:
            all_files = os.listdir(image_dir)
            print(f"Files found in directory: {all_files}")
        except Exception as e:
            print(f"Error listing directory {image_dir}: {str(e)}")
            return image_data

        for filename in all_files:
            file_path = os.path.join(image_dir, filename)
            print(f"Checking file: {file_path}")

            if not os.path.isfile(file_path):
                print(f"Not a file, skipping: {file_path}")
                continue

            file_ext = Path(filename).suffix.lower()
            print(f"File extension: {file_ext}")

            if file_ext not in self.supported_formats:
                print(f"Unsupported format, skipping: {filename}")
                continue

            try:
                print(f"Attempting to open image: {file_path}")
                with Image.open(file_path) as img:
                    # Get image info
                    dimensions = img.size  # (width, height)
                    format_type = img.format
                    print(f"Image opened successfully: {dimensions}, {format_type}")

                # Get file size in MB
                file_size = os.path.getsize(file_path) / (1024 * 1024)

                image_info = ImageInfo(
                    filename=filename,
                    size_mb=round(file_size, 2),
                    dimensions=dimensions,
                    format=format_type or file_ext[1:].upper()
                )

                image_data[filename] = image_info
                print(f"Successfully processed image: {filename}")

            except Exception as e:
                print(f"Error processing image {filename}: {str(e)}")
                continue

        print(f"Total images processed: {len(image_data)}")
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

        print(f"Available columns in DataFrame: {list(excel_data.columns)}")
        print(f"Looking for ref_photo_column: '{ref_photo_column}'")

        # Check if ref_photo_column exists (exact match first)
        if ref_photo_column not in excel_data.columns:
            # Try case-insensitive match
            column_mapping = {col.lower().strip(): col for col in excel_data.columns}
            ref_photo_lower = ref_photo_column.lower().strip()

            if ref_photo_lower in column_mapping:
                actual_column = column_mapping[ref_photo_lower]
                print(f"Found case-insensitive match: '{ref_photo_column}' -> '{actual_column}'")
                ref_photo_column = actual_column
            else:
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

                # Extract plant data with fallbacks and flexible column mapping
                plant_data = {
                    'id': str(uuid.uuid4()),
                    'refPhoto': str(ref_photo) if not pd.isna(ref_photo) else f"ref_{index}",
                    'yProj': self._safe_float_convert(
                        self._get_column_value(row, ['y_proj', 'Y_Proj', 'yProj', 'Y', 'Latitude'])),
                    'xProj': self._safe_float_convert(
                        self._get_column_value(row, ['x_proj', 'X_Proj', 'xProj', 'X', 'Longitude'])),
                    'speciesName': str(self._get_column_value(row, ['nom de l\'espèce', 'Species Name', 'speciesName',
                                                                    'Species', 'Name'], 'Unknown Species')),
                    'family': str(self._get_column_value(row, ['famille', 'Family', 'family'], 'Unknown Family')),
                    'formation': str(
                        self._get_column_value(row, ['formation', 'Formation', 'Habitat'], 'Unknown Formation')),
                    'slope': self._safe_float_convert(self._get_column_value(row, ['pente', 'Slope', 'slope'])),
                    'exposure': str(
                        self._get_column_value(row, ['exposition', 'Exposure', 'exposure', 'Aspect'], 'Unknown')),
                    'altitude': self._safe_float_convert(
                        self._get_column_value(row, ['Altitude', 'altitude', 'Elevation'], 0)),
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

    def _get_column_value(self, row, possible_columns: List[str], default=None):
        """Get value from row using multiple possible column names"""
        for col in possible_columns:
            if col in row.index and not pd.isna(row[col]):
                return row[col]
        return default

    def _safe_float_convert(self, value) -> Optional[float]:
        """Safely convert value to float"""
        if pd.isna(value) or value == '' or value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None