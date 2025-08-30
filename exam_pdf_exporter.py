#!/usr/bin/env python3

import os
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import tempfile

class ExamPDFExporter:
    """
    Exports exam templates and answer keys to PDF format.
    Can handle both image-based templates and text-based answer keys.
    """
    
    def __init__(self, page_size: str = 'A4'):
        """
        Initialize the PDF exporter.
        
        Args:
            page_size: Page size for PDFs ('A4' or 'letter')
        """
        self.page_size = A4 if page_size == 'A4' else letter
        self.page_width, self.page_height = self.page_size
        
        # Styles for text-based PDFs
        self.styles = getSampleStyleSheet()
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Title'],
            fontSize=18,
            spaceAfter=20,
            alignment=1  # Center alignment
        )
        self.heading_style = ParagraphStyle(
            'CustomHeading',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceBefore=15,
            spaceAfter=10
        )
        
        print(f"📄 PDF Exporter initialized")
        print(f"   Page size: {page_size}")
    
    def image_to_pdf(self, image_path: str, output_path: str) -> str:
        """
        Convert an image file to PDF.
        
        Args:
            image_path: Path to the image file
            output_path: Output PDF file path
            
        Returns:
            Path to created PDF file
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file not found: {image_path}")
        
        # Open and process the image
        with Image.open(image_path) as img:
            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Calculate scaling to fit page while maintaining aspect ratio
            img_width, img_height = img.size
            page_width_points = self.page_width
            page_height_points = self.page_height
            
            # Calculate scale factor
            scale_x = page_width_points / img_width
            scale_y = page_height_points / img_height
            scale = min(scale_x, scale_y) * 0.95  # 95% to leave small margin
            
            # Calculate centered position
            new_width = img_width * scale
            new_height = img_height * scale
            x_offset = (page_width_points - new_width) / 2
            y_offset = (page_height_points - new_height) / 2
            
            # Create PDF
            c = canvas.Canvas(output_path, pagesize=self.page_size)
            
            # Save image as temporary file if needed
            temp_image_path = None
            if image_path.lower().endswith('.png'):
                # Convert PNG to JPEG for ReportLab compatibility
                temp_image_path = tempfile.mktemp(suffix='.jpg')
                img.convert('RGB').save(temp_image_path, 'JPEG', quality=95)
                image_to_use = temp_image_path
            else:
                image_to_use = image_path
            
            try:
                # Draw the image
                c.drawImage(image_to_use, x_offset, y_offset, width=new_width, height=new_height)
                c.save()
            finally:
                # Clean up temporary file
                if temp_image_path and os.path.exists(temp_image_path):
                    os.remove(temp_image_path)
        
        print(f"✅ Image converted to PDF: {output_path}")
        return output_path
    
    def multiple_images_to_pdf(self, image_paths: List[str], output_path: str) -> str:
        """
        Convert multiple images to a single multi-page PDF.
        
        Args:
            image_paths: List of image file paths
            output_path: Output PDF file path
            
        Returns:
            Path to created PDF file
        """
        if not image_paths:
            raise ValueError("No image paths provided")
        
        c = canvas.Canvas(output_path, pagesize=self.page_size)
        
        for i, image_path in enumerate(image_paths):
            if not os.path.exists(image_path):
                print(f"⚠️ Image not found, skipping: {image_path}")
                continue
            
            print(f"📄 Adding page {i+1}/{len(image_paths)}: {os.path.basename(image_path)}")
            
            try:
                with Image.open(image_path) as img:
                    # Convert to RGB if necessary
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    # Calculate scaling
                    img_width, img_height = img.size
                    scale_x = self.page_width / img_width
                    scale_y = self.page_height / img_height
                    scale = min(scale_x, scale_y) * 0.95
                    
                    # Calculate position
                    new_width = img_width * scale
                    new_height = img_height * scale
                    x_offset = (self.page_width - new_width) / 2
                    y_offset = (self.page_height - new_height) / 2
                    
                    # Handle PNG conversion
                    temp_image_path = None
                    if image_path.lower().endswith('.png'):
                        temp_image_path = tempfile.mktemp(suffix='.jpg')
                        img.convert('RGB').save(temp_image_path, 'JPEG', quality=95)
                        image_to_use = temp_image_path
                    else:
                        image_to_use = image_path
                    
                    try:
                        # Draw the image
                        c.drawImage(image_to_use, x_offset, y_offset, width=new_width, height=new_height)
                        
                        # Add page break if not last image
                        if i < len(image_paths) - 1:
                            c.showPage()
                    finally:
                        # Clean up temporary file
                        if temp_image_path and os.path.exists(temp_image_path):
                            os.remove(temp_image_path)
                            
            except Exception as e:
                print(f"❌ Error processing {image_path}: {e}")
        
        c.save()
        print(f"✅ Multi-page PDF created: {output_path}")
        return output_path
    
    def answer_key_to_pdf(self, answer_key: Dict, output_path: str) -> str:
        """
        Create a PDF answer key from answer key data.
        
        Args:
            answer_key: Answer key dictionary
            output_path: Output PDF file path
            
        Returns:
            Path to created PDF file
        """
        doc = SimpleDocTemplate(output_path, pagesize=self.page_size)
        story = []
        
        # Title
        title_text = f"Answer Key - {answer_key.get('exam_title', 'Exam')}"
        title_text += f" (Model {answer_key.get('model_name', 'Unknown')})"
        story.append(Paragraph(title_text, self.title_style))
        
        # Metadata
        metadata_text = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br/>"
        metadata_text += f"Total Questions: {answer_key.get('total_questions', 0)}"
        story.append(Paragraph(metadata_text, self.styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Create answers table
        answers = answer_key.get('answers', [])
        
        # Prepare table data
        table_data = [['Question', 'Correct Answer', 'Question Text']]
        
        for answer in answers:
            question_num = answer.get('question_number', '?')
            correct_answer = answer.get('correct_answer', '?')
            question_text = answer.get('question_text', 'No text available')
            
            # Truncate long question text
            if len(question_text) > 60:
                question_text = question_text[:60] + '...'
            
            table_data.append([
                str(question_num),
                correct_answer,
                question_text
            ])
        
        # Create table
        table = Table(table_data, colWidths=[1*inch, 1.5*inch, 4*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        story.append(table)
        
        # Add answer distribution summary
        if answers:
            story.append(Spacer(1, 30))
            story.append(Paragraph("Answer Distribution Summary", self.heading_style))
            
            # Calculate answer distribution
            answer_counts = {}
            for answer in answers:
                correct = answer.get('correct_answer', 'Unknown')
                answer_counts[correct] = answer_counts.get(correct, 0) + 1
            
            distribution_text = ""
            for letter in sorted(answer_counts.keys()):
                count = answer_counts[letter]
                percentage = (count / len(answers)) * 100
                distribution_text += f"<b>{letter}:</b> {count} questions ({percentage:.1f}%)<br/>"
            
            story.append(Paragraph(distribution_text, self.styles['Normal']))
        
        # Build PDF
        doc.build(story)
        
        print(f"✅ Answer key PDF created: {output_path}")
        return output_path
    
    def create_exam_set_pdf(self, 
                          exam_images: Dict[str, str],
                          answer_keys: Dict[str, Dict],
                          output_dir: str,
                          exam_name: str) -> Dict[str, str]:
        """
        Create a complete set of exam PDFs (exams + answer keys).
        
        Args:
            exam_images: Dictionary mapping model names to image file paths
            answer_keys: Dictionary mapping model names to answer key data
            output_dir: Output directory
            exam_name: Base name for files
            
        Returns:
            Dictionary of created PDF file paths
        """
        os.makedirs(output_dir, exist_ok=True)
        
        created_files = {}
        
        # Create exam PDFs from images
        for model, image_path in exam_images.items():
            exam_pdf_path = os.path.join(output_dir, f"{exam_name}_exam_model_{model}.pdf")
            
            if os.path.exists(image_path):
                self.image_to_pdf(image_path, exam_pdf_path)
                created_files[f'exam_{model}'] = exam_pdf_path
            else:
                print(f"⚠️ Image not found for model {model}: {image_path}")
        
        # Create answer key PDFs
        for model, answer_key in answer_keys.items():
            answer_key_pdf_path = os.path.join(output_dir, f"{exam_name}_answer_key_model_{model}.pdf")
            self.answer_key_to_pdf(answer_key, answer_key_pdf_path)
            created_files[f'answer_key_{model}'] = answer_key_pdf_path
        
        # Create combined PDF with all exams
        all_exam_images = [path for path in exam_images.values() if os.path.exists(path)]
        if all_exam_images:
            combined_exam_path = os.path.join(output_dir, f"{exam_name}_all_exams.pdf")
            self.multiple_images_to_pdf(all_exam_images, combined_exam_path)
            created_files['all_exams'] = combined_exam_path
        
        print(f"📁 Exam set PDFs created in: {output_dir}")
        return created_files
    
    def create_instructor_package(self,
                                exam_images: Dict[str, str],
                                answer_keys: Dict[str, Dict],
                                output_dir: str,
                                exam_name: str) -> str:
        """
        Create a complete instructor package with all materials.
        
        Args:
            exam_images: Dictionary mapping model names to image file paths  
            answer_keys: Dictionary mapping model names to answer key data
            output_dir: Output directory
            exam_name: Base name for files
            
        Returns:
            Path to main package directory
        """
        package_dir = os.path.join(output_dir, f"{exam_name}_instructor_package")
        os.makedirs(package_dir, exist_ok=True)
        
        # Create subdirectories
        exams_dir = os.path.join(package_dir, "exams")
        answer_keys_dir = os.path.join(package_dir, "answer_keys")
        os.makedirs(exams_dir, exist_ok=True)
        os.makedirs(answer_keys_dir, exist_ok=True)
        
        # Create individual exam PDFs
        for model, image_path in exam_images.items():
            if os.path.exists(image_path):
                exam_pdf = os.path.join(exams_dir, f"exam_model_{model}.pdf")
                self.image_to_pdf(image_path, exam_pdf)
        
        # Create answer key PDFs
        for model, answer_key in answer_keys.items():
            answer_pdf = os.path.join(answer_keys_dir, f"answer_key_model_{model}.pdf")
            self.answer_key_to_pdf(answer_key, answer_pdf)
        
        # Create combined materials
        all_exam_images = [path for path in exam_images.values() if os.path.exists(path)]
        if all_exam_images:
            combined_exams = os.path.join(package_dir, "all_exam_models.pdf")
            self.multiple_images_to_pdf(all_exam_images, combined_exams)
        
        # Create instructor summary
        self._create_instructor_summary(package_dir, exam_name, answer_keys)
        
        print(f"📦 Instructor package created: {package_dir}")
        return package_dir
    
    def _create_instructor_summary(self, package_dir: str, exam_name: str, answer_keys: Dict[str, Dict]):
        """Create an instructor summary document."""
        summary_path = os.path.join(package_dir, "instructor_summary.pdf")
        
        doc = SimpleDocTemplate(summary_path, pagesize=self.page_size)
        story = []
        
        # Title
        story.append(Paragraph(f"Instructor Summary - {exam_name}", self.title_style))
        story.append(Spacer(1, 20))
        
        # Package contents
        story.append(Paragraph("Package Contents:", self.heading_style))
        contents_text = """
        • <b>exams/</b> - Individual exam PDFs for each model<br/>
        • <b>answer_keys/</b> - Answer key PDFs for each model<br/>
        • <b>all_exam_models.pdf</b> - Combined PDF with all exam models<br/>
        • <b>instructor_summary.pdf</b> - This summary document
        """
        story.append(Paragraph(contents_text, self.styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Models overview
        story.append(Paragraph("Exam Models Overview:", self.heading_style))
        
        for model, answer_key in answer_keys.items():
            model_text = f"<b>Model {model}:</b><br/>"
            model_text += f"• Questions: {answer_key.get('total_questions', 0)}<br/>"
            model_text += f"• Created: {answer_key.get('creation_time', 'Unknown')[:19]}<br/>"
            
            # Answer distribution
            answers = answer_key.get('answers', [])
            if answers:
                answer_counts = {}
                for answer in answers:
                    correct = answer.get('correct_answer', 'Unknown')
                    answer_counts[correct] = answer_counts.get(correct, 0) + 1
                
                model_text += f"• Answer distribution: "
                for letter in sorted(answer_counts.keys()):
                    count = answer_counts[letter]
                    model_text += f"{letter}:{count} "
                model_text += "<br/><br/>"
            
            story.append(Paragraph(model_text, self.styles['Normal']))
        
        # Instructions
        story.append(Spacer(1, 20))
        story.append(Paragraph("Instructions:", self.heading_style))
        instructions_text = """
        1. Print exam models from the exams/ folder<br/>
        2. Distribute different models to students (mix A, B, C models)<br/>
        3. Use corresponding answer keys for grading<br/>
        4. Each model has shuffled questions and answers for test security<br/>
        5. All models test the same content with equivalent difficulty
        """
        story.append(Paragraph(instructions_text, self.styles['Normal']))
        
        doc.build(story)

def main():
    """Example usage of the PDF exporter."""
    print("📄 PDF Exporter")
    print("=" * 30)
    
    exporter = ExamPDFExporter()
    
    # Example: Create a sample answer key
    sample_answer_key = {
        'model_name': 'A',
        'exam_title': 'Sample Math Exam',
        'total_questions': 5,
        'answers': [
            {'question_number': 1, 'correct_answer': 'B', 'question_text': 'What is 2 + 2?'},
            {'question_number': 2, 'correct_answer': 'C', 'question_text': 'What is the square root of 16?'},
            {'question_number': 3, 'correct_answer': 'A', 'question_text': 'What is 10 - 7?'},
            {'question_number': 4, 'correct_answer': 'D', 'question_text': 'What is 5 * 3?'},
            {'question_number': 5, 'correct_answer': 'B', 'question_text': 'What is 20 / 4?'}
        ]
    }
    
    # Create answer key PDF
    answer_key_path = exporter.answer_key_to_pdf(sample_answer_key, "sample_answer_key.pdf")
    
    print(f"✅ Sample answer key created: {answer_key_path}")

if __name__ == "__main__":
    main()
