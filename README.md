Telegram Auto Comment Bot

This is a Python-based bot that automatically monitors specified Telegram channels and posts thoughtful, context-aware comments using OpenAI's GPT-based prompts. The bot uses the Telethon library to interact with Telegram and is configured to use multiple accounts with proxy support for each session.
Features

    Automatic Commenting: Monitors channels for new posts and comments based on pre-defined tones or prompts.
    Session Management: Uses multiple Telethon sessions to handle different accounts and proxies.
    Comment Limiting and Sleep Mode: Allows setting a limit on the number of comments per account before putting it to sleep for a specified duration.
    Error Handling and Logging: Logs all activities and handles exceptions like bans, mutes, and flood waits.
    Proxy Support: Configurable proxies for each account session.
    Customizable Prompts: Allows adjusting the tone of comments via prompt-based instructions.

Prerequisites

    Python 3.8+
    Telethon library
    OpenAI API key (for generating comments using GPT-based prompts)
    Telegram account(s) with active session files
    Proxy information for each account (optional)

Installation

    Clone the repository:


git clone https://github.com/yourusername/telegram-auto-comment-bot.git
cd telegram-auto-comment-bot

Create and activate a virtual environment:


python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`

Install the required packages:


pip install -r requirements.txt

Create the necessary files:

    config.txt: For storing API keys and configuration settings.
    groups.txt: List of channels to monitor.
    proxies.txt: List of proxies (if needed).
    Session files for each account should be placed in the accounts/ folder.

Set up the config.txt file:


api_id=<YOUR_API_ID>
api_hash=<YOUR_API_HASH>
openai_api_key=<YOUR_OPENAI_API_KEY>

Prepare the groups.txt file with the channels you want to monitor (without "https://"). For example:


t.me/examplechannel1
t.me/examplechannel2

Prepare the proxies.txt file if you are using proxies:


    172.120.53.203:62097:B8SHnMHa:N1TAkpN2

Usage

    Run the bot:

    python bot.py

    The bot will:
        Log in using each account’s session file.
        Join and monitor channels specified in groups.txt.
        Respond to new posts with contextually relevant comments using OpenAI-generated responses based on the provided prompt tone.

Configuration
Setting Prompt Tone

The prompt for generating comments is defined within the script. You can customize it to change the tone and style of the comments. For example, you can use a prompt like:


"Write a supportive and friendly comment that engages with the post. Express appreciation and interest, and ask a follow-up question to continue the conversation."

Log Configuration

The bot logs all activities to logs.log and the console. You can configure the logging level and format in the script:


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

Contributing

Feel free to submit issues and pull requests to improve the bot. Make sure to follow standard coding conventions and document your code well.
License

This project is open-source and available under the MIT License.
Disclaimer

This bot interacts with Telegram’s API, so use it responsibly and ensure that it adheres to Telegram’s terms of service. Automating comments excessively or violating Telegram's guidelines may lead to bans or other consequences for your accounts.