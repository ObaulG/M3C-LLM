#!/usr/bin/env python3
"""
Test script to verify the RAG pipeline initialization works with the event loop fix
"""
import sys
import asyncio
import os

# Set the event loop policy first, just like in api_server.py
if sys.platform == "win32":
    if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        print("[OK] Windows event loop policy set to WindowsSelectorEventLoopPolicy")
    else:
        print("[WARNING] WindowsSelectorEventLoopPolicy not available, trying fallback...")
        try:
            import selectors
            asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
        except:
            pass

# Now try to import and initialize the RAG pipeline
def test_rag_initialization():
    try:
        print("Attempting to import RAG pipeline...")
        from LLMAgents-These.rag_pipeline import RAGPipeline
        print("[OK] RAGPipeline imported successfully")
        
        print("Attempting to initialize RAG pipeline...")
        rag_pipeline = RAGPipeline()
        print("[OK] RAGPipeline initialized successfully")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to initialize RAG pipeline: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    print(f"Platform: {sys.platform}")
    print(f"Python version: {sys.version}")
    print(f"Current event loop policy: {asyncio.get_event_loop_policy()}")
    print()
    
    success = test_rag_initialization()
    
    if success:
        print("\n[SUCCESS] All tests passed! The event loop fix should work.")
    else:
        print("\n[FAILURE] Tests failed. The event loop issue may persist.")