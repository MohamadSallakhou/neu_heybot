import logging
import json
import asyncio
import aiohttp
import os
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Variables from the .env file
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
MODEL_HUMOR_PATH = os.getenv('MODEL_HUMOR_PATH1')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
PROJECT_CONTEXT_INFO = os.getenv("PROJECT_CONTEXT_INFO", "Keine weiteren Informationen")

if not DISCORD_WEBHOOK_URL:
    raise ValueError("DISCORD_WEBHOOK_URL is missing in the .env file.")
if not MODEL_HUMOR_PATH:
    raise ValueError("MODEL_HUMOR_PATH1 is missing in the .env file.")
if not DEEPSEEK_API_KEY:
    raise ValueError("DEEPSEEK_API_KEY is missing in the .env file.")

# Initialize DeepSeek client
client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

# Severity ranking for sorting
SEVERITY_ORDER = {
    "CRITICAL": 0,
    "HIGH": 1,
    "MEDIUM": 2,
    "LOW": 3,
    "UNKNOWN": 4
}


def generate_joke(vulnerability, style="neutral"):
    """Generate a joke based on the vulnerability and style."""
    joke = ""
    if style == "neutral":
        joke = f"This vulnerability in {vulnerability['Package']} is like a ticking time bomb. Better patch it soon!"
    elif style == "sarkastisch":
        joke = f"Oh great, another flaw in {vulnerability['Package']}. Because we really needed more problems!"
    elif style == "freundlich":
        joke = f"Looks like {vulnerability['Package']} needs a little TLC – time to fix that bug! 😊"
    return joke


