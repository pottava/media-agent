# メディア エージェント

さまざまなメディアを依頼された内容に基づいて生成する AI エージェントです。

Google の [Agent Development Kit (ADK)](https://google.github.io/adk-docs/) をベースに  
さまざまな AI モデルを活用してメディアを生成します。

## ローカル起動

Google Cloud への認証を通し

```bash
gcloud auth login
gcloud auth application-default login
```

プロジェクト ID とリージョンを設定しましょう。

```bash
gcloud config set project "<your-project-id>"
export GOOGLE_CLOUD_PROJECT="$( gcloud config get-value project )"
export GOOGLE_CLOUD_LOCATION="us-central1"
```

メディアを保存する GCS バケットを作り

```bash
datetime=$( date +"%Y%m%d%H%M%S" )
export GENMEDIA_BUCKET="media-agent-handson-${datetime}"
gcloud storage buckets create "gs://${GENMEDIA_BUCKET}" --location "${GOOGLE_CLOUD_LOCATION}" --uniform-bucket-level-access
```

動画の参考にしたい画像をアップロードします。

```bash
wget -qO your-image.jpg https://example.com/your-image.jpg
gcloud storage cp your-image.jpg gs://$GENMEDIA_BUCKET/
export REFERENCE_IMAGE_URI="gs://${GENMEDIA_BUCKET}/your-image.jpg"
```

エージェントが作成する動画・画像に対する[署名付き URL](https://cloud.google.com/storage/docs/access-control/signed-urls?hl=ja) を発行する[サービス アカウント](https://cloud.google.com/iam/docs/service-account-overview?hl=ja)を作ります。

```bash
export GOOGLE_CLOUD_SA_EMAIL="media-agent-${datetime}@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com"
gcloud iam service-accounts create "media-agent-${datetime}" --display-name "Media-agent Handson SA"
gcloud projects add-iam-policy-binding "${GOOGLE_CLOUD_PROJECT}" \
    --member "serviceAccount:${GOOGLE_CLOUD_SA_EMAIL}" \
    --role "roles/storage.admin"
gcloud projects add-iam-policy-binding "${GOOGLE_CLOUD_PROJECT}" \
    --member "serviceAccount:${GOOGLE_CLOUD_SA_EMAIL}" \
    --role "roles/iam.serviceAccountTokenCreator"
```

あなた自身にも `Service Account Token Creator` 権限があることを確認します。

```bash
export YOUR_GOOGLE_ACCOUNT_EMAIL=
gcloud projects add-iam-policy-binding "${GOOGLE_CLOUD_PROJECT}" \
    --member "user:${YOUR_GOOGLE_ACCOUNT_EMAIL}" \
    --role="roles/iam.serviceAccountTokenCreator"
```

このリポジトリを git clone して、環境で参照する `.env` ファイルを作成します。

```bash
git clone https://github.com/pottava/media-agent.git
cd media-agent
cat << EOF > .devcontainer/.env
# Project
PROJECT_NAME="media-agent"

# Google Cloud resources
GOOGLE_GENAI_USE_VERTEXAI=1
GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT}
GOOGLE_CLOUD_LOCATION=${GOOGLE_CLOUD_LOCATION}
GOOGLE_CLOUD_SA_EMAIL=${GOOGLE_CLOUD_SA_EMAIL}

# Genmedia
GENMEDIA_BUCKET=${GENMEDIA_BUCKET}
REFERENCE_IMAGE_URI=${REFERENCE_IMAGE_URI}
EOF
```

VS Code の Devcontainer で開くか、  
ローカルに Python の仮想環境を作って依存を解決してください。

```bash
uv venv
uv sync --directory .devcontainer
```

VS Code でない場合、MCP Servers for Genmedia や mcptools をインストールしてください。

```bash
git clone https://github.com/GoogleCloudPlatform/vertex-ai-creative-studio.git \
cd vertex-ai-creative-studio/experiments/mcp-genmedia/mcp-genmedia-go/
./install.sh
go install github.com/f/mcptools/cmd/mcptools@latest
```

ローカル環境で MCP サーバが動作することを確認します。

```bash
PROJECT_ID=${GOOGLE_CLOUD_PROJECT} mcptools call imagen_t2i \
    --params '{"prompt": "A dog running around the park", "output_directory": "./output"}' \
    mcp-imagen-go
```

問題なければ ADK を起動し、エージェントと対話してみてください。

```bash
adk web
```


## クラウドへのデプロイ

動画や画像を生成する MCP サーバは Cloud Run へデプロイし  
AI エージェント本体のみの Agent Engine へデプロイします。  
その後、社内のエージェント プラットフォームとして公開するために Agentspace へ登録します。

### MCP サーバを Cloud Run へ

利用するサービスの API を有効化して

```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
```

Artifact Registry にリポジトリを作成します。

```bash
export REPOSITORY_NAME=ai-agents
gcloud artifacts repositories create "${REPOSITORY_NAME}" \
    --repository-format docker --location "${GOOGLE_CLOUD_LOCATION}"
```

Cloud Build を使ってイメージをビルドし、Artifact Registry に保存します。

```bash
export IMAGE_NAME="${GOOGLE_CLOUD_LOCATION}-docker.pkg.dev/${GOOGLE_CLOUD_PROJECT}/${REPOSITORY_NAME}/media-agent:latest"
compute_sa="$( gcloud projects describe ${GOOGLE_CLOUD_PROJECT} --format="value(projectNumber)" )-compute@developer.gserviceaccount.com"
gcloud projects add-iam-policy-binding ${GOOGLE_CLOUD_PROJECT} --member "serviceAccount:${compute_sa}" --role "roles/serviceusage.serviceUsageConsumer"
gcloud projects add-iam-policy-binding ${GOOGLE_CLOUD_PROJECT} --member "serviceAccount:${compute_sa}" --role "roles/artifactregistry.writer"
gcloud projects add-iam-policy-binding ${GOOGLE_CLOUD_PROJECT} --member "serviceAccount:${compute_sa}" --role "roles/storage.admin"
gcloud builds submit --tag "${IMAGE_NAME}" .devcontainer/.mcp-genmedia
```

Cloud Run のためのサービスアカウントを作り

```bash
datetime=$( date +"%Y%m%d%H%M%S" )
gcloud iam service-accounts create "genmedia-mcps-${datetime}" --display-name "GenMedia MCP servers on Cloud Run"
gcloud projects add-iam-policy-binding ${GOOGLE_CLOUD_PROJECT} \
    --member "serviceAccount:genmedia-mcps-${datetime}@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com" \
    --role "roles/aiplatform.user"
gcloud projects add-iam-policy-binding ${GOOGLE_CLOUD_PROJECT} \
    --member "serviceAccount:genmedia-mcps-${datetime}@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com" \
    --role "roles/storage.admin"
```

Cloud Run をデプロイします。

```bash
gcloud run deploy mcp-veo --region "${GOOGLE_CLOUD_LOCATION}" \
    --image "${IMAGE_NAME}" --command "/mcp-veo-go,-transport,http" \
    --set-env-vars "PROJECT_ID=${GOOGLE_CLOUD_PROJECT},LOCATION=${GOOGLE_CLOUD_LOCATION},GENMEDIA_BUCKET=${GENMEDIA_BUCKET}" \
    --service-account "genmedia-mcps-${datetime}@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com" \
    --cpu 1 --memory 128Mi --max-instances 1 --allow-unauthenticated
gcloud run deploy mcp-imagen --region "${GOOGLE_CLOUD_LOCATION}" \
    --image "${IMAGE_NAME}" --command "/mcp-imagen-go,-transport,http" \
    --set-env-vars "PROJECT_ID=${GOOGLE_CLOUD_PROJECT},LOCATION=${GOOGLE_CLOUD_LOCATION},GENMEDIA_BUCKET=${GENMEDIA_BUCKET}" \
    --service-account "genmedia-mcps-${datetime}@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com" \
    --cpu 1 --memory 128Mi --max-instances 1 --allow-unauthenticated
```

### AI エージェントを Agent Engine へ

`media_agent` フォルダに `.env` ファイルをコピーしましょう。

```bash
cat << EOF > media_agent/.env
PROJECT_NAME="media-agent"
GOOGLE_GENAI_USE_VERTEXAI=1

# Genmedia
GENMEDIA_BUCKET=${GENMEDIA_BUCKET}
REFERENCE_IMAGE_URI=${REFERENCE_IMAGE_URI}

# MCP servers
MCP_VEO_ENDPOINT=$( gcloud run services describe mcp-veo --region ${GOOGLE_CLOUD_LOCATION} --format 'value(status.url)' )/mcp
MCP_IMAGEN_ENDPOINT=$( gcloud run services describe mcp-imagen --region ${GOOGLE_CLOUD_LOCATION} --format 'value(status.url)' )/mcp
EOF
```

Agent Engine のカスタム サービスアカウントを権限とともに設定します。

```bash
gcloud beta services identity create --service "aiplatform.googleapis.com"
export AGENT_ENGINE_SERVICE_ACCOUNT="service-$( gcloud projects describe ${GOOGLE_CLOUD_PROJECT} \
    --format="value(projectNumber)" )@gcp-sa-aiplatform-re.iam.gserviceaccount.com"
gcloud projects add-iam-policy-binding ${GOOGLE_CLOUD_PROJECT} --member "serviceAccount:${compute_sa}" \
    --role "roles/aiplatform.user"
gcloud projects add-iam-policy-binding ${GOOGLE_CLOUD_PROJECT} --member "serviceAccount:${compute_sa}" \
    --role "roles/storage.admin"
gcloud projects add-iam-policy-binding ${GOOGLE_CLOUD_PROJECT} --member "serviceAccount:${compute_sa}" \
    --role "roles/run.invoker"
```

Agent Engine に登録する予定の名前と概要を環境変数に設定しておきます。

```bash
export AGENT_ENGINE_DISPLAY_NAME="Media agent"
export AGENT_ENGINE_DESCRIPTION="四則演算を行うエージェントです"
```

本来 `adk deploy agent_engine` コマンドが手軽なのですが、2025 年 10 月 1 日現在 [こんな不具合](https://github.com/google/adk-python/issues/2995) が起こっているため、代わりに [Agent Starter Pack (ASP)](https://googlecloudplatform.github.io/agent-starter-pack/) を使ってみます。

```bash
uvx agent-starter-pack enhance --adk -d agent_engine
```

いくつか選択を迫られますが、常に最初の選択肢を選んでしまって問題ありません。

- Continue with enhancement? [Y/n]: -> `Y`
- Select agent directory (1): -> `1` (media_agent)
- Enter the number of your CI/CD runner choice (1): -> `1` (Google Cloud Build)
- Enter desired GCP region (Gemini uses global endpoint by default) (us-central1) -> `us-central1` (Iowa)

ASP で生成されたコードも依存解決し

```bash
make install
```

2025 年 10 月 1 日現在意図しない挙動があるため、ちょっとしたワークアラウンドを行いつつ Agent Engine に登録します。

```bash
uv pip freeze > .requirements.txt
mv media_agent/agent_engine_app.py ./
uv run agent_engine_app.py --agent-name "${AGENT_ENGINE_DISPLAY_NAME}" --service-account "${AGENT_ENGINE_SERVICE_ACCOUNT}"
```

デプロイできたことの確認も兼ねて、リソースの名前を取得してみます。

```bash
api_host="https://${GOOGLE_CLOUD_LOCATION}-aiplatform.googleapis.com"
api_endpoint="${api_host}/v1/projects/${GOOGLE_CLOUD_PROJECT}/locations/${GOOGLE_CLOUD_LOCATION}/reasoningEngines"
export AGENT_ENGINE_RESOURCE_NAME=$( curl -sX GET "${api_endpoint}" -H "Authorization: Bearer $(gcloud auth print-access-token)" | jq -r '.reasoningEngines[] | select(.displayName | contains("Media")) | .name' )
echo "${AGENT_ENGINE_RESOURCE_NAME}"
```

### Agent Engine へのアクセス

実際に対話してみます。`test_user` としてセッションを開始して

```text
session=$( curl -sX POST "${api_endpoint}/"${AGENT_ENGINE_RESOURCE_NAME##*/}":query" -H "Authorization: Bearer $(gcloud auth print-access-token)" -H "Content-Type: application/json" -d '{"class_method": "async_create_session", "input": {"user_id": "test_user"}}' )
session_id=$( echo "${session}" | jq -r ".output.id")
echo "${session}" | jq .
```

そのセッションを利用してエージェントにメッセージを送信してみます。

```text
message_base='{"class_method": "async_stream_query", "input": {"user_id": "test_user", "message": "(1456 - 98 * 12) / 7 = ?"'
response=$( curl -sX POST "${api_endpoint}/"${AGENT_ENGINE_RESOURCE_NAME##*/}":streamQuery?alt=sse" -H "Authorization: Bearer $(gcloud auth print-access-token)" -H "Content-Type: application/json" -d "${message_base}, \"session_id\": \"${session_id}\"}}" )
echo "${response}" | jq -s ".[-1].content.parts"
```

ローカルの ADK から、セッション管理だけを利用することもできます。繋いでみましょう。

```bash
adk web --session_service_uri "agentengine://${AGENT_ENGINE_RESOURCE_NAME}"
```

### AI エージェントを Agentspace へ登録

作ったエージェントは Google Agentspace へ登録し、同僚たちに使ってもらいましょう。  
一時フォルダを作り、ツールをダウンロードします。

```bash
mkdir tmp && cd $_
git clone https://github.com/VeerMuchandi/agent_registration_tool.git
cd agent_registration_tool
```

クラウドの管理コンソールの URL から Agentspace の ID とロケーションを確認します。

例えば `https://console.cloud.google.com/gen-app-builder/locations/<location>/engines/<agentspace-id>/as-overview/..` といった URL の中の

`<agentspace-id>` がその ID であり

```bash
agentspace_id=
```

`<location>` がロケーションです。

```bash
agentspace_location="global"
```

設定ファイルを `config.json` として用意して

```text
cat << EOF > config.json
{
    "project_id": "${GOOGLE_CLOUD_PROJECT}",
    "location": "${GOOGLE_CLOUD_LOCATION}",
    "re_resource_name": "${AGENT_ENGINE_RESOURCE_NAME}",
    "re_resource_id": "${AGENT_ENGINE_RESOURCE_NAME##*/}",
    "re_display_name": "${AGENT_ENGINE_DISPLAY_NAME}",
    "app_id": "${agentspace_id}",
    "agent_id": "media-agent",
    "ars_display_name": "${AGENT_ENGINE_DISPLAY_NAME}",
    "description": "${AGENT_ENGINE_DESCRIPTION}",
    "tool_description": "This is an agent that can perform arithmetic operations. Don't answer based on intuition; think carefully about how to use the tool beforehand and make an effort to serve properly.",
    "adk_deployment_id": "${AGENT_ENGINE_RESOURCE_NAME##*/}",
    "auth_id": "",
    "icon_uri": "",
    "api_location": "${agentspace_location}",
    "re_location": "${GOOGLE_CLOUD_LOCATION}"
}
EOF
```

準備ができたら登録します。

```bash
python3 as_registry_client.py register_agent
```

以下のようなエラーがでるかもしれません。  
その場合、現在 Agentspace への登録が制限されている可能性があります。また後日試してみてください。

```json
"error": {
    "code": 404,
    "message": "Method not found.",
    "status": "NOT_FOUND"
}
```
