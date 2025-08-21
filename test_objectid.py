#!/usr/bin/env python3
"""
Test script to debug ObjectId validation
"""

from bson import ObjectId
import sys

def test_objectid(id_string):
    print(f"Testing ObjectId: '{id_string}'")
    print(f"Length: {len(id_string)}")
    print(f"Type: {type(id_string)}")
    
    # Test basic ObjectId validation
    is_valid = ObjectId.is_valid(id_string)
    print(f"ObjectId.is_valid(): {is_valid}")
    
    if is_valid:
        try:
            oid = ObjectId(id_string)
            print(f"✓ Successfully created ObjectId: {oid}")
            print(f"✓ String representation: {str(oid)}")
            return True
        except Exception as e:
            print(f"✗ Error creating ObjectId: {e}")
            return False
    else:
        print("✗ Invalid ObjectId format")
        return False

if __name__ == "__main__":
    # Test with your specific ID
    test_id = "688f6e20c4535772b8b81c26"
    
    print("=" * 50)
    print("OBJECTID VALIDATION TEST")
    print("=" * 50)
    
    success = test_objectid(test_id)
    
    if not success:
        print("\nTroubleshooting:")
        print("1. ObjectId must be exactly 24 characters")
        print("2. ObjectId must contain only hexadecimal characters (0-9, a-f)")
        print("3. Check for any hidden characters or spaces")
