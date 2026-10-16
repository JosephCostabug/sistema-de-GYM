"""Inicia a API e o frontend para desenvolvimento local."""

from pathlib import Path
import argparse
import os
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def valid_port(value: str) -> int:
    port = int(value)
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("a porta deve estar entre 1 e 65535")
    return port


def python_executable() -> str:
    """Prefere o ambiente virtual do repositório, se existir."""
    if os.name == "nt":
        candidate = ROOT / ".venv" / "Scripts" / "python.exe"
    else:
        candidate = ROOT / ".venv" / "bin" / "python"
    return str(candidate) if candidate.is_file() else sys.executable


def start_process(
    command: list[str] | str,
    *,
    cwd: Path,
    env: dict[str, str],
    use_shell: bool = False,
) -> subprocess.Popen:
    options: dict[str, object] = {
        "cwd": cwd,
        "env": env,
        "shell": use_shell,
    }
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    return subprocess.Popen(command, **options)


def stop_process(process: subprocess.Popen) -> None:
    """Encerra também os processos descendentes do servidor."""
    if process.poll() is not None:
        return

    try:
        if os.name == "nt":
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            os.killpg(process.pid, signal.SIGTERM)
    except OSError:
        process.terminate()

    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inicia a API e o frontend do G7M para desenvolvimento local."
    )
    parser.add_argument("--api-port", type=valid_port, default=8000)
    parser.add_argument("--frontend-port", type=valid_port, default=5173)
    args = parser.parse_args()

    api_url = f"http://127.0.0.1:{args.api_port}"
    frontend_url = f"http://127.0.0.1:{args.frontend_port}"

    npm = shutil.which("npm")
    if npm is None:
        print("Não foi encontrado o npm. Instale o Node.js e tente novamente.", file=sys.stderr)
        return 1

    python = python_executable()
    try:
        subprocess.run(
            [python, "-m", "uvicorn", "--version"],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        print(
            "Uvicorn não está instalado no interpretador Python seleccionado. "
            "Instale as dependências do backend no ambiente virtual.",
            file=sys.stderr,
        )
        if error.stderr:
            print(error.stderr.strip(), file=sys.stderr)
        return 1

    env = os.environ.copy()
    env.setdefault("VITE_API_URL", api_url)
    commands: list[tuple[str, list[str] | str, Path, bool]] = [
        (
            "Backend",
            [
                python,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(args.api_port),
                "--reload",
                "--reload-dir",
                "app",
            ],
            ROOT,
            False,
        ),
        (
            "Frontend",
            subprocess.list2cmdline([npm, "run", "dev"])
            + f" -- --port {args.frontend_port} --strictPort"
            if os.name == "nt"
            else [
                npm,
                "run",
                "dev",
                "--",
                "--port",
                str(args.frontend_port),
                "--strictPort",
            ],
            FRONTEND,
            os.name == "nt",
        ),
    ]
    processes: list[tuple[str, subprocess.Popen]] = []

    try:
        for name, command, cwd, use_shell in commands:
            processes.append(
                (
                    name,
                    start_process(command, cwd=cwd, env=env, use_shell=use_shell),
                )
            )
        print(f"Backend:  {api_url}/docs", flush=True)
        print(f"Frontend: {frontend_url}", flush=True)
        print("Prima Ctrl+C para encerrar os dois servidores.", flush=True)

        while True:
            for name, process in processes:
                exit_code = process.poll()
                if exit_code is not None:
                    print(
                        f"{name} terminou (código {exit_code}); a encerrar o outro servidor.",
                        file=sys.stderr,
                        flush=True,
                    )
                    return exit_code or 1
            time.sleep(0.25)
    except KeyboardInterrupt:
        print("\nA encerrar os servidores...", flush=True)
        return 0
    except OSError as error:
        print(f"Não foi possível iniciar os servidores: {error}", file=sys.stderr)
        return 1
    finally:
        for _, process in reversed(processes):
            stop_process(process)


if __name__ == "__main__":
    raise SystemExit(main())
