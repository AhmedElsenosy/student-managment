#!/usr/bin/env python3

import cv2
import numpy as np
import json
import csv
import os
from dotenv import load_dotenv
from datetime import datetime
from BubbleSheetCorrecterModule.compare_bubbles import highlight_reference_bubbles, create_visualization, calculate_grade
from BubbleSheetCorrecterModule.bubble_edge_detector import detect_aruco_markers, compare_with_reference
from BubbleSheetCorrecterModule.aruco_based_exam_model import calculate_exam_model_positions_from_aruco, detect_bubble_contour_at_position

load_dotenv()

def process_bubble_sheet(image, 
                        reference_data_file='BubbleSheetCorrecterModule/reference_data.json',
                        id_reference_file='BubbleSheetCorrecterModule/id_coordinates.json', 
                        exam_models_file='BubbleSheetCorrecterModule/exam_models.json',
                        exam_model_key='exam_model_aruco',
                        output_dir='BubbleSheetCorrecterModule/results'):
    """
    Complete bubble sheet processing function.
    
    Args:
        image_path: Path to the bubble sheet image
        reference_data_file: Path to reference data JSON
        id_reference_file: Path to ID coordinates JSON  
        exam_models_file: Path to exam models JSON
        exam_model_key: Which exam model to use
        output_dir: Directory to save output files
        
    Returns:
        dict: {
            'visualization_image': cv2 image array,
            'results': dict with detailed results,
            'csv_path': path to generated CSV file,
            'json_path': path to generated JSON file
        }
    """
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate base Name from input image
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"Processing bubble sheet")
    print("=" * 60)
    
    try:
        # Load reference data files
        with open(reference_data_file, 'r') as f:
            reference_data = json.load(f)
        
        # Load ID reference data if available
        id_reference_data = None
        if os.path.exists(id_reference_file):
            with open(id_reference_file, 'r') as f:
                id_reference_data = json.load(f)
        
        # Load exam model reference data if available
        exam_model_reference_data = None
        if os.path.exists(exam_models_file):
            with open(exam_models_file, 'r') as f:
                exam_models_data = json.load(f)
                
            if exam_model_key in exam_models_data:
                exam_model_reference_data = exam_models_data[exam_model_key]
                print(f"Using exam model: {exam_model_key}")
            else:
                print(f"Exam model '{exam_model_key}' not found")
        
        # Load and align the image
        if image is None:
            raise ValueError(f"Could not load image")

        print(f"Image loaded: {image.shape[1]}x{image.shape[0]} pixels")
        
        # Align image with reference using ArUco markers
        aligned_image, transform = compare_with_reference(image, reference_data_file)
        print("Image aligned using ArUco markers")
        
        # Create visualization and get detailed grade data
        vis_image, grade_data = create_visualization(
            aligned_image, 
            reference_data, 
            id_reference_data, 
            exam_model_reference_data, 
            transform
        )
        
        # Enhance results with additional metadata
        results = {
            'metadata': {
                
                'processing_timestamp': datetime.now().isoformat(),
                'image_dimensions': {
                    'width': image.shape[1],
                    'height': image.shape[0]
                },
                'reference_files': {
                    'reference_data': reference_data_file,
                    'id_reference': id_reference_file if id_reference_data else None,
                    'exam_models': exam_models_file if exam_model_reference_data else None,
                    'exam_model_key': exam_model_key if exam_model_reference_data else None
                }
            },
            'grade_data': grade_data,
            'summary': {
                'total_questions': grade_data['total_questions'],
                'questions_answered': grade_data['statistics']['total_answered'],
                'multiple_answers': grade_data['statistics']['multiple_answers'],
                'unanswered': grade_data['statistics']['unanswered'],
                'completion_rate': round((grade_data['statistics']['total_answered'] / grade_data['total_questions']) * 100, 1) if grade_data['total_questions'] > 0 else 0
            }
        }
        
        # Add exam model summary if available
        if 'exam_model' in grade_data:
            results['summary']['exam_model'] = {
                'value': grade_data['exam_model']['value'],
                'is_valid': grade_data['exam_model']['is_valid'],
                'fill_percentages': grade_data['exam_model']['fill_percentages']
            }
        
        # Add ID summary if available
        if 'id' in grade_data:
            results['summary']['student_id'] = {
                'value': grade_data['id']['value'],
                'is_complete': grade_data['id']['is_complete']
            }
        
        if os.getenv('SAVE_RESULTS', 'false').lower() == 'true':
            # Save detailed JSON results
            json_path = os.path.join(output_dir, f"results_{timestamp}.json")
            with open(json_path, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"Detailed results saved: {json_path}")
            
            # Create comprehensive CSV file
            csv_path = os.path.join(output_dir, f"grades_{timestamp}.csv")
            create_comprehensive_csv(results, csv_path)
            print(f"Grade CSV saved: {csv_path}")
            
            # Save visualization image
            vis_path = os.path.join(output_dir, f"visualization_{timestamp}.jpg")
            cv2.imwrite(vis_path, vis_image)
            print(f"Visualization saved: {vis_path}")
            
        print("=" * 60)
        print("✅ Processing completed successfully!")
        
        return {
            'visualization_image': vis_image,
            'results': results,
            'csv_path': [csv_path if os.getenv('SAVE_RESULTS', 'false').lower() == 'true' else None],
            'json_path': [json_path if os.getenv('SAVE_RESULTS', 'false').lower() == 'true' else None],
            'visualization_path': [vis_path if os.getenv('SAVE_RESULTS', 'false').lower() == 'true' else None],
            'success': True,
            'message': 'Processing completed successfully'
        }
        
    except Exception as e:
        error_msg = f"Error processing bubble sheet: {str(e)}"
        print(f"❌ {error_msg}")
        
        return {
            'visualization_image': None,
            'results': None,
            'csv_path': None,
            'json_path': None,
            'visualization_path': None,
            'success': False,
            'message': error_msg
        }

