from __future__ import annotations

from datetime import datetime
import os
import sys
from dotenv import load_dotenv, dotenv_values
import tempfile
import json
import shutil
import subprocess
from typing import Final
from typing import Optional

import vertexai
from vertexai import agent_engines


# from media_agent.agent import app


load_dotenv()

required_env_vars = [
    "GOOGLE_CLOUD_PROJECT",
    "GOOGLE_CLOUD_LOCATION",
    "GENMEDIA_BUCKET",
    "AGENT_ENGINE_DISPLAY_NAME",
    "AGENT_ENGINE_DESCRIPTION",
    # "AGENT_ENGINE_SERVICE_ACCOUNT",
]
missing_env_vars = []


for var in required_env_vars:
    if var not in os.environ:
        missing_env_vars.append(var)

if missing_env_vars:
    print(f"The following variables are missing: {', '.join(missing_env_vars)}")
    sys.exit(1)

vertexai.init(
    project=os.getenv("GOOGLE_CLOUD_PROJECT"),
    location=os.getenv("GOOGLE_CLOUD_LOCATION"),
    staging_bucket=f"gs://{os.getenv("GENMEDIA_BUCKET")}",
)


def main():
    # from google.adk.cli.cli_deploy import to_agent_engine を参考に実装
    to_agent_engine(
        agent_folder="media_agent",
        project=os.getenv("GOOGLE_CLOUD_PROJECT"),
        region=os.getenv("GOOGLE_CLOUD_LOCATION"),
        staging_bucket=f"gs://{os.getenv("GENMEDIA_BUCKET")}",
        agent_engine_id=os.getenv("AGENT_ENGINE_RESOURCE_NAME"),
        trace_to_cloud=True,
        display_name=os.getenv("AGENT_ENGINE_DISPLAY_NAME"),
        description=os.getenv("AGENT_ENGINE_DESCRIPTION"),
        adk_app="agent_engine_app",
        temp_folder=os.path.join(
            tempfile.gettempdir(),
            "agent_engine_deploy_src",
            datetime.now().strftime("%Y%m%d_%H%M%S"),
        ),
        env_file="",
        requirements_file="",
        absolutize_imports=True,
        agent_engine_config_file="",
        min_instances=0,
        max_instances=1,
        service_account=os.getenv("AGENT_ENGINE_SERVICE_ACCOUNT"),
    )

    # agent_engine_config = {
    #     "display_name": os.getenv("AGENT_ENGINE_DISPLAY_NAME"),
    #     "description": os.getenv("AGENT_ENGINE_DESCRIPTION"),
    #     "requirements": [
    #         "google-cloud-aiplatform[adk,agent-engines]>=1.117.0",
    #         "a2a-sdk>=0.3.7",
    #         "google-adk[a2a,eval]>=1.15.1",
    #         "python-dotenv>=1.1.1",
    #     ],
    #     "env_vars": {
    #         "GOOGLE_GENAI_USE_VERTEXAI": os.getenv("AGENT_ENGINE_DESCRIPTION"),
    #         "GENMEDIA_BUCKET": os.getenv("GENMEDIA_BUCKET"),
    #         "REFERENCE_IMAGE_URI": os.getenv("REFERENCE_IMAGE_URI"),
    #         "IMAGEN_INSTRUCTION": os.getenv("IMAGEN_INSTRUCTION"),
    #         "MCP_VEO_ENDPOINT": os.getenv("MCP_VEO_ENDPOINT"),
    #         "MCP_IMAGEN_ENDPOINT": os.getenv("MCP_IMAGEN_ENDPOINT"),
    #     },
    #     "min_instances": 0,
    #     "max_instances": 1,
    #     "resource_limits": {"cpu": "2", "memory": "1Gi"},
    #     "service_account": os.getenv("AGENT_ENGINE_SERVICE_ACCOUNT"),
    # }
    # if resource_name := os.getenv("AGENT_ENGINE_RESOURCE_NAME"):
    #     result = agent_engines.update(
    #         **agent_engine_config, resource_name=resource_name, agent_engine=app
    #     )
    # else:
    #     result = agent_engines.create(**agent_engine_config, agent_engine=app)
    # print(result)


