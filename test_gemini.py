import os
from google import genai
from google.genai import types

def test():
    api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        system_instruction="Hello", temperature=0.7)
    
    for model_name in ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.5-flash"]:
        try:
            res = client.models.generate_content(
                model=model_name, contents="hi", config=config)
            print("Success for model:", model_name, res.text)
        except Exception as e:
            print(f"Error for model {model_name}:", e)

if __name__ == "__main__":
    test()
