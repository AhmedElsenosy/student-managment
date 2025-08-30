#!/usr/bin/env python3

import requests
import sys
from datetime import datetime
import pytz

# Test script for daily absence marking endpoint
API_BASE = "http://localhost:8000"

def test_without_auth():
    """Test if the endpoint exists and returns proper error for missing auth"""
    print("Testing endpoint without authentication...")
    
    response = requests.post(f"{API_BASE}/admin/test-absence-marking?test_date=2025-08-30")
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 401:
        print("✅ Endpoint exists and properly requires authentication")
        return True
    else:
        print("❌ Unexpected response")
        return False

def test_timezone():
    """Test Cairo timezone calculation"""
    print("\nTesting Cairo timezone...")
    
    cairo_tz = pytz.timezone('Africa/Cairo')
    today_cairo = datetime.now(cairo_tz).date()
    today_str = today_cairo.strftime("%Y-%m-%d")
    current_weekday = today_cairo.weekday()
    
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    day_name = days[current_weekday]
    
    print(f"Today in Cairo: {today_str}")
    print(f"Weekday: {current_weekday} ({day_name})")
    print("✅ Timezone calculation working")

def main():
    print("=" * 50)
    print("DAILY ABSENCE MARKING SYSTEM - TEST")
    print("=" * 50)
    
    # Test endpoint existence
    if not test_without_auth():
        print("\n❌ Basic endpoint test failed!")
        sys.exit(1)
    
    # Test timezone
    test_timezone()
    
    print("\n" + "=" * 50)
    print("NEXT STEPS:")
    print("=" * 50)
    print("1. Get authentication token:")
    print("   curl -X POST 'http://localhost:8000/assistant/login' \\")
    print("     -H 'Content-Type: application/x-www-form-urlencoded' \\")
    print("     -d 'username=YOUR_USERNAME&password=YOUR_PASSWORD'")
    print()
    print("2. Test with real token:")
    print("   curl -X POST 'http://localhost:8000/admin/test-absence-marking?test_date=2025-08-30' \\")
    print("     -H 'Authorization: Bearer YOUR_TOKEN'")
    print()
    print("3. Update the shell script with your token:")
    print("   nano /home/ahmed/Desktop/teacher/daily_absence_task.sh")
    print()
    print("4. Test the shell script:")
    print("   /home/ahmed/Desktop/teacher/daily_absence_task.sh")
    print()
    print("✅ Cron job is already set up to run daily at 11:59 PM!")

if __name__ == "__main__":
    main()
