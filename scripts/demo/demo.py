"""Guarded local Demo lifecycle. No migrations, fixtures, reset or auth bypass."""
import argparse
import hmac
import json
import socket
from socketserver import ThreadingMixIn
import subprocess
import threading
import time
from urllib.error import URLError
from urllib.request import Request, urlopen
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

from common import *


HEALTH = "/__demo_infrastructure__/"


def port_free():
    try:
        with socket.socket() as sock:
            if os.name == "nt":
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            sock.bind(("127.0.0.1", APP_PORT))
    except OSError:
        raise DemoError(f"Port {APP_PORT} is unavailable; no process was stopped.") from None


def health(profile):
    try:
        with urlopen(profile["url"] + HEALTH, timeout=3) as response:
            value = json.load(response)
    except (URLError, ValueError, OSError):
        raise DemoError("No verified Demo listener is available.") from None
    require(value.get("identity") == profile["identity"] and value.get("database") == DATABASE
            and value.get("role") == RUNTIME and value.get("migration_fingerprint") == profile["migration_fingerprint"],
            "Listener identity mismatch; no shutdown request was sent.")
    return value


def preflight(profile, state):
    verify_container(profile)
    from lock_capabilities import validate_runtime
    from initialization import fixture_ready
    with connect(profile, state) as conn:
        capabilities = validate_runtime(conn, profile, state)
        fixture_ready(conn,profile,state)
    configure_django(profile, state)
    check_schema(profile)
    return capabilities


def serve(profile, state):
    port_free()
    capabilities = preflight(profile, state)
    from django.core.wsgi import get_wsgi_application
    from django.contrib.staticfiles.handlers import StaticFilesHandler
    application = StaticFilesHandler(get_wsgi_application())
    token = (state / "credentials/control-token.key").read_text(encoding="utf-8").strip()
    require(len(token) >= 48, "Demo control credential missing.")

    def wrapped(environ, start_response):
        path = environ.get("PATH_INFO")
        if path in (HEALTH, HEALTH + "stop/"):
            method = environ.get("REQUEST_METHOD")
            allowed = environ.get("HTTP_HOST") == f"localhost:{profile['application_port']}" and environ.get("REMOTE_ADDR") == "127.0.0.1"
            if path == HEALTH and method == "GET" and allowed:
                fixture_path = state / "fixtures/manifest.json"
                fixture = read_json(fixture_path) if fixture_path.exists() else {}
                value = dict(identity=profile["identity"], database=DATABASE, role=RUNTIME, pid=os.getpid(), parent_pid=os.getppid(),
                             migration_fingerprint=profile["migration_fingerprint"],
                             capability_version=capabilities['version'], capability_sha256=capabilities['sha256'],
                             fixtures_ready=fixture.get("identity") == profile["identity"] and fixture.get("phase") == "complete")
                start_response("200 OK", [("Content-Type", "application/json"), ("Cache-Control", "no-store")])
                return [json.dumps(value).encode()]
            if path == HEALTH + "stop/" and method == "POST" and allowed and hmac.compare_digest(
                    environ.get("HTTP_X_DEMO_CONTROL", ""), token):
                start_response("200 OK", [("Content-Type", "application/json")])
                threading.Thread(target=server.shutdown, daemon=True).start()
                return [b'{"stopping":true}']
            start_response("403 Forbidden", [("Content-Type", "text/plain")])
            return [b"Denied"]
        return application(environ, start_response)

    class Server(ThreadingMixIn, WSGIServer):
        daemon_threads = True
        allow_reuse_address = False

        def server_bind(self):
            if os.name == "nt":
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            super().server_bind()

    class QuietHandler(WSGIRequestHandler):
        def log_message(self, format, *args):
            # Do not log signed contexts, CSRF values or passwords in query strings.
            pass

    with make_server("127.0.0.1", profile["application_port"], wrapped, server_class=Server, handler_class=QuietHandler) as server:
        write_json(state / "run/listener.json", {"pid": os.getpid(), "identity": profile["identity"]})
        server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "start", "serve", "status", "stop", "restart-database"))
    parser.add_argument("--state-root", type=Path, default=DEFAULT_STATE)
    args = parser.parse_args()
    state = args.state_root.resolve()
    profile = load_profile(state)
    if args.command == "status":
        verify_container(profile)
        print(json.dumps(health(profile), sort_keys=True))
    elif args.command == "check":
        preflight(profile, state)
        print("Verified dedicated Demo identity, runtime connection and 50-migration graph.")
    elif args.command == "serve":
        serve(profile, state)
    elif args.command == "start":
        port_free()
        value = verify_container(profile, running=False)
        if not value["State"]["Running"]:
            docker("start", profile["container_id"])
            for _ in range(60):
                value = json.loads(docker("inspect", CONTAINER))[0]
                if value["State"].get("Health", {}).get("Status") == "healthy":
                    break
                time.sleep(1)
        preflight(profile, state)
        with (state / "run/server.log").open("ab") as log:
            process = subprocess.Popen([sys.executable, "-B", str(Path(__file__).resolve()), "serve", "--state-root", str(state)],
                cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        for _ in range(30):
            if process.poll() is not None:
                raise DemoError("Demo listener stopped; inspect the protected server log.")
            try:
                value = health(profile)
                # Windows venv python.exe can be a redirector: the serving Python
                # process is its direct child, not Popen.pid itself.
                require(process.pid in {value["pid"], value.get("parent_pid")}, "Unexpected listener process ancestry.")
                print(f"Demo available: {profile['url']}/accounts/login/; TEST credentials, if provisioned, remain in protected local state.")
                break
            except DemoError:
                time.sleep(1)
        else:
            raise DemoError("Listener readiness timed out; inspect protected listener metadata before retry.")
    elif args.command == "stop":
        value = health(profile)
        require(value == health(profile), "Listener changed during shutdown verification.")
        token = (state / "credentials/control-token.key").read_text(encoding="utf-8").strip()
        request = Request(profile["url"] + HEALTH + "stop/", data=b"", headers={"X-Demo-Control": token}, method="POST")
        with urlopen(request, timeout=5) as response:
            require(response.status == 200, "Verified Demo shutdown failed.")
        for _ in range(20):
            try:
                port_free()
                print("Verified Demo Django listener stopped; database and other previews unchanged.")
                break
            except DemoError:
                time.sleep(.25)
        else:
            raise DemoError("Shutdown incomplete; no process was force-killed.")
    elif args.command == "restart-database":
        port_free()
        verify_container(profile, running=False)
        docker("restart", profile["container_id"])
        for _ in range(60):
            try:
                verify_container(profile)
                with connect(profile, state):
                    pass
                print("Verified dedicated Demo PostgreSQL restarted with its existing volume and marker.")
                break
            except DemoError:
                time.sleep(1)
        else:
            raise DemoError("Demo database restart readiness failed.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("Demo stopped safely: " + (str(exc) if isinstance(exc, DemoError) else type(exc).__name__), file=sys.stderr)
        sys.exit(1)
