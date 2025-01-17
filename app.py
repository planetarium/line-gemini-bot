import os
import time
import json
import google.generativeai as genai
import requests

from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    FlexMessage,
    FlexContainer,
    MessagingApiBlob,
    UserProfileResponse
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    ImageMessageContent,
    VideoMessageContent,
    AudioMessageContent,
    FollowEvent
)
from config import (
    LINE_CHANNEL_ACCESS_TOKEN,
    LINE_CHANNEL_SECRET,
    GOOGLE_API_KEY,
    REDIS_URL,
    FIXED_MESSAGES,
    MAX_FILE_SIZE,
    MODEL_NAME
)

# Initialize Redis cache if available
try:
    redis_url = REDIS_URL
    if redis_url:
        import redis
        cache = redis.from_url(redis_url, ssl_cert_reqs=None)
    else:
        cache = None
except ImportError:
    cache = None

def load_system_instruction(filepath):
    """Load system instruction from file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            system_instruction = f.read()
        return system_instruction
    except FileNotFoundError:
        print(f"Error: System instruction file not found at {filepath}")
        return ""

# System instruction configuration
SYSTEM_INSTRUCTION_FILE = "system_instruction.txt"
system_instruction = load_system_instruction(SYSTEM_INSTRUCTION_FILE)

# Initialize LINE and Gemini APIs
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel(
    model_name=MODEL_NAME,
    system_instruction=system_instruction,
)

app = Flask(__name__)

# Webhook handler
@app.route("/callback", methods=["POST"])
def callback():
    """Handle LINE webhook callback"""
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    print("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError as e:
        print(f"Invalid signature: {e}")
        abort(400)

    return "OK"

# Event handlers
@handler.add(FollowEvent)
def handle_follow(event):
    """Handle follow/unblock events"""
    user_id = event.source.user_id
    is_unblocked = event.follow.is_unblocked

    try:
        # Get user profile information
        profile = get_user_profile(user_id)
        user_language = profile.language or 'en'
        user_name = profile.display_name or 'User'
    except Exception as e:
        print(f"Error getting user profile: {e}")
        user_language = 'en'
        user_name = 'User'

    # Select message based on user's language and event type
    if user_language in FIXED_MESSAGES:
        event_type = 'unblock' if is_unblocked else 'follow'
        send_line_reply(
            event.reply_token,
            FIXED_MESSAGES[user_language][event_type].format(user_name=user_name)
        )
    else:
        # Generate welcome message using Gemini
        if is_unblocked:
            instruction = (
                f"Generate a personalized welcome back message for user {user_name}. "
                f"If possible, respond in their language (detected: {user_language})."
            )
        else:
            instruction = (
                f"Generate a personalized welcome message for new user {user_name}. "
                f"If possible, respond in their language (detected: {user_language})."
            )

        response_text = query_gemini(user_id, instruction)
        send_line_reply(event.reply_token, response_text)

# 메시지 이벤트 처리 (텍스트 메시지)
@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    """Handle text message events"""
    user_id = event.source.user_id
    user_message = event.message.text

    response_text = query_gemini(user_id, user_message)
    send_line_reply(event.reply_token, response_text)

# 메시지 이벤트 처리 (이미지 메시지)
@handler.add(MessageEvent, message=(ImageMessageContent,
                                  VideoMessageContent,
                                  AudioMessageContent))
def handle_content_message(event):
    """Handle media content message events"""
    user_id = event.source.user_id
    try:
        profile = get_user_profile(user_id)
        user_language = profile.language or 'en'
        user_name = profile.display_name or 'User'
    except Exception as e:
        print(f"Error getting user profile: {e}")
        user_language = 'en'
        user_name = 'User'
    
    if isinstance(event.message, ImageMessageContent):
        ext = 'jpg'
    elif isinstance(event.message, VideoMessageContent):
        ext = 'mp4'
    elif isinstance(event.message, AudioMessageContent):
        ext = 'm4a'
    else:
        return

    with ApiClient(configuration) as api_client:
        line_bot_blob_api = MessagingApiBlob(api_client)
        message_dict = event.message.to_dict()
        
        # Handle external or uploaded content
        if message_dict['contentProvider']['type'] == 'external':
            image_url = message_dict['contentProvider']['originalContentUrl']
            response = requests.get(image_url, stream=True)
            image_data = response.content
        else:
            message_content = line_bot_blob_api.get_message_content(message_id=event.message.id)
            image_data = message_content

        if len(image_data) > MAX_FILE_SIZE:
            response_text = "Sorry, the file is too large to process."
        elif ext == 'jpg':
            prompt = (
                f"User: {user_name}, Language: {user_language}. "
                f"Please analyze this image and provide relevant information. "
                f"If possible, respond in the user's language."
            )
            response_text = query_gemini(user_id, user_message=prompt, image=image_data)
        else:
            response_text = "I can only process image files at the moment."

    send_line_reply(event.reply_token, response_text)

# Gemini에 질의하고 응답을 받아오는 함수
def query_gemini(user_id, user_message=None, image=None):
    """Query Gemini AI with user message and/or image"""
    try:
        profile = get_user_profile(user_id)
        user_language = profile.language or 'en'
        user_name = profile.display_name or 'User'
    except Exception as e:
        print(f"Error getting user profile: {e}")
        user_language = 'en'
        user_name = 'User'

    # Load conversation history
    user_context = load_user_context(user_id)

    # Build current context with user profile
    current_context = [
        {
            "role": "user",
            "parts": [
                f"User: {user_name}, Language: {user_language}. "
                "Please respond in the user's language if possible."
            ]
        }
    ]

    # Add conversation history
    current_context.extend([
        {"role": msg["role"], "parts": msg["parts"]} 
        for msg in user_context
    ])

    # Add current message
    if user_message and not image:
        user_context.append({
            "role": "user",
            "parts": [user_message],
            "timestamp": time.time()
        })
        current_context.append({"role": "user", "parts": [user_message]})
    elif image:
        current_context.append({
            "role": "user",
            "parts": [
                {"inline_data": {"mime_type": "image/jpeg", "data": image}},
                user_message
            ]
        })

    try:
        # Call Gemini API
        response = model.generate_content(current_context)

        # Add response to conversation history
        user_context.append({
            "role": "model",
            "parts": [response.text],
            "timestamp": time.time()
        })

        # Save updated conversation history
        save_user_context(user_id, user_context)

        return response.text

    except Exception as e:
        print(f"Error during Gemini query: {e}")
        return "Sorry, I couldn't understand your message."

def load_user_context(user_id):
    """Load user's conversation history"""
    if cache:
        user_context = cache.get(user_id)
        if user_context:
            return json.loads(user_context.decode('utf-8'))
        return []
    
    if not hasattr(load_user_context, "local_cache"):
        load_user_context.local_cache = {}
    return load_user_context.local_cache.get(user_id, [])

