from langchain_mistralai.chat_models import ChatMistralAI
from langchain_google_genai import ChatGoogleGenerativeAI

from dotenv import load_dotenv

load_dotenv()

ministral_medium_chat = ChatMistralAI(
    model="mistral-medium-3-5",
    max_retries=3,
)

gemini_flash = ChatGoogleGenerativeAI(
    model="gemini-3.7-flash",
    max_retries=3,
)
