#!/usr/bin/env python3

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from typing import List, Dict, Tuple, Optional
import os
import json
from datetime import datetime

class ExamTemplateGenerator:
    """
    Generates bubble sheet exam templates with questions, answers, and ArUco markers.
    Creates templates that are compatible with the existing BubbleSheetCorrecterModule.
    """
    
    def __init__(self, 
                 page_width: int = 2480,     # A4 at 300 DPI width
                 page_height: int = 3508,    # A4 at 300 DPI height
                 margin: int = 200,          # Margin in pixels
                 bubble_size: int = 40):     # Bubble diameter
        """
        Initialize the exam template generator.
        
        Args:
            page_width: Page width in pixels
            page_height: Page height in pixels  
            margin: Page margin in pixels
            bubble_size: Bubble diameter in pixels
        """
        self.page_width = page_width
        self.page_height = page_height
        self.margin = margin
        self.bubble_size = bubble_size
        
        # Font settings
        self.title_font_size = 60
        self.question_font_size = 36
        self.answer_font_size = 32
        self.info_font_size = 28
        
        # Colors
        self.black = (0, 0, 0)
        self.gray = (128, 128, 128)
        self.light_gray = (200, 200, 200)
        
        # ArUco dictionary for markers
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
        
        print(f"📄 Exam Template Generator initialized")
        print(f"   Page size: {page_width}x{page_height} pixels")
        print(f"   Bubble size: {bubble_size} pixels")
    
    def generate_aruco_marker(self, marker_id: int, size: int = 200) -> np.ndarray:
        """Generate an ArUco marker."""
        marker_image = cv2.aruco.generateImageMarker(self.aruco_dict, marker_id, size)
        return marker_image
    
    def create_base_template(self, 
                           exam_title: str,
                           exam_model: str,
                           instructions: str = None) -> Image.Image:
        """
        Create the base template with header, title, and ArUco markers.
        
        Args:
            exam_title: Title of the exam
            exam_model: Exam model (A, B, C)
            instructions: Optional instructions text
            
        Returns:
            PIL Image with base template
        """
        # Create white background
        img = Image.new('RGB', (self.page_width, self.page_height), 'white')
        draw = ImageDraw.Draw(img)
        
        try:
            title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", self.title_font_size)
            question_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", self.question_font_size)
            answer_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", self.answer_font_size)
            info_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", self.info_font_size)
        except:
            # Fallback to default font if system fonts not available
            title_font = ImageFont.load_default()
            question_font = ImageFont.load_default()
            answer_font = ImageFont.load_default()
            info_font = ImageFont.load_default()
        
        current_y = self.margin
        
        # Add ArUco markers in corners
        marker_size = 150
        
        # Top-left marker (ID: 0)
        marker_0 = self.generate_aruco_marker(0, marker_size)
        marker_0_pil = Image.fromarray(marker_0)
        img.paste(marker_0_pil, (self.margin, self.margin))
        
        # Top-right marker (ID: 1)  
        marker_1 = self.generate_aruco_marker(1, marker_size)
        marker_1_pil = Image.fromarray(marker_1)
        img.paste(marker_1_pil, (self.page_width - self.margin - marker_size, self.margin))
        
        # Bottom-left marker (ID: 2)
        marker_2 = self.generate_aruco_marker(2, marker_size)
        marker_2_pil = Image.fromarray(marker_2)
        img.paste(marker_2_pil, (self.margin, self.page_height - self.margin - marker_size))
        
        # Bottom-right marker (ID: 3)
        marker_3 = self.generate_aruco_marker(3, marker_size)
        marker_3_pil = Image.fromarray(marker_3)
        img.paste(marker_3_pil, (self.page_width - self.margin - marker_size, self.page_height - self.margin - marker_size))
        
        # Move below top markers
        current_y = self.margin + marker_size + 50
        
        # Exam title
        title_text = f"{exam_title} - Model {exam_model}"
        title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (self.page_width - title_width) // 2
        draw.text((title_x, current_y), title_text, fill=self.black, font=title_font)
        current_y += 100
        
        # Date and time
        date_text = f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        draw.text((self.margin + marker_size + 50, self.margin + 20), date_text, fill=self.black, font=info_font)
        
        # Model indicator box
        model_box_x = self.page_width - self.margin - marker_size - 200
        model_box_y = self.margin + marker_size + 20
        draw.rectangle([model_box_x, model_box_y, model_box_x + 150, model_box_y + 80], 
                      outline=self.black, width=3)
        draw.text((model_box_x + 20, model_box_y + 15), f"Model: {exam_model}", 
                 fill=self.black, font=title_font)
        
        # Instructions
        if instructions:
            instructions_y = current_y + 20
            lines = instructions.split('\n')
            for line in lines:
                draw.text((self.margin + marker_size + 50, instructions_y), 
                         line, fill=self.black, font=info_font)
                instructions_y += 40
            current_y = instructions_y + 30
        
        # Student information section
        current_y += 50
        draw.text((self.margin + marker_size + 50, current_y), 
                 "Student Information:", fill=self.black, font=question_font)
        current_y += 60
        
        # Student ID bubbles section
        id_y = current_y
        draw.text((self.margin + marker_size + 50, id_y), "Student ID:", fill=self.black, font=answer_font)
        
        # Create ID bubble grid (10 digits, 0-9 for each position)
        id_start_x = self.margin + marker_size + 200
        id_start_y = id_y
        
        for digit_pos in range(8):  # 8-digit student ID
            digit_x = id_start_x + digit_pos * 60
            
            # Digit position label
            draw.text((digit_x + 15, id_start_y - 25), str(digit_pos + 1), 
                     fill=self.black, font=info_font)
            
            # Bubbles for digits 0-9
            for digit in range(10):
                bubble_y = id_start_y + digit * 45
                bubble_center = (digit_x + self.bubble_size // 2, 
                               bubble_y + self.bubble_size // 2)
                
                # Draw bubble
                draw.ellipse([digit_x, bubble_y, 
                            digit_x + self.bubble_size, 
                            bubble_y + self.bubble_size],
                           outline=self.black, width=2)
                
                # Draw digit label
                draw.text((digit_x - 30, bubble_y + 10), str(digit), 
                         fill=self.black, font=answer_font)
        
        # Update current_y to be after student ID section
        current_y = id_start_y + 10 * 45 + 60
        
        # Exam model bubbles
        model_y = current_y
        draw.text((self.margin + marker_size + 50, model_y), "Exam Model:", fill=self.black, font=answer_font)
        
        model_start_x = self.margin + marker_size + 200
        for i, model in enumerate(['A', 'B', 'C']):
            bubble_x = model_start_x + i * 80
            bubble_center = (bubble_x + self.bubble_size // 2, 
                           model_y + self.bubble_size // 2)
            
            # Draw bubble
            draw.ellipse([bubble_x, model_y, 
                        bubble_x + self.bubble_size, 
                        model_y + self.bubble_size],
                       outline=self.black, width=2)
            
            # Fill the bubble if it's the current model
            if model == exam_model:
                draw.ellipse([bubble_x + 5, model_y + 5, 
                            bubble_x + self.bubble_size - 5, 
                            model_y + self.bubble_size - 5],
                           fill=self.black)
            
            # Draw model label
            draw.text((bubble_x + 50, model_y + 10), model, 
                     fill=self.black, font=answer_font)
        
        current_y = model_y + self.bubble_size + 80
        
        # Return the template and current Y position for questions
        return img, current_y, draw, (question_font, answer_font, info_font)
    
    def add_questions_to_template(self, 
                                img: Image.Image,
                                draw: ImageDraw.Draw,
                                fonts: Tuple,
                                questions: List[Dict],
                                start_y: int,
                                max_questions_per_column: int = 25) -> Image.Image:
        """
        Add questions and answer bubbles to the template.
        
        Args:
            img: PIL Image to draw on
            draw: ImageDraw object
            fonts: Tuple of (question_font, answer_font, info_font)
            questions: List of question dictionaries
            start_y: Y position to start drawing questions
            max_questions_per_column: Maximum questions per column
            
        Returns:
            Updated PIL Image
        """
        question_font, answer_font, info_font = fonts
        
        # Calculate available space
        available_width = self.page_width - 2 * self.margin - 400  # Account for margins and markers
        available_height = self.page_height - start_y - self.margin - 200  # Account for bottom margin and markers
        
        # Determine number of columns based on number of questions
        num_questions = len(questions)
        if num_questions <= max_questions_per_column:
            num_columns = 1
        elif num_questions <= max_questions_per_column * 2:
            num_columns = 2
        else:
            num_columns = 3
        
        column_width = available_width // num_columns
        questions_per_column = (num_questions + num_columns - 1) // num_columns
        
        current_question = 0
        
        for col in range(num_columns):
            if current_question >= num_questions:
                break
                
            col_x = self.margin + 200 + col * column_width
            current_y = start_y
            
            # Add questions for this column
            questions_in_col = min(questions_per_column, num_questions - current_question)
            
            for q_idx in range(questions_in_col):
                if current_question >= num_questions:
                    break
                    
                question = questions[current_question]
                question_num = current_question + 1
                
                # Question text
                question_text = f"{question_num}. {question.get('text', f'Question {question_num}')}"
                
                # Handle long questions by wrapping text
                max_chars_per_line = 45  # Adjust based on column width
                words = question_text.split()
                lines = []
                current_line = ""
                
                for word in words:
                    test_line = current_line + (" " if current_line else "") + word
                    if len(test_line) <= max_chars_per_line:
                        current_line = test_line
                    else:
                        if current_line:
                            lines.append(current_line)
                        current_line = word
                
                if current_line:
                    lines.append(current_line)
                
                # Draw question text
                question_start_y = current_y
                for line in lines:
                    draw.text((col_x, current_y), line, fill=self.black, font=answer_font)
                    current_y += 35
                
                current_y += 10  # Space after question text
                
                # Draw answer bubbles
                choices = question.get('choices', ['A', 'B', 'C', 'D', 'E'])
                bubble_start_y = current_y
                
                for i, choice in enumerate(choices):
                    bubble_x = col_x + i * (self.bubble_size + 15)
                    bubble_y = current_y
                    
                    # Draw bubble
                    draw.ellipse([bubble_x, bubble_y, 
                                bubble_x + self.bubble_size, 
                                bubble_y + self.bubble_size],
                               outline=self.black, width=2)
                    
                    # Draw choice label
                    label_x = bubble_x + self.bubble_size + 5
                    draw.text((label_x, bubble_y + 8), choice, 
                             fill=self.black, font=answer_font)
                
                current_y += self.bubble_size + 25  # Space before next question
                current_question += 1
        
        return img
    
    def create_exam_template(self, 
                           exam_title: str,
                           exam_model: str,
                           questions: List[Dict],
                           instructions: str = None,
                           output_path: str = None) -> str:
        """
        Create a complete exam template.
        
        Args:
            exam_title: Title of the exam
            exam_model: Exam model (A, B, C)
            questions: List of question dictionaries
            instructions: Optional instructions
            output_path: Output file path
            
        Returns:
            Path to generated image file
        """
        # Create base template
        img, start_y, draw, fonts = self.create_base_template(
            exam_title, exam_model, instructions
        )
        
        # Add questions
        img = self.add_questions_to_template(
            img, draw, fonts, questions, start_y
        )
        
        # Save the image
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"exam_template_model_{exam_model}_{timestamp}.png"
        
        img.save(output_path, 'PNG', dpi=(300, 300))
        
        print(f"✅ Exam template created: {output_path}")
        print(f"   Model: {exam_model}")
        print(f"   Questions: {len(questions)}")
        
        return output_path

def main():
    """Example usage of the exam template generator."""
    print("📄 Exam Template Generator")
    print("=" * 40)
    
    # Initialize generator
    generator = ExamTemplateGenerator()
    
    # Sample questions
    sample_questions = [
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
            "text": "What is 2 + 2?",
            "choices": ["A) 3", "B) 4", "C) 5", "D) 6", "E) 7"],
            "correct": "B"
        }
    ]
    
    # Add more sample questions to test layout
    for i in range(4, 21):  # Add questions 4-20
        sample_questions.append({
            "text": f"Sample question number {i} for testing layout?",
            "choices": ["A) Option A", "B) Option B", "C) Option C", "D) Option D", "E) Option E"],
            "correct": "A"
        })
    
    instructions = """Instructions:
• Use a #2 pencil only
• Fill in bubbles completely
• Erase cleanly if you change an answer
• Mark only one answer per question"""
    
    # Generate template
    output_path = generator.create_exam_template(
        exam_title="Sample Mathematics Exam",
        exam_model="A",
        questions=sample_questions,
        instructions=instructions,
        output_path="sample_exam_template.png"
    )
    
    print(f"\n✅ Sample template generated: {output_path}")

if __name__ == "__main__":
    main()
