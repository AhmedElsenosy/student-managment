# Exam Creator System 🎓

A comprehensive exam creation system that generates bubble sheet exams in PDF format with 3 different models (A, B, C). The system creates shuffled question orders and answer choices to prevent cheating while maintaining equivalent difficulty across all models.

## 🚀 Features

### Complete Exam Generation Pipeline
- **Question Input**: JSON format or programmatic input
- **3 Model Variations**: Automatic generation of models A, B, and C
- **Smart Shuffling**: Questions and answer choices shuffled differently for each model
- **Visual Templates**: High-quality bubble sheet templates with ArUco markers
- **PDF Export**: Professional PDF files ready for printing
- **Answer Keys**: Automatic generation of answer keys for all models
- **Instructor Package**: Organized folder structure with all materials

### Bubble Sheet Compatibility
- **ArUco Markers**: Corner markers for precise alignment
- **Student ID Section**: 8-digit bubble grid for student identification
- **Model Identification**: Pre-filled model bubbles (A/B/C)
- **Answer Bubbles**: Standard A-E multiple choice format
- **Compatible Format**: Works with existing BubbleSheetCorrecterModule

### Advanced Features
- **Reproducible Results**: Optional random seed for consistent shuffling
- **Batch Processing**: Create multiple exam sets
- **Session Management**: Track and manage created exams
- **Comprehensive Metadata**: Full creation history and settings
- **Clean Output**: Organized directory structure with instructor materials

## 📁 File Structure

```
src/
├── exam_template_generator.py       # Creates visual bubble sheet templates
├── exam_model_generator.py          # Generates 3 shuffled exam models
├── exam_pdf_exporter.py             # Exports templates and keys to PDF
├── exam_creator.py                  # Main interface combining all components
├── requirements_exam_creator.txt    # Dependencies for exam creation
└── README_Exam_Creator.md          # This documentation
```

## 🔧 Installation

### 1. Install System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install poppler-utils fonts-dejavu fonts-dejavu-core
```

**CentOS/RHEL:**
```bash
sudo yum install poppler-utils dejavu-sans-fonts
```

**macOS:**
```bash
brew install poppler
```

### 2. Install Python Dependencies

```bash
pip install -r requirements_exam_creator.txt
```

### 3. Verify Installation

```python
python3 exam_creator.py
```

## 🎯 Quick Start

### Basic Usage

```python
from exam_creator import ExamCreator

# Initialize creator
creator = ExamCreator(
    random_seed=42,  # For reproducible results
    output_base_dir="my_exams"
)

# Define questions
questions = [
    {
        "text": "What is the capital of France?",
        "choices": ["A) London", "B) Paris", "C) Berlin", "D) Madrid", "E) Rome"],
        "correct": "B"
    },
    {
        "text": "What is 2 + 2?",
        "choices": ["A) 3", "B) 4", "C) 5", "D) 6", "E) 7"],
        "correct": "B"
    }
    # Add more questions...
]

# Create complete exam set
result = creator.create_complete_exam_set(
    exam_title="My Math Exam",
    questions=questions,
    instructions="Use #2 pencil only. Fill bubbles completely.",
    shuffle_questions=True,
    shuffle_answers=True
)

if result['success']:
    print(f"✅ Exam created: {result['session_metadata']['session_directory']}")
```

### Create from JSON File

```python
# Create exam from JSON file
result = creator.create_from_question_file(
    "my_questions.json",
    exam_title="Custom Exam",
    instructions="Follow all instructions carefully."
)
```

**JSON Format:**
```json
{
    "title": "Sample Exam",
    "instructions": "Use #2 pencil only",
    "questions": [
        {
            "text": "Question text here?",
            "choices": ["A) Option 1", "B) Option 2", "C) Option 3", "D) Option 4", "E) Option 5"],
            "correct": "B"
        }
    ]
}
```

## 📊 Output Structure

Each exam creation generates a comprehensive package:

```
created_exams/
└── exam_20240827_123456/
    ├── session_metadata.json           # Complete session info
    ├── models/                         # JSON data files
    │   ├── exam_model_A.json
    │   ├── exam_model_B.json
    │   ├── exam_model_C.json
    │   ├── answer_key_A.json
    │   ├── answer_key_B.json
    │   └── answer_key_C.json
    ├── templates/                      # Visual templates (PNG)
    │   ├── exam_template_model_A.png
    │   ├── exam_template_model_B.png
    │   └── exam_template_model_C.png
    └── exam_instructor_package/        # Instructor materials
        ├── exams/
        │   ├── exam_model_A.pdf
        │   ├── exam_model_B.pdf
        │   └── exam_model_C.pdf
        ├── answer_keys/
        │   ├── answer_key_model_A.pdf
        │   ├── answer_key_model_B.pdf
        │   └── answer_key_model_C.pdf
        ├── all_exam_models.pdf         # Combined PDF
        └── instructor_summary.pdf      # Usage guide
```

## 🎓 Exam Model Differences

The system creates 3 truly different exam models:

### Model A (Example)
```
1. What is the capital of France?
   A) London  B) Paris  C) Berlin  D) Madrid  E) Rome

2. What is 2 + 2?
   A) 3  B) 4  C) 5  D) 6  E) 7
```

### Model B (Shuffled Questions & Answers)
```
1. What is 2 + 2?
   A) 4  B) 3  C) 6  D) 5  E) 7

2. What is the capital of France?
   A) Berlin  B) Madrid  C) Paris  D) London  E) Rome
```

### Model C (Different Shuffling)
```
1. What is the capital of France?
   A) Madrid  B) Berlin  C) London  D) Rome  E) Paris

2. What is 2 + 2?
   A) 6  B) 7  C) 3  D) 4  E) 5
