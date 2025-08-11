## Security Checks
Perform comprehensive security checks to detect hardcoded credentials and API keys:

### Search Patterns
Search for these patterns across ALL files (excluding .aws-sam/, .git/, __pycache__/):
- AWS Access Keys: `AKIA[0-9A-Z]{16}`
- AWS Secret Keys: `[A-Za-z0-9+/]{40}`
- Bedrock API Keys: `AWS_BEARER_TOKEN_BEDROCK|ABSKQmVkcm9ja0FQSUtleS`
- OpenAI API Keys: `sk-[a-zA-Z0-9]{32,}`
- Anthropic API Keys: `sk-ant-[a-zA-Z0-9-]{32,}`
- Generic API Keys: `api_key.*[=:]\s*['\"][^'\"]{20,}['\"]`
- Bearer Tokens: `Bearer\s+[A-Za-z0-9+/=]{20,}`
- Private Keys: `-----BEGIN.*PRIVATE KEY-----`

### File Types to Check
- Source code: `*.py`, `*.js`, `*.ts`, `*.java`, `*.go`
- Scripts: `*.sh`, `*.bash`, `*.ps1`, `*.bat`
- Configuration: `*.json`, `*.yaml`, `*.yml`, `*.env`, `*.config`, `*.ini`
- Documentation: `*.md`, `*.txt`, `*.rst`

### Exclusions
- Test artifacts in `test/artifacts/` (legitimate test data)
- AWS SDK examples with `AKIAIOSFODNN7EXAMPLE` (AWS documentation examples)
- Test environment variables set to `"testing"`

### Action on Detection
If ANY hardcoded credentials are found:
1. STOP the workflow immediately
2. Create a security report in planning/ directory
3. List all files containing credentials
4. Do NOT proceed with deployment or commits

