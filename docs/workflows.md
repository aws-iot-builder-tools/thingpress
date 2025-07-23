# GitHub Workflows in this repository

# Runners

## ubuntu-latest

pylint -> coverage -> sam lint -> sam build

pylint -> coverage -> sam lint -> sam build -> sam deploy


## windows-latest

## macos-latest

# Workflows

## Pylint

## Coverage

## SAM Lint

SAM Lint depends on pylint and coverage jobs.

## SAM Build
SAM Build runs on pull requests and push to main.

SAM Build runs on Ubuntu, Windows, and MacOS runners to verify buildability for those events.

SAM Build depends on SAM Lint.

## SAM Deploy
SAM Deploy runs on release events.

SAM Deploy runs on Ubuntu, Windows, and MacOS runners to verify buildability for those platforms.

SAM Deploy depends on the SAM Build job.

