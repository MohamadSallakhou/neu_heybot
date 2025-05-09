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

# Variables from the environment or .env
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
MODEL_HUMOR_PATH = os.getenv('MODEL_HUMOR_PATH')
OLLAMA_API_URL = os.getenv('OLLAMA_API_URL')

# Validate required variables
if not DISCORD_WEBHOOK_URL:
    raise ValueError("DISCORD_WEBHOOK_URL is missing in the environment or .env file.")
if not MODEL_HUMOR_PATH:
    raise ValueError("MODEL_HUMOR_PATH is missing in the environment or .env file.")
if not OLLAMA_API_URL:
    raise ValueError("OLLAMA_API_URL is missing in the environment or .env file.")

# Load Trivy logs from file
def load_trivy_logs(log_path="trivy_output.json"):
    try:
        with open(log_path, "r") as file:
            raw_data = json.load(file)
            logging.debug(f"Raw Trivy log content: {json.dumps(raw_data, indent=2)}")

            vulnerabilities = []
            if isinstance(raw_data, dict) and "Results" in raw_data:
                for result in raw_data["Results"]:
                    vulns = result.get("Vulnerabilities", [])
                    if isinstance(vulns, list):
                        vulnerabilities.extend(vulns)
            elif isinstance(raw_data, dict) and "vulnerabilities" in raw_data:
                vulnerabilities = raw_data["vulnerabilities"]

            if not isinstance(vulnerabilities, list):
                logging.error("Log format error: Logs should be a list of dictionaries.")
                return []

            logging.info(f"Extracted {len(vulnerabilities)} vulnerability entries.")
            return vulnerabilities
    except Exception as e:
        logging.error(f"Error loading logs: {e}")
        return []

# Build funny + sarcastic prompt with logs
def build_prompt_with_logs(logs):
    try:
        # Read the humor base from file (contains the SYSTEM prompt)
        with open(MODEL_HUMOR_PATH, "r") as file:
            humor_base = file.read().strip()

        logs_as_text = "\n".join([
            (
                f"{i+1}. Title: {log.get('Target', 'Unknown')}\n"
                f"Severity: {log.get('Severity', 'N/A')} | CVSS: {log.get('CVSS', {}).get('bitnami', {}).get('V3Score', 'N/A')}\n"
                f"CWE: {', '.join(log.get('CweIDs', [])) if log.get('CweIDs') else 'None'}\n"
                f"Fix it (maybe?): {log.get('References', [])[0] if log.get('References') else 'No clue, good luck'}"
            ) for i, log in enumerate(logs)
        ])

        return (
            f"{humor_base}\n\n"
            f"Here are the vulnerabilities that need your sarcastic expertise:\n\n"
            f"{logs_as_text}\n\n"
            "Now roast each one with:\n"
            "- Gordon Ramsay-level intensity\n"
            "- Stand-up comedian timing\n"
            "- DevOps intern frustration\n"
            "Bonus points for Sheldon Cooper references!"
        )
    except Exception as e:
        logging.error(f"Error building prompt with humor path: {e}")
        return ""

# Send prompt to Ollama via HTTP API
async def send_prompt_to_ollama(prompt, model="deepseek-chat", temperature=1.0):
    url = f"{OLLAMA_API_URL}/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a sarcastic security assistant"},
            {"role": "user", "content": prompt}
        ],
        "temperature": temperature
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                response.raise_for_status()
                data = await response.json()
                # Extract chat completion
                return data["choices"][0]["message"]["content"]
    except Exception as e:
        logging.error(f"Error calling Ollama API: {e}")
        return ""

# Clean messages for Discord
def clean_discord_message(text, max_length=1900):
    try:
        cleaned = text.encode("utf-8", "ignore").decode("utf-8").replace('\u0000', '')
        if len(cleaned) > max_length:
            cleaned = cleaned[:max_length] + "\n... (truncated)"
        return cleaned
    except Exception as e:
        logging.error(f"Error cleaning message: {e}")
        return ": Message could not be processed."

# Send to Discord asynchronously
async def send_discord_message_async(message):
    try:
        payload = {"content": message}
        headers = {"Content-Type": "application/json"}
        logging.debug(f"Discord Payload: {json.dumps(payload)}")
        async with aiohttp.ClientSession() as session:
            async with session.post(DISCORD_WEBHOOK_URL, json=payload, headers=headers) as response:
                if response.status == 204:
                    logging.debug("Message sent to Discord.")
                else:
                    logging.error(f"Discord responded with status: {response.status}")
    except Exception as e:
        logging.error(f"Error sending to Discord: {e}")

# Main entry point
async def main():
    try:
        logs = load_trivy_logs()
        if not logs:
            return

        prompt = build_prompt_with_logs(logs)
        if not prompt:
            logging.error("Failed to build prompt.")
            return

        response = await send_prompt_to_ollama(prompt, temperature=1.1)
        final_message = clean_discord_message(response)
        await send_discord_message_async(final_message)

    except Exception as e:
        logging.error(f"Error in main process: {e}")

if __name__ == "__main__":
    asyncio.run(main())
