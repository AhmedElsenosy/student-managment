#!/usr/bin/env python3
"""
Script to create a new student directly in the database without sending to fingerprint backend.
This bypasses the FastAPI endpoint and creates the student record directly in MongoDB.
"""

import asyncio
import sys
from datetime import datetime, date
from motor.motor_asyncio import AsyncIOMotorClient
from decouple import config
from bson import ObjectId

# Configuration
try:
    MONGO_URI = config("MONGO_URI")
    DATABASE_NAME = config("DATABASE_NAME")
except Exception as e:
    print(f"❌ Error loading configuration: {e}")
    print("Make sure you have a .env file with MONGO_URI and DATABASE_NAME")
    sys.exit(1)

# MongoDB client
client = AsyncIOMotorClient(MONGO_URI)
db = client[DATABASE_NAME]
students_collection = db["students"]
counters_collection = db["counters"]
blacklist_collection = db["blacklist_students"]

async def get_next_student_id():
    """Get the next student ID from the counter"""
    counter = await counters_collection.find_one({"name": "student_id"})
    if not counter:
        # Initialize counter if it doesn't exist
        counter = {"name": "student_id", "sequence_value": 9999}  # So first will be 10000
        await counters_collection.insert_one(counter)
        return 10000
    
    # Increment counter
    result = await counters_collection.update_one(
        {"name": "student_id"},
        {"$inc": {"sequence_value": 1}}
    )
    
    # Get updated counter
    updated_counter = await counters_collection.find_one({"name": "student_id"})
    return updated_counter["sequence_value"]

async def check_blacklist(phone_number, first_name, last_name):
    """Check if student is in blacklist"""
    # Check by phone number
    blacklisted_by_phone = await blacklist_collection.find_one(
        {"phone_number": phone_number}
    )
    
    # Check by name
    blacklisted_by_name = await blacklist_collection.find_one({
        "first_name": first_name,
        "last_name": last_name
    })
    
    return blacklisted_by_phone, blacklisted_by_name

async def create_student(student_data):
    """Create a new student directly in the database"""
    print("🔍 Checking for blacklisted students...")
    
    # Check blacklist
    blacklisted_by_phone, blacklisted_by_name = await check_blacklist(
        student_data["phone_number"],
        student_data["first_name"],
        student_data["last_name"]
    )
    
    if blacklisted_by_phone:
        raise Exception(f"❌ Cannot create student. Phone number {student_data['phone_number']} is blacklisted.")
    
    if blacklisted_by_name:
        raise Exception(f"❌ Cannot create student. Name {student_data['first_name']} {student_data['last_name']} is blacklisted.")
    
    print("✅ Student is not blacklisted, proceeding...")
    
    # Get next student ID
    print("🔢 Getting next student ID...")
    next_id = await get_next_student_id()
    student_data["student_id"] = next_id
    student_data["uid"] = next_id
    
    print(f"📝 Assigned Student ID: {next_id}")
    
    # Convert birth_date to datetime if it's a date object
    if isinstance(student_data.get("birth_date"), date):
        student_data["birth_date"] = datetime.combine(student_data["birth_date"], datetime.min.time())
    
    # Add required metadata
    student_data["created_at"] = datetime.utcnow()
    student_data["updated_at"] = None
    student_data["exams"] = []
    student_data["attendance"] = {}
    student_data["subscription"] = {}
    student_data["months_without_payment"] = 0
    student_data["archived"] = False
    student_data["fingerprint_template"] = None
    
    # Insert into database
    print("💾 Inserting student into database...")
    result = await students_collection.insert_one(student_data)
    student_data["id"] = str(result.inserted_id)
    
    print(f"✅ Student created successfully!")
    print(f"   - Database ID: {student_data['id']}")
    print(f"   - Student ID: {student_data['student_id']}")
    print(f"   - Name: {student_data['first_name']} {student_data['last_name']}")
    print(f"   - Phone: {student_data['phone_number']}")
    print(f"   - Level: {student_data['level']}")
    
    return student_data

