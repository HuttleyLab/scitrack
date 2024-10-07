import nox


@nox.session(python=[f"3.{v}" for v in range(9, 14)])
def test(session):
    session.install(".[test]")
    session.chdir("tests")
    session.run(
        "pytest",
        "-s",
        "-x",
        *session.posargs,
    )