_AGENT_ENGINE_APP_TEMPLATE: Final[
    str
] = """
from vertexai.preview.reasoning_engines import AdkApp

if {is_config_agent}:
  from google.adk.agents import config_agent_utils
  try:
    # This path is for local loading.
    root_agent = config_agent_utils.from_config("{agent_folder}/root_agent.yaml")
  except FileNotFoundError:
    # This path is used to support the file structure in Agent Engine.
    root_agent = config_agent_utils.from_config("./{temp_folder}/{app_name}/root_agent.yaml")
else:
  from {app_name}.agent import root_agent

adk_app = AdkApp(
  agent=root_agent,
  enable_tracing={trace_to_cloud_option},
)
"""


def _resolve_project(project_in_option: Optional[str]) -> str:
    if project_in_option:
        return project_in_option

    result = subprocess.run(
        ["gcloud", "config", "get-value", "project"],
        check=True,
        capture_output=True,
        text=True,
    )
    project = result.stdout.strip()
    print(f"Use default project: {project}")
    return project


def to_agent_engine(
    *,
    agent_folder: str,
    temp_folder: str,
    adk_app: str,
    staging_bucket: str,
    trace_to_cloud: bool,
    agent_engine_id: Optional[str] = None,
    absolutize_imports: bool = True,
    project: Optional[str] = None,
    region: Optional[str] = None,
    display_name: Optional[str] = None,
    description: Optional[str] = None,
    requirements_file: Optional[str] = None,
    env_file: Optional[str] = None,
    agent_engine_config_file: Optional[str] = None,
    min_instances: Optional[str] = None,
    max_instances: Optional[str] = None,
    service_account: Optional[str] = None,
):
    """Deploys an agent to Vertex AI Agent Engine."""

    app_name = os.path.basename(agent_folder)
    agent_src_path = os.path.join(temp_folder, app_name)
    # remove agent_src_path if it exists
    if os.path.exists(agent_src_path):
        print("Removing existing files")
        shutil.rmtree(agent_src_path)

    try:
        ignore_patterns = None
        ae_ignore_path = os.path.join(agent_folder, ".ae_ignore")
        if os.path.exists(ae_ignore_path):
            print(f"Ignoring files matching the patterns in {ae_ignore_path}")
            with open(ae_ignore_path, "r") as f:
                patterns = [pattern.strip() for pattern in f.readlines()]
                ignore_patterns = shutil.ignore_patterns(*patterns)
        print("Copying agent source code...")
        shutil.copytree(agent_folder, agent_src_path, ignore=ignore_patterns)
        print("Copying agent source code complete.")

        print("Initializing Vertex AI...")

        sys.path.append(temp_folder)  # To register the adk_app operations
        project = _resolve_project(project)

        print("Resolving files and dependencies...")
        agent_config = {}
        if not agent_engine_config_file:
            # Attempt to read the agent engine config from .agent_engine_config.json in the dir (if any).
            agent_engine_config_file = os.path.join(
                agent_folder, ".agent_engine_config.json"
            )
        if os.path.exists(agent_engine_config_file):
            print(f"Reading agent engine config from {agent_engine_config_file}")
            with open(agent_engine_config_file, "r") as f:
                agent_config = json.load(f)
        if display_name:
            if "display_name" in agent_config:
                print(
                    "Overriding display_name in agent engine config with"
                    f" {display_name}"
                )
            agent_config["display_name"] = display_name
        if description:
            if "description" in agent_config:
                print(
                    f"Overriding description in agent engine config with {description}"
                )
            agent_config["description"] = description
        if agent_config.get("extra_packages"):
            agent_config["extra_packages"].append(temp_folder)
        else:
            agent_config["extra_packages"] = [temp_folder]

        if not requirements_file:
            # Attempt to read requirements from requirements.txt in the dir (if any).
            requirements_txt_path = os.path.join(agent_src_path, "requirements.txt")
            if not os.path.exists(requirements_txt_path):
                print(f"Creating {requirements_txt_path}...")
                with open(requirements_txt_path, "w", encoding="utf-8") as f:
                    f.write("google-cloud-aiplatform[adk,agent_engines]")
                print(f"Created {requirements_txt_path}")
            agent_config["requirements"] = agent_config.get(
                "requirements",
                requirements_txt_path,
            )
        else:
            if "requirements" in agent_config:
                print(
                    "Overriding requirements in agent engine config with "
                    f"{requirements_file}"
                )
            agent_config["requirements"] = requirements_file

        env_vars = None
        if not env_file:
            # Attempt to read the env variables from .env in the dir (if any).
            env_file = os.path.join(agent_folder, ".env")
        if os.path.exists(env_file):

            print(f"Reading environment variables from {env_file}")
            env_vars = dotenv_values(env_file)
            if "GOOGLE_CLOUD_PROJECT" in env_vars:
                env_project = env_vars.pop("GOOGLE_CLOUD_PROJECT")
                if env_project:
                    if project:
                        print(
                            "Ignoring GOOGLE_CLOUD_PROJECT in .env as `--project` was explicitly passed and takes precedence"
                        )
                    else:
                        project = env_project
                        print(f"{project=} set by GOOGLE_CLOUD_PROJECT in {env_file}")
            if "GOOGLE_CLOUD_LOCATION" in env_vars:
                env_region = env_vars.pop("GOOGLE_CLOUD_LOCATION")
                if env_region:
                    if region:
                        print(
                            "Ignoring GOOGLE_CLOUD_LOCATION in .env as `--region` was explicitly passed and takes precedence"
                        )
                    else:
                        region = env_region
                        print(f"{region=} set by GOOGLE_CLOUD_LOCATION in {env_file}")
        if env_vars:
            if "env_vars" in agent_config:
                print(f"Overriding env_vars in agent engine config with {env_vars}")
            agent_config["env_vars"] = env_vars
        # Set env_vars in agent_config to None if it is not set.
        agent_config["env_vars"] = agent_config.get("env_vars", env_vars)

        if min_instances is not None:
            agent_config["min_instances"] = min_instances

        if max_instances is not None:
            agent_config["max_instances"] = max_instances

        if service_account is not None:
            agent_config["service_account"] = service_account

        agent_config["resource_limits"] = {"cpu": "2", "memory": "1Gi"}

        vertexai.init(
            project=project,
            location=region,
            staging_bucket=staging_bucket,
        )
        print("Vertex AI initialized.")

        is_config_agent = False
        config_root_agent_file = os.path.join(agent_src_path, "root_agent.yaml")
        if os.path.exists(config_root_agent_file):
            print(f"Config agent detected: {config_root_agent_file}")
            is_config_agent = True

        adk_app_file = os.path.join(temp_folder, f"{adk_app}.py")
        with open(adk_app_file, "w", encoding="utf-8") as f:
            f.write(
                _AGENT_ENGINE_APP_TEMPLATE.format(
                    app_name=app_name,
                    trace_to_cloud_option=trace_to_cloud,
                    is_config_agent=is_config_agent,
                    temp_folder=temp_folder,
                    agent_folder=agent_folder,
                )
            )
        print(f"Created {adk_app_file}")
        print("Files and dependencies resolved")
        if absolutize_imports:
            for root, _, files in os.walk(agent_src_path):
                for file in files:
                    if file.endswith(".py"):
                        absolutize_imports_path = os.path.join(root, file)
                        try:
                            print(
                                f"Running `absolufy-imports {absolutize_imports_path}`"
                            )
                            subprocess.run(
                                ["absolufy-imports", absolutize_imports_path],
                                cwd=temp_folder,
                            )
                        except Exception as e:
                            print(f"The following exception was raised: {e}")

        print("Deploying to agent engine...")
        agent_config["agent_engine"] = agent_engines.ModuleAgent(
            module_name=adk_app,
            agent_name="adk_app",
            register_operations={
                "": [
                    "get_session",
                    "list_sessions",
                    "create_session",
                    "delete_session",
                ],
                "async": [
                    "async_get_session",
                    "async_list_sessions",
                    "async_create_session",
                    "async_delete_session",
                ],
                "async_stream": ["async_stream_query"],
                "stream": ["stream_query", "streaming_agent_run_with_events"],
            },
            sys_paths=[temp_folder[1:]],
            agent_framework="google-adk",
        )

        print(f"********** Agent config ********** {agent_config}")

        if agent_engine_id:
            result = agent_engines.update(**agent_config, resource_name=agent_engine_id)
        else:
            result = agent_engines.create(**agent_config)
        print(result)

        # if not agent_engine_id:
        #     agent_engines.create(**agent_config)
        # else:
        #     resource_name = f"projects/{project}/locations/{region}/reasoningEngines/{agent_engine_id}"
        #     agent_engines.update(resource_name=resource_name, **agent_config)
    finally:
        print(f"Cleaning up the temp folder: {temp_folder}")
        shutil.rmtree(temp_folder)


if __name__ == "__main__":
    main()