async def interactive_create_student():
    """Interactive function to create a student"""
    print("🎓 Student Creation Script")
    print("=" * 50)
    print()
    
    try:
        # Collect student information
        print("Please provide student information:")
        
        first_name = input("👤 First Name: ").strip()
        if not first_name:
            raise ValueError("First name is required")
        
        last_name = input("👤 Last Name: ").strip()
        if not last_name:
            raise ValueError("Last name is required")
        
        email = input("📧 Email (optional): ").strip()
        if not email:
            email = None
        
        phone_number = input("📱 Phone Number: ").strip()
        if not phone_number:
            raise ValueError("Phone number is required")
        
        guardian_number = input("👨‍👩‍👧‍👦 Guardian Number: ").strip()
        if not guardian_number:
            raise ValueError("Guardian number is required")
        
        # Birth date (optional)
        birth_date_str = input("🎂 Birth Date (YYYY-MM-DD, optional): ").strip()
        birth_date = None
        if birth_date_str:
            try:
                birth_date = datetime.strptime(birth_date_str, "%Y-%m-%d").date()
            except ValueError:
                print("⚠️ Invalid date format, skipping birth date")
        
        national_id = input("🆔 National ID (optional): ").strip()
        if not national_id:
            national_id = None
        
        # Gender
        print("🚻 Gender:")
        print("  1. Male")
        print("  2. Female")
        gender_choice = input("Choose (1 or 2): ").strip()
        if gender_choice == "1":
            gender = "male"
        elif gender_choice == "2":
            gender = "female"
        else:
            raise ValueError("Invalid gender choice")
        
        # Level
        print("📚 Student Level:")
        print("  1. Level 1")
        print("  2. Level 2")
        print("  3. Level 3")
        level_choice = input("Choose (1, 2, or 3): ").strip()
        if level_choice in ["1", "2", "3"]:
            level = int(level_choice)
        else:
            raise ValueError("Invalid level choice")
        
        school_name = input("🏫 School Name (optional): ").strip()
        if not school_name:
            school_name = None
        
        # Subscription status
        print("💳 Subscription Status:")
        print("  1. Active subscription")
        print("  2. No subscription")
        subscription_choice = input("Choose (1 or 2): ").strip()
        if subscription_choice == "1":
            is_subscription = True
        elif subscription_choice == "2":
            is_subscription = False
        else:
            raise ValueError("Invalid subscription choice")
        
        # Prepare student data
        student_data = {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone_number": phone_number,
            "guardian_number": guardian_number,
            "birth_date": birth_date,
            "national_id": national_id,
            "gender": gender,
            "level": level,
            "school_name": school_name,
            "is_subscription": is_subscription
        }
        
        print()
        print("📋 Student Information Summary:")
        print("-" * 30)
        print(f"Name: {first_name} {last_name}")
        print(f"Email: {email or 'Not provided'}")
        print(f"Phone: {phone_number}")
        print(f"Guardian: {guardian_number}")
        print(f"Birth Date: {birth_date or 'Not provided'}")
        print(f"National ID: {national_id or 'Not provided'}")
        print(f"Gender: {gender}")
        print(f"Level: {level}")
        print(f"School: {school_name or 'Not provided'}")
        print(f"Subscription: {'Active' if is_subscription else 'Inactive'}")
        print()
        
        confirm = input("✅ Confirm creation? (y/N): ").strip().lower()
        if confirm != 'y':
            print("❌ Student creation cancelled.")
            return
        
        # Create the student
        created_student = await create_student(student_data)
        
        print()
        print("🎉 Student created successfully!")
        print("Note: This student was created directly in the database without syncing to the fingerprint backend.")
        
    except Exception as e:
        print(f"❌ Error creating student: {e}")
        return None

async def create_student_from_data(student_data):
    """Create student from provided data dictionary"""
    try:
        created_student = await create_student(student_data)
        return created_student
    except Exception as e:
        print(f"❌ Error creating student: {e}")
        return None
    finally:
        # Close MongoDB connection
        client.close()

def create_sample_student():
    """Create a sample student for testing"""
    sample_data = {
        "first_name": "Ahmed",
        "last_name": "Mohamed",
        "email": "ahmed.mohamed@email.com",
        "phone_number": "01234567890",
        "guardian_number": "01987654321",
        "birth_date": date(2000, 5, 15),
        "national_id": "12345678901234",
        "gender": "male",
        "level": 2,
        "school_name": "Cairo High School",
        "is_subscription": True
    }
    
    print("🧪 Creating sample student...")
    return asyncio.run(create_student_from_data(sample_data))

async def main():
    """Main function"""
    if len(sys.argv) > 1:
        if sys.argv[1] == "--sample":
            create_sample_student()
            return
        elif sys.argv[1] == "--help":
            print("Student Creation Script")
            print("Usage:")
            print("  python create_student_script.py          # Interactive mode")
            print("  python create_student_script.py --sample # Create sample student")
            print("  python create_student_script.py --help   # Show this help")
            return
    
    # Interactive mode
    try:
        await interactive_create_student()
    finally:
        # Close MongoDB connection
        client.close()

if __name__ == "__main__":
    # Run the script
    asyncio.run(main())
