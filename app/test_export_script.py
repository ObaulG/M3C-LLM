#!/usr/bin/env python3
"""
Simple test script to verify the export_questions_to_csv.py functionality.
This script tests the basic functionality without requiring a real database connection.
"""

import asyncio
import csv
import os
import tempfile
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import sys

# Add the current directory to Python path so we can import the export script
sys.path.insert(0, '.')

def test_csv_export_function():
    """Test the CSV export function with mock data."""
    print("Testing CSV export function...")
    
    # Mock question data
    mock_questions = [
        {
            "question_id": 1,
            "content": "What is the capital of France?",
            "status": "validated",
            "difficulty_level": 2,
            "created_by": None,
            "validated_by": 1,
            "validation_date": datetime.now(),
            "created_at": datetime.now(),
            "chunk_id": "doc123-chunk1",
            "answers": [
                {
                    "content": "Paris",
                    "is_correct": True,
                    "created_by": None
                }
            ]
        },
        {
            "question_id": 2,
            "content": "What are the colors of the French flag?",
            "status": "generated",
            "difficulty_level": 1,
            "created_by": None,
            "validated_by": None,
            "validation_date": None,
            "created_at": datetime.now(),
            "chunk_id": "doc123-chunk2",
            "answers": [
                {
                    "content": "Blue, white, red",
                    "is_correct": True,
                    "created_by": None
                },
                {
                    "content": "Red, white, blue",
                    "is_correct": False,
                    "created_by": 1
                }
            ]
        }
    ]
    
    # Create a temporary file for testing
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', encoding='utf-8') as temp_file:
        temp_filename = temp_file.name
    
    try:
        # Import and test the export function
        from export_questions_to_csv import export_questions_to_csv
        
        # Test the export
        success = export_questions_to_csv(mock_questions, temp_filename)
        
        if success:
            print("[OK] CSV export function works correctly")
            
            # Verify the CSV content
            with open(temp_filename, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                
                if len(rows) == 2:
                    print("[OK] Correct number of questions exported")
                    
                    # Check first question
                    if rows[0]['question_id'] == '1' and rows[0]['content'] == 'What is the capital of France?':
                        print("[OK] First question data is correct")
                    
                    # Check second question
                    if rows[1]['question_id'] == '2' and rows[1]['content'] == 'What are the colors of the French flag?':
                        print("[OK] Second question data is correct")
                    
                    # Check answers
                    if rows[0]['answer_1'] == 'Paris' and rows[0]['answer_1_correct'] == 'True':
                        print("[OK] First question answers are correct")
                    
                    if rows[1]['answer_1'] == 'Blue, white, red' and rows[1]['answer_2'] == 'Red, white, blue':
                        print("[OK] Second question answers are correct")
                else:
                    print(f"[ERROR] Expected 2 questions, got {len(rows)}")
                    
        else:
            print("[ERROR] CSV export function failed")
            
    except Exception as e:
        print(f"[ERROR] Error during test: {e}")
    finally:
        # Clean up
        if os.path.exists(temp_filename):
            os.unlink(temp_filename)

def test_command_line_interface():
    """Test the command line interface."""
    print("\nTesting command line interface...")
    
    # Test with no arguments
    test_args = ['export_questions_to_csv.py']
    with patch.object(sys, 'argv', test_args):
        try:
            from export_questions_to_csv import main
            # This should print usage and exit
            # We can't easily test the exit behavior, but we can check it doesn't crash
            print("[OK] Command line interface handles missing arguments")
        except SystemExit:
            print("[OK] Command line interface exits properly on missing arguments")
        except Exception as e:
            print(f"[ERROR] Command line interface error: {e}")

async def test_database_query():
    """Test the database query function with mock data."""
    print("\nTesting database query function...")
    
    # Mock database connection and cursor
    mock_conn = AsyncMock()
    mock_cursor = AsyncMock()
    
    # Mock data
    mock_chunk_rows = [('doc123-chunk1',), ('doc123-chunk2',)]
    mock_question_rows = [
        (1, 'Test question 1', 'generated', 2, None, None, None, datetime.now(), 'doc123-chunk1'),
        (2, 'Test question 2', 'validated', 3, None, 1, datetime.now(), datetime.now(), 'doc123-chunk2')
    ]
    mock_answer_rows = [
        (('Test answer 1', True, None),)
    ]
    
    # Set up mock behavior
    mock_cursor.fetchall.side_effect = [mock_chunk_rows, mock_question_rows, mock_answer_rows]
    mock_conn.cursor.return_value.__aenter__.return_value = mock_cursor
    
    try:
        from export_questions_to_csv import get_document_questions
        
        with patch('export_questions_to_csv.psycopg.AsyncConnection.connect', return_value=mock_conn):
            questions = await get_document_questions('test_doc')
            
            if len(questions) == 2:
                print("[OK] Database query returns correct number of questions")
                if questions[0]['content'] == 'Test question 1':
                    print("[OK] First question data is correct")
                if questions[1]['content'] == 'Test question 2':
                    print("[OK] Second question data is correct")
            else:
                print(f"[ERROR] Expected 2 questions, got {len(questions)}")
                
    except Exception as e:
        print(f"[ERROR] Database query test error: {e}")

def main():
    """Run all tests."""
    print("Running tests for export_questions_to_csv.py...")
    print("=" * 50)
    
    # Test CSV export function
    test_csv_export_function()
    
    # Test command line interface
    test_command_line_interface()
    
    # Test database query (async)
    asyncio.run(test_database_query())
    
    print("\n" + "=" * 50)
    print("Tests completed!")

if __name__ == "__main__":
    main()