```

Each model tests the same content but with different arrangements to prevent cheating.

## ⚙️ Configuration Options

### ExamCreator Options
```python
creator = ExamCreator(
    random_seed=42,                     # Reproducible shuffling
    output_base_dir="custom_output",    # Output directory
    page_size='A4',                     # or 'letter'
    temp_cleanup=True                   # Clean temporary files
)
```

### Exam Creation Options
```python
result = creator.create_complete_exam_set(
    exam_title="Your Exam Title",
    questions=question_list,
    instructions="Custom instructions...",
    exam_name="custom_name",            # File naming
    shuffle_questions=True,             # Shuffle question order
    shuffle_answers=True,               # Shuffle answer choices
    create_instructor_package=True      # Create organized package
)
```

## 🔍 Advanced Features

### Session Management
```python
# List all created exams
sessions = creator.list_created_exams()
for session in sessions:
    print(f"{session['exam_title']} - {session['creation_time']}")

# Get specific session info
session_info = creator.get_session_info("/path/to/session")
```

### Batch Processing
```python
# Process multiple question files
question_files = ["math_exam.json", "science_exam.json", "history_exam.json"]

for file_path in question_files:
    result = creator.create_from_question_file(file_path)
    print(f"Created: {result['session_metadata']['exam_title']}")
```

### Custom Templates
The system automatically creates professional bubble sheet templates with:
- **ArUco markers** in all four corners for precise scanning
- **Student ID grid** for 8-digit student identification
- **Model identification** with pre-filled bubbles
- **Answer sections** with proper spacing and labeling
- **Instructions** and exam metadata

## 📋 Question Format

### Required Fields
```python
question = {
    "text": "Question text here?",
    "choices": ["A) Option 1", "B) Option 2", "C) Option 3", "D) Option 4", "E) Option 5"],
    "correct": "B"  # Must match choice letter
}
```

### Optional Fields
```python
question = {
    "text": "Question text here?",
    "choices": ["A) Option 1", "B) Option 2", "C) Option 3", "D) Option 4"],  # 4 choices OK
    "correct": "B",
    "category": "mathematics",      # Optional categorization
    "difficulty": "medium",         # Optional difficulty level
    "explanation": "Explanation",   # Optional explanation
}
```

## 📈 Answer Key Features

Generated answer keys include:
- **Question-by-question answers** with correct letters
- **Question text preview** for easy reference
- **Answer distribution analysis** showing balance across A-E
- **Model identification** and creation metadata
- **Professional PDF formatting** ready for instructor use

## 🔗 Integration with Existing System

This exam creator is designed to work seamlessly with your existing bubble sheet processing system:

### Compatible Output
- **ArUco markers** match existing detection system
- **Bubble positions** align with current processing coordinates
- **Model identification** integrates with existing model detection
- **PDF format** ready for printing and distribution

### Workflow Integration
1. **Create exams** using this system
2. **Print and distribute** the PDF files
3. **Collect completed exams** from students
4. **Process using existing** PDF Exam Assistant
5. **Get results** with automatic grading

## 🛠️ Troubleshooting

### Common Issues

**1. Font errors:**
```bash
# Install system fonts
sudo apt-get install fonts-dejavu fonts-dejavu-core
```

**2. PDF generation fails:**
```bash
# Install ReportLab
pip install reportlab>=4.0.0
```

**3. Template generation fails:**
```bash
# Install Pillow
pip install Pillow>=10.0.0
```

**4. ArUco markers not generated:**
```bash
# Install OpenCV
pip install opencv-python>=4.8.0
```

### Debug Mode
```python
# Enable verbose output
creator = ExamCreator(temp_cleanup=False)  # Keep temporary files for inspection
```

## 📝 API Reference

### ExamCreator Class
```python
creator = ExamCreator(random_seed, output_base_dir, page_size, temp_cleanup)
```

### Main Methods
```python
# Create complete exam set
result = creator.create_complete_exam_set(exam_title, questions, instructions, ...)

# Create from JSON file
result = creator.create_from_question_file(file_path, exam_title, instructions, ...)

# Session management
sessions = creator.list_created_exams()
info = creator.get_session_info(session_dir)
```

## 🎉 Example Usage Script

```python
#!/usr/bin/env python3

from exam_creator import ExamCreator, create_sample_questions

def main():
    # Initialize
    creator = ExamCreator(random_seed=42)
    
    # Get questions (replace with your questions)
    questions = create_sample_questions()
    
    # Instructions
    instructions = """Instructions:
• Use a #2 pencil only
• Fill in bubbles completely
• Erase cleanly if you change an answer
• Mark only one answer per question
• Fill in your student ID completely
• Mark the correct exam model (A, B, or C)"""
    
    # Create exam
    result = creator.create_complete_exam_set(
        exam_title="Final Exam - Spring 2024",
        questions=questions,
        instructions=instructions,
        exam_name="spring_2024_final",
        shuffle_questions=True,
        shuffle_answers=True,
        create_instructor_package=True
    )
    
    if result['success']:
        print("🎉 Success!")
        print(f"📁 Files: {result['session_metadata']['session_directory']}")
    else:
        print(f"❌ Error: {result['error']}")

if __name__ == "__main__":
    main()
```

## 📄 License

This exam creator follows the same license as your existing BubbleSheetCorrecterModule project.

---

## 🎊 Ready to Create Exams!

Your exam creator system is now ready to generate professional bubble sheet exams with multiple models. The system provides:

- ✅ **Complete automation** - from questions to printable PDFs
- ✅ **Multiple model support** - automatic A, B, C variations
- ✅ **Professional output** - print-ready materials
- ✅ **Instructor packages** - organized materials with answer keys
- ✅ **Seamless integration** - works with existing grading system

Start creating your exams today! 🚀
