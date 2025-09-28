import requests

def call_agentrouter_api(prompt, model="claude-3-5-haiku-20241022"):
    url = "https://api.agentrouter.org/v1/complete"
    headers = {
        "Authorization": "sk-FHbU9oOQvFsNZua1ptb9nt9VPaftJ2i86SuKooGcxxAsubJI",  # Thay YOUR_API_KEY bằng API key của bạn
        "Content-Type": "application/json",
    }
    data = {
        "model": model,
        "input": prompt
    }
    response = requests.post(url, json=data, headers=headers)
    return response.json()
