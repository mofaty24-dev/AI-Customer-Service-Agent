import os
from dotenv import load_dotenv
from agents.extensions.models.litellm_model import LitellmModel
from langchain_groq import ChatGroq
from langchain_nvidia import ChatNVIDIA
from openai import AsyncOpenAI
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel

load_dotenv()
# =================================================================

## OpenAI-compatible clients for Groq, NVIDIA, and OpenRouter ##

# =================================================================


#groq_client = AsyncOpenAI(
#    api_key=os.environ["GROQ_API_KEY"],
#    base_url="https://api.groq.com/openai/v1",
#)

#nvidia_client = AsyncOpenAI(
#    api_key=os.environ["NVIDIA_API_KEY"],
 #   base_url="https://integrate.api.nvidia.com/v1",
#)
#openrouter_client = AsyncOpenAI(
#    api_key=os.environ["OPENROUTER_API_KEY"],
#    base_url="https://openrouter.ai/api/v1",
#
#)

#groq_model = OpenAIChatCompletionsModel(
#    model="openai/gpt-oss-120b",
#    openai_client=openrouter_client,
#)

#groq_light_model = OpenAIChatCompletionsModel(
#    model="qwen/qwen3.8-27b",
#    openai_client=groq_client,
#)

###  OPENROUTER / NVIDIA / GROQ MODELS  ###

# Choose one of these free models (change as needed)
# Good options for your project:
#   "openai/gpt-oss-120b"
#   "nvidia/nemotron-3-ultra-550b-a55b:free"
#   "nvidia/nemotron-3-super-120b-a12b:free"
#   "qwen/qwen3.8-27b"
#   "google/gemma-3-27b-it:free"   (if available)

#MODEL_NAME = OpenAIChatCompletionsModel(
#    model="nvidia/nemotron-3-ultra-550b-a55b:free",   # ← change this
#    openai_client=openrouter_client,
#)

#groq_model = LitellmModel(
#    model="groq/qwen/qwen3-32b",
#    api_key=os.environ["GROQ_API_KEY"],
#)



# =====================================================================

## Groq and NVIDIA models Langchain-compatible ##

# =====================================================================


groq_model = ChatGroq(
    model="qwen/qwen3.8-27b",
    api_key=os.environ["GROQ_API_KEY"],
    max_tokens=500,
)

nvidia_model = ChatNVIDIA(
    model="nvidia/nemotron-3-ultra-550b-a55b",
    api_key=os.environ["NVIDIA_API_KEY"],
    temperature=1,
    top_p=0.95,
    max_tokens=500
)

