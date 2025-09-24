# Scripts for local testing

This directory contains scripts that can be used for local testing of the project. These scripts are intended to facilitate development and debugging by providing a straightforward way to run tests and other tasks without needing to set up a full CI/CD pipeline.

## Requirements

Install the project dependencies in the root directory of the repository:

```bash
uv sync --all-extras
```

Build and run the docker image for the Fetch Abstracts Robot from the root directory:

```bash
./build_fetch_abstracts_docker.sh
./run_fetch_abstracts_docker.sh
```

In this directory, run a local file server that mimics remote Azure Blob Storage:

```bash
python file_server.py
```

Separately, run a local copy of the destiny repository by following the instructions in the [destiny repository](https://github.com/destiny-evidence/destiny-repository). This isn't stricly mandatory as you could use the remote dev instance of the repository, but that then requires additional permissions being set in Azure. Local testing is easier with a local instance of the repository as you are able to register robots and follow logs more easily.

## Available Scripts

- `file_server.py`: A simple HTTP file server to simulate remote storage. See requirements section above.
- `run_robot_request_pipeline.py`: Script to run the robot request pipeline locally. Currently handles single and batch requests, but will soon be refactored to remove single enhancement requests.
- `get_user_token.py`: Script to obtain a user token with the correct robot scope for testing purposes. This is useful for authenticating requests to the destiny repository. Note that this script requires the manual input of a generated code into a browser in order to generate the token.