def filter_recent_messages(user_context):
    """Filter messages from the last 24 hours"""
    one_day_ago = time.time() - 24 * 60 * 60
    return [
        message for message in user_context 
        if message["timestamp"] > one_day_ago
    ]

def save_user_context(user_id, user_context):
    """Save user's conversation history"""
    # Keep only recent messages and limit to last 20 messages
    user_context = filter_recent_messages(user_context)[-20:]
    
    if cache:
        cache.set(
            user_id,
            json.dumps(user_context),
            ex=60*60*24  # Expire after 24 hours
        )
    else:
        load_user_context.local_cache[user_id] = user_context

# LINE 응답 메시지 생성 및 전송
def send_line_reply(reply_token, response_text):
    """Send reply message to LINE
    
    Handles both text and Flex messages, with support for message segmentation
    and markdown-style formatting.
    """
    messages = []
    segments = response_text.split("```")

    for segment in segments:
        if segment.strip().startswith("json"):
            # Handle Flex message JSON
            segment = segment.strip()[4:]
            try:
                messages.append(
                    FlexMessage(
                        alt_text="Interactive Message",
                        contents=FlexContainer.from_json(segment)
                    )
                )
            except json.JSONDecodeError:
                # Fallback to text if JSON parsing fails
                messages.append(
                    TextMessage(text=segment.strip().replace("**", ""))
                )
        else:
            # Handle text messages with paragraph splitting
            if segment.strip():
                paragraphs = segment.strip().split("\n\n")
                
                # Check message limit (LINE allows max 5 messages per reply)
                if len(messages) + len(paragraphs) > 5:
                    messages.append(
                        TextMessage(text=segment.strip().replace("**", ""))
                    )
                else:
                    for paragraph in paragraphs:
                        messages.append(
                            TextMessage(
                                text=paragraph.replace("**", "").strip()
                            )
                        )

    # Send messages through LINE API
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=messages
            )
        )

def get_user_profile(user_id: str) -> UserProfileResponse:
    """Get LINE user profile"""
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        return line_bot_api.get_profile(user_id=user_id)

if __name__ == "__main__":
    """Run the Flask application"""
    port = int(os.environ.get("PORT", 5000))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False  # Disable debug mode in production
    )