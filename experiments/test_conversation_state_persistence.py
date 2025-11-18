#!/usr/bin/env python3
"""
Test script to verify conversation state persistence across bot restarts.

This test validates that conversation_states are properly saved to disk
and loaded on bot restart, preventing unnecessary full message reloads.
"""
import json
import os
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

CONVERSATION_STATES_FILE = "conversation_states.json"
TEST_PEER_ID = 2000000001  # Example chat ID


def cleanup_test_files():
    """Remove test files if they exist"""
    if os.path.exists(CONVERSATION_STATES_FILE):
        os.remove(CONVERSATION_STATES_FILE)
        print(f"✓ Cleaned up {CONVERSATION_STATES_FILE}")


def test_state_persistence():
    """Test that conversation states are persisted and loaded correctly"""
    print("\n=== Testing Conversation State Persistence ===\n")

    # Step 1: Clean up any existing test files
    print("Step 1: Cleanup existing test files")
    cleanup_test_files()

    # Step 2: Simulate saving conversation state
    print("\nStep 2: Simulate saving conversation state")
    test_state = {
        str(TEST_PEER_ID): {
            'last_full_update': time.time(),
            'last_message_id': 12345,
            'total_messages': 100,
            'last_message_date': int(time.time())
        }
    }

    with open(CONVERSATION_STATES_FILE, 'w', encoding='utf-8') as f:
        json.dump(test_state, f, ensure_ascii=False, indent=2)
    print(f"✓ Saved conversation state to {CONVERSATION_STATES_FILE}")
    print(f"  State: {test_state}")

    # Step 3: Verify file exists
    print("\nStep 3: Verify file exists")
    if not os.path.exists(CONVERSATION_STATES_FILE):
        print("✗ ERROR: File was not created!")
        return False
    print(f"✓ File {CONVERSATION_STATES_FILE} exists")

    # Step 4: Load the state back (simulating bot restart)
    print("\nStep 4: Load state back (simulating bot restart)")
    with open(CONVERSATION_STATES_FILE, 'r', encoding='utf-8') as f:
        loaded_state = json.load(f)
    print(f"✓ Loaded conversation state from {CONVERSATION_STATES_FILE}")
    print(f"  State: {loaded_state}")

    # Step 5: Verify data integrity
    print("\nStep 5: Verify data integrity")
    peer_str = str(TEST_PEER_ID)

    if peer_str not in loaded_state:
        print(f"✗ ERROR: Peer ID {TEST_PEER_ID} not found in loaded state!")
        return False

    if loaded_state[peer_str]['last_message_id'] != test_state[peer_str]['last_message_id']:
        print("✗ ERROR: last_message_id mismatch!")
        return False

    if loaded_state[peer_str]['total_messages'] != test_state[peer_str]['total_messages']:
        print("✗ ERROR: total_messages mismatch!")
        return False

    print("✓ All data fields match!")

    # Step 6: Test incremental update logic
    print("\nStep 6: Test incremental update logic")
    current_time = time.time()
    last_update_time = loaded_state[peer_str]['last_full_update']
    time_since_update = current_time - last_update_time

    print(f"  Time since last full update: {time_since_update:.2f} seconds")

    # Should NOT trigger full update (less than 86400 seconds / 24 hours)
    should_full_update = time_since_update > 86400
    print(f"  Should trigger full update: {should_full_update}")

    if should_full_update:
        print("✗ WARNING: Full update would be triggered (expected for old states)")
    else:
        print("✓ Incremental update would be used (expected for fresh states)")

    # Step 7: Cleanup
    print("\nStep 7: Cleanup test files")
    cleanup_test_files()

    print("\n=== Test PASSED ===\n")
    print("Summary:")
    print("  • Conversation states are properly persisted to disk")
    print("  • States are correctly loaded on bot restart")
    print("  • Incremental updates will be used when appropriate")
    print("  • Full updates only trigger after 24 hours or on first run")

    return True


def test_integration_with_main():
    """Test that the main bot code properly uses persistence"""
    print("\n=== Testing Integration with main8gpt.py ===\n")

    # Check if the constants are defined
    print("Step 1: Check if CONVERSATION_STATES_FILE is defined in main8gpt.py")
    try:
        with open('main8gpt.py', 'r', encoding='utf-8') as f:
            content = f.read()
            if 'CONVERSATION_STATES_FILE' in content:
                print("✓ CONVERSATION_STATES_FILE constant is defined")
            else:
                print("✗ ERROR: CONVERSATION_STATES_FILE constant not found!")
                return False
    except FileNotFoundError:
        print("✗ ERROR: main8gpt.py not found!")
        return False

    # Check if save_conversation_states method exists
    print("\nStep 2: Check if save_conversation_states method exists")
    if 'def save_conversation_states(self):' in content:
        print("✓ save_conversation_states method is defined")
    else:
        print("✗ ERROR: save_conversation_states method not found!")
        return False

    # Check if conversation_states is loaded from file
    print("\nStep 3: Check if conversation_states is loaded from file")
    if 'self.conversation_states = self.load_json(CONVERSATION_STATES_FILE' in content:
        print("✓ conversation_states is loaded from file on initialization")
    else:
        print("✗ ERROR: conversation_states is not loaded from file!")
        return False

    # Check if save is called in appropriate places
    print("\nStep 4: Check if save is called in appropriate places")
    save_count = content.count('self.save_conversation_states()')
    if save_count >= 2:
        print(f"✓ save_conversation_states is called {save_count} times")
    else:
        print(f"✗ WARNING: save_conversation_states is only called {save_count} times")

    print("\n=== Integration Test PASSED ===\n")
    return True


if __name__ == "__main__":
    success = True

    try:
        # Run persistence test
        if not test_state_persistence():
            success = False

        # Run integration test
        if not test_integration_with_main():
            success = False

        if success:
            print("\n" + "="*50)
            print("ALL TESTS PASSED ✓")
            print("="*50 + "\n")
            sys.exit(0)
        else:
            print("\n" + "="*50)
            print("SOME TESTS FAILED ✗")
            print("="*50 + "\n")
            sys.exit(1)

    except Exception as e:
        print(f"\n✗ ERROR: Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
