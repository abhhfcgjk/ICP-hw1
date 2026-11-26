from pathlib import Path
from subprocess import DEVNULL, run
from urllib.request import urlretrieve


image = "hw1-nncp:3.3"


def setup_nncp(work : Path):
    build_dir = work / "nncp-build"
    build_dir.mkdir(exist_ok=True)
    archive = build_dir / "nncp.tgz"
    if not archive.exists():
        url = "https://bellard.org/nncp/nncp-2024-06-05.tar.gz"
        download = build_dir / "nncp.tgz.part"
        urlretrieve(url, download)
        download.replace(archive)
    dockerfile = Path(__file__).with_name("Dockerfile")
    run(["docker", "build", "--platform", "linux/amd64", "-q",
         "-f", dockerfile, "-t", image, build_dir], check=True, stdout=DEVNULL)


def run_nncp(source : Path, output : Path, mode : str):
    docker = ["docker", "run", "--rm", "--platform", "linux/amd64",
              "-v", f"{source.parent.resolve()}:/data:ro",
              "-v", f"{output.parent.resolve()}:/out", image]
    timer = ["/usr/bin/time", "-f", "%e", "-o", "/out/time.txt"] if mode == "c" else []
    nncp = ["/opt/nncp/nncp", "-q", "-T", "2", mode, source.name, f"/out/{output.name}"]
    run(docker + timer + nncp, check=True, stdout=DEVNULL)


def compress_nncp(source : Path, archive : Path):
    run_nncp(source, archive, "c")
    return float((archive.parent / "time.txt").read_text())


def decompress_nncp(archive : Path, restored : Path):
    run_nncp(archive, restored, "d")
