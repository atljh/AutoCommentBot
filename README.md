![Working](https://media.giphy.com/media/20NLMBm0BkUOwNljwv/giphy.gif)

## 🧐 About <a name = "about"></a>

This is a Python-based bot designed to automatically monitor specified Telegram channels and post thoughtful, context-aware comments using OpenAI's GPT-based prompts. The bot utilizes the Telethon library to interact with Telegram and can be configured to use multiple accounts with proxy support.

![Build Status](https://img.shields.io/badge/build-passing-brightgreen) ![License](https://img.shields.io/badge/license-MIT-blue) ![Documentation](https://img.shields.io/badge/documentation-ready-yellow)

Features

- **Automatic Commenting**: Monitors channels for new posts and adds comments based on pre-defined tones or prompts.
- **Session Management**: Utilizes multiple Telethon sessions to manage different accounts and proxies.
- **Comment Limiting and Sleep Mode**: Set limits on the number of comments per account and trigger a sleep period to avoid detection.
- **Error Handling and Logging**: Logs all activities and gracefully handles errors like bans, mutes, and flood waits.
- **Proxy Support**: Configurable proxies for each account session.
- **Customizable Prompts**: Easily adjust the tone and style of comments using prompt-based instructions.

Prerequisites

- Python 3.8+
- Telethon library
- OpenAI API key (for generating comments using GPT-based prompts)
- Telegram account(s) with active session files
- Proxy information for each account (optional)

## 🚀 Installation <a name = "getting_started"></a>


1. Clone the repository:
   ```bash
   git clone https://github.com/atljh/AutoCommentBot.git
   cd AutoCommentBot
   ```
## Option A: Run the Script Directly
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```

3. Install the required packages:
   ```bash
   pip install poetry
   poetry install
   ```

4. Create the necessary files:
   - `config.yaml`: For storing API keys and configuration settings.
   - `groups.txt`: List of channels to monitor.
   - Session files for each account should be placed in the `accounts/` folder.

5. Set up the `config.yaml` file:
   ```txt
   openai_api_key: <YOUR_OPENAI_API_KEY>
   ```

6. Prepare the `groups.txt` file: List the channels you want to monitor (without https://). Example:
   ```txt
   t.me/examplechannel1
   t.me/examplechannel2
   ```

## Option B: Compile the Script into an Executable
 
   ```bash
   scripts/compile.cmd
   ```

## 🎈 Usage <a name = "usage"></a>

```python
python main.py
```
of
```bash
dist/main.exe
```

Bot Actions:
- Logs in using each account’s session file.
- Joins and monitors channels specified in `groups.txt`.
- Responds to new posts with contextually relevant comments using OpenAI-generated responses based on the provided prompt tone.

Configuration

### Setting Prompt Tone

The prompt for generating comments is defined within the script. You can customize it to change the tone and style of the comments. For example:
```txt
"Write a supportive and friendly comment that engages with the post. Express appreciation and interest, and ask a follow-up question to continue the conversation."
```


Contributing

Feel free to submit issues and pull requests to improve the bot. Make sure to follow standard coding conventions and document your code well.

Roadmap

- [ ] Add support for more Telegram APIs.
- [ ] Improve error handling capabilities.
- [ ] Implement a GUI for easier configuration.
- [ ] Add support for multiple languages in comments.

FAQ

**Q: What happens if I get banned?**  
A: The bot will log the error, and you may need to adjust your commenting strategy to avoid detection.

**Q: Can I run multiple instances of the bot?**  
A: Yes, but ensure each instance uses a different set of accounts and configuration files.

License

This project is open-source and available under the MIT License.

Disclaimer

This bot interacts with Telegram’s API, so use it responsibly and ensure that it adheres to Telegram’s terms of service. Automating comments excessively or violating Telegram's guidelines may lead to bans or other consequences for your accounts.