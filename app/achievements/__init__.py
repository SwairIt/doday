"""Achievements/badges — derived from existing user data, no extra storage.

Each achievement has a stable code, an emoji, a Russian title and a check
function that returns True/False given the user's current stats. The /profile
view renders unlocked + locked badges so users can see what's coming next.
"""
