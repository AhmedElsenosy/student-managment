#!/usr/bin/env python3

import random
import json
import copy
from typing import List, Dict, Tuple, Optional
from datetime import datetime

class ExamModelGenerator:
    """
    Generates 3 different exam models (A, B, C) by shuffling questions and answer choices.
    Ensures each model has different question order and answer choice arrangements.
    """
    
    def __init__(self, random_seed: Optional[int] = None):
        """
        Initialize the exam model generator.
        
        Args:
            random_seed: Optional random seed for reproducible shuffling
        """
        self.random_seed = random_seed
        if random_seed is not None:
            random.seed(random_seed)
            
        print(f"🎯 Exam Model Generator initialized")
        if random_seed:
            print(f"   Using random seed: {random_seed}")
    
    def shuffle_questions(self, questions: List[Dict], model_name: str) -> List[Dict]:
        """
        Shuffle the order of questions for a specific model.
        
        Args:
            questions: List of question dictionaries
            model_name: Model name (A, B, C) for consistent shuffling
            
        Returns:
            List of shuffled questions
        """
        # Create a copy to avoid modifying original
        shuffled_questions = copy.deepcopy(questions)
        
        # Use model name to create consistent but different shuffles
        model_seed = hash(model_name + str(self.random_seed or 0)) % 10000
        random.seed(model_seed)
        
        random.shuffle(shuffled_questions)
        
        # Reset to original seed if one was provided
        if self.random_seed is not None:
            random.seed(self.random_seed)
            
        return shuffled_questions
    
    def shuffle_answer_choices(self, question: Dict, model_name: str, question_index: int) -> Dict:
        """
        Shuffle answer choices for a question while maintaining correct answer tracking.
        
        Args:
            question: Question dictionary with 'choices' and 'correct' keys
            model_name: Model name (A, B, C)
            question_index: Index of question for unique shuffling
            
        Returns:
            Question with shuffled choices and updated correct answer
        """
        # Create a copy to avoid modifying original
        shuffled_question = copy.deepcopy(question)
        
        # Extract choices and correct answer
        choices = shuffled_question.get('choices', [])
        correct_answer = shuffled_question.get('correct', 'A')
        
        if len(choices) < 2:
            return shuffled_question  # Nothing to shuffle
        
        # Create choice pairs (choice text, original letter)
        choice_pairs = []
        for i, choice in enumerate(choices):
            original_letter = chr(ord('A') + i)
            choice_pairs.append((choice, original_letter))
        
        # Shuffle using consistent seed based on model and question
        shuffle_seed = hash(f"{model_name}_{question_index}_{self.random_seed or 0}") % 10000
        random.seed(shuffle_seed)
        random.shuffle(choice_pairs)
        
        # Reset to original seed
        if self.random_seed is not None:
            random.seed(self.random_seed)
        
        # Rebuild choices list and find new correct answer position
        new_choices = []
        new_correct_answer = 'A'
        
        for i, (choice_text, original_letter) in enumerate(choice_pairs):
            new_letter = chr(ord('A') + i)
            new_choices.append(choice_text)
            
            # Update correct answer if this was the original correct choice
            if original_letter == correct_answer:
                new_correct_answer = new_letter
        
        # Update the question
        shuffled_question['choices'] = new_choices
        shuffled_question['correct'] = new_correct_answer
        shuffled_question['original_correct'] = correct_answer  # Keep track of original
        
        return shuffled_question
    
    def generate_model_variations(self, 
                                base_questions: List[Dict],
                                exam_title: str,
                                shuffle_questions: bool = True,
                                shuffle_answers: bool = True) -> Dict[str, Dict]:
        """
        Generate 3 exam model variations (A, B, C).
        
        Args:
            base_questions: List of base question dictionaries
            exam_title: Title of the exam
            shuffle_questions: Whether to shuffle question order
            shuffle_answers: Whether to shuffle answer choices
            
        Returns:
            Dictionary with models A, B, C containing questions and metadata
        """
        models = {}
        
        for model_name in ['A', 'B', 'C']:
            print(f"🔄 Generating model {model_name}...")
            
            # Start with base questions
            model_questions = copy.deepcopy(base_questions)
            
            # Shuffle question order if requested
            if shuffle_questions:
                model_questions = self.shuffle_questions(model_questions, model_name)
            
            # Shuffle answer choices if requested
            if shuffle_answers:
                for i, question in enumerate(model_questions):
                    model_questions[i] = self.shuffle_answer_choices(question, model_name, i)
            
            # Create model metadata
            models[model_name] = {
                'model_name': model_name,
                'exam_title': exam_title,
                'questions': model_questions,
                'total_questions': len(model_questions),
                'creation_time': datetime.now().isoformat(),
                'shuffled_questions': shuffle_questions,
                'shuffled_answers': shuffle_answers,
                'random_seed': self.random_seed
            }
            
            print(f"   ✅ Model {model_name}: {len(model_questions)} questions")
        
        return models
    
    def generate_answer_key(self, model_data: Dict) -> Dict:
        """
        Generate answer key for a specific model.
        
        Args:
            model_data: Model data dictionary
            
        Returns:
            Answer key dictionary
        """
        questions = model_data['questions']
        
        answer_key = {
            'model_name': model_data['model_name'],
            'exam_title': model_data['exam_title'],
            'answers': [],
            'total_questions': len(questions),
            'creation_time': datetime.now().isoformat()
        }
        
        for i, question in enumerate(questions):
            answer_entry = {
                'question_number': i + 1,
                'correct_answer': question.get('correct', 'A'),
                'question_text': question.get('text', f'Question {i + 1}'),
                'all_choices': question.get('choices', [])
            }
            
            # Include original correct answer if available (for tracking shuffles)
            if 'original_correct' in question:
                answer_entry['original_correct'] = question['original_correct']
            
            answer_key['answers'].append(answer_entry)
        
        return answer_key
    
    def generate_all_answer_keys(self, models: Dict[str, Dict]) -> Dict[str, Dict]:
        """
        Generate answer keys for all models.
        
        Args:
            models: Dictionary of all exam models
            
        Returns:
            Dictionary of answer keys for each model
        """
        answer_keys = {}
        
        for model_name, model_data in models.items():
            answer_keys[model_name] = self.generate_answer_key(model_data)
            print(f"🔑 Generated answer key for model {model_name}")
        
        return answer_keys
    
    def save_models_to_files(self, 
                           models: Dict[str, Dict],
                           output_dir: str = "generated_exams",
                           exam_name: str = None) -> Dict[str, str]:
        """
        Save exam models to JSON files.
        
        Args:
            models: Dictionary of exam models
            output_dir: Output directory
            exam_name: Base name for files
            
        Returns:
            Dictionary of saved file paths
        """
        import os
        
        os.makedirs(output_dir, exist_ok=True)
        
        if exam_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            exam_name = f"exam_{timestamp}"
        
        saved_files = {}
        
        for model_name, model_data in models.items():
            filename = f"{exam_name}_model_{model_name}.json"
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(model_data, f, indent=2, ensure_ascii=False)
            
            saved_files[model_name] = filepath
            print(f"💾 Saved model {model_name}: {filepath}")
        
        return saved_files
    
    def save_answer_keys_to_files(self,
                                answer_keys: Dict[str, Dict],
                                output_dir: str = "generated_exams",
                                exam_name: str = None) -> Dict[str, str]:
        """
        Save answer keys to JSON files.
        
        Args:
            answer_keys: Dictionary of answer keys
            output_dir: Output directory
            exam_name: Base name for files
            
        Returns:
            Dictionary of saved file paths
        """
        import os
        
        os.makedirs(output_dir, exist_ok=True)
        
        if exam_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            exam_name = f"exam_{timestamp}"
        
        saved_files = {}
        
        for model_name, answer_key in answer_keys.items():
            filename = f"{exam_name}_answer_key_{model_name}.json"
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(answer_key, f, indent=2, ensure_ascii=False)
            
            saved_files[model_name] = filepath
            print(f"🔑 Saved answer key {model_name}: {filepath}")
        
        return saved_files
    
    def print_model_comparison(self, models: Dict[str, Dict]):
        """
        Print a comparison of the generated models.
        
        Args:
            models: Dictionary of exam models
        """
        print(f"\n📊 Model Comparison:")
        print("=" * 60)
        
        # Compare first few questions
        for i in range(min(5, len(models['A']['questions']))):
            print(f"Question {i + 1}:")
            for model_name in ['A', 'B', 'C']:
                question = models[model_name]['questions'][i]
                question_text = question.get('text', 'No text')[:50] + "..."
                correct_answer = question.get('correct', '?')
                print(f"  Model {model_name}: {question_text} [Answer: {correct_answer}]")
            print()
        
        # Summary statistics
        print("Model Statistics:")
        for model_name, model_data in models.items():
            questions = model_data['questions']
            correct_answers = [q.get('correct', 'A') for q in questions]
            answer_distribution = {letter: correct_answers.count(letter) for letter in 'ABCDE'}
            print(f"  Model {model_name}: {answer_distribution}")

