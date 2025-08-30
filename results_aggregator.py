#!/usr/bin/env python3

import os
import json
import csv
import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import glob
from collections import Counter, defaultdict

class ResultsAggregator:
    """
    Advanced results aggregator for exam processing.
    Provides comprehensive statistics, grade analysis, and reporting features.
    """
    
    def __init__(self):
        """Initialize the results aggregator."""
        pass
    
    def aggregate_session_results(self, session_dir: str) -> Dict:
        """
        Aggregate results from a single processing session.
        
        Args:
            session_dir: Directory containing session results
            
        Returns:
            Dictionary with aggregated results
        """
        if not os.path.exists(session_dir):
            raise FileNotFoundError(f"Session directory not found: {session_dir}")
        
        summary_file = os.path.join(session_dir, "exam_summary.csv")
        detailed_file = os.path.join(session_dir, "detailed_answers.csv")
        
        if not os.path.exists(summary_file):
            raise FileNotFoundError(f"Summary file not found: {summary_file}")
        
        # Read summary data
        summary_df = pd.read_csv(summary_file, skiprows=5)  # Skip header rows
        summary_df = summary_df.dropna(how='all')  # Remove empty rows
        
        # Read detailed data if available
        detailed_df = None
        if os.path.exists(detailed_file):
            detailed_df = pd.read_csv(detailed_file)
        
        # Calculate aggregated statistics
        aggregated = {
            'session_info': {
                'session_dir': session_dir,
                'timestamp': datetime.now().isoformat(),
                'summary_file': summary_file,
                'detailed_file': detailed_file if os.path.exists(detailed_file) else None
            },
            'overview': self._calculate_overview_stats(summary_df),
            'exam_model_analysis': self._analyze_exam_models(summary_df),
            'completion_analysis': self._analyze_completion_rates(summary_df),
            'question_analysis': self._analyze_questions(detailed_df) if detailed_df is not None else None,
            'student_analysis': self._analyze_students(detailed_df) if detailed_df is not None else None,
            'quality_metrics': self._calculate_quality_metrics(summary_df, detailed_df)
        }
        
        return aggregated
    
    def compare_multiple_sessions(self, session_dirs: List[str]) -> Dict:
        """
        Compare results across multiple processing sessions.
        
        Args:
            session_dirs: List of session directories to compare
            
        Returns:
            Dictionary with comparison results
        """
        all_sessions = []
        
        for session_dir in session_dirs:
            try:
                session_results = self.aggregate_session_results(session_dir)
                session_results['session_name'] = os.path.basename(session_dir)
                all_sessions.append(session_results)
            except Exception as e:
                print(f"Warning: Could not process session {session_dir}: {e}")
        
        if not all_sessions:
            raise ValueError("No valid sessions found")
        
        comparison = {
            'comparison_info': {
                'total_sessions': len(all_sessions),
                'session_names': [s['session_name'] for s in all_sessions],
                'timestamp': datetime.now().isoformat()
            },
            'session_summaries': [
                {
                    'name': s['session_name'],
                    'total_pages': s['overview']['total_pages'],
                    'successful_pages': s['overview']['successful_pages'],
                    'success_rate': s['overview']['success_rate_percent'],
                    'avg_completion': s['completion_analysis']['average_completion_rate'],
                    'exam_models_used': s['exam_model_analysis']['models_used']
                }
                for s in all_sessions
            ],
            'aggregate_stats': self._calculate_cross_session_stats(all_sessions),
            'detailed_sessions': all_sessions
        }
        
        return comparison
    
    def generate_comprehensive_report(self, aggregated_data: Dict, output_file: str):
        """
        Generate a comprehensive Excel report from aggregated data.
        
        Args:
            aggregated_data: Aggregated results data
            output_file: Output Excel file path
        """
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            
            # Overview sheet
            overview_data = []
            overview = aggregated_data['overview']
            for key, value in overview.items():
                overview_data.append([key.replace('_', ' ').title(), value])
            
            overview_df = pd.DataFrame(overview_data, columns=['Metric', 'Value'])
            overview_df.to_excel(writer, sheet_name='Overview', index=False)
            
            # Exam Model Analysis
            if aggregated_data['exam_model_analysis']:
                model_data = []
                for model, count in aggregated_data['exam_model_analysis']['model_distribution'].items():
                    model_data.append([model, count, f"{count/aggregated_data['overview']['successful_pages']*100:.1f}%"])
                
                model_df = pd.DataFrame(model_data, columns=['Exam Model', 'Count', 'Percentage'])
                model_df.to_excel(writer, sheet_name='Exam Models', index=False)
            
            # Question Analysis
            if aggregated_data['question_analysis']:
                qa = aggregated_data['question_analysis']
                
                # Question difficulty
                difficulty_data = []
                for q_num, stats in qa['question_difficulty'].items():
                    difficulty_data.append([
                        q_num, 
                        stats['answered_count'],
                        stats['blank_count'],
                        stats['multiple_count'],
                        f"{stats['answer_rate_percent']:.1f}%",
                        stats['difficulty_level']
                    ])
                
                difficulty_df = pd.DataFrame(difficulty_data, columns=[
                    'Question', 'Answered', 'Blank', 'Multiple', 'Answer Rate', 'Difficulty'
                ])
                difficulty_df.to_excel(writer, sheet_name='Question Analysis', index=False)
                
                # Answer distribution
                if qa['answer_distribution']:
                    answer_data = []
                    for q_num, answers in qa['answer_distribution'].items():
                        for answer, count in answers.items():
                            answer_data.append([q_num, answer, count])
                    
                    answer_df = pd.DataFrame(answer_data, columns=['Question', 'Answer', 'Count'])
                    answer_pivot = answer_df.pivot_table(index='Question', columns='Answer', values='Count', fill_value=0)
                    answer_pivot.to_excel(writer, sheet_name='Answer Distribution')
            
            # Student Analysis
            if aggregated_data['student_analysis']:
                sa = aggregated_data['student_analysis']
                
                student_data = []
                for page, stats in sa['student_performance'].items():
                    student_data.append([
                        page,
                        stats['student_id'],
                        stats['exam_model'],
                        stats['completion_rate'],
                        stats['answers_given'],
                        stats['total_questions'],
                        stats['multiple_answers'],
                        stats['performance_category']
                    ])
                
                student_df = pd.DataFrame(student_data, columns=[
                    'Page', 'Student ID', 'Exam Model', 'Completion Rate', 
                    'Answered', 'Total Questions', 'Multiple Answers', 'Performance'
                ])
                student_df.to_excel(writer, sheet_name='Student Performance', index=False)
        
        print(f"📊 Comprehensive report generated: {output_file}")
    
    def _calculate_overview_stats(self, summary_df: pd.DataFrame) -> Dict:
        """Calculate overview statistics."""
        total_pages = len(summary_df)
        successful_pages = len(summary_df[summary_df['Status'] == 'SUCCESS'])
        failed_pages = total_pages - successful_pages
        
        return {
            'total_pages': total_pages,
            'successful_pages': successful_pages,
            'failed_pages': failed_pages,
            'success_rate_percent': round(successful_pages / total_pages * 100, 1) if total_pages > 0 else 0
        }
    
    def _analyze_exam_models(self, summary_df: pd.DataFrame) -> Dict:
        """Analyze exam model usage."""
        successful_df = summary_df[summary_df['Status'] == 'SUCCESS']
        
        if len(successful_df) == 0:
            return {'model_distribution': {}, 'models_used': []}
        
        model_counts = successful_df['Model Used'].value_counts().to_dict()
        models_used = list(model_counts.keys())
        
        return {
            'model_distribution': model_counts,
            'models_used': models_used,
            'most_common_model': max(model_counts, key=model_counts.get) if model_counts else None
        }
    
    def _analyze_completion_rates(self, summary_df: pd.DataFrame) -> Dict:
        """Analyze completion rates."""
        successful_df = summary_df[summary_df['Status'] == 'SUCCESS']
        
        if len(successful_df) == 0:
            return {'average_completion_rate': 0, 'completion_distribution': {}}
        
        completion_rates = successful_df['Completion%'].astype(float)
        
        # Categorize completion rates
        categories = {
            'Excellent (90-100%)': len(completion_rates[completion_rates >= 90]),
            'Good (70-89%)': len(completion_rates[(completion_rates >= 70) & (completion_rates < 90)]),
            'Fair (50-69%)': len(completion_rates[(completion_rates >= 50) & (completion_rates < 70)]),
            'Poor (0-49%)': len(completion_rates[completion_rates < 50])
        }
        
        return {
            'average_completion_rate': round(completion_rates.mean(), 1),
            'median_completion_rate': round(completion_rates.median(), 1),
            'min_completion_rate': round(completion_rates.min(), 1),
            'max_completion_rate': round(completion_rates.max(), 1),
            'completion_distribution': categories
        }
    
    def _analyze_questions(self, detailed_df: pd.DataFrame) -> Dict:
        """Analyze question-level statistics."""
        if detailed_df is None or len(detailed_df) == 0:
            return None
        
        question_stats = {}
        answer_distribution = {}
        
        for question in detailed_df['Question'].unique():
            q_data = detailed_df[detailed_df['Question'] == question]
            
            answered_count = len(q_data[q_data['Answer'] != 'BLANK'])
            blank_count = len(q_data[q_data['Answer'] == 'BLANK'])
            multiple_count = len(q_data[q_data['Answer'] == 'MULTIPLE'])
            total_count = len(q_data)
            
            answer_rate = (answered_count - multiple_count) / total_count * 100
            
            # Determine difficulty level
            if answer_rate >= 80:
                difficulty = 'Easy'
            elif answer_rate >= 60:
                difficulty = 'Medium'
            else:
                difficulty = 'Hard'
            
            question_stats[question] = {
                'answered_count': answered_count,
                'blank_count': blank_count,
                'multiple_count': multiple_count,
                'total_count': total_count,
                'answer_rate_percent': round(answer_rate, 1),
                'difficulty_level': difficulty
            }
            
            # Answer distribution
            answer_counts = q_data['Answer'].value_counts().to_dict()
            answer_distribution[question] = answer_counts
        
        return {
            'question_difficulty': question_stats,
            'answer_distribution': answer_distribution,
            'easiest_questions': sorted(question_stats.items(), 
                                      key=lambda x: x[1]['answer_rate_percent'], reverse=True)[:5],
            'hardest_questions': sorted(question_stats.items(), 
                                      key=lambda x: x[1]['answer_rate_percent'])[:5]
        }
    
    def _analyze_students(self, detailed_df: pd.DataFrame) -> Dict:
        """Analyze student-level performance."""
        if detailed_df is None or len(detailed_df) == 0:
            return None
        
        student_performance = {}
        
        for page in detailed_df['Page'].unique():
            page_data = detailed_df[detailed_df['Page'] == page]
            
            if len(page_data) == 0:
                continue
            
            student_id = page_data['Student_ID'].iloc[0]
            exam_model = page_data['Exam_Model'].iloc[0]
            
            total_questions = len(page_data)
            answers_given = len(page_data[page_data['Answer'] != 'BLANK'])
            multiple_answers = len(page_data[page_data['Answer'] == 'MULTIPLE'])
            
            completion_rate = (answers_given - multiple_answers) / total_questions * 100
            
            # Performance categorization
            if completion_rate >= 90:
                performance = 'Excellent'
            elif completion_rate >= 70:
                performance = 'Good'
            elif completion_rate >= 50:
                performance = 'Fair'
            else:
                performance = 'Poor'
            
            student_performance[page] = {
                'student_id': student_id,
                'exam_model': exam_model,
                'total_questions': total_questions,
                'answers_given': answers_given,
                'multiple_answers': multiple_answers,
                'completion_rate': round(completion_rate, 1),
                'performance_category': performance
            }
        
        # Performance distribution
        performance_dist = Counter(stats['performance_category'] for stats in student_performance.values())
        
        return {
            'student_performance': student_performance,
            'performance_distribution': dict(performance_dist),
            'total_students': len(student_performance),
            'average_completion': round(np.mean([s['completion_rate'] for s in student_performance.values()]), 1)
        }
    
    def _calculate_quality_metrics(self, summary_df: pd.DataFrame, detailed_df: Optional[pd.DataFrame]) -> Dict:
        """Calculate quality metrics for the processing."""
        metrics = {
            'processing_success_rate': 0,
            'data_completeness_score': 0,
            'consistency_score': 0,
            'overall_quality_score': 0
        }
        
        if len(summary_df) == 0:
            return metrics
        
        # Processing success rate
        success_rate = len(summary_df[summary_df['Status'] == 'SUCCESS']) / len(summary_df)
        metrics['processing_success_rate'] = round(success_rate * 100, 1)
        
        # Data completeness (based on student IDs and exam models)
        successful_df = summary_df[summary_df['Status'] == 'SUCCESS']
        if len(successful_df) > 0:
            complete_ids = len(successful_df[successful_df['Student ID'].str.contains('Complete', na=False)])
            valid_models = len(successful_df[successful_df['Exam Model'].str.contains('Valid', na=False)])
            
            completeness = (complete_ids + valid_models) / (len(successful_df) * 2)
            metrics['data_completeness_score'] = round(completeness * 100, 1)
        
        # Consistency score (variation in completion rates)
        if detailed_df is not None and len(detailed_df) > 0:
            completion_rates = []
            for page in detailed_df['Page'].unique():
                page_data = detailed_df[detailed_df['Page'] == page]
                answered = len(page_data[page_data['Answer'] != 'BLANK'])
                rate = answered / len(page_data) * 100
                completion_rates.append(rate)
            
            if completion_rates:
                std_dev = np.std(completion_rates)
                consistency = max(0, 100 - std_dev)  # Lower std dev = higher consistency
                metrics['consistency_score'] = round(consistency, 1)
        
        # Overall quality score
        scores = [metrics['processing_success_rate'], metrics['data_completeness_score'], metrics['consistency_score']]
        valid_scores = [s for s in scores if s > 0]
        if valid_scores:
            metrics['overall_quality_score'] = round(np.mean(valid_scores), 1)
        
        return metrics
    
    def _calculate_cross_session_stats(self, sessions: List[Dict]) -> Dict:
        """Calculate statistics across multiple sessions."""
        total_pages = sum(s['overview']['total_pages'] for s in sessions)
        successful_pages = sum(s['overview']['successful_pages'] for s in sessions)
        
        all_completion_rates = []
        all_models_used = []
        
        for session in sessions:
            if session.get('completion_analysis', {}).get('average_completion_rate'):
                all_completion_rates.append(session['completion_analysis']['average_completion_rate'])
            
            if session.get('exam_model_analysis', {}).get('models_used'):
                all_models_used.extend(session['exam_model_analysis']['models_used'])
        
        return {
            'total_pages_all_sessions': total_pages,
            'successful_pages_all_sessions': successful_pages,
            'overall_success_rate': round(successful_pages / total_pages * 100, 1) if total_pages > 0 else 0,
            'average_completion_rate_all_sessions': round(np.mean(all_completion_rates), 1) if all_completion_rates else 0,
            'unique_models_used': list(set(all_models_used)),
            'most_popular_model': Counter(all_models_used).most_common(1)[0][0] if all_models_used else None
        }

