import os

import google.auth
from google.adk.agents import LlmAgent

from .tools import genmedia_tools
from .callbacks import before_model, after_tool
from . import prompt


_, project_id = google.auth.default()
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project_id)
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")

root_agent = LlmAgent(
    name="media_agent",
    model="gemini-2.5-flash",
    description="メディア生成エージェント",
    instruction=prompt.PROMPT.format(
        reference_image_uri=os.getenv("REFERENCE_IMAGE_URI")
    ),
    tools=genmedia_tools,
    before_model_callback=before_model,
    after_tool_callback=after_tool,
)
