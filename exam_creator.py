#!/usr/bin/env python3

import os
import json
from typing import List, Dict, Optional
from datetime import datetime
import tempfile

# Import the exam creation components
from exam_template_generator import ExamTemplateGenerator
from exam_model_generator import ExamModelGenerator  
from exam_pdf_exporter import ExamPDFExporter

class ExamCreator:
    """
    Main exam creator interface that integrates all components to create complete exam sets.
    Creates 3 different exam models (A, B, C) with shuffled questions and exports as PDFs.
    """
    
    def __init__(self,
                 random_seed: Optional[int] = None,
                 output_base_dir: str = "created_exams",
                 page_size: str = 'A4',
                 temp_cleanup: bool = True):
        """
        Initialize the exam creator.
        
        Args:
            random_seed: Random seed for reproducible shuffling
            output_base_dir: Base directory for output files
            page_size: PDF page size ('A4' or 'letter')
            temp_cleanup: Whether to clean up temporary files
        """
        self.output_base_dir = output_base_dir
        self.temp_cleanup = temp_cleanup
        
        # Initialize components
        self.template_generator = ExamTemplateGenerator()
        self.model_generator = ExamModelGenerator(random_seed=random_seed)
        self.pdf_exporter = ExamPDFExporter(page_size=page_size)
        
        # Create output directory
        os.makedirs(output_base_dir, exist_ok=True)
        
        print(f"🎓 Exam Creator initialized")
        print(f"   Output directory: {os.path.abspath(output_base_dir)}")
        if random_seed:
            print(f"   Random seed: {random_seed}")
    
    def create_complete_exam_set(self,
                               exam_title: str,
                               questions: List[Dict],
                               instructions: str = None,
                               exam_name: str = None,
                               shuffle_questions: bool = True,
                               shuffle_answers: bool = True,
                               create_instructor_package: bool = True) -> Dict:
        """
        Create a complete exam set with 3 models and all necessary files.
        
        Args:
            exam_title: Title of the exam
            questions: List of question dictionaries
            instructions: Instructions text for the exam
            exam_name: Base name for files (auto-generated if None)
            shuffle_questions: Whether to shuffle question order between models
            shuffle_answers: Whether to shuffle answer choices between models  
            create_instructor_package: Whether to create organized instructor package
            
        Returns:
            Dictionary with created files and session information
        """
        if exam_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            exam_name = f"exam_{timestamp}"
        
        session_dir = os.path.join(self.output_base_dir, exam_name)
        os.makedirs(session_dir, exist_ok=True)
        
        print(f"\n🚀 Creating complete exam set: {exam_title}")
        print(f"📁 Session directory: {session_dir}")
        print(f"📝 Questions: {len(questions)}")
        print("=" * 70)
        
        try:
            # Step 1: Generate exam model variations
            print("🔄 Step 1: Generating exam model variations...")
            models = self.model_generator.generate_model_variations(
                base_questions=questions,
                exam_title=exam_title,
                shuffle_questions=shuffle_questions,
                shuffle_answers=shuffle_answers
            )
            
            # Step 2: Generate answer keys
            print("\n🔑 Step 2: Generating answer keys...")
            answer_keys = self.model_generator.generate_all_answer_keys(models)
            
            # Step 3: Create visual templates for each model
            print("\n🎨 Step 3: Creating visual exam templates...")
            templates_dir = os.path.join(session_dir, "templates")
            os.makedirs(templates_dir, exist_ok=True)
            
            exam_images = {}
            
            for model_name, model_data in models.items():
                print(f"   Creating template for model {model_name}...")
                
                template_path = os.path.join(templates_dir, f"exam_template_model_{model_name}.png")
                
                # Create template image
                self.template_generator.create_exam_template(
                    exam_title=exam_title,
                    exam_model=model_name,
                    questions=model_data['questions'],
                    instructions=instructions,
                    output_path=template_path
                )
                
                exam_images[model_name] = template_path
            
            # Step 4: Export to PDF
            print("\n📄 Step 4: Exporting to PDF...")
            if create_instructor_package:
                # Create comprehensive instructor package
                package_dir = self.pdf_exporter.create_instructor_package(
                    exam_images=exam_images,
                    answer_keys=answer_keys,
                    output_dir=session_dir,
                    exam_name=exam_name
                )
                pdf_files = {'instructor_package': package_dir}
            else:
                # Create simple exam set PDFs
                pdf_files = self.pdf_exporter.create_exam_set_pdf(
                    exam_images=exam_images,
                    answer_keys=answer_keys,
                    output_dir=session_dir,
                    exam_name=exam_name
                )
            
            # Step 5: Save model data and metadata
            print("\n💾 Step 5: Saving data files...")
            
            # Save models to JSON
            models_dir = os.path.join(session_dir, "models")
            os.makedirs(models_dir, exist_ok=True)
            
            model_files = self.model_generator.save_models_to_files(
                models, models_dir, exam_name
            )
            
            answer_key_files = self.model_generator.save_answer_keys_to_files(
                answer_keys, models_dir, exam_name
            )
            
            # Create session metadata
            session_metadata = {
                'exam_title': exam_title,
                'exam_name': exam_name,
                'creation_time': datetime.now().isoformat(),
                'session_directory': session_dir,
                'total_questions': len(questions),
                'models_created': list(models.keys()),
                'shuffle_questions': shuffle_questions,
                'shuffle_answers': shuffle_answers,
                'random_seed': self.model_generator.random_seed,
                'files_created': {
                    'models': model_files,
                    'answer_keys': answer_key_files,
                    'templates': exam_images,
                    'pdfs': pdf_files
                },
                'instructions': instructions
            }
            
            # Save session metadata
            metadata_path = os.path.join(session_dir, "session_metadata.json")
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(session_metadata, f, indent=2, ensure_ascii=False)
            
            # Clean up temporary files if requested
            if self.temp_cleanup:
                self._cleanup_temp_files(session_dir)
            
            print(f"\n" + "=" * 70)
            print("✅ EXAM SET CREATION COMPLETED!")
            print("=" * 70)
            print(f"📁 Session directory: {session_dir}")
            print(f"📊 Created {len(models)} exam models: {', '.join(models.keys())}")
            print(f"🎨 Generated {len(exam_images)} visual templates")
            print(f"📄 Exported {len(pdf_files)} PDF file sets")
            print(f"💾 Saved metadata: {metadata_path}")
            
            return {
                'success': True,
                'session_metadata': session_metadata,
                'models': models,
                'answer_keys': answer_keys,
                'exam_images': exam_images,
                'pdf_files': pdf_files
            }
            
        except Exception as e:
            error_msg = f"Error creating exam set: {str(e)}"
            print(f"❌ {error_msg}")
            
            return {
                'success': False,
                'error': error_msg,
                'session_directory': session_dir
            }
    
    def create_from_question_file(self,
                                question_file_path: str,
                                exam_title: str = None,
                                instructions: str = None,
                                **kwargs) -> Dict:
        """
        Create exam set from a JSON file containing questions.
        
        Args:
            question_file_path: Path to JSON file with questions
            exam_title: Title for the exam (uses filename if None)
            instructions: Instructions text
            **kwargs: Additional arguments passed to create_complete_exam_set
            
        Returns:
            Dictionary with creation results
        """
        if not os.path.exists(question_file_path):
            return {
                'success': False,
                'error': f'Question file not found: {question_file_path}'
            }
        
        try:
            # Load questions from file
            with open(question_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract questions (support different file formats)
            if isinstance(data, list):
                questions = data
            elif isinstance(data, dict):
                questions = data.get('questions', [])
                if exam_title is None:
                    exam_title = data.get('title', data.get('exam_title'))
                if instructions is None:
                    instructions = data.get('instructions')
            else:
                return {
                    'success': False,
                    'error': 'Invalid question file format'
                }
            
            # Use filename as title if not provided
            if exam_title is None:
                exam_title = os.path.splitext(os.path.basename(question_file_path))[0]
            
            print(f"📖 Loaded {len(questions)} questions from: {question_file_path}")
            
            # Create exam set
            return self.create_complete_exam_set(
                exam_title=exam_title,
                questions=questions,
                instructions=instructions,
                **kwargs
            )
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Error loading question file: {str(e)}'
            }
    
    def get_session_info(self, session_dir: str) -> Dict:
        """Get information about an existing exam creation session."""
        metadata_path = os.path.join(session_dir, "session_metadata.json")
        
        if not os.path.exists(metadata_path):
            return {'error': 'Session metadata not found'}
        
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            return metadata
        except Exception as e:
            return {'error': f'Error reading session metadata: {str(e)}'}
    
    def list_created_exams(self) -> List[Dict]:
        """List all created exam sessions in the output directory."""
        if not os.path.exists(self.output_base_dir):
            return []
        
        sessions = []
        for item in os.listdir(self.output_base_dir):
            session_dir = os.path.join(self.output_base_dir, item)
            if os.path.isdir(session_dir):
                session_info = self.get_session_info(session_dir)
                if 'error' not in session_info:
                    sessions.append(session_info)
        
        # Sort by creation time, newest first
        sessions.sort(key=lambda x: x.get('creation_time', ''), reverse=True)
        return sessions
    
    def _cleanup_temp_files(self, session_dir: str):
        """Clean up temporary files in the session directory."""
        # Remove template images if PDFs were created successfully
        templates_dir = os.path.join(session_dir, "templates")
        if os.path.exists(templates_dir):
            # Check if PDFs exist
            pdf_exists = any(
                f.endswith('.pdf') for f in os.listdir(session_dir) 
                if os.path.isfile(os.path.join(session_dir, f))
            )
            
            if pdf_exists:
                print("🧹 Cleaning up temporary template images...")
                try:
                    import shutil
                    # Keep one template as reference, remove others
                    template_files = [f for f in os.listdir(templates_dir) if f.endswith('.png')]
                    if len(template_files) > 1:
                        # Keep model A template, remove others
                        for template_file in template_files[1:]:
                            template_path = os.path.join(templates_dir, template_file)
                            os.remove(template_path)
                except Exception as e:
                    print(f"⚠️ Warning: Could not clean up templates: {e}")

