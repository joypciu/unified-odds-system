"""Check available Google models"""
import os
from google import genai
from google.genai import types

os.environ['GOOGLE_API_KEY'] = "AIzaSyCqS5F_fbYzB-ZUHKOdGXrVpmRYaQ9jVbU"
client = genai.Client(api_key=os.environ['GOOGLE_API_KEY'])

print("Available Google Gemini models:")
print("=" * 60)

try:
    models = client.models.list()
    for model in models:
        print(f"\nModel: {model.name}")
        if hasattr(model, 'display_name'):
            print(f"Display Name: {model.display_name}")
        if hasattr(model, 'description'):
            desc = model.description or "No description"
            print(f"Description: {desc[:100]}...")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
