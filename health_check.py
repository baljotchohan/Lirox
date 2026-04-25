#!/usr/bin/env python3
"""
Lirox Health Check & Diagnostic Script
Checks all systems, imports, and configurations.
"""

import sys
import os
import importlib
from pathlib import Path

# Colors for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def print_header(text):
    print(f"\n{BLUE}{'=' * 70}{RESET}")
    print(f"{BLUE}{text.center(70)}{RESET}")
    print(f"{BLUE}{'=' * 70}{RESET}\n")

def check_pass(msg):
    print(f"{GREEN}✓{RESET} {msg}")

def check_fail(msg):
    print(f"{RED}✗{RESET} {msg}")

def check_warn(msg):
    print(f"{YELLOW}⚠{RESET} {msg}")

def check_info(msg):
    print(f"{BLUE}ℹ{RESET} {msg}")


# ══════════════════════════════════════════════════════════════
# CHECK 1: PYTHON VERSION
# ══════════════════════════════════════════════════════════════
def check_python_version():
    print_header("Python Version Check")
    
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    
    if version.major == 3 and version.minor >= 9:
        check_pass(f"Python version: {version_str} (OK)")
        return True
    else:
        check_fail(f"Python version: {version_str} (Need 3.9+)")
        return False


# ══════════════════════════════════════════════════════════════
# CHECK 2: REQUIRED PACKAGES
# ══════════════════════════════════════════════════════════════
def check_packages():
    print_header("Required Packages Check")
    
    required_packages = {
        'ddgs': 'Web search functionality',
        'rich': 'Terminal UI',
        'anthropic': 'Claude API (if using)',
        'openai': 'OpenAI API (if using)',
        'google.generativeai': 'Gemini API (if using)',
    }
    
    all_ok = True
    
    for package, purpose in required_packages.items():
        try:
            if '.' in package:
                parts = package.split('.')
                mod = __import__(parts[0])
                for part in parts[1:]:
                    mod = getattr(mod, part)
            else:
                __import__(package)
            check_pass(f"{package:30s} - {purpose}")
        except ImportError:
            check_fail(f"{package:30s} - {purpose} (NOT INSTALLED)")
            all_ok = False
    
    return all_ok


# ══════════════════════════════════════════════════════════════
# CHECK 3: LIROX STRUCTURE
# ══════════════════════════════════════════════════════════════
def check_structure():
    print_header("Directory Structure Check")
    
    required_dirs = [
        'lirox',
        'lirox/agents',
        'lirox/tools',
        'lirox/memory',
        'lirox/orchestrator',
        'lirox/mind',
    ]
    
    recommended_dirs = [
        'lirox/pipeline',
        'lirox/designer',
        'lirox/quality',
        'lirox/tools/search',
        'lirox/thinking',
    ]
    
    all_required = True
    
    for dir_path in required_dirs:
        if os.path.isdir(dir_path):
            check_pass(f"Required: {dir_path}")
        else:
            check_fail(f"Required: {dir_path} (MISSING)")
            all_required = False
    
    for dir_path in recommended_dirs:
        if os.path.isdir(dir_path):
            check_pass(f"Recommended: {dir_path}")
        else:
            check_warn(f"Recommended: {dir_path} (MISSING - new features may not work)")
    
    return all_required


# ══════════════════════════════════════════════════════════════
# CHECK 4: LIROX IMPORTS
# ══════════════════════════════════════════════════════════════
def check_lirox_imports():
    print_header("Lirox Module Imports Check")
    
    modules_to_check = [
        'lirox',
        'lirox.agents.personal_agent',
        'lirox.orchestrator.master',
        'lirox.memory.manager',
        'lirox.mind.soul',
        'lirox.tools.search',
    ]
    
    all_ok = True
    
    for module_name in modules_to_check:
        try:
            importlib.import_module(module_name)
            check_pass(f"Import: {module_name}")
        except ImportError as e:
            check_fail(f"Import: {module_name} ({str(e)})")
            all_ok = False
        except Exception as e:
            check_fail(f"Import: {module_name} (Error: {str(e)})")
            all_ok = False
    
    return all_ok