async def get_mcp_context():
    """Fetch MCP context (style, mode, language) from the MCP server"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:7861/mcp/context") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logging.error("Error fetching MCP context")
                    return {"style": "neutral", "mode": "default", "language": "de"}
    except Exception as e:
        logging.error(f"Error getting MCP context: {e}")
        return {"style": "neutral", "mode": "default", "language": "de"}


def load_humor_template():
    """Load the humor template from the humor file."""
    try:
        with open(MODEL_HUMOR_PATH, 'r') as file:
            return file.read().strip()
    except Exception as e:
        logging.error(f"Error loading humor template: {e}")
        return """You are a AI specializing in roasting vulnerabilities with  fun jokes. The style from the Joke base on humor_style and the mode
        Rules:
        - Include scientific references where appropriate.
        - The style from the Joke base on humor_style and the mode
        - Keep jokes 1-2 sentences.
        - Use emojis that match the context of the joke.
        - your are {mode} and {humor_style} and you do jokes like that too

        Respond ONLY with the joke - no explanations!"
        """


def sort_vulnerabilities(vulnerabilities):
    """Sort vulnerabilities by severity (CRITICAL > HIGH > MEDIUM > LOW)"""
    return sorted(
        vulnerabilities,
        key=lambda x: SEVERITY_ORDER.get(x.get('Severity', 'UNKNOWN'), 100)
    )


async def generate_security_report(vulnerabilities, humor_template, context):
    """Generate a full security report with joke, table, and action items using DeepSeek"""
    try:
        if not vulnerabilities:
            return "No vulnerabilities found! Your code is as flawless as a perfect algorithm."

        # Sort vulnerabilities by severity before processing
        sorted_vulns = sort_vulnerabilities(vulnerabilities)

        # Hol den aktuellen Humor-Stil und die Sprache aus dem Kontext
        humor_style = context.get("style", "neutral")
        language = context.get("language", "de")
        mode = context.get("mode", "juristisch")

        # Anpassung des Humor-Stils im Template
        if humor_style == "sarkastisch":
            humor_template += "\n(Verwende einen sarkastischen Ton in den Witzen!)"
        elif humor_style == "freundlich":
            humor_template += "\n(Verwende einen freundlichen Ton in den Witzen!)"

        # Sprachoptionen im Prompt einfügen
        if language == "de":
            language_note = "Verwende deutsche Sprache für alle Antworten."
        elif language == "en":
            language_note = "Use English for all responses."
        else:
            language_note = "Use the appropriate language based on the context."

        additional_info = context.get("additional_info", "Keine weiteren Informationen zum Projektkontext.")

        prompt = f"""
        {humor_template}
        Humor Style: {humor_style}
        {language_note}
        Language: {language}
        mode: {mode}

        Analyze the vulnerabilities below and generate:
        1. A joke about the vulnerability (e.g., comparison to everyday situations, science references, etc.)
        2. A markdown table with columns: Package, Severity, CVE, Fixed Version, How to Fix.
        3. Key notes for critical/high vulnerabilities.
        4. Actionable remediation steps.
        5. your are {mode} and {humor_style} and you do jokes like that too

        Vulnerabilities (first 5 by severity):
        {json.dumps(sorted_vulns[:5], indent=2)}

        Additional context:
        {context.get("additional_info", "No additional context.")}

        **Vulnerabilities**:
        ```
        | Package  | Severity | CVE              | Fixed Version | How to Fix                      |
        |----------|----------|------------------|---------------|---------------------------------|
        | libaom3  | CRITICAL | CVE-2023-6879    | Not specified | Upgrade via Debian security updates |
        |          | HIGH     | CVE-2023-39616   | Will not fix  | Monitor for future patches      |
        ```

        **Key Notes**:
        - libaom3: Heap overflow (CRITICAL) and memory read issue (HIGH).

        **Action**:
        - Patch CRITICAL issues immediately with `apt upgrade`.
        - Restrict untrusted inputs for HIGH-severity unfixable issues.
        """

        # Anfrage an DeepSeek (angepasst für Humor und Sprache)
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7  # Balance von Kreativität und Struktur
        )

        report = response.choices[0].message.content

        # # Adjust according to humor style
        # if humor_style == "sarkastisch":
        #     report += " Wow, that's a real shocker... not! 😒"
        # elif humor_style == "freundlich":
        #     report += " Don't worry, we can fix this quickly! 😊"
        # else:
        #     report += " No big deal, we'll get it sorted out! 😅"

        # Adjust according to mode
        if context["mode"] == "error":
            report += " This issue needs urgent attention. Please patch it ASAP!"
        elif context["mode"] == "default":
            report += " It's a manageable issue, but better safe than sorry."

        return report

    except Exception as e:
        logging.error(f"Error generating report: {e}")
        return "This vulnerability analysis failed harder than my last coding project!"


def load_trivy_logs(log_path="trivy_output.json"):
    try:
        with open(log_path, "r") as file:
            raw_data = json.load(file)
            vulnerabilities = []
            if isinstance(raw_data, dict):
                if "Results" in raw_data:
                    for result in raw_data["Results"]:
                        if "Vulnerabilities" in result:
                            vulnerabilities.extend(result["Vulnerabilities"])
                elif "vulnerabilities" in raw_data:
                    vulnerabilities = raw_data["vulnerabilities"]
            return vulnerabilities or []
    except Exception as e:
        logging.error(f"Error loading logs: {e}")
        return []


async def send_discord_message_async(message):
    try:
        payload = {"content": message}
        headers = {"Content-Type": "application/json"}
        async with aiohttp.ClientSession() as session:
            async with session.post(DISCORD_WEBHOOK_URL, json=payload, headers=headers) as response:
                if response.status != 204:
                    logging.error(f"Discord responded with status: {response.status}")
    except Exception as e:
        logging.error(f"Error sending to Discord: {e}")


async def main():
    try:
        vulnerabilities = load_trivy_logs()
        humor_template = load_humor_template()

        # Hol den aktuellen Kontext vom MCP-Server
        context = await get_mcp_context()
        print("Context:", context)
        context["additional_info"] = PROJECT_CONTEXT_INFO  # 👈 fügt .env-Info ein
        # Generiere den Bericht mit Kontext
        report = await generate_security_report(vulnerabilities, humor_template, context)
        await send_discord_message_async(report)
        logging.info("Full security report sent to Discord")

    except Exception as e:
        logging.error(f"Error in main process: {e}")


if __name__ == "__main__":
    asyncio.run(main())