def main():
    """Example usage of the results aggregator."""
    print("📊 Results Aggregator")
    print("=" * 30)
    
    aggregator = ResultsAggregator()
    
    # Example: find all session directories
    session_pattern = input("Enter session directories pattern (e.g., exam_results/*/): ").strip()
    if not session_pattern:
        session_pattern = "exam_results/*/"
    
    session_dirs = glob.glob(session_pattern)
    session_dirs = [d for d in session_dirs if os.path.isdir(d)]
    
    if not session_dirs:
        print(f"No session directories found matching: {session_pattern}")
        return
    
    print(f"Found {len(session_dirs)} session directories:")
    for i, d in enumerate(session_dirs[:5]):  # Show first 5
        print(f"  {i+1}. {d}")
    if len(session_dirs) > 5:
        print(f"  ... and {len(session_dirs) - 5} more")
    
    # Process single session or compare multiple
    if len(session_dirs) == 1:
        print(f"\n📈 Analyzing single session: {session_dirs[0]}")
        results = aggregator.aggregate_session_results(session_dirs[0])
        
        # Generate Excel report
        output_file = f"analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        aggregator.generate_comprehensive_report(results, output_file)
        
    else:
        print(f"\n📊 Comparing {len(session_dirs)} sessions...")
        comparison = aggregator.compare_multiple_sessions(session_dirs)
        
        print("\n📋 Session Summary:")
        for summary in comparison['session_summaries']:
            print(f"  {summary['name']}: {summary['successful_pages']}/{summary['total_pages']} pages "
                  f"({summary['success_rate']:.1f}%), avg completion: {summary['avg_completion']:.1f}%")
        
        print(f"\n📊 Overall Statistics:")
        stats = comparison['aggregate_stats']
        print(f"  Total pages: {stats['total_pages_all_sessions']}")
        print(f"  Success rate: {stats['overall_success_rate']:.1f}%")
        print(f"  Average completion: {stats['average_completion_rate_all_sessions']:.1f}%")
        print(f"  Models used: {', '.join(stats['unique_models_used'])}")

if __name__ == "__main__":
    main()
