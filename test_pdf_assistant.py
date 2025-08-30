#!/usr/bin/env python3

"""
Test Script for PDF Exam Assistant

This script verifies that all components are properly set up and working.
Run this script to ensure your PDF exam assistant is ready to use.
"""

import os
import sys
from datetime import datetime

def test_imports():
    """Test that all required modules can be imported."""
    print("🧪 Testing imports...")
    
    try:
        # Test existing modules
        from bubble_sheet_processor import process_bubble_sheet
        print("  ✅ bubble_sheet_processor imported successfully")
        
        from BubbleSheetCorrecterModule.compare_bubbles import calculate_grade
        print("  ✅ BubbleSheetCorrecterModule.compare_bubbles imported successfully")
        
        # Test new modules
        from pdf_converter import PDFConverter, check_dependencies
        print("  ✅ pdf_converter imported successfully")
        
        from exam_assistant import ExamAssistant
        print("  ✅ exam_assistant imported successfully")
        
        from results_aggregator import ResultsAggregator
        print("  ✅ results_aggregator imported successfully")
        
        return True
        
    except ImportError as e:
        print(f"  ❌ Import failed: {e}")
        return False

def test_dependencies():
    """Test that all dependencies are available."""
    print("\n🔧 Testing dependencies...")
    
    try:
        import cv2
        print(f"  ✅ OpenCV version: {cv2.__version__}")
    except ImportError:
        print("  ❌ OpenCV not available")
        return False
    
    try:
        import numpy as np
        print(f"  ✅ NumPy version: {np.__version__}")
    except ImportError:
        print("  ❌ NumPy not available")
        return False
    
    try:
        import pandas as pd
        print(f"  ✅ Pandas version: {pd.__version__}")
    except ImportError:
        print("  ❌ Pandas not available")
        return False
    
    try:
        import pdf2image
        print("  ✅ pdf2image is available")
    except ImportError:
        print("  ❌ pdf2image not available - run: pip install pdf2image")
        return False
    
    # Test PDF dependencies
    from pdf_converter import check_dependencies
    pdf_deps_ok = check_dependencies()
    if pdf_deps_ok:
        print("  ✅ PDF processing dependencies are available")
    else:
        print("  ❌ PDF processing dependencies missing")
        return False
    
    return True

def test_existing_module_structure():
    """Test that existing module structure is intact."""
    print("\n📁 Testing existing module structure...")
    
    required_files = [
        "BubbleSheetCorrecterModule/aruco_based_exam_model.py",
        "BubbleSheetCorrecterModule/bubble_sheet_reader.py", 
        "BubbleSheetCorrecterModule/compare_bubbles.py",
        "BubbleSheetCorrecterModule/exam_models.json",
        "bubble_sheet_processor.py"
    ]
    
    missing_files = []
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"  ✅ {file_path}")
        else:
            print(f"  ❌ {file_path} - MISSING")
            missing_files.append(file_path)
    
    if missing_files:
        print(f"\n⚠️  Missing required files: {missing_files}")
        return False
    
    return True

def test_pdf_converter():
    """Test PDF converter functionality."""
    print("\n🔄 Testing PDF converter...")
    
    try:
        from pdf_converter import PDFConverter
        
        converter = PDFConverter(dpi=150)  # Low DPI for testing
        print("  ✅ PDF converter initialized successfully")
        
        # Test with a non-existent file to check error handling
        try:
            converter.get_pdf_info("non_existent.pdf")
            print("  ❌ Error handling test failed")
            return False
        except FileNotFoundError:
            print("  ✅ Error handling works correctly")
        
        return True
        
    except Exception as e:
        print(f"  ❌ PDF converter test failed: {e}")
        return False

