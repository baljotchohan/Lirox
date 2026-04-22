import os
from lirox.utils.llm import generate_response

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    prompt = "ok so create a pdf with name lirox.pdf add all fdetailes of future of ai in that pdf use browser to get real data make fully detailed pdf"
    print("Testing generate_response with prompt:", prompt)
    resp = generate_response(prompt)
    print("Response:", resp)
