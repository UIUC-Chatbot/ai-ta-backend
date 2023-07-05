---
include: ["**/**.py"]
---

don't approve obvious bugs.

Comment on code smells and bugs, suggest better 'best practices' ways to achieve the same result.

Suggest potential refactors if they're useful.

<!-- 
Usage 
lintrule.com

# Check against main and the a feature branch
rules check --diff main..my-feature-branch

# Run on the last 3 commits
rules check --diff HEAD~3

-->