def main():
    """Example usage of the exam model generator."""
    print("🎯 Exam Model Generator")
    print("=" * 40)
    
    # Initialize generator with a seed for reproducible results
    generator = ExamModelGenerator(random_seed=42)
    
    # Sample base questions
    base_questions = [
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
        },
        {
            "text": "What is the largest ocean on Earth?",
            "choices": ["A) Atlantic", "B) Indian", "C) Arctic", "D) Pacific", "E) Southern"],
            "correct": "D"
        },
        {
            "text": "In which year did World War II end?",
            "choices": ["A) 1944", "B) 1945", "C) 1946", "D) 1947", "E) 1948"],
            "correct": "B"
        }
    ]
    
    # Generate 3 model variations
    models = generator.generate_model_variations(
        base_questions=base_questions,
        exam_title="Sample General Knowledge Exam",
        shuffle_questions=True,
        shuffle_answers=True
    )
    
    # Generate answer keys
    answer_keys = generator.generate_all_answer_keys(models)
    
    # Print comparison
    generator.print_model_comparison(models)
    
    # Save to files
    print(f"\n💾 Saving files...")
    model_files = generator.save_models_to_files(models, exam_name="sample_exam")
    answer_key_files = generator.save_answer_keys_to_files(answer_keys, exam_name="sample_exam")
    
    print(f"\n✅ Generated {len(models)} exam models with answer keys")
    print(f"📁 Files saved in: generated_exams/")

if __name__ == "__main__":
    main()