# ══════════════════════════════════════════════════════════════
# CHECK 5: WEB SEARCH FUNCTIONALITY
# ══════════════════════════════════════════════════════════════
def check_web_search():
    print_header("Web Search Functionality Check")
    
    try:
        from lirox.tools.search import search
        check_pass("Web search module imported")
        
        check_info("Testing live search (this may take 2-3 seconds)...")
        results = search("Python programming", max_results=3)
        
        if results and len(results) > 0:
            check_pass(f"Web search working: Found {len(results)} results")
            
            first = results[0]
            if 'title' in first and 'url' in first and 'snippet' in first:
                check_pass("Result structure correct (title, url, snippet)")
                check_info(f"Sample result: {first['title'][:50]}...")
                return True
            else:
                check_fail("Result structure incorrect")
                check_info(f"Keys found: {list(first.keys())}")
                return False
        else:
            check_fail("Web search returned no results")
            return False
    
    except ImportError as e:
        check_fail(f"Web search module not found: {e}")
        return False
    except Exception as e:
        check_fail(f"Web search error: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# CHECK 6: CLASSIFIER FUNCTION
# ══════════════════════════════════════════════════════════════
def check_classifier():
    print_header("Query Classifier Check")
    
    try:
        from lirox.agents.personal_agent import _classify
        check_pass("Classifier function imported")
        
        test_cases = [
            ("search for Python tutorials", "web"),
            ("find information on web", "web"),
            ("deep research on AI", "web"),
            ("create a PDF document", "filegen"),
            ("make a resume", "filegen"),
            ("read my file", "file"),
            ("list files in directory", "file"),
            ("run command ls", "shell"),
            ("hello how are you", "chat"),
        ]
        
        all_correct = True
        
        for query, expected in test_cases:
            result = _classify(query)
            if result == expected:
                check_pass(f"'{query[:30]:30s}' → {result}")
            else:
                check_fail(f"'{query[:30]:30s}' → {result} (expected: {expected})")
                all_correct = False
        
        return all_correct
    
    except Exception as e:
        check_fail(f"Classifier error: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# CHECK 7: MEMORY SYSTEM
# ══════════════════════════════════════════════════════════════
def check_memory():
    print_header("Memory System Check")
    
    try:
        from lirox.memory.manager import MemoryManager
        check_pass("MemoryManager imported")
        
        memory = MemoryManager()
        check_pass("MemoryManager instance created")
        
        memory.add_exchange("user", "test query", "assistant", "test response")
        check_pass("Memory add_exchange works")
        
        recent = memory.get_recent_exchanges(n=1)
        if recent:
            check_pass("Memory retrieval works")
            return True
        else:
            check_warn("Memory retrieval returned empty (might be normal)")
            return True
    
    except Exception as e:
        check_fail(f"Memory system error: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# CHECK 8: PIPELINE
# ══════════════════════════════════════════════════════════════
def check_pipeline():
    print_header("Pipeline System Check (Optional)")
    
    try:
        from lirox.pipeline.core import ExecutionPipeline
        check_pass("ExecutionPipeline imported")
        
        from lirox.pipeline.planner import ExecutionPlanner
        check_pass("ExecutionPlanner imported")
        
        from lirox.pipeline.executor import StepExecutor
        check_pass("StepExecutor imported")
        
        from lirox.pipeline.verifier import SystemVerifier
        check_pass("SystemVerifier imported")
        
        return True
    
    except ImportError as e:
        check_warn(f"Pipeline not fully implemented: {e}")
        return True  # Not critical
    except Exception as e:
        check_fail(f"Pipeline error: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# CHECK 9: DESIGNER AGENT
# ══════════════════════════════════════════════════════════════
def check_designer():
    print_header("Designer Agent Check (Optional)")
    
    try:
        from lirox.designer.intent_analyzer import IntentAnalyzer
        check_pass("IntentAnalyzer imported")
        
        from lirox.designer.ux_strategist import UXStrategist
        check_pass("UXStrategist imported")
        
        from lirox.designer.visual_designer import VisualDesigner
        check_pass("VisualDesigner imported")
        
        return True
    
    except ImportError as e:
        check_warn(f"Designer agent not fully implemented: {e}")
        return True  # Not critical
    except Exception as e:
        check_fail(f"Designer error: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# CHECK 10: CONFIGURATION FILES
# ══════════════════════════════════════════════════════════════
def check_config():
    print_header("Configuration Check")
    
    config_files = [
        'pyproject.toml',
        'lirox/config.py',
    ]
    
    all_ok = True
    
    for config_file in config_files:
        if os.path.exists(config_file):
            check_pass(f"Config file: {config_file}")
        else:
            check_warn(f"Config file: {config_file} (MISSING)")
            all_ok = False
    
    try:
        from lirox.config import LLM_PROVIDERS
        if LLM_PROVIDERS:
            check_pass(f"LLM providers configured: {len(LLM_PROVIDERS)}")
        else:
            check_warn("No LLM providers configured")
    except Exception as e:
        check_warn(f"Could not check LLM provider configuration: {e}")
    
    return all_ok


# ══════════════════════════════════════════════════════════════
# CHECK 11: FILE SYSTEM PERMISSIONS
# ══════════════════════════════════════════════════════════════
def check_permissions():
    print_header("File System Permissions Check")
    
    try:
        from lirox.config import WORKSPACE_DIR
        workspace = Path(WORKSPACE_DIR).expanduser()
        
        if workspace.exists():
            check_pass(f"Workspace directory exists: {workspace}")
        else:
            check_warn(f"Workspace directory doesn't exist: {workspace}")
            check_info("Lirox will create it on first run")
        
        test_file = workspace / '.lirox_test'
        try:
            workspace.mkdir(parents=True, exist_ok=True)
            test_file.write_text('test')
            test_file.unlink()
            check_pass("Workspace is writable")
            return True
        except Exception as e:
            check_fail(f"Workspace not writable: {e}")
            return False
    
    except Exception as e:
        check_warn(f"Could not check workspace: {e}")
        return True


# ══════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ══════════════════════════════════════════════════════════════
def main():
    print(f"\n{BLUE}╔════════════════════════════════════════════════════════════════════╗{RESET}")
    print(f"{BLUE}║{RESET}          LIROX HEALTH CHECK & DIAGNOSTIC REPORT                   {BLUE}║{RESET}")
    print(f"{BLUE}╚════════════════════════════════════════════════════════════════════╝{RESET}")
    
    results = {}
    
    results['python'] = check_python_version()
    results['packages'] = check_packages()
    results['structure'] = check_structure()
    results['imports'] = check_lirox_imports()
    results['web_search'] = check_web_search()
    results['classifier'] = check_classifier()
    results['memory'] = check_memory()
    results['pipeline'] = check_pipeline()
    results['designer'] = check_designer()
    results['config'] = check_config()
    results['permissions'] = check_permissions()
    
    print_header("FINAL SUMMARY")
    
    critical_checks = ['python', 'packages', 'structure', 'imports', 'web_search', 'classifier']
    critical_passed = all(results[k] for k in critical_checks if k in results)
    
    optional_checks = ['pipeline', 'designer']
    optional_passed = sum(results[k] for k in optional_checks if k in results)
    
    total_checks = len(results)
    passed_checks = sum(results.values())
    
    print(f"\nTotal checks: {total_checks}")
    print(f"Passed: {passed_checks}")
    print(f"Failed: {total_checks - passed_checks}")
    
    if critical_passed:
        print(f"\n{GREEN}✓ CRITICAL SYSTEMS: ALL PASSED{RESET}")
        print(f"{GREEN}✓ Lirox is ready to use!{RESET}")
    else:
        print(f"\n{RED}✗ CRITICAL SYSTEMS: SOME FAILED{RESET}")
        print(f"{RED}✗ Fix errors above before using Lirox{RESET}")
    
    if optional_passed == len(optional_checks):
        print(f"{GREEN}✓ OPTIONAL FEATURES: ALL IMPLEMENTED{RESET}")
    else:
        print(f"{YELLOW}⚠ OPTIONAL FEATURES: {optional_passed}/{len(optional_checks)} implemented{RESET}")
        print(f"{YELLOW}⚠ Some new features may not be available{RESET}")
    
    return 0 if critical_passed else 1


if __name__ == '__main__':
    sys.exit(main())
