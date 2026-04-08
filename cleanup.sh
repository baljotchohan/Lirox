#!/bin/bash

echo "🧹 Cleaning Lirox repository..."

# Delete unnecessary root-level files
rm -f index.html
rm -f script.js
rm -f styles.css
rm -f test_v0_3_results.txt
rm -f gemma-compact.Modelfile
rm -f lirox-compact.Modelfile
rm -f skills_config.json
rm -f run_hf_bnb.py
rm -f .DS_Store
rm -f .env.example

# Delete unnecessary directories
# Note: docs/ here refers to a legacy /docs directory, not the root-level .md files
rm -rf scripts/
rm -rf tests/
rm -rf docs/
rm -rf path/

# Remove Python cache files
find . -type f -name "*.pyc" -delete
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true

# Remove any backup/temp files
find . -type f -name "*.backup" -delete
find . -type f -name "*.old" -delete
find . -type f -name "*.tmp" -delete

echo ""
echo "✅ Repository cleaned!"
echo ""
echo "Kept:"
echo "  ✅ README.md, LICENSE, .gitignore"
echo "  ✅ pyproject.toml, requirements.txt"
echo "  ✅ lirox/ (all source files)"
echo "  ✅ USE_LIROX.md, COMMANDS.md, ADVANCED.md"
echo "  ✅ CONTRIBUTING.md, CHANGELOG.md"
echo ""
echo "Repository is now cleaner and more professional."
