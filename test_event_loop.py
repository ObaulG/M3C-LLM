#!/usr/bin/env python3
"""
Test script to verify the event loop policy is set correctly for Windows
"""
import sys
import asyncio

def test_event_loop_policy():
    print(f"Platform: {sys.platform}")
    print(f"Python version: {sys.version}")
    
    if sys.platform == "win32":
        print("Running on Windows - checking event loop policy...")
        
        # Check current event loop policy
        current_policy = asyncio.get_event_loop_policy()
        print(f"Current event loop policy: {current_policy}")
        
        # Check if WindowsSelectorEventLoopPolicy is available
        if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
            print("[OK] WindowsSelectorEventLoopPolicy is available")
            
            # Set the policy
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            new_policy = asyncio.get_event_loop_policy()
            print(f"[OK] Event loop policy set to: {new_policy}")
            
            # Test creating an event loop
            try:
                loop = asyncio.new_event_loop()
                print(f"[OK] Successfully created event loop: {loop}")
                loop.close()
            except Exception as e:
                print(f"[ERROR] Failed to create event loop: {e}")
                
        else:
            print("[ERROR] WindowsSelectorEventLoopPolicy is NOT available")
            print("This might cause issues with Psycopg async operations")
    else:
        print("Not running on Windows - no special event loop policy needed")

if __name__ == "__main__":
    test_event_loop_policy()