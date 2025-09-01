#!/usr/bin/env python3
"""
Simple test script to create a student with UID 10012 directly in the database.
"""

import asyncio
from datetime import datetime, date
from motor.motor_asyncio import AsyncIOMotorClient

# MongoDB connection (adjust if needed)
MONGO_URI = "mongodb://localhost:27017"
DATABASE_NAME = "teacher_app"

async def create_test_student():
    """Create a test student with UID 10012"""
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DATABASE_NAME]
    students_collection = db["students"]
    
    try:
        # Test student data
        student_data = {
            "student_id": 10012,
            "uid": 10012,
            "first_name": "Test",
            "last_name": "Student",
            "email": "test10012@example.com",
            "phone_number": "01234567890",
            "guardian_number": "01987654321",
            "birth_date": datetime(2000, 1, 15),
            "national_id": "12345678901234",
            "gender": "male",
            "level": 1,
            "school_name": "Test School",
            "is_subscription": True,
            "created_at": datetime.utcnow(),
            "exams": [],
            "attendance": {},
            "subscription": {},
            "months_without_payment": 0,
            "archived": False,
            "fingerprint_template": None
        }
        
        print(f"🚀 Creating student with UID {student_data['uid']}...")
        
        # Insert into database
        result = await students_collection.insert_one(student_data)
        
        print(f"✅ Student created successfully!")
        print(f"   - Database ID: {result.inserted_id}")
        print(f"   - Student ID: {student_data['student_id']}")
        print(f"   - UID: {student_data['uid']}")
        print(f"   - Name: {student_data['first_name']} {student_data['last_name']}")
        print(f"   - Phone: {student_data['phone_number']}")
        
        # Verify it was created
        created_student = await students_collection.find_one({"uid": 10012})
        if created_student:
            print(f"🔍 Verification: Student with UID 10012 found in database")
        else:
            print(f"❌ Verification failed: Student not found")
            
        return True
        
    except Exception as e:
        print(f"❌ Error creating student: {e}")
        return False
    finally:
        client.close()

if __name__ == "__main__":
    success = asyncio.run(create_test_student())
    if success:
        print("🎉 Test completed successfully!")
    else:
        print("💥 Test failed!")
