# Fetch Abstracts Robot

A _DESTINY_ robot for retrieving abstracts from various third-party APIs, and adding them to `Work`s as an `Enhancement`.

This derived from the example robot producing toy enhancements against the destiny repository available at [destiny-evidence/toy-robot](https://github.com/destiny-evidence/toy-robot).

## tl, dr

A **robot** is an extension/plugin to the _DESTINY_ repository, which, using _DESTINY_'s API (specifically POST) endpoints to create `Enhancement`s on the core unit of analysis, `Record`s (the bespoke data model for scientific publications, reports, papers, etc. which are stored in _DESTINY_-repository).

The **Fetch Abstracts Robot (FAR)** contains functionality for retrieving abstracts for target works by [_DOI_](https://en.wikipedia.org/wiki/Digital_object_identifier). Abstracts are retrieved from third-party APIs and transformed into generic enhancements to a target work. Third-party APIs are configured via an `APIConfig` class, with functionality for handling authentication, abstract unpacking (`AbstractUnpackStrategy`) and abstract (string) cleaning. There is functionality for batch and single abstract retrieval. The hierarchy of which API to hit first is then declared in an `ExternalAPIPriority` class.

If further third-party APIs are to be added, simply instantiate such an `APIConfig`, and import and add it to `AVAILABLE_API_CONFIGS` in `main.py`.

## Setup

### Requirements

[uv](https://astral.sh/uv/) is used for dependency management and managing virtual environments. You can install uv either using `pipx install uv` or the uv installer script:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Installing Dependencies

Once uv is installed, set up a virtual environment:

```sh
uv venv
source .venv/bin/activate
```

Then install the dependencies with the uv-managed `pip`:

```sh
uv pip install .
```

To install additional development and test dependencies, run:

```sh
uv pip install ".[dev,test]"
```

## Development

Before commiting any changes, please run the pre-commit hooks. This will ensure that the code is formatted correctly and minimise diffs to code changes when submitting a pull request.

After installing dependencies as shown above, install the pre-commit hooks:

```sh
pre-commit install
```

pre-commit hooks will run automatically when you commit changes. To run them manually, use:

```sh
pre-commit run --all-files
```

See [.pre-commit-config.yaml](.pre-commit-config.yaml) for the list of pre-commit hooks and their configuration.

## Application

Run the development server:

```sh
fastapi dev --port 8001
```

## Implemented request flows

### Single Enhancement Request Flow

```mermaid
    sequenceDiagram
        participant Destiny Repository
        participant Robot
        Destiny Repository->>+Robot: POST /<robot_base_url>/single/ : destiny_sdk.robots.RobotRequest
        Robot->>Robot: Create enhancement background job
        Robot->>Destiny Repository: Response: 202 Accepted or Failure Status Code
        alt Background Job Success
            Robot->>Destiny Repository: POST /enhancement-requests/single-requests/ : destiny_sdk.robots.RobotResult(request_id, enhancement)
        else Failure
            Robot->>-Destiny Repository: POST /enhancement-requests/single-requests/ : destiny_sdk.robots.RobotResult(request_id, RobotError)
        end
```

### Batch Enhancement Request Flow

```mermaid
    sequenceDiagram
        participant Destiny Repository
        participant Robot
        participant Blob Storage
        Destiny Repository->>+Robot: POST /<robot_base_url>/batch/ : destiny_sdk.robots.BatchRobotRequest
        Robot->>Robot: Create batch enhancement background job
        Robot->>Destiny Repository: Response: 202 Accepted or Failure Status Code
        Robot->>Blob Storage: Download reference file provided in BatchRobotRequest
        Robot->>Robot: Process batch
        alt Background Job Success
            Robot->>Blob Storage: Upload created enhancements
            Robot->>Destiny Repository: POST /enhancement-requests/batch-requests/ : destiny_sdk.robots.BatchRobotResult(request_id, url_storage)
        else Failure
            Robot->>-Destiny Repository: POST /enhancement-requests/batch-requests/ : destiny_sdk.robots.BatchRobotResult(request_id, RobotError)
        end
```

## Authentication Against Destiny Repository

Authentication between the Toy Robot and Destiny Repository uses HMAC authentication, where a request signature is encrypted with the robot's secret key and set as a header. To simplify this process, the destiny_sdk provides both a client for communicating with destiny repository that handles adding signatures, and a service auth that can be used to validate incoming requests.

In Toy Robot the client is inititalised in [main.py](app/main.py) and used for sending requests, the service auth is initialised in [auth.py](app/auth.py) and then used as a dependency on the app endpoints in [main.py](app/main.py)

### Configuring Authentication

- If you are running the robot with a local instance of destiny repository that is not enforcing authentication, add `ENV=local` to your `.env` file. This will cause the robot to bypass authentication. This is to allow easy development only and the robot should not be deployed with `env=local`.
  - In this case you will need to set dummy values for the `ROBOT_ID` and the `ROBOT_SECRET`. For example `ROBOT_ID="9fa8b9bd-12b1-4450-affb-712face23390"` and `ROBOT_SECRET="dummy_secret"`
- If you want to deploy the Toy Robot and use it with destiny repository, the robot will need to be registered with that deployment of destiny repository. The registration process will provide the robot_id and client_secret needed to configure authentication. You can check out the proceedure for registering a robot [here](https://destiny-evidence.github.io/destiny-repository/procedures/robot-registration.html).

## Container Image

When building the docker image

```sh
docker buildx build --tag fetch-abstracts-robot .
```

### Manual push

If you want to deploy the toy robot into Azure using the provided terraform infrastructure, you'll need to manually push the docker image to a container registry. We're using destiny-shared-infra for this.

```sh
az login
docker buildx build --no-cache --platform linux/amd64 --tag destinyevidenceregistry.azurecr.io/fetch-abstracts-robot .
az acr login --name destinyevidenceregistry
docker push destinyevidenceregistry.azurecr.io/fetch-abstracts-robot:YOUR_TAG
```

Then you can deploy your image to the container app

```sh
az containerapp update az containerapp update -n fetch-abstracts-robot-stag-app -g rg-fetch-abstracts-robot-staging --image estinyevidenceregistry.azurecr.io/fetch-abstracts-robot:YOUR_TAG
```

Then you can restart the revision with the following command

```sh
az containerapp revision restart --name fetch-abstracts-robot-stag-app --resource-group rg-fetch-abstracts-robot-staging --revision [REVISION_NAME]
```
