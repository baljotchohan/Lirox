"""
Lirox v1.1 — Memory Utilities
Handles high-level import/export for Lirox profile and learnings.
"""
import json
import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from lirox.config import PROJECT_ROOT, MIND_LEARN_FILE

def export_full_memory(output_path: str = None) -> str:
    """
    Export profile + learnings + session metadata into a single JSON package.
    """
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(Path.home(), f"lirox_memory_export_{timestamp}.json")
    
    profile_path = os.path.join(PROJECT_ROOT, "profile.json")
    
    data = {
        "format_version": "1.0",
        "exported_at": datetime.now().isoformat(),
        "profile": {},
        "learnings": {}
    }
    
    if os.path.exists(profile_path):
        try:
            with open(profile_path, "r") as f:
                data["profile"] = json.load(f)
        except Exception:
            pass
            
    if os.path.exists(MIND_LEARN_FILE):
        try:
            with open(MIND_LEARN_FILE, "r") as f:
                data["learnings"] = json.load(f)
        except Exception:
            pass
            
    with open(output_path, "w") as f:
        json.dump(data, f, indent=4)
        
    return output_path

def import_full_memory(file_path: str) -> Dict[str, Any]:
    """
    Import a Lirox memory package.
    """
    path = Path(file_path)
    if not path.exists():
        return {"success": False, "error": "File not found"}
        
    try:
        data = json.loads(path.read_text())
        if "profile" not in data or "learnings" not in data:
            return {"success": False, "error": "Invalid Lirox memory package"}
            
        profile_path = os.path.join(PROJECT_ROOT, "profile.json")
        
        # Merge profile
        if data["profile"]:
            current_profile = {}
            if os.path.exists(profile_path):
                with open(profile_path, "r") as f:
                    current_profile = json.load(f)
            
            # Update current profile with imported data, but keep some locals if needed
            # For now, let's just overwrite but maybe keep created_at?
            current_profile.update(data["profile"])
            with open(profile_path, "w") as f:
                json.dump(current_profile, f, indent=4)
                
        # Merge learnings
        if data["learnings"]:
            # For learnings, we should probably be smarter about merging
            from lirox.mind.learnings import LearningsStore
            store = LearningsStore()
            
            imported = data["learnings"]
            
            # Simple merge for now: add facts that don't exist
            facts_added = 0
            existing_facts = [f["fact"].lower() for f in store.data["user_facts"]]
            for f in imported.get("user_facts", []):
                if f["fact"].lower() not in existing_facts:
                    store.data["user_facts"].append(f)
                    facts_added += 1
            
            # Merge projects
            existing_projects = [p["name"] for p in store.data["projects"]]
            for p in imported.get("projects", []):
                if p["name"] not in existing_projects:
                    store.data["projects"].append(p)
            
            # Merge preferences
            for cat, prefs in imported.get("preferences", {}).items():
                if cat not in store.data["preferences"]:
                    store.data["preferences"][cat] = prefs
                else:
                    for p in prefs:
                        if p not in store.data["preferences"][cat]:
                            store.data["preferences"][cat].append(p)
            
            store.save()
            return {"success": True, "facts_added": facts_added, "is_full_import": True}
            
    except Exception as e:
        return {"success": False, "error": str(e)}
    
    return {"success": True}
