# メディア エージェント

さまざまなメディアを依頼された内容に基づいて生成する AI エージェントです。

Google の [Agent Development Kit (ADK)](https://google.github.io/adk-docs/) をベースに  
さまざまな AI モデルを活用してメディアを生成します。

### ローカル起動

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
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member "serviceAccount:${GOOGLE_CLOUD_SA_EMAIL}" \
    --role "roles/storage.admin"
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member "serviceAccount:${GOOGLE_CLOUD_SA_EMAIL}" \
    --role "roles/iam.serviceAccountTokenCreator"
```

あなた自身にも `Service Account Token Creator` 権限があることを確認します。

```bash
export YOUR_GOOGLE_ACCOUNT_EMAIL=
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
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
IMAGEN_INSTRUCTION="Please create an image that will increase its favorable impression."
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
mcptools call imagen_t2i --params '{"prompt": "A dog running around the park", "output_directory": "./output"}' mcp-imagen-go
```

問題なければ ADK を起動し、エージェントと対話してみてください。

```bash
adk web
```
