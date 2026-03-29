import requests
import google.generativeai as genai
import json
from lirox.config import (
    OPENAI_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY, 
    GROQ_API_KEY, DEEPSEEK_API_KEY, NVIDIA_API_KEY, SYSTEM_PROMPT
)

def openai_call(prompt, model="gpt-4o"):
    if not OPENAI_API_KEY: return "OpenAI API key missing."
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    data = {
        "model": model, 
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
    }
    response = requests.post(url, headers=headers, json=data)
    return response.json().get('choices', [{}])[0].get('message', {}).get('content', "Error in OpenAI call")

def gemini_call(prompt):
    if not GEMINI_API_KEY: return "Gemini API key missing."
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.0-flash')
    # Gemini uses a different system instruction format, but for now we prepend it
    full_prompt = f"{SYSTEM_PROMPT}\n\nUser Question: {prompt}"
    response = model.generate_content(full_prompt)
    return response.text

def openrouter_call(prompt, model="arcee-ai/trinity-large-preview:free"):
    if not OPENROUTER_API_KEY: return "OpenRouter API key missing."
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}
    data = {
        "model": model, 
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
    }
    response = requests.post(url, headers=headers, json=data)
    return response.json().get('choices', [{}])[0].get('message', {}).get('content', "Error in OpenRouter call")

def groq_call(prompt, model="llama3-8b-8192"):
    if not GROQ_API_KEY: return "Groq API key missing."
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    data = {
        "model": model, 
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
    }
    response = requests.post(url, headers=headers, json=data)
    return response.json().get('choices', [{}])[0].get('message', {}).get('content', "Error in Groq call")

def deepseek_call(prompt, model="deepseek-chat"):
    if not DEEPSEEK_API_KEY: return "DeepSeek API key missing."
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}"}
    data = {
        "model": model, 
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
    }
    response = requests.post(url, headers=headers, json=data)
    return response.json().get('choices', [{}])[0].get('message', {}).get('content', "Error in DeepSeek call")

def nvidia_call(prompt, model="google/gemma-3n-e4b-it"):
    if not NVIDIA_API_KEY: return "NVIDIA API key missing."
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
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
