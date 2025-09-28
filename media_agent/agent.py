import os
import sys

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    SseConnectionParams,
    StdioConnectionParams,
    StdioServerParameters,
)

from .callbacks import before_model, after_tool


if "GENMEDIA_BUCKET" not in os.environ:
    print("エラー: 環境変数 GENMEDIA_BUCKET が設定されていません。")
    sys.exit(1)

if "REFERENCE_IMAGE_URI" not in os.environ:
    print("エラー: 環境変数 REFERENCE_IMAGE_URI が設定されていません。")
    sys.exit(1)


project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
location = os.getenv("GOOGLE_CLOUD_LOCATION")
bucket = os.getenv("GENMEDIA_BUCKET")
image_uri = os.getenv("REFERENCE_IMAGE_URI")


# MCP: Veo
# veo_model = "veo-3.0-fast-generate-001"
veo_model = "veo-3.0-fast-generate-preview"
veo = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="mcp-veo-go",
            env=dict(os.environ, PROJECT_ID=project_id, LOCATION=location),
        ),
        timeout=120,
    ),
    tool_filter=["veo_i2v"],
)
if veo_endpoint := os.getenv("MCP_VEO_ENDPOINT"):
    veo._connection_params = SseConnectionParams(
        headers={"Authorization": f"Bearer {os.getenv("MCP_VEO_AUTH_TOKEN")}"},
        url=veo_endpoint,
    )

# MCP: Imagen
imagen_model = "imagen-4.0-fast-generate-001"
imagen = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="mcp-imagen-go",
            env=dict(os.environ, PROJECT_ID=project_id, LOCATION=location),
        ),
        timeout=60,
    ),
    tool_filter=["imagen_t2i"],
)
if imagen_endpoint := os.getenv("MCP_IMAGEN_ENDPOINT"):
    imagen._connection_params = SseConnectionParams(
        headers={"Authorization": f"Bearer {os.getenv("MCP_IMAGEN_AUTH_TOKEN")}"},
        url=imagen_endpoint,
    )

# Media agent
root_agent = LlmAgent(
    name="media_agent",
    model="gemini-2.5-flash",
    description="メディア生成エージェント",
    instruction=f"""
        あなたは自社メディアコンテンツの作成を支援するアシスタントです。

        1. もしユーザからの依頼が動画の生成なのか画像の生成なのかはっきりしない場合は確認してください。
        2. 依頼内容が動画や画像の生成以外の場合は対応できない旨を返信して作業を完了です。
        3. 依頼が動画像の生成なら、まずはいったん作業に着手する旨を応答した上で
        4. 適切なツールに英語で指示しつつ、ユーザーから頼まれた画像や動画を生成してください。
        5. ユーザへの応答は日本語で、生成した画像へのアクセス URL を含めてください。
           URL には X-Goog-Algorithm といったクエリパラメタが付属しているはずですが
           これは **絶対に一切省略せず、一文字たりとも変更せずに** 応答に含めてください。

        veo_i2v を使う時は、どうしても必要でない限り imagen_t2i で作った画像ではなく
        **必ず** image_uri パラメタに {image_uri} を、 bucket パラメタには {bucket} を
        そして model パラメタには {veo_model} を指定してください。
        imagen_t2i を使う時は gcs_bucket_uri パラメタに {bucket} を
        そして model パラメタには {imagen_model} を指定してください。
    """,
    tools=[veo, imagen],
    before_model_callback=before_model,
    after_tool_callback=after_tool,
)
