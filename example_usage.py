#!/usr/bin/env python3

"""
Example Usage Script for PDF Exam Assistant

This script demonstrates how to use the PDF Exam Assistant to process
bubble sheet exams from PDF files using the existing BubbleSheetCorrecterModule.

Features demonstrated:
1. Processing single PDF files
2. Batch processing multiple PDFs
3. Generating comprehensive reports
4. Analyzing results with advanced statistics

Requirements:
- All existing BubbleSheetCorrecterModule files (no modifications needed)
- bubble_sheet_processor.py (existing file)
- pdf_converter.py (new)
- exam_assistant.py (new)
- results_aggregator.py (new)
- pdf2image library: pip install pdf2image
- poppler-utils: sudo apt-get install poppler-utils (on Ubuntu)
"""

import os
import sys
from datetime import datetime

# Import the PDF exam assistant modules
from pdf_converter import PDFConverter, check_dependencies as check_pdf_deps
from exam_assistant import ExamAssistant
from results_aggregator import ResultsAggregator

def example_single_pdf_processing():
    """Example 1: Process a single PDF file with all 3 exam models."""
    
    print("🎓 Example 1: Single PDF Processing")
    print("=" * 50)
    
    # Check if we have the required dependencies
    if not check_pdf_deps():
        print("❌ PDF processing dependencies not available")
        print("Please install: pip install pdf2image")
        print("And on Ubuntu: sudo apt-get install poppler-utils")
        return
    
    # Initialize the exam assistant
    assistant = ExamAssistant(
        dpi=300,                    # High quality conversion
        output_base_dir="exam_results",  # Where to save results
        temp_cleanup=True           # Clean up temporary files
    )
    
    # Example PDF file path - replace with your actual PDF
    pdf_file = "sample_exam.pdf"
    
    if not os.path.exists(pdf_file):
        print(f"📄 PDF file '{pdf_file}' not found.")
        print("Please place a PDF file with bubble sheets in the current directory")
        print("or modify the path in this example script.")
        return
    
    # Process the PDF with all available exam models (A, B, C)
    print(f"🚀 Processing: {pdf_file}")
    result = assistant.process_pdf_exam(
        pdf_path=pdf_file,
        exam_models=['A', 'B', 'C'],  # Try all models
        custom_output_dir=None        # Use default naming
    )
    
    if result['success']:
        print("✅ Processing completed successfully!")
        print(f"📁 Results saved to: {result['session_directory']}")
        print(f"📊 Processed: {result['successful_pages']}/{result['total_pages']} pages")
        
        # Show some statistics
        stats = assistant.get_processing_statistics(result['session_directory'])
        print(f"📈 Average completion rate: {stats.get('average_completion_rate', 0)}%")
        print(f"🎯 Models used: {stats.get('exam_models_used', {})}")
        
        return result['session_directory']
    else:
        print(f"❌ Processing failed: {result['message']}")
        return None

