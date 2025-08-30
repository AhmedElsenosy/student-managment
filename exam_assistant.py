#!/usr/bin/env python3

import os
import cv2
import json
import csv
import shutil
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import tempfile

# Import existing modules (no modifications needed)
from pdf_converter import PDFConverter, check_dependencies as check_pdf_dependencies
from bubble_sheet_processor import process_bubble_sheet, print_processing_summary
from BubbleSheetCorrecterModule.compare_bubbles import calculate_grade

class ExamAssistant:
    """
    Main exam assistant that processes PDF files containing bubble sheet exams.
    Supports multiple exam models (A, B, C) and handles batch processing.
    """
    
    def __init__(self, 
                 dpi: int = 300,
                 output_base_dir: str = "exam_results",
                 temp_cleanup: bool = True):
        """
        Initialize the exam assistant.
        
        Args:
            dpi: DPI for PDF to image conversion
            output_base_dir: Base directory for saving results
            temp_cleanup: Whether to clean up temporary files
        """
        self.pdf_converter = PDFConverter(dpi=dpi)
        self.output_base_dir = output_base_dir
        self.temp_cleanup = temp_cleanup
        
        # Create output directory
        os.makedirs(output_base_dir, exist_ok=True)
        
        # Available exam models from the existing system
        self.available_exam_models = {
            'A': 'exam_model_1',
            'B': 'exam_model_2', 
            'C': 'exam_model_3'
        }
        
        print(f"🎓 Exam Assistant initialized")
        print(f"   Output directory: {os.path.abspath(output_base_dir)}")
        print(f"   Available exam models: {list(self.available_exam_models.keys())}")
    
    def process_pdf_exam(self, 
                        pdf_path: str,
                        exam_models: Optional[List[str]] = None,
                        custom_output_dir: Optional[str] = None) -> Dict:
        """
        Process a PDF containing bubble sheet exams.
        
        Args:
            pdf_path: Path to the PDF file
            exam_models: List of exam models to try (default: ['A', 'B', 'C'])
            custom_output_dir: Custom output directory for this batch
            
        Returns:
            Dictionary with processing results
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        if exam_models is None:
            exam_models = ['A', 'B', 'C']
        
        # Validate exam models
        invalid_models = [m for m in exam_models if m not in self.available_exam_models]
        if invalid_models:
            raise ValueError(f"Invalid exam models: {invalid_models}. Available: {list(self.available_exam_models.keys())}")
        
        # Create session output directory
        pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = custom_output_dir or os.path.join(self.output_base_dir, f"{pdf_name}_{timestamp}")
        os.makedirs(session_dir, exist_ok=True)
        
        print(f"\n🚀 Processing PDF: {pdf_name}")
        print(f"📁 Session directory: {session_dir}")
        print(f"🎯 Exam models to try: {exam_models}")
        print("=" * 70)
        
        try:
            # Get PDF info
            pdf_info = self.pdf_converter.get_pdf_info(pdf_path)
            print(f"📄 PDF Info:")
            print(f"   Pages: {pdf_info['total_pages']}")
            print(f"   Size: {pdf_info['file_size_mb']} MB")
            print(f"   First page: {pdf_info['first_page_size'][0]}x{pdf_info['first_page_size'][1]} pixels")
            
            # Convert PDF to images
            temp_dir = tempfile.mkdtemp(prefix="exam_processing_")
            
            try:
                image_paths = self.pdf_converter.convert_pdf_to_images(pdf_path, temp_dir)
                
                # Process each page
                all_results = []
                successful_pages = 0
                
                for i, image_path in enumerate(image_paths):
                    page_num = i + 1
                    print(f"\n📖 Processing Page {page_num}/{len(image_paths)}")
                    print("-" * 50)
                    
                    # Load image
                    image = cv2.imread(image_path)
                    if image is None:
                        print(f"❌ Could not load image: {image_path}")
                        continue
                    
                    # Try each exam model until one works
                    page_result = None
                    for model in exam_models:
                        print(f"🔍 Trying exam model {model}...")
                        
                        try:
                            model_key = self.available_exam_models[model]
                            result = process_bubble_sheet(
                                image,
                                exam_model_key=model_key,
                                output_dir=os.path.join(session_dir, f"page_{page_num:03d}")
                            )
                            
                            if result['success']:
                                print(f"✅ Successfully processed with model {model}")
                                result['page_number'] = page_num
                                result['exam_model_used'] = model
                                result['image_source'] = os.path.basename(image_path)
                                page_result = result
                                successful_pages += 1
                                break
                            else:
                                print(f"⚠️ Model {model} failed: {result['message']}")
                                
                        except Exception as e:
                            print(f"❌ Error with model {model}: {str(e)}")
                            continue
                    
                    if page_result:
                        all_results.append(page_result)
                        # Print summary for this page
                        if page_result['results']:
                            self._print_page_summary(page_num, page_result)
                    else:
                        print(f"❌ Page {page_num} could not be processed with any model")
                        all_results.append({
                            'page_number': page_num,
                            'success': False,
                            'message': 'No suitable exam model found',
                            'exam_model_used': None
                        })
                
                # Generate comprehensive report
                report = self._generate_comprehensive_report(all_results, pdf_info, session_dir)
                
                print(f"\n" + "=" * 70)
                print(f"📊 FINAL RESULTS")
                print(f"=" * 70)
                print(f"✅ Successfully processed: {successful_pages}/{len(image_paths)} pages")
                print(f"📁 Results saved to: {session_dir}")
                print(f"📋 Summary report: {report['summary_file']}")
                
                return {
                    'success': True,
                    'pdf_info': pdf_info,
                    'total_pages': len(image_paths),
                    'successful_pages': successful_pages,
                    'session_directory': session_dir,
                    'page_results': all_results,
                    'comprehensive_report': report
                }
                
            finally:
                # Cleanup temporary files
                if self.temp_cleanup and os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                    print(f"🧹 Cleaned up temporary files: {temp_dir}")
        
        except Exception as e:
            error_msg = f"Error processing PDF: {str(e)}"
            print(f"❌ {error_msg}")
            return {
                'success': False,
                'message': error_msg,
                'session_directory': session_dir
            }
    
    def _print_page_summary(self, page_num: int, result: Dict):
        """Print a summary for a single page."""
        if not result.get('results'):
            return
            
        summary = result['results']['summary']
        print(f"   📋 Questions: {summary['total_questions']}")
        print(f"   ✅ Answered: {summary['questions_answered']}")
        print(f"   🔄 Multiple: {summary['multiple_answers']}")
        print(f"   ❌ Blank: {summary['unanswered']}")
        print(f"   📈 Completion: {summary['completion_rate']}%")
        
        if 'exam_model' in summary:
            em = summary['exam_model']
            status = "✅" if em['is_valid'] else "⚠️"
            print(f"   📝 Model: {em['value']} {status}")
        
        if 'student_id' in summary:
            sid = summary['student_id']
            status = "✅" if sid['is_complete'] else "⚠️"
            print(f"   🆔 ID: {sid['value']} {status}")
    
    def _generate_comprehensive_report(self, results: List[Dict], pdf_info: Dict, session_dir: str) -> Dict:
        """Generate a comprehensive report for all processed pages."""
        
        # Create summary CSV
        summary_file = os.path.join(session_dir, "exam_summary.csv")
        detailed_file = os.path.join(session_dir, "detailed_answers.csv")
        
        with open(summary_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow(['Exam Processing Summary'])
            writer.writerow(['Generated:', datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
            writer.writerow(['PDF:', pdf_info['file_path']])
            writer.writerow(['Total Pages:', pdf_info['total_pages']])
            writer.writerow([])
            
            # Page summary
            writer.writerow(['Page', 'Status', 'Model Used', 'Questions', 'Answered', 'Multiple', 'Blank', 'Completion%', 'Exam Model', 'Student ID'])
            
            for result in results:
                if result['success'] and result.get('results'):
                    summary = result['results']['summary']
                    row = [
                        result['page_number'],
                        'SUCCESS',
                        result['exam_model_used'],
                        summary['total_questions'],
                        summary['questions_answered'],
                        summary['multiple_answers'],
                        summary['unanswered'],
                        summary['completion_rate']
                    ]
                    
                    # Add exam model info
                    if 'exam_model' in summary:
                        row.append(f"{summary['exam_model']['value']} ({'Valid' if summary['exam_model']['is_valid'] else 'Invalid'})")
                    else:
                        row.append('N/A')
                    
                    # Add student ID info
                    if 'student_id' in summary:
                        row.append(f"{summary['student_id']['value']} ({'Complete' if summary['student_id']['is_complete'] else 'Incomplete'})")
                    else:
                        row.append('N/A')
                    
                    writer.writerow(row)
                else:
                    writer.writerow([
                        result['page_number'],
                        'FAILED',
                        'N/A',
                        'N/A',
                        'N/A',
                        'N/A',
                        'N/A',
                        'N/A',
                        'N/A',
                        'N/A'
                    ])
        
        # Create detailed answers CSV
        with open(detailed_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Page', 'Question', 'Answer', 'A_Fill%', 'B_Fill%', 'C_Fill%', 'D_Fill%', 'E_Fill%', 'Student_ID', 'Exam_Model'])
            
            for result in results:
                if result['success'] and result.get('results'):
                    page_num = result['page_number']
                    grade_data = result['results']['grade_data']
                    summary = result['results']['summary']
                    
                    student_id = summary.get('student_id', {}).get('value', 'N/A')
                    exam_model = summary.get('exam_model', {}).get('value', 'N/A')
                    
                    for answer in grade_data['answers']:
                        fills = answer['fill_percentages'] + [0] * (5 - len(answer['fill_percentages']))  # Pad to 5 columns
                        writer.writerow([
                            page_num,
                            answer['question'],
                            answer['answer'] or 'BLANK',
                            f"{fills[0]:.1f}%",
                            f"{fills[1]:.1f}%",
                            f"{fills[2]:.1f}%",
                            f"{fills[3]:.1f}%",
                            f"{fills[4]:.1f}%",
                            student_id,
                            exam_model
                        ])
        
        return {
            'summary_file': summary_file,
            'detailed_file': detailed_file,
            'session_directory': session_dir
        }
    
    def get_processing_statistics(self, session_dir: str) -> Dict:
        """Get processing statistics for a session."""
        summary_file = os.path.join(session_dir, "exam_summary.csv")
        if not os.path.exists(summary_file):
            return {'error': 'Summary file not found'}
        
        # Read summary file and calculate statistics
        stats = {
            'total_pages': 0,
            'successful_pages': 0,
            'failed_pages': 0,
            'exam_models_used': {},
            'total_questions_processed': 0,
            'average_completion_rate': 0
        }
        
        try:
            with open(summary_file, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                rows = list(reader)
                
                # Find data rows (after headers)
                data_start = -1
                for i, row in enumerate(rows):
                    if len(row) > 0 and row[0] == 'Page':
                        data_start = i + 1
                        break
                
                if data_start > 0:
                    completion_rates = []
                    for row in rows[data_start:]:
                        if len(row) >= 8:
                            stats['total_pages'] += 1
                            if row[1] == 'SUCCESS':
                                stats['successful_pages'] += 1
                                model = row[2]
                                stats['exam_models_used'][model] = stats['exam_models_used'].get(model, 0) + 1
                                
                                try:
                                    completion_rate = float(row[7])
                                    completion_rates.append(completion_rate)
                                    stats['total_questions_processed'] += int(row[3])
                                except (ValueError, IndexError):
                                    pass
                            else:
                                stats['failed_pages'] += 1
                    
                    if completion_rates:
                        stats['average_completion_rate'] = round(sum(completion_rates) / len(completion_rates), 1)
        
        except Exception as e:
            stats['error'] = str(e)
        
        return stats

def main():
    """Example usage of the exam assistant."""
    print("🎓 Bubble Sheet Exam Assistant")
    print("=" * 50)
    
    # Check dependencies
    if not check_pdf_dependencies():
        print("❌ Required dependencies not available")
        return
    
    # Initialize assistant
    assistant = ExamAssistant(
        dpi=300,
        output_base_dir="exam_results",
        temp_cleanup=True
    )
    
    # Example: process a PDF file
    pdf_file = input("Enter path to PDF file (or press Enter to skip): ").strip()
    
    if pdf_file and os.path.exists(pdf_file):
        print(f"\n🚀 Processing: {pdf_file}")
        
        # Ask which models to try
        models_input = input("Enter exam models to try (A,B,C or press Enter for all): ").strip()
        exam_models = None
        if models_input:
            exam_models = [m.strip().upper() for m in models_input.split(',')]
        
        result = assistant.process_pdf_exam(pdf_file, exam_models)
        
        if result['success']:
            print("\n✅ Processing completed successfully!")
            
            # Show statistics
            stats = assistant.get_processing_statistics(result['session_directory'])
            print(f"\n📊 Statistics:")
            print(f"   Successful pages: {stats.get('successful_pages', 0)}/{stats.get('total_pages', 0)}")
            print(f"   Models used: {stats.get('exam_models_used', {})}")
            print(f"   Average completion rate: {stats.get('average_completion_rate', 0)}%")
        else:
            print(f"\n❌ Processing failed: {result['message']}")
    else:
        print("📝 No PDF file provided or file not found")
        print("💡 You can use assistant.process_pdf_exam('/path/to/your/exam.pdf') programmatically")

if __name__ == "__main__":
    main()
