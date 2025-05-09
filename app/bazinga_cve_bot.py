import logging
import json
import asyncio
import aiohttp
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Environment variables
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
MODEL_HUMOR_PATH = os.getenv('MODEL_HUMOR_PATH')
OLLAMA_API_URL = os.getenv('OLLAMA_API_URL')
PROJECT_CONTEXT_INFO = os.getenv('PROJECT_CONTEXT_INFO', 'Keine weiteren Informationen')

# Validate required variables
if not DISCORD_WEBHOOK_URL:
    raise ValueError('DISCORD_WEBHOOK_URL is missing in the environment or .env file.')
if not MODEL_HUMOR_PATH:
    raise ValueError('MODEL_HUMOR_PATH is missing in the environment or .env file.')
if not OLLAMA_API_URL:
    raise ValueError('OLLAMA_API_URL is missing in the environment or .env file.')

# Severity ranking
SEVERITY_ORDER = {
    'CRITICAL': 0,
    'HIGH': 1,
    'MEDIUM': 2,
    'LOW': 3,
    'UNKNOWN': 4
}

# Load Trivy logs
def load_trivy_logs(log_path='trivy_output.json'):
    try:
        with open(log_path, 'r') as f:
            data = json.load(f)
        vulns = []
        if isinstance(data, dict) and 'Results' in data:
            for result in data['Results']:
                vulns.extend(result.get('Vulnerabilities', []))
        elif isinstance(data, dict) and 'vulnerabilities' in data:
            vulns = data['vulnerabilities']
        return vulns
    except Exception as e:
        logging.error(f'Error loading trivy logs: {e}')
        return []

# Build prompt
def build_prompt_with_logs(logs, context):
    try:
        base = open(MODEL_HUMOR_PATH, 'r').read().strip()
        # Adjust for style & language
        style = context.get('style', 'neutral')
        lang = context.get('language', 'de')
        if style == 'sarkastisch':
            base += '\n(Verwende einen sarkastischen Ton!)'
        elif style == 'freundlich':
            base += '\n(Verwende einen freundlichen Ton!)'
        lang_note = 'Verwende deutsche Sprache.' if lang=='de' else 'Use English.'

        sorted_logs = sorted(logs, key=lambda x: SEVERITY_ORDER.get(x.get('Severity','UNKNOWN'), 100))
        snippet = json.dumps(sorted_logs[:5], indent=2)

        return f"""
{base}

Here are the top vulnerabilities:
{snippet}

{lang_note}
Jetzt roast each one with Gordon Ramsay intensity, stand-up timing, DevOps frustration!"""
    except Exception as e:
        logging.error(f'Error building prompt: {e}')
        return ''

# Send to Ollama
async def send_prompt_to_ollama(prompt, model='deepseek-chat', temperature=1.0):
    url = f"{OLLAMA_API_URL}/v1/chat/completions"
    payload = {
        'model': model,
        'messages': [
            {'role':'system','content':'You are a sarcastic security assistant'},
            {'role':'user','content':prompt}
        ],
        'temperature': temperature
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers={'Content-Type':'application/json'}) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return data['choices'][0]['message']['content']
    except Exception as e:
        logging.error(f'Error calling Ollama: {e}')
        return ''

# Clean Discord message
def clean_discord_message(text, max_len=1900):
    out = text.replace('\u0000','')
    return (out[:max_len]+'\n...') if len(out)>max_len else out

# Send to Discord
async def send_discord_message_async(message):
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(DISCORD_WEBHOOK_URL, json={'content':message}, headers={'Content-Type':'application/json'})
    except Exception as e:
        logging.error(f'Error sending Discord message: {e}')

# Main
async def main():
    logs = load_trivy_logs()
    if not logs:
        return
    # Fetch context from MCP if used, else defaults
    context = {'style':'neutral','language':'de','mode':'default'}
    context['additional_info'] = PROJECT_CONTEXT_INFO

    prompt = build_prompt_with_logs(logs, context)
    if not prompt:
        return

    response = await send_prompt_to_ollama(prompt, temperature=1.1)
    msg = clean_discord_message(response)
    await send_discord_message_async(msg)

if __name__ == '__main__':
    asyncio.run(main())
