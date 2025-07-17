# Amazon Q Developer Profiles

This directory contains Amazon Q Developer profiles for the Thingpress project. These profiles help Amazon Q understand the project context and provide more relevant assistance.

## Usage

To use these profiles with Amazon Q Developer:

1. Copy the contents of the profile file you want to use
2. Create a new profile in your local Amazon Q Developer settings
3. Paste the content into the profile
4. Save and activate the profile

Alternatively, you can configure Amazon Q to automatically use these profiles by setting up a symbolic link:

```bash
# Create a symbolic link from your local Amazon Q profiles directory to this repository
ln -s /path/to/repo/.amazonq/prompts/thingpress-profile.md ~/.aws/amazonq/prompts/thingpress-profile.md
```

## Available Profiles

- `thingpress-profile.md`: General development profile for the Thingpress project
