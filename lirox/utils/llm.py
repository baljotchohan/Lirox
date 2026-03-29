import os
import requests
import google.generativeai as genai
import json

def get_api_key(name):
    return os.getenv(name)

def get_system_prompt():
    return os.getenv("SYSTEM_PROMPT", "You are Lirox, a helpful and concise local AI agent.")

def openai_call(prompt, model="gpt-4o"):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key: return "OpenAI API key missing."
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    data = {
        "model": model, 
        "messages": [
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": prompt}
        ]
    }
    response = requests.post(url, headers=headers, json=data)
    return response.json().get('choices', [{}])[0].get('message', {}).get('content', "Error in OpenAI call")

def gemini_call(prompt):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: return "Gemini API key missing."
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    # Gemini uses a different system instruction format, but for now we prepend it
    full_prompt = f"{get_system_prompt()}\n\nUser Question: {prompt}"
    response = model.generate_content(full_prompt)
    return response.text

def openrouter_call(prompt, model="arcee-ai/trinity-large-preview:free"):
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key: return "OpenRouter API key missing."
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    data = {
        "model": model, 
        "messages": [
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": prompt}
        ]
    }
    response = requests.post(url, headers=headers, json=data)
    return response.json().get('choices', [{}])[0].get('message', {}).get('content', "Error in OpenRouter call")

def groq_call(prompt, model="llama-3.3-70b-versatile"):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key: return "Groq API key missing."
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    data = {
        "model": model, 
        "messages": [
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": prompt}
        ]
    }
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code != 200:
            return f"Groq API Error ({response.status_code}): {response.text}"
        return response.json().get('choices', [{}])[0].get('message', {}).get('content', "Error in Groq call")
    except Exception as e:
        return f"Groq Connection Error: {str(e)}"

def deepseek_call(prompt, model="deepseek-chat"):
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key: return "DeepSeek API key missing."
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    data = {
        "model": model, 
        "messages": [
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": prompt}
        ]
    }
    response = requests.post(url, headers=headers, json=data)
    return response.json().get('choices', [{}])[0].get('message', {}).get('content', "Error in DeepSeek call")

def nvidia_call(prompt, model="google/gemma-3n-e4b-it"):
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key: return "NVIDIA API key missing."
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 1024,
        "temperature": 0.20,
        "top_p": 0.70,
        "frequency_penalty": 0.00,
        "presence_penalty": 0.00,
        "stream": False
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code != 200:
            return f"NVIDIA API Error ({response.status_code}): {response.text}"
        data = response.json()
        return data.get('choices', [{}])[0].get('message', {}).get('content', "No content from NVIDIA.")
    except Exception as e:
        return f"NVIDIA Connection Error: {str(e)}"

def generate_response(prompt, provider="openai"):
    provider = provider.lower().strip("[]'\" ")
    if provider == "openai": return openai_call(prompt)
    if provider == "gemini": return gemini_call(prompt)
    if provider == "openrouter": return openrouter_call(prompt)
    if provider == "groq": return groq_call(prompt)
    if provider == "deepseek": return deepseek_call(prompt)
    if provider == "nvidia": return nvidia_call(prompt)
    return f"Unknown provider: {provider}"

def smart_router(prompt):
    p_lower = prompt.lower()
    if any(k in p_lower for k in ["code", "create", "python", "script", "install"]):
        return "groq"
    if any(k in p_lower for k in ["research", "who is", "what is", "explain"]):
        return "openrouter"
    return "openai"