def create_sample_questions() -> List[Dict]:
    """Create sample questions for testing."""
    return [
        {
            "text": "What is the capital of France?",
            "choices": ["A) London", "B) Paris", "C) Berlin", "D) Madrid", "E) Rome"],
            "correct": "B"
        },
        {
            "text": "Which planet is closest to the sun?",
            "choices": ["A) Venus", "B) Earth", "C) Mercury", "D) Mars", "E) Jupiter"],
            "correct": "C"
        },
        {
            "text": "What is 15 + 27?",
            "choices": ["A) 41", "B) 42", "C) 43", "D) 44", "E) 45"],
            "correct": "B"
        },
        {
            "text": "Who wrote 'Romeo and Juliet'?",
            "choices": ["A) Charles Dickens", "B) William Shakespeare", "C) Jane Austen", "D) Mark Twain", "E) Oscar Wilde"],
            "correct": "B"
        },
        {
            "text": "What is the chemical symbol for gold?",
            "choices": ["A) Go", "B) Gd", "C) Au", "D) Ag", "E) Al"],
            "correct": "C"
        },
        {
            "text": "In which year did World War II end?",
            "choices": ["A) 1944", "B) 1945", "C) 1946", "D) 1947", "E) 1948"],
            "correct": "B"
        },
        {
            "text": "What is the largest ocean on Earth?",
            "choices": ["A) Atlantic", "B) Indian", "C) Arctic", "D) Pacific", "E) Southern"],
            "correct": "D"
        },
        {
            "text": "How many sides does a hexagon have?",
            "choices": ["A) 5", "B) 6", "C) 7", "D) 8", "E) 9"],
            "correct": "B"
        },
        {
            "text": "What is the square root of 64?",
            "choices": ["A) 6", "B) 7", "C) 8", "D) 9", "E) 10"],
            "correct": "C"
        },
        {
            "text": "Which element has the atomic number 1?",
            "choices": ["A) Helium", "B) Hydrogen", "C) Lithium", "D) Carbon", "E) Oxygen"],
            "correct": "B"
        }
    ]

