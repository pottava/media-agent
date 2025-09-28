import copy
import os
import re
import datetime
from urllib.parse import urlparse
from typing import Optional, Dict, Any

import google.auth
from google.auth import impersonated_credentials
from google.cloud import storage
from google.api_core import exceptions
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmResponse, LlmRequest
from google.adk.tools.tool_context import ToolContext
from google.adk.tools.base_tool import BaseTool


instruction = os.getenv("IMAGEN_INSTRUCTION")
bucket_name = os.getenv("GENMEDIA_BUCKET")
sa_email = os.getenv("GOOGLE_CLOUD_SA_EMAIL")


def before_model(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[LlmResponse]:
    print(f"[Before Model callback] {callback_context.agent_name}")
    if (
        llm_request.contents
        and llm_request.contents[-1].role == "user"
        and llm_request.contents[-1].parts
        and llm_request.contents[-1].parts[0].text
    ):
        llm_request.contents[-1].parts[0].text = (
            instruction + "\n\n" + llm_request.contents[-1].parts[0].text
        )
    return None


def after_tool(
    tool: BaseTool, args: Dict[str, Any], tool_context: ToolContext, tool_response: Dict
) -> Optional[Dict]:
    print(f"[After Tool callback] Tool '{tool.name}' in '{tool_context.agent_name}'")
    if (
        tool_response
        and tool_response.content
        and isinstance(tool_response.content, list)
        and len(tool_response.content) > 0
    ):
        text = tool_response.content[0].text
        modified = copy.deepcopy(tool_response)
        modified.content[0].text = replace_gcs_paths_with_signed_urls(text)
        print(f"[After Tool callback] Modified response: {modified}")
        return modified

    return None


# GCS に作られたファイルに署名 URL を割り当てる
# 署名にはサービスアカウントの鍵が必要になるため、ローカル環境では成り代わりが必要
credentials, _ = google.auth.default()
if sa_email:
    credentials = impersonated_credentials.Credentials(
        source_credentials=credentials,
        target_principal=sa_email,
        target_scopes=["https://www.googleapis.com/auth/devstorage.read_write"],
    )
try:
    storage_client = storage.Client(credentials=credentials)
except Exception as e:
    storage_client = None
    print(f"Error initializing GCS client: {e}")


def parse_gcs_path(path: str, bucket_name: str) -> tuple[str | None, str | None]:
    """
    gs://bucket/path/to/obj や https://.../bucket/path/to/obj といった
    文字列を (bucket_name, object_name) に分割する
    """
    initial_object_name = None
    parsed_bucket_name = None

    if path.startswith(f"gs://{bucket_name}/"):
        initial_object_name = path.replace(f"gs://{bucket_name}/", "")
        parsed_bucket_name = bucket_name

    elif path.startswith("https://"):
        try:
            path = urlparse(path).path

            bucket_search_key = f"/{bucket_name}/"
            bucket_start_index = path.find(bucket_search_key)

            if bucket_start_index != -1:
                object_start_index = bucket_start_index + len(bucket_search_key)
                initial_object_name = path[object_start_index:]
                parsed_bucket_name = bucket_name
        except (ValueError, IndexError):
            pass

    if initial_object_name:
        pattern = re.compile(r"(.*?\.jpeg|.*?\.png|.*?\.mp4)")
        match = pattern.search(initial_object_name)
        if match:
            valid_object_name = match.group(1)
            return parsed_bucket_name, valid_object_name

    return None, None


def generate_signed_url_for_path(gcs_path: str, bucket_name: str) -> str | None:
    """
    GCS パス文字列から署名付き URL を生成
    """
    if not storage_client:
        print("GCS client is not initialized.")
        return None

    bucket_name, object_name = parse_gcs_path(gcs_path, bucket_name)
    if not bucket_name or not object_name:
        print(f"Could not parse GCS path: {gcs_path}")
        return None

    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(object_name)

        signed_url = blob.generate_signed_url(
            method="GET",
            version="v4",
            service_account_email=credentials.service_account_email,
            expiration=datetime.timedelta(minutes=5),
        )
        return signed_url

    except exceptions.NotFound:
        print(f"Object not found: {gcs_path}")
        return None
    except Exception as e:
        print(f"Failed to generate signed URL for {gcs_path}: {e}")
        return None


def replace_gcs_paths_with_signed_urls(text: str) -> str:
    """
    文字列内の GCS パスを検出し、署名付き URL に置換
    """
    url_pattern = re.compile(r"(gs://[^ \n\r\t]+|https://[^ \n\r\t]+)")

    def replacer(match):
        original_path = match.group(0)
        signed_url = generate_signed_url_for_path(original_path, bucket_name)
        return signed_url if signed_url else original_path

    return url_pattern.sub(replacer, text)
