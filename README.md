# LINE Bot with Google Gemini AI

A Flask-based LINE Bot that integrates with Google's Gemini AI to create an intelligent chatbot. This bot can handle text messages and images, maintaining conversation context and supporting multiple languages.

[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://www.heroku.com/deploy?template=https://github.com/planetarium/line-gemini-bot)

## Features

- Integration with LINE Messaging API
- Powered by Google's Gemini AI
- Multi-language support
- Image processing capabilities
- Conversation context management
- Redis-based caching (optional)
- Easy deployment to Heroku

## Prerequisites

- Python 3.8+
- LINE Developer Account
- Google AI API Key
- Heroku Account (for deployment)

## Setup

1. **LINE Channel Setup**
   - Go to the [LINE Developers site](https://developers.line.biz/en/) and create a LINE developer account.
   - Create a new Messaging API channel.
   - Go to the channel settings and get the **Channel Secret** and **Channel Access Token**.
     - **How to get the Channel Secret and Channel Access Token:**
       1. Log in to the [LINE Developers Console](https://developers.line.biz/console/).
       2. Select the Messaging API channel you created.
       3. You can find the **Channel Secret** in the "Basic settings" section of your channel settings.
       4. You can find the **Channel Access Token** in the "Messaging API" section of your channel settings. In the "Channel access token" section, click the "Issue" button to issue a token.
       5. Keep the issued tokens safe. These tokens are used by the bot to communicate with the LINE API.

2. **Google AI Setup**
   - Go to [Google AI Studio](https://aistudio.google.com/apikey) to create a Google AI project and generate an API key.

3. **Local Development**
   ```bash
   # Clone the repository
   git clone https://github.com/planetarium/line-gemini-bot.git
   cd line-gemini-bot

   # Create and activate virtual environment
   python -m venv venv
   source venv/bin/activate  # For Windows: venv\Scripts\activate

   # Install dependencies
   pip install -r requirements.txt

   # Set up environment variables
   cp .env.example .env
   ```

4. **Configure Environment Variables**
   Edit the `.env` file with your credentials:
   ```
   LINE_CHANNEL_ACCESS_TOKEN=your_line_channel_access_token
   LINE_CHANNEL_SECRET=your_line_channel_secret
   GOOGLE_API_KEY=your_google_ai_api_key
   REDIS_URL=your_redis_url (optional)
   ```

5. **Configure Application Settings**
   Copy the example configuration files:
   ```bash
   cp config.py.example config.py
   cp system_instruction.txt.example system_instruction.txt
   ```

   Customize `config.py` for your needs:
   - Adjust `MAX_FILE_SIZE` if needed
   - Modify `FIXED_MESSAGES` for different languages
   - Add or remove language support

   Customize `system_instruction.txt` to define your AI assistant's behavior and personality.

6. **Running the Server Locally**
   ```bash
   python app.py
   ```
   This will start the Flask development server. You can access the bot locally, typically at `http://localhost:5000`.

## Deployment

### Heroku Deployment

1. Click the "Deploy to Heroku" button above
2. Fill in the required environment variables
3. Deploy the application
4. Set the webhook URL in your LINE Channel settings to:
   `https://your-app-name.herokuapp.com/callback`

### Manual Deployment

1. Create a new Heroku app
   ```bash
   heroku create your-app-name
   ```

2. Set environment variables
   ```bash
   heroku config:set LINE_CHANNEL_ACCESS_TOKEN=your_token
   heroku config:set LINE_CHANNEL_SECRET=your_secret
   heroku config:set GOOGLE_API_KEY=your_key
   ```

3. Deploy the application
   ```bash
   git push heroku main
   ```

## Customization

### System Instructions
Create a `system_instruction.txt` file to customize the AI's behavior: