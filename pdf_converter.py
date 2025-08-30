#!/usr/bin/env python3

import os
import cv2
import numpy as np
from pdf2image import convert_from_path
from typing import List, Optional, Tuple
import tempfile

class PDFConverter:
    """
    Converts PDF pages to images for bubble sheet processing.
    """
    
    def __init__(self, dpi: int = 300, format: str = 'PNG'):
        """
        Initialize PDF converter.
        
        Args:
            dpi: DPI for PDF to image conversion (higher = better quality, larger files)
            format: Image format for conversion (PNG, JPEG, etc.)
        """
        self.dpi = dpi
        self.format = format.upper()
        
    def convert_pdf_to_images(self, pdf_path: str, output_dir: Optional[str] = None) -> List[str]:
        """
        Convert PDF to individual page images.
        
        Args:
            pdf_path: Path to the PDF file
            output_dir: Directory to save images (if None, uses temp directory)
            
        Returns:
            List of image file paths
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        # Create output directory if not provided
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="pdf_conversion_")
        else:
            os.makedirs(output_dir, exist_ok=True)
        
        print(f"Converting PDF to images at {self.dpi} DPI...")
        print(f"PDF: {pdf_path}")
        print(f"Output directory: {output_dir}")
        
        try:
            # Convert PDF to images
            pages = convert_from_path(
                pdf_path,
                dpi=self.dpi,
                fmt=self.format.lower(),
                thread_count=4  # Use multiple threads for faster conversion
            )
            
            image_paths = []
            pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
            
            for i, page in enumerate(pages):
                # Save each page as an image
                image_filename = f"{pdf_name}_page_{i+1:03d}.{self.format.lower()}"
                image_path = os.path.join(output_dir, image_filename)
                
                page.save(image_path, self.format)
                image_paths.append(image_path)
                
                print(f"  Page {i+1:2d}: {image_filename}")
            
            print(f"✅ Converted {len(pages)} pages successfully!")
            return image_paths
            
        except Exception as e:
            print(f"❌ Error converting PDF: {str(e)}")
            raise
    
    def convert_pdf_to_cv2_images(self, pdf_path: str) -> List[np.ndarray]:
        """
        Convert PDF directly to OpenCV images in memory.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            List of OpenCV images (numpy arrays)
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        print(f"Converting PDF to OpenCV images at {self.dpi} DPI...")
        print(f"PDF: {pdf_path}")
        
        try:
            # Convert PDF to images
            pages = convert_from_path(
                pdf_path,
                dpi=self.dpi,
                fmt='RGB',
                thread_count=4
            )
            
            cv2_images = []
            
            for i, page in enumerate(pages):
                # Convert PIL image to numpy array
                img_array = np.array(page)
                
                # Convert RGB to BGR (OpenCV format)
                cv2_image = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                cv2_images.append(cv2_image)
                
                print(f"  Page {i+1:2d}: {cv2_image.shape[1]}x{cv2_image.shape[0]} pixels")
            
            print(f"✅ Converted {len(pages)} pages to OpenCV format!")
            return cv2_images
            
        except Exception as e:
            print(f"❌ Error converting PDF: {str(e)}")
            raise
    
    def get_pdf_info(self, pdf_path: str) -> dict:
        """
        Get basic information about the PDF.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Dictionary with PDF information
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        try:
            # Convert just first page to get basic info
            pages = convert_from_path(pdf_path, dpi=72, last_page=1)  # Low DPI for quick info
            
            if pages:
                first_page = pages[0]
                
                # Get total page count by converting again (inefficient but works)
                all_pages = convert_from_path(pdf_path, dpi=72)
                
                return {
                    'file_path': pdf_path,
                    'file_size_mb': round(os.path.getsize(pdf_path) / (1024 * 1024), 2),
                    'total_pages': len(all_pages),
                    'first_page_size': first_page.size,  # (width, height)
                    'estimated_conversion_size_mb': round(
                        (first_page.size[0] * first_page.size[1] * 3 * len(all_pages) * (self.dpi/72)**2) / (1024 * 1024), 2
                    )
                }
        except Exception as e:
            print(f"❌ Error getting PDF info: {str(e)}")
            raise

def check_dependencies():
    """Check if required dependencies are available."""
    try:
        import pdf2image
        print("✅ pdf2image is available")
        return True
    except ImportError:
        print("❌ pdf2image not found. Please install it with:")
        print("   sudo apt-get install poppler-utils")
        print("   pip install pdf2image")
        return False

if __name__ == "__main__":
    # Test the converter
    if check_dependencies():
        converter = PDFConverter(dpi=300)
        
        # Example usage
        test_pdf = "/path/to/your/test.pdf"  # Replace with actual PDF path
        if os.path.exists(test_pdf):
            info = converter.get_pdf_info(test_pdf)
            print("PDF Info:", info)
            
            # Convert to images
            image_paths = converter.convert_pdf_to_images(test_pdf)
            print("Generated images:", image_paths[:3], "..." if len(image_paths) > 3 else "")
        else:
            print(f"Test PDF not found: {test_pdf}")