def main():
    """Example usage of the exam creator."""
    print("🎓 Exam Creator")
    print("=" * 50)
    
    # Initialize creator
    creator = ExamCreator(
        random_seed=42,  # For reproducible results
        output_base_dir="created_exams",
        page_size='A4'
    )
    
    # Get sample questions
    questions = create_sample_questions()
    
    # Create instructions
    instructions = """Instructions:
• Use a #2 pencil only
• Fill in bubbles completely
• Erase cleanly if you change an answer
• Mark only one answer per question
• Fill in your student ID completely
• Mark the correct exam model"""
    
    # Create complete exam set
    result = creator.create_complete_exam_set(
        exam_title="Sample General Knowledge Exam",
        questions=questions,
        instructions=instructions,
        exam_name="sample_general_knowledge",
        shuffle_questions=True,
        shuffle_answers=True,
        create_instructor_package=True
    )
    
    if result['success']:
        print("\n🎉 Exam creation completed successfully!")
        metadata = result['session_metadata']
        print(f"📁 Output directory: {metadata['session_directory']}")
        print(f"📄 Files created: {len(metadata['files_created']['pdfs'])} PDF sets")
        
        # Show created files
        if 'instructor_package' in metadata['files_created']['pdfs']:
            package_dir = metadata['files_created']['pdfs']['instructor_package']
            print(f"📦 Instructor package: {package_dir}")
    else:
        print(f"❌ Exam creation failed: {result['error']}")
    
    # List all created exams
    print(f"\n📋 All created exams:")
    sessions = creator.list_created_exams()
    for i, session in enumerate(sessions[:5], 1):  # Show first 5
        print(f"  {i}. {session['exam_title']} ({session['creation_time'][:10]})")

if __name__ == "__main__":
    main()
