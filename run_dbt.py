import os
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv


def main():
    project_dir = Path(__file__).resolve().parent
    dbt_dir = project_dir / "dbt"

    load_dotenv(project_dir / ".env")

    if not os.getenv("POSTGRES_PASSWORD"):
        raise ValueError("POSTGRES_PASSWORD is missing from the environment")

    dbt_executable = shutil.which("dbt")

    if dbt_executable is None:
        raise RuntimeError(
            "dbt was not found. Activate the virtual environment "
            "and install the project requirements."
        )

    if len(sys.argv) < 2:
        raise SystemExit("Usage: python run_dbt.py <dbt command>")

    command = [
        dbt_executable,
        *sys.argv[1:],
        "--project-dir",
        str(dbt_dir),
        "--profiles-dir",
        str(dbt_dir),
    ]

    result = subprocess.run(command, cwd=project_dir)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())