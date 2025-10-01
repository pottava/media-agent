import os
import time
import mimetypes

from google import genai
from google.adk.tools import ToolContext
from google.api_core import exceptions


# @see https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/veo-video-generation#model-versions
veo_model = "veo-3.0-generate-preview"

# @see https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/imagen-api#model-versions
imagen_model = "imagen-4.0-generate-001"

project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
location = os.getenv("GOOGLE_CLOUD_LOCATION")
bucket = os.getenv("GENMEDIA_BUCKET")


# https://github.com/GoogleCloudPlatform/vertex-ai-creative-studio/blob/main/experiments/mcp-genmedia/mcp-genmedia-go/mcp-veo-go/README.md
def veo_i2v(
    prompt: str,
    image_uri: str,
    bucket: str,
    num_videos: int = 1,
    aspect_ratio: str = "16:9",
    duration: int = 6,
    tool_context: ToolContext = None,
) -> dict:
    """
    Generate a video from an input image (and optional prompt) using Veo.

    Args:
        prompt (string, required): Text prompt for video generation.
        image_uri (string, required): GCS URI of the input image for video generation (e.g., "gs://your-bucket/input-image.png").
        bucket (string, required): Google Cloud Storage bucket for output. Same logic as veo_t2v.
        num_videos (number, optional): Number of videos. Default: 1. Min: 1, Max: 4.
        aspect_ratio (string, optional): Aspect ratio. Default: "16:9".
        duration (number, optional): Duration in seconds. Default: 6. Min: 4, Max: 8
    """
    mime_type, _ = mimetypes.guess_type(image_uri)
    if not mime_type in ["image/jpeg", "image/png"]:
        return {"status": f"エラー: '{image_uri}' は未対応の形式です ({mime_type})"}

    if not bucket.startswith("gs://"):
        bucket = f"gs://{bucket}"
    if not bucket.endswith("/"):
        bucket = f"{bucket}/"

    config = genai.types.GenerateVideosConfigDict(
        generate_audio=True,
        aspect_ratio=aspect_ratio,
        duration_seconds=duration,
        number_of_videos=num_videos,
        output_gcs_uri=bucket,
    )
    client = genai.Client()
    try:
        operation = client.models.generate_videos(
            model=veo_model,
            prompt=prompt,
            image=genai.types.Image(gcs_uri=image_uri, mime_type=mime_type),
            config=config,
        )
        while not operation.done:
            operation = client.operations.get(operation)
            time.sleep(3)

        if operation.error:
            return {"status": f"エラーが発生しました {operation.error}"}
        else:
            video = operation.response.generated_videos[0].video
            return {
                "status": "success",
                "uri": video.uri,
            }
    except exceptions.GoogleAPICallError as e:
        return {"status": f"API 呼び出しでエラーが発生しました: {e}"}
    except Exception as e:
        return {"status": f"エラーが発生しました: {e}"}


def imagen_t2i(
    prompt: str,
    bucket: str,
    num_images: int = 1,
    aspect_ratio: str = "1:1",
    tool_context: ToolContext = None,
) -> dict:
    """
    Generates an image based on a text prompt using Google's Imagen models.
    The image can be stored in a Google Cloud Storage bucket.

    Args:
        prompt (string, required): Prompt for text to image generation.
        bucket (string, required): Google Cloud Storage bucket for output. Same logic as veo_t2v.
        num_images (number, optional): Number of images. Default: 1. Min: 1, Max: 4.
        aspect_ratio (string, optional): Aspect ratio. Default: "1:1".
    """
    if not bucket.startswith("gs://"):
        bucket = f"gs://{bucket}"
    if not bucket.endswith("/"):
        bucket = f"{bucket}/"

    client = genai.Client()
    try:
        response = client.models.generate_images(
            model=imagen_model,
            prompt=prompt,
            config=genai.types.GenerateImagesConfig(
                number_of_images=num_images,
                aspect_ratio=aspect_ratio,
                output_gcs_uri=bucket,
            ),
        )
        image = response.generated_images[0]
        return {
            "status": "success",
            "uri": image.image.gcs_uri,
        }
    except exceptions.GoogleAPICallError as e:
        return {"status": f"API 呼び出しでエラーが発生しました: {e}"}
    except Exception as e:
        return {"status": f"エラーが発生しました: {e}"}
