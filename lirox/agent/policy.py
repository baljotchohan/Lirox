class ExecutionPolicy:
    """
    Central logic for deciding if a task should auto-execute or require confirmation.
    Risk is calculated based on tool types, path access, and complexity.
    """

    def __init__(self):
        # Defaults - can be overridden by user settings in the future
        self.max_auto_steps = 5
        self.max_auto_time_mins = 2
        self.allow_terminal_auto = False
        self.safe_outputs_only = True

    def evaluate_risk(self, plan: dict) -> dict:
        """
        Evaluate the risk of executing a given plan.
        
        Returns:
            dict: {
                "auto_execute": bool,
                "requires_confirmation": bool,
                "reason": str,
                "risk_level": "low" | "medium" | "high"
            }
        """
        steps = plan.get("steps", [])
        goal = plan.get("goal", "").lower()
        
        # 1. Check for Terminal Commands (High Risk)
        has_terminal = any("terminal" in step.get("tools", []) for step in steps)
        if has_terminal:
            return {
                "auto_execute": False,
                "requires_confirmation": True,
                "reason": "Plan contains terminal commands that require manual approval.",
                "risk_level": "high"
            }

        # 2. Check for File Writes outside /outputs/ (High Risk)
        # Assuming file_io tool checks paths internally, but we can do a cursory check here
        has_suspicious_writes = any(
            "file_io" in step.get("tools", []) and "write" in step.get("task", "").lower() 
            for step in steps
        )
        # Simple heuristic: if goal mentions writing outside outputs or modifying system files
        if has_suspicious_writes and "outputs" not in goal:
            return {
                "auto_execute": False,
                "requires_confirmation": True,
                "reason": "Plan involves file modifications outside the designated outputs directory.",
                "risk_level": "medium"
            }

        # 3. Check for Complexity (Threshold based)
        if len(steps) > self.max_auto_steps:
             return {
                "auto_execute": False,
                "requires_confirmation": True,
                "reason": f"Plan is too complex ({len(steps)} steps) for auto-execution.",
                "risk_level": "medium"
            }

        # 4. Destructive keywords
        destructive = ["delete", "remove", "wipe", "format", "uninstall"]
        if any(d in goal for d in destructive):
            return {
                "auto_execute": False,
                "requires_confirmation": True,
                "reason": "Goal contains potentially destructive actions.",
                "risk_level": "high"
            }

        # 5. Default: Auto-execute for small research/read-only tasks
        return {
            "auto_execute": True,
            "requires_confirmation": False,
            "reason": "Safe research/read-only task within thresholds.",
            "risk_level": "low"
        }

policy_engine = ExecutionPolicy()
