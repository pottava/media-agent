from google.adk.agents import LlmAgent


root_agent = LlmAgent(
    name="media_agent",
    model="gemini-2.5-flash",
    description="メディア生成エージェント",
    instruction="あなたは自社メディアコンテンツの作成を支援するアシスタントです",
)
