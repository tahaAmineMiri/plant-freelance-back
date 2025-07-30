#!/usr/bin/env python3
"""
Development runner script for the Plant Database API
"""
import uvicorn
import os
from pathlib import Path


def create_directories():
    """Create necessary directories"""
    directories = [
        "uploads/excel",
        "uploads/images",
        "processed_data",
        "static/images"
    ]

    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✓ Created directory: {directory}")


def main():
    print("🌱 Starting Plant Database API Development Server")
    print("=" * 50)

    # Create directories
    create_directories()

    # Configuration
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", 8000))

    print(f"🚀 Server will start at: http://{host}:{port}")
    print(f"📚 API Documentation: http://{host}:{port}/docs")
    print(f"🔧 ReDoc Documentation: http://{host}:{port}/redoc")
    print("=" * 50)

    # Start server
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        reload_dirs=["./"],
        log_level="info"
    )


if __name__ == "__main__":
    main()