def test_exam_assistant():
    """Test exam assistant initialization."""
    print("\n🎓 Testing exam assistant...")
    
    try:
        from exam_assistant import ExamAssistant
        
        # Test initialization
        assistant = ExamAssistant(
            dpi=150,
            output_base_dir="test_output", 
            temp_cleanup=True
        )
        print("  ✅ Exam assistant initialized successfully")
        
        # Check available exam models
        print(f"  ✅ Available exam models: {list(assistant.available_exam_models.keys())}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Exam assistant test failed: {e}")
        return False

def test_results_aggregator():
    """Test results aggregator."""
    print("\n📊 Testing results aggregator...")
    
    try:
        from results_aggregator import ResultsAggregator
        
        aggregator = ResultsAggregator()
        print("  ✅ Results aggregator initialized successfully")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Results aggregator test failed: {e}")
        return False

def test_file_structure():
    """Test that all new files are created correctly."""
    print("\n📄 Testing new file structure...")
    
    expected_files = [
        "pdf_converter.py",
        "exam_assistant.py", 
        "results_aggregator.py",
        "example_usage.py",
        "requirements_pdf_assistant.txt",
        "README_PDF_Exam_Assistant.md",
        "test_pdf_assistant.py"  # This file
    ]
    
    missing_files = []
    for file_path in expected_files:
        if os.path.exists(file_path):
            size_kb = round(os.path.getsize(file_path) / 1024, 1)
            print(f"  ✅ {file_path} ({size_kb} KB)")
        else:
            print(f"  ❌ {file_path} - MISSING")
            missing_files.append(file_path)
    
    return len(missing_files) == 0

def print_summary_and_next_steps(all_tests_passed):
    """Print summary and next steps."""
    print("\n" + "=" * 70)
    print("📋 TEST SUMMARY")
    print("=" * 70)
    
    if all_tests_passed:
        print("🎉 ALL TESTS PASSED! Your PDF Exam Assistant is ready to use.")
        print("")
        print("🚀 Next Steps:")
        print("  1. Install any missing dependencies:")
        print("     pip install -r requirements_pdf_assistant.txt")
        print("  2. Install system dependencies (if not already installed):")
        print("     sudo apt-get install poppler-utils  # On Ubuntu/Debian")
        print("  3. Try the example usage script:")
        print("     python example_usage.py")
        print("  4. Place your PDF files and start processing:")
        
        print("\n📖 Quick Start Example:")
        print("```python")
        print("from exam_assistant import ExamAssistant")
        print("assistant = ExamAssistant()")
        print("result = assistant.process_pdf_exam('your_exam.pdf')")
        print("```")
        
    else:
        print("❌ SOME TESTS FAILED!")
        print("")
        print("🔧 Please fix the issues above before using the PDF assistant.")
        print("Common solutions:")
        print("  - Install missing dependencies: pip install -r requirements_pdf_assistant.txt")
        print("  - Install poppler-utils: sudo apt-get install poppler-utils")
        print("  - Ensure all existing BubbleSheetCorrecterModule files are present")
    
    print("=" * 70)

def main():
    """Run all tests."""
    print("🎓 PDF Exam Assistant Test Suite")
    print("=" * 70)
    print(f"📅 Test run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📁 Working directory: {os.getcwd()}")
    print("=" * 70)
    
    # Run all tests
    tests = [
        test_existing_module_structure,
        test_imports,
        test_dependencies,
        test_pdf_converter,
        test_exam_assistant,
        test_results_aggregator,
        test_file_structure
    ]
    
    test_results = []
    for test_func in tests:
        try:
            result = test_func()
            test_results.append(result)
        except Exception as e:
            print(f"❌ Test {test_func.__name__} crashed: {e}")
            test_results.append(False)
    
    # Calculate results
    passed_tests = sum(test_results)
    total_tests = len(test_results)
    all_tests_passed = all(test_results)
    
    print(f"\n📊 Test Results: {passed_tests}/{total_tests} passed")
    
    # Print summary and next steps
    print_summary_and_next_steps(all_tests_passed)
    
    return all_tests_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
