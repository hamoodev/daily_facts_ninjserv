#!/usr/bin/env python3
"""
Test script for AOTTG score decoder functionality
"""

import sys
import os

# Add src directory to path so we can import our modules
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from utils.score_decoder import decode_and_verify, parse_score_data


def test_score_decoder():
    """Test the score decoder with various test cases"""
    print("🧪 Testing AOTTG Score Decoder")
    print("=" * 50)
    
    # Test cases: (code, expected_valid, expected_kills, expected_deaths)
    test_cases = [
        # Valid test cases  
        ("WYAR-126", True, 15, 3),  # 15 kills, 3 deaths
        ("QAAA-0", True, 0, 0),     # 0 kills, 0 deaths
        ("WAAA-7", True, 1, 0),     # 1 kill, 0 deaths
        ("QAAW-14", True, 0, 1),    # 0 kills, 1 death
        
        # Invalid test cases
        ("INVALID", False, None, None),  # No checksum separator
        ("WYAR-999", False, None, None), # Wrong checksum
        ("XYZ-123", False, None, None),  # Invalid characters
        ("WY-123", False, None, None),   # Missing data
        ("", False, None, None),         # Empty string
    ]
    
    passed = 0
    total = len(test_cases)
    
    for i, (code, expected_valid, expected_kills, expected_deaths) in enumerate(test_cases, 1):
        print(f"\nTest {i}: {code}")
        
        try:
            # Test decode_and_verify
            result = decode_and_verify(code)
            
            if result["valid"] != expected_valid:
                print(f"❌ FAIL: Expected valid={expected_valid}, got {result['valid']}")
                if result.get("error"):
                    print(f"   Error: {result['error']}")
                continue
            
            if expected_valid:
                # Test parse_score_data
                score_data = parse_score_data(result["decoded"])
                
                if not score_data["valid"]:
                    print(f"❌ FAIL: Score parsing failed: {score_data.get('error')}")
                    continue
                
                if score_data["kills"] != expected_kills or score_data["deaths"] != expected_deaths:
                    print(f"❌ FAIL: Expected {expected_kills}|{expected_deaths}, got {score_data['kills']}|{score_data['deaths']}")
                    continue
                
                kd_ratio = expected_kills / expected_deaths if expected_deaths > 0 else float(expected_kills)
                print(f"✅ PASS: {expected_kills} kills, {expected_deaths} deaths, K/D: {kd_ratio:.2f}")
            else:
                print(f"✅ PASS: Correctly rejected invalid code")
                if result.get("error"):
                    print(f"   Reason: {result['error']}")
            
            passed += 1
            
        except Exception as e:
            print(f"❌ FAIL: Exception occurred: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        return True
    else:
        print("❌ Some tests failed!")
        return False


def demo_score_codes():
    """Demonstrate how to create valid score codes"""
    print("\n🎮 Example Valid Score Codes:")
    print("=" * 50)
    
    examples = [
        ("15 kills, 3 deaths", "WYAR-126"),
        ("25 kills, 8 deaths", "EYAO-203"),  
        ("0 kills, 0 deaths", "QAAA-0"),
        ("100 kills, 10 deaths", "WQQAW-217"),
    ]
    
    for description, code in examples:
        result = decode_and_verify(code)
        if result["valid"]:
            score_data = parse_score_data(result["decoded"])
            if score_data["valid"]:
                print(f"✅ {code} → {description} (K/D: {score_data['kd_ratio']:.2f})")
            else:
                print(f"❌ {code} → Parse error")
        else:
            print(f"❌ {code} → Invalid")


if __name__ == "__main__":
    success = test_score_decoder()
    demo_score_codes()
    
    if success:
        print("\n✅ Score decoder is working correctly!")
        sys.exit(0)
    else:
        print("\n❌ Score decoder has issues!")
        sys.exit(1) 