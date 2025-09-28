# メディア エージェント

さまざまなメディアを依頼された内容に基づいて生成する AI エージェントです。

Google の [Agent Development Kit (ADK)](https://google.github.io/adk-docs/) をベースに  
さまざまな AI モデルを活用してメディアを生成します。

### ローカル起動

このリポジトリを git clone して VS Code の Devcontainer で開きます。  
ターミナルを開き、Google Cloud への認証を通し

```bash
gcloud auth application-default login
```

プロジェクト ID とリージョンを設定しましょう。

```bash
gcloud config set project "<your-project-id>"
export GOOGLE_CLOUD_PROJECT="$( gcloud config get-value project )"
export GOOGLE_CLOUD_LOCATION="us-central1"
```

ADK を起動し、対話してみてください。

```bash
adk run media-agent
```
