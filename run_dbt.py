import json
import os
import subprocess
import sys
import sysconfig
from pathlib import Path

from dotenv import load_dotenv

from locations import LOCATIONS


def find_dbt_executable() -> Path:
    scripts_dir = Path(sysconfig.get_path("scripts"))
    executable_name = "dbt.exe" if os.name == "nt" else "dbt"
    executable_path = scripts_dir / executable_name

    if not executable_path.is_file():
        raise RuntimeError(
            f"dbt executable was not found at: {executable_path}. "
            "Install requirements using this Python interpreter: "
            f"{sys.executable}"
        )

    return executable_path


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit(
            "Usage: python run_dbt.py <dbt command>"
        )

    project_dir = Path(__file__).resolve().parent
    dbt_dir = project_dir / "dbt"

    load_dotenv(project_dir / ".env")

    if not os.getenv("POSTGRES_PASSWORD"):
        raise ValueError(
            "POSTGRES_PASSWORD is missing from the environment"
        )

    dbt_executable = find_dbt_executable()

    variables = {
        "weather_locations": LOCATIONS,
    }

    command = [
        str(dbt_executable),
        *sys.argv[1:],
        "--project-dir",
        str(dbt_dir),
        "--profiles-dir",
        str(dbt_dir),
        "--vars",
        json.dumps(variables),
    ]

    result = subprocess.run(
        command,
        cwd=project_dir,
    )

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())