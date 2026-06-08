import nox

py_vers = [f"3.{v}" for v in range(10, 15)]


@nox.session(python=py_vers[-1], venv_backend="uv")
def fmt(session: nox.Session) -> None:
    session.install("-e", ".", "--group", "dev")
    session.run("ruff", "check", "--fix-only", ".")
    session.run("ruff", "format", ".")


@nox.session(python=py_vers, venv_backend="uv")
def test(session):
    session.install("-e", ".", "--group", "dev")
    session.chdir("tests")
    session.run(
        "pytest",
        "-s",
        "-x",
        *session.posargs,
    )