def create_comprehensive_csv(results, csv_path):
    """Create a comprehensive CSV file with all grade information."""
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Header information
        writer.writerow(['Bubble Sheet Processing Results'])
        writer.writerow(['Processed at:', results['metadata']['processing_timestamp']])
        writer.writerow([])  # Empty row
        
        # Summary section
        writer.writerow(['SUMMARY'])
        writer.writerow(['Total questions:', results['summary']['total_questions']])
        writer.writerow(['Questions answered:', results['summary']['questions_answered']])
        writer.writerow(['Multiple answers:', results['summary']['multiple_answers']])
        writer.writerow(['Unanswered:', results['summary']['unanswered']])
        writer.writerow(['Completion rate:', f"{results['summary']['completion_rate']}%"])
        writer.writerow([])  # Empty row
        
        # Exam model section
        if 'exam_model' in results['summary']:
            writer.writerow(['EXAM MODEL'])
            writer.writerow(['Selected model:', results['summary']['exam_model']['value']])
            writer.writerow(['Is valid:', 'Yes' if results['summary']['exam_model']['is_valid'] else 'No'])
            fill_percentages = results['summary']['exam_model']['fill_percentages']
            for i, fill in enumerate(fill_percentages):
                model_letter = chr(65 + i)  # A, B, C, etc.
                writer.writerow([f'Model {model_letter} fill:', f'{fill:.1f}%'])
            writer.writerow([])  # Empty row
        
        # Student ID section
        if 'student_id' in results['summary']:
            writer.writerow(['STUDENT ID'])
            writer.writerow(['ID number:', results['summary']['student_id']['value']])
            writer.writerow(['Is complete:', 'Yes' if results['summary']['student_id']['is_complete'] else 'No'])
            writer.writerow([])  # Empty row
        
        # Detailed answers section
        writer.writerow(['DETAILED ANSWERS'])
        writer.writerow(['Question', 'Answer', 'A_Fill%', 'B_Fill%', 'C_Fill%', 'D_Fill%', 'E_Fill%'])
        
        for answer in results['grade_data']['answers']:
            question_num = answer['question']
            answer_value = answer['answer'] if answer['answer'] else 'BLANK'
            if answer_value == 'multiple':
                answer_value = 'MULTIPLE'
            
            # Fill percentages for each option
            fills = answer['fill_percentages']
            fill_strings = [f"{fill:.1f}%" for fill in fills]
            
            # Pad with empty strings if less than 5 options
            while len(fill_strings) < 5:
                fill_strings.append('')
            
            writer.writerow([question_num, answer_value] + fill_strings[:5])
        
        writer.writerow([])  # Empty row
        
        # Statistics section
        writer.writerow(['STATISTICS'])
        stats = results['grade_data']['statistics']
        writer.writerow(['Total answered:', stats['total_answered']])
        writer.writerow(['Multiple answers:', stats['multiple_answers']])
        writer.writerow(['Unanswered:', stats['unanswered']])

def print_processing_summary(result):
    """Print a summary of the processing results."""
    
    if not result['success']:
        print(f"❌ Processing failed: {result['message']}")
        return
    
    results = result['results']
    summary = results['summary']
    
    print("\n" + "=" * 60)
    print("📊 PROCESSING SUMMARY")
    print("=" * 60)
    
    # Basic stats
    print(f"📋 Questions: {summary['total_questions']}")
    print(f"✅ Answered: {summary['questions_answered']}")
    print(f"🔄 Multiple: {summary['multiple_answers']}")
    print(f"❌ Blank: {summary['unanswered']}")
    print(f"📈 Completion: {summary['completion_rate']}%")
    
    # Exam model
    if 'exam_model' in summary:
        em = summary['exam_model']
        status = "✅ Valid" if em['is_valid'] else "⚠️ Invalid"
        print(f"📝 Exam Model: {em['value']} ({status})")
    
    # Student ID
    if 'student_id' in summary:
        sid = summary['student_id']
        status = "✅ Complete" if sid['is_complete'] else "⚠️ Incomplete"
        print(f"🆔 Student ID: {sid['value']} ({status})")
    
    print("=" * 60)
    print(f"💾 Files generated:")
    print(f"   📊 CSV: {result['csv_path']}")
    print(f"   📄 JSON: {result['json_path']}")
    print(f"   🖼️ Visualization: {result['visualization_path']}")
    print("=" * 60)