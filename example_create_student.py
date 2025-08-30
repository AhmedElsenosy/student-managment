#!/usr/bin/env python3
"""
Example usage of the create_student_script module.
Shows how to use the script programmatically to create students.
"""

import asyncio
from datetime import date
from create_student_script import create_student_from_data

async def create_multiple_students():
    """Example: Create multiple students programmatically"""
    
    students_to_create = [
        {
            "first_name": "Sara",
            "last_name": "Ahmed",
            "email": "sara.ahmed@email.com",
            "phone_number": "01111111111",
            "guardian_number": "01222222222",
            "birth_date": date(2001, 3, 10),
            "national_id": "11111111111111",
            "gender": "female",
            "level": 1,
            "school_name": "Cairo International School",
            "is_subscription": True
        },
        {
            "first_name": "Omar",
            "last_name": "Hassan",
            "email": None,  # Optional field
            "phone_number": "01333333333",
            "guardian_number": "01444444444",
            "birth_date": date(2000, 7, 22),
            "national_id": "22222222222222",
            "gender": "male",
            "level": 3,
            "school_name": "Alexandria High School",
            "is_subscription": False
        },
        {
            "first_name": "Menna",
            "last_name": "Khaled",
            "email": "menna.khaled@email.com",
            "phone_number": "01555555555",
            "guardian_number": "01666666666",
            "birth_date": None,  # Optional field
            "national_id": None,  # Optional field
            "gender": "female",
            "level": 2,
            "school_name": None,  # Optional field
            "is_subscription": True
        }
    ]
    
    print("🎓 Creating multiple students...")
    print("=" * 50)
    
    for i, student_data in enumerate(students_to_create, 1):
        print(f"\n📝 Creating student {i}/3: {student_data['first_name']} {student_data['last_name']}")
        try:
            created_student = await create_student_from_data(student_data.copy())
            if created_student:
                print(f"   ✅ Successfully created student {created_student['student_id']}")
            else:
                print(f"   ❌ Failed to create student")
        except Exception as e:
            print(f"   ❌ Error: {e}")

def create_single_student_example():
    """Example: Create a single student with minimal data"""
    
    minimal_student = {
        "first_name": "Youssef",
        "last_name": "Mohamed",
        "phone_number": "01777777777",
        "guardian_number": "01888888888",
        "gender": "male",
        "level": 1,
        "is_subscription": True
    }
    
    print("🎓 Creating student with minimal data...")
    print("=" * 40)
    
    # Run the async function
    result = asyncio.run(create_student_from_data(minimal_student))
    
    if result:
        print("🎉 Student creation completed!")
    else:
        print("❌ Student creation failed!")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--multiple":
            # Create multiple students
            asyncio.run(create_multiple_students())
        elif sys.argv[1] == "--single":
            # Create single student
            create_single_student_example()
        else:
            print("Usage:")
            print("  python example_create_student.py --multiple  # Create multiple students")
            print("  python example_create_student.py --single    # Create single student")
    else:
        print("Student Creation Examples")
        print("========================")
        print()
        print("Usage:")
        print("  python example_create_student.py --multiple  # Create multiple students")
        print("  python example_create_student.py --single    # Create single student")
        print()
        print("You can also import this module and use the functions directly:")
        print("  from example_create_student import create_multiple_students")
        print("  asyncio.run(create_multiple_students())")