def example_batch_processing():
    """Example 2: Process multiple PDF files in a directory."""
    
    print("\n🎓 Example 2: Batch PDF Processing")
    print("=" * 50)
    
    # Initialize assistant
    assistant = ExamAssistant(dpi=300, output_base_dir="batch_exam_results")
    
    # Directory containing PDF files
    pdf_directory = "exam_pdfs"
    
    if not os.path.exists(pdf_directory):
        print(f"📁 Directory '{pdf_directory}' not found.")
        print("Create this directory and add PDF files to test batch processing.")
        return []
    
    # Find all PDF files
    pdf_files = [f for f in os.listdir(pdf_directory) if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        print(f"📄 No PDF files found in '{pdf_directory}'")
        return []
    
    print(f"Found {len(pdf_files)} PDF files:")
    for i, pdf_file in enumerate(pdf_files[:5], 1):  # Show first 5
        print(f"  {i}. {pdf_file}")
    if len(pdf_files) > 5:
        print(f"  ... and {len(pdf_files) - 5} more")
    
    session_directories = []
    
    # Process each PDF
    for i, pdf_file in enumerate(pdf_files, 1):
        pdf_path = os.path.join(pdf_directory, pdf_file)
        print(f"\n📖 Processing {i}/{len(pdf_files)}: {pdf_file}")
        print("-" * 40)
        
        result = assistant.process_pdf_exam(
            pdf_path=pdf_path,
            exam_models=['A', 'B', 'C'],  # Try all models
            custom_output_dir=None
        )
        
        if result['success']:
            session_directories.append(result['session_directory'])
            print(f"✅ {pdf_file}: {result['successful_pages']}/{result['total_pages']} pages processed")
        else:
            print(f"❌ {pdf_file}: {result['message']}")
    
    print(f"\n📊 Batch processing complete!")
    print(f"Successfully processed: {len(session_directories)}/{len(pdf_files)} PDFs")
    
    return session_directories

def example_advanced_reporting(session_directories):
    """Example 3: Generate advanced reports and statistics."""
    
    print("\n🎓 Example 3: Advanced Reporting")
    print("=" * 50)
    
    if not session_directories:
        print("📋 No session directories provided for analysis")
        return
    
    # Initialize the results aggregator
    aggregator = ResultsAggregator()
    
    if len(session_directories) == 1:
        # Single session analysis
        session_dir = session_directories[0]
        print(f"📈 Analyzing single session: {os.path.basename(session_dir)}")
        
        try:
            results = aggregator.aggregate_session_results(session_dir)
            
            # Print overview
            overview = results['overview']
            print(f"  📊 Total pages: {overview['total_pages']}")
            print(f"  ✅ Success rate: {overview['success_rate_percent']}%")
            
            # Print completion analysis
            completion = results['completion_analysis']
            print(f"  📈 Average completion: {completion['average_completion_rate']}%")
            
            # Print exam model analysis
            models = results['exam_model_analysis']
            if models['model_distribution']:
                print(f"  🎯 Most used model: {models['most_common_model']}")
            
            # Print quality metrics
            quality = results['quality_metrics']
            print(f"  🏆 Overall quality score: {quality['overall_quality_score']}/100")
            
            # Generate comprehensive Excel report
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            excel_file = f"comprehensive_report_{timestamp}.xlsx"
            aggregator.generate_comprehensive_report(results, excel_file)
            print(f"  📊 Excel report generated: {excel_file}")
            
        except Exception as e:
            print(f"❌ Error analyzing session: {e}")
    
    else:
        # Multi-session comparison
        print(f"📊 Comparing {len(session_directories)} sessions...")
        
        try:
            comparison = aggregator.compare_multiple_sessions(session_directories)
            
            # Print session summaries
            print("\n📋 Session Summary:")
            for summary in comparison['session_summaries'][:10]:  # Show first 10
                print(f"  {summary['name']}: "
                      f"{summary['successful_pages']}/{summary['total_pages']} pages "
                      f"({summary['success_rate']:.1f}%), "
                      f"avg completion: {summary['avg_completion']:.1f}%")
            
            if len(comparison['session_summaries']) > 10:
                remaining = len(comparison['session_summaries']) - 10
                print(f"  ... and {remaining} more sessions")
            
            # Print aggregate statistics
            print(f"\n📊 Overall Statistics:")
            stats = comparison['aggregate_stats']
            print(f"  📄 Total pages processed: {stats['total_pages_all_sessions']}")
            print(f"  ✅ Overall success rate: {stats['overall_success_rate']:.1f}%")
            print(f"  📈 Average completion rate: {stats['average_completion_rate_all_sessions']:.1f}%")
            print(f"  🎯 Models used: {', '.join(stats['unique_models_used'])}")
            
            if stats['most_popular_model']:
                print(f"  👑 Most popular model: {stats['most_popular_model']}")
            
        except Exception as e:
            print(f"❌ Error comparing sessions: {e}")

def example_specific_model_processing():
    """Example 4: Process PDF with specific exam models only."""
    
    print("\n🎓 Example 4: Specific Model Processing")
    print("=" * 50)
    
    # Initialize assistant
    assistant = ExamAssistant()
    
    # Example: process only with models A and B
    pdf_file = "model_a_b_exam.pdf"
    
    if not os.path.exists(pdf_file):
        print(f"📄 PDF file '{pdf_file}' not found - skipping this example")
        return
    
    print(f"🎯 Processing with models A and B only: {pdf_file}")
    
    result = assistant.process_pdf_exam(
        pdf_path=pdf_file,
        exam_models=['A', 'B'],  # Only try models A and B
        custom_output_dir=f"specific_model_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    
    if result['success']:
        print("✅ Specific model processing completed!")
        print(f"📊 Results: {result['successful_pages']}/{result['total_pages']} pages")
        
        # Show which models were actually used
        stats = assistant.get_processing_statistics(result['session_directory'])
        models_used = stats.get('exam_models_used', {})
        print(f"🎯 Models actually used: {models_used}")
    else:
        print(f"❌ Processing failed: {result['message']}")

def main():
    """Run all examples."""
    
    print("🎓 PDF Exam Assistant - Usage Examples")
    print("=" * 70)
    print("This script demonstrates various ways to use the PDF exam assistant.")
    print("The assistant works with your existing BubbleSheetCorrecterModule")
    print("without requiring any modifications to the existing code.")
    print("=" * 70)
    
    # Check current working directory
    print(f"📁 Current directory: {os.getcwd()}")
    print(f"📄 Available files: {[f for f in os.listdir('.') if f.endswith(('.pdf', '.py'))]}")
    
    session_dirs = []
    
    # Example 1: Single PDF processing
    session_dir = example_single_pdf_processing()
    if session_dir:
        session_dirs.append(session_dir)
    
    # Example 2: Batch processing (if directory exists)
    batch_sessions = example_batch_processing()
    session_dirs.extend(batch_sessions)
    
    # Example 3: Advanced reporting
    if session_dirs:
        example_advanced_reporting(session_dirs)
    
    # Example 4: Specific model processing
    example_specific_model_processing()
    
    # Summary
    print(f"\n" + "=" * 70)
    print("📋 SUMMARY")
    print("=" * 70)
    print("The PDF Exam Assistant provides these key features:")
    print("  ✅ Automatic PDF to image conversion")
    print("  🎯 Support for multiple exam models (A, B, C)")
    print("  📊 Comprehensive statistics and reporting")
    print("  🔄 Batch processing capabilities")
    print("  📁 Organized output with timestamps")
    print("  🧹 Automatic cleanup of temporary files")
    print("")
    print("All existing BubbleSheetCorrecterModule functionality is preserved!")
    print("The assistant only adds PDF handling on top of your existing system.")
    print("")
    if session_dirs:
        print(f"✅ Generated {len(session_dirs)} processing sessions")
        print("Check the 'exam_results' directory for detailed outputs.")
    else:
        print("💡 Add PDF files to test the examples with real data.")
    
    print("=" * 70)

if __name__ == "__main__":
    main()
