#!/usr/bin/env python3
"""
Simple test script to verify Gemini integration works
"""

import os
import asyncio
from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel

load_dotenv()

class FactResponse(BaseModel):
    """A structured fact response"""
    fact: str
    category: str = "general"

async def test_gemini():
    """Test basic Gemini integration"""
    
    # Get API key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set!")
        return False
    
    try:
        # Initialize client
        client = genai.Client(api_key=api_key)
        print("✅ Gemini client initialized successfully")
        
        # Test basic generation
        prompt = """Generate a fun 'Did you know' fact about technology. 
        Start with 'Did you know' and keep it under 200 characters."""
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": FactResponse,
                    "generation_config": {
                        "max_output_tokens": 120,
                        "temperature": 0.7
                    }
                }
            )
        )
        
        # Parse response
        fact_data = FactResponse.model_validate_json(response.text)
        print(f"✅ Generated fact: {fact_data.fact}")
        print(f"✅ Category: {fact_data.category}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing Gemini: {e}")
        return False

if __name__ == "__main__":
    print("Testing Gemini integration...")
    success = asyncio.run(test_gemini())
    
    if success:
        print("\n🎉 All tests passed! Gemini integration is working.")
    else:
        print("\n💥 Tests failed! Check your API key and configuration